from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.agent.post_stage import handle_stage_completion
from app.config import settings
from app.models import AgentLog, AgentRun, RunStatus
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


def _verify_secret(x_internal_secret: str = Header(...)) -> None:
    if x_internal_secret != settings.internal_api_secret:
        raise HTTPException(status_code=403, detail="Invalid internal secret")


class LogLine(BaseModel):
    type: str
    content: str
    timestamp: float


class LogBatch(BaseModel):
    lines: list[LogLine]


class RunCompletion(BaseModel):
    status: str
    exit_code: Optional[int] = None
    token_usage: Optional[dict] = None
    cost: Optional[dict] = None
    error_message: Optional[str] = None


@router.post("/runs/{run_id}/logs")
async def receive_logs(
    run_id: str,
    batch: LogBatch,
    x_internal_secret: str = Header(...),
) -> dict:
    _verify_secret(x_internal_secret)

    run = await AgentRun.filter(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Move from launching to running on first log batch
    if run.status == RunStatus.LAUNCHING:
        run.status = RunStatus.RUNNING
        await run.save()

    for line in batch.lines:
        log = await AgentLog.create(
            run_id=run.id,
            type=line.type,
            content={"text": line.content},
        )
        # Broadcast to WebSocket clients
        await ws_manager.broadcast_dict(
            str(run.id),
            {
                "id": str(log.id),
                "run_id": str(run.id),
                "type": line.type,
                "content": {"text": line.content},
                "created_at": log.created_at.isoformat() if log.created_at else None,
            },
        )

    return {"received": len(batch.lines)}


@router.post("/runs/{run_id}/complete")
async def complete_run(
    run_id: str,
    body: RunCompletion,
    x_internal_secret: str = Header(...),
) -> dict:
    _verify_secret(x_internal_secret)

    run = await AgentRun.filter(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Map "completed" -> "done" to match RunStatus enum
    status_value = body.status
    if status_value == "completed":
        status_value = "done"

    run.status = RunStatus(status_value)
    run.finished_at = datetime.now(timezone.utc)
    if body.error_message:
        run.error_message = body.error_message
    if body.token_usage:
        run.tokens_in = body.token_usage.get("input_tokens", 0)
        run.tokens_out = body.token_usage.get("output_tokens", 0)
    if body.cost:
        from decimal import Decimal
        run.cost_usd = Decimal(str(body.cost.get("total_cost", 0)))
    await run.save()

    # Broadcast completion event
    await ws_manager.broadcast_dict(
        str(run.id),
        {
            "type": "run_complete",
            "run_id": str(run.id),
            "status": status_value,
            "exit_code": body.exit_code,
        },
    )

    # Handle post-stage logic
    if status_value == "done":
        try:
            await handle_stage_completion(run)
        except Exception:
            logger.exception("Post-stage handler failed for run %s", run.id)

    return {"ok": True}
