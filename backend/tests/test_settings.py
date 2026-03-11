from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.setting import Setting


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestEnvVarsEndpoints:
    async def test_get_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/settings/env-vars", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["updated_at"] is None

    async def test_put_and_get(self, client, auth_headers):
        # Create env vars
        resp = await client.put(
            "/api/v1/settings/env-vars",
            json={"items": [{"name": "MY_KEY", "value": "secret123"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "MY_KEY"
        assert data["items"][0]["masked_value"] == "*********"  # len("secret123") = 9
        assert data["updated_at"] is not None

        # Read back
        resp = await client.get("/api/v1/settings/env-vars", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "MY_KEY"
        assert data["items"][0]["masked_value"] == "*********"

    async def test_preserve_masked_value(self, client, auth_headers):
        # First, create a value
        await client.put(
            "/api/v1/settings/env-vars",
            json={"items": [{"name": "MY_KEY", "value": "secret123"}]},
            headers=auth_headers,
        )

        # Now send back with masked value (all asterisks) — should preserve
        resp = await client.put(
            "/api/v1/settings/env-vars",
            json={"items": [{"name": "MY_KEY", "value": "*********"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"][0]["masked_value"] == "*********"

        # Verify the actual stored value is still the original
        setting = await Setting.filter(key="env_vars").first()
        stored = json.loads(setting.value)
        assert stored[0]["value"] == "secret123"

    async def test_update_value(self, client, auth_headers):
        # Create
        await client.put(
            "/api/v1/settings/env-vars",
            json={"items": [{"name": "MY_KEY", "value": "old"}]},
            headers=auth_headers,
        )

        # Update with new value (not all asterisks)
        resp = await client.put(
            "/api/v1/settings/env-vars",
            json={"items": [{"name": "MY_KEY", "value": "new_secret"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"][0]["masked_value"] == "**********"  # len("new_secret")

        setting = await Setting.filter(key="env_vars").first()
        stored = json.loads(setting.value)
        assert stored[0]["value"] == "new_secret"

    async def test_multiple_items(self, client, auth_headers):
        resp = await client.put(
            "/api/v1/settings/env-vars",
            json={
                "items": [
                    {"name": "KEY_A", "value": "val_a"},
                    {"name": "KEY_B", "value": "val_b"},
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "KEY_A"
        assert data["items"][1]["name"] == "KEY_B"

    async def test_empty_name_skipped(self, client, auth_headers):
        resp = await client.put(
            "/api/v1/settings/env-vars",
            json={
                "items": [
                    {"name": "", "value": "ignored"},
                    {"name": "VALID", "value": "kept"},
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "VALID"

    async def test_remove_item(self, client, auth_headers):
        # Create two items
        await client.put(
            "/api/v1/settings/env-vars",
            json={
                "items": [
                    {"name": "KEEP", "value": "a"},
                    {"name": "DROP", "value": "b"},
                ]
            },
            headers=auth_headers,
        )

        # Send only one back
        resp = await client.put(
            "/api/v1/settings/env-vars",
            json={"items": [{"name": "KEEP", "value": "*"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "KEEP"

        setting = await Setting.filter(key="env_vars").first()
        stored = json.loads(setting.value)
        assert len(stored) == 1
        assert stored[0]["value"] == "a"  # preserved because "*" matches existing
