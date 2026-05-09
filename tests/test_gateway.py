from __future__ import annotations

from fastapi.testclient import TestClient

from app.adapters.addition import AdditionToolAdapter
from app.config import GatewaySettings
from app.main import create_app


def make_client(settings: GatewaySettings) -> TestClient:
    return TestClient(create_app(settings))


def test_tools_endpoint_returns_structured_metadata() -> None:
    client = make_client(GatewaySettings())

    response = client.get("/tools")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "tools": [
            {
                "name": "math.add",
                "description": "Add two numbers and return the sum.",
                "source": "local",
                "input_schema": AdditionToolAdapter.definition.input_schema,
            }
        ]
    }


def test_tools_openapi_schema_is_descriptive() -> None:
    client = make_client(GatewaySettings())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    tools_get = schema["paths"]["/tools"]["get"]
    assert tools_get["summary"] == "List registered tools"
    assert tools_get["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ToolsResponse"
    }

    tools_response = schema["components"]["schemas"]["ToolsResponse"]
    assert tools_response["properties"]["tools"]["description"] == "All tools currently registered in the gateway."
    assert tools_response["properties"]["tools"]["items"] == {
        "$ref": "#/components/schemas/ToolDefinitionResponse"
    }


def test_unknown_tool_returns_gateway_error_envelope() -> None:
    client = make_client(GatewaySettings())

    response = client.post("/gateway/call", json={"tool": "missing.tool", "input": {}})

    assert response.status_code == 404
    assert response.json() == {
        "tool": "missing.tool",
        "ok": False,
        "data": None,
        "error": "Tool 'missing.tool' is not registered.",
    }


def test_invalid_adapter_input_keeps_error_envelope() -> None:
    client = make_client(GatewaySettings())

    response = client.post(
        "/gateway/call",
        json={"tool": "math.add", "input": {"a": 2, "b": "bad"}},
    )

    assert response.status_code == 400
    assert response.json() == {
        "tool": "math.add",
        "ok": False,
        "data": None,
        "error": "Invalid input for math.add: 'a' and 'b' must both be numbers",
    }


def test_health_reflects_configured_registry() -> None:
    client = make_client(GatewaySettings())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "mcp-gateway",
        "registered_tools": ["math.add"],
    }


def test_successful_call_uses_gateway_envelope() -> None:
    client = make_client(GatewaySettings())

    response = client.post(
        "/gateway/call",
        json={"tool": "math.add", "input": {"a": 2, "b": 4}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tool": "math.add",
        "ok": True,
        "data": {"a": 2, "b": 4, "sum": 6},
        "error": None,
    }