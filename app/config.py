from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class UpstreamServerSettings:
    name: str
    url: str
    type: str = "http"


@dataclass(slots=True, frozen=True)
class GatewaySettings:
    upstream_servers: tuple[UpstreamServerSettings, ...] = ()
    log_level: str = "INFO"
    port: int = 8080


def load_settings() -> GatewaySettings:
    return GatewaySettings(
        upstream_servers=_load_upstream_servers(),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        port=int(os.environ.get("PORT", "8080")),
    )


def _load_upstream_servers() -> tuple[UpstreamServerSettings, ...]:
    """Read upstream server definitions from MCP_UPSTREAM_SERVERS (JSON array).

    Example value:
        [{"name": "my-server", "url": "http://my-server:8000/mcp", "type": "http"}]
    """
    raw = os.environ.get("MCP_UPSTREAM_SERVERS", "").strip()
    if not raw:
        return ()
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    servers: list[UpstreamServerSettings] = []
    for entry in entries:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and isinstance(entry.get("url"), str)
        ):
            servers.append(
                UpstreamServerSettings(
                    name=entry["name"],
                    url=entry["url"],
                    type=entry.get("type", "http"),
                )
            )
    return tuple(servers)
