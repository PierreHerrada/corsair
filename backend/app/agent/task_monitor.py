from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.models import AgentRun, RunStatus

logger = logging.getLogger(__name__)


class AgentTaskMonitor:
    def __init__(self, orchestrator: object, interval: int = 30) -> None:
        self._orchestrator = orchestrator
        self._interval = interval
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Agent task monitor started (interval=%ds)", self._interval)
        while self._running:
            try:
                await self._check_runs()
            except Exception:
                logger.exception("Error in agent task monitor")
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("Agent task monitor stopped")

    async def _check_runs(self) -> None:
        active_runs = await AgentRun.filter(
            status__in=[RunStatus.LAUNCHING, RunStatus.RUNNING],
            ecs_task_arn__not_isnull=True,
        )

        for run in active_runs:
            if not run.ecs_task_arn:
                continue

            ecs_status = await self._orchestrator.status(run.ecs_task_arn)
            last_status = ecs_status.get("lastStatus", "UNKNOWN")

            if last_status == "STOPPED" and run.status in (RunStatus.LAUNCHING, RunStatus.RUNNING):
                # Container stopped but callback never arrived
                stop_reason = ecs_status.get("stoppedReason", "Unknown reason")
                run.status = RunStatus.FAILED
                run.error_message = f"Container stopped: {stop_reason}"
                run.finished_at = datetime.now(timezone.utc)
                await run.save()
                logger.warning(
                    "Run %s marked as failed: container stopped (%s)",
                    run.id, stop_reason,
                )
            elif last_status == "UNKNOWN":
                run.status = RunStatus.FAILED
                run.error_message = "ECS task not found"
                run.finished_at = datetime.now(timezone.utc)
                await run.save()
                logger.warning("Run %s marked as failed: ECS task not found", run.id)

            # Check for timeout
            if run.status in (RunStatus.LAUNCHING, RunStatus.RUNNING) and run.started_at:
                max_duration = 3600  # default
                try:
                    await run.fetch_related("task")
                    if hasattr(run.task, "agent_type_id") and run.task.agent_type_id:
                        await run.task.fetch_related("agent_type")
                        if run.task.agent_type:
                            max_duration = run.task.agent_type.max_duration_seconds
                except Exception:
                    pass

                deadline = run.started_at + timedelta(seconds=max_duration)
                if datetime.now(timezone.utc) > deadline:
                    await self._orchestrator.stop(run.ecs_task_arn, reason="Timed out")
                    run.status = RunStatus.FAILED
                    run.error_message = "Timed out"
                    run.finished_at = datetime.now(timezone.utc)
                    await run.save()
                    logger.warning("Run %s timed out after %ds", run.id, max_duration)
