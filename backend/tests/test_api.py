from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models import AgentRun, ChatMessage, Repository


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestTasksEndpoints:
    async def test_list_tasks_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_tasks(self, client, auth_headers, sample_task):
        resp = await client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test task"
        assert data[0]["status"] == "backlog"

    async def test_get_task(self, client, auth_headers, sample_task):
        resp = await client.get(f"/api/v1/tasks/{sample_task.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test task"
        assert data["latest_run"] is None

    async def test_get_task_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/tasks/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_task_with_run(self, client, auth_headers, sample_task, sample_run):
        resp = await client.get(f"/api/v1/tasks/{sample_task.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_run"] is not None
        assert data["latest_run"]["stage"] == "plan"

    async def test_patch_task_status(self, client, auth_headers, sample_task):
        resp = await client.patch(
            f"/api/v1/tasks/{sample_task.id}",
            json={"status": "planned"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "planned"

    async def test_patch_task_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/v1/tasks/{fake_id}",
            json={"status": "planned"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_trigger_plan(self, client, auth_headers, sample_task):
        with patch("app.api.v1.tasks._run_agent_background", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/tasks/{sample_task.id}/plan", headers=auth_headers
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["stage"] == "plan"
            assert data["status"] == "running"

    async def test_trigger_work(self, client, auth_headers, sample_task):
        with patch("app.api.v1.tasks._run_agent_background", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/tasks/{sample_task.id}/work", headers=auth_headers
            )
            assert resp.status_code == 201
            assert resp.json()["stage"] == "work"

    async def test_trigger_review(self, client, auth_headers, sample_task):
        with patch("app.api.v1.tasks._run_agent_background", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/tasks/{sample_task.id}/review", headers=auth_headers
            )
            assert resp.status_code == 201
            assert resp.json()["stage"] == "review"

    async def test_trigger_plan_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/tasks/{fake_id}/plan", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_trigger_conflict(self, client, auth_headers, sample_task, sample_run):
        resp = await client.post(
            f"/api/v1/tasks/{sample_task.id}/plan", headers=auth_headers
        )
        assert resp.status_code == 409

    async def test_stop_task_no_active_run(self, client, auth_headers, sample_task):
        resp = await client.post(
            f"/api/v1/tasks/{sample_task.id}/stop", headers=auth_headers
        )
        assert resp.status_code == 409

    async def test_stop_task_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/tasks/{fake_id}/stop", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_stop_task_success(self, client, auth_headers, sample_task, sample_run):
        with patch("app.api.v1.tasks.stop_run", return_value=True):
            resp = await client.post(
                f"/api/v1/tasks/{sample_task.id}/stop", headers=auth_headers
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(sample_run.id)
            assert data["status"] == "running"

    async def test_stop_task_process_not_in_registry(self, client, auth_headers, sample_task, sample_run):
        """Active run in DB but process not in registry (e.g. container restart) — should mark as failed."""
        from app.models import RunStatus, TaskStatus, Task

        with patch("app.api.v1.tasks.stop_run", return_value=False):
            resp = await client.post(
                f"/api/v1/tasks/{sample_task.id}/stop", headers=auth_headers
            )
            assert resp.status_code == 200

        # Run and task should be marked as failed
        run = await AgentRun.get(id=sample_run.id)
        assert run.status == RunStatus.FAILED
        task = await Task.get(id=sample_task.id)
        assert task.status == TaskStatus.FAILED


class TestDashboardEndpoints:
    async def test_stats_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0
        assert data["active_runs"] == 0
        assert data["tasks_by_status"]["backlog"] == 0

    async def test_stats_with_data(self, client, auth_headers, sample_task, sample_run):
        # Update run with cost
        await AgentRun.filter(id=sample_run.id).update(cost_usd=Decimal("0.50"))
        resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0.5
        assert data["active_runs"] == 1
        assert data["tasks_by_status"]["backlog"] == 1

    async def test_costs_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/dashboard/costs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_costs_with_data(self, client, auth_headers, sample_task, sample_run):
        await AgentRun.filter(id=sample_run.id).update(cost_usd=Decimal("1.50"))
        resp = await client.get("/api/v1/dashboard/costs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["task_title"] == "Test task"
        assert data[0]["total_cost_usd"] == 1.5


class TestWebhookEndpoint:
    async def test_webhook(self, client):
        resp = await client.post(
            "/api/v1/webhooks/test-integration",
            json={"event": "test"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestIntegrationsEndpoint:
    async def test_list_integrations(self, client, auth_headers):
        resp = await client.get("/api/v1/integrations", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_health_check(self, client, auth_headers):
        resp = await client.get("/api/v1/integrations/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for entry in data:
            assert "name" in entry
            assert "configured" in entry
            assert "healthy" in entry
            assert "error" in entry

    async def test_health_check_with_mock(self, client, auth_headers):
        from app.integrations.base import BaseIntegration
        from app.integrations.registry import IntegrationRegistry

        class HealthyIntegration(BaseIntegration):
            name = "test-healthy"
            description = "Test healthy integration"
            required_env_vars = []

            async def health_check(self) -> bool:
                return True

        class UnhealthyIntegration(BaseIntegration):
            name = "test-unhealthy"
            description = "Test unhealthy integration"
            required_env_vars = []

            async def health_check(self) -> bool:
                return False

        original = IntegrationRegistry._integrations
        try:
            IntegrationRegistry._integrations = [
                HealthyIntegration(),
                UnhealthyIntegration(),
            ]
            resp = await client.get("/api/v1/integrations/health", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["healthy"] is True
            assert data[0]["error"] is None
            assert data[1]["healthy"] is False
            assert data[1]["error"] == "Health check returned unhealthy"
        finally:
            IntegrationRegistry._integrations = original

    async def test_health_check_exception(self, client, auth_headers):
        from app.integrations.base import BaseIntegration
        from app.integrations.registry import IntegrationRegistry

        class ErrorIntegration(BaseIntegration):
            name = "test-error"
            description = "Test error integration"
            required_env_vars = []

            async def health_check(self) -> bool:
                raise ConnectionError("Cannot connect")

        original = IntegrationRegistry._integrations
        try:
            IntegrationRegistry._integrations = [ErrorIntegration()]
            resp = await client.get("/api/v1/integrations/health", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["healthy"] is False
            assert "Cannot connect" in data[0]["error"]
        finally:
            IntegrationRegistry._integrations = original

    async def test_health_check_unconfigured(self, client, auth_headers):
        from app.integrations.base import BaseIntegration
        from app.integrations.registry import IntegrationRegistry

        class UnconfiguredIntegration(BaseIntegration):
            name = "test-unconfigured"
            description = "Missing env vars"
            required_env_vars = ["NONEXISTENT_VAR_12345"]

            async def health_check(self) -> bool:
                return True

        original = IntegrationRegistry._integrations
        try:
            IntegrationRegistry._integrations = [UnconfiguredIntegration()]
            resp = await client.get("/api/v1/integrations/health", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["configured"] is False
            assert data[0]["healthy"] is None
        finally:
            IntegrationRegistry._integrations = original

    async def test_health_check_timeout(self, client, auth_headers):
        import asyncio

        from app.integrations.base import BaseIntegration
        from app.integrations.registry import IntegrationRegistry

        class SlowIntegration(BaseIntegration):
            name = "test-slow"
            description = "Slow integration"
            required_env_vars = []

            async def health_check(self) -> bool:
                await asyncio.sleep(20)
                return True

        original = IntegrationRegistry._integrations
        try:
            IntegrationRegistry._integrations = [SlowIntegration()]
            # Patch the timeout to 0.1s so test doesn't take 10s
            with patch("app.api.v1.asyncio.wait_for", side_effect=asyncio.TimeoutError):
                resp = await client.get("/api/v1/integrations/health", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data[0]["healthy"] is False
            assert "timed out" in data[0]["error"]
        finally:
            IntegrationRegistry._integrations = original


class TestIntegrationRegistry:
    def test_initialize_and_get_status(self):
        from app.integrations.registry import IntegrationRegistry

        original_integrations = IntegrationRegistry._integrations
        original_active = IntegrationRegistry._active
        try:
            IntegrationRegistry._integrations = []
            IntegrationRegistry._active = []
            IntegrationRegistry.initialize()
            status = IntegrationRegistry.get_status()
            assert isinstance(status, list)
            assert len(status) > 0
            for entry in status:
                assert "name" in entry
                assert "active" in entry
        finally:
            IntegrationRegistry._integrations = original_integrations
            IntegrationRegistry._active = original_active

    def test_get_all_and_get_active(self):
        from app.integrations.registry import IntegrationRegistry

        original_integrations = IntegrationRegistry._integrations
        original_active = IntegrationRegistry._active
        try:
            IntegrationRegistry._integrations = []
            IntegrationRegistry._active = []
            IntegrationRegistry.initialize()
            all_integrations = IntegrationRegistry.get_all()
            active = IntegrationRegistry.get_active()
            assert isinstance(all_integrations, list)
            assert isinstance(active, list)
            assert len(all_integrations) >= len(active)
        finally:
            IntegrationRegistry._integrations = original_integrations
            IntegrationRegistry._active = original_active

    def test_get_by_name(self):
        from app.integrations.base import BaseIntegration
        from app.integrations.registry import IntegrationRegistry

        class FakeIntegration(BaseIntegration):
            name = "fake"
            description = "Fake"
            required_env_vars = []

            async def health_check(self) -> bool:
                return True

        original_integrations = IntegrationRegistry._integrations
        original_active = IntegrationRegistry._active
        try:
            instance = FakeIntegration()
            IntegrationRegistry._integrations = [instance]
            IntegrationRegistry._active = [instance]
            found = IntegrationRegistry.get("fake")
            assert found is instance
            assert IntegrationRegistry.get("nonexistent") is None
        finally:
            IntegrationRegistry._integrations = original_integrations
            IntegrationRegistry._active = original_active

    def test_reset(self):
        from app.integrations.registry import IntegrationRegistry

        original_integrations = IntegrationRegistry._integrations
        original_active = IntegrationRegistry._active
        try:
            IntegrationRegistry.reset()
            assert IntegrationRegistry._integrations == []
            assert IntegrationRegistry._active == []
        finally:
            IntegrationRegistry._integrations = original_integrations
            IntegrationRegistry._active = original_active


class TestSettingsEndpoints:
    async def test_get_setting_not_set(self, client, auth_headers):
        resp = await client.get("/api/v1/settings/base_prompt", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "base_prompt"
        assert data["value"] == ""
        assert data["updated_at"] is None

    async def test_put_setting_create(self, client, auth_headers):
        resp = await client.put(
            "/api/v1/settings/base_prompt",
            json={"value": "You are a senior engineer."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "base_prompt"
        assert data["value"] == "You are a senior engineer."
        assert data["updated_at"] is not None

    async def test_put_setting_update(self, client, auth_headers):
        await client.put(
            "/api/v1/settings/base_prompt",
            json={"value": "old value"},
            headers=auth_headers,
        )
        resp = await client.put(
            "/api/v1/settings/base_prompt",
            json={"value": "new value"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "new value"

    async def test_get_setting_after_put(self, client, auth_headers):
        await client.put(
            "/api/v1/settings/base_prompt",
            json={"value": "test prompt"},
            headers=auth_headers,
        )
        resp = await client.get("/api/v1/settings/base_prompt", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["value"] == "test prompt"

    async def test_settings_require_auth(self, client):
        resp = await client.get("/api/v1/settings/base_prompt")
        assert resp.status_code in (401, 403)


class TestChatEndpoint:
    async def test_list_messages_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/chat/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["messages"] == []
        assert data["offset"] == 0
        assert data["limit"] == 50

    async def test_list_messages(self, client, auth_headers, sample_chat_message):
        resp = await client.get("/api/v1/chat/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["messages"]) == 1
        msg = data["messages"][0]
        assert msg["channel_id"] == "C123456"
        assert msg["user_name"] == "Jane Doe"
        assert msg["message"] == "Hello from Slack!"

    async def test_list_messages_pagination(self, client, auth_headers):
        for i in range(5):
            await ChatMessage.create(
                id=uuid.uuid4(),
                channel_id="C1",
                user_id="U1",
                message=f"Message {i}",
                slack_ts=f"1.{i}",
            )
        resp = await client.get(
            "/api/v1/chat/messages?limit=2&offset=0", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["messages"]) == 2

    async def test_list_messages_channel_filter(self, client, auth_headers):
        await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id="C_ALPHA",
            user_id="U1",
            message="Alpha msg",
            slack_ts="1.1",
        )
        await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id="C_BETA",
            user_id="U1",
            message="Beta msg",
            slack_ts="1.2",
        )
        resp = await client.get(
            "/api/v1/chat/messages?channel_id=C_ALPHA", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["messages"][0]["channel_id"] == "C_ALPHA"


class TestRepositoriesEndpoints:
    async def test_list_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/repositories", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_after_create(self, client, auth_headers):
        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/repo-1",
            name="repo-1",
            description="First repo",
        )
        resp = await client.get("/api/v1/repositories", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "org/repo-1"
        assert data[0]["enabled"] is False

    async def test_sync_without_github(self, client, auth_headers):
        """Sync should 503 when GitHub is not configured."""
        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            return_value=None,
        ):
            resp = await client.post("/api/v1/repositories/sync", headers=auth_headers)
            assert resp.status_code == 503

    async def test_sync_with_mock(self, client, auth_headers):
        from app.integrations.github.client import GitHubIntegration

        mock_github = MagicMock(spec=GitHubIntegration)
        mock_github.list_org_repos.return_value = [
            {
                "full_name": "org/repo-a",
                "name": "repo-a",
                "description": "Repo A",
                "private": False,
                "default_branch": "main",
                "github_url": "https://github.com/org/repo-a",
            },
            {
                "full_name": "org/repo-b",
                "name": "repo-b",
                "description": "Repo B",
                "private": True,
                "default_branch": "develop",
                "github_url": "https://github.com/org/repo-b",
            },
        ]

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            return_value=mock_github,
        ):
            resp = await client.post("/api/v1/repositories/sync", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["created"] == 2
            assert data["updated"] == 0
            assert data["total"] == 2

        # Verify repos in DB
        repos = await Repository.all()
        assert len(repos) == 2

    async def test_sync_updates_existing(self, client, auth_headers):
        """Second sync should update, not duplicate."""
        from app.integrations.github.client import GitHubIntegration

        await Repository.create(
            id=uuid.uuid4(),
            full_name="org/existing",
            name="existing",
            description="Old description",
        )

        mock_github = MagicMock(spec=GitHubIntegration)
        mock_github.list_org_repos.return_value = [
            {
                "full_name": "org/existing",
                "name": "existing",
                "description": "New description",
                "private": False,
                "default_branch": "main",
                "github_url": "https://github.com/org/existing",
            },
        ]

        with patch(
            "app.integrations.registry.IntegrationRegistry.get",
            return_value=mock_github,
        ):
            resp = await client.post("/api/v1/repositories/sync", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["created"] == 0
            assert data["updated"] == 1

        repo = await Repository.get(full_name="org/existing")
        assert repo.description == "New description"

    async def test_toggle(self, client, auth_headers):
        repo = await Repository.create(
            id=uuid.uuid4(),
            full_name="org/toggle-repo",
            name="toggle-repo",
            enabled=False,
        )
        resp = await client.patch(
            f"/api/v1/repositories/{repo.id}",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

        # Verify DB
        refreshed = await Repository.get(id=repo.id)
        assert refreshed.enabled is True

    async def test_toggle_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/v1/repositories/{fake_id}",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_repositories_require_auth(self, client):
        resp = await client.get("/api/v1/repositories")
        assert resp.status_code in (401, 403)
