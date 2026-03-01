from __future__ import annotations

from fastapi import APIRouter

from app.models import AgentRun, RunStage, RunStatus, Task, TaskStatus

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats() -> dict:
    runs = await AgentRun.all()
    total_cost = sum(float(r.cost_usd) for r in runs)
    active_runs = await AgentRun.filter(status=RunStatus.RUNNING).count()

    tasks_by_status = {}
    for status in TaskStatus:
        count = await Task.filter(status=status).count()
        tasks_by_status[status.value] = count

    cost_by_stage = {}
    for stage in RunStage:
        stage_runs = await AgentRun.filter(stage=stage)
        cost_by_stage[stage.value] = sum(float(r.cost_usd) for r in stage_runs)

    return {
        "total_cost_usd": round(total_cost, 2),
        "active_runs": active_runs,
        "tasks_by_status": tasks_by_status,
        "cost_by_stage": cost_by_stage,
    }


@router.get("/costs")
async def get_costs() -> list[dict]:
    tasks = await Task.all()
    result = []
    for task in tasks:
        runs = await AgentRun.filter(task_id=task.id)
        total_cost = sum(float(r.cost_usd) for r in runs)
        cost_by_stage = {}
        for stage in RunStage:
            stage_cost = sum(float(r.cost_usd) for r in runs if r.stage == stage)
            cost_by_stage[stage.value] = round(stage_cost, 6)
        result.append(
            {
                "task_id": str(task.id),
                "task_title": task.title,
                "total_cost_usd": round(total_cost, 6),
                "cost_by_stage": cost_by_stage,
            }
        )
    return result
