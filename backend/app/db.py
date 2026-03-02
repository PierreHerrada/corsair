from app.config import settings

TORTOISE_ORM = {
    "connections": {
        "default": settings.database_url,
    },
    "apps": {
        "models": {
            "models": [
                "app.models.task",
                "app.models.agent_run",
                "app.models.agent_log",
                "app.models.conversation",
                "app.models.chat_message",
                "app.models.datadog_analysis",
                "app.models.internal_log",
            ],
            "default_connection": "default",
        },
    },
}
