from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.config import settings
from app.integrations.jira.adf import extract_text_from_adf
from app.integrations.jira.client import JiraIntegration
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

_sync_task: Optional[asyncio.Task] = None

_STATUS_MAP: dict[str, TaskStatus] = {
    "to do": TaskStatus.BACKLOG,
    "backlog": TaskStatus.BACKLOG,
    "selected for development": TaskStatus.PLANNED,
    "planned": TaskStatus.PLANNED,
    "in progress": TaskStatus.WORKING,
    "in review": TaskStatus.REVIEWING,
    "review": TaskStatus.REVIEWING,
    "done": TaskStatus.DONE,
    "closed": TaskStatus.DONE,
    "resolved": TaskStatus.DONE,
}


def _map_jira_status(name: str) -> TaskStatus:
    return _STATUS_MAP.get(name.lower(), TaskStatus.BACKLOG)


async def sync_jira_tickets(jira: JiraIntegration) -> int:
    label = settings.jira_sync_label
    project = settings.jira_project_key
    jql = f'project = "{project}" AND labels = "{label}"'

    try:
        issues = await jira.search_issues(jql)
    except Exception:
        logger.exception("Failed to fetch Jira issues")
        return 0

    created = 0
    for issue in issues:
        key = issue["key"]
        existing = await Task.filter(jira_key=key).first()
        if existing:
            continue

        fields = issue.get("fields", {})
        summary = fields.get("summary", key)
        description = extract_text_from_adf(fields.get("description"))
        status_name = fields.get("status", {}).get("name", "")
        status = _map_jira_status(status_name)
        jira_url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"

        await Task.create(
            title=summary,
            description=description,
            status=status,
            jira_key=key,
            jira_url=jira_url,
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        logger.info("Created task from Jira issue %s", key)
        created += 1

    return created


async def _sync_loop(jira: JiraIntegration) -> None:
    interval = settings.jira_sync_interval_seconds
    while True:
        count = await sync_jira_tickets(jira)
        if count:
            logger.info("Synced %d new Jira tickets", count)
        await asyncio.sleep(interval)


def start_sync(jira: JiraIntegration) -> asyncio.Task:
    global _sync_task
    _sync_task = asyncio.create_task(_sync_loop(jira))
    return _sync_task


def stop_sync() -> None:
    global _sync_task
    if _sync_task is not None:
        _sync_task.cancel()
        _sync_task = None
