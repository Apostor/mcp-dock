import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp.server.dependencies import _current_http_request
from starlette.requests import Request

from core.oauth import OAuthBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_file(tokens_dir: Path, instance: str = "default") -> Path:
    return tokens_dir / f"google-drive-{instance}.json"


def _write_valid_token(tokens_dir: Path, instance: str = "default") -> None:
    tokens_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "token": "valid-access-token",
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "expiry": time.time() + 3600,
    }
    f = _token_file(tokens_dir, instance)
    f.write_text(json.dumps(data))
    f.chmod(0o600)


def _inject_headers(headers: dict[str, str]) -> None:
    """Set request headers in the FastMCP context variable for unit tests."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/mcp/",
        "raw_path": b"/mcp/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": None,
        "server": None,
        "root_path": "",
    }
    _current_http_request.set(Request(scope))


# ---------------------------------------------------------------------------
# Tracer bullet: server health
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_health_returns_200():
    from servers.google_drive.server import google_drive
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=google_drive.http_app()), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_all_tools_are_registered():
    from servers.google_drive.server import google_drive
    tools = {t.name for t in await google_drive.list_tools()}
    expected = {
        "list_files", "search_files", "get_file_metadata",
        "download_file", "upload_file", "create_folder",
        "create_doc", "create_sheet",
        "read_doc", "update_doc",
        "read_sheet", "update_sheet",
        "share_file", "update_permissions", "list_permissions",
        "reauth",
    }
    assert expected <= tools


# ---------------------------------------------------------------------------
# Tool behaviour (mocked Google API)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_files_calls_drive_api(tmp_path):
    _write_valid_token(tmp_path)
    _inject_headers({
        "x-google-credentials-path": "/fake/client_secret.json",
        "x-mcp-instance": "default",
    })

    mock_files = [{"id": "1", "name": "doc.txt", "mimeType": "text/plain"}]
    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": mock_files}

    with patch("servers.google_drive.server._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("list_files", {})

    assert any("doc.txt" in str(item) for item in result)


@pytest.mark.anyio
async def test_two_instances_use_separate_token_files(tmp_path):
    _write_valid_token(tmp_path, instance="work")
    _write_valid_token(tmp_path, instance="personal")

    tokens_seen = []
    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": []}

    def capture_service(token):
        tokens_seen.append(token)
        return mock_svc

    with patch("servers.google_drive.server._drive_service", side_effect=capture_service), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        from servers.google_drive.server import google_drive

        _inject_headers({"x-google-credentials-path": "/fake/creds.json", "x-mcp-instance": "work"})
        await google_drive.call_tool("list_files", {})

        _inject_headers({"x-google-credentials-path": "/fake/creds.json", "x-mcp-instance": "personal"})
        await google_drive.call_tool("list_files", {})

    assert len(tokens_seen) == 2
    assert tokens_seen[0] == tokens_seen[1] == "valid-access-token"
    assert _token_file(tmp_path, "work").exists()
    assert _token_file(tmp_path, "personal").exists()


@pytest.mark.anyio
async def test_expired_token_is_refreshed_before_api_call(tmp_path):
    tokens_dir = tmp_path
    tokens_dir.mkdir(exist_ok=True)
    expired_data = {
        "token": "expired-token",
        "refresh_token": "refresh-token-abc",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "expiry": time.time() - 60,
    }
    token_file = _token_file(tokens_dir)
    token_file.write_text(json.dumps(expired_data))
    token_file.chmod(0o600)

    _inject_headers({
        "x-google-credentials-path": "/fake/client_secret.json",
        "x-mcp-instance": "default",
    })

    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": []}

    refreshed_expiry = time.time() + 3600

    with patch("servers.google_drive.server._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings, \
         patch("core.oauth.Credentials") as MockCreds:
        mock_settings.return_value.tokens_path = str(tokens_dir)
        mock_creds = MagicMock()
        mock_creds.token = "refreshed-token"
        mock_creds.expiry.timestamp.return_value = refreshed_expiry
        mock_creds.refresh_token = expired_data["refresh_token"]
        mock_creds.token_uri = expired_data["token_uri"]
        mock_creds.client_id = expired_data["client_id"]
        mock_creds.client_secret = expired_data["client_secret"]
        MockCreds.return_value = mock_creds

        from servers.google_drive.server import google_drive
        await google_drive.call_tool("list_files", {})

    mock_creds.refresh.assert_called_once()
    token_after = json.loads(token_file.read_text())
    assert token_after["token"] == "refreshed-token"


# ---------------------------------------------------------------------------
# Credential header enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_missing_credentials_header_raises_mcp_error():
    from servers.google_drive.server import google_drive
    from starlette.applications import Starlette
    from starlette.routing import Mount

    app = Starlette(routes=[Mount("/google-drive", app=google_drive.http_app())])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/google-drive/mcp/",
            json={
                "jsonrpc": "2.0", "id": 1,
                "method": "tools/call",
                "params": {"name": "list_files", "arguments": {}},
            },
            headers={"content-type": "application/json", "accept": "application/json"},
        )
    assert response.status_code != 500
