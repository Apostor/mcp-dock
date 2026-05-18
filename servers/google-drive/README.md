# Google Drive MCP Server

Covers Drive, Docs, and Sheets with a single OAuth credential set per instance.

## Setup

### Step 1: Create OAuth 2.0 credentials in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Enabled APIs & Services**
2. Enable all three APIs:
   - **Google Drive API**
   - **Google Docs API**
   - **Google Sheets API**
3. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Choose **Web application** as the application type
5. Under **Authorized redirect URIs**, click **Add URI** and enter the exact value for your deployment:

   | Deployment | Redirect URI |
   |------------|-------------|
   | Local (default) | `http://localhost/google-drive/auth/callback` |
   | Remote / VPS | `http://your-server.example.com/google-drive/auth/callback` |

   > **Common mistake:** Do not add a port number (e.g. `:8000`). Traefik listens on port 80, so the URI has no port.

6. Click **Create**, then **Download JSON**

### Step 2: Configure OAuth consent screen (required once)

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** user type → **Create**
3. Fill in App name, user support email, developer contact email → **Save and Continue**
4. On the **Scopes** step → **Save and Continue** (scopes are requested at runtime)
5. On the **Test users** step, add your Google account email → **Save and Continue**
6. Go back to the **OAuth consent screen** summary and click **Publish App** → **Confirm**

   > Publishing prevents the 7-day refresh token expiry that applies to apps in **Testing** mode.

### Step 3: Place your credentials file on the server

```bash
mkdir -p ~/.mcp-dock/credentials/google-drive
cp ~/Downloads/client_secret_*.json ~/.mcp-dock/credentials/google-drive/personal.json
```

The filename (without `.json`) becomes the **instance name** — use any label you like (`personal`, `work`, etc.).

### Step 4: Configure your MCP client

**Claude Desktop** requires a stdio bridge because it only supports stdio transport:

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

**Claude Code / Cursor / other HTTP-native clients:**

```json
{
  "mcpServers": {
    "personal-google-drive": {
      "url": "http://localhost/google-drive/mcp?instance=personal"
    }
  }
}
```

No credentials or file paths in the config — just the instance name in the URL.

### Step 5: Authenticate on first use

On the first tool call, the server returns an error with an auth URL:

```
Not authenticated. Open this URL to authenticate:
http://localhost/google-drive/auth/start?instance=personal
```

Open that URL in your browser → Google sign-in → **Allow**. You'll see a confirmation page. After that, every tool call works automatically — tokens refresh silently in the background.

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

Each instance needs its own OAuth client secret file and its own entry in **Authorized redirect URIs** in Google Cloud Console. You can reuse the same OAuth client for both accounts — just add both redirect URIs to the same client.

## Token lifecycle

| Event | Behaviour |
|-------|-----------|
| Token valid | Returned from cache instantly |
| Token expired (1 h) | Silently refreshed using refresh token |
| Refresh token expired (6+ months inactive, or Testing mode app) | Tool returns auth URL again |
| User calls `reauth` tool | Clears token; next call returns auth URL |

## Remote / VPS deployment

Replace `localhost` with your server's hostname everywhere, including the redirect URI in Google Cloud Console:

```json
{
  "command": "npx",
  "args": ["-y", "supergateway", "--streamableHttp", "https://mcp.example.com/google-drive/mcp?instance=personal"]
}
```

Redirect URI to register: `https://mcp.example.com/google-drive/auth/callback`

Credentials live on the remote host — no local files needed in the client config.

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
