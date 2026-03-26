# app/adapters/investor_tool_adapter.py
from __future__ import annotations
from typing import Any
from app.types import ToolAdapter
from app.clients.investor import InvestorMcpClient


class InvestorToolAdapter(ToolAdapter):
    def __init__(self, client: InvestorMcpClient, upstream_tool_name: str) -> None:
        self.client = client
        self.upstream_tool_name = upstream_tool_name
        self.name = f"investor.{upstream_tool_name}"

    async def execute(self, input_data: Any) -> Any:
        args = input_data if isinstance(input_data, dict) else {}
        return await self.client.call_tool(self.upstream_tool_name, args)