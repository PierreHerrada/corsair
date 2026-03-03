from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.workspace import (
    capture_file_tree,
    cleanup_old_workspaces,
    cleanup_workspace,
    clone_repo,
    create_workspace,
    write_claude_md,
)
from app.models import AgentRun, RunStage, RunStatus


class TestCreateWorkspace:
    async def test_creates_directory(self, tmp_path):
        run_id = str(uuid.uuid4())
        with patch("app.agent.workspace.settings") as mock_settings:
            mock_settings.workspace_base_dir = str(tmp_path)
            workspace = await create_workspace(run_id)
            assert workspace.exists()
            assert workspace.is_dir()
            assert workspace.name == run_id

    async def test_creates_nested_parents(self, tmp_path):
        run_id = str(uuid.uuid4())
        base = tmp_path / "nested" / "dir"
        with patch("app.agent.workspace.settings") as mock_settings:
            mock_settings.workspace_base_dir = str(base)
            workspace = await create_workspace(run_id)
            assert workspace.exists()


class TestCloneRepo:
    async def test_clone_success(self, tmp_path):
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await clone_repo(tmp_path, "org/repo", "main", "ghp_test123")

        call_args = mock_exec.call_args[0]
        assert "git" in call_args
        assert "clone" in call_args
        assert "--depth" in call_args
        assert str(tmp_path) in call_args

    async def test_clone_failure_raises(self, tmp_path):
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"fatal: repo not found"))
        mock_process.returncode = 128

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError, match="git clone failed"):
                await clone_repo(tmp_path, "org/nonexistent", "main", "ghp_test123")

    async def test_clone_scrubs_token_from_error(self, tmp_path):
        token = "ghp_secret123"
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", f"fatal: could not access {token}".encode())
        )
        mock_process.returncode = 128

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError) as exc_info:
                await clone_repo(tmp_path, "org/repo", "main", token)
            assert token not in str(exc_info.value)
            assert "***" in str(exc_info.value)


class TestWriteClaudeMd:
    def test_writes_file(self, tmp_path):
        content = "# Instructions\nAlways write tests."
        write_claude_md(tmp_path, content)
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        assert claude_md.read_text() == content


class TestCaptureFileTree:
    def test_captures_files_and_dirs(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Readme")

        tree = capture_file_tree(tmp_path)
        paths = {e["path"] for e in tree}
        assert "src" in paths
        assert os.path.join("src", "main.py") in paths
        assert "README.md" in paths

    def test_skips_git_directory(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("...")
        (tmp_path / "app.py").write_text("print('hi')")

        tree = capture_file_tree(tmp_path)
        paths = {e["path"] for e in tree}
        assert ".git" not in paths
        assert os.path.join(".git", "config") not in paths
        assert "app.py" in paths

    def test_includes_file_sizes(self, tmp_path):
        (tmp_path / "data.txt").write_text("12345")
        tree = capture_file_tree(tmp_path)
        file_entry = next(e for e in tree if e["path"] == "data.txt")
        assert file_entry["size"] == 5

    def test_respects_max_entries(self, tmp_path):
        for i in range(20):
            (tmp_path / f"file_{i}.txt").write_text(f"content {i}")

        tree = capture_file_tree(tmp_path, max_entries=5)
        assert len(tree) == 5

    def test_empty_directory(self, tmp_path):
        tree = capture_file_tree(tmp_path)
        assert tree == []

    def test_type_field_correct(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file.txt").write_text("hello")

        tree = capture_file_tree(tmp_path)
        dir_entry = next(e for e in tree if e["path"] == "subdir")
        assert dir_entry["type"] == "dir"
        file_entry = next(e for e in tree if e["path"] == os.path.join("subdir", "file.txt"))
        assert file_entry["type"] == "file"


class TestCleanupWorkspace:
    def test_removes_directory(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("hello")

        cleanup_workspace(str(workspace))
        assert not workspace.exists()

    def test_noop_for_nonexistent_dir(self, tmp_path):
        cleanup_workspace(str(tmp_path / "nonexistent"))


class TestCleanupOldWorkspaces:
    async def test_cleans_old_workspaces(self, sample_task, tmp_path):
        run = await AgentRun.create(
            id=uuid.uuid4(),
            task=sample_task,
            stage=RunStage.PLAN,
            status=RunStatus.DONE,
            workspace_path=str(tmp_path / "old_ws"),
            finished_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        # Create the directory
        ws_dir = tmp_path / "old_ws"
        ws_dir.mkdir()
        (ws_dir / "file.txt").write_text("hello")

        cleaned = await cleanup_old_workspaces(retention_hours=24)
        assert cleaned == 1
        assert not ws_dir.exists()

        # workspace_path should be cleared
        updated_run = await AgentRun.get(id=run.id)
        assert updated_run.workspace_path is None

    async def test_skips_recent_workspaces(self, sample_task, tmp_path):
        await AgentRun.create(
            id=uuid.uuid4(),
            task=sample_task,
            stage=RunStage.PLAN,
            status=RunStatus.DONE,
            workspace_path=str(tmp_path / "recent_ws"),
            finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        ws_dir = tmp_path / "recent_ws"
        ws_dir.mkdir()

        cleaned = await cleanup_old_workspaces(retention_hours=24)
        assert cleaned == 0
        assert ws_dir.exists()
