# MCP Gateway (Simple Project)

This project is a minimal example of an **MCP Gateway**: a single service that an AI agent can call, while the gateway orchestrates requests to multiple tools and services.

## Why a Gateway?

MCP gives agents standardized communication pipes, but production agents usually need more than direct point-to-point connections.

A gateway helps by centralizing:

- tool registration and discovery
- request routing
- input validation
- consistent error handling
- extension points for auth, rate limits, logging, and policy

## Project Structure

- `app/main.py` - FastAPI server and gateway endpoints
- `app/registry.py` - in-memory registry for tool adapters
- `app/types.py` - shared types
- `app/adapters/echo_mcp_adapter.py` - mock MCP-style tool adapter
- `app/adapters/time_api_adapter.py` - mock non-MCP API adapter
- `pyproject.toml` - Python project metadata and dependencies managed by uv

## Endpoints

- `GET /health` - health check
- `GET /tools` - list registered tools
- `POST /gateway/call` - execute a tool through the gateway

Request shape for `POST /gateway/call`:

```json
{
  "tool": "mcp.echo",
  "input": {
    "message": "hello"
  }
}
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

### Install & Run

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Start the gateway:**
   ```bash
   uv run uvicorn app.main:app --reload --port 3000
   ```

   The server will start at `http://localhost:3000`

3. **Verify it's running:**
   ```bash
   curl http://localhost:3000/health
   ```

   You should see: `{"ok":true,"service":"mcp-gateway"}`

### Production Run

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 3000
```

## Example Calls

List tools:

```bash
curl http://localhost:3000/tools
```

Call MCP-style tool:

```bash
curl -X POST http://localhost:3000/gateway/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"mcp.echo","input":{"message":"Hello from agent"}}'
```

Call non-MCP API-style tool:

```bash
curl -X POST http://localhost:3000/gateway/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"api.time","input":{"timezone":"UTC"}}'
```

## Next Steps

- add auth between agent and gateway
- add retry and circuit-breaker behavior per adapter
- add request tracing and observability
- load adapters from config instead of hard-coded registration
