# MCP Gateway Codebase Standard
**Version 1.0**

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Plane Separation](#2-plane-separation)
3. [Tool Definition as a First-Class Artifact](#3-tool-definition-as-a-first-class-artifact)
4. [Session Affinity Contract](#4-session-affinity-contract)
5. [Auth Boundaries](#5-auth-boundaries)
6. [Metadata Store Consistency](#6-metadata-store-consistency)
7. [Kubernetes Manifest Rules](#7-kubernetes-manifest-rules)
8. [Containerization Rules](#8-containerization-rules)
9. [Observability Requirements](#9-observability-requirements)
10. [What a Coding Agent Must Never Do](#10-what-a-coding-agent-must-never-do)

---

## 1. Repository Layout

Every MCP gateway codebase must follow this top-level structure. A coding agent should be able to orient itself in any conforming repo within 30 seconds.

```
/
├── gateway/              # Core gateway service (control plane + data plane)
├── tool-router/          # Tool Gateway Router service
├── servers/              # MCP server implementations (one dir per server)
│   └── {server-name}/
│       ├── Dockerfile
│       ├── src/
│       └── README.md
├── tools/                # Registered tool server implementations
│   └── {tool-name}/
│       ├── Dockerfile
│       ├── src/
│       └── tool-definition.json
├── deployment/
│   ├── k8s/              # Kubernetes manifests (StatefulSets, Services, etc.)
│   ├── infra/            # IaC (Bicep, Terraform, etc.)
│   └── local/            # Local dev (docker-compose or kind config)
├── openapi/              # OpenAPI specs for control plane APIs
├── docs/
│   ├── auth.md           # Auth setup (Entra ID, roles, secrets)
│   ├── routing.md        # Session affinity and tool routing decisions
│   └── runbook.md        # Ops runbook: scaling, incident response
└── README.md
```

> **`servers/` and `tools/` are intentionally separate.** A server is a stateful MCP backend accessed via `/adapters/{name}/mcp`. A tool is a registered, dynamically-routed capability accessed through the Tool Gateway Router at `/mcp`. These have different lifecycle semantics and must not be co-mingled.

---

## 2. Plane Separation

The gateway has two planes. Treat them as independently deployable concerns even if they run in the same process initially.

### Control Plane
Owns lifecycle operations:
- `POST /adapters`, `PUT /adapters/{name}`, `DELETE /adapters/{name}`
- Equivalent `/tools` CRUD
- Reads and writes the metadata store
- Talks to the Deployment Manager to reconcile Kubernetes state
- **Is the only component that writes to the metadata store**

### Data Plane
Owns traffic:
- `/adapters/{name}/mcp` — direct server routing
- `/mcp` — tool router traffic
- Reads from the metadata store but **never writes**
- Must be able to serve requests if the control plane is unavailable (read-only degraded mode, not a complete outage)

> **Enforcement:** the data plane's service layer must have no write path to the metadata store. A PR that introduces a write from a data plane handler must be rejected.

---

## 3. Tool Definition as a First-Class Artifact

Every tool must have a `tool-definition.json` file committed alongside its source code. This is the source of truth for what the tool does, what it accepts, and how the router finds it. It must not live only in a POST request body.

```json
{
  "tool": {
    "name": "weather",
    "title": "Weather Information",
    "description": "Gets current weather for a specified location.",
    "type": "http",
    "inputSchema": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City and state, e.g. Chicago, IL"
        }
      },
      "required": ["location"]
    },
    "annotations": {
      "readOnly": true
    }
  },
  "port": 8000,
  "path": "/mcp"
}
```

> **`annotations.readOnly` is a contract, not decoration.** Tools that mutate state must not carry `readOnly: true`. This is auditable.

---

## 4. Session Affinity Contract

Any MCP server that holds in-memory session state must declare it explicitly in its `README.md` under a `## Session Contract` heading.

**Required fields:**

| Field | Description |
|---|---|
| `Stateful` | `yes` or `no` |
| `Session scope` | What data is pinned per `session_id` |
| `Eviction` | What happens when a session ends or a pod restarts |
| `Replica safe` | Can two replicas serve the same `session_id`? |

**Deployment rules derived from the contract:**

- Stateless servers → `Deployment`
- Stateful servers → `StatefulSet` with a headless `Service`

> **A stateful server deployed as a `Deployment` is a latent production incident.**

---

## 5. Auth Boundaries

Three auth boundaries exist in every conforming gateway deployment. All three must be documented in `docs/auth.md`.

### Boundary 1 — Client → Gateway
Bearer token via Entra ID (or equivalent IdP). The gateway validates the token and resolves role claims (`mcp.admin`, `mcp.engineer`, or custom roles set in `requiredRoles`). No unauthenticated request reaches the data or control plane.

### Boundary 2 — Gateway → Tool Router
Shared secret passed as `X-Gateway-Secret`. Generated at deploy time, injected via Kubernetes secret into both `mcpgateway` and `toolgateway` pods.
- Never hardcoded
- Never logged
- Requests without a valid secret header → `401`
- Rotate on a documented schedule

### Boundary 3 — Tool Router → Tool Server
Workload Identity (preferred) or service account token. Tool servers must not be publicly reachable — they sit inside the cluster and accept traffic only from the router's pod identity. In Azure this means `useWorkloadIdentity: true` in the tool registration payload.

---

## 6. Metadata Store Consistency

The metadata store (Cosmos DB in Azure, or equivalent) is the routing table. The Tool Gateway Router derives its knowledge of registered tools from it. Because there is no push invalidation, the router operates on eventual consistency — a `PUT /tools/{name}` update may not be reflected in router behavior immediately.

Every codebase must:

1. Document the consistency window in `docs/routing.md`
2. Implement and document a force-refresh mechanism: either a router endpoint that flushes its local cache on demand, or a TTL short enough that stale routing resolves within an acceptable window for the use case

> Do not deploy a tool update and immediately test it without accounting for the consistency window.

---

## 7. Kubernetes Manifest Rules

| Resource | Required Kind | Notes |
|---|---|---|
| Stateful MCP server | `StatefulSet` + headless `Service` | Replica-safe: no |
| Stateless MCP server | `Deployment` + `ClusterIP` `Service` | Replica-safe: yes |
| Tool Gateway Router | `Deployment` | `minReplicas ≥ 2` in production — single instance is a SPOF for all `/mcp` traffic |
| All pods | — | Resource `requests` and `limits` must be set. No unbounded pods in production |
| All secrets | `Secret` | Never `ConfigMap`, never env var literals in the manifest |

**Namespace rules:**
- All gateway resources → dedicated namespace (e.g. `mcp-system`)
- Tool servers → separate namespace (e.g. `mcp-tools`)
- Network policy must restrict `mcp-tools` to only accept ingress from `mcp-system`

---

## 8. Containerization Rules

Every server and tool must have a `Dockerfile` that satisfies all of the following:

- Uses a **pinned base image tag** — no `latest`
- Runs as a **non-root user**
- Exposes **exactly one port**, matching the `port` field in `tool-definition.json` or the adapter registration
- Has a `HEALTHCHECK` instruction pointing to `/health` or equivalent

> **`/health` is not optional.** The gateway's Deployment Manager uses it to determine whether a server is ready to receive traffic. A server without a health endpoint will be routed to before it's ready.

---

## 9. Observability Requirements

Every gateway deployment must ship the following before going to production:

### Structured Logs
All control plane mutations must be logged with:
- Timestamp
- Principal
- Resource name
- Action
- Result

### Trace IDs
Propagated through the full data plane path:
```
client request → gateway → tool router → tool server
```
Use `session_id` as a correlation dimension in addition to trace ID.

### Metrics
At minimum, on `/mcp` and `/adapters/{name}/mcp` endpoints, broken down by adapter/tool name:
- Request count
- Error rate
- p99 latency

### Alerts
- Error rate spike on any adapter or tool
- Tool router instance count below 2
- Metadata store write latency above threshold

Use Application Insights (Azure) or equivalent. A tool routing failure that isn't observable is a production black hole.

---

## 10. What a Coding Agent Must Never Do

These are hard stops. A conforming implementation must not contain any of the following:

| Violation | Reason |
|---|---|
| A data plane handler that writes to the metadata store | Breaks plane separation |
| A `Deployment` manifest for a server with `Stateful: yes` | Causes session routing failures under load |
| A hardcoded value for `GatewaySettings:Secret` in source or manifests | Security — treat as a credential |
| `annotations.readOnly: true` on a tool that performs writes | False contract audited by the router |
| A tool server listening on a port other than its declared `port` | Breaks tool router dynamic routing |
| A single Tool Gateway Router replica in a production manifest | SPOF for all `/mcp` traffic |
| A `latest` image tag in any Kubernetes manifest | Non-deterministic deployments |

---

## Language and Implementation Note

This standard is language-agnostic at the tool and server level. The reference implementation is C# / ASP.NET Core (`microsoft/mcp-gateway`) but conforming tool servers can be written in any language, provided they:

- Expose a streamable HTTP MCP endpoint
- Expose a `/health` check on the declared port
- Declare their `tool-definition.json` as described in section 3

The gateway and tool router are the C# implementation from `microsoft/mcp-gateway` unless replaced in full.