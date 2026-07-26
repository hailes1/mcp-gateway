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

    def deregister_prefix(self, prefix: str) -> int:
        """Remove all tools whose name is exactly `prefix` or starts with `prefix.`."""
        to_remove = [
            name for name in self._tools if name == prefix or name.startswith(f"{prefix}.")
        ]
        for name in to_remove:
            del self._tools[name]
        return len(to_remove)
