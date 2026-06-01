import os

# Disable the gateway by default so existing tests run without gateway.yaml.
# Gateway-specific tests set GATEWAY_ENABLED=true explicitly via monkeypatch.
os.environ.setdefault("GATEWAY_ENABLED", "false")
