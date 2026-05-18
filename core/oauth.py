import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

if TYPE_CHECKING:
    from fastmcp import FastMCP


class OAuthBase:
    def __init__(self, server: str, instance: str, tokens_path: str) -> None:
        self.server = server
        self.instance = instance
        self.tokens_path = Path(tokens_path)

    def _token_file(self) -> Path:
        return self.tokens_path / f"{self.server}-{self.instance}.json"

    def _save_token(self, creds: Credentials) -> None:
        data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "expiry": creds.expiry.timestamp(),
        }
        token_file = self._token_file()
        token_file.write_text(json.dumps(data))
        token_file.chmod(0o600)

    def register_reauth_tool(self, server: "FastMCP") -> None:
        oauth = self

        @server.tool()
        async def reauth() -> str:
            oauth.clear_token()
            return "Token cleared. Re-authenticate on next request."

    def clear_token(self) -> None:
        token_file = self._token_file()
        if token_file.exists():
            token_file.unlink()

    def get_token(self, credentials_path: str) -> str:
        token_file = self._token_file()
        if token_file.exists():
            data = json.loads(token_file.read_text())
            if data.get("expiry", 0) > time.time():
                return data["token"]
            creds = Credentials(
                token=data["token"],
                refresh_token=data["refresh_token"],
                token_uri=data["token_uri"],
                client_id=data["client_id"],
                client_secret=data["client_secret"],
            )
            creds.refresh(Request())
            self._save_token(creds)
            return creds.token
        raise RuntimeError("No valid token available")
