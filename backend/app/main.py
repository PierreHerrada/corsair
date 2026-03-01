import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.api.v1 import (
    chat_router,
    dashboard_router,
    datadog_router,
    integrations_router,
    tasks_router,
    webhooks_router,
)
from app.api.v1.agent import router as agent_router
from app.auth import auth_router, get_current_user
from app.config import settings
from app.db import TORTOISE_ORM
from app.integrations.registry import IntegrationRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Corsair", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_tortoise(
        app,
        config=TORTOISE_ORM,
        generate_schemas=True,
        add_exception_handlers=True,
    )

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Corsair starting up (environment=%s)", settings.environment)
        IntegrationRegistry.initialize()
        for status in IntegrationRegistry.get_status():
            state = "active" if status["active"] else "inactive"
            logger.info("  Integration: %s — %s", status["name"], state)

        # Start Slack message listener if configured
        slack = IntegrationRegistry.get("slack")
        if slack is not None:
            try:
                from app.integrations.slack.bot import SlackIntegration

                if isinstance(slack, SlackIntegration):
                    await slack.start_listening()
                    logger.info("Slack message listener started")
            except Exception:
                logger.exception("Failed to start Slack listener")

        # Start Jira ticket sync if configured
        jira = IntegrationRegistry.get("jira")
        if jira is not None:
            try:
                from app.integrations.jira.client import JiraIntegration
                from app.integrations.jira.sync import start_sync

                if isinstance(jira, JiraIntegration):
                    start_sync(jira)
                    logger.info("Jira ticket sync started")
            except Exception:
                logger.exception("Failed to start Jira sync")

    # Public routers (no auth)
    app.include_router(auth_router)
    app.include_router(webhooks_router)

    # Protected routers (require auth)
    auth_dep = [Depends(get_current_user)]
    app.include_router(tasks_router, dependencies=auth_dep)
    app.include_router(dashboard_router, dependencies=auth_dep)
    app.include_router(integrations_router, dependencies=auth_dep)
    app.include_router(chat_router, dependencies=auth_dep)
    app.include_router(datadog_router, dependencies=auth_dep)

    # WebSocket router — auth handled inside the handler
    app.include_router(agent_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
