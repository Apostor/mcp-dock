import pytest

from core.credentials import require_headers


def test_returns_values_for_present_headers():
    headers = {"x-trello-key": "key123", "x-trello-token": "tok456"}
    result = require_headers(headers, "x-trello-key", "x-trello-token")
    assert result == {"x-trello-key": "key123", "x-trello-token": "tok456"}


def test_header_lookup_is_case_insensitive():
    headers = {"X-Trello-Key": "key123"}
    result = require_headers(headers, "x-trello-key")
    assert result["x-trello-key"] == "key123"


def test_raises_with_all_missing_headers_named():
    with pytest.raises(Exception) as exc_info:
        require_headers({}, "x-trello-key", "x-trello-token")
    assert "x-trello-key" in str(exc_info.value)
    assert "x-trello-token" in str(exc_info.value)
