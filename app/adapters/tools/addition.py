from __future__ import annotations

from typing import Any

from app.exceptions import invalid_addition_number_error, invalid_addition_payload_error
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
            raise invalid_addition_payload_error()

        a = input_data.get("a")
        b = input_data.get("b")

        if (
            not isinstance(a, int | float)
            or not isinstance(b, int | float)
            or isinstance(a, bool)
            or isinstance(b, bool)
        ):
            raise invalid_addition_number_error()

        return {"a": a, "b": b, "sum": a + b}
