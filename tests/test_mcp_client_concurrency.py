from __future__ import annotations

import asyncio
import json

import httpx

from app.clients.mcp_client import McpHttpClient
from app.config import UpstreamServerSettings


def test_concurrent_requests_keep_response_id_alignment() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        # Request body is standard JSON-RPC payload.
        message = json.loads(request.content.decode("utf-8"))
        request_id = message["id"]

        if request_id == 1:
            await asyncio.sleep(0.05)

        return httpx.Response(
            status_code=200,
            json={"jsonrpc": "2.0", "id": request_id, "result": {"echo": request_id}},
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            client = McpHttpClient(
                server=UpstreamServerSettings(name="mock", url="http://test/mcp"),
                client=http_client,
            )
            client._initialized = True  # bypass initialize for this unit test

            first, second = await asyncio.gather(
                client.call_tool("echo", {"v": 1}),
                client.call_tool("echo", {"v": 2}),
            )

            assert {first["echo"], second["echo"]} == {1, 2}

    asyncio.run(run_test())
