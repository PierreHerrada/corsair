from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.cost import TokenUsage, parse_claude_code_usage
from app.agent.prompts import build_plan_prompt, build_review_prompt, build_work_prompt
from app.agent.runner import (
    _active_processes,
    _get_base_prompt,
    _get_enabled_repos,
    _notify_run_complete,
    _stopped_runs,
    run_agent,
    save_log,
    stop_run,
)
from app.models import AgentLog, AgentRun, LogType, Repository, RunStage, RunStatus, Setting, Task, TaskStatus
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

    async def test_run_agent_with_existing_run(self, sample_task):
        """When an existing_run is passed, run_agent reuses it instead of creating a new one."""
        import json

        existing_run = await AgentRun.create(
            id=uuid.uuid4(),
            task=sample_task,
            stage=RunStage.PLAN,
            status=RunStatus.RUNNING,
        )

        result_event = json.dumps({
            "type": "result",
            "cost_usd": 0.1,
            "duration_ms": 1000,
            "num_input_tokens": 1000,
            "num_output_tokens": 500,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            run = await run_agent(sample_task, RunStage.PLAN, existing_run=existing_run)

        # Should reuse the same run ID
        assert run.id == existing_run.id
        assert run.status == RunStatus.DONE
        # Should not have created an extra run
        total_runs = await AgentRun.filter(task_id=sample_task.id).count()
        assert total_runs == 1


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


class TestStopRun:
    def test_stop_run_returns_false_when_not_found(self):
        assert stop_run("nonexistent-id") is False

    def test_stop_run_terminates_process(self):
        mock_process = MagicMock()
        run_id = "test-run-id"
        _active_processes[run_id] = mock_process
        try:
            result = stop_run(run_id)
            assert result is True
            mock_process.terminate.assert_called_once()
            assert run_id in _stopped_runs
        finally:
            _active_processes.pop(run_id, None)
            _stopped_runs.discard(run_id)

    async def test_stopped_run_does_not_fail_task(self, sample_task):
        """When a run is stopped by user, task status should NOT change to FAILED."""
        import json

        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = -15  # SIGTERM

        original_status = sample_task.status

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # Pre-register the run as stopped — we need to know the run ID
            # so we patch _stopped_runs after run creation
            with patch("app.agent.runner._stopped_runs", new=set()) as stopped:
                with patch("app.agent.runner._active_processes", new={}) as active:
                    # We need to intercept the run_id after creation
                    original_create = AgentRun.create

                    async def patched_create(**kwargs):
                        run = await original_create(**kwargs)
                        stopped.add(str(run.id))
                        return run

                    with patch.object(AgentRun, "create", side_effect=patched_create):
                        run = await run_agent(sample_task, RunStage.PLAN)

        assert run.status == RunStatus.FAILED
        # Task should NOT be set to FAILED
        task = await Task.get(id=sample_task.id)
        assert task.status == original_status

        # Verify the "Stopped by user" log was saved
        logs = await AgentLog.filter(run_id=run.id, type=LogType.ERROR).all()
        assert any("Stopped by user" in log.content.get("message", "") for log in logs)


class TestRepoValidationGate:
    async def test_rejects_disabled_repo(self, sample_task):
        """Agent should fail if task targets a repo that isn't enabled."""
        sample_task.repo = "org/disabled-repo"
        await sample_task.save()

        # Create an enabled repo (different from task's repo)
        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/enabled-repo",
            name="enabled-repo",
            enabled=True,
        )

        run = await run_agent(sample_task, RunStage.PLAN)
        assert run.status == RunStatus.FAILED

        task = await Task.get(id=sample_task.id)
        assert task.status == TaskStatus.FAILED

        logs = await AgentLog.filter(run_id=run.id, type=LogType.ERROR).all()
        assert any("not enabled" in log.content.get("message", "") for log in logs)

    async def test_allows_enabled_repo(self, sample_task):
        """Agent should proceed if task targets an enabled repo."""
        sample_task.repo = "org/good-repo"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/good-repo",
            name="good-repo",
            enabled=True,
        )

        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("app.agent.runner.create_workspace") as mock_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md"), \
             patch("app.agent.runner.capture_file_tree", return_value=[]), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from pathlib import Path

            mock_ws.return_value = Path("/tmp/fake-ws")
            run = await run_agent(sample_task, RunStage.PLAN)
            assert run.status == RunStatus.DONE

    async def test_allows_when_no_repos_configured(self, sample_task):
        """Agent should allow all repos when no repos are enabled (feature unconfigured)."""
        sample_task.repo = "org/any-repo"
        await sample_task.save()

        # No repositories in DB at all
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("app.agent.runner.create_workspace") as mock_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md"), \
             patch("app.agent.runner.capture_file_tree", return_value=[]), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from pathlib import Path

            mock_ws.return_value = Path("/tmp/fake-ws")
            run = await run_agent(sample_task, RunStage.PLAN)
            assert run.status == RunStatus.DONE

    async def test_allows_when_task_has_no_repo(self, sample_task):
        """Agent should proceed if task has no repo set, even if repos are configured."""
        assert sample_task.repo is None

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/some-repo",
            name="some-repo",
            enabled=True,
        )

        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            run = await run_agent(sample_task, RunStage.PLAN)
            assert run.status == RunStatus.DONE


class TestRunAgentWorkspace:
    async def test_run_agent_creates_workspace_for_repo_task(self, sample_task):
        """When task has a repo, run_agent should create workspace, clone, and set cwd."""
        import json

        sample_task.repo = "org/my-app"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/my-app",
            name="my-app",
            enabled=True,
            default_branch="develop",
        )

        result_event = json.dumps({
            "type": "result",
            "num_input_tokens": 100,
            "num_output_tokens": 50,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo") as mock_clone, \
             patch("app.agent.runner.write_claude_md") as mock_write_claude, \
             patch("app.agent.runner.capture_file_tree", return_value=[{"path": "README.md", "type": "file", "size": 10}]), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            run = await run_agent(sample_task, RunStage.PLAN)

            mock_create_ws.assert_called_once()
            mock_clone.assert_called_once()
            # Verify branch passed from Repository record
            clone_call_kwargs = mock_clone.call_args
            assert clone_call_kwargs[0][2] == "develop"

            # Verify cwd was set to workspace
            exec_call = mock_exec.call_args
            assert exec_call.kwargs["cwd"] == "/tmp/fake-workspace"

            assert run.status == RunStatus.DONE

    async def test_run_agent_workspace_clone_failure_marks_failed(self, sample_task):
        """When clone fails, run should be marked FAILED immediately."""
        sample_task.repo = "org/broken-repo"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/broken-repo",
            name="broken-repo",
            enabled=True,
        )

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo", side_effect=RuntimeError("clone failed")):
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            run = await run_agent(sample_task, RunStage.PLAN)

            assert run.status == RunStatus.FAILED

        task = await Task.get(id=sample_task.id)
        assert task.status == TaskStatus.FAILED

        logs = await AgentLog.filter(run_id=run.id, type=LogType.ERROR).all()
        assert any("Workspace setup failed" in log.content.get("message", "") for log in logs)

    async def test_run_agent_no_workspace_when_no_repo(self, sample_task):
        """When task has no repo, workspace should not be created."""
        assert sample_task.repo is None

        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            await run_agent(sample_task, RunStage.PLAN)
            mock_create_ws.assert_not_called()

    async def test_run_agent_writes_claude_md_with_base_prompt(self, sample_task):
        """When base_prompt exists, CLAUDE.md should be written to workspace."""
        import json

        sample_task.repo = "org/my-app"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/my-app",
            name="my-app",
            enabled=True,
        )

        await Setting.create(
            id=uuid.uuid4(),
            key="base_prompt",
            value="Always write tests first.",
        )

        result_event = json.dumps({
            "type": "result",
            "num_input_tokens": 100,
            "num_output_tokens": 50,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md") as mock_write, \
             patch("app.agent.runner.capture_file_tree", return_value=[]), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            await run_agent(sample_task, RunStage.PLAN)

            mock_write.assert_called_once_with(
                Path("/tmp/fake-workspace"),
                "Always write tests first.",
            )

    async def test_run_agent_captures_file_tree_after_run(self, sample_task):
        """File tree should be captured and stored after run completes."""
        import json

        sample_task.repo = "org/my-app"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/my-app",
            name="my-app",
            enabled=True,
        )

        result_event = json.dumps({
            "type": "result",
            "num_input_tokens": 100,
            "num_output_tokens": 50,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        fake_tree = [
            {"path": "README.md", "type": "file", "size": 100},
            {"path": "src", "type": "dir"},
        ]

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md"), \
             patch("app.agent.runner.capture_file_tree", return_value=fake_tree), \
             patch("os.path.isdir", return_value=True), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            run = await run_agent(sample_task, RunStage.PLAN)

        # Refresh from DB
        updated_run = await AgentRun.get(id=run.id)
        assert updated_run.file_tree is not None
        assert len(updated_run.file_tree) == 2


    async def test_run_agent_workspace_step_logs(self, sample_task):
        """Workspace setup should produce visible log entries for each step."""
        import json

        sample_task.repo = "org/my-app"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/my-app",
            name="my-app",
            enabled=True,
            default_branch="main",
        )

        await Setting.create(
            id=uuid.uuid4(),
            key="base_prompt",
            value="Test instructions.",
        )

        result_event = json.dumps({
            "type": "result",
            "num_input_tokens": 100,
            "num_output_tokens": 50,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        fake_tree = [{"path": "README.md", "type": "file", "size": 10}]

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md"), \
             patch("app.agent.runner.capture_file_tree", return_value=fake_tree), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            run = await run_agent(sample_task, RunStage.PLAN)

        assert run.status == RunStatus.DONE
        logs = await AgentLog.filter(run_id=run.id).order_by("created_at").all()
        messages = [log.content.get("message", "") for log in logs]

        # Verify each workspace step produced a log
        assert any("Creating workspace" in m for m in messages)
        assert any("Cloning org/my-app" in m for m in messages)
        assert any("Cloned org/my-app successfully" in m for m in messages)
        assert any("CLAUDE.md" in m for m in messages)
        assert any("Workspace ready" in m for m in messages)
        assert any("Launching Claude Code" in m for m in messages)

    async def test_run_agent_workspace_initial_file_tree_captured(self, sample_task):
        """File tree should be captured right after clone, before Claude runs."""
        import json

        sample_task.repo = "org/my-app"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/my-app",
            name="my-app",
            enabled=True,
        )

        fake_tree = [
            {"path": "src", "type": "dir"},
            {"path": "src/main.py", "type": "file", "size": 50},
        ]

        file_tree_at_cli_launch = None

        async def capture_tree_at_launch(*args, **kwargs):
            nonlocal file_tree_at_cli_launch
            run_record = await AgentRun.filter(task_id=sample_task.id).first()
            file_tree_at_cli_launch = run_record.file_tree
            return mock_process

        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md"), \
             patch("app.agent.runner.capture_file_tree", return_value=fake_tree), \
             patch("asyncio.create_subprocess_exec", side_effect=capture_tree_at_launch):
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            await run_agent(sample_task, RunStage.PLAN)

        # File tree should have been set BEFORE Claude CLI launched
        assert file_tree_at_cli_launch is not None
        assert len(file_tree_at_cli_launch) == 2

    async def test_run_agent_workspace_broadcast_logs(self, sample_task):
        """Workspace step logs should be broadcast via WebSocket."""
        import json

        sample_task.repo = "org/my-app"
        await sample_task.save()

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/my-app",
            name="my-app",
            enabled=True,
        )

        result_event = json.dumps({
            "type": "result",
            "num_input_tokens": 100,
            "num_output_tokens": 50,
        })
        mock_process = AsyncMock()
        mock_process.stdout = AsyncIteratorMock([result_event.encode() + b"\n"])
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.returncode = 0

        mock_broadcast = AsyncMock()

        with patch("app.agent.runner.create_workspace") as mock_create_ws, \
             patch("app.agent.runner.clone_repo"), \
             patch("app.agent.runner.write_claude_md"), \
             patch("app.agent.runner.capture_file_tree", return_value=[]), \
             patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from pathlib import Path

            mock_create_ws.return_value = Path("/tmp/fake-workspace")

            await run_agent(
                sample_task, RunStage.PLAN, ws_broadcast=mock_broadcast,
            )

        # Workspace setup should have broadcast multiple logs
        broadcast_messages = [
            call.args[1].content.get("message", "")
            for call in mock_broadcast.call_args_list
        ]
        assert any("Creating workspace" in m for m in broadcast_messages)
        assert any("Cloning" in m for m in broadcast_messages)
        assert any("Launching Claude Code" in m for m in broadcast_messages)


class TestGetEnabledRepos:
    async def test_returns_empty_set_when_none(self):
        result = await _get_enabled_repos()
        assert result == set()

    async def test_returns_enabled_repos(self):
        await Repository.create(
            id=uuid.uuid4(), full_name="org/enabled", name="enabled", enabled=True
        )
        await Repository.create(
            id=uuid.uuid4(), full_name="org/disabled", name="disabled", enabled=False
        )
        result = await _get_enabled_repos()
        assert result == {"org/enabled"}
