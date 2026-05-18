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
```

Edit `.env` and set `ENABLED_SERVERS=google-drive` (comma-separated list of servers to run).

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

**Claude Desktop** only supports stdio transport — use the [`supergateway`](https://github.com/supercorp-ai/supergateway) bridge:

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "command": "npx",
      "args": ["-y", "supergateway", "--streamableHttp", "http://localhost/google-drive/mcp?instance=personal"]
    }
  }
}
```

**Claude Code / Cursor / other HTTP-native clients** connect directly:

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "url": "http://localhost/google-drive/mcp?instance=personal"
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
| Trello | `/trello` | Coming soon |
| GitHub | `/github` | Coming soon |
| GitLab | `/gitlab` | Coming soon |
| Slack | `/slack` | Coming soon |
| Notion | `/notion` | Coming soon |
| Linear | `/linear` | Coming soon |
| Jira | `/jira` | Coming soon |
| Telegram | `/telegram` | Coming soon |
| WhatsApp | `/whatsapp` | Coming soon |

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
      "args": ["-y", "supergateway", "--streamableHttp", "http://localhost/google-drive/mcp?instance=personal"]
    },
    "work-drive": {
      "command": "npx",
      "args": ["-y", "supergateway", "--streamableHttp", "http://localhost/google-drive/mcp?instance=work"]
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
cp .env.example .env       # set ENABLED_SERVERS
uv run uvicorn app:app --reload
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new server with `mcp-dock new <name>`.

## License

MIT
