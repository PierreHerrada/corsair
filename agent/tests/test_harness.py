from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path so we can import agent modules
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from config import AgentConfig
from log_streamer import LogStreamer, post_status
from prompt_loader import get_prompt


# --- Config tests ---


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TASK_ID", "abc-123")
    monkeypatch.setenv("AGENT_RUN_ID", "run-456")
    monkeypatch.setenv("STAGE", "plan")
    monkeypatch.setenv("REPO_URL", "https://github.com/org/repo.git")
    monkeypatch.setenv("CALLBACK_URL", "http://control-plane:8000")
    monkeypatch.setenv("INTERNAL_API_SECRET", "secret123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("BRANCH", "develop")
    monkeypatch.setenv("MAX_DURATION_SECONDS", "1800")

    config = AgentConfig()  # type: ignore[call-arg]
    assert config.task_id == "abc-123"
    assert config.agent_run_id == "run-456"
    assert config.stage == "plan"
    assert config.repo_url == "https://github.com/org/repo.git"
    assert config.branch == "develop"
    assert config.max_duration_seconds == 1800


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("TASK_ID", "abc")
    monkeypatch.setenv("AGENT_RUN_ID", "run")
    monkeypatch.setenv("STAGE", "work")
    monkeypatch.setenv("REPO_URL", "https://github.com/org/repo.git")
    monkeypatch.setenv("CALLBACK_URL", "http://control-plane:8000")
    monkeypatch.setenv("INTERNAL_API_SECRET", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    config = AgentConfig()  # type: ignore[call-arg]
    assert config.branch == "main"
    assert config.max_duration_seconds == 3600
    assert config.github_token == ""
    assert config.work_dir == "/home/corsair/workspaces"
    assert config.prompt_override == ""
    assert config.docker_host == ""


# --- LogStreamer tests ---


@pytest.mark.asyncio
async def test_log_streamer_batching():
    streamer = LogStreamer("http://test:8000", "run-1", "secret")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    streamer._client = AsyncMock()
    streamer._client.post = AsyncMock(return_value=mock_resp)

    # Add 5 lines — should NOT flush (under max_batch=10)
    for i in range(5):
        # Reset last flush so time doesn't trigger a flush
        streamer._last_flush = __import__("time").monotonic()
        await streamer.add("text", f"line {i}")

    assert streamer._client.post.call_count == 0

    # Add 5 more — should flush at 10
    for i in range(5, 10):
        streamer._last_flush = __import__("time").monotonic()
        await streamer.add("text", f"line {i}")

    assert streamer._client.post.call_count == 1


@pytest.mark.asyncio
async def test_log_streamer_flush_on_close():
    streamer = LogStreamer("http://test:8000", "run-1", "secret")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    streamer._client = AsyncMock()
    streamer._client.post = AsyncMock(return_value=mock_resp)
    streamer._client.aclose = AsyncMock()

    for i in range(3):
        streamer._last_flush = __import__("time").monotonic()
        await streamer.add("text", f"line {i}")

    assert streamer._client.post.call_count == 0
    await streamer.close()
    assert streamer._client.post.call_count == 1


@pytest.mark.asyncio
async def test_log_streamer_retry_on_failure():
    streamer = LogStreamer("http://test:8000", "run-1", "secret")
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("Connection error")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    streamer._client = AsyncMock()
    streamer._client.post = mock_post

    streamer._buffer = [{"type": "text", "content": "hello", "timestamp": 0}]
    await streamer.flush()
    assert call_count == 3


@pytest.mark.asyncio
async def test_log_streamer_fallback_to_stdout(capsys):
    streamer = LogStreamer("http://test:8000", "run-1", "secret")
    streamer._client = AsyncMock()
    streamer._client.post = AsyncMock(side_effect=Exception("always fail"))

    streamer._buffer = [{"type": "text", "content": "fallback line", "timestamp": 0}]
    await streamer.flush()

    captured = capsys.readouterr()
    assert "fallback line" in captured.out


# --- post_status tests ---


@pytest.mark.asyncio
async def test_post_status_success():
    with patch("log_streamer.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        await post_status(
            "http://test:8000", "run-1", "secret",
            status="completed", exit_code=0,
            token_usage={"input_tokens": 100, "output_tokens": 50},
        )

        mock_instance.post.assert_called_once()
        call_kwargs = mock_instance.post.call_args
        assert "completed" in str(call_kwargs)


@pytest.mark.asyncio
async def test_post_status_retry():
    with patch("log_streamer.httpx.AsyncClient") as MockClient:
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection error")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        mock_instance = AsyncMock()
        mock_instance.post = mock_post
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        await post_status("http://test:8000", "run-1", "secret", status="completed")
        assert call_count == 2


# --- Prompt tests ---


def test_get_prompt_plan():
    prompt = get_prompt("plan", "Fix the login bug")
    assert "Fix the login bug" in prompt
    assert "plan" in prompt.lower() or "analyze" in prompt.lower()


def test_get_prompt_work():
    prompt = get_prompt("work", "Fix the login bug", "Step 1: update auth module")
    assert "Fix the login bug" in prompt
    assert "Step 1: update auth module" in prompt


def test_get_prompt_unknown_stage():
    prompt = get_prompt("unknown_stage", "Some task")
    assert "Some task" in prompt
