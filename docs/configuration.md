# Configuration Reference

## Environment Variables

All variables are read from `.env` (see `.env.example` for the full template).

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLED_SERVERS` | `""` | Comma-separated list of servers to load (e.g. `google-drive,slack`) |
| `TOKENS_PATH` | `/opt/app/tokens` | Container path where OAuth tokens are stored (bind-mounted writable) |
| `CREDENTIALS_PATH` | `/opt/app/credentials` | Container path for OAuth client secrets (bind-mounted read-only) |
| `GATEWAY_ENABLED` | `true` | Set to `false` to disable all gateway logic |
| `GATEWAY_CONFIG_PATH` | `gateway.yaml` | Path to `gateway.yaml` — relative for local dev, absolute in Docker |

### Local Development vs Docker

| Context | `GATEWAY_CONFIG_PATH` | Notes |
|---------|----------------------|-------|
| Local (`uv run uvicorn`) | `gateway.yaml` | Resolved relative to project root |
| Docker Compose | `/opt/app/gateway.yaml` | Set in `.env`; bind-mounted via `docker-compose.yml` |

---

## `gateway.yaml` Schema

```yaml
# Named API keys — one per agent client.
clients:
  <client-name>: <mcp-key>      # key must match mcp-[A-Za-z0-9_-]{16,}

# Per-server tool governance (optional — omit to allow all tools).
servers:
  <server-name>:
    allowlist:                   # permit only these tools (mutually exclusive with blocklist)
      - <tool-name>
    blocklist:                   # block these tools (mutually exclusive with allowlist)
      - <tool-name>
```

Validation enforced at startup:
- Every key must start with `mcp-` and be at least 20 characters
- `allowlist` and `blocklist` cannot both be set for the same server
- Missing or malformed `gateway.yaml` when `GATEWAY_ENABLED=true` → process exits with a clear error

---

## Docker Compose Volume Mounts

```yaml
services:
  mcp-dock:
    volumes:
      - ./tokens:/opt/app/tokens          # writable — OAuth tokens written here
      - ./credentials:/opt/app/credentials:ro  # read-only — client secrets
      - ./gateway.yaml:/opt/app/gateway.yaml:ro  # read-only — API keys & governance
```

All three paths must exist on the host before running `docker compose up`.
`gateway.yaml` can be created by copying `gateway.yaml.example`.
