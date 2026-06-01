from __future__ import annotations

import sys

from loguru import logger as _root_logger

# Remove loguru's default stderr sink so only our configured sinks emit.
_root_logger.remove()

# Audit sink: serialized JSON, stdout, filtered to records bound with audit=True.
_root_logger.add(
    sys.stdout,
    serialize=True,
    level="INFO",
    filter=lambda record: record["extra"].get("audit") is True,
)

_audit_logger = _root_logger.bind(audit=True)


class AuditLogger:
    def log(
        self,
        *,
        request_id: str,
        client: str,
        server: str,
        tool: str,
        instance: str,
        status: str,
        latency_ms: int,
        error_code: int | None,
        tool_args_redacted: list[str],
    ) -> None:
        _audit_logger.info(
            "tool_call",
            request_id=request_id,
            client=client,
            server=server,
            tool=tool,
            instance=instance,
            status=status,
            latency_ms=latency_ms,
            error_code=error_code,
            tool_args_redacted=tool_args_redacted,
        )
