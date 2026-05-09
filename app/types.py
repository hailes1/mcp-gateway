from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    source: str
    input_schema: dict[str, Any]


@dataclass(slots=True)
class GatewayResult:
    tool: str
    ok: bool
    data: Any | None = None
    error: str | None = None


class ToolAdapter(Protocol):
    definition: ToolDefinition

    async def execute(self, input_data: Any) -> Any: ...
