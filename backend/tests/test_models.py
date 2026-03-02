import uuid
from decimal import Decimal

import pytest

from app.models import (
    AgentLog,
    AgentRun,
    ChatMessage,
    Conversation,
    LogType,
    MessageRole,
    RunStage,
    RunStatus,
    Setting,
    Task,
    TaskStatus,
)


class TestTask:
    async def test_create_task(self, sample_task):
        assert sample_task.title == "Test task"
        assert sample_task.status == TaskStatus.BACKLOG
        assert sample_task.slack_channel == "C123456"
        assert sample_task.jira_key is None
        assert sample_task.pr_url is None

    async def test_task_defaults(self):
        task = await Task.create(
            id=uuid.uuid4(),
            title="Minimal task",
            slack_channel="C1",
            slack_thread_ts="1.1",
            slack_user_id="U1",
        )
        assert task.description == ""
        assert task.acceptance == ""
        assert task.status == TaskStatus.BACKLOG

    async def test_task_status_enum(self):
        for status in TaskStatus:
            task = await Task.create(
                id=uuid.uuid4(),
                title=f"Task {status}",
                slack_channel="C1",
                slack_thread_ts="1.1",
                slack_user_id="U1",
                status=status,
            )
            assert task.status == status

    async def test_task_update(self, sample_task):
        await Task.filter(id=sample_task.id).update(status=TaskStatus.PLANNED)
        refreshed = await Task.get(id=sample_task.id)
        assert refreshed.status == TaskStatus.PLANNED

    async def test_task_with_jira(self, sample_task):
        await Task.filter(id=sample_task.id).update(
            jira_key="SWE-123", jira_url="https://company.atlassian.net/browse/SWE-123"
        )
        refreshed = await Task.get(id=sample_task.id)
        assert refreshed.jira_key == "SWE-123"
        assert refreshed.jira_url == "https://company.atlassian.net/browse/SWE-123"

    async def test_task_with_pr(self, sample_task):
        await Task.filter(id=sample_task.id).update(
            pr_url="https://github.com/org/repo/pull/42", pr_number=42
        )
        refreshed = await Task.get(id=sample_task.id)
        assert refreshed.pr_url == "https://github.com/org/repo/pull/42"
        assert refreshed.pr_number == 42

    async def test_task_str(self, sample_task):
        assert "Test task" in str(sample_task)
        assert "backlog" in str(sample_task)


class TestAgentRun:
    async def test_create_run(self, sample_run, sample_task):
        assert sample_run.stage == RunStage.PLAN
        assert sample_run.status == RunStatus.RUNNING
        assert sample_run.tokens_in == 0
        assert sample_run.tokens_out == 0
        assert sample_run.cost_usd == Decimal("0")
        assert sample_run.finished_at is None

    async def test_run_stages(self, sample_task):
        for stage in RunStage:
            run = await AgentRun.create(
                id=uuid.uuid4(),
                task=sample_task,
                stage=stage,
            )
            assert run.stage == stage

    async def test_run_update_cost(self, sample_run):
        await AgentRun.filter(id=sample_run.id).update(
            tokens_in=50000,
            tokens_out=10000,
            cost_usd=Decimal("0.300000"),
            status=RunStatus.DONE,
        )
        refreshed = await AgentRun.get(id=sample_run.id)
        assert refreshed.tokens_in == 50000
        assert refreshed.tokens_out == 10000
        assert refreshed.cost_usd == Decimal("0.300000")
        assert refreshed.status == RunStatus.DONE

    async def test_run_foreign_key(self, sample_run, sample_task):
        runs = await AgentRun.filter(task_id=sample_task.id)
        assert len(runs) == 1
        assert runs[0].id == sample_run.id

    async def test_run_str(self, sample_run):
        assert "plan" in str(sample_run)
        assert "running" in str(sample_run)


class TestAgentLog:
    async def test_create_log(self, sample_log, sample_run):
        assert sample_log.type == LogType.TEXT
        assert sample_log.content == {"message": "Starting analysis..."}

    async def test_log_types(self, sample_run):
        for log_type in LogType:
            log = await AgentLog.create(
                id=uuid.uuid4(),
                run=sample_run,
                type=log_type,
                content={"test": True},
            )
            assert log.type == log_type

    async def test_log_jsonb_content(self, sample_run):
        content = {
            "tool": "Read",
            "input": {"file_path": "/src/main.py"},
            "nested": {"deep": {"value": 42}},
        }
        log = await AgentLog.create(
            id=uuid.uuid4(),
            run=sample_run,
            type=LogType.TOOL_USE,
            content=content,
        )
        refreshed = await AgentLog.get(id=log.id)
        assert refreshed.content == content

    async def test_log_foreign_key(self, sample_log, sample_run):
        logs = await AgentLog.filter(run_id=sample_run.id)
        assert len(logs) == 1
        assert logs[0].id == sample_log.id

    async def test_log_str(self, sample_log):
        assert "text" in str(sample_log)


class TestConversation:
    async def test_create_conversation(self, sample_conversation, sample_task):
        assert sample_conversation.role == MessageRole.USER
        assert sample_conversation.message == "Please implement the feature"
        assert sample_conversation.slack_ts == "1234567890.123456"

    async def test_conversation_roles(self, sample_task):
        for role in MessageRole:
            conv = await Conversation.create(
                id=uuid.uuid4(),
                task=sample_task,
                role=role,
                message=f"Message from {role}",
            )
            assert conv.role == role

    async def test_conversation_foreign_key(self, sample_conversation, sample_task):
        convs = await Conversation.filter(task_id=sample_task.id)
        assert len(convs) == 1
        assert convs[0].id == sample_conversation.id

    async def test_conversation_str(self, sample_conversation):
        assert "user" in str(sample_conversation)


class TestChatMessage:
    async def test_create_chat_message(self, sample_chat_message):
        assert sample_chat_message.channel_id == "C123456"
        assert sample_chat_message.channel_name == "general"
        assert sample_chat_message.user_id == "U789012"
        assert sample_chat_message.user_name == "Jane Doe"
        assert sample_chat_message.message == "Hello from Slack!"
        assert sample_chat_message.slack_ts == "1234567890.111111"
        assert sample_chat_message.thread_ts is None
        assert sample_chat_message.task_id is None

    async def test_chat_message_defaults(self):
        msg = await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id="C1",
            user_id="U1",
            message="Test",
            slack_ts="1.1",
        )
        assert msg.channel_name == ""
        assert msg.user_name == ""
        assert msg.thread_ts is None
        assert msg.task_id is None

    async def test_chat_message_with_thread(self):
        msg = await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id="C1",
            user_id="U1",
            message="Thread reply",
            slack_ts="1.2",
            thread_ts="1.1",
        )
        assert msg.thread_ts == "1.1"

    async def test_chat_message_with_task(self, sample_task):
        msg = await ChatMessage.create(
            id=uuid.uuid4(),
            channel_id="C1",
            user_id="U1",
            message="Related to task",
            slack_ts="1.3",
            task=sample_task,
        )
        assert msg.task_id == sample_task.id

    async def test_chat_message_str(self, sample_chat_message):
        assert "Jane Doe" in str(sample_chat_message)
        assert "general" in str(sample_chat_message)


class TestSetting:
    async def test_create_setting(self):
        setting = await Setting.create(
            id=uuid.uuid4(),
            key="base_prompt",
            value="You are a helpful assistant.",
        )
        assert setting.key == "base_prompt"
        assert setting.value == "You are a helpful assistant."
        assert setting.updated_at is not None

    async def test_setting_default_value(self):
        setting = await Setting.create(
            id=uuid.uuid4(),
            key="empty_setting",
        )
        assert setting.value == ""

    async def test_setting_unique_key(self):
        await Setting.create(id=uuid.uuid4(), key="unique_key", value="v1")
        with pytest.raises(Exception):
            await Setting.create(id=uuid.uuid4(), key="unique_key", value="v2")

    async def test_setting_update(self):
        setting = await Setting.create(id=uuid.uuid4(), key="test_key", value="old")
        setting.value = "new"
        await setting.save()
        refreshed = await Setting.get(id=setting.id)
        assert refreshed.value == "new"

    async def test_setting_str(self):
        setting = await Setting.create(id=uuid.uuid4(), key="str_key", value="test_val")
        assert "str_key" in str(setting)
