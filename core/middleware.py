_CREDENTIAL_KEYWORDS = {"token", "key", "secret", "password"}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: "[REDACTED]" if any(kw in k.lower() for kw in _CREDENTIAL_KEYWORDS) else v
        for k, v in headers.items()
    }
