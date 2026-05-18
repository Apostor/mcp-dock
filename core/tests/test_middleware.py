from core.middleware import redact_headers


def test_redacts_credential_headers():
    headers = {"x-trello-key": "secret", "x-github-token": "ghp_abc", "x-custom-id": "board123"}
    result = redact_headers(headers)
    assert result["x-trello-key"] == "[REDACTED]"
    assert result["x-github-token"] == "[REDACTED]"
    assert result["x-custom-id"] == "board123"


def test_redaction_matches_mixed_case_header_names():
    headers = {"X-Trello-Key": "abc", "X-Google-Secret": "xyz", "X-Board-Id": "123"}
    result = redact_headers(headers)
    assert result["X-Trello-Key"] == "[REDACTED]"
    assert result["X-Google-Secret"] == "[REDACTED]"
    assert result["X-Board-Id"] == "123"
