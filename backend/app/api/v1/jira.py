from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.jira.client import JiraIntegration
from app.integrations.jira.sync import import_jira_issue
from app.integrations.registry import IntegrationRegistry
from app.models.task import Task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jira", tags=["jira"])


def _get_jira() -> JiraIntegration:
    jira = IntegrationRegistry.get("jira")
    if jira is None or not isinstance(jira, JiraIntegration):
        raise HTTPException(status_code=503, detail="Jira integration is not configured")
    return jira


class JiraImportRequest(BaseModel):
    issue_key: str


@router.post("/import", status_code=200)
async def import_issue(body: JiraImportRequest) -> dict:
    """Fetch a Jira issue by key and add it to the board if not already present."""
    jira = _get_jira()

    # Check if already in the board
    existing = await Task.filter(jira_key=body.issue_key).first()
    if existing:
        return {"status": "exists", "task_id": str(existing.id), "jira_key": body.issue_key}

    try:
        issue = await jira.get_issue(body.issue_key)
    except Exception:
        logger.exception("Jira import: failed to fetch %s", body.issue_key)
        raise HTTPException(status_code=404, detail=f"Could not fetch Jira issue {body.issue_key}")

    task = await import_jira_issue(issue)
    if task is None:
        # Race condition: created between the check and import
        existing = await Task.filter(jira_key=body.issue_key).first()
        return {"status": "exists", "task_id": str(existing.id) if existing else None, "jira_key": body.issue_key}

    logger.info("Jira import: imported %s as task %s", body.issue_key, task.id)
    return {"status": "created", "task_id": str(task.id), "jira_key": body.issue_key}
