from __future__ import annotations

import logging
from typing import Any

from app.clients.mcp_client import McpHttpClient
from app.config import GatewaySettings, UpstreamServerSettings
from app.exceptions import McpHttpError, ToolInputError, UpstreamToolDefinitionError, UpstreamToolError
from app.registry import ToolRegistry
from app.types import ToolAdapter, ToolDefinition


logger = logging.getLogger(__name__)


class RemoteMcpToolAdapter(ToolAdapter):
    def __init__(self, server: UpstreamServerSettings, definition: ToolDefinition, client: McpHttpClient) -> None:
        self.definition = definition
        self._server = server
        self._client = client
        self._upstream_tool_name = definition.name.removeprefix(f"{server.name}.")

    async def execute(self, input_data: Any) -> Any:
        if not isinstance(input_data, dict):
            raise ToolInputError(f"Invalid input for {self.definition.name}: expected an object")

        try:
            return await self._client.call_tool(self._upstream_tool_name, input_data)
        except McpHttpError as exc:
            raise UpstreamToolError(self._server.name, self.definition.name, str(exc)) from exc


async def register(registry: ToolRegistry, settings: GatewaySettings) -> None:
    for server in settings.upstream_servers:
        if server.type != "http":
            logger.warning("Skipping unsupported upstream server type", extra={"server": server.name, "type": server.type})
            continue

        client = McpHttpClient(server)
        try:
            await client.initialize()
            for tool in await client.list_tools():
                registry.register(_build_adapter(server, tool, client))
        except Exception:
            logger.exception("Failed to register upstream MCP server", extra={"server": server.name, "url": server.url})
            await client.aclose()


def _build_adapter(
    server: UpstreamServerSettings,
    tool_payload: dict[str, Any],
    client: McpHttpClient,
) -> RemoteMcpToolAdapter:
    tool_name = tool_payload.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise UpstreamToolDefinitionError(server.name)

    description = tool_payload.get("description")
    input_schema = tool_payload.get("inputSchema")
    if not isinstance(description, str):
        description = f"Proxy for {tool_name} from {server.name}."
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object"}

    definition = ToolDefinition(
        name=f"{server.name}.{tool_name}",
        description=description,
        source=f"remote:{server.name}",
        input_schema=input_schema,
    )
    return RemoteMcpToolAdapter(server, definition, client)