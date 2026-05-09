from __future__ import annotations


class GatewayError(Exception):
    pass


class ToolNotRegisteredError(GatewayError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Tool '{tool_name}' is not registered.")


class ToolInputError(ValueError, GatewayError):
    pass


class McpHttpError(RuntimeError, GatewayError):
    pass


class UpstreamToolError(ToolInputError):
    def __init__(self, server_name: str, tool_name: str, reason: str) -> None:
        super().__init__(f"Upstream MCP server '{server_name}' rejected {tool_name}: {reason}")


class UpstreamToolDefinitionError(McpHttpError):
    def __init__(self, server_name: str) -> None:
        super().__init__(f"Upstream MCP server '{server_name}' returned a tool without a name")


def invalid_addition_payload_error() -> ToolInputError:
    return ToolInputError("Invalid input for math.add: expected an object with numeric 'a' and 'b' fields")


def invalid_addition_number_error() -> ToolInputError:
    return ToolInputError("Invalid input for math.add: 'a' and 'b' must both be numbers")
