from __future__ import annotations

import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AgentLog, AgentRun, RunStage, RunStatus, Task, TaskStatus
from app.models.agent_type import AgentType

# Ensure boto3 and docker are available as mocks if not installed
_mock_boto3 = MagicMock()
_mock_docker = MagicMock()
if "boto3" not in sys.modules:
    sys.modules["boto3"] = _mock_boto3
if "docker" not in sys.modules:
    sys.modules["docker"] = _mock_docker
    sys.modules["docker.errors"] = _mock_docker.errors


@pytest.fixture
async def agent_type():
    return await AgentType.create(
        id=uuid.uuid4(),
        name="default",
        display_name="Default Agent",
        ecs_task_definition="arn:aws:ecs:us-east-1:123:task-definition/agent:1",
        subnet_ids=["subnet-123"],
        security_group_ids=["sg-123"],
        max_duration_seconds=3600,
        is_default=True,
    )


@pytest.fixture
async def task_obj():
    return await Task.create(
        id=uuid.uuid4(),
        title="Test task",
        description="desc",
        acceptance="ok",
        status=TaskStatus.BACKLOG,
        slack_channel="C1",
        slack_thread_ts="123",
        slack_user_id="U1",
    )


@pytest.fixture
async def run_obj(task_obj):
    return await AgentRun.create(
        id=uuid.uuid4(),
        task=task_obj,
        stage=RunStage.PLAN,
        status=RunStatus.LAUNCHING,
    )


class TestAgentOrchestrator:
    async def test_launch(self, task_obj, run_obj, agent_type):
        mock_ecs = MagicMock()
        mock_ecs.run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/abc123"}]
        }

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            task_arn = await orch.launch(task_obj, run_obj, "plan", agent_type)

        assert task_arn == "arn:aws:ecs:us-east-1:123:task/abc123"
        mock_ecs.run_task.assert_called_once()

    async def test_launch_no_tasks_raises(self, task_obj, run_obj, agent_type):
        mock_ecs = MagicMock()
        mock_ecs.run_task.return_value = {
            "tasks": [],
            "failures": [{"reason": "RESOURCE:CPU"}],
        }

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            with pytest.raises(RuntimeError, match="ECS RunTask returned no tasks"):
                await orch.launch(task_obj, run_obj, "plan", agent_type)

    async def test_launch_work_stage_includes_plan_output(self, task_obj, agent_type):
        plan_run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task_obj,
            stage=RunStage.PLAN,
            status=RunStatus.DONE,
        )
        await AgentLog.create(
            id=uuid.uuid4(),
            run=plan_run,
            type="text",
            content={"text": "Plan output here"},
        )

        work_run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task_obj,
            stage=RunStage.WORK,
            status=RunStatus.LAUNCHING,
        )

        mock_ecs = MagicMock()
        mock_ecs.run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/work123"}]
        }

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            await orch.launch(task_obj, work_run, "work", agent_type)

        call_kwargs = mock_ecs.run_task.call_args
        container_env = call_kwargs[1]["overrides"]["containerOverrides"][0]["environment"]
        plan_env = [e for e in container_env if e["name"] == "PLAN_OUTPUT"]
        assert len(plan_env) == 1
        assert plan_env[0]["value"] == "Plan output here"

    async def test_launch_dind_sets_docker_host(self, task_obj, run_obj):
        dind_type = await AgentType.create(
            id=uuid.uuid4(),
            name="dind",
            display_name="DinD Agent",
            ecs_task_definition="arn:aws:ecs:us-east-1:123:task-definition/dind:1",
            enable_dind=True,
            is_default=False,
        )

        mock_ecs = MagicMock()
        mock_ecs.run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/dind123"}]
        }

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            await orch.launch(task_obj, run_obj, "plan", dind_type)

        call_kwargs = mock_ecs.run_task.call_args
        container_env = call_kwargs[1]["overrides"]["containerOverrides"][0]["environment"]
        docker_host = [e for e in container_env if e["name"] == "DOCKER_HOST"]
        assert len(docker_host) == 1
        assert docker_host[0]["value"] == "tcp://localhost:2375"

    async def test_status(self):
        mock_ecs = MagicMock()
        mock_ecs.describe_tasks.return_value = {
            "tasks": [{"lastStatus": "RUNNING", "taskArn": "arn:task/123"}]
        }

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            result = await orch.status("arn:task/123")

        assert result["lastStatus"] == "RUNNING"

    async def test_status_no_tasks(self):
        mock_ecs = MagicMock()
        mock_ecs.describe_tasks.return_value = {"tasks": []}

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            result = await orch.status("arn:task/missing")

        assert result["lastStatus"] == "UNKNOWN"

    async def test_status_exception(self):
        mock_ecs = MagicMock()
        mock_ecs.describe_tasks.side_effect = Exception("AWS error")

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            result = await orch.status("arn:task/fail")

        assert result["lastStatus"] == "UNKNOWN"

    async def test_stop(self):
        mock_ecs = MagicMock()

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            await orch.stop("arn:task/123", reason="Test stop")

        mock_ecs.stop_task.assert_called_once()

    async def test_stop_exception(self):
        mock_ecs = MagicMock()
        mock_ecs.stop_task.side_effect = Exception("AWS error")

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            await orch.stop("arn:task/fail")

    async def test_get_plan_output_no_plan_run(self):
        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            result = await orch.get_plan_output(str(uuid.uuid4()))

        assert result == ""

    async def test_launch_with_task_role_arn(self, task_obj, run_obj):
        at = await AgentType.create(
            id=uuid.uuid4(),
            name="with-role",
            display_name="With Role",
            ecs_task_definition="arn:aws:ecs:us-east-1:123:task-definition/role:1",
            task_role_arn="arn:aws:iam::123:role/agent-role",
            is_default=False,
        )

        mock_ecs = MagicMock()
        mock_ecs.run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/role123"}]
        }

        with patch("app.agent.orchestrator.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_ecs
            from app.agent.orchestrator import AgentOrchestrator

            orch = AgentOrchestrator()
            await orch.launch(task_obj, run_obj, "plan", at)

        call_kwargs = mock_ecs.run_task.call_args
        assert call_kwargs[1]["overrides"]["taskRoleArn"] == "arn:aws:iam::123:role/agent-role"


class TestLocalAgentRunner:
    async def test_launch(self, task_obj, run_obj, agent_type):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_client.containers.run.return_value = mock_container

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            task_arn = await runner.launch(task_obj, run_obj, "plan", agent_type)

        assert task_arn == "local:abc123"
        mock_client.containers.run.assert_called_once()

    async def test_launch_dind(self, task_obj, run_obj):
        dind_type = await AgentType.create(
            id=uuid.uuid4(),
            name="local-dind",
            display_name="Local DinD",
            ecs_task_definition="unused",
            enable_dind=True,
            is_default=False,
        )

        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "dind123"
        mock_client.containers.run.return_value = mock_container

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            await runner.launch(task_obj, run_obj, "plan", dind_type)

        call_kwargs = mock_client.containers.run.call_args
        assert call_kwargs[1]["environment"]["DOCKER_HOST"] == "tcp://localhost:2375"

    async def test_status_running(self):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            result = await runner.status("local:abc123")

        assert result["lastStatus"] == "RUNNING"

    async def test_status_exited(self):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_client.containers.get.return_value = mock_container

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            result = await runner.status("local:abc123")

        assert result["lastStatus"] == "STOPPED"

    async def test_status_not_found(self):
        mock_client = MagicMock()
        NotFoundError = type("NotFound", (Exception,), {})
        mock_client.containers.get.side_effect = NotFoundError("gone")

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.NotFound = NotFoundError
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            result = await runner.status("local:gone")

        assert result["lastStatus"] == "STOPPED"

    async def test_status_unknown_error(self):
        mock_client = MagicMock()
        NotFoundError = type("NotFound", (Exception,), {})
        mock_client.containers.get.side_effect = RuntimeError("Docker daemon down")

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.NotFound = NotFoundError
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            result = await runner.status("local:err")

        assert result["lastStatus"] == "UNKNOWN"

    async def test_stop(self):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            await runner.stop("local:abc123")

        mock_container.stop.assert_called_once_with(timeout=10)

    async def test_stop_not_found(self):
        mock_client = MagicMock()
        NotFoundError = type("NotFound", (Exception,), {})
        mock_client.containers.get.side_effect = NotFoundError("gone")

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.NotFound = NotFoundError
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            await runner.stop("local:gone")

    async def test_stop_exception(self):
        mock_client = MagicMock()
        NotFoundError = type("NotFound", (Exception,), {})
        mock_client.containers.get.side_effect = RuntimeError("fail")

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.NotFound = NotFoundError
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            await runner.stop("local:err")

    async def test_get_plan_output_no_plan(self):
        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = MagicMock()
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            result = await runner._get_plan_output(str(uuid.uuid4()))

        assert result == ""

    async def test_get_plan_output_with_logs(self, task_obj):
        plan_run = await AgentRun.create(
            id=uuid.uuid4(),
            task=task_obj,
            stage=RunStage.PLAN,
            status=RunStatus.DONE,
        )
        await AgentLog.create(
            id=uuid.uuid4(),
            run=plan_run,
            type="text",
            content={"text": "Step 1"},
        )
        await AgentLog.create(
            id=uuid.uuid4(),
            run=plan_run,
            type="text",
            content={"text": "Step 2"},
        )

        with patch("app.agent.local_runner.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = MagicMock()
            from app.agent.local_runner import LocalAgentRunner

            runner = LocalAgentRunner()
            result = await runner._get_plan_output(str(task_obj.id))

        assert "Step 1" in result
        assert "Step 2" in result
