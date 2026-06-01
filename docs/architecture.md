# Architecture

## Request Flow

```
Agent (Claude Desktop / Cursor / Claude Code)
  │
  │  HTTP  Authorization: Bearer mcp-...
  ▼
Traefik  (optional reverse proxy — TLS, routing)
  │
  ▼
AuthMiddleware  (Starlette ASGI layer in app.py)
  │  valid key → sets scope["gateway_client"] = "claude-desktop"
  │  invalid / missing key → HTTP 401
  ▼
Starlette app  (app.py — path-based server mounting)
  │  /google-drive/* → google-drive server
  ▼
FastMCP server  (servers/google-drive/server.py)
  │
  ▼
GatewayMiddleware  (FastMCP Middleware — runs per tool call)
  │  checks is_tool_allowed(server, tool)
  │  blocked → MCP JSON-RPC error code -32001
  │  allowed → emits audit log → call_next
  ▼
Tool function  (tools_drive.py / tools_sheets.py / tools_docs.py)
  │  resolves OAuth token via OAuthBase
  ▼
Google API
```

## Layer Responsibilities

| Layer | Where | What it does |
|-------|-------|--------------|
| `AuthMiddleware` | `app.py` (ASGI wrap) | Bearer token validation — HTTP 401 for bad/missing keys |
| `GatewayMiddleware` | `core/gateway.py` (FastMCP Middleware) | Tool governance + audit logging per tool call |
| `OAuthBase` | `core/oauth.py` | Token persistence, refresh, per-instance namespacing |
| `CredentialsStore` | `core/credentials.py` | OAuth client secret lookup |

## Module Map

```
mcp-dock/
├── app.py                  # Starlette app factory; mounts all enabled servers;
│                           # wraps with AuthMiddleware when GATEWAY_ENABLED=true
├── gateway.yaml            # API keys + tool governance config (gitignored)
├── gateway.yaml.example    # Committed template
│
├── core/
│   ├── factory.py          # create_server() — attaches GatewayMiddleware
│   ├── gateway.py          # GatewayConfig, AuthMiddleware, GatewayMiddleware
│   ├── logging.py          # AuditLogger (loguru, JSON to stdout)
│   ├── oauth.py            # OAuthBase — token get/refresh/save
│   ├── credentials.py      # CredentialsStore — client secret lookup
│   └── settings.py         # Pydantic settings (env vars)
│
└── servers/
    └── google-drive/
        ├── server.py       # FastMCP instance + OAuth routes
        ├── tools_drive.py  # Drive tools
        ├── tools_sheets.py # Sheets tools
        └── tools_docs.py   # Docs tools
```

## Credential Model

- **OAuth client secrets**: `credentials/<server>/<instance>.json` — mounted read-only
- **OAuth tokens**: `tokens/<server>-<instance>.json` — written by the server, refreshed automatically
- **Instance namespacing**: `?instance=<name>` query param (default: `default`)
- **Gateway API keys**: `gateway.yaml` `clients:` block — one named key per agent

Multiple accounts per service are supported by placing multiple credential files and configuring
multiple MCP server entries in the client, each with a different `?instance=` value.
