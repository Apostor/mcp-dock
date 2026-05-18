import pytest

from core.credentials import CredentialsStore


class TestCredentialsStore:
    def test_resolve_returns_path_when_file_exists(self, tmp_path):
        creds_dir = tmp_path / "google-drive"
        creds_dir.mkdir(parents=True)
        (creds_dir / "personal.json").write_text("{}")

        store = CredentialsStore(str(tmp_path))
        result = store.resolve("google-drive", "personal")

        assert result == str(tmp_path / "google-drive" / "personal.json")

    def test_resolve_raises_mcp_error_when_file_missing(self, tmp_path):
        store = CredentialsStore(str(tmp_path))
        with pytest.raises(Exception) as exc_info:
            store.resolve("google-drive", "missing-instance")
        assert "missing-instance" in str(exc_info.value)
