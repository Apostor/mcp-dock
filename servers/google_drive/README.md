# Google Drive MCP Server

Covers Drive, Docs, and Sheets with a single OAuth credential set.

## Setup

### Step 1: Create OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Desktop app type)
3. Download the JSON file and save it anywhere on your machine (e.g. `~/.mcp-dock/google-client-secret.json`)
4. Enable the following APIs: Google Drive API, Google Docs API, Google Sheets API

### Step 2: Configure your MCP client

Pass the path to your `client_secret.json` via request headers:

| Header | Required | Description |
|--------|----------|-------------|
| `x-google-credentials-path` | Yes | Absolute path to `client_secret.json` |
| `x-mcp-instance` | No | Instance name for token isolation (default: `"default"`) |

### Step 3: First authentication

Call the `reauth` tool to initiate the browser OAuth flow. Tokens are stored at:

```
~/.mcp-dock/tokens/google-drive-{instance}.json
```

Tokens auto-refresh on expiry. Run `reauth` again to clear and re-authenticate.

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
| `reauth` | Clear cached token and re-authenticate |

## Multi-account usage

Use different `x-mcp-instance` values to keep separate token files:

```
x-mcp-instance: work      → google-drive-work.json
x-mcp-instance: personal  → google-drive-personal.json
```
