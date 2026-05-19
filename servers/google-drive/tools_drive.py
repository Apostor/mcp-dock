from servers.google_drive.server import google_drive, _get_token, _drive_service


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
    safe_query = query.replace("'", "\\'")
    result = svc.files().list(
        q=f"fullText contains '{safe_query}' and trashed=false",
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


@google_drive.tool()
async def list_comments(
    file_id: str,
) -> list[dict]:
    """List comments on a Google Drive file."""
    token = _get_token()
    svc = _drive_service(token)
    result = svc.comments().list(
        fileId=file_id,
        fields="comments(id,content,author,createdTime,resolved)",
    ).execute()
    return result.get("comments", [])


@google_drive.tool()
async def add_comment(
    file_id: str,
    content: str,
) -> dict:
    """Add a comment to a Google Drive file."""
    token = _get_token()
    svc = _drive_service(token)
    return svc.comments().create(
        fileId=file_id,
        body={"content": content},
        fields="id,content,createdTime",
    ).execute()


@google_drive.tool()
async def trash_file(
    file_id: str,
) -> str:
    """Move a Google Drive file to trash (recoverable)."""
    token = _get_token()
    svc = _drive_service(token)
    svc.files().update(fileId=file_id, body={"trashed": True}).execute()
    return f"Moved file {file_id} to trash"
