from __future__ import annotations

from dataclasses import asdict
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.tools.addition import AdditionToolAdapter
from app.adapters.mcp.mcp import connect_adapter, register
from app.config import GatewaySettings, UpstreamServerSettings, load_settings
from app.exceptions import ToolNotRegisteredError
from app.registry import ToolRegistry
from app.types import GatewayResult


logger = logging.getLogger(__name__)


class GatewayCall(BaseModel):
    tool: str = Field(min_length=1)
    input: Any = Field(default_factory=dict)


class ToolDefinitionResponse(BaseModel):
    name: str = Field(
        description="Stable tool identifier used in /mcp.", examples=["math.add"]
    )
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


class AdapterRegistrationRequest(BaseModel):
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    type: str = Field(default="http")


class AdapterInfo(BaseModel):
    name: str
    url: str
    type: str
    tool_count: int
    status: str


class AdaptersResponse(BaseModel):
    adapters: list[AdapterInfo]


def build_registry(settings: GatewaySettings) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(AdditionToolAdapter())

    return registry


def create_app(settings: GatewaySettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    app = FastAPI(title="MCP Gateway", version="0.1.0", lifespan=create_lifespan(resolved_settings))
    app.state.gateway_settings = resolved_settings
    app.state.registry = build_registry(resolved_settings)
    app.state.upstream_clients = {}
    app.state.upstream_failed = []
    app.state.adapter_store = {}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "mcp-gateway",
            "upstreams": {
                "ok": sorted(app.state.upstream_clients.keys()),
                "failed": sorted(app.state.upstream_failed),
            },
            "registered_tools": [tool.name for tool in app.state.registry.list_definitions()],
        }

    async def execute_tool(tool_name: str, input_data: Any) -> JSONResponse:
        tool = app.state.registry.get(tool_name)
        if tool is None:
            logger.warning("Unknown tool requested", extra={"tool": tool_name})
            return gateway_response(
                GatewayResult(
                    tool=tool_name, ok=False, error=str(ToolNotRegisteredError(tool_name))
                ),
                status_code=404,
            )

        try:
            logger.info("Executing tool", extra={"tool": tool_name})
            data = await tool.execute(input_data)
            return gateway_response(GatewayResult(tool=tool_name, ok=True, data=data))
        except ValueError as exc:
            logger.info("Tool input rejected", extra={"tool": tool_name, "error": str(exc)})
            return gateway_response(
                GatewayResult(tool=tool_name, ok=False, error=str(exc)), status_code=400
            )
        except Exception:  # pragma: no cover
            logger.exception("Tool execution failed", extra={"tool": tool_name})
            return gateway_response(
                GatewayResult(tool=tool_name, ok=False, error="Unknown error"), status_code=500
            )

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
            tools=[
                ToolDefinitionResponse.model_validate(asdict(tool))
                for tool in app.state.registry.list_definitions()
            ]
        )

    @control_router.get(
        "/adapters", response_model=AdaptersResponse, summary="List registered adapters"
    )
    async def list_adapters() -> AdaptersResponse:
        adapters = []
        for name, server in app.state.adapter_store.items():
            tool_count = sum(
                1 for t in app.state.registry.list_definitions() if t.source == f"remote:{name}"
            )
            status = "failed" if name in app.state.upstream_failed else "ok"
            adapters.append(
                AdapterInfo(
                    name=name,
                    url=server.url,
                    type=server.type,
                    tool_count=tool_count,
                    status=status,
                )
            )
        return AdaptersResponse(adapters=sorted(adapters, key=lambda a: a.name))

    @control_router.post("/adapters", summary="Register a new upstream adapter")
    async def register_adapter(req: AdapterRegistrationRequest) -> JSONResponse:
        if req.name in app.state.adapter_store:
            return JSONResponse(
                status_code=409,
                content={"error": f"Adapter '{req.name}' is already registered."},
            )
        server = UpstreamServerSettings(name=req.name, url=req.url, type=req.type)
        app.state.adapter_store[req.name] = server
        client = await connect_adapter(app.state.registry, server)
        if client is not None:
            app.state.upstream_clients[req.name] = client
            registered_tools = [
                t.name
                for t in app.state.registry.list_definitions()
                if t.source == f"remote:{req.name}"
            ]
            return JSONResponse(
                status_code=201,
                content={"name": req.name, "status": "ok", "registered_tools": registered_tools},
            )
        app.state.upstream_failed.append(req.name)
        return JSONResponse(
            status_code=201,
            content={"name": req.name, "status": "failed", "registered_tools": []},
        )

    @control_router.delete("/adapters/{adapter_name}", summary="Remove an upstream adapter")
    async def deregister_adapter(adapter_name: str) -> JSONResponse:
        if adapter_name not in app.state.adapter_store:
            return JSONResponse(
                status_code=404,
                content={"error": f"Adapter '{adapter_name}' not found."},
            )
        del app.state.adapter_store[adapter_name]
        app.state.registry.deregister_prefix(adapter_name)
        client = app.state.upstream_clients.pop(adapter_name, None)
        if client is not None:
            await client.aclose()
        if adapter_name in app.state.upstream_failed:
            app.state.upstream_failed.remove(adapter_name)
        return JSONResponse(status_code=200, content={"ok": True})

    @data_router.post("/mcp")
    async def mcp_router_call(call: GatewayCall) -> JSONResponse:
        return await execute_tool(call.tool, call.input)

    @data_router.post("/adapters/{adapter_name}/mcp")
    async def adapter_mcp_call(adapter_name: str, call: GatewayCall) -> JSONResponse:
        requested_tool = call.tool
        qualified_tool = (
            requested_tool if "." in requested_tool else f"{adapter_name}.{requested_tool}"
        )
        if not qualified_tool.startswith(f"{adapter_name}."):
            logger.warning(
                "Adapter tool mismatch",
                extra={
                    "adapter": adapter_name,
                    "requested_tool": requested_tool,
                    "qualified_tool": qualified_tool,
                },
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

    app.include_router(control_router)
    app.include_router(data_router)

    return app


def gateway_response(result: GatewayResult, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=asdict(result))


def create_lifespan(settings: GatewaySettings) -> Any:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        clients, failed = await register(app.state.registry, settings)
        app.state.upstream_clients = clients
        app.state.upstream_failed = failed
        app.state.adapter_store = {s.name: s for s in settings.upstream_servers}
        try:
            yield
        finally:
            for client in app.state.upstream_clients.values():
                await client.aclose()

    return lifespan


app = create_app()
