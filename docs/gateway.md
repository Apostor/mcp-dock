# Gateway Layer

The gateway sits between agents and MCP servers inside mcp-dock. It provides three sub-layers:

1. **Proxy** — API key authentication (HTTP 401 before any server code runs)
2. **Governance** — allowlist / blocklist per server (MCP JSON-RPC error when blocked)
3. **Observability** — structured JSON audit log per tool call (stdout)

## Quick Setup

```bash
cp gateway.yaml.example gateway.yaml
# Generate a key and paste it in
python -c "import secrets; print('mcp-' + secrets.token_urlsafe(32))"
```

Add your agent entry to `gateway.yaml`:

```yaml
clients:
  claude-desktop: mcp-<your-generated-key>
```

Then configure your MCP client to send the key (see [README.md](../README.md)).

---

## API Key Format

Keys must match: `mcp-[A-Za-z0-9_-]` with a minimum total length of 20 characters.

| Part | Example | Purpose |
|------|---------|---------|
| Prefix | `mcp-` | Grep-able, identifies the token type |
| Body | 43 URL-safe base64 chars | 256-bit entropy |

**Generation options** (all fully local — nothing leaves your machine):

```bash
# Python
python -c "import secrets; print('mcp-' + secrets.token_urlsafe(32))"

# Node.js
node -e "const c=require('crypto');console.log('mcp-'+c.randomBytes(32).toString('base64url'))"
```

```js
// Browser DevTools (F12 → Console)
'mcp-' + btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))).replace(/[+/=]/g,'').slice(0,43)
```

### Add / Rotate / Revoke a Key

- **Add**: add a new `name: mcp-...` line under `clients:` and restart mcp-dock
- **Rotate**: replace the key value, restart mcp-dock; the old key stops working immediately
- **Revoke**: remove the client's line, restart mcp-dock

---

## Tool Governance

Specify an **allowlist** (permit only listed tools) or a **blocklist** (block listed tools) per server.
Using both for the same server is an error caught at startup.

```yaml
servers:
  google-drive:
    blocklist:
      - delete_file
      - remove_permission
      - deleteItem
```

```yaml
servers:
  google-drive:
    allowlist:
      - list_files
      - search
      - read_file
```

Default when no policy is defined for a server: **allow all tools**.

When a blocked tool is called, the gateway returns an MCP JSON-RPC error:

```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": "Tool 'delete_file' is blocked by gateway policy"}}
```

---

## Audit Log

Every tool call emits one JSON line to stdout. Arg **values** are never logged — only arg names.

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When the call was received |
| `request_id` | UUID v4 | Unique per call — correlate with upstream errors |
| `client` | string | Named client from `gateway.yaml` (`"unknown"` if no HTTP context) |
| `server` | string | MCP server name (e.g. `google-drive`) |
| `tool` | string | Tool name called |
| `instance` | string | `?instance=` query param value (default: `"default"`) |
| `status` | `ok` / `blocked` / `error` | Outcome |
| `latency_ms` | integer | Time from middleware entry to exit in milliseconds |
| `error_code` | integer or null | `-32001` when blocked, `null` otherwise |
| `tool_args_redacted` | string[] | Argument **names** only — no values |

### Example

```json
{
  "text": "tool_call",
  "record": {
    "extra": {
      "request_id": "a1b2c3d4-...",
      "client": "claude-desktop",
      "server": "google-drive",
      "tool": "list_files",
      "instance": "personal",
      "status": "ok",
      "latency_ms": 142,
      "error_code": null,
      "tool_args_redacted": ["folder_id", "page_size"]
    }
  }
}
```

### Disable the Gateway

Set `GATEWAY_ENABLED=false` in `.env`. All three sub-layers are skipped with zero overhead.
