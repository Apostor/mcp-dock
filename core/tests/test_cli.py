import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from core.cli import app


runner = CliRunner()


class TestNew:
    def test_generated_test_passes_immediately(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["new", "myservice"])

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "servers/myservice/tests/test_server.py", "-x", "-q"],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_generated_server_is_importable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        runner.invoke(app, ["new", "myservice"])

        import importlib
        mod = importlib.import_module("servers.myservice.server")
        assert hasattr(mod, "myservice")

    def test_creates_all_five_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["new", "slack"])

        assert result.exit_code == 0
        base = tmp_path / "servers" / "slack"
        assert (base / "__init__.py").exists()
        assert (base / "server.py").exists()
        assert (base / "pyproject.toml").exists()
        assert (base / "README.md").exists()
        assert (base / "tests" / "test_server.py").exists()


class TestRun:
    def test_run_invokes_uvicorn(self, monkeypatch):
        import uvicorn
        calls = []
        monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))

        result = runner.invoke(app, ["run"])

        assert result.exit_code == 0
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert args[0] == "app:app"

    def test_run_defaults_to_port_8000(self, monkeypatch):
        import uvicorn
        calls = []
        monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))

        runner.invoke(app, ["run"])

        _, kwargs = calls[0]
        assert kwargs.get("port") == 8000


class TestHelp:
    def test_help_exits_zero_and_lists_subcommands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "new" in result.output
