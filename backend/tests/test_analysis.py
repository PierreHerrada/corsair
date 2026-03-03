from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.agent.analysis import _call_anthropic, _post_analysis_notifications, analyze_task
from app.models import ChatMessage, Task, TaskStatus


def _make_response(status_code: int, json_data: dict) -> httpx.Response:
    """Build a mock httpx.Response with a request object attached."""
    resp = httpx.Response(status_code, json=json_data)
    resp._request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return resp


class TestCallAnthropic:
    async def test_success(self):
        mock_response = _make_response(200, {
            "content": [{"type": "text", "text": "Analysis result"}],
        })

        with patch("app.agent.analysis.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await _call_anthropic("test prompt")
            assert result == "Analysis result"

            # Verify request shape
            call_kwargs = mock_client.post.call_args
            assert call_kwargs[0][0] == "https://api.anthropic.com/v1/messages"
            headers = call_kwargs[1]["headers"]
            assert "x-api-key" in headers
            assert headers["anthropic-version"] == "2023-06-01"
            body = call_kwargs[1]["json"]
            assert body["model"] == "claude-sonnet-4-20250514"
            assert body["max_tokens"] == 1024
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"] == "test prompt"

    async def test_api_error_raises(self):
        mock_response = _make_response(500, {"error": "Server error"})

        with patch("app.agent.analysis.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await _call_anthropic("test prompt")


class TestAnalyzeTask:
    async def test_analysis_stored(self, sample_task):
        with patch("app.agent.analysis._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "This is the analysis."

            with patch("app.agent.analysis._post_analysis_notifications", new_callable=AsyncMock):
                result = await analyze_task(sample_task)

            assert result == "This is the analysis."

            # Verify task was updated in DB
            refreshed = await Task.get(id=sample_task.id)
            assert refreshed.analysis == "This is the analysis."

    async def test_notifications_sent(self, sample_task):
        with patch("app.agent.analysis._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Analysis text"

            with patch("app.agent.analysis._post_analysis_notifications", new_callable=AsyncMock) as mock_notify:
                await analyze_task(sample_task)
                mock_notify.assert_called_once_with(sample_task, "Analysis text")

    async def test_api_failure_stores_error(self, sample_task):
        with patch("app.agent.analysis._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = Exception("API timeout")

            result = await analyze_task(sample_task)

            assert result == "Analysis failed — see logs for details."
            refreshed = await Task.get(id=sample_task.id)
            assert refreshed.analysis == "Analysis failed — see logs for details."


class TestGatherMessages:
    async def test_with_matching_messages(self, sample_task):
        """Verify that ChatMessages with matching channel/thread are gathered."""
        await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id=sample_task.slack_channel,
            user_id="U1",
            user_name="Alice",
            message="First message",
            slack_ts=sample_task.slack_thread_ts,
        )
        await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id=sample_task.slack_channel,
            user_id="U2",
            user_name="Bob",
            message="Thread reply",
            slack_ts="1234567890.999999",
            thread_ts=sample_task.slack_thread_ts,
        )

        with patch("app.agent.analysis._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Analysis"

            with patch("app.agent.analysis._post_analysis_notifications", new_callable=AsyncMock):
                await analyze_task(sample_task)

            # Check the prompt passed to _call_anthropic includes conversation context
            prompt = mock_api.call_args[0][0]
            assert "[Alice]: First message" in prompt
            assert "[Bob]: Thread reply" in prompt

    async def test_no_messages(self):
        """Analysis works for Jira-only tasks with no Slack messages."""
        task = await Task.create(
            id=uuid.uuid4(),
            title="Jira-only task",
            description="Fix a bug",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
            jira_key="SWE-42",
        )

        with patch("app.agent.analysis._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Jira analysis"

            with patch("app.agent.analysis._post_analysis_notifications", new_callable=AsyncMock):
                result = await analyze_task(task)

            assert result == "Jira analysis"
            prompt = mock_api.call_args[0][0]
            assert "No conversation context available." in prompt


class TestPostAnalysisNotifications:
    async def test_jira_notification(self, sample_task):
        sample_task.jira_key = "SWE-123"
        await sample_task.save()

        mock_jira = AsyncMock()
        mock_jira.add_comment = AsyncMock()

        with patch("app.integrations.registry.IntegrationRegistry") as mock_registry:
            mock_registry.get.side_effect = lambda name: mock_jira if name == "jira" else None

            await _post_analysis_notifications(sample_task, "Test analysis")
            mock_jira.add_comment.assert_called_once_with(
                "SWE-123", "Task Analysis:\nTest analysis"
            )

    async def test_slack_notification(self, sample_task):
        mock_slack = AsyncMock()
        mock_slack.post_thread_update = AsyncMock()

        with patch("app.integrations.registry.IntegrationRegistry") as mock_registry:
            mock_registry.get.side_effect = lambda name: mock_slack if name == "slack" else None

            await _post_analysis_notifications(sample_task, "Test analysis")
            mock_slack.post_thread_update.assert_called_once_with(
                sample_task.slack_channel,
                sample_task.slack_thread_ts,
                "Analysis:\nTest analysis",
            )

    async def test_notification_failure_does_not_raise(self, sample_task):
        sample_task.jira_key = "SWE-123"
        await sample_task.save()

        mock_jira = AsyncMock()
        mock_jira.add_comment = AsyncMock(side_effect=Exception("Jira down"))

        with patch("app.integrations.registry.IntegrationRegistry") as mock_registry:
            mock_registry.get.side_effect = lambda name: mock_jira if name == "jira" else None

            # Should not raise
            await _post_analysis_notifications(sample_task, "Test analysis")
