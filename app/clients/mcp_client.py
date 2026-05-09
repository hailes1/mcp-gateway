from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import UpstreamServerSettings
from app.exceptions import McpHttpError


class McpHttpClient:
    def __init__(self, server: UpstreamServerSettings, client: httpx.AsyncClient | None = None) -> None:
        self._server = server
        self._client = client or httpx.AsyncClient(timeout=15.0)
        self._owns_client = client is None
        self._request_id = 0
        self._initialized = False

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {"ok": True}

        response = await self._request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "mcp-gateway", "version": "0.1.0"},
            },
        )
        self._initialized = True
        return response

    async def list_tools(self) -> list[dict[str, Any]]:
        response = await self._request("tools/list", {})
        tools = response.get("tools")
        if not isinstance(tools, list):
            raise McpHttpError(f"Invalid tools/list response from {self._server.name}")
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        response = await self._request("tools/call", {"name": tool_name, "arguments": arguments})
        return response

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        http_response = await self._post(method, params)

        payload = _parse(http_response)
        result = payload.get("result")
        return result

    async def _post(self, method: str, params: dict[str, Any]) -> httpx.Response:
        try:
            http_response = await self._client.post(
                self._server.url,
                headers={
                    "content-type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": self._request_id,
                    "method": method,
                    "params": params,
                },
            )
            http_response.raise_for_status()
            return http_response
        except httpx.HTTPStatusError as exc:
            raise McpHttpError(
                f"Upstream MCP server '{self._server.name}' returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise McpHttpError(f"Request to upstream MCP server '{self._server.name}' failed: {exc}") from exc


def _parse(response: httpx.Response) -> dict[str, Any]:
    payload: Any | None = None

    for chunk in response.text.strip().split("\n\n"):
        data = "\n".join(line[5:].strip() for line in chunk.splitlines() if line.startswith("data:"))
        if data:
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise McpHttpError("Invalid SSE payload from upstream MCP server")
            break

    if payload is None:
        payload = response.json()
        if not isinstance(payload, dict):
            raise McpHttpError("Invalid non-object JSON response from upstream MCP server")

    return payload