import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.slack.bot import SlackIntegration


@pytest.fixture
def slack():
    return SlackIntegration()


class TestSlackIntegration:
    def test_metadata(self, slack):
        assert slack.name == "slack"
        assert "SLACK_BOT_TOKEN" in slack.required_env_vars
        assert "SLACK_APP_TOKEN" in slack.required_env_vars

    def test_not_configured(self, slack):
        with patch.dict(os.environ, {}, clear=True):
            missing = slack.check_env_vars()
            assert "SLACK_BOT_TOKEN" in missing
            assert "SLACK_APP_TOKEN" in missing
            assert not slack.is_configured

    def test_configured(self, slack):
        env = {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_APP_TOKEN": "xapp-test"}
        with patch.dict(os.environ, env):
            assert slack.is_configured

    async def test_health_check_success(self, slack):
        mock_client = AsyncMock()
        mock_client.auth_test.return_value = {"ok": True}
        with patch.object(slack, "get_client", return_value=mock_client):
            result = await slack.health_check()
            assert result is True

    async def test_health_check_failure(self, slack):
        mock_client = AsyncMock()
        mock_client.auth_test.return_value = {"ok": False}
        with patch.object(slack, "get_client", return_value=mock_client):
            result = await slack.health_check()
            assert result is False

    async def test_health_check_exception(self, slack):
        mock_client = AsyncMock()
        mock_client.auth_test.side_effect = Exception("Connection failed")
        with patch.object(slack, "get_client", return_value=mock_client):
            result = await slack.health_check()
            assert result is False

    async def test_post_thread_update(self, slack):
        mock_client = AsyncMock()
        mock_client.chat_postMessage.return_value = {
            "ts": "1234567890.123456",
            "channel": "C123456",
        }
        with patch.object(slack, "get_client", return_value=mock_client):
            result = await slack.post_thread_update(
                channel="C123456",
                thread_ts="1234567890.000000",
                message="Test update",
            )
            assert result is not None
            assert result["ts"] == "1234567890.123456"
            assert result["channel"] == "C123456"
            mock_client.chat_postMessage.assert_called_once_with(
                channel="C123456",
                thread_ts="1234567890.000000",
                text="Test update",
            )

    async def test_post_thread_update_failure(self, slack):
        mock_client = AsyncMock()
        mock_client.chat_postMessage.side_effect = Exception("API error")
        with patch.object(slack, "get_client", return_value=mock_client):
            result = await slack.post_thread_update(
                channel="C123456",
                thread_ts="1234567890.000000",
                message="Test update",
            )
            assert result is None
