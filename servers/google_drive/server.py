from urllib.parse import quote

from google_auth_oauthlib.flow import Flow
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.credentials import CredentialsStore
from core.factory import create_server
from core.oauth import OAuthBase
from core.settings import get_settings

google_drive = create_server("google-drive")

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Holds in-progress OAuth flows: {state: (flow, instance)}
_pending_flows: dict[str, tuple] = {}

oauth = OAuthBase(
    server="google-drive",
    instance="default",
    tokens_path=get_settings().tokens_path,
)
oauth.register_reauth_tool(google_drive)


def _get_token() -> str:
    from fastmcp.server.dependencies import get_http_request
    try:
        req = get_http_request()
        instance = req.query_params.get("instance", "default")
        host = req.headers.get("host", "localhost")
        scheme = req.url.scheme
    except RuntimeError:
        instance = "default"
        host, scheme = "localhost", "http"

    store = CredentialsStore(get_settings().credentials_path)
    store.resolve("google-drive", instance)  # validates credentials file exists

    client_oauth = OAuthBase(
        server="google-drive",
        instance=instance,
        tokens_path=get_settings().tokens_path,
    )
    try:
        return client_oauth.get_token()
    except RuntimeError:
        auth_url = (
            f"{scheme}://{host}/google-drive/auth/start"
            f"?instance={quote(instance)}"
        )
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"Not authenticated. Open this URL to authenticate: {auth_url}",
            )
        )


@google_drive.custom_route("/auth/start", methods=["GET"])
async def auth_start(request: Request) -> RedirectResponse:
    instance = request.query_params.get("instance", "default")

    store = CredentialsStore(get_settings().credentials_path)
    try:
        credentials_path = store.resolve("google-drive", instance)
    except McpError:
        return JSONResponse(
            {"error": f"No credentials file for instance '{instance}'"},
            status_code=400,
        )

    host = request.headers.get("host", "localhost")
    scheme = request.url.scheme
    redirect_uri = f"{scheme}://{host}/google-drive/auth/callback"

    flow = Flow.from_client_secrets_file(credentials_path, scopes=_SCOPES, redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    _pending_flows[state] = (flow, instance)

    return RedirectResponse(auth_url)


@google_drive.custom_route("/auth/callback", methods=["GET"])
async def auth_callback(request: Request) -> HTMLResponse:
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not state or state not in _pending_flows:
        return JSONResponse({"error": "Invalid or expired state"}, status_code=400)

    flow, instance = _pending_flows.pop(state)

    host = request.headers.get("host", "localhost")
    scheme = request.url.scheme
    flow.redirect_uri = f"{scheme}://{host}/google-drive/auth/callback"
    flow.fetch_token(code=code)

    client_oauth = OAuthBase(
        server="google-drive",
        instance=instance,
        tokens_path=get_settings().tokens_path,
    )
    client_oauth._save_token(flow.credentials)

    return HTMLResponse(
        "<html><body><h1>✓ Authenticated</h1>"
        "<p>Google Drive is connected. You can close this tab.</p></body></html>"
    )


def _drive_service(token: str):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    creds = google.oauth2.credentials.Credentials(token=token)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _docs_service(token: str):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    creds = google.oauth2.credentials.Credentials(token=token)
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def _sheets_service(token: str):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    creds = google.oauth2.credentials.Credentials(token=token)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


@google_drive.tool()
async def list_files(
    page_size: int = 20,
    folder_id: str = "root",
) -> list[dict]:
    """List files in a Google Drive folder."""
    token = _get_token()
    svc = _drive_service(token)
    result = svc.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        pageSize=page_size,
        fields="files(id,name,mimeType,modifiedTime,size)",
    ).execute()
    return result.get("files", [])


@google_drive.tool()
async def search_files(
    query: str,
    page_size: int = 20,
) -> list[dict]:
    """Search for files in Google Drive."""
    token = _get_token()
    svc = _drive_service(token)
    result = svc.files().list(
        q=f"fullText contains '{query}' and trashed=false",
        pageSize=page_size,
        fields="files(id,name,mimeType,modifiedTime)",
    ).execute()
    return result.get("files", [])


@google_drive.tool()
async def get_file_metadata(
    file_id: str,
) -> dict:
    """Get metadata for a file."""
    token = _get_token()
    svc = _drive_service(token)
    return svc.files().get(
        fileId=file_id,
        fields="id,name,mimeType,modifiedTime,size,parents,webViewLink",
    ).execute()


@google_drive.tool()
async def download_file(
    file_id: str,
) -> str:
    """Download file content as a string (text files only)."""
    import io
    from googleapiclient.http import MediaIoBaseDownload
    token = _get_token()
    svc = _drive_service(token)
    request = svc.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8", errors="replace")


@google_drive.tool()
async def upload_file(
    name: str,
    content: str,
    mime_type: str = "text/plain",
    folder_id: str = "root",
) -> dict:
    """Upload a text file to Google Drive."""
    import io
    from googleapiclient.http import MediaIoBaseUpload
    token = _get_token()
    svc = _drive_service(token)
    metadata = {"name": name, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(content.encode()), mimetype=mime_type)
    return svc.files().create(body=metadata, media_body=media, fields="id,name").execute()


@google_drive.tool()
async def create_folder(
    name: str,
    parent_id: str = "root",
) -> dict:
    """Create a folder in Google Drive."""
    token = _get_token()
    svc = _drive_service(token)
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    return svc.files().create(body=metadata, fields="id,name").execute()


@google_drive.tool()
async def create_doc(
    title: str,
    folder_id: str = "root",
) -> dict:
    """Create a new Google Doc."""
    token = _get_token()
    svc = _drive_service(token)
    metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    return svc.files().create(body=metadata, fields="id,name,webViewLink").execute()


@google_drive.tool()
async def create_sheet(
    title: str,
    folder_id: str = "root",
) -> dict:
    """Create a new Google Sheet."""
    token = _get_token()
    svc = _drive_service(token)
    metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id],
    }
    return svc.files().create(body=metadata, fields="id,name,webViewLink").execute()


@google_drive.tool()
async def read_doc(
    document_id: str,
) -> str:
    """Read the plain-text content of a Google Doc."""
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    body = doc.get("body", {})
    text_parts = []
    for element in body.get("content", []):
        for para_element in element.get("paragraph", {}).get("elements", []):
            text_run = para_element.get("textRun", {})
            text_parts.append(text_run.get("content", ""))
    return "".join(text_parts)


@google_drive.tool()
async def update_doc(
    document_id: str,
    content: str,
) -> dict:
    """Replace all content in a Google Doc with the given text."""
    token = _get_token()
    svc = _docs_service(token)
    doc = svc.documents().get(documentId=document_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1
    requests = []
    if end_index > 1:
        requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}})
    requests.append({"insertText": {"location": {"index": 1}, "text": content}})
    return svc.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()


@google_drive.tool()
async def read_sheet(
    spreadsheet_id: str,
    range_notation: str = "Sheet1",
) -> list[list]:
    """Read values from a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    result = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_notation)
        .execute()
    )
    return result.get("values", [])


@google_drive.tool()
async def update_sheet(
    spreadsheet_id: str,
    range_notation: str,
    values: list[list],
) -> dict:
    """Write values to a Google Sheet range."""
    token = _get_token()
    svc = _sheets_service(token)
    return (
        svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )


@google_drive.tool()
async def share_file(
    file_id: str,
    email: str,
    role: str = "reader",
) -> dict:
    """Share a file with a user by email."""
    token = _get_token()
    svc = _drive_service(token)
    permission = {"type": "user", "role": role, "emailAddress": email}
    return svc.permissions().create(fileId=file_id, body=permission, fields="id").execute()


@google_drive.tool()
async def update_permissions(
    file_id: str,
    permission_id: str,
    role: str,
) -> dict:
    """Update an existing permission on a file."""
    token = _get_token()
    svc = _drive_service(token)
    return svc.permissions().update(
        fileId=file_id, permissionId=permission_id, body={"role": role}, fields="id,role"
    ).execute()


@google_drive.tool()
async def list_permissions(
    file_id: str,
) -> list[dict]:
    """List all permissions on a file."""
    token = _get_token()
    svc = _drive_service(token)
    result = svc.permissions().list(
        fileId=file_id, fields="permissions(id,type,role,emailAddress)"
    ).execute()
    return result.get("permissions", [])
