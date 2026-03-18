from __future__ import annotations

import logging

from app.models import AgentRun, TaskStatus

logger = logging.getLogger(__name__)


async def handle_stage_completion(run: AgentRun) -> None:
    """Handle post-completion logic after an agent run finishes."""
    await run.fetch_related("task")
    task = run.task

    if run.status.value != "done":
        return

    if run.stage.value == "plan" and task.status != TaskStatus.DONE:
        task.status = TaskStatus.PLANNED
        await task.save()
        logger.info("Task %s moved to planned after plan stage", task.id)

    elif run.stage.value == "work" and task.status != TaskStatus.DONE:
        task.status = TaskStatus.REVIEWING
        await task.save()
        logger.info("Task %s moved to reviewing after work stage", task.id)

    elif run.stage.value == "review":
        task.status = TaskStatus.DONE
        await task.save()
        logger.info("Task %s moved to done after review stage", task.id)
