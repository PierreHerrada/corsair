from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.integrations.datadog.analyzer import run_analysis
from app.integrations.datadog.client import DatadogIntegration
from app.integrations.registry import IntegrationRegistry
from app.models.datadog_analysis import AnalysisSource, AnalysisStatus, DatadogAnalysis

router = APIRouter(prefix="/api/v1/datadog", tags=["datadog"])

logger = logging.getLogger(__name__)


def _analysis_to_dict(a: DatadogAnalysis) -> dict:
    return {
        "id": str(a.id),
        "source": a.source,
        "trigger": a.trigger,
        "status": a.status,
        "query": a.query,
        "trace_id": a.trace_id,
        "log_count": a.log_count,
        "raw_logs": a.raw_logs,
        "raw_trace": a.raw_trace,
        "summary": a.summary,
        "error_message": a.error_message,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _analysis_to_list_dict(a: DatadogAnalysis) -> dict:
    """Lighter dict for list responses (no raw data)."""
    return {
        "id": str(a.id),
        "source": a.source,
        "trigger": a.trigger,
        "status": a.status,
        "query": a.query,
        "trace_id": a.trace_id,
        "log_count": a.log_count,
        "summary": a.summary,
        "error_message": a.error_message,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


class AnalyzeRequest(BaseModel):
    url: Optional[str] = None
    query: Optional[str] = None
    trace_id: Optional[str] = None


def _get_datadog_client() -> DatadogIntegration:
    integration = IntegrationRegistry.get("datadog")
    if integration is None:
        raise HTTPException(status_code=503, detail="Datadog integration is not configured")
    return integration  # type: ignore[return-value]


async def _run_analysis_task(
    analysis_id: str,
    url: str | None,
    query: str | None,
    trace_id: str | None,
) -> None:
    """Background task that performs the actual analysis."""
    analysis = await DatadogAnalysis.get(id=analysis_id)
    analysis.status = AnalysisStatus.ANALYZING
    await analysis.save()

    try:
        client = _get_datadog_client()
        result = await run_analysis(client, query=query, trace_id=trace_id, url=url)
        analysis.query = result["query"]
        analysis.trace_id = result["trace_id"]
        analysis.log_count = result["log_count"]
        analysis.raw_logs = result["raw_logs"]
        analysis.raw_trace = result["raw_trace"]
        analysis.summary = result["summary"]
        analysis.error_message = result["error_message"]
        analysis.status = AnalysisStatus.FAILED if result["error_message"] else AnalysisStatus.DONE
        await analysis.save()
    except Exception as exc:
        logger.exception("Analysis %s failed", analysis_id)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = str(exc)
        await analysis.save()


@router.get("/analyses")
async def list_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    qs = DatadogAnalysis.all().order_by("-created_at")
    total = await qs.count()
    analyses = await qs.offset(offset).limit(limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "analyses": [_analysis_to_list_dict(a) for a in analyses],
    }


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str) -> dict:
    analysis = await DatadogAnalysis.get_or_none(id=analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _analysis_to_dict(analysis)


@router.post("/analyze", status_code=201)
async def trigger_analysis(body: AnalyzeRequest, background_tasks: BackgroundTasks) -> dict:
    if not body.url and not body.query and not body.trace_id:
        raise HTTPException(
            status_code=422,
            detail="At least one of url, query, or trace_id is required",
        )

    trigger = body.url or body.query or body.trace_id or ""
    analysis = await DatadogAnalysis.create(
        source=AnalysisSource.MANUAL,
        trigger=trigger,
        status=AnalysisStatus.PENDING,
    )
    background_tasks.add_task(
        _run_analysis_task, str(analysis.id),
        body.url, body.query, body.trace_id,
    )
    return _analysis_to_dict(analysis)
