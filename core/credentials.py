from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS


def require_headers(headers: dict[str, str], *keys: str) -> dict[str, str]:
    headers_lower = {k.lower(): v for k, v in headers.items()}
    missing = [k for k in keys if k.lower() not in headers_lower]
    if missing:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Missing required headers: {', '.join(missing)}")
        )
    return {k: headers_lower[k.lower()] for k in keys}
