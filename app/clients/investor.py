from __future__ import annotations
import uuid
from typing import Any
import httpx


class InvestorMcpClient:
    def __init__(self, base_url: str, auth_header: str | None = None) -> None:
        self.base_url = base_url
        self.auth_header = auth_header
        self._session_id: str | None = None

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        headers: dict[str, str] = {"content-type": "application/json"}
        if self.auth_header:
            headers["authorization"] = self.auth_header
        if self._session_id:
            headers["mcp-session-id"] = self._session_id

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Some MCP HTTP servers return/set session metadata in headers/result.
        self._session_id = resp.headers.get("mcp-session-id", self._session_id)

        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        return data.get("result")

    async def initialize(self) -> Any:
        return await self._rpc("initialize", {"clientInfo": {"name": "mcp-gateway", "version": "0.1.0"}})

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._rpc("tools/list")
        return result.get("tools", []) if isinstance(result, dict) else []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        return await self._rpc("tools/call", {"name": tool_name, "arguments": arguments})