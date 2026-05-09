from __future__ import annotations

from dataclasses import asdict
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI
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
    name: str = Field(description="Stable tool identifier used in /gateway/call.", examples=["math.add"])
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

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "mcp-gateway",
            "registered_tools": [tool.name for tool in app.state.registry.list_definitions()],
        }

    @app.get(
        "/tools",
        response_model=ToolsResponse,
        summary="List registered tools",
        response_description="Registered gateway tools with descriptions and input schemas.",
    )
    async def list_tools() -> ToolsResponse:
        return ToolsResponse(
            tools=[ToolDefinitionResponse.model_validate(asdict(tool)) for tool in app.state.registry.list_definitions()]
        )

    @app.post("/gateway/call")
    async def gateway_call(call: GatewayCall) -> JSONResponse:
        tool = app.state.registry.get(call.tool)
        if tool is None:
            logger.warning("Unknown tool requested", extra={"tool": call.tool})
            return gateway_response(
                GatewayResult(tool=call.tool, ok=False, error=str(ToolNotRegisteredError(call.tool))),
                status_code=404,
            )

        try:
            logger.info("Executing tool", extra={"tool": call.tool})
            data = await tool.execute(call.input)
            return gateway_response(GatewayResult(tool=call.tool, ok=True, data=data))
        except ValueError as exc:
            logger.info("Tool input rejected", extra={"tool": call.tool, "error": str(exc)})
            return gateway_response(GatewayResult(tool=call.tool, ok=False, error=str(exc)), status_code=400)
        except Exception:  # pragma: no cover
            logger.exception("Tool execution failed", extra={"tool": call.tool})
            return gateway_response(GatewayResult(tool=call.tool, ok=False, error="Unknown error"), status_code=500)

    return app


def gateway_response(result: GatewayResult, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=asdict(result))


def create_lifespan(settings: GatewaySettings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await register(app.state.registry, settings)
        yield

    return lifespan


app = create_app()
