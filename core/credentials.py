from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS


class CredentialsStore:
    def __init__(self, credentials_path: str) -> None:
        self._base = Path(credentials_path)

    def resolve(self, server: str, instance: str) -> str:
        path = self._base / server / f"{instance}.json"
        if not path.exists():
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=(
                        f"No credentials file for instance '{instance}'. "
                        f"Place your OAuth client secret at: {path}"
                    ),
                )
            )
        return str(path)
