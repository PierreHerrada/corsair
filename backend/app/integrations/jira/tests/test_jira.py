import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.jira.client import JiraIntegration


def _make_response(status_code: int, json_data=None) -> httpx.Response:
    """Create a mock httpx Response with a request set (needed for raise_for_status)."""
    resp = httpx.Response(status_code, json=json_data)
    resp._request = httpx.Request("GET", "https://test.atlassian.net")
    return resp


@pytest.fixture
def jira():
    return JiraIntegration()


class TestJiraIntegration:
    def test_metadata(self, jira):
        assert jira.name == "jira"
        assert jira.description == "Jira integration for ticket management"
        assert "JIRA_BASE_URL" in jira.required_env_vars
        assert "JIRA_EMAIL" in jira.required_env_vars
        assert "JIRA_API_TOKEN" in jira.required_env_vars
        assert "JIRA_PROJECT_KEY" in jira.required_env_vars

    def test_not_configured(self, jira):
        with patch.dict(os.environ, {}, clear=True):
            missing = jira.check_env_vars()
            assert len(missing) == 4
            assert not jira.is_configured

    def test_configured(self, jira):
        env = {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_EMAIL": "test@test.com",
            "JIRA_API_TOKEN": "token",
            "JIRA_PROJECT_KEY": "SWE",
        }
        with patch.dict(os.environ, env):
            assert jira.is_configured
            assert jira.check_env_vars() == []

    async def test_health_check_success(self, jira):
        mock_response = _make_response(200, {"displayName": "Test User"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await jira.health_check()
            assert result is True

    async def test_health_check_failure(self, jira):
        mock_response = _make_response(401, {"error": "Unauthorized"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await jira.health_check()
            assert result is False

    async def test_health_check_exception(self, jira):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await jira.health_check()
            assert result is False

    async def test_create_issue(self, jira):
        mock_response = _make_response(201, {"key": "SWE-123", "id": "10001"})
        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response),
            patch.object(jira, "_get_base_url", return_value="https://test.atlassian.net"),
        ):
            result = await jira.create_issue(
                title="Test issue",
                description="Test description",
                acceptance="Tests pass",
            )
            assert result["key"] == "SWE-123"
            assert "SWE-123" in result["url"]

    async def test_update_status_success(self, jira):
        transitions_response = _make_response(
            200,
            {
                "transitions": [
                    {"id": "21", "name": "In Progress"},
                    {"id": "31", "name": "Done"},
                ]
            },
        )
        transition_response = _make_response(204)

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=transitions_response),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=transition_response),
            patch.object(jira, "_get_base_url", return_value="https://test.atlassian.net"),
        ):
            result = await jira.update_status("SWE-123", "Done")
            assert result is True

    async def test_update_status_transition_not_found(self, jira):
        transitions_response = _make_response(
            200,
            {"transitions": [{"id": "21", "name": "In Progress"}]},
        )
        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=transitions_response),
            patch.object(jira, "_get_base_url", return_value="https://test.atlassian.net"),
        ):
            result = await jira.update_status("SWE-123", "Nonexistent")
            assert result is False

    async def test_update_fields_success(self, jira):
        mock_response = _make_response(204)
        mock_put = AsyncMock(return_value=mock_response)
        with (
            patch("httpx.AsyncClient.put", mock_put),
            patch.object(jira, "_get_base_url", return_value="https://test.atlassian.net"),
        ):
            fields = {"customfield_10157": "plan text"}
            result = await jira.update_fields("SWE-123", fields)
            assert result is True
            mock_put.assert_called_once()
            call_kwargs = mock_put.call_args
            assert call_kwargs.kwargs["json"] == {"fields": fields}

    async def test_update_fields_failure(self, jira):
        resp = _make_response(400, {"errors": {"customfield_10157": "invalid"}})
        with (
            patch("httpx.AsyncClient.put", AsyncMock(return_value=resp)),
            patch.object(jira, "_get_base_url", return_value="https://test.atlassian.net"),
        ):
            result = await jira.update_fields("SWE-123", {"cf": "bad"})
            assert result is False

    async def test_update_fields_exception(self, jira):
        err = Exception("Network error")
        with (
            patch("httpx.AsyncClient.put", AsyncMock(side_effect=err)),
            patch.object(jira, "_get_base_url", return_value="https://test.atlassian.net"),
        ):
            result = await jira.update_fields("SWE-123", {"cf": "plan"})
            assert result is False
