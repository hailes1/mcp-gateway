from __future__ import annotations

from app.types import ToolAdapter


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolAdapter] = {}

    def register(self, tool: ToolAdapter) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolAdapter | None:
        return self._tools.get(name)

    def list(self) -> list[str]:
        return sorted(self._tools.keys())
