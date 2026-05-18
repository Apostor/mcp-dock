# Google Drive MCP Server

Covers Drive, Docs, and Sheets with a single OAuth credential set per instance.

## Setup

### Step 1: Place your OAuth credentials on the server

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** — choose **Web application** type
3. Under **Authorized redirect URIs**, add: `http://<your-server-host>/google-drive/auth/callback`
   - Local: `http://localhost/google-drive/auth/callback`
   - Remote/VPS: `http://your-server.example.com/google-drive/auth/callback`
4. Enable: Google Drive API, Google Docs API, Google Sheets API
5. Download the JSON file and place it in the credentials directory:

```bash
mkdir -p ~/.mcp-dock/credentials/google-drive
cp ~/Downloads/client_secret.json ~/.mcp-dock/credentials/google-drive/personal.json
```

The filename (without `.json`) is the **instance name** — use any label you like (`personal`, `work`, etc.).

### Step 2: Configure your MCP client

In `claude_desktop_config.json` (or any MCP client):

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "url": "http://localhost/google-drive/mcp/?instance=personal"
    }
  }
}
```

No credentials or file paths in the config — just a URL with an `?instance=` parameter.

### Step 3: Authenticate on first use

On the first tool call, the server returns an error with an auth URL:

```
Not authenticated. Open this URL to authenticate:
http://localhost/google-drive/auth/start?instance=personal
```

Open that URL in your browser → Google login → Allow access. You'll see a confirmation page. After that, every tool call works automatically — tokens refresh silently in the background.

## Multi-account usage

Add multiple credential files, one per account:

```
~/.mcp-dock/credentials/google-drive/personal.json
~/.mcp-dock/credentials/google-drive/work.json
```

Add separate entries to your MCP config:

```json
{
  "mcpServers": {
    "personal-drive": { "url": "http://localhost/google-drive/mcp/?instance=personal" },
    "work-drive":     { "url": "http://localhost/google-drive/mcp/?instance=work" }
  }
}
```

## Token lifecycle

| Event | Behaviour |
|-------|-----------|
| Token valid | Returned from cache instantly |
| Token expired (1 h) | Silently refreshed using refresh token |
| Refresh token expired (6+ months inactive, or Testing mode app) | Tool returns auth URL again |
| User calls `reauth` tool | Clears token; next call returns auth URL |

**Tip:** In Google Cloud Console, publish your app (set status to **Production**). This prevents the 7-day refresh token expiry that applies to apps in Testing mode.

## Remote / VPS deployment

Replace `localhost` with your server's hostname. Credentials live on the remote host — no local files needed in the MCP client config.

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
