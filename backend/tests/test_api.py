from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models import AgentRun, RunStage, RunStatus, Task, TaskStatus


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
    async def test_list_tasks_empty(self, client):
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_tasks(self, client, sample_task):
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test task"
        assert data[0]["status"] == "backlog"

    async def test_get_task(self, client, sample_task):
        resp = await client.get(f"/api/v1/tasks/{sample_task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test task"
        assert data["latest_run"] is None

    async def test_get_task_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/tasks/{fake_id}")
        assert resp.status_code == 404

    async def test_get_task_with_run(self, client, sample_task, sample_run):
        resp = await client.get(f"/api/v1/tasks/{sample_task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_run"] is not None
        assert data["latest_run"]["stage"] == "plan"

    async def test_patch_task_status(self, client, sample_task):
        resp = await client.patch(
            f"/api/v1/tasks/{sample_task.id}",
            json={"status": "planned"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "planned"

    async def test_patch_task_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/v1/tasks/{fake_id}",
            json={"status": "planned"},
        )
        assert resp.status_code == 404

    async def test_trigger_plan(self, client, sample_task):
        with patch("app.api.v1.tasks._run_agent_background", new_callable=AsyncMock):
            resp = await client.post(f"/api/v1/tasks/{sample_task.id}/plan")
            assert resp.status_code == 201
            data = resp.json()
            assert data["stage"] == "plan"
            assert data["status"] == "running"

    async def test_trigger_work(self, client, sample_task):
        with patch("app.api.v1.tasks._run_agent_background", new_callable=AsyncMock):
            resp = await client.post(f"/api/v1/tasks/{sample_task.id}/work")
            assert resp.status_code == 201
            assert resp.json()["stage"] == "work"

    async def test_trigger_review(self, client, sample_task):
        with patch("app.api.v1.tasks._run_agent_background", new_callable=AsyncMock):
            resp = await client.post(f"/api/v1/tasks/{sample_task.id}/review")
            assert resp.status_code == 201
            assert resp.json()["stage"] == "review"

    async def test_trigger_plan_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/api/v1/tasks/{fake_id}/plan")
        assert resp.status_code == 404

    async def test_trigger_conflict(self, client, sample_task, sample_run):
        resp = await client.post(f"/api/v1/tasks/{sample_task.id}/plan")
        assert resp.status_code == 409


class TestDashboardEndpoints:
    async def test_stats_empty(self, client):
        resp = await client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0
        assert data["active_runs"] == 0
        assert data["tasks_by_status"]["backlog"] == 0

    async def test_stats_with_data(self, client, sample_task, sample_run):
        # Update run with cost
        await AgentRun.filter(id=sample_run.id).update(cost_usd=Decimal("0.50"))
        resp = await client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0.5
        assert data["active_runs"] == 1
        assert data["tasks_by_status"]["backlog"] == 1

    async def test_costs_empty(self, client):
        resp = await client.get("/api/v1/dashboard/costs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_costs_with_data(self, client, sample_task, sample_run):
        await AgentRun.filter(id=sample_run.id).update(cost_usd=Decimal("1.50"))
        resp = await client.get("/api/v1/dashboard/costs")
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
    async def test_list_integrations(self, client):
        resp = await client.get("/api/v1/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
