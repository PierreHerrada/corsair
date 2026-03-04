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
    sync_status_to_jira,
)
from app.models.setting import Setting
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
    async def test_known_statuses(self):
        assert await _map_jira_status("To Do") == TaskStatus.BACKLOG
        assert await _map_jira_status("In Progress") == TaskStatus.WORKING
        assert await _map_jira_status("Done") == TaskStatus.DONE
        assert await _map_jira_status("In Review") == TaskStatus.REVIEWING
        assert await _map_jira_status("Planned") == TaskStatus.PLANNED

    async def test_unknown_defaults_to_backlog(self):
        assert await _map_jira_status("Some Custom Status") == TaskStatus.BACKLOG

    async def test_case_insensitive(self):
        assert await _map_jira_status("IN PROGRESS") == TaskStatus.WORKING
        assert await _map_jira_status("done") == TaskStatus.DONE

    async def test_db_backed_mapping(self):
        import json

        await Setting.create(
            key="jira_status_mapping",
            value=json.dumps({"custom status": "working"}),
        )
        assert await _map_jira_status("Custom Status") == TaskStatus.WORKING
        # Default statuses still work (merged)
        assert await _map_jira_status("Done") == TaskStatus.DONE

    async def test_invalid_json_falls_back(self):
        await Setting.create(
            key="jira_status_mapping",
            value="not valid json{{{",
        )
        # Should fall back to defaults without error
        assert await _map_jira_status("Done") == TaskStatus.DONE
        assert await _map_jira_status("In Progress") == TaskStatus.WORKING

    async def test_partial_override(self):
        import json

        # Override only "done" → "reviewing"
        await Setting.create(
            key="jira_status_mapping",
            value=json.dumps({"done": "reviewing"}),
        )
        assert await _map_jira_status("Done") == TaskStatus.REVIEWING
        # Other defaults remain
        assert await _map_jira_status("In Progress") == TaskStatus.WORKING

    async def test_invalid_status_value_ignored(self):
        import json

        await Setting.create(
            key="jira_status_mapping",
            value=json.dumps({"custom": "not_a_real_status"}),
        )
        # Invalid values are skipped, defaults remain
        assert await _map_jira_status("custom") == TaskStatus.BACKLOG
        assert await _map_jira_status("Done") == TaskStatus.DONE


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


# --- sync_status_to_jira ---


class TestSyncStatusToJira:
    async def test_no_jira_key(self):
        """Tasks without a jira_key should be skipped."""
        task = await Task.create(
            title="No Jira",
            jira_key=None,
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        result = await sync_status_to_jira(task, TaskStatus.WORKING)
        assert result is False

    async def test_no_jira_integration(self):
        """When Jira integration is not registered, should return False."""
        task = await Task.create(
            title="Has Jira",
            jira_key="SWE-100",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        with patch(
            "app.integrations.registry.IntegrationRegistry"
        ) as mock_registry:
            mock_registry.get.return_value = None
            result = await sync_status_to_jira(task, TaskStatus.WORKING)
            assert result is False

    async def test_successful_transition(self, jira):
        """Should call update_status with the first matching transition."""
        task = await Task.create(
            title="Transition test",
            jira_key="SWE-101",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        with (
            patch(
                "app.integrations.registry.IntegrationRegistry"
            ) as mock_registry,
            patch.object(
                jira,
                "update_status",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_update,
        ):
            mock_registry.get.return_value = jira
            result = await sync_status_to_jira(task, TaskStatus.WORKING)
            assert result is True
            mock_update.assert_called_once_with("SWE-101", "In Progress")

    async def test_first_transition_fails_second_succeeds(self, jira):
        """Should try the next candidate when the first returns False."""
        task = await Task.create(
            title="Fallback test",
            jira_key="SWE-102",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        with (
            patch(
                "app.integrations.registry.IntegrationRegistry"
            ) as mock_registry,
            patch.object(
                jira,
                "update_status",
                new_callable=AsyncMock,
                side_effect=[False, True],
            ) as mock_update,
        ):
            mock_registry.get.return_value = jira
            # DONE has candidates: ["Done", "Closed", "Resolved"]
            result = await sync_status_to_jira(task, TaskStatus.DONE)
            assert result is True
            assert mock_update.call_count == 2
            mock_update.assert_any_call("SWE-102", "Done")
            mock_update.assert_any_call("SWE-102", "Closed")

    async def test_all_transitions_fail(self, jira):
        """When no transitions match, should return False."""
        task = await Task.create(
            title="No match test",
            jira_key="SWE-103",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        with (
            patch(
                "app.integrations.registry.IntegrationRegistry"
            ) as mock_registry,
            patch.object(
                jira,
                "update_status",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            mock_registry.get.return_value = jira
            result = await sync_status_to_jira(task, TaskStatus.WORKING)
            assert result is False

    async def test_db_backed_reverse_mapping(self, jira):
        """Custom reverse mapping from DB should override defaults."""
        import json

        await Setting.create(
            key="jira_reverse_status_mapping",
            value=json.dumps({"working": ["Start Work", "Begin"]}),
        )
        task = await Task.create(
            title="Custom mapping",
            jira_key="SWE-104",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        with (
            patch(
                "app.integrations.registry.IntegrationRegistry"
            ) as mock_registry,
            patch.object(
                jira,
                "update_status",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_update,
        ):
            mock_registry.get.return_value = jira
            result = await sync_status_to_jira(task, TaskStatus.WORKING)
            assert result is True
            # Should use the custom mapping, not the default "In Progress"
            mock_update.assert_called_once_with("SWE-104", "Start Work")

    async def test_exception_in_update_status(self, jira):
        """Exceptions in update_status should be caught and next candidate tried."""
        task = await Task.create(
            title="Exception test",
            jira_key="SWE-105",
            slack_channel="",
            slack_thread_ts="",
            slack_user_id="",
        )
        with (
            patch(
                "app.integrations.registry.IntegrationRegistry"
            ) as mock_registry,
            patch.object(
                jira,
                "update_status",
                new_callable=AsyncMock,
                side_effect=[Exception("network error"), True],
            ) as mock_update,
        ):
            mock_registry.get.return_value = jira
            result = await sync_status_to_jira(task, TaskStatus.WORKING)
            assert result is True
            assert mock_update.call_count == 2
