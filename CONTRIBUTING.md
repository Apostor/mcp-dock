# Contributing to mcp-dock

## Workflow

mcp-dock uses a **fork-based** contribution model. Direct pushes to this repo are not accepted.

1. **Fork** the repo on GitHub
2. Clone your fork: `git clone https://github.com/<your-username>/mcp-dock`
3. Add the upstream remote: `git remote add upstream https://github.com/Apostor/mcp-dock`
4. Create a branch off `dev`: `git checkout -b feature/my-feature upstream/dev`
5. Make your changes, commit, push to your fork
6. Open a PR targeting the `dev` branch of this repo

## Adding a new server

Scaffold a new server with the CLI:

```bash
uv sync
mcp-dock new <name>
```

This generates `servers/<name>/` with:

- `server.py` — FastMCP app using `create_server`
- `pyproject.toml` — uv workspace member with server-specific dependencies
- `README.md` — header contract table and tool list
- `tests/test_server.py` — smoke test that passes out of the box

## Server contract

Every server must:

1. Use `create_server(name)` from `core` to create its FastMCP instance
2. Use `require_headers(ctx, "X-Service-Key", ...)` to extract credentials on every tool call
3. Never log credential values
4. Export the server instance as the module-level name matching the server directory

Example:

```python
from core import create_server, require_headers

trello = create_server("trello")

@trello.tool()
async def get_cards(ctx) -> list:
    creds = require_headers(ctx, "X-Trello-Key", "X-Trello-Token", "X-Trello-Board-Id")
    ...
```

## Header naming convention

| Type | Format | Example |
|------|--------|---------|
| Auth token | `X-{Service}-Token` | `X-GitHub-Token` |
| API key | `X-{Service}-Key` | `X-Trello-Key` |
| Instance URL | `X-{Service}-Url` | `X-GitLab-Url` |
| OAuth credentials path | `X-{Service}-Credentials-Path` | `X-Google-Credentials-Path` |
| Multi-account namespace | `X-MCP-Instance` | `X-MCP-Instance: work` |

## Running tests

```bash
uv sync
uv run pytest
```

No real API credentials are needed — all tests mock upstream HTTP calls.

## Commit style

```
feat: add list-cards tool to trello server
fix: handle expired token in google-drive
chore: add respx to telegram dev deps
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

## PR checklist

- [ ] Branch targets `dev`, not `main`
- [ ] Tests pass locally (`uv run pytest`)
- [ ] No credential values in logs or test output
- [ ] `servers/<name>/README.md` documents all tools and required headers
