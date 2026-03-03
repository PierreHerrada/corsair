import asyncio
import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.api.v1 import (
    chat_router,
    dashboard_router,
    datadog_router,
    integrations_router,
    jira_router,
    logs_router,
    repositories_router,
    settings_router,
    tasks_router,
    webhooks_router,
)
from app.api.v1.agent import router as agent_router
from app.auth import auth_router, get_current_user
from app.config import settings
from app.db import TORTOISE_ORM
from app.integrations.registry import IntegrationRegistry
from app.log_handler import setup_db_logging

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
        setup_db_logging()
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

        # Start hourly workspace cleanup
        async def _workspace_cleanup_loop() -> None:
            from app.agent.workspace import cleanup_old_workspaces

            while True:
                await asyncio.sleep(3600)  # every hour
                try:
                    cleaned = await cleanup_old_workspaces(retention_hours=24)
                    if cleaned:
                        logger.info("Workspace cleanup: removed %d old workspaces", cleaned)
                except Exception:
                    logger.exception("Workspace cleanup failed")

        app.state.workspace_cleanup_task = asyncio.create_task(_workspace_cleanup_loop())
        logger.info("Workspace cleanup task started (hourly, 24h retention)")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("Corsair shutting down — marking active agent runs as failed")

        from app.integrations.jira.sync import stop_sync
        from app.models import AgentRun, RunStatus, Task, TaskStatus

        stop_sync()

        # Cancel workspace cleanup task
        cleanup_task = getattr(app.state, "workspace_cleanup_task", None)
        if cleanup_task:
            cleanup_task.cancel()

        now = datetime.now(timezone.utc)
        running_runs = await AgentRun.filter(status=RunStatus.RUNNING).select_related("task")
        for run in running_runs:
            run.status = RunStatus.FAILED
            run.finished_at = now
            await run.save()
            logger.info("Marked run %s (task %s) as failed", run.id, run.task_id)

            task = run.task
            if task.status in (TaskStatus.WORKING, TaskStatus.REVIEWING):
                task.status = TaskStatus.FAILED
                await task.save()
                logger.info("Marked task %s as failed", task.id)

        logger.info("Shutdown cleanup complete")

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
    app.include_router(jira_router, dependencies=auth_dep)
    app.include_router(logs_router, dependencies=auth_dep)
    app.include_router(settings_router, dependencies=auth_dep)
    app.include_router(repositories_router, dependencies=auth_dep)

    # WebSocket router — auth handled inside the handler
    app.include_router(agent_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
