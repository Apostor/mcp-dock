import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.oauth import OAuthBase


def _make_token(expired: bool = False) -> dict:
    expiry = time.time() - 60 if expired else time.time() + 3600
    return {
        "token": "access-token-123",
        "refresh_token": "refresh-token-abc",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "expiry": expiry,
    }


@pytest.fixture
def tokens_dir(tmp_path: Path) -> Path:
    return tmp_path / "tokens"


class TestRegisterReauthTool:
    @pytest.mark.anyio
    async def test_registers_reauth_tool_on_server(self, tokens_dir: Path):
        from fastmcp import FastMCP
        tokens_dir.mkdir()
        token_file = tokens_dir / "myservice-default.json"
        token_file.write_text(json.dumps(_make_token()))

        server = FastMCP("myservice")
        oauth = OAuthBase(server="myservice", instance="default", tokens_path=str(tokens_dir))
        oauth.register_reauth_tool(server)

        tool_names = [t.name for t in await server.list_tools()]
        assert "reauth" in tool_names

    @pytest.mark.anyio
    async def test_reauth_tool_clears_token_file(self, tokens_dir: Path):
        from fastmcp import FastMCP
        tokens_dir.mkdir()
        token_file = tokens_dir / "myservice-default.json"
        token_file.write_text(json.dumps(_make_token()))

        server = FastMCP("myservice")
        oauth = OAuthBase(server="myservice", instance="default", tokens_path=str(tokens_dir))
        oauth.register_reauth_tool(server)

        await server.call_tool("reauth", {})

        assert not token_file.exists()


class TestReauth:
    def test_reauth_deletes_token_file(self, tokens_dir: Path):
        tokens_dir.mkdir()
        token_file = tokens_dir / "google-drive-default.json"
        token_file.write_text(json.dumps(_make_token()))

        oauth = OAuthBase(server="google-drive", instance="default", tokens_path=str(tokens_dir))
        oauth.clear_token()

        assert not token_file.exists()

    def test_reauth_no_error_when_no_token_file(self, tokens_dir: Path):
        tokens_dir.mkdir()
        oauth = OAuthBase(server="google-drive", instance="default", tokens_path=str(tokens_dir))
        oauth.clear_token()  # should not raise


class TestTokenIsolation:
    def test_two_instances_use_separate_files(self, tokens_dir: Path):
        tokens_dir.mkdir()

        for instance, token_value in [("work", "token-work"), ("personal", "token-personal")]:
            token_data = _make_token()
            token_data["token"] = token_value
            (tokens_dir / f"google-drive-{instance}.json").write_text(json.dumps(token_data))

        work = OAuthBase(server="google-drive", instance="work", tokens_path=str(tokens_dir))
        personal = OAuthBase(server="google-drive", instance="personal", tokens_path=str(tokens_dir))

        assert work.get_token(credentials_path="/fake/credentials.json") == "token-work"
        assert personal.get_token(credentials_path="/fake/credentials.json") == "token-personal"

    def test_token_file_has_600_permissions(self, tokens_dir: Path):
        tokens_dir.mkdir()
        token_data = _make_token(expired=True)
        token_file = tokens_dir / "google-drive-default.json"
        token_file.write_text(json.dumps(token_data))

        oauth = OAuthBase(server="google-drive", instance="default", tokens_path=str(tokens_dir))

        refreshed_expiry = time.time() + 3600
        with patch("core.oauth.Credentials") as MockCreds:
            mock_creds = MagicMock()
            mock_creds.token = "new-token"
            mock_creds.expiry.timestamp.return_value = refreshed_expiry
            mock_creds.refresh_token = token_data["refresh_token"]
            mock_creds.token_uri = token_data["token_uri"]
            mock_creds.client_id = token_data["client_id"]
            mock_creds.client_secret = token_data["client_secret"]
            MockCreds.return_value = mock_creds

            oauth.get_token(credentials_path="/fake/credentials.json")

        assert oct(token_file.stat().st_mode & 0o777) == oct(0o600)


class TestGetTokenRefresh:
    def test_refreshes_token_when_expired(self, tokens_dir: Path):
        tokens_dir.mkdir()
        token_data = _make_token(expired=True)
        token_file = tokens_dir / "google-drive-default.json"
        token_file.write_text(json.dumps(token_data))

        oauth = OAuthBase(
            server="google-drive",
            instance="default",
            tokens_path=str(tokens_dir),
        )

        refreshed_expiry = time.time() + 3600
        with patch("core.oauth.Credentials") as MockCreds:
            mock_creds = MagicMock()
            mock_creds.token = "new-access-token"
            mock_creds.expiry.timestamp.return_value = refreshed_expiry
            mock_creds.refresh_token = "refresh-token-abc"
            mock_creds.token_uri = token_data["token_uri"]
            mock_creds.client_id = token_data["client_id"]
            mock_creds.client_secret = token_data["client_secret"]
            MockCreds.return_value = mock_creds

            result = oauth.get_token(credentials_path="/fake/credentials.json")

        assert result == "new-access-token"
        mock_creds.refresh.assert_called_once()

    def test_persists_refreshed_token_to_file(self, tokens_dir: Path):
        tokens_dir.mkdir()
        token_data = _make_token(expired=True)
        token_file = tokens_dir / "google-drive-default.json"
        token_file.write_text(json.dumps(token_data))

        oauth = OAuthBase(
            server="google-drive",
            instance="default",
            tokens_path=str(tokens_dir),
        )

        refreshed_expiry = time.time() + 3600
        with patch("core.oauth.Credentials") as MockCreds:
            mock_creds = MagicMock()
            mock_creds.token = "new-access-token"
            mock_creds.expiry.timestamp.return_value = refreshed_expiry
            mock_creds.refresh_token = "refresh-token-abc"
            mock_creds.token_uri = token_data["token_uri"]
            mock_creds.client_id = token_data["client_id"]
            mock_creds.client_secret = token_data["client_secret"]
            MockCreds.return_value = mock_creds

            oauth.get_token(credentials_path="/fake/credentials.json")

        saved = json.loads(token_file.read_text())
        assert saved["token"] == "new-access-token"


class TestGetTokenCached:
    def test_returns_access_token_from_valid_cached_file(self, tokens_dir: Path):
        tokens_dir.mkdir()
        token_data = _make_token()
        token_file = tokens_dir / "google-drive-default.json"
        token_file.write_text(json.dumps(token_data))

        oauth = OAuthBase(
            server="google-drive",
            instance="default",
            tokens_path=str(tokens_dir),
        )

        token = oauth.get_token(credentials_path="/fake/credentials.json")

        assert token == "access-token-123"

    def test_no_http_calls_when_token_valid(self, tokens_dir: Path):
        tokens_dir.mkdir()
        token_data = _make_token()
        token_file = tokens_dir / "google-drive-default.json"
        token_file.write_text(json.dumps(token_data))

        oauth = OAuthBase(
            server="google-drive",
            instance="default",
            tokens_path=str(tokens_dir),
        )

        with patch("google.oauth2.credentials.Credentials.refresh") as mock_refresh:
            oauth.get_token(credentials_path="/fake/credentials.json")
            mock_refresh.assert_not_called()
