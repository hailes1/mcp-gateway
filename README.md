# MCP Gateway

This project is a minimal **gateway-style tool service**: a single FastAPI app that exposes a stable tool-facing API with one local sample tool.

## Why a Gateway?

A gateway shape is still useful even for a local sample because it makes the tool contract, discovery surface, and error envelope explicit.

A gateway helps by centralizing:

- tool registration and discovery
- request routing
- input validation
- consistent error handling
- extension points for auth, rate limits, logging, and policy

This repo is currently focused on the architectural seams that make gateway experimentation useful:

- a registry of gateway tools
- adapter-specific validation and normalization
- a uniform response envelope for tool execution
- a simple self-contained example with no external upstream dependencies

## Project Structure

- `app/main.py` - app factory, FastAPI endpoints, and gateway response handling
- `app/config.py` - minimal gateway settings
- `app/registry.py` - in-memory registry for tool adapters and discovery metadata
- `app/types.py` - shared gateway result and tool definition types
- `app/adapters/addition.py` - local sample tool that adds two numbers
- `pyproject.toml` - Python project metadata and dependencies managed by uv

## Endpoints

- `GET /health` - health check plus the currently registered tools
- `GET /tools` - list registered tools with discovery metadata
- `POST /gateway/call` - execute a tool through the gateway

Request shape for `POST /gateway/call`:

```json
{
  "tool": "math.add",
  "input": {
    "a": 2,
    "b": 4
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

   You should see a payload like:

   ```json
   {
     "ok": true,
     "service": "mcp-gateway",
     "registered_tools": ["math.add"]
   }
   ```

### Production Run

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 3000
```

## Example Calls

List tools:

```bash
curl http://localhost:3000/tools
```

Call the addition tool:

```bash
curl -X POST http://localhost:3000/gateway/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"math.add","input":{"a":2,"b":4}}'
```

## Configuration

The current sample does not require any external service configuration.

## Next Steps

- add more local sample tools once the discovery and validation model settles
- normalize adapter input validation through shared schemas or input models
- add tests for registry loading and consistent gateway error envelopes
