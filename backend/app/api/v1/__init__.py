from __future__ import annotations

from fastapi import APIRouter

from app.integrations.registry import IntegrationRegistry

from .dashboard import router as dashboard_router
from .tasks import router as tasks_router
from .webhooks import router as webhooks_router

integrations_router = APIRouter(prefix="/api/v1", tags=["integrations"])


@integrations_router.get("/integrations")
async def list_integrations() -> list[dict]:
    return IntegrationRegistry.get_status()
