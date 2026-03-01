from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agent.cost import parse_claude_code_usage
from app.agent.prompts import build_plan_prompt, build_review_prompt, build_work_prompt
from app.config import settings
from app.models import AgentLog, AgentRun, LogType, RunStage, RunStatus, Task, TaskStatus

logger = logging.getLogger(__name__)


async def save_log(run_id: uuid.UUID, content: str, log_type: LogType = LogType.TEXT) -> AgentLog:
    return await AgentLog.create(
        id=uuid.uuid4(),
        run_id=run_id,
        type=log_type,
        content={"message": content},
    )


async def update_run_cost(
    run_id: uuid.UUID, tokens_in: int, tokens_out: int, cost_usd: float
) -> None:
    await AgentRun.filter(id=run_id).update(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        status=RunStatus.DONE,
        finished_at=datetime.now(timezone.utc),
    )


def _build_prompt(task: Task, stage: RunStage) -> str:
    if stage == RunStage.PLAN:
        return build_plan_prompt(task.title, task.description, task.acceptance)
    elif stage == RunStage.WORK:
        return build_work_prompt()
    elif stage == RunStage.REVIEW:
        return build_review_prompt(
            task.jira_key or "UNKNOWN",
            task.title,
            task.jira_url or "",
        )
    raise ValueError(f"Unknown stage: {stage}")


_STAGE_TO_TASK_STATUS = {
    RunStage.PLAN: TaskStatus.PLANNED,
    RunStage.WORK: TaskStatus.WORKING,
    RunStage.REVIEW: TaskStatus.REVIEWING,
}


async def run_agent(
    task: Task,
    stage: RunStage,
    ws_broadcast: Optional[object] = None,
    repo_path: Optional[str] = None,
) -> AgentRun:
    """Execute Claude Code CLI for a given task and stage."""
    run = await AgentRun.create(
        id=uuid.uuid4(),
        task=task,
        stage=stage,
        status=RunStatus.RUNNING,
    )

    prompt = _build_prompt(task, stage)
    cwd = repo_path or os.getcwd()

    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            prompt,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key},
        )

        # Stream stdout line by line
        async for line in process.stdout:
            decoded = line.decode().rstrip()
            if decoded:
                log = await save_log(run.id, decoded)
                if ws_broadcast:
                    await ws_broadcast(str(run.id), log)

        await process.wait()

        # Parse cost from stderr
        stderr_output = (await process.stderr.read()).decode()
        usage = parse_claude_code_usage(stderr_output)

        if process.returncode == 0:
            await update_run_cost(run.id, usage.tokens_in, usage.tokens_out, float(usage.cost_usd))
            # Update task status
            new_status = _STAGE_TO_TASK_STATUS.get(stage)
            if new_status:
                await Task.filter(id=task.id).update(status=new_status)
        else:
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                cost_usd=float(usage.cost_usd),
                finished_at=datetime.now(timezone.utc),
            )
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            await save_log(run.id, f"Process exited with code {process.returncode}", LogType.ERROR)

    except Exception as e:
        logger.exception("Agent run failed for task %s stage %s", task.id, stage)
        await AgentRun.filter(id=run.id).update(
            status=RunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
        )
        await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
        await save_log(run.id, str(e), LogType.ERROR)

    return await AgentRun.get(id=run.id)
