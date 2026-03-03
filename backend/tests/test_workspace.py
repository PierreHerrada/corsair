from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.workspace import (
    capture_file_tree,
    cleanup_old_workspaces,
    cleanup_workspace,
    clone_all_repos,
    clone_repo,
    create_workspace,
    read_lessons_md,
    repo_to_subfolder,
    write_claude_md,
    write_lessons_md,
    write_skill_files,
    write_subagent_files,
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


class TestRepoToSubfolder:
    def test_basic_conversion(self):
        assert repo_to_subfolder("org/repo-name") == "org--repo-name"

    def test_no_slash(self):
        assert repo_to_subfolder("repo-name") == "repo-name"

    def test_multiple_slashes(self):
        assert repo_to_subfolder("a/b/c") == "a--b--c"

    def test_empty_string(self):
        assert repo_to_subfolder("") == ""


class TestCloneRepo:
    async def test_clone_success(self, tmp_path):
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await clone_repo(tmp_path, "org/repo", "main", "ghp_test123")

        call_args = mock_exec.call_args[0]
        assert "git" in call_args
        assert "clone" in call_args
        assert "--depth" in call_args
        assert str(tmp_path) in call_args
        assert result == tmp_path

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

    async def test_clone_with_subfolder(self, tmp_path):
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await clone_repo(
                tmp_path, "org/repo", "main", "ghp_test123", subfolder="org--repo",
            )

        call_args = mock_exec.call_args[0]
        assert str(tmp_path / "org--repo") in call_args
        assert result == tmp_path / "org--repo"

    async def test_clone_chowns_files_when_root(self, tmp_path):
        """After cloning as root, files are recursively chowned to corsair."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        # Create a fake cloned tree to verify os.walk-based chown
        target = tmp_path / "org--repo"
        target.mkdir()
        (target / "subdir").mkdir()
        (target / "subdir" / "file.txt").write_text("hello")

        mock_pw = type("PwEntry", (), {"pw_uid": 1000, "pw_gid": 1000})()

        chowned_paths = []

        original_chown = os.chown

        def tracking_chown(path, uid, gid):
            chowned_paths.append(path)

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("os.getuid", return_value=0),
            patch("os.chown", side_effect=tracking_chown),
            patch.dict("sys.modules", {}),
            patch("pwd.getpwnam", return_value=mock_pw),
        ):
            await clone_repo(
                tmp_path, "org/repo", "main", "ghp_test123", subfolder="org--repo",
            )

        # Should have chowned the directory, subdirectory, and file
        assert len(chowned_paths) >= 3


class TestCloneAllRepos:
    async def test_clones_all_repos(self, tmp_path):
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        repos = [("org/repo-a", "main"), ("org/repo-b", "develop")]

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            results = await clone_all_repos(tmp_path, repos, "ghp_token")

        assert len(results) == 2
        assert results["org/repo-a"] == tmp_path / "org--repo-a"
        assert results["org/repo-b"] == tmp_path / "org--repo-b"

    async def test_partial_failure_skips_non_task_repo(self, tmp_path):
        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            process = AsyncMock()
            # Fail the second clone (org/repo-b)
            if "org--repo-b" in str(args):
                process.communicate = AsyncMock(return_value=(b"", b"fatal: not found"))
                process.returncode = 128
            else:
                process.communicate = AsyncMock(return_value=(b"", b""))
                process.returncode = 0
            return process

        repos = [("org/repo-a", "main"), ("org/repo-b", "develop")]

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            results = await clone_all_repos(
                tmp_path, repos, "ghp_token", task_repo="org/repo-a",
            )

        assert results["org/repo-a"] == tmp_path / "org--repo-a"
        assert results["org/repo-b"] is None

    async def test_task_repo_failure_raises(self, tmp_path):
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"fatal: not found"))
        mock_process.returncode = 128

        repos = [("org/task-repo", "main")]

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError, match="git clone failed"):
                await clone_all_repos(
                    tmp_path, repos, "ghp_token", task_repo="org/task-repo",
                )

    async def test_empty_repos_list(self, tmp_path):
        results = await clone_all_repos(tmp_path, [], "ghp_token")
        assert results == {}


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


class TestWriteSkillFiles:
    def test_writes_skill_files(self, tmp_path):
        import json

        skills = json.dumps([
            {"name": "code-review", "content": "# Code Review\nReview all code."},
            {"name": "testing", "content": "# Testing\nWrite tests."},
        ])
        count = write_skill_files(tmp_path, skills)
        assert count == 2
        assert (tmp_path / ".claude" / "skills" / "code-review.md").exists()
        content = (tmp_path / ".claude" / "skills" / "testing.md").read_text()
        assert content == "# Testing\nWrite tests."

    def test_skips_empty_names(self, tmp_path):
        import json

        skills = json.dumps([
            {"name": "", "content": "empty"},
            {"name": "valid", "content": "ok"},
        ])
        count = write_skill_files(tmp_path, skills)
        assert count == 1

    def test_sanitizes_filenames(self, tmp_path):
        import json

        skills = json.dumps([{"name": "../evil/path", "content": "x"}])
        count = write_skill_files(tmp_path, skills)
        assert count == 1
        assert (tmp_path / ".claude" / "skills" / "--evil-path.md").exists()

    def test_returns_zero_on_invalid_json(self, tmp_path):
        assert write_skill_files(tmp_path, "not json") == 0

    def test_returns_zero_on_empty_string(self, tmp_path):
        assert write_skill_files(tmp_path, "") == 0

    def test_returns_zero_on_non_list_json(self, tmp_path):
        assert write_skill_files(tmp_path, '{"key": "val"}') == 0


class TestWriteSubagentFiles:
    def test_writes_subagent_files(self, tmp_path):
        import json

        subagents = json.dumps([
            {"name": "reviewer", "content": "# Reviewer agent"},
        ])
        count = write_subagent_files(tmp_path, subagents)
        assert count == 1
        assert (tmp_path / ".claude" / "agents" / "reviewer.md").exists()
        assert (tmp_path / ".claude" / "agents" / "reviewer.md").read_text() == "# Reviewer agent"

    def test_returns_zero_on_invalid(self, tmp_path):
        assert write_subagent_files(tmp_path, "bad") == 0
        assert write_subagent_files(tmp_path, "") == 0
        assert write_subagent_files(tmp_path, "42") == 0

    def test_skips_non_dict_items(self, tmp_path):
        import json

        subagents = json.dumps(["string item", {"name": "valid", "content": "ok"}])
        count = write_subagent_files(tmp_path, subagents)
        assert count == 1


class TestWriteLessonsMd:
    def test_writes_file(self, tmp_path):
        write_lessons_md(tmp_path, "# Lessons\nLesson 1.")
        assert (tmp_path / "LESSONS.md").exists()
        assert (tmp_path / "LESSONS.md").read_text() == "# Lessons\nLesson 1."


class TestReadLessonsMd:
    def test_reads_existing_file(self, tmp_path):
        (tmp_path / "LESSONS.md").write_text("content here")
        result = read_lessons_md(tmp_path)
        assert result == "content here"

    def test_returns_none_when_missing(self, tmp_path):
        result = read_lessons_md(tmp_path)
        assert result is None
