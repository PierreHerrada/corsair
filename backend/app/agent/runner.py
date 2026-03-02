from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.agent.cost import INPUT_PRICE_PER_M, OUTPUT_PRICE_PER_M
from app.agent.prompts import build_plan_prompt, build_review_prompt, build_work_prompt
from app.config import settings
from app.models import AgentLog, AgentRun, LogType, RunStage, RunStatus, Task, TaskStatus

logger = logging.getLogger(__name__)


async def save_log(
    run_id: uuid.UUID, content: dict, log_type: LogType = LogType.TEXT
) -> AgentLog:
    return await AgentLog.create(
        id=uuid.uuid4(),
        run_id=run_id,
        type=log_type,
        content=content,
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


async def _get_base_prompt() -> str:
    """Fetch the base prompt from settings, returning empty string if not set."""
    from app.models.setting import Setting

    setting = await Setting.filter(key="base_prompt").first()
    if setting and setting.value.strip():
        return setting.value.strip()
    return ""


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


def _classify_event(event: dict) -> tuple[LogType, dict]:
    """Classify a stream-json event into a log type and content dict."""
    event_type = event.get("type", "")

    if event_type == "assistant" and "message" in event:
        # Assistant text message
        msg = event["message"]
        content_blocks = msg.get("content", [])
        texts = []
        for block in content_blocks:
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
        if texts:
            return LogType.TEXT, {"message": "\n".join(texts)}
        return LogType.TEXT, {"message": json.dumps(event)}

    if event_type == "tool_use":
        return LogType.TOOL_USE, {
            "tool": event.get("tool", event.get("name", "unknown")),
            "input": event.get("input", {}),
            "message": f"Tool: {event.get('tool', event.get('name', 'unknown'))}",
        }

    if event_type == "tool_result":
        return LogType.TOOL_RESULT, {
            "tool": event.get("tool", event.get("name", "unknown")),
            "output": event.get("output", ""),
            "message": f"Result: {event.get('tool', event.get('name', 'unknown'))}",
        }

    if event_type == "error":
        return LogType.ERROR, {
            "message": event.get("error", {}).get("message", json.dumps(event)),
        }

    if event_type == "result":
        # Final result event with cost info
        return LogType.TEXT, {
            "message": "Run completed",
            "is_result": True,
            "cost": event.get("cost_usd"),
            "duration": event.get("duration_ms"),
            "tokens_in": event.get("num_input_tokens", event.get("usage", {}).get("input_tokens", 0)),
            "tokens_out": event.get("num_output_tokens", event.get("usage", {}).get("output_tokens", 0)),
        }

    # Fallback: store as text
    return LogType.TEXT, {"message": json.dumps(event)}


async def _notify_run_complete(task: Task, stage: RunStage, success: bool) -> None:
    """Send Jira comment and Slack thread message when an agent run finishes."""
    status_text = "completed successfully" if success else "failed"
    stage_label = stage.value.capitalize()
    message = f"{stage_label} stage {status_text}."

    from app.integrations.registry import IntegrationRegistry

    # Jira comment
    try:
        jira = IntegrationRegistry.get("jira")
        if jira is not None and task.jira_key:
            await jira.add_comment(task.jira_key, message)
    except Exception:
        logger.exception("Failed to post Jira comment for task %s", task.id)

    # Slack thread reply
    try:
        slack = IntegrationRegistry.get("slack")
        if slack is not None and task.slack_channel and task.slack_thread_ts:
            await slack.post_thread_update(task.slack_channel, task.slack_thread_ts, message)
    except Exception:
        logger.exception("Failed to post Slack update for task %s", task.id)


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
    base_prompt = await _get_base_prompt()
    if base_prompt:
        prompt = base_prompt + "\n\n" + prompt
    cwd = repo_path or os.getcwd()

    tokens_in = 0
    tokens_out = 0

    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--max-turns", "200",
            "-p", prompt,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key},
        )

        # Stream stdout line by line — each line is a JSON event
        async for line in process.stdout:
            decoded = line.decode().rstrip()
            if not decoded:
                continue
            try:
                event = json.loads(decoded)
            except json.JSONDecodeError:
                # Non-JSON output — store as plain text
                log = await save_log(run.id, {"message": decoded})
                if ws_broadcast:
                    await ws_broadcast(str(run.id), log)
                continue

            log_type, content = _classify_event(event)

            # Extract token usage from result events
            if content.get("is_result"):
                tokens_in = content.get("tokens_in", 0)
                tokens_out = content.get("tokens_out", 0)

            log = await save_log(run.id, content, log_type)
            if ws_broadcast:
                await ws_broadcast(str(run.id), log)

        await process.wait()

        # Compute cost
        cost = (Decimal(tokens_in) / 1_000_000 * INPUT_PRICE_PER_M) + (
            Decimal(tokens_out) / 1_000_000 * OUTPUT_PRICE_PER_M
        )

        if process.returncode == 0:
            await update_run_cost(run.id, tokens_in, tokens_out, float(cost))
            new_status = _STAGE_TO_TASK_STATUS.get(stage)
            if new_status:
                await Task.filter(id=task.id).update(status=new_status)
            await _notify_run_complete(task, stage, success=True)
        else:
            await AgentRun.filter(id=run.id).update(
                status=RunStatus.FAILED,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=float(cost),
                finished_at=datetime.now(timezone.utc),
            )
            await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
            stderr_output = (await process.stderr.read()).decode()
            await save_log(
                run.id,
                {"message": f"Process exited with code {process.returncode}\n{stderr_output}"},
                LogType.ERROR,
            )
            await _notify_run_complete(task, stage, success=False)

    except Exception as e:
        logger.exception("Agent run failed for task %s stage %s", task.id, stage)
        await AgentRun.filter(id=run.id).update(
            status=RunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
        )
        await Task.filter(id=task.id).update(status=TaskStatus.FAILED)
        await save_log(run.id, {"message": str(e)}, LogType.ERROR)
        await _notify_run_complete(task, stage, success=False)

    return await AgentRun.get(id=run.id)
