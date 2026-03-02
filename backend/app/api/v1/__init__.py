from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

from app.integrations.registry import IntegrationRegistry

from .chat import router as chat_router
from .dashboard import router as dashboard_router
from .datadog import router as datadog_router
from .jira import router as jira_router
from .logs import router as logs_router
from .settings import router as settings_router
from .tasks import router as tasks_router
from .webhooks import router as webhooks_router

__all__ = [
    "chat_router",
    "dashboard_router",
    "datadog_router",
    "integrations_router",
    "jira_router",
    "logs_router",
    "settings_router",
    "tasks_router",
    "webhooks_router",
]

logger = logging.getLogger(__name__)

integrations_router = APIRouter(prefix="/api/v1", tags=["integrations"])


@integrations_router.get("/integrations")
async def list_integrations() -> list[dict]:
    return IntegrationRegistry.get_status()


@integrations_router.get("/integrations/health")
async def check_integration_health() -> list[dict]:
    results = []
    for integration in IntegrationRegistry.get_all():
        entry: dict = {
            "name": integration.name,
            "description": integration.description,
            "configured": integration.is_configured,
            "healthy": None,
            "error": None,
        }
        if not integration.is_configured:
            results.append(entry)
            continue
        try:
            healthy = await asyncio.wait_for(
                integration.health_check(), timeout=10.0
            )
            entry["healthy"] = healthy
            if not healthy:
                entry["error"] = "Health check returned unhealthy"
        except asyncio.TimeoutError:
            entry["healthy"] = False
            entry["error"] = "Health check timed out (10s)"
        except Exception as exc:
            entry["healthy"] = False
            entry["error"] = str(exc)
        results.append(entry)
    return results
