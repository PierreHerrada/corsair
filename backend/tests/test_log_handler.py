from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.log_handler import DatabaseLogHandler, _resolve_source, setup_db_logging


class TestResolveSource:
    def test_jira_logger(self):
        assert _resolve_source("app.integrations.jira.client") == "jira"

    def test_slack_logger(self):
        assert _resolve_source("app.integrations.slack.bot") == "slack"

    def test_github_logger(self):
        assert _resolve_source("app.integrations.github.hooks") == "github"

    def test_datadog_logger(self):
        assert _resolve_source("app.integrations.datadog.api") == "datadog"

    def test_generic_integration(self):
        assert _resolve_source("app.integrations.unknown") == "integrations"

    def test_main_logger(self):
        assert _resolve_source("app.main") == "main"

    def test_app_logger(self):
        assert _resolve_source("app.something") == "app"

    def test_unrelated_logger(self):
        assert _resolve_source("uvicorn.access") is None


class TestDatabaseLogHandler:
    def test_emit_buffers_entry(self):
        handler = DatabaseLogHandler()
        record = logging.LogRecord(
            name="app.integrations.jira",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        assert len(handler._buffer) == 1
        assert handler._buffer[0]["source"] == "jira"
        assert handler._buffer[0]["message"] == "test message"

    def test_emit_skips_unrelated_logger(self):
        handler = DatabaseLogHandler()
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="GET /health",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        assert len(handler._buffer) == 0

    def test_max_buffer(self):
        handler = DatabaseLogHandler(max_buffer=2)
        for i in range(5):
            record = logging.LogRecord(
                name="app.main",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"msg {i}",
                args=None,
                exc_info=None,
            )
            handler.emit(record)
        assert len(handler._buffer) == 2

    @pytest.mark.asyncio
    async def test_persist(self):
        handler = DatabaseLogHandler()
        entry = {
            "id": "test-id",
            "source": "jira",
            "level": "INFO",
            "logger_name": "app.integrations.jira",
            "message": "synced",
        }
        with patch("app.log_handler.InternalLog", create=True) as mock_model:
            mock_model.create = AsyncMock()
            # Patch the import inside _persist
            with patch(
                "app.models.internal_log.InternalLog.create", new=AsyncMock(),
            ) as mock_create:
                await handler._persist(entry)
                mock_create.assert_called_once()


class TestSetupDbLogging:
    def test_returns_handler(self):
        # Reset singleton
        import app.log_handler as mod
        mod._handler = None
        handler = setup_db_logging()
        assert isinstance(handler, DatabaseLogHandler)
        # Calling again returns same instance
        assert setup_db_logging() is handler
        # Cleanup
        logging.getLogger("app").removeHandler(handler)
        mod._handler = None
