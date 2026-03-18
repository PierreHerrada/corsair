import pytest
from tortoise import Tortoise

DB_URL = "sqlite://:memory:"

MODELS = [
    "app.models.task",
    "app.models.agent_run",
    "app.models.agent_log",
    "app.models.agent_type",
    "app.models.conversation",
    "app.models.chat_message",
    "app.models.setting",
]


@pytest.fixture(autouse=True)
async def setup_db():
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": MODELS},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise._drop_databases()
    await Tortoise.close_connections()
