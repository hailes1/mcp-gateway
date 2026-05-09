from __future__ import annotations

from app.types import ToolAdapter, ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolAdapter] = {}

    def register(self, tool: ToolAdapter) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> ToolAdapter | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [self._tools[name].definition for name in sorted(self._tools.keys())]
