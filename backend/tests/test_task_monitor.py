from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.agent.task_monitor import AgentTaskMonitor
from app.models import AgentRun, RunStage, RunStatus, Task, TaskStatus
from app.models.agent_type import AgentType


@pytest.fixture
async def agent_type():
    return await AgentType.create(
        id=uuid.uuid4(),
        name="default",
        display_name="Default Agent",
        ecs_task_definition="arn:aws:ecs:us-east-1:123:task-definition/agent:1",
        max_duration_seconds=3600,
        is_default=True,
    )


@pytest.fixture
async def task_obj(agent_type):
    return await Task.create(
        id=uuid.uuid4(),
        title="Test task",
        description="desc",
        acceptance="ok",
        status=TaskStatus.WORKING,
        slack_channel="C1",
        slack_thread_ts="123",
        slack_user_id="U1",
        agent_type=agent_type,
    )


@pytest.fixture
async def active_run(task_obj):
    return await AgentRun.create(
        id=uuid.uuid4(),
        task=task_obj,
        stage=RunStage.WORK,
        status=RunStatus.RUNNING,
        ecs_task_arn="arn:aws:ecs:us-east-1:123:task/abc123",
    )


class TestAgentTaskMonitor:
    async def test_check_runs_stopped_container(self, active_run):
        mock_orch = AsyncMock()
        mock_orch.status.return_value = {
            "lastStatus": "STOPPED",
            "stoppedReason": "OutOfMemoryError",
        }

        monitor = AgentTaskMonitor(mock_orch)
        await monitor._check_runs()

        run = await AgentRun.get(id=active_run.id)
        assert run.status == RunStatus.FAILED
        assert "OutOfMemoryError" in run.error_message
        assert run.finished_at is not None

    async def test_check_runs_unknown_status(self, active_run):
        mock_orch = AsyncMock()
        mock_orch.status.return_value = {"lastStatus": "UNKNOWN"}

        monitor = AgentTaskMonitor(mock_orch)
        await monitor._check_runs()

        run = await AgentRun.get(id=active_run.id)
        assert run.status == RunStatus.FAILED
        assert "not found" in run.error_message

    async def test_check_runs_running_no_change(self, active_run):
        mock_orch = AsyncMock()
        mock_orch.status.return_value = {"lastStatus": "RUNNING"}

        monitor = AgentTaskMonitor(mock_orch)
        await monitor._check_runs()

        run = await AgentRun.get(id=active_run.id)
        assert run.status == RunStatus.RUNNING

    async def test_check_runs_timeout(self, task_obj):
        # Create a run that started 2 hours ago (well past the 3600s default)
        run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task_obj,
            stage=RunStage.WORK,
            status=RunStatus.RUNNING,
            ecs_task_arn="arn:aws:ecs:us-east-1:123:task/timeout",
        )
        # Override started_at to be in the past
        run.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
        await run.save()

        mock_orch = AsyncMock()
        mock_orch.status.return_value = {"lastStatus": "RUNNING"}

        monitor = AgentTaskMonitor(mock_orch)
        await monitor._check_runs()

        run = await AgentRun.get(id=run.id)
        assert run.status == RunStatus.FAILED
        assert run.error_message == "Timed out"
        mock_orch.stop.assert_called_once()

    async def test_check_runs_no_ecs_arn_skipped(self, task_obj):
        # Run without ecs_task_arn should be skipped
        run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task_obj,
            stage=RunStage.WORK,
            status=RunStatus.RUNNING,
        )

        mock_orch = AsyncMock()
        monitor = AgentTaskMonitor(mock_orch)
        await monitor._check_runs()

        mock_orch.status.assert_not_called()
        run = await AgentRun.get(id=run.id)
        assert run.status == RunStatus.RUNNING

    async def test_check_runs_launching_status_also_checked(self, task_obj):
        run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task_obj,
            stage=RunStage.PLAN,
            status=RunStatus.LAUNCHING,
            ecs_task_arn="arn:aws:ecs:us-east-1:123:task/launching",
        )

        mock_orch = AsyncMock()
        mock_orch.status.return_value = {
            "lastStatus": "STOPPED",
            "stoppedReason": "CannotStartContainerError",
        }

        monitor = AgentTaskMonitor(mock_orch)
        await monitor._check_runs()

        run = await AgentRun.get(id=run.id)
        assert run.status == RunStatus.FAILED

    async def test_stop(self):
        mock_orch = AsyncMock()
        monitor = AgentTaskMonitor(mock_orch)
        monitor._running = True
        await monitor.stop()
        assert monitor._running is False
