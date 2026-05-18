# mcp-dock

Self-hosted MCP servers running on localhost. Your data never leaves your machine.

Connect your AI assistant (Claude Desktop, Cursor, etc.) to Google Drive, Trello, GitHub, Slack, and more — without routing credentials through third-party servers.

## How it works

Credentials live on the server, not in your MCP client config. You place an OAuth client secret (or API key file) in `~/.mcp-dock/credentials/<server>/<instance>.json` once, then point your MCP client at the server URL with `?instance=<name>`.

## Quickstart

```bash
git clone https://github.com/your-org/mcp-dock
cd mcp-dock
cp .env.example .env        # edit ENABLED_SERVERS
docker compose up
```

### 1. Place your credentials on the server

Create the credentials directory and drop your OAuth client secret (downloaded from Google Cloud Console) in the right location:

```
mkdir -p ~/.mcp-dock/credentials/google-drive
cp ~/Downloads/client_secret.json ~/.mcp-dock/credentials/google-drive/personal.json
```

Each file is named after the **instance** — a label you choose to distinguish accounts (e.g. `personal`, `work`).

### 2. Add to your MCP client config

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "url": "http://localhost/google-drive/mcp/?instance=personal"
    },
    "work-google-drive": {
      "url": "http://localhost/google-drive/mcp/?instance=work"
    }
  }
}
```

No API keys or credentials in the config — just a URL.

### 3. Authenticate

On first use, the server returns an auth URL. Open it in your browser to complete the OAuth flow. After that, the server caches the token automatically and refreshes it when needed.

## Available Servers

| Server | Path | Credentials file |
|--------|------|-----------------|
| Google Drive | `/google-drive` | OAuth client secret JSON (from Google Cloud Console) |
| Trello | `/trello` | *(coming soon)* |
| GitHub | `/github` | *(coming soon)* |
| GitLab | `/gitlab` | *(coming soon)* |
| Slack | `/slack` | *(coming soon)* |
| Notion | `/notion` | *(coming soon)* |
| Linear | `/linear` | *(coming soon)* |
| Jira | `/jira` | *(coming soon)* |
| Telegram | `/telegram` | *(coming soon)* |
| WhatsApp | `/whatsapp` | *(coming soon)* |

## Credentials directory layout

```
~/.mcp-dock/
  credentials/
    google-drive/
      personal.json   ← OAuth client secret for "personal" instance
      work.json       ← OAuth client secret for "work" instance
  tokens/
    google-drive-personal.json   ← cached OAuth token (managed automatically)
    google-drive-work.json
```

The `credentials/` directory is bind-mounted read-only into the container. Token files in `tokens/` are written by the server after the first OAuth flow.

## Multi-account support

Run multiple accounts for the same service by using different instance names:

```
~/.mcp-dock/credentials/google-drive/personal.json
~/.mcp-dock/credentials/google-drive/work.json
```

```json
{
  "mcpServers": {
    "personal-drive": { "url": "http://localhost/google-drive/mcp/?instance=personal" },
    "work-drive":     { "url": "http://localhost/google-drive/mcp/?instance=work" }
  }
}
```

## Remote / VPS deployment

If mcp-dock runs on a remote server, replace `localhost` with your server's hostname or IP:

```json
{
  "mcpServers": {
    "personal-drive": { "url": "https://mcp.example.com/google-drive/mcp/?instance=personal" }
  }
}
```

The credentials directory lives on the remote host. No local secrets required in the client config.

## Local development

```bash
uv sync
cp .env.example .env
mcp-dock run
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new server with `mcp-dock new <name>`.

## License

MIT
