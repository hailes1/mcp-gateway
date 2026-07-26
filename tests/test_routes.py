from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import GatewaySettings
from app.main import create_app


def _client() -> TestClient:
    app = create_app(GatewaySettings(upstream_servers=()))
    return TestClient(app)


def test_mcp_route_executes_tool() -> None:
    with _client() as client:
        response = client.post("/mcp", json={"tool": "math.add", "input": {"a": 3, "b": 4}})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "math.add"
    assert body["data"]["sum"] == 7


def test_adapter_route_executes_prefixed_tool() -> None:
    with _client() as client:
        response = client.post("/adapters/math/mcp", json={"tool": "add", "input": {"a": 2, "b": 5}})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "math.add"
    assert body["data"]["sum"] == 7


def test_adapter_route_rejects_mismatched_tool() -> None:
    with _client() as client:
        response = client.post("/adapters/langchain-agent/mcp", json={"tool": "math.add", "input": {"a": 1, "b": 2}})

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert "does not belong to adapter" in body["error"]


def test_gateway_call_alias_still_works() -> None:
    with _client() as client:
        response = client.post("/gateway/call", json={"tool": "math.add", "input": {"a": 6, "b": 1}})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["sum"] == 7
