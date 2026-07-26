# MCP Gateway

A single FastAPI service that sits in front of one or more **MCP servers** and gives every caller one stable address to discover and call tools — regardless of how many servers are behind it.

---

## What is MCP?

**MCP (Model Context Protocol)** is an open standard that lets AI agents call external tools over HTTP. A tool is just a named function with a typed input schema — something like `weather.get_forecast` or `math.add`. Any server that speaks the MCP protocol can expose tools.

## What does this gateway do?

Without a gateway, every agent has to know the address of every individual MCP server. That gets messy fast.

This gateway solves that by being the **one address** agents talk to:

```
Agent  →  MCP Gateway  →  MCP Server A (e.g. your weather tool)
                       →  MCP Server B (e.g. your database tool)
                       →  Built-in tools (e.g. math.add)
```

The gateway handles:
- **Discovery** — one endpoint to see every available tool
- **Routing** — figures out which upstream server owns the tool and calls it
- **Error handling** — consistent error shape no matter which server fails
- **Lifecycle** — register and remove servers at runtime without restarting

---

## Running locally

```bash
uv sync
uvicorn app.main:app --port 8080
```

Or press **F5** in VS Code (the launch config is already set up).

Visit `http://localhost:8080/docs` for the interactive API explorer.

---

## Connecting your own MCP server

You have two options.

### Option A — environment variable (loaded at startup)

Set `MCP_UPSTREAM_SERVERS` before starting the gateway:

```bash
export MCP_UPSTREAM_SERVERS='[
  {"name": "my-server", "url": "http://localhost:9000/mcp", "type": "http"}
]'
uvicorn app.main:app --port 8080
```

The gateway connects on boot and registers every tool your server exposes. Tools appear as `my-server.<tool-name>`.

### Option B — live registration (no restart needed)

```bash
curl -X POST http://localhost:8080/adapters \
  -H "Content-Type: application/json" \
  -d '{"name": "my-server", "url": "http://localhost:9000/mcp"}'
```

Response tells you which tools were registered:

```json
{
  "name": "my-server",
  "status": "ok",
  "registered_tools": ["my-server.get_forecast", "my-server.get_alerts"]
}
```

If your server isn't reachable the status will be `"failed"` — the gateway records it so you can retry.

To remove a server:

```bash
curl -X DELETE http://localhost:8080/adapters/my-server
```

---

## Calling a tool from your agent

Once a server is connected, call any of its tools through `/mcp`:

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "my-server.get_forecast", "input": {"location": "Chicago, IL"}}'
```

Or call a tool directly on a specific adapter:

```bash
curl -X POST http://localhost:8080/adapters/my-server/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_forecast", "input": {"location": "Chicago, IL"}}'
```

Both return the same envelope:

```json
{"tool": "my-server.get_forecast", "ok": true, "data": {...}, "error": null}
```

---

## Seeing what's available

| What you want | Endpoint |
|---|---|
| All tools (every server) | `GET /tools` |
| All connected servers | `GET /adapters` |
| Gateway health + upstream status | `GET /health` |
| Interactive docs | `GET /docs` |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MCP_UPSTREAM_SERVERS` | _(none)_ | JSON array of servers to connect at startup |
| `PORT` | `8080` | Port the gateway listens on |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Adding a built-in tool (local code)

If you want to ship a tool as part of this repo instead of a separate server, add a class to `app/adapters/tools/` and register it in `build_registry` inside `app/main.py`. See `app/adapters/tools/addition.py` for the pattern — it's about 30 lines.

---

## Running tests

```bash
pytest
```
