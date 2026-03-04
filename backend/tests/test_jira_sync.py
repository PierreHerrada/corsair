from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.jira.sync import (
    import_jira_issue,
    push_board_tasks_to_jira,
    sync_jira_tickets,
)
from app.models.task import Task, TaskStatus


def _make_issue(key: str, summary: str = "Test", status_name: str = "To Do") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": None,
            "status": {"name": status_name},
        },
    }


@pytest.fixture
async def jira_task():
    return await Task.create(
        id=uuid.uuid4(),
        title="Jira task",
        description="Synced from Jira",
        status=TaskStatus.BACKLOG,
        jira_key="SWE-100",
        jira_url="https://company.atlassian.net/browse/SWE-100",
        slack_channel="",
        slack_thread_ts="",
        slack_user_id="",
    )


@pytest.fixture
async def deleted_jira_task():
    return await Task.create(
        id=uuid.uuid4(),
        title="Deleted Jira task",
        description="Was soft-deleted",
        status=TaskStatus.BACKLOG,
        jira_key="SWE-200",
        jira_url="https://company.atlassian.net/browse/SWE-200",
        slack_channel="",
        slack_thread_ts="",
        slack_user_id="",
        deleted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
async def local_task():
    """A task created locally (no jira_key) — should not be affected by sync."""
    return await Task.create(
        id=uuid.uuid4(),
        title="Local task",
        description="Created locally",
        status=TaskStatus.BACKLOG,
        slack_channel="C1",
        slack_thread_ts="1.1",
        slack_user_id="U1",
    )


class TestSyncJiraTickets:
    @patch("app.integrations.jira.sync.settings")
    async def test_soft_deletes_missing_keys(self, mock_settings, jira_task):
        """Tasks with jira_keys not in the Jira results should be soft-deleted."""
        mock_settings.jira_sync_label = "corsair"
        mock_settings.jira_project_key = "SWE"
        mock_settings.jira_base_url = "https://company.atlassian.net"

        jira = AsyncMock()
        # Return issues that do NOT include SWE-100
        jira.search_issues.return_value = [_make_issue("SWE-999")]

        await sync_jira_tickets(jira)

        refreshed = await Task.get(id=jira_task.id)
        assert refreshed.deleted_at is not None

    @patch("app.integrations.jira.sync.settings")
    async def test_restores_reappearing_key(self, mock_settings, deleted_jira_task):
        """A soft-deleted task whose key reappears should be restored."""
        mock_settings.jira_sync_label = "corsair"
        mock_settings.jira_project_key = "SWE"
        mock_settings.jira_base_url = "https://company.atlassian.net"

        jira = AsyncMock()
        jira.search_issues.return_value = [_make_issue("SWE-200")]

        await sync_jira_tickets(jira)

        refreshed = await Task.get(id=deleted_jira_task.id)
        assert refreshed.deleted_at is None

    @patch("app.integrations.jira.sync.settings")
    async def test_does_not_touch_active_matching_tasks(self, mock_settings, jira_task):
        """Tasks whose keys ARE in the Jira results stay active."""
        mock_settings.jira_sync_label = "corsair"
        mock_settings.jira_project_key = "SWE"
        mock_settings.jira_base_url = "https://company.atlassian.net"

        jira = AsyncMock()
        jira.search_issues.return_value = [_make_issue("SWE-100")]

        await sync_jira_tickets(jira)

        refreshed = await Task.get(id=jira_task.id)
        assert refreshed.deleted_at is None

    @patch("app.integrations.jira.sync.settings")
    async def test_does_not_touch_local_tasks(self, mock_settings, local_task):
        """Tasks without jira_key should not be soft-deleted."""
        mock_settings.jira_sync_label = "corsair"
        mock_settings.jira_project_key = "SWE"
        mock_settings.jira_base_url = "https://company.atlassian.net"

        jira = AsyncMock()
        jira.search_issues.return_value = []

        await sync_jira_tickets(jira)

        refreshed = await Task.get(id=local_task.id)
        assert refreshed.deleted_at is None

    @patch("app.integrations.jira.sync.settings")
    async def test_returns_zero_on_fetch_failure(self, mock_settings):
        mock_settings.jira_sync_label = "corsair"
        mock_settings.jira_project_key = "SWE"

        jira = AsyncMock()
        jira.search_issues.side_effect = Exception("API error")

        result = await sync_jira_tickets(jira)
        assert result == 0


class TestImportJiraIssue:
    @patch("app.integrations.jira.sync.settings")
    async def test_creates_new_task(self, mock_settings):
        mock_settings.jira_base_url = "https://company.atlassian.net"
        issue = _make_issue("SWE-300", summary="New issue")

        task = await import_jira_issue(issue)

        assert task is not None
        assert task.jira_key == "SWE-300"
        assert task.title == "New issue"
        assert task.deleted_at is None

    @patch("app.integrations.jira.sync.settings")
    async def test_skips_existing_active_task_same_status(self, mock_settings, jira_task):
        """Existing task with unchanged status returns None."""
        mock_settings.jira_base_url = "https://company.atlassian.net"
        issue = _make_issue("SWE-100", status_name="To Do")  # maps to BACKLOG, same as fixture

        task = await import_jira_issue(issue)
        assert task is None

    @patch("app.integrations.jira.sync.settings")
    async def test_updates_existing_task_status(self, mock_settings, jira_task):
        """Existing task with changed Jira status gets updated in the DB."""
        mock_settings.jira_base_url = "https://company.atlassian.net"
        issue = _make_issue("SWE-100", status_name="In Progress")

        task = await import_jira_issue(issue)

        assert task is not None
        assert task.id == jira_task.id
        refreshed = await Task.get(id=jira_task.id)
        assert refreshed.status == TaskStatus.WORKING

    @patch("app.integrations.jira.sync.settings")
    async def test_restores_soft_deleted_task(self, mock_settings, deleted_jira_task):
        mock_settings.jira_base_url = "https://company.atlassian.net"
        issue = _make_issue("SWE-200")

        task = await import_jira_issue(issue)

        assert task is not None
        assert task.id == deleted_jira_task.id
        assert task.deleted_at is None

    @patch("app.integrations.jira.sync.settings")
    async def test_restores_and_updates_status(self, mock_settings, deleted_jira_task):
        """Soft-deleted task that reappears with a new status gets both restored and updated."""
        mock_settings.jira_base_url = "https://company.atlassian.net"
        issue = _make_issue("SWE-200", status_name="Done")

        task = await import_jira_issue(issue)

        assert task is not None
        assert task.deleted_at is None
        refreshed = await Task.get(id=deleted_jira_task.id)
        assert refreshed.status == TaskStatus.DONE


class TestPushBoardTasksToJira:
    async def test_skips_soft_deleted_tasks(self):
        """Soft-deleted tasks without jira_key should not be pushed."""
        await Task.create(
            id=uuid.uuid4(),
            title="Deleted local task",
            status=TaskStatus.BACKLOG,
            slack_channel="C1",
            slack_thread_ts="1.1",
            slack_user_id="U1",
            deleted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        jira = AsyncMock()
        result = await push_board_tasks_to_jira(jira)

        assert result == 0
        jira.create_issue.assert_not_called()


class TestTaskActive:
    async def test_active_excludes_soft_deleted(self, jira_task, deleted_jira_task):
        active = await Task.active().all()
        active_ids = {t.id for t in active}
        assert jira_task.id in active_ids
        assert deleted_jira_task.id not in active_ids

    async def test_active_includes_all_non_deleted(self, jira_task, local_task):
        active = await Task.active().all()
        active_ids = {t.id for t in active}
        assert jira_task.id in active_ids
        assert local_task.id in active_ids


class TestListTasksExcludesSoftDeleted:
    async def test_list_tasks_excludes_soft_deleted(self, jira_task, deleted_jira_task):
        from httpx import ASGITransport, AsyncClient

        from app.auth import create_access_token
        from app.main import create_app

        app = create_app()
        token = create_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/tasks", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        task_ids = [t["id"] for t in data]
        assert str(jira_task.id) in task_ids
        assert str(deleted_jira_task.id) not in task_ids
