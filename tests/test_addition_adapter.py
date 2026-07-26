from __future__ import annotations

import asyncio

import pytest

from app.adapters.tools.addition import AdditionToolAdapter
from app.exceptions import ToolInputError


def test_addition_happy_path() -> None:
    adapter = AdditionToolAdapter()

    result = asyncio.run(adapter.execute({"a": 2, "b": 3.5}))

    assert result == {"a": 2, "b": 3.5, "sum": 5.5}


def test_addition_rejects_booleans() -> None:
    adapter = AdditionToolAdapter()

    with pytest.raises(ToolInputError):
        asyncio.run(adapter.execute({"a": True, "b": 2}))
