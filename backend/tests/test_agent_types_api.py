from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.agent_type import AgentType


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def sample_agent_type():
    return await AgentType.create(
        id=uuid.uuid4(),
        name="default",
        display_name="Default Agent",
        description="Default agent type",
        ecs_task_definition="arn:aws:ecs:us-east-1:123456:task-definition/default:1",
        is_default=True,
    )


@pytest.fixture
async def non_default_agent_type():
    return await AgentType.create(
        id=uuid.uuid4(),
        name="custom",
        display_name="Custom Agent",
        description="Custom agent type",
        ecs_task_definition="arn:aws:ecs:us-east-1:123456:task-definition/custom:1",
        is_default=False,
    )


class TestListAgentTypes:
    async def test_list_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/agent-types", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_types(self, client, auth_headers, sample_agent_type):
        resp = await client.get("/api/v1/agent-types", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "default"
        assert data[0]["display_name"] == "Default Agent"
        assert data[0]["is_default"] is True


class TestCreateAgentType:
    async def test_create(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/agent-types",
            json={
                "name": "test-agent",
                "display_name": "Test Agent",
                "description": "A test agent",
                "ecs_task_definition": "arn:aws:ecs:us-east-1:123456:task-definition/test:1",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-agent"
        assert data["display_name"] == "Test Agent"
        assert data["is_default"] is False

    async def test_create_default_clears_existing(self, client, auth_headers, sample_agent_type):
        resp = await client.post(
            "/api/v1/agent-types",
            json={
                "name": "new-default",
                "display_name": "New Default",
                "ecs_task_definition": "arn:aws:ecs:us-east-1:123456:task-definition/new:1",
                "is_default": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["is_default"] is True

        # Old default should be cleared
        old = await AgentType.get(id=sample_agent_type.id)
        assert old.is_default is False


class TestGetAgentType:
    async def test_get(self, client, auth_headers, sample_agent_type):
        resp = await client.get(
            f"/api/v1/agent-types/{sample_agent_type.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "default"

    async def test_get_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/agent-types/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestUpdateAgentType:
    async def test_update(self, client, auth_headers, sample_agent_type):
        resp = await client.put(
            f"/api/v1/agent-types/{sample_agent_type.id}",
            json={"display_name": "Updated Agent"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Agent"

    async def test_update_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.put(
            f"/api/v1/agent-types/{fake_id}",
            json={"display_name": "Nope"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_update_set_default_clears_existing(
        self, client, auth_headers, sample_agent_type, non_default_agent_type
    ):
        resp = await client.put(
            f"/api/v1/agent-types/{non_default_agent_type.id}",
            json={"is_default": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

        old = await AgentType.get(id=sample_agent_type.id)
        assert old.is_default is False


class TestDeleteAgentType:
    async def test_delete(self, client, auth_headers, non_default_agent_type):
        resp = await client.delete(
            f"/api/v1/agent-types/{non_default_agent_type.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_delete_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(
            f"/api/v1/agent-types/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_delete_default_blocked(self, client, auth_headers, sample_agent_type):
        resp = await client.delete(
            f"/api/v1/agent-types/{sample_agent_type.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "default" in resp.json()["detail"].lower()
