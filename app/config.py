from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GatewaySettings:
    sample_tool_name: str = "math.add"


def load_settings() -> GatewaySettings:
    return GatewaySettings()