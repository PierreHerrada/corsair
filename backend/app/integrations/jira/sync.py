from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.integrations.jira.adf import extract_text_from_adf
from app.integrations.jira.client import JiraIntegration
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


async def _analyze_task_safe(task) -> None:
    try:
        from app.agent.analysis import analyze_task
        await analyze_task(task)
    except Exception:
        logger.exception("Failed to analyze task %s", task.id)

_sync_task: Optional[asyncio.Task] = None

_STATUS_MAP: dict[str, TaskStatus] = {
    "to do": TaskStatus.BACKLOG,
    "backlog": TaskStatus.BACKLOG,
    "icebox": TaskStatus.BACKLOG,
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
    """Pull Jira issues with the corsair label into the board."""
    label = settings.jira_sync_label
    project = settings.jira_project_key
    jql = f'project = "{project}" AND labels = "{label}"'

    logger.info("Jira sync: searching with JQL: %s", jql)

    try:
        issues = await jira.search_issues(jql)
    except Exception:
        logger.exception("Jira sync: failed to fetch issues")
        return 0

    logger.info("Jira sync: found %d issues matching label '%s'", len(issues), label)

    jira_keys = {issue["key"] for issue in issues}

    # Soft-delete active tasks whose jira_key is no longer in the Jira results
    active_jira_tasks = await Task.active().filter(
        jira_key__not_isnull=True,
    ).exclude(jira_key="").all()
    now = datetime.now(timezone.utc)
    for task in active_jira_tasks:
        if task.jira_key not in jira_keys:
            task.deleted_at = now
            await task.save()
            logger.info(
                "Jira sync: soft-deleted task '%s' (%s) — key %s no longer in Jira results",
                task.title[:60], task.id, task.jira_key,
            )

    # Restore previously soft-deleted tasks that reappear in the results
    deleted_jira_tasks = await Task.filter(
        deleted_at__not_isnull=True,
        jira_key__not_isnull=True,
    ).exclude(jira_key="").all()
    for task in deleted_jira_tasks:
        if task.jira_key in jira_keys:
            task.deleted_at = None
            await task.save()
            logger.info(
                "Jira sync: restored soft-deleted task '%s' (%s) — key %s reappeared",
                task.title[:60], task.id, task.jira_key,
            )

    created = 0
    for issue in issues:
        try:
            task = await import_jira_issue(issue)
            if task is not None:
                created += 1
        except Exception:
            logger.exception("Jira sync: failed to import issue %s", issue.get("key", "?"))

    return created


async def push_board_tasks_to_jira(jira: JiraIntegration) -> int:
    """Push active board tasks that have no Jira key to Jira."""
    tasks = await Task.active().filter(jira_key=None).all()
    if not tasks:
        # Also check for empty string jira_key
        tasks = await Task.active().filter(jira_key="").all()
    if not tasks:
        return 0

    logger.info("Jira push: found %d board tasks without Jira key", len(tasks))

    pushed = 0
    for task in tasks:
        # Skip tasks with empty string jira_key=None OR jira_key=""
        if task.jira_key:
            continue
        try:
            result = await jira.create_issue(
                title=task.title,
                description=task.description,
                acceptance=task.acceptance,
            )
            task.jira_key = result["key"]
            task.jira_url = result["url"]
            await task.save()
            pushed += 1
            logger.info(
                "Jira push: created %s for board task '%s' (%s)",
                result["key"], task.title[:60], task.id,
            )
        except Exception:
            logger.exception("Jira push: failed to create issue for task %s", task.id)

    return pushed


async def import_jira_issue(issue: dict) -> Optional[Task]:
    """Import a single Jira issue dict into the board.

    Returns the Task if created/restored, None if it already exists.
    """
    key = issue["key"]
    existing = await Task.filter(jira_key=key).first()
    if existing:
        updated = False
        if existing.deleted_at is not None:
            existing.deleted_at = None
            updated = True
            logger.info("Jira import: restored soft-deleted task %s (%s)", key, existing.id)

        # Update status from Jira
        fields = issue.get("fields", {})
        status_name = fields.get("status", {}).get("name", "")
        jira_status = _map_jira_status(status_name)
        if existing.status != jira_status:
            logger.info(
                "Jira import: updating task %s (%s) status %s → %s",
                key, existing.id, existing.status.value, jira_status.value,
            )
            existing.status = jira_status
            updated = True

        if updated:
            await existing.save()
            return existing
        logger.debug("Jira import: skipping %s (already exists, status unchanged)", key)
        return None

    fields = issue.get("fields", {})
    summary = fields.get("summary", key)
    description = extract_text_from_adf(fields.get("description"))
    status_name = fields.get("status", {}).get("name", "")
    status = _map_jira_status(status_name)
    jira_url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"

    logger.info(
        "Jira import: creating task from %s — '%s' (status: %s → %s)",
        key, summary, status_name, status.value,
    )

    task = await Task.create(
        title=summary,
        description=description,
        status=status,
        jira_key=key,
        jira_url=jira_url,
        slack_channel="",
        slack_thread_ts="",
        slack_user_id="",
    )

    # Trigger analysis in background
    asyncio.create_task(_analyze_task_safe(task))

    return task


async def _sync_loop(jira: JiraIntegration) -> None:
    interval = settings.jira_sync_interval_seconds
    logger.info("Jira sync loop started (interval: %ds)", interval)
    while True:
        try:
            # Pull: Jira → board
            count = await sync_jira_tickets(jira)
            if count:
                logger.info("Jira sync: imported %d new tickets", count)
            else:
                logger.info("Jira sync: no new tickets found")

            # Push: board → Jira
            pushed = await push_board_tasks_to_jira(jira)
            if pushed:
                logger.info("Jira sync: pushed %d board tasks to Jira", pushed)
        except Exception:
            logger.exception("Jira sync: unexpected error in sync loop")

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
