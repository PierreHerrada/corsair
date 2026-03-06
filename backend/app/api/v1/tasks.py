from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from tortoise.expressions import Q

from app.agent.runner import run_agent, stop_run
from app.models import AgentLog, AgentRun, RunStage, RunStatus, Task, TaskStatus
from app.models.setting import Setting
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    repo: Optional[str] = None
    auto_work: Optional[bool] = None


async def _task_to_dict(task: Task) -> dict:
    latest_run = await AgentRun.filter(task_id=task.id).order_by("-started_at").first()
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "acceptance": task.acceptance,
        "status": task.status.value,
        "jira_key": task.jira_key,
        "jira_url": task.jira_url,
        "slack_thread_ts": task.slack_thread_ts,
        "pr_url": task.pr_url,
        "pr_number": task.pr_number,
        "repo": task.repo,
        "plan": task.plan,
        "analysis": task.analysis,
        "auto_work": task.auto_work,
        "created_at": task.created_at.isoformat(),
        "latest_run": _run_to_dict(latest_run) if latest_run else None,
    }


def _run_to_dict(run: AgentRun) -> dict:
    return {
        "id": str(run.id),
        "task_id": str(run.task_id),
        "stage": run.stage.value,
        "status": run.status.value,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "cost_usd": float(run.cost_usd),
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "workspace_path": run.workspace_path,
        "file_tree": run.file_tree,
    }


@router.get("")
async def list_tasks() -> list[dict]:
    today_start = datetime(
        *datetime.now(timezone.utc).timetuple()[:3], tzinfo=timezone.utc
    )
    tasks = await (
        Task.active()
        .exclude(Q(status=TaskStatus.DONE) & Q(updated_at__lt=today_start))
        .order_by("-created_at")
    )
    return [await _task_to_dict(t) for t in tasks]


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict:
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _task_to_dict(task)


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate) -> dict:
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    old_status = task.status
    updates = {}
    if body.status is not None:
        updates["status"] = body.status
    if body.repo is not None:
        updates["repo"] = body.repo if body.repo != "" else None
    if "auto_work" in body.model_fields_set:
        updates["auto_work"] = body.auto_work
    if updates:
        await Task.filter(id=task_id).update(**updates)
    task = await Task.get(id=task_id)

    # Sync status change to Jira if the task has a linked ticket
    if body.status is not None and body.status != old_status and task.jira_key:
        try:
            from app.integrations.jira.sync import sync_status_to_jira

            await sync_status_to_jira(task, body.status)
        except Exception:
            logger.exception(
                "Failed to sync status to Jira for task %s (%s)",
                task_id, task.jira_key,
            )

    return await _task_to_dict(task)


async def _trigger_stage(task_id: str, stage: RunStage, background_tasks: BackgroundTasks) -> dict:
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check for active runs
    active_run = await AgentRun.filter(task_id=task_id, status=RunStatus.RUNNING).first()
    if active_run:
        raise HTTPException(status_code=409, detail="A run is already active for this task")

    # Enforce global max active agents limit
    setting = await Setting.filter(key="max_active_agents").first()
    try:
        max_active = int(setting.value) if setting and setting.value else 0
    except (ValueError, TypeError):
        max_active = 0
    if max_active > 0:
        running_count = await AgentRun.filter(status=RunStatus.RUNNING).count()
        if running_count >= max_active:
            raise HTTPException(
                status_code=429,
                detail=f"Max active agents limit reached ({max_active})",
            )

    run = await AgentRun.create(
        task=task,
        stage=stage,
        status=RunStatus.RUNNING,
    )

    # Start agent in background
    background_tasks.add_task(_run_agent_background, task, stage, run)

    return _run_to_dict(run)


async def _run_agent_background(task: Task, stage: RunStage, existing_run: AgentRun) -> None:
    """Background task to run the agent, reusing the already-created run."""
    await run_agent(task, stage, ws_broadcast=ws_manager.broadcast, existing_run=existing_run)


@router.post("/{task_id}/retry", status_code=200)
async def retry_task(task_id: str) -> dict:
    """Retry a failed task by resetting its status based on its Jira issue status."""
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=409, detail="Task is not in failed status")

    new_status = TaskStatus.BACKLOG  # default fallback

    if task.jira_key:
        try:
            from app.integrations.jira.client import JiraIntegration
            from app.integrations.jira.sync import _map_jira_status
            from app.integrations.registry import IntegrationRegistry

            jira = IntegrationRegistry.get("jira")
            if jira is not None and isinstance(jira, JiraIntegration):
                issue = await jira.get_issue(task.jira_key)
                jira_status_name = issue.get("fields", {}).get("status", {}).get("name", "")
                new_status = await _map_jira_status(jira_status_name)
                logger.info(
                    "Retry task %s: Jira %s status '%s' → %s",
                    task.id, task.jira_key, jira_status_name, new_status.value,
                )
        except Exception:
            logger.exception(
                "Retry task %s: failed to fetch Jira status, defaulting to backlog",
                task.id,
            )

    task.status = new_status
    await task.save()
    return await _task_to_dict(task)


@router.post("/{task_id}/stop", status_code=200)
async def stop_task(task_id: str) -> dict:
    """Stop a running agent for a task."""
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    active_run = await AgentRun.filter(task_id=task_id, status=RunStatus.RUNNING).first()
    if not active_run:
        raise HTTPException(status_code=409, detail="No active run for this task")

    stopped = stop_run(str(active_run.id))
    if not stopped:
        # Process not in memory (e.g. container restarted) — mark orphaned run as failed
        await AgentRun.filter(id=active_run.id).update(
            status=RunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
        )
        await Task.filter(id=task_id).update(status=TaskStatus.FAILED)
        active_run = await AgentRun.get(id=active_run.id)

    return _run_to_dict(active_run)


@router.get("/{task_id}/runs")
async def list_task_runs(task_id: str) -> list[dict]:
    """Get all runs for a task, with their logs."""
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    runs = await AgentRun.filter(task_id=task_id).order_by("-started_at")
    result = []
    for run in runs:
        logs = await AgentLog.filter(run_id=run.id).order_by("created_at")
        run_dict = _run_to_dict(run)
        run_dict["logs"] = [
            {
                "id": str(log.id),
                "run_id": str(log.run_id),
                "type": log.type.value,
                "content": log.content,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
        result.append(run_dict)
    return result


@router.get("/{task_id}/runs/{run_id}/files")
async def get_run_files(task_id: str, run_id: str) -> list[dict]:
    """Get the file tree for a specific run."""
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    run = await AgentRun.filter(id=run_id, task_id=task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.file_tree or []


@router.post("/{task_id}/plan", status_code=201)
async def trigger_plan(task_id: str, background_tasks: BackgroundTasks) -> dict:
    return await _trigger_stage(task_id, RunStage.PLAN, background_tasks)


@router.post("/{task_id}/work", status_code=201)
async def trigger_work(task_id: str, background_tasks: BackgroundTasks) -> dict:
    return await _trigger_stage(task_id, RunStage.WORK, background_tasks)


@router.post("/{task_id}/review", status_code=201)
async def trigger_review(task_id: str, background_tasks: BackgroundTasks) -> dict:
    return await _trigger_stage(task_id, RunStage.REVIEW, background_tasks)


@router.post("/{task_id}/analyze", status_code=200)
async def trigger_analysis(task_id: str, background_tasks: BackgroundTasks) -> dict:
    """Manually trigger analysis for a task."""
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    background_tasks.add_task(_run_analysis, task)
    return {"status": "analyzing"}


async def _run_analysis(task: Task) -> None:
    from app.agent.analysis import analyze_task

    try:
        await analyze_task(task)
    except Exception:
        logger.exception("Background analysis failed for task %s", task.id)
