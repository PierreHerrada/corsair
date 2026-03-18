import re

from app.config import settings


def _parse_database_url(url: str) -> dict:
    """Parse a postgres:// URL into a Tortoise connection dict.

    Avoids URL parser issues when the password contains special characters.
    """
    pattern = r"postgres(?:ql)?://(?P<user>[^:]+):(?P<password>.+)@(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<database>.+)"
    m = re.match(pattern, url)
    if not m:
        return url  # type: ignore[return-value]
    return {
        "engine": "tortoise.backends.asyncpg",
        "credentials": {
            "host": m.group("host"),
            "port": int(m.group("port")) if m.group("port") else 5432,
            "user": m.group("user"),
            "password": m.group("password"),
            "database": m.group("database"),
        },
    }


TORTOISE_ORM = {
    "connections": {
        "default": _parse_database_url(settings.database_url),
    },
    "apps": {
        "models": {
            "models": [
                "app.models.task",
                "app.models.agent_run",
                "app.models.agent_log",
                "app.models.agent_type",
                "app.models.conversation",
                "app.models.chat_message",
                "app.models.datadog_analysis",
                "app.models.internal_log",
                "app.models.setting",
                "app.models.setting_history",
                "app.models.repository",
            ],
            "default_connection": "default",
        },
    },
}
