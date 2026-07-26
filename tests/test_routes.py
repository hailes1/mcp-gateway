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
        response = client.post(
            "/adapters/math/mcp", json={"tool": "add", "input": {"a": 2, "b": 5}}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "math.add"
    assert body["data"]["sum"] == 7


def test_adapter_route_rejects_mismatched_tool() -> None:
    with _client() as client:
        response = client.post(
            "/adapters/langchain-agent/mcp", json={"tool": "math.add", "input": {"a": 1, "b": 2}}
        )

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert "does not belong to adapter" in body["error"]


def test_gateway_call_alias_still_works() -> None:
    with _client() as client:
        response = client.post(
            "/gateway/call", json={"tool": "math.add", "input": {"a": 6, "b": 1}}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["sum"] == 7


def test_health_includes_upstream_status() -> None:
    with _client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "upstreams" in body
    assert "ok" in body["upstreams"]
    assert "failed" in body["upstreams"]


def test_list_adapters_starts_empty() -> None:
    with _client() as client:
        response = client.get("/adapters")

    assert response.status_code == 200
    body = response.json()
    assert body["adapters"] == []


def test_register_adapter_fails_gracefully_and_is_listed() -> None:
    with _client() as client:
        response = client.post(
            "/adapters",
            json={"name": "test-server", "url": "http://localhost:19999/mcp"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "test-server"
    assert body["status"] in {"ok", "failed"}


def test_register_duplicate_adapter_is_rejected() -> None:
    with _client() as client:
        client.post("/adapters", json={"name": "dup-server", "url": "http://localhost:19999/mcp"})
        response = client.post(
            "/adapters", json={"name": "dup-server", "url": "http://localhost:19999/mcp"}
        )

    assert response.status_code == 409
    assert "already registered" in response.json()["error"]


def test_deregister_missing_adapter_returns_404() -> None:
    with _client() as client:
        response = client.delete("/adapters/nonexistent")

    assert response.status_code == 404


def test_register_then_deregister_adapter() -> None:
    with _client() as client:
        client.post("/adapters", json={"name": "tmp-server", "url": "http://localhost:19999/mcp"})
        assert any(a["name"] == "tmp-server" for a in client.get("/adapters").json()["adapters"])

        response = client.delete("/adapters/tmp-server")
        assert response.status_code == 200

        assert not any(
            a["name"] == "tmp-server" for a in client.get("/adapters").json()["adapters"]
        )
