from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.cost import TokenUsage, parse_claude_code_usage
from app.agent.prompts import build_plan_prompt, build_review_prompt, build_work_prompt
from app.agent.runner import run_agent, save_log
from app.models import AgentLog, AgentRun, LogType, RunStage, RunStatus, Task, TaskStatus
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
        log = await save_log(sample_run.id, "Test message")
        assert log.type == LogType.TEXT
        assert log.content == {"message": "Test message"}

    async def test_save_error_log(self, sample_run):
        log = await save_log(sample_run.id, "Error occurred", LogType.ERROR)
        assert log.type == LogType.ERROR


class TestRunAgent:
    async def test_run_agent_success(self, sample_task):
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([b"Analyzing code...\n", b"Writing plan...\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(
            return_value=b"Input: 50000 tokens\nOutput: 10000 tokens\n"
        )
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
        mock_process.stdout = AsyncIteratorMock([b"Error...\n"])
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
