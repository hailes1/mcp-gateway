from __future__ import annotations

from typing import Any

from app.types import ToolAdapter, ToolDefinition


class AdditionToolAdapter(ToolAdapter):
    definition = ToolDefinition(
        name="math.add",
        description="Add two numbers and return the sum.",
        source="local",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    )

    async def execute(self, input_data: Any) -> dict[str, int | float]:
        if not isinstance(input_data, dict):
            raise ValueError("Invalid input for math.add: expected an object with numeric 'a' and 'b' fields")

        a = input_data.get("a")
        b = input_data.get("b")
        if not isinstance(a, int | float) or not isinstance(b, int | float):
            raise ValueError("Invalid input for math.add: 'a' and 'b' must both be numbers")

        return {"a": a, "b": b, "sum": a + b}