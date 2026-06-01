# mcp-dock

Self-hosted MCP servers running on localhost. Your data never leaves your machine.

Connect Claude Desktop, Claude Code, Cursor, and other AI assistants to Google Drive, Trello, GitHub, Slack, and more — without routing credentials through third-party servers.

## How it works

1. You place an OAuth client secret in `./credentials/<server>/<instance>.json` inside the project directory.
2. Docker mounts that directory read-only into the container.
3. Your MCP client connects with `?instance=<name>` in the URL — no secrets in the client config.
4. On the first tool call the server returns an auth URL. Open it in your browser to complete OAuth. Tokens are stored in `./tokens/` and refreshed automatically.

## Quickstart

```bash
git clone https://github.com/Apostor/mcp-dock
cd mcp-dock
cp .env.example .env
cp gateway.yaml.example gateway.yaml
```

Edit `.env` and set `ENABLED_SERVERS=google-drive`.

Generate an API key for each agent that will connect and add it to `gateway.yaml`:

```bash
python -c "import secrets; print('mcp-' + secrets.token_urlsafe(32))"
```

```yaml
# gateway.yaml
clients:
  claude-desktop: mcp-<paste-your-generated-key-here>
```

```bash
docker compose up -d
```

### 1. Place your OAuth credentials

```bash
mkdir -p credentials/google-drive
cp ~/Downloads/client_secret_*.json credentials/google-drive/personal.json
```

The filename without `.json` is the **instance name** — use any label (`personal`, `work`, etc.). See the server's own README for how to create the OAuth client secret in Google Cloud Console.

### 2. Configure your MCP client

All requests must include `Authorization: Bearer <your-key>`.

**`supergateway` bridge** (for stdio-based clients):

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "command": "npx",
      "args": [
        "-y", "supergateway",
        "--streamableHttp", "http://localhost/google-drive/mcp?instance=personal",
        "--header", "Authorization: Bearer mcp-<your-key>"
      ]
    }
  }
}
```

**HTTP-native clients** (Claude Code, Cursor):

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "url": "http://localhost/google-drive/mcp?instance=personal",
      "headers": {
        "Authorization": "Bearer mcp-<your-key>"
      }
    }
  }
}
```

### 3. Authenticate on first use

On the first tool call the server returns an error with an auth URL:

```
Google Drive is not authenticated yet.
Ask the user to open this URL in their browser:
  http://localhost/google-drive/auth/start?instance=personal
```

Open that URL in your browser → Google sign-in → Allow. After that every tool call works automatically — tokens refresh silently in the background.

## Gateway

mcp-dock requires agents to authenticate with a bearer API key before they can call any tool.
This prevents unauthorized local processes from accessing your data.

Keys are configured in `gateway.yaml` (gitignored, created from `gateway.yaml.example`).
The gateway also supports per-server tool governance (allowlist / blocklist) and emits a
structured JSON audit log to stdout on every tool call.

See [docs/gateway.md](docs/gateway.md) for the full reference.

## Credentials and tokens directory layout

Both directories live inside the project and are gitignored:

```
mcp-dock/
  credentials/                        ← mounted read-only into container
    google-drive/
      personal.json                   ← OAuth client secret ("personal" instance)
      work.json                       ← OAuth client secret ("work" instance)
  tokens/                             ← written by the server, never commit this
    google-drive-personal.json        ← cached OAuth token (auto-managed)
    google-drive-work.json
```

`CredentialsStore` resolves `credentials/<server>/<instance>.json` at request time. `OAuthBase` reads and writes `tokens/<server>-<instance>.json`, refreshing automatically when the token expires.

## Available servers

| Server | Path | Status |
|--------|------|--------|
| Google Drive | `/google-drive` | Available — [README](servers/google-drive/README.md) |

Enable only the servers you need via `ENABLED_SERVERS` in `.env`.

## Multi-account support

Add one credential file per account and one MCP server entry per instance:

```bash
credentials/google-drive/personal.json
credentials/google-drive/work.json
```

```json
{
  "mcpServers": {
    "personal-drive": {
      "command": "npx",
      "args": [
        "-y", "supergateway",
        "--streamableHttp", "http://localhost/google-drive/mcp?instance=personal",
        "--header", "Authorization: Bearer mcp-<your-key>"
      ]
    },
    "work-drive": {
      "command": "npx",
      "args": [
        "-y", "supergateway",
        "--streamableHttp", "http://localhost/google-drive/mcp?instance=work",
        "--header", "Authorization: Bearer mcp-<your-key>"
      ]
    }
  }
}
```

## Remote / VPS deployment

Replace `localhost` with your server's hostname everywhere, including the redirect URI you register in the OAuth provider's console:

```json
{
  "mcpServers": {
    "personal-drive": {
      "command": "npx",
      "args": ["-y", "supergateway", "--streamableHttp", "https://mcp.example.com/google-drive/mcp?instance=personal"]
    }
  }
}
```

Credentials live on the remote host. No local secrets needed in the client config.

## Local development

```bash
uv sync
cp .env.example .env              # set ENABLED_SERVERS
cp gateway.yaml.example gateway.yaml  # add your keys
uv run uvicorn app:app --reload
```

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/architecture.md) | Request flow, layer responsibilities, module map, credential model |
| [Gateway](docs/gateway.md) | API key setup, key generation, tool governance, audit log reference |
| [Configuration](docs/configuration.md) | All env vars, `gateway.yaml` schema, Docker volume mounts |
| [Servers](docs/servers.md) | Implemented servers, tool counts, auth methods |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new server with `mcp-dock new <name>`.

## License

MIT
