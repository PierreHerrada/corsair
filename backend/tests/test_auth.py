from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.auth import ALGORITHM, create_access_token, verify_ws_token
from app.config import settings
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestLoginEndpoint:
    async def test_login_success(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"password": settings.admin_password},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid password"

    async def test_login_missing_password(self, client):
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


class TestProtectedEndpoints:
    async def test_tasks_requires_auth(self, client):
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 403

    async def test_dashboard_requires_auth(self, client):
        resp = await client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 403

    async def test_integrations_requires_auth(self, client):
        resp = await client.get("/api/v1/integrations")
        assert resp.status_code == 403

    async def test_chat_requires_auth(self, client):
        resp = await client.get("/api/v1/chat/messages")
        assert resp.status_code == 403

    async def test_tasks_with_valid_token(self, client, auth_headers):
        resp = await client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200

    async def test_health_no_auth_required(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_webhooks_no_auth_required(self, client):
        resp = await client.post(
            "/api/v1/webhooks/test",
            json={"event": "test"},
        )
        assert resp.status_code == 200

    async def test_invalid_token(self, client):
        resp = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    async def test_expired_token(self, client):
        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, settings.jwt_secret, algorithm=ALGORITHM
        )
        resp = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401


class TestTokenFunctions:
    def test_create_access_token(self):
        token = create_access_token()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin"
        assert "exp" in payload

    def test_verify_ws_token_valid(self):
        token = create_access_token()
        assert verify_ws_token(token) is True

    def test_verify_ws_token_invalid(self):
        assert verify_ws_token("garbage") is False

    def test_verify_ws_token_expired(self):
        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, settings.jwt_secret, algorithm=ALGORITHM
        )
        assert verify_ws_token(expired_token) is False

    def test_verify_ws_token_no_sub(self):
        payload = {"exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
        assert verify_ws_token(token) is False
