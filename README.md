# mcp-dock

Self-hosted MCP servers running on localhost. Your data never leaves your machine.

Connect your AI assistant (Claude Desktop, Cursor, etc.) to Google Drive, Trello, GitHub, Slack, and more — without routing credentials through third-party servers.

## Quickstart

```bash
git clone https://github.com/your-org/mcp-dock
cd mcp-dock
cp .env.example .env        # edit ENABLED_SERVERS
docker compose up
```

Then add to your MCP client config:

```json
{
  "mcpServers": {
    "trello": {
      "url": "http://localhost/trello",
      "headers": {
        "X-Trello-Key": "your-key",
        "X-Trello-Token": "your-token",
        "X-Trello-Board-Id": "your-board-id"
      }
    }
  }
}
```

## Available Servers

| Server | Path | Auth Headers |
|--------|------|-------------|
| Google Drive | `/google-drive` | `X-Google-Credentials-Path` (OAuth) |
| Trello | `/trello` | `X-Trello-Key`, `X-Trello-Token`, `X-Trello-Board-Id` |
| GitHub | `/github` | `X-GitHub-Token` |
| GitLab | `/gitlab` | `X-GitLab-Token`, `X-GitLab-Url` |
| Slack | `/slack` | `X-Slack-Credentials-Path` (OAuth) |
| Notion | `/notion` | `X-Notion-Token` |
| Linear | `/linear` | `X-Linear-Token` |
| Jira | `/jira` | `X-Jira-Url`, `X-Jira-Email`, `X-Jira-Token` |
| Telegram | `/telegram` | `X-Telegram-Token`, `X-Telegram-Chat-Id` |
| WhatsApp | `/whatsapp` | `X-WhatsApp-Token`, `X-WhatsApp-Phone-Id` |

## Multi-account support

Use `X-MCP-Instance` to run multiple accounts for the same service simultaneously:

```json
{
  "mcpServers": {
    "trello-personal": {
      "url": "http://localhost/trello",
      "headers": {
        "X-Trello-Key": "key1",
        "X-Trello-Token": "token1",
        "X-Trello-Board-Id": "board1",
        "X-MCP-Instance": "personal"
      }
    },
    "trello-work": {
      "url": "http://localhost/trello",
      "headers": {
        "X-Trello-Key": "key2",
        "X-Trello-Token": "token2",
        "X-Trello-Board-Id": "board2",
        "X-MCP-Instance": "work"
      }
    }
  }
}
```

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
