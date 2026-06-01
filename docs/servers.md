# Servers

## Implemented

| Server | Mount path | Status | Auth | Tools |
|--------|-----------|--------|------|-------|
| Google Drive | `/google-drive` | ✅ Available | OAuth 2.0 | 26+ (Drive, Docs, Sheets) |

See [servers/google-drive/README.md](../servers/google-drive/README.md) for setup instructions,
OAuth credential setup, and a full tool reference.

## Adding a New Server

```bash
mcp-dock new <server-name>
```

This scaffolds `servers/<name>/` with a working server, `pyproject.toml`, `README.md`,
and a test that passes on first run. Register the new server in `app.py`'s `_SERVER_REGISTRY`.
