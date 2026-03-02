from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.cost import TokenUsage, parse_claude_code_usage
from app.agent.prompts import build_plan_prompt, build_review_prompt, build_work_prompt
from app.agent.runner import _get_base_prompt, _notify_run_complete, run_agent, save_log
from app.models import AgentLog, AgentRun, LogType, RunStage, RunStatus, Setting, Task, TaskStatus
from app.websocket.manager import ConnectionManager


class AsyncIteratorMock:
    """A proper async iterator for mocking process.stdout."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


class TestTokenUsage:
    def test_zero_cost(self):
        usage = TokenUsage(tokens_in=0, tokens_out=0)
        assert usage.cost_usd == Decimal("0.000000")

    def test_cost_calculation(self):
        usage = TokenUsage(tokens_in=1_000_000, tokens_out=1_000_000)
        # 1M input * $3/M + 1M output * $15/M = $18
        assert usage.cost_usd == Decimal("18.000000")

    def test_typical_usage(self):
        usage = TokenUsage(tokens_in=50000, tokens_out=10000)
        # 50k * 3/1M + 10k * 15/1M = 0.15 + 0.15 = 0.30
        assert usage.cost_usd == Decimal("0.300000")


class TestParseUsage:
    def test_parse_input_output(self):
        stderr = "Input: 50000 tokens\nOutput: 10000 tokens\n"
        usage = parse_claude_code_usage(stderr)
        assert usage.tokens_in == 50000
        assert usage.tokens_out == 10000

    def test_parse_with_commas(self):
        stderr = "Input: 1,000,000 tokens\nOutput: 500,000 tokens\n"
        usage = parse_claude_code_usage(stderr)
        assert usage.tokens_in == 1000000
        assert usage.tokens_out == 500000

    def test_parse_empty(self):
        usage = parse_claude_code_usage("")
        assert usage.tokens_in == 0
        assert usage.tokens_out == 0

    def test_parse_no_match(self):
        usage = parse_claude_code_usage("some random output")
        assert usage.tokens_in == 0
        assert usage.tokens_out == 0

    def test_parse_lowercase(self):
        stderr = "input: 25000 tokens, output: 5000 tokens"
        usage = parse_claude_code_usage(stderr)
        assert usage.tokens_in == 25000
        assert usage.tokens_out == 5000


class TestPrompts:
    def test_plan_prompt(self):
        prompt = build_plan_prompt("Fix bug", "There is a bug", "Bug is fixed")
        assert "Fix bug" in prompt
        assert "There is a bug" in prompt
        assert "Bug is fixed" in prompt
        assert "PLAN.md" in prompt

    def test_work_prompt(self):
        prompt = build_work_prompt()
        assert "PLAN.md" in prompt
        assert "Commit" in prompt
        assert "Do not open a PR" in prompt

    def test_review_prompt(self):
        prompt = build_review_prompt("SWE-123", "Fix bug", "https://jira.com/SWE-123")
        assert "SWE-123" in prompt
        assert "Fix bug" in prompt
        assert "https://jira.com/SWE-123" in prompt
        assert "Pull Request" in prompt


class TestSaveLog:
    async def test_save_log(self, sample_run):
        log = await save_log(sample_run.id, {"message": "Test message"})
        assert log.type == LogType.TEXT
        assert log.content == {"message": "Test message"}

    async def test_save_error_log(self, sample_run):
        log = await save_log(sample_run.id, {"message": "Error occurred"}, LogType.ERROR)
        assert log.type == LogType.ERROR


class TestRunAgent:
    async def test_run_agent_success(self, sample_task):
        import json

        result_event = json.dumps({
            "type": "result",
            "cost_usd": 0.3,
            "duration_ms": 5000,
            "num_input_tokens": 50000,
            "num_output_tokens": 10000,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            run = await run_agent(sample_task, RunStage.PLAN)
            assert run.status == RunStatus.DONE
            assert run.tokens_in == 50000
            assert run.tokens_out == 10000

        # Check task status updated
        task = await Task.get(id=sample_task.id)
        assert task.status == TaskStatus.PLANNED

    async def test_run_agent_failure(self, sample_task):
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([b'{"type":"error","error":{"message":"fail"}}\n'])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            run = await run_agent(sample_task, RunStage.PLAN)
            assert run.status == RunStatus.FAILED

        task = await Task.get(id=sample_task.id)
        assert task.status == TaskStatus.FAILED

    async def test_run_agent_exception(self, sample_task):
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("claude not found"),
        ):
            run = await run_agent(sample_task, RunStage.PLAN)
            assert run.status == RunStatus.FAILED

        task = await Task.get(id=sample_task.id)
        assert task.status == TaskStatus.FAILED


class TestBasePrompt:
    async def test_get_base_prompt_returns_value(self):
        await Setting.create(
            id=uuid.uuid4(),
            key="base_prompt",
            value="Always write tests first.",
        )
        result = await _get_base_prompt()
        assert result == "Always write tests first."

    async def test_get_base_prompt_returns_empty_when_not_set(self):
        result = await _get_base_prompt()
        assert result == ""

    async def test_get_base_prompt_returns_empty_for_whitespace(self):
        await Setting.create(
            id=uuid.uuid4(),
            key="base_prompt",
            value="   ",
        )
        result = await _get_base_prompt()
        assert result == ""

    async def test_base_prompt_prepended_to_agent_call(self, sample_task):
        await Setting.create(
            id=uuid.uuid4(),
            key="base_prompt",
            value="Custom instructions here.",
        )

        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await run_agent(sample_task, RunStage.PLAN)
            call_args = mock_exec.call_args
            prompt_arg = call_args[0][-1]  # last positional arg is the prompt
            assert prompt_arg.startswith("Custom instructions here.\n\n")

    async def test_no_base_prompt_not_prepended(self, sample_task):
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await run_agent(sample_task, RunStage.PLAN)
            call_args = mock_exec.call_args
            prompt_arg = call_args[0][-1]
            assert not prompt_arg.startswith("Custom instructions here.")
            assert "senior software engineer" in prompt_arg


class TestNotifyRunComplete:
    async def test_notify_success_calls_jira_and_slack(self, sample_task):
        sample_task.jira_key = "SWE-42"
        await sample_task.save()

        mock_jira = AsyncMock()
        mock_jira.add_comment = AsyncMock(return_value=True)

        mock_slack = AsyncMock()
        mock_slack.post_thread_update = AsyncMock(return_value={"ts": "1"})

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            side_effect=lambda n: {"jira": mock_jira, "slack": mock_slack}.get(n),
        ):
            await _notify_run_complete(sample_task, RunStage.PLAN, success=True)

        mock_jira.add_comment.assert_called_once_with(
            "SWE-42", "Plan stage completed successfully."
        )
        mock_slack.post_thread_update.assert_called_once_with(
            "C123456", "1234567890.123456", "Plan stage completed successfully."
        )

    async def test_notify_failure_message(self, sample_task):
        sample_task.jira_key = "SWE-42"
        await sample_task.save()

        mock_jira = AsyncMock()
        mock_jira.add_comment = AsyncMock(return_value=True)

        mock_slack = AsyncMock()
        mock_slack.post_thread_update = AsyncMock(return_value={"ts": "1"})

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            side_effect=lambda n: {"jira": mock_jira, "slack": mock_slack}.get(n),
        ):
            await _notify_run_complete(sample_task, RunStage.WORK, success=False)

        mock_jira.add_comment.assert_called_once_with("SWE-42", "Work stage failed.")
        mock_slack.post_thread_update.assert_called_once_with(
            "C123456", "1234567890.123456", "Work stage failed."
        )

    async def test_notify_skips_jira_when_no_key(self, sample_task):
        mock_jira = AsyncMock()
        mock_jira.name = "jira"

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            return_value=None,
        ):
            await _notify_run_complete(sample_task, RunStage.PLAN, success=True)

        mock_jira.add_comment.assert_not_called()

    async def test_notify_does_not_crash_on_jira_error(self, sample_task):
        sample_task.jira_key = "SWE-42"
        await sample_task.save()

        mock_jira = AsyncMock()
        mock_jira.add_comment = AsyncMock(side_effect=Exception("Jira down"))

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            side_effect=lambda n: {"jira": mock_jira}.get(n),
        ):
            # Should not raise
            await _notify_run_complete(sample_task, RunStage.PLAN, success=True)

    async def test_notify_does_not_crash_on_slack_error(self, sample_task):
        mock_slack = AsyncMock()
        mock_slack.post_thread_update = AsyncMock(side_effect=Exception("Slack down"))

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            side_effect=lambda n: {"slack": mock_slack}.get(n),
        ):
            # Should not raise
            await _notify_run_complete(sample_task, RunStage.PLAN, success=True)


class TestConnectionManager:
    def test_init(self):
        mgr = ConnectionManager()
        assert mgr.get_connections("run-1") == []

    async def test_connect_disconnect(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        await mgr.connect("run-1", mock_ws)
        assert len(mgr.get_connections("run-1")) == 1
        mgr.disconnect("run-1", mock_ws)
        assert mgr.get_connections("run-1") == []

    async def test_broadcast(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        await mgr.connect("run-1", mock_ws)

        mock_log = MagicMock()
        mock_log.id = uuid.uuid4()
        mock_log.run_id = uuid.uuid4()
        mock_log.type = LogType.TEXT
        mock_log.content = {"message": "test"}
        mock_log.created_at = None

        await mgr.broadcast("run-1", mock_log)
        mock_ws.send_text.assert_called_once()

    async def test_broadcast_removes_dead_connections(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.send_text.side_effect = Exception("Connection closed")
        await mgr.connect("run-1", mock_ws)

        mock_log = MagicMock()
        mock_log.id = uuid.uuid4()
        mock_log.run_id = uuid.uuid4()
        mock_log.type = LogType.TEXT
        mock_log.content = {"message": "test"}
        mock_log.created_at = None

        await mgr.broadcast("run-1", mock_log)
        assert mgr.get_connections("run-1") == []

    async def test_broadcast_no_connections(self):
        mgr = ConnectionManager()
        mock_log = MagicMock()
        # Should not raise
        await mgr.broadcast("nonexistent", mock_log)
