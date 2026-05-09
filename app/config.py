from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class UpstreamServerSettings:
    name: str
    url: str
    type: str = "http"


@dataclass(slots=True)
class GatewaySettings:
    sample_tool_name: str = "math.add"
    upstream_servers: tuple[UpstreamServerSettings, ...] = ()


def load_settings() -> GatewaySettings:
    return GatewaySettings(
        upstream_servers=(
            UpstreamServerSettings(
                name="langchain-agent",
                url="https://docs.langchain.com/mcp",
                type="http",
            ),
        )
    )