import uuid

import pytest
from tortoise import Tortoise

from app.auth import create_access_token
from app.models import (
    AgentLog,
    AgentRun,
    ChatMessage,
    Conversation,
    LogType,
    MessageRole,
    RunStage,
    RunStatus,
    Task,
    TaskStatus,
)

DB_URL = "sqlite://:memory:"

MODELS = [
    "app.models.task",
    "app.models.agent_run",
    "app.models.agent_log",
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


@pytest.fixture
def auth_headers():
    token = create_access_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sample_task():
    return await Task.create(
        id=uuid.uuid4(),
        title="Test task",
        description="A test task description",
        acceptance="Should pass all tests",
        status=TaskStatus.BACKLOG,
        slack_channel="C123456",
        slack_thread_ts="1234567890.123456",
        slack_user_id="U123456",
    )


@pytest.fixture
async def sample_run(sample_task):
    return await AgentRun.create(
        id=uuid.uuid4(),
        task=sample_task,
        stage=RunStage.PLAN,
        status=RunStatus.RUNNING,
    )


@pytest.fixture
async def sample_log(sample_run):
    return await AgentLog.create(
        id=uuid.uuid4(),
        run=sample_run,
        type=LogType.TEXT,
        content={"message": "Starting analysis..."},
    )


@pytest.fixture
async def sample_conversation(sample_task):
    return await Conversation.create(
        id=uuid.uuid4(),
        task=sample_task,
        role=MessageRole.USER,
        message="Please implement the feature",
        slack_ts="1234567890.123456",
    )


@pytest.fixture
async def sample_chat_message():
    return await ChatMessage.create(
        id=uuid.uuid4(),
        channel_id="C123456",
        channel_name="general",
        user_id="U789012",
        user_name="Jane Doe",
        message="Hello from Slack!",
        slack_ts="1234567890.111111",
    )
