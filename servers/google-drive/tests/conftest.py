import importlib
import importlib.util
import sys
import types
from pathlib import Path

_SERVER_PATH = Path(__file__).parent.parent / "server.py"
_MODULE_KEY = "servers.google_drive.server"
_PARENT_KEY = "servers.google_drive"

# Ensure the real `servers` namespace package is imported first so its
# __path__ stays intact (required by test_cli.py's dynamic server creation).
_servers_pkg = importlib.import_module("servers")

# Attach a google_drive stub onto the real servers namespace so that
# `patch("servers.google_drive.server.X")` can traverse the hierarchy.
if _PARENT_KEY not in sys.modules:
    stub = types.ModuleType(_PARENT_KEY)
    stub.__path__ = [str(_SERVER_PATH.parent)]
    stub.__package__ = _PARENT_KEY
    sys.modules[_PARENT_KEY] = stub
    _servers_pkg.google_drive = stub

# Load the actual server module from the hyphenated directory.
if _MODULE_KEY not in sys.modules:
    spec = importlib.util.spec_from_file_location(_MODULE_KEY, _SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_KEY] = module
    sys.modules[_PARENT_KEY].server = module
    spec.loader.exec_module(module)

