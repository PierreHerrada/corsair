from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from typing import Optional

# Map logger name prefixes to human-readable sources
_SOURCE_MAP: dict[str, str] = {
    "app.integrations.jira": "jira",
    "app.integrations.slack": "slack",
    "app.integrations.github": "github",
    "app.integrations.datadog": "datadog",
    "app.integrations": "integrations",
    "app.main": "main",
    "app": "app",
}


def _resolve_source(logger_name: str) -> Optional[str]:
    for prefix, source in _SOURCE_MAP.items():
        if logger_name.startswith(prefix):
            return source
    return None


class DatabaseLogHandler(logging.Handler):
    """Captures log records from integration loggers and persists to DB."""

    def __init__(self, max_buffer: int = 2000) -> None:
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=max_buffer)

    def emit(self, record: logging.LogRecord) -> None:
        source = _resolve_source(record.name)
        if source is None:
            return

        entry = {
            "id": str(uuid.uuid4()),
            "source": source,
            "level": record.levelname,
            "logger_name": record.name,
            "message": self.format(record),
        }
        self._buffer.append(entry)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist(entry))
        except RuntimeError:
            pass  # No event loop yet — skip DB write

    async def _persist(self, entry: dict) -> None:
        try:
            from app.models.internal_log import InternalLog

            await InternalLog.create(
                id=entry["id"],
                source=entry["source"],
                level=entry["level"],
                logger_name=entry["logger_name"],
                message=entry["message"],
            )
        except Exception:
            pass  # Don't let logging errors crash the app


# Singleton handler instance
_handler: Optional[DatabaseLogHandler] = None


def setup_db_logging() -> DatabaseLogHandler:
    """Install the DB log handler on the root app logger."""
    global _handler
    if _handler is not None:
        return _handler

    _handler = DatabaseLogHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))

    # Attach to the app root logger so all app.integrations.* logs are captured
    app_logger = logging.getLogger("app")
    app_logger.addHandler(_handler)

    return _handler
