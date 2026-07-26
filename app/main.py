from __future__ import annotations

from dataclasses import asdict
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.tools.addition import AdditionToolAdapter
from app.adapters.mcp.mcp import register
from app.config import GatewaySettings, load_settings
from app.exceptions import ToolNotRegisteredError
from app.registry import ToolRegistry
from app.types import GatewayResult


logger = logging.getLogger(__name__)


class GatewayCall(BaseModel):
    tool: str = Field(min_length=1)
    input: Any = Field(default_factory=dict)


class ToolDefinitionResponse(BaseModel):
    name: str = Field(description="Stable tool identifier used in /mcp or /gateway/call.", examples=["math.add"])
    description: str = Field(
        description="Human-readable summary of what the tool does.",
        examples=["Add two numbers and return the sum."],
    )
    source: str = Field(description="Where the tool is implemented.", examples=["local"])
    input_schema: dict[str, Any] = Field(
        description="JSON Schema-like shape describing the expected input payload for the tool.",
        examples=[
            {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            }
        ],
    )


class ToolsResponse(BaseModel):
    tools: list[ToolDefinitionResponse] = Field(
        description="All tools currently registered in the gateway.",
        examples=[
            [
                {
                    "name": "math.add",
                    "description": "Add two numbers and return the sum.",
                    "source": "local",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number"},
                            "b": {"type": "number"},
                        },
                        "required": ["a", "b"],
                        "additionalProperties": False,
                    },
                }
            ]
        ],
    )


def build_registry(settings: GatewaySettings) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(AdditionToolAdapter())

    return registry


def create_app(settings: GatewaySettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    app = FastAPI(title="MCP Gateway", version="0.1.0", lifespan=create_lifespan(resolved_settings))
    app.state.gateway_settings = resolved_settings
    app.state.registry = build_registry(resolved_settings)
    app.state.upstream_clients = []

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "mcp-gateway",
            "registered_tools": [tool.name for tool in app.state.registry.list_definitions()],
        }

    async def execute_tool(tool_name: str, input_data: Any) -> JSONResponse:
        tool = app.state.registry.get(tool_name)
        if tool is None:
            logger.warning("Unknown tool requested", extra={"tool": tool_name})
            return gateway_response(
                GatewayResult(tool=tool_name, ok=False, error=str(ToolNotRegisteredError(tool_name))),
                status_code=404,
            )

        try:
            logger.info("Executing tool", extra={"tool": tool_name})
            data = await tool.execute(input_data)
            return gateway_response(GatewayResult(tool=tool_name, ok=True, data=data))
        except ValueError as exc:
            logger.info("Tool input rejected", extra={"tool": tool_name, "error": str(exc)})
            return gateway_response(GatewayResult(tool=tool_name, ok=False, error=str(exc)), status_code=400)
        except Exception:  # pragma: no cover
            logger.exception("Tool execution failed", extra={"tool": tool_name})
            return gateway_response(GatewayResult(tool=tool_name, ok=False, error="Unknown error"), status_code=500)

    control_router = APIRouter()
    data_router = APIRouter()

    @control_router.get(
        "/tools",
        response_model=ToolsResponse,
        summary="List registered tools",
        response_description="Registered gateway tools with descriptions and input schemas.",
    )
    async def list_tools() -> ToolsResponse:
        return ToolsResponse(
            tools=[ToolDefinitionResponse.model_validate(asdict(tool)) for tool in app.state.registry.list_definitions()]
        )

    @data_router.post("/mcp")
    async def mcp_router_call(call: GatewayCall) -> JSONResponse:
        return await execute_tool(call.tool, call.input)

    @data_router.post("/adapters/{adapter_name}/mcp")
    async def adapter_mcp_call(adapter_name: str, call: GatewayCall) -> JSONResponse:
        requested_tool = call.tool
        qualified_tool = requested_tool if "." in requested_tool else f"{adapter_name}.{requested_tool}"
        if not qualified_tool.startswith(f"{adapter_name}."):
            logger.warning(
                "Adapter tool mismatch",
                extra={"adapter": adapter_name, "requested_tool": requested_tool, "qualified_tool": qualified_tool},
            )
            return gateway_response(
                GatewayResult(
                    tool=qualified_tool,
                    ok=False,
                    error=f"Tool '{requested_tool}' does not belong to adapter '{adapter_name}'.",
                ),
                status_code=400,
            )
        return await execute_tool(qualified_tool, call.input)

    # Backward-compatible alias while callers migrate to /mcp.
    @data_router.post("/gateway/call")
    async def gateway_call_legacy(call: GatewayCall) -> JSONResponse:
        return await execute_tool(call.tool, call.input)

    app.include_router(control_router)
    app.include_router(data_router)

    return app


def gateway_response(result: GatewayResult, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=asdict(result))


def create_lifespan(settings: GatewaySettings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.upstream_clients = await register(app.state.registry, settings)
        try:
            yield
        finally:
            for client in app.state.upstream_clients:
                await client.aclose()

    return lifespan


app = create_app()
