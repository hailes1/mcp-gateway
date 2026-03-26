from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.adapters.investor import InvestorToolAdapter
from app.adapters.jsonplaceholder import JsonPlaceholderPostsAdapter
from app.clients.investor import InvestorMcpClient
from app.registry import ToolRegistry
from app.types import GatewayResult


class GatewayCall(BaseModel):
    tool: str = Field(min_length=1)
    input: Any = Field(default_factory=dict)


app = FastAPI(title="mcp-gateway", version="0.1.0")
registry = ToolRegistry()

investor_client = InvestorMcpClient(base_url="https://investor.ferdousbhai.com/mcp")
registry.register(InvestorToolAdapter(investor_client, "example_tool"))
registry.register(JsonPlaceholderPostsAdapter())


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "mcp-gateway"}


@app.get("/tools")
async def list_tools() -> dict[str, list[str]]:
    return {"tools": registry.list()}


@app.post("/gateway/call")
async def gateway_call(call: GatewayCall) -> dict[str, Any]:
    tool = registry.get(call.tool)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{call.tool}' is not registered.")

    try:
        data = await tool.execute(call.input)
        result = GatewayResult(tool=call.tool, ok=True, data=data)
        return result.__dict__
    except ValueError as exc:
        result = GatewayResult(tool=call.tool, ok=False, error=str(exc))
        raise HTTPException(status_code=400, detail=result.__dict__) from exc
    except Exception as exc:  # pragma: no cover
        result = GatewayResult(tool=call.tool, ok=False, error="Unknown error")
        raise HTTPException(status_code=500, detail=result.__dict__) from exc
