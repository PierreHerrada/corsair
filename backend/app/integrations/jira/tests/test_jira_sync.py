import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.jira.adf import extract_text_from_adf
from app.integrations.jira.client import JiraIntegration
from app.integrations.jira.sync import (
    _map_jira_status,
    start_sync,
    stop_sync,
    sync_jira_tickets,
)
from app.models.task import Task, TaskStatus


def _make_response(status_code: int, json_data=None) -> httpx.Response:
    resp = httpx.Response(status_code, json=json_data)
    resp._request = httpx.Request("GET", "https://test.atlassian.net")
    return resp


@pytest.fixture
def jira():
    return JiraIntegration()


# --- ADF extraction ---


class TestExtractTextFromAdf:
    def test_none_input(self):
        assert extract_text_from_adf(None) == ""

    def test_empty_doc(self):
        assert extract_text_from_adf({"type": "doc", "content": []}) == ""

    def test_single_paragraph(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }
        assert extract_text_from_adf(adf) == "Hello world"

    def test_multi_paragraph(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "First"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second"}],
                },
            ],
        }
        result = extract_text_from_adf(adf)
        assert "First" in result
        assert "Second" in result

    def test_formatting_marks(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "bold ",
                            "marks": [{"type": "strong"}],
                        },
                        {"type": "text", "text": "normal"},
                    ],
                }
            ],
        }
        result = extract_text_from_adf(adf)
        assert "bold " in result
        assert "normal" in result

    def test_bullet_list(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "item one"}
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "item two"}
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        result = extract_text_from_adf(adf)
        assert "item one" in result
        assert "item two" in result


# --- Status mapping ---


class TestMapJiraStatus:
    def test_known_statuses(self):
        assert _map_jira_status("To Do") == TaskStatus.BACKLOG
        assert _map_jira_status("In Progress") == TaskStatus.WORKING
        assert _map_jira_status("Done") == TaskStatus.DONE
        assert _map_jira_status("In Review") == TaskStatus.REVIEWING
        assert _map_jira_status("Planned") == TaskStatus.PLANNED

    def test_unknown_defaults_to_backlog(self):
        assert _map_jira_status("Some Custom Status") == TaskStatus.BACKLOG

    def test_case_insensitive(self):
        assert _map_jira_status("IN PROGRESS") == TaskStatus.WORKING
        assert _map_jira_status("done") == TaskStatus.DONE


# --- search_issues ---


class TestSearchIssues:
    async def test_success(self, jira):
        issues = [{"key": "SWE-1"}, {"key": "SWE-2"}]
        mock_resp = _make_response(200, {"issues": issues})
        with (
            patch(
                "httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            patch.object(
                jira,
                "_get_base_url",
                return_value="https://test.atlassian.net",
            ),
        ):
            result = await jira.search_issues("project = SWE")
            assert len(result) == 2
            assert result[0]["key"] == "SWE-1"

    async def test_empty_results(self, jira):
        mock_resp = _make_response(200, {"issues": []})
        with (
            patch(
                "httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            patch.object(
                jira,
                "_get_base_url",
                return_value="https://test.atlassian.net",
            ),
        ):
            result = await jira.search_issues("project = SWE")
            assert result == []

    async def test_http_error(self, jira):
        mock_resp = _make_response(400, {"errorMessages": ["bad query"]})
        with (
            patch(
                "httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            patch.object(
                jira,
                "_get_base_url",
                return_value="https://test.atlassian.net",
            ),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await jira.search_issues("bad jql")


# --- sync_jira_tickets ---


class TestSyncJiraTickets:
    async def test_creates_new_tasks(self, jira):
        issues = [
            {
                "key": "SWE-10",
                "fields": {
                    "summary": "New feature",
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "Build it"}
                                ],
                            }
                        ],
                    },
                    "status": {"name": "To Do"},
                },
            }
        ]
        with (
            patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                return_value=issues,
            ),
            patch(
                "app.integrations.jira.sync.settings",
                jira_sync_label="corsair",
                jira_project_key="SWE",
                jira_base_url="https://test.atlassian.net",
            ),
        ):
            count = await sync_jira_tickets(jira)
            assert count == 1
            task = await Task.filter(jira_key="SWE-10").first()
            assert task is not None
            assert task.title == "New feature"
            assert "Build it" in task.description
            assert task.status == TaskStatus.BACKLOG
            assert task.slack_channel == ""
            assert task.slack_thread_ts == ""
            assert task.slack_user_id == ""

    async def test_skips_existing(self, jira):
        await Task.create(
            title="Existing",
            jira_key="SWE-20",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        issues = [
            {
                "key": "SWE-20",
                "fields": {
                    "summary": "Existing task",
                    "description": None,
                    "status": {"name": "To Do"},
                },
            }
        ]
        with (
            patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                return_value=issues,
            ),
            patch(
                "app.integrations.jira.sync.settings",
                jira_sync_label="corsair",
                jira_project_key="SWE",
                jira_base_url="https://test.atlassian.net",
            ),
        ):
            count = await sync_jira_tickets(jira)
            assert count == 0

    async def test_handles_api_failure(self, jira):
        with (
            patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError(
                    "error",
                    request=httpx.Request("GET", "https://test"),
                    response=_make_response(500),
                ),
            ),
            patch(
                "app.integrations.jira.sync.settings",
                jira_sync_label="corsair",
                jira_project_key="SWE",
                jira_base_url="https://test.atlassian.net",
            ),
        ):
            count = await sync_jira_tickets(jira)
            assert count == 0

    async def test_null_description(self, jira):
        issues = [
            {
                "key": "SWE-30",
                "fields": {
                    "summary": "No desc",
                    "description": None,
                    "status": {"name": "In Progress"},
                },
            }
        ]
        with (
            patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                return_value=issues,
            ),
            patch(
                "app.integrations.jira.sync.settings",
                jira_sync_label="corsair",
                jira_project_key="SWE",
                jira_base_url="https://test.atlassian.net",
            ),
        ):
            count = await sync_jira_tickets(jira)
            assert count == 1
            task = await Task.filter(jira_key="SWE-30").first()
            assert task.description == ""
            assert task.status == TaskStatus.WORKING

    async def test_status_mapping(self, jira):
        issues = [
            {
                "key": "SWE-40",
                "fields": {
                    "summary": "Done task",
                    "description": None,
                    "status": {"name": "Done"},
                },
            }
        ]
        with (
            patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                return_value=issues,
            ),
            patch(
                "app.integrations.jira.sync.settings",
                jira_sync_label="corsair",
                jira_project_key="SWE",
                jira_base_url="https://test.atlassian.net",
            ),
        ):
            await sync_jira_tickets(jira)
            task = await Task.filter(jira_key="SWE-40").first()
            assert task.status == TaskStatus.DONE

    async def test_multiple_issues(self, jira):
        issues = [
            {
                "key": f"SWE-{i}",
                "fields": {
                    "summary": f"Task {i}",
                    "description": None,
                    "status": {"name": "To Do"},
                },
            }
            for i in range(50, 53)
        ]
        with (
            patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                return_value=issues,
            ),
            patch(
                "app.integrations.jira.sync.settings",
                jira_sync_label="corsair",
                jira_project_key="SWE",
                jira_base_url="https://test.atlassian.net",
            ),
        ):
            count = await sync_jira_tickets(jira)
            assert count == 3
            assert await Task.filter(jira_key="SWE-50").exists()
            assert await Task.filter(jira_key="SWE-51").exists()
            assert await Task.filter(jira_key="SWE-52").exists()


# --- start_sync / stop_sync ---


class TestSyncLifecycle:
    async def test_start_and_stop(self, jira):
        with patch(
            "app.integrations.jira.sync.settings",
            jira_sync_interval_seconds=1,
            jira_sync_label="corsair",
            jira_project_key="SWE",
            jira_base_url="https://test.atlassian.net",
        ):
            with patch.object(
                jira,
                "search_issues",
                new_callable=AsyncMock,
                return_value=[],
            ):
                task = start_sync(jira)
                assert isinstance(task, asyncio.Task)
                assert not task.done()

                stop_sync()
                # Give the event loop a chance to process cancellation
                await asyncio.sleep(0.1)
                assert task.done()

    async def test_stop_when_not_started(self):
        # Should not raise
        stop_sync()
