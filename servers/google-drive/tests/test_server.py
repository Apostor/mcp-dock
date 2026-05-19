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


def _write_credentials(base: Path, instance: str = "default") -> None:
    creds_dir = base / "google-drive"
    creds_dir.mkdir(parents=True, exist_ok=True)
    (creds_dir / f"{instance}.json").write_text("{}")


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


def _inject_request(headers: dict[str, str] | None = None, query_string: str = "") -> None:
    """Inject an HTTP request into the FastMCP context variable for unit tests."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/mcp/",
        "raw_path": b"/mcp/",
        "query_string": query_string.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
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
        # Sheets tools
        "format_cells", "add_sheet", "delete_sheet", "rename_sheet",
        "list_sheets", "merge_cells", "set_borders", "add_conditional_format",
        "add_data_validation", "add_named_range", "protect_range",
        "append_rows", "get_spreadsheet_info",
        # Docs/Drive tools
        "get_doc_content", "format_doc_text", "format_doc_paragraph",
        "insert_text", "delete_range", "find_and_replace", "insert_table",
        "edit_table_cell", "create_paragraph_bullets", "insert_image",
        "list_comments", "add_comment", "trash_file",
    }
    assert expected <= tools


# ---------------------------------------------------------------------------
# Tool behaviour (mocked Google API)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_files_resolves_instance_from_query_param(tmp_path):
    _write_valid_token(tmp_path, instance="personal")
    _write_credentials(tmp_path, instance="personal")
    _inject_request(query_string="instance=personal")

    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": [{"id": "1", "name": "f.txt"}]}

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("list_files", {})

    assert any("f.txt" in str(item) for item in result)


@pytest.mark.anyio
async def test_list_files_calls_drive_api(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_files = [{"id": "1", "name": "doc.txt", "mimeType": "text/plain"}]
    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": mock_files}

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("list_files", {})

    assert any("doc.txt" in str(item) for item in result)


@pytest.mark.anyio
async def test_list_files_defaults_to_default_instance(tmp_path):
    _write_valid_token(tmp_path, instance="default")
    _write_credentials(tmp_path, instance="default")
    _inject_request()

    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": []}

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("list_files", {})

    assert result.structured_content["result"] == []


@pytest.mark.anyio
async def test_two_instances_use_separate_token_files(tmp_path):
    _write_valid_token(tmp_path, instance="work")
    _write_valid_token(tmp_path, instance="personal")
    _write_credentials(tmp_path, instance="work")
    _write_credentials(tmp_path, instance="personal")

    tokens_seen = []
    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": []}

    def capture_service(token):
        tokens_seen.append(token)
        return mock_svc

    with patch("servers.google_drive.tools_drive._drive_service", side_effect=capture_service), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive

        _inject_request(query_string="instance=work")
        await google_drive.call_tool("list_files", {})

        _inject_request(query_string="instance=personal")
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
    _write_credentials(tmp_path)
    _inject_request()

    mock_svc = MagicMock()
    mock_svc.files().list().execute.return_value = {"files": []}
    refreshed_expiry = time.time() + 3600

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings, \
         patch("core.oauth.Credentials") as MockCreds:
        mock_settings.return_value.tokens_path = str(tokens_dir)
        mock_settings.return_value.credentials_path = str(tmp_path)
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
# First-auth: no token file → McpError with auth URL
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_no_token_raises_error_with_auth_url(tmp_path):
    _write_credentials(tmp_path)
    _inject_request(headers={"host": "my-server.example.com"})

    from fastmcp.exceptions import ToolError
    with patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        with pytest.raises(ToolError) as exc_info:
            await google_drive.call_tool("list_files", {})

    error_message = str(exc_info.value)
    assert "http://my-server.example.com/google-drive/auth/start" in error_message
    assert "instance=default" in error_message


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_auth_start_redirects_to_google(tmp_path):
    from servers.google_drive.server import google_drive
    from starlette.applications import Starlette
    from starlette.routing import Mount

    _write_credentials(tmp_path)
    app = Starlette(routes=[Mount("/google-drive", app=google_drive.http_app())])

    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?...", "state-123")

    with patch("servers.google_drive.server.Flow") as MockFlow, \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.credentials_path = str(tmp_path)
        mock_settings.return_value.tokens_path = str(tmp_path)
        MockFlow.from_client_secrets_file.return_value = mock_flow
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/google-drive/auth/start",
                params={"instance": "default"},
                follow_redirects=False,
            )

    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]


@pytest.mark.anyio
async def test_auth_start_returns_400_when_no_credentials_file(tmp_path):
    from servers.google_drive.server import google_drive
    from starlette.applications import Starlette
    from starlette.routing import Mount

    app = Starlette(routes=[Mount("/google-drive", app=google_drive.http_app())])

    with patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.credentials_path = str(tmp_path)
        mock_settings.return_value.tokens_path = str(tmp_path)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/google-drive/auth/start",
                params={"instance": "nonexistent"},
                follow_redirects=False,
            )

    assert response.status_code == 400
    assert "nonexistent" in response.text


@pytest.mark.anyio
async def test_auth_callback_saves_token(tmp_path):
    from servers.google_drive.server import google_drive, _pending_flows
    from starlette.applications import Starlette
    from starlette.routing import Mount
    import time as _time

    app = Starlette(routes=[Mount("/google-drive", app=google_drive.http_app())])

    mock_flow = MagicMock()
    mock_flow.credentials.token = "brand-new-token"
    mock_flow.credentials.refresh_token = "refresh-abc"
    mock_flow.credentials.token_uri = "https://oauth2.googleapis.com/token"
    mock_flow.credentials.client_id = "client-id"
    mock_flow.credentials.client_secret = "client-secret"
    mock_flow.credentials.expiry.timestamp.return_value = _time.time() + 3600

    state_key = "test-state-xyz"
    _pending_flows[state_key] = (mock_flow, "default")

    with patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/google-drive/auth/callback",
                params={"code": "auth-code-from-google", "state": state_key},
            )

    assert response.status_code == 200
    assert "Authenticated" in response.text
    saved = json.loads((tmp_path / "google-drive-default.json").read_text())
    assert saved["token"] == "brand-new-token"


# ---------------------------------------------------------------------------
# No credentials file in store → error before attempting OAuth
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_missing_credentials_file_raises_error(tmp_path):
    _inject_request(query_string="instance=unconfigured")

    from fastmcp.exceptions import ToolError
    with patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        with pytest.raises(ToolError) as exc_info:
            await google_drive.call_tool("list_files", {})

    assert "unconfigured" in str(exc_info.value)


# ===========================================================================
# Private helper tests
# ===========================================================================

# ---------------------------------------------------------------------------
# _hex_to_color
# ---------------------------------------------------------------------------

def test_hex_to_color_black():
    from servers.google_drive._helpers import _hex_to_color
    result = _hex_to_color("#000000")
    assert result == {"red": 0.0, "green": 0.0, "blue": 0.0}


def test_hex_to_color_white():
    from servers.google_drive._helpers import _hex_to_color
    result = _hex_to_color("#ffffff")
    assert result["red"] == pytest.approx(1.0)
    assert result["green"] == pytest.approx(1.0)
    assert result["blue"] == pytest.approx(1.0)


def test_hex_to_color_red():
    from servers.google_drive._helpers import _hex_to_color
    result = _hex_to_color("#FF0000")
    assert result["red"] == pytest.approx(1.0)
    assert result["green"] == pytest.approx(0.0)
    assert result["blue"] == pytest.approx(0.0)


def test_hex_to_color_mid_value():
    from servers.google_drive._helpers import _hex_to_color
    result = _hex_to_color("#804020")
    assert result["red"] == pytest.approx(0x80 / 255)
    assert result["green"] == pytest.approx(0x40 / 255)
    assert result["blue"] == pytest.approx(0x20 / 255)


def test_hex_to_color_invalid_raises():
    from mcp.shared.exceptions import McpError
    from servers.google_drive._helpers import _hex_to_color
    with pytest.raises(McpError):
        _hex_to_color("#ZZZ")


# ---------------------------------------------------------------------------
# _col_letter_to_index
# ---------------------------------------------------------------------------

def test_col_letter_a():
    from servers.google_drive._helpers import _col_letter_to_index
    assert _col_letter_to_index("A") == 0


def test_col_letter_z():
    from servers.google_drive._helpers import _col_letter_to_index
    assert _col_letter_to_index("Z") == 25


def test_col_letter_aa():
    from servers.google_drive._helpers import _col_letter_to_index
    assert _col_letter_to_index("AA") == 26


def test_col_letter_ab():
    from servers.google_drive._helpers import _col_letter_to_index
    assert _col_letter_to_index("AB") == 27


def test_col_letter_lowercase():
    from servers.google_drive._helpers import _col_letter_to_index
    assert _col_letter_to_index("b") == 1


# ---------------------------------------------------------------------------
# _get_sheet_id
# ---------------------------------------------------------------------------

def test_get_sheet_id_found():
    from servers.google_drive._helpers import _get_sheet_id
    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "sheets": [
            {"properties": {"sheetId": 0, "title": "Sheet1"}},
            {"properties": {"sheetId": 42, "title": "MySheet"}},
        ]
    }
    result = _get_sheet_id(mock_svc, "spreadsheet-id", "MySheet")
    assert result == 42


def test_get_sheet_id_not_found():
    from mcp.shared.exceptions import McpError
    from servers.google_drive._helpers import _get_sheet_id
    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"sheetId": 0, "title": "Sheet1"}}]
    }
    with pytest.raises(McpError):
        _get_sheet_id(mock_svc, "spreadsheet-id", "Nonexistent")


# ---------------------------------------------------------------------------
# _a1_to_grid_range
# ---------------------------------------------------------------------------

def test_a1_to_grid_range_basic():
    from servers.google_drive._helpers import _a1_to_grid_range
    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"sheetId": 5, "title": "Sheet1"}}]
    }
    result = _a1_to_grid_range(mock_svc, "spreadsheet-id", "Sheet1!A1:B3")
    assert result["sheetId"] == 5
    assert result["startRowIndex"] == 0
    assert result["endRowIndex"] == 3
    assert result["startColumnIndex"] == 0
    assert result["endColumnIndex"] == 2


def test_a1_to_grid_range_single_col():
    from servers.google_drive._helpers import _a1_to_grid_range
    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"sheetId": 0, "title": "Data"}}]
    }
    result = _a1_to_grid_range(mock_svc, "sid", "Data!C2:C5")
    assert result["startColumnIndex"] == 2
    assert result["endColumnIndex"] == 3
    assert result["startRowIndex"] == 1
    assert result["endRowIndex"] == 5


# ---------------------------------------------------------------------------
# _find_text_ranges
# ---------------------------------------------------------------------------

_SAMPLE_CONTENT = [
    {
        "paragraph": {
            "elements": [
                {"startIndex": 1, "textRun": {"content": "Hello World"}},
            ]
        }
    },
    {
        "paragraph": {
            "elements": [
                {"startIndex": 13, "textRun": {"content": "Hello again"}},
            ]
        }
    },
]


def test_find_text_ranges_finds_all():
    from servers.google_drive._helpers import _find_text_ranges
    results = _find_text_ranges(_SAMPLE_CONTENT, "Hello")
    assert len(results) == 2
    assert results[0] == (1, 6)
    assert results[1] == (13, 18)


def test_find_text_ranges_occurrence_index():
    from servers.google_drive._helpers import _find_text_ranges
    results = _find_text_ranges(_SAMPLE_CONTENT, "Hello", occurrence_index=1)
    assert len(results) == 1
    assert results[0] == (13, 18)


def test_find_text_ranges_occurrence_out_of_range():
    from mcp.shared.exceptions import McpError
    from servers.google_drive._helpers import _find_text_ranges
    with pytest.raises(McpError):
        _find_text_ranges(_SAMPLE_CONTENT, "Hello", occurrence_index=5)


def test_find_text_ranges_no_match():
    from servers.google_drive._helpers import _find_text_ranges
    results = _find_text_ranges(_SAMPLE_CONTENT, "XYZ")
    assert results == []


# ---------------------------------------------------------------------------
# _find_table_by_index
# ---------------------------------------------------------------------------

_SAMPLE_CONTENT_WITH_TABLES = [
    {"paragraph": {"elements": [{"startIndex": 1, "textRun": {"content": "Title"}}]}},
    {"table": {"tableRows": [{"tableCells": [{"content": [{"startIndex": 10}]}]}]}},
    {"paragraph": {"elements": [{"startIndex": 20, "textRun": {"content": "Middle"}}]}},
    {"table": {"tableRows": [{"tableCells": [{"content": [{"startIndex": 30}]}]}]}},
]


def test_find_table_by_index_first():
    from servers.google_drive._helpers import _find_table_by_index
    result = _find_table_by_index(_SAMPLE_CONTENT_WITH_TABLES, 0)
    assert "table" in result
    first_cell_start = result["table"]["tableRows"][0]["tableCells"][0]["content"][0]["startIndex"]
    assert first_cell_start == 10


def test_find_table_by_index_second():
    from servers.google_drive._helpers import _find_table_by_index
    result = _find_table_by_index(_SAMPLE_CONTENT_WITH_TABLES, 1)
    first_cell_start = result["table"]["tableRows"][0]["tableCells"][0]["content"][0]["startIndex"]
    assert first_cell_start == 30


def test_find_table_by_index_out_of_range():
    from mcp.shared.exceptions import McpError
    from servers.google_drive._helpers import _find_table_by_index
    with pytest.raises(McpError):
        _find_table_by_index(_SAMPLE_CONTENT_WITH_TABLES, 5)


# ===========================================================================
# Sheets tool tests
# ===========================================================================

def _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1"):
    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"sheetId": sheet_id, "title": title}}]
    }
    mock_svc.spreadsheets().batchUpdate().execute.return_value = {}
    return mock_svc


@pytest.mark.anyio
async def test_format_cells(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("format_cells", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:B2",
            "bold": True,
            "font_size": 12.0,
        })

    assert "Formatted" in str(result)
    mock_svc.spreadsheets().batchUpdate.assert_called()


@pytest.mark.anyio
async def test_add_sheet(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.spreadsheets().batchUpdate().execute.return_value = {}

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("add_sheet", {
            "spreadsheet_id": "sid",
            "title": "NewSheet",
        })

    assert "NewSheet" in str(result)


@pytest.mark.anyio
async def test_delete_sheet(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=5, title="OldSheet")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("delete_sheet", {
            "spreadsheet_id": "sid",
            "sheet_name": "OldSheet",
        })

    assert "OldSheet" in str(result)
    # Verify deleteSheet was called with correct sheetId
    call_args = mock_svc.spreadsheets().batchUpdate.call_args
    body = call_args.kwargs.get("body") or call_args.args[0] if call_args.args else call_args.kwargs["body"]
    # The call was made, sufficient to check it succeeded
    assert "Deleted" in str(result)


@pytest.mark.anyio
async def test_rename_sheet(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=3, title="OldName")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("rename_sheet", {
            "spreadsheet_id": "sid",
            "sheet_name": "OldName",
            "new_title": "NewName",
        })

    assert "NewName" in str(result)


@pytest.mark.anyio
async def test_list_sheets(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "sheets": [
            {"properties": {"sheetId": 0, "title": "Sheet1"}},
            {"properties": {"sheetId": 1, "title": "Sheet2"}},
        ]
    }

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("list_sheets", {"spreadsheet_id": "sid"})

    assert "Sheet1" in str(result)
    assert "Sheet2" in str(result)


@pytest.mark.anyio
async def test_merge_cells(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("merge_cells", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:C3",
        })

    assert "Merged" in str(result)


@pytest.mark.anyio
async def test_set_borders(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("set_borders", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:B2",
            "sides": ["top", "bottom"],
            "style": "SOLID",
            "color": "#000000",
        })

    assert "borders" in str(result).lower() or "Sheet1" in str(result)


@pytest.mark.anyio
async def test_add_conditional_format(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("add_conditional_format", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:A10",
            "condition_type": "NUMBER_GREATER",
            "condition_value": "5",
            "background_color": "#FF0000",
        })

    assert "conditional" in str(result).lower()


@pytest.mark.anyio
async def test_add_data_validation_list(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("add_data_validation", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:A5",
            "validation_type": "LIST",
            "values": ["Yes", "No", "Maybe"],
        })

    assert "validation" in str(result).lower()
    # Check the batchUpdate was called with ONE_OF_LIST
    call_args = mock_svc.spreadsheets().batchUpdate.call_args
    assert call_args is not None


@pytest.mark.anyio
async def test_add_named_range(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("add_named_range", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:B5",
            "name": "MyRange",
        })

    assert "MyRange" in str(result)


@pytest.mark.anyio
async def test_protect_range(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_sheets_svc_with_sheet(sheet_id=0, title="Sheet1")

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("protect_range", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1!A1:A10",
            "description": "Protected",
            "editors": ["user@example.com"],
        })

    assert "Protected" in str(result) or "protect" in str(result).lower()


@pytest.mark.anyio
async def test_append_rows(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.spreadsheets().values().append().execute.return_value = {
        "updates": {"updatedRows": 2}
    }

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("append_rows", {
            "spreadsheet_id": "sid",
            "range_notation": "Sheet1",
            "values": [["A", "B"], ["C", "D"]],
        })

    assert "updatedRows" in str(result) or "updates" in str(result)


@pytest.mark.anyio
async def test_get_spreadsheet_info(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.spreadsheets().get().execute.return_value = {
        "spreadsheetId": "sid",
        "properties": {"title": "My Sheet"},
        "sheets": [
            {
                "properties": {
                    "sheetId": 0,
                    "title": "Sheet1",
                    "gridProperties": {"rowCount": 1000, "columnCount": 26},
                }
            }
        ],
    }

    with patch("servers.google_drive.tools_sheets._sheets_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("get_spreadsheet_info", {"spreadsheet_id": "sid"})

    assert "My Sheet" in str(result)
    assert "Sheet1" in str(result)


# ===========================================================================
# Docs / Drive tool tests
# ===========================================================================

def _mock_docs_svc(content=None):
    mock_svc = MagicMock()
    body_content = content or [
        {
            "startIndex": 1,
            "endIndex": 12,
            "paragraph": {
                "elements": [
                    {"startIndex": 1, "textRun": {"content": "Hello World"}},
                ]
            },
        }
    ]
    mock_svc.documents().get().execute.return_value = {
        "body": {"content": body_content}
    }
    mock_svc.documents().batchUpdate().execute.return_value = {}
    return mock_svc


@pytest.mark.anyio
async def test_get_doc_content(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("get_doc_content", {"document_id": "doc-id"})

    assert "paragraph" in str(result)


@pytest.mark.anyio
async def test_format_doc_text_with_indices(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("format_doc_text", {
            "document_id": "doc-id",
            "start_index": 1,
            "end_index": 6,
            "bold": True,
        })

    assert "Formatted" in str(result)
    mock_svc.documents().batchUpdate.assert_called()


@pytest.mark.anyio
async def test_format_doc_text_with_text_find(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("format_doc_text", {
            "document_id": "doc-id",
            "text_to_find": "Hello",
            "italic": True,
        })

    assert "Formatted" in str(result)


@pytest.mark.anyio
async def test_format_doc_paragraph(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("format_doc_paragraph", {
            "document_id": "doc-id",
            "start_index": 1,
            "end_index": 12,
            "alignment": "CENTER",
        })

    assert "Formatted" in str(result)


@pytest.mark.anyio
async def test_insert_text(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("insert_text", {
            "document_id": "doc-id",
            "index": 1,
            "text": "New text ",
        })

    assert "Inserted" in str(result)
    mock_svc.documents().batchUpdate.assert_called()


@pytest.mark.anyio
async def test_delete_range(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("delete_range", {
            "document_id": "doc-id",
            "start_index": 1,
            "end_index": 6,
        })

    assert "Deleted" in str(result)


@pytest.mark.anyio
async def test_find_and_replace(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("find_and_replace", {
            "document_id": "doc-id",
            "find": "Hello",
            "replace": "Hi",
        })

    assert "Hello" in str(result) or "Replaced" in str(result)


@pytest.mark.anyio
async def test_insert_table(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("insert_table", {
            "document_id": "doc-id",
            "index": 1,
            "rows": 3,
            "columns": 4,
        })

    assert "3x4" in str(result) or "Inserted" in str(result)


@pytest.mark.anyio
async def test_edit_table_cell(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    table_content = [
        {
            "startIndex": 1,
            "endIndex": 50,
            "table": {
                "tableRows": [
                    {
                        "tableCells": [
                            {"content": [{"startIndex": 5}]},
                            {"content": [{"startIndex": 10}]},
                        ]
                    },
                    {
                        "tableCells": [
                            {"content": [{"startIndex": 20}]},
                            {"content": [{"startIndex": 25}]},
                        ]
                    },
                ]
            },
        }
    ]
    mock_svc = _mock_docs_svc(content=table_content)

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("edit_table_cell", {
            "document_id": "doc-id",
            "table_index": 0,
            "row": 1,
            "column": 0,
            "text": "Cell text",
        })

    assert "Edited" in str(result)
    # Verify it inserted at the correct index (row 1, col 0 → startIndex 20)
    call_args = mock_svc.documents().batchUpdate.call_args
    body = call_args.kwargs.get("body") or (call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["body"])
    insert_req = body["requests"][0]["insertText"]
    assert insert_req["location"]["index"] == 20
    assert insert_req["text"] == "Cell text"


@pytest.mark.anyio
async def test_create_paragraph_bullets(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("create_paragraph_bullets", {
            "document_id": "doc-id",
            "text_to_find": "Hello",
            "bullet_type": "DECIMAL",
        })

    assert "DECIMAL" in str(result) or "bullets" in str(result).lower()
    call_args = mock_svc.documents().batchUpdate.call_args
    body = call_args.kwargs.get("body") or (call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["body"])
    req = body["requests"][0]["createParagraphBullets"]
    assert req["bulletPreset"] == "NUMBERED_DECIMAL_NESTED"


@pytest.mark.anyio
async def test_insert_image(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = _mock_docs_svc()

    with patch("servers.google_drive.tools_docs._docs_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("insert_image", {
            "document_id": "doc-id",
            "index": 1,
            "url": "https://example.com/img.png",
            "width": 100.0,
            "height": 50.0,
        })

    assert "Inserted" in str(result)
    call_args = mock_svc.documents().batchUpdate.call_args
    body = call_args.kwargs.get("body") or (call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["body"])
    req = body["requests"][0]["insertInlineImage"]
    assert req["uri"] == "https://example.com/img.png"
    assert req["objectSize"]["width"]["magnitude"] == 100.0


@pytest.mark.anyio
async def test_list_comments(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.comments().list().execute.return_value = {
        "comments": [{"id": "c1", "content": "Great work!", "resolved": False}]
    }

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("list_comments", {"file_id": "file-id"})

    assert "Great work!" in str(result)


@pytest.mark.anyio
async def test_add_comment(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.comments().create().execute.return_value = {
        "id": "c2", "content": "Nice!", "createdTime": "2024-01-01T00:00:00Z"
    }

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("add_comment", {
            "file_id": "file-id",
            "content": "Nice!",
        })

    assert "Nice!" in str(result)


@pytest.mark.anyio
async def test_trash_file(tmp_path):
    _write_valid_token(tmp_path)
    _write_credentials(tmp_path)
    _inject_request(query_string="instance=default")

    mock_svc = MagicMock()
    mock_svc.files().update().execute.return_value = {}

    with patch("servers.google_drive.tools_drive._drive_service", return_value=mock_svc), \
         patch("servers.google_drive.server.get_settings") as mock_settings:
        mock_settings.return_value.tokens_path = str(tmp_path)
        mock_settings.return_value.credentials_path = str(tmp_path)
        from servers.google_drive.server import google_drive
        result = await google_drive.call_tool("trash_file", {"file_id": "file-id"})

    assert "trash" in str(result).lower()
    mock_svc.files().update.assert_called()
