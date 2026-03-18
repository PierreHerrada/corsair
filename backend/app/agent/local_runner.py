from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import docker

from app.config import settings
from app.models import AgentLog, AgentRun

if TYPE_CHECKING:
    from app.models import Task
    from app.models.agent_type import AgentType

logger = logging.getLogger(__name__)


class LocalAgentRunner:
    def __init__(self) -> None:
        self.docker = docker.from_env()
        self.image = settings.local_agent_image
        self.callback_url = "http://host.docker.internal:8000"
        self.secret = settings.internal_api_secret

    async def launch(self, task: Task, run: AgentRun, stage: str, agent_type: AgentType) -> str:
        env = {
            "TASK_ID": str(task.id),
            "AGENT_RUN_ID": str(run.id),
            "STAGE": stage,
            "REPO_URL": task.repo or "",
            "BRANCH": "main",
            "CALLBACK_URL": self.callback_url,
            "INTERNAL_API_SECRET": self.secret,
            "ANTHROPIC_API_KEY": settings.anthropic_api_key,
            "MAX_DURATION_SECONDS": str(agent_type.max_duration_seconds),
            "TASK_DESCRIPTION": task.title or task.description or "",
            "GITHUB_TOKEN": settings.github_token,
        }

        # Pass plan output for work/review stages
        if stage in ("work", "review"):
            plan_output = await self._get_plan_output(str(task.id))
            if plan_output:
                env["PLAN_OUTPUT"] = plan_output

        if agent_type.enable_dind:
            env["DOCKER_HOST"] = "tcp://localhost:2375"

        container = self.docker.containers.run(
            self.image,
            detach=True,
            environment=env,
            remove=True,
            name=f"corsair-agent-{run.id}",
        )

        task_arn = f"local:{container.id}"
        logger.info("Launched local container %s for run %s", container.id, run.id)
        return task_arn

    async def status(self, task_arn: str) -> dict:
        container_id = task_arn.replace("local:", "")
        try:
            container = self.docker.containers.get(container_id)
            docker_status = container.status
            # Map Docker status to ECS-like status
            if docker_status == "running":
                return {"lastStatus": "RUNNING"}
            elif docker_status == "exited":
                return {"lastStatus": "STOPPED", "stoppedReason": "Container exited"}
            return {"lastStatus": "UNKNOWN"}
        except docker.errors.NotFound:
            return {"lastStatus": "STOPPED", "stoppedReason": "Container not found (removed)"}
        except Exception:
            logger.exception("Failed to check local container %s", container_id)
            return {"lastStatus": "UNKNOWN"}

    async def stop(self, task_arn: str, reason: str = "Cancelled by user") -> None:
        container_id = task_arn.replace("local:", "")
        try:
            container = self.docker.containers.get(container_id)
            container.stop(timeout=10)
            logger.info("Stopped local container %s: %s", container_id, reason)
        except docker.errors.NotFound:
            logger.warning("Local container %s not found (already stopped)", container_id)
        except Exception:
            logger.exception("Failed to stop local container %s", container_id)

    async def _get_plan_output(self, task_id: str) -> str:
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
