from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Request

from app.models.datadog_analysis import AnalysisSource, AnalysisStatus, DatadogAnalysis

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

logger = logging.getLogger(__name__)


async def _handle_datadog_webhook(payload: dict, background_tasks: BackgroundTasks) -> None:
    """Parse a Datadog Monitor webhook payload and create an analysis."""
    title = payload.get("title", payload.get("alert_title", "Datadog alert"))
    tags = payload.get("tags", "")
    query = ""

    # Extract log query from tags or build a default from the alert
    if isinstance(tags, str) and tags:
        query = tags
    elif isinstance(tags, list) and tags:
        query = " ".join(tags)

    logs_sample = payload.get("logs_sample", [])

    analysis = await DatadogAnalysis.create(
        source=AnalysisSource.WEBHOOK,
        trigger=title,
        status=AnalysisStatus.PENDING,
        query=query,
        raw_logs=logs_sample if isinstance(logs_sample, list) else [],
    )

    if query:
        from app.api.v1.datadog import _run_analysis_task

        background_tasks.add_task(_run_analysis_task, str(analysis.id), None, query, None)
    else:
        # No query to run — mark done with whatever we have
        analysis.status = AnalysisStatus.DONE
        analysis.summary = f"Webhook alert received: {title}"
        analysis.log_count = len(logs_sample) if isinstance(logs_sample, list) else 0
        await analysis.save()


@router.post("/{integration_name}")
async def receive_webhook(
    integration_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generic webhook endpoint for integrations."""
    body = await request.body()
    logger.info("Webhook received for integration '%s': %d bytes", integration_name, len(body))

    if integration_name == "datadog":
        try:
            payload = await request.json()
            await _handle_datadog_webhook(payload, background_tasks)
        except Exception:
            logger.exception("Failed to process Datadog webhook")

    return {"status": "ok"}
