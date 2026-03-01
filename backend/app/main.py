import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.api.v1 import dashboard_router, integrations_router, tasks_router, webhooks_router
from app.api.v1.agent import router as agent_router
from app.config import settings
from app.db import TORTOISE_ORM
from app.integrations.registry import IntegrationRegistry

logging.basicConfig(level=logging.INFO)
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
        generate_schemas=settings.environment != "production",
        add_exception_handlers=True,
    )

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Corsair starting up (environment=%s)", settings.environment)
        IntegrationRegistry.initialize()
        for status in IntegrationRegistry.get_status():
            state = "active" if status["active"] else "inactive"
            logger.info("  Integration: %s — %s", status["name"], state)

    # Register routers
    app.include_router(tasks_router)
    app.include_router(dashboard_router)
    app.include_router(webhooks_router)
    app.include_router(integrations_router)
    app.include_router(agent_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
