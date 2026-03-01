from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.agent.runner import run_agent
from app.models import AgentRun, RunStage, RunStatus, Task, TaskStatus
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


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
    }


@router.get("")
async def list_tasks() -> list[dict]:
    tasks = await Task.all().order_by("-created_at")
    return [await _task_to_dict(t) for t in tasks]


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict:
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _task_to_dict(task)


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskStatusUpdate) -> dict:
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await Task.filter(id=task_id).update(status=body.status)
    task = await Task.get(id=task_id)
    return await _task_to_dict(task)


async def _trigger_stage(task_id: str, stage: RunStage, background_tasks: BackgroundTasks) -> dict:
    task = await Task.filter(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check for active runs
    active_run = await AgentRun.filter(task_id=task_id, status=RunStatus.RUNNING).first()
    if active_run:
        raise HTTPException(status_code=409, detail="A run is already active for this task")

    run = await AgentRun.create(
        task=task,
        stage=stage,
        status=RunStatus.RUNNING,
    )

    # Start agent in background
    background_tasks.add_task(_run_agent_background, task, stage, run)

    return _run_to_dict(run)


async def _run_agent_background(task: Task, stage: RunStage, placeholder_run: AgentRun) -> None:
    """Background task to run the agent. Replaces the placeholder run."""
    # Delete the placeholder run since run_agent creates its own
    await AgentRun.filter(id=placeholder_run.id).delete()
    await run_agent(task, stage, ws_broadcast=ws_manager.broadcast)


@router.post("/{task_id}/plan", status_code=201)
async def trigger_plan(task_id: str, background_tasks: BackgroundTasks) -> dict:
    return await _trigger_stage(task_id, RunStage.PLAN, background_tasks)


@router.post("/{task_id}/work", status_code=201)
async def trigger_work(task_id: str, background_tasks: BackgroundTasks) -> dict:
    return await _trigger_stage(task_id, RunStage.WORK, background_tasks)


@router.post("/{task_id}/review", status_code=201)
async def trigger_review(task_id: str, background_tasks: BackgroundTasks) -> dict:
    return await _trigger_stage(task_id, RunStage.REVIEW, background_tasks)
