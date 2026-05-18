# Google Drive MCP Server

Covers Drive, Docs, and Sheets with a single OAuth credential set.

## Setup

### Step 1: Create OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** — choose **Web application** type
3. Under **Authorized redirect URIs**, add: `http://<your-server-host>/google-drive/auth/callback`
   - Local: `http://localhost/google-drive/auth/callback`
   - Remote/Docker: `http://your-server.example.com/google-drive/auth/callback`
4. Download the JSON file and save it on the machine running mcp-dock
5. Enable: Google Drive API, Google Docs API, Google Sheets API

### Step 2: Configure your MCP client

In `claude.json` / `claude_desktop_config.json`, pass the path to your `client_secret.json` as a header:

```json
{
  "mcpServers": {
    "google-drive": {
      "url": "http://localhost/google-drive/mcp/",
      "headers": {
        "x-google-credentials-path": "/path/to/client_secret.json",
        "x-mcp-instance": "default"
      }
    }
  }
}
```

| Header | Required | Description |
|--------|----------|-------------|
| `x-google-credentials-path` | Yes | Absolute path to `client_secret.json` on the server |
| `x-mcp-instance` | No | Instance name for token isolation (default: `"default"`) |

### Step 3: First authentication

On first use, any tool call will return an error with an authentication URL:

```
Not authenticated. Open this URL to authenticate:
http://your-server/google-drive/auth/start?credentials_path=...&instance=default
```

Open that URL in your browser → Google login → Allow. You'll see a confirmation page.
After that, every tool call works automatically — tokens refresh silently in the background.

## Token lifecycle

| Event | Behaviour |
|-------|-----------|
| Token valid | Returned from cache instantly |
| Token expired (1h) | Silently refreshed using refresh token |
| Refresh token expired (6+ months inactive, or Testing mode app) | Tool returns auth URL again |
| User calls `reauth` tool | Clears token, next call returns auth URL |

**Tip:** In Google Cloud Console, set your app's publishing status to **Production** (no verification needed for personal use — just click through the warning). This prevents the 7-day refresh token expiry that applies to apps in Testing mode.

## Multi-account usage

Use different `x-mcp-instance` values to keep separate token files for different Google accounts:

```json
"x-mcp-instance": "work"      → google-drive-work.json
"x-mcp-instance": "personal"  → google-drive-personal.json
```

## Tools

| Tool | Description |
|------|-------------|
| `list_files` | List files in a Drive folder |
| `search_files` | Full-text search across Drive |
| `get_file_metadata` | Get file ID, name, MIME type, size, links |
| `download_file` | Download text file content |
| `upload_file` | Upload a text file |
| `create_folder` | Create a new folder |
| `create_doc` | Create a blank Google Doc |
| `create_sheet` | Create a blank Google Sheet |
| `read_doc` | Read plain-text content of a Doc |
| `update_doc` | Replace all content in a Doc |
| `read_sheet` | Read values from a Sheet range |
| `update_sheet` | Write values to a Sheet range |
| `share_file` | Share a file with a user by email |
| `update_permissions` | Change an existing permission role |
| `list_permissions` | List all permissions on a file |
| `reauth` | Clear cached token (triggers re-auth on next tool call) |
