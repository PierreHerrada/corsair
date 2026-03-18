from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import boto3

from app.config import settings
from app.models import AgentLog, AgentRun

if TYPE_CHECKING:
    from app.models import Task
    from app.models.agent_type import AgentType

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self) -> None:
        self.cluster = settings.ecs_cluster_arn
        self.callback_url = settings.internal_callback_url
        self.secret = settings.internal_api_secret
        self.ecs = boto3.client("ecs", region_name=settings.aws_region)

    async def launch(self, task: Task, run: AgentRun, stage: str, agent_type: AgentType) -> str:
        env_overrides = [
            {"name": "TASK_ID", "value": str(task.id)},
            {"name": "AGENT_RUN_ID", "value": str(run.id)},
            {"name": "STAGE", "value": stage},
            {"name": "REPO_URL", "value": task.repo or ""},
            {"name": "BRANCH", "value": "main"},
            {"name": "CALLBACK_URL", "value": self.callback_url},
            {"name": "INTERNAL_API_SECRET", "value": self.secret},
            {"name": "MAX_DURATION_SECONDS", "value": str(agent_type.max_duration_seconds)},
            {"name": "TASK_DESCRIPTION", "value": task.title or task.description or ""},
        ]

        # Pass plan output for work/review stages
        if stage in ("work", "review"):
            plan_output = await self.get_plan_output(str(task.id))
            if plan_output:
                env_overrides.append({"name": "PLAN_OUTPUT", "value": plan_output})

        if agent_type.enable_dind:
            env_overrides.append({"name": "DOCKER_HOST", "value": "tcp://localhost:2375"})

        overrides: dict = {
            "containerOverrides": [
                {"name": "agent", "environment": env_overrides}
            ],
        }
        if agent_type.task_role_arn:
            overrides["taskRoleArn"] = agent_type.task_role_arn

        response = self.ecs.run_task(
            cluster=self.cluster,
            taskDefinition=agent_type.ecs_task_definition,
            capacityProviderStrategy=[
                {"capacityProvider": "FARGATE_SPOT", "weight": 3},
                {"capacityProvider": "FARGATE", "weight": 1, "base": 1},
            ],
            overrides=overrides,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": agent_type.subnet_ids or [],
                    "securityGroups": agent_type.security_group_ids or [],
                    "assignPublicIp": "DISABLED",
                }
            },
            tags=[
                {"key": "corsair:task-id", "value": str(task.id)},
                {"key": "corsair:run-id", "value": str(run.id)},
                {"key": "corsair:agent-type", "value": agent_type.name},
            ],
        )

        tasks = response.get("tasks", [])
        if not tasks:
            failures = response.get("failures", [])
            raise RuntimeError(f"ECS RunTask returned no tasks. Failures: {failures}")

        task_arn = tasks[0]["taskArn"]
        logger.info("Launched ECS task %s for run %s", task_arn, run.id)
        return task_arn

    async def status(self, task_arn: str) -> dict:
        try:
            response = self.ecs.describe_tasks(
                cluster=self.cluster,
                tasks=[task_arn],
            )
            tasks = response.get("tasks", [])
            if not tasks:
                return {"lastStatus": "UNKNOWN"}
            return tasks[0]
        except Exception:
            logger.exception("Failed to describe ECS task %s", task_arn)
            return {"lastStatus": "UNKNOWN"}

    async def stop(self, task_arn: str, reason: str = "Cancelled by user") -> None:
        try:
            self.ecs.stop_task(
                cluster=self.cluster,
                task=task_arn,
                reason=reason,
            )
            logger.info("Stopped ECS task %s: %s", task_arn, reason)
        except Exception:
            logger.exception("Failed to stop ECS task %s", task_arn)

    async def get_plan_output(self, task_id: str) -> str:
        plan_run = (
            await AgentRun.filter(task_id=task_id, stage="plan", status="done")
            .order_by("-started_at")
            .first()
        )
        if not plan_run:
            return ""
        logs = await AgentLog.filter(run_id=plan_run.id, type="text").order_by("created_at")
        return "\n".join(
            log.content.get("text", "") if isinstance(log.content, dict) else str(log.content)
            for log in logs
        )
