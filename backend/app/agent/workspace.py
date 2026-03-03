from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def repo_to_subfolder(full_name: str) -> str:
    """Convert 'org/repo-name' to 'org--repo-name' for use as a directory name."""
    return full_name.replace("/", "--")


async def create_workspace(run_id: str) -> Path:
    """Create a workspace directory for an agent run."""
    workspace = Path(settings.workspace_base_dir) / run_id
    workspace.mkdir(parents=True, exist_ok=True)
    logger.info("Created workspace: %s", workspace)

    # Chown to corsair user if running as root
    if os.getuid() == 0:
        try:
            import pwd

            pw = pwd.getpwnam("corsair")
            os.chown(str(workspace), pw.pw_uid, pw.pw_gid)
        except KeyError:
            logger.warning("User 'corsair' not found — skipping chown")

    return workspace


async def clone_repo(
    workspace: Path,
    repo_full_name: str,
    branch: str,
    github_token: str,
    subfolder: Optional[str] = None,
) -> Path:
    """Shallow-clone a GitHub repo into the workspace directory.

    When *subfolder* is given the repo is cloned into ``workspace / subfolder``
    instead of directly into *workspace*.  Returns the target directory.
    """
    target = workspace / subfolder if subfolder else workspace
    clone_url = f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"
    cmd = [
        "git", "clone",
        "--depth", "1",
        "--branch", branch,
        clone_url,
        str(target),
    ]
    # Log without token
    safe_cmd = " ".join(cmd).replace(github_token, "***")
    logger.info("Cloning repo: %s", safe_cmd)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        # Scrub token from error message
        error_msg = error_msg.replace(github_token, "***")
        raise RuntimeError(f"git clone failed (exit {process.returncode}): {error_msg}")

    logger.info("Cloned %s (branch %s) into %s", repo_full_name, branch, target)

    # Recursively chown to corsair user so the agent process can read/write
    if os.getuid() == 0:
        try:
            import pwd

            pw = pwd.getpwnam("corsair")
            for root, dirs, files in os.walk(str(target)):
                os.chown(root, pw.pw_uid, pw.pw_gid)
                for name in files:
                    os.chown(os.path.join(root, name), pw.pw_uid, pw.pw_gid)
        except KeyError:
            logger.warning("User 'corsair' not found — skipping chown")

    return target


async def clone_all_repos(
    workspace: Path,
    repos: list[tuple[str, str]],
    github_token: str,
    task_repo: Optional[str] = None,
) -> dict[str, Optional[Path]]:
    """Clone multiple repos into named subfolders concurrently.

    *repos* is a list of ``(full_name, branch)`` tuples.
    If the *task_repo* clone fails the error is re-raised (run should fail).
    Failures for other repos are logged and skipped.

    Returns ``{full_name: Path | None}`` — ``None`` when a non-critical clone
    was skipped.
    """

    async def _clone_one(full_name: str, branch: str) -> tuple[str, Optional[Path]]:
        subfolder = repo_to_subfolder(full_name)
        try:
            path = await clone_repo(workspace, full_name, branch, github_token, subfolder=subfolder)
            return full_name, path
        except Exception:
            if full_name == task_repo:
                raise
            logger.exception("Failed to clone %s — skipping", full_name)
            return full_name, None

    results = await asyncio.gather(
        *[_clone_one(fn, br) for fn, br in repos],
        return_exceptions=True,
    )

    out: dict[str, Optional[Path]] = {}
    for item in results:
        if isinstance(item, BaseException):
            raise item
        full_name, path = item
        out[full_name] = path
    return out


def write_claude_md(workspace: Path, content: str) -> None:
    """Write a CLAUDE.md file at the workspace root."""
    claude_md_path = workspace / "CLAUDE.md"
    claude_md_path.write_text(content, encoding="utf-8")
    logger.info("Wrote CLAUDE.md (%d chars) to %s", len(content), workspace)


def _sanitize_filename(name: str) -> str:
    """Sanitize a filename by replacing path separators and traversal patterns."""
    return name.replace("/", "-").replace("\\", "-").replace("..", "-")


def write_skill_files(workspace: Path, skills_json: str) -> int:
    """Write skill files to .claude/skills/{name}.md in the workspace.

    Returns the number of files written; 0 on empty/invalid JSON.
    """
    try:
        items = json.loads(skills_json) if skills_json else []
    except (json.JSONDecodeError, TypeError):
        return 0

    if not isinstance(items, list):
        return 0

    skills_dir = workspace / ".claude" / "skills"
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "").strip()
        content = item.get("content", "")
        if not name:
            continue
        safe_name = _sanitize_filename(name)
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / f"{safe_name}.md").write_text(content, encoding="utf-8")
        count += 1

    if count:
        logger.info("Wrote %d skill file(s) to %s", count, skills_dir)
    return count


def write_subagent_files(workspace: Path, subagents_json: str) -> int:
    """Write subagent files to .claude/agents/{name}.md in the workspace.

    Returns the number of files written; 0 on empty/invalid JSON.
    """
    try:
        items = json.loads(subagents_json) if subagents_json else []
    except (json.JSONDecodeError, TypeError):
        return 0

    if not isinstance(items, list):
        return 0

    agents_dir = workspace / ".claude" / "agents"
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "").strip()
        content = item.get("content", "")
        if not name:
            continue
        safe_name = _sanitize_filename(name)
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / f"{safe_name}.md").write_text(content, encoding="utf-8")
        count += 1

    if count:
        logger.info("Wrote %d subagent file(s) to %s", count, agents_dir)
    return count


def write_plan_md(workspace: Path, content: str) -> None:
    """Write a PLAN.md file at the workspace root."""
    plan_path = workspace / "PLAN.md"
    plan_path.write_text(content, encoding="utf-8")
    logger.info("Wrote PLAN.md (%d chars) to %s", len(content), workspace)


def write_lessons_md(workspace: Path, content: str) -> None:
    """Write a LESSONS.md file at the workspace root."""
    lessons_path = workspace / "LESSONS.md"
    lessons_path.write_text(content, encoding="utf-8")
    logger.info("Wrote LESSONS.md (%d chars) to %s", len(content), workspace)


def read_lessons_md(workspace: Path) -> Optional[str]:
    """Read LESSONS.md from the workspace root. Returns None if not found."""
    lessons_path = workspace / "LESSONS.md"
    if lessons_path.exists():
        return lessons_path.read_text(encoding="utf-8")
    return None


def read_pr_url(workspace: Path) -> Optional[str]:
    """Read PR_URL.txt from the workspace root. Returns None if not found."""
    pr_path = workspace / "PR_URL.txt"
    if pr_path.exists():
        content = pr_path.read_text(encoding="utf-8").strip()
        return content if content else None
    return None


def capture_file_tree(workspace: Path, max_entries: int = 5000) -> list[dict]:
    """Walk the workspace and return a flat list of {path, type, size} entries.

    Skips .git/ directories. Paths are relative to the workspace root.
    """
    entries: list[dict] = []
    workspace_str = str(workspace)

    for root, dirs, files in os.walk(workspace_str):
        # Skip .git directories
        dirs[:] = [d for d in dirs if d != ".git"]

        rel_root = os.path.relpath(root, workspace_str)

        # Add directory entry (skip the root "." itself)
        if rel_root != ".":
            entries.append({"path": rel_root, "type": "dir"})
            if len(entries) >= max_entries:
                break

        for fname in sorted(files):
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, workspace_str)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            entries.append({"path": rel_path, "type": "file", "size": size})
            if len(entries) >= max_entries:
                break

        if len(entries) >= max_entries:
            logger.warning("File tree capped at %d entries for %s", max_entries, workspace)
            break

    return entries


def cleanup_workspace(workspace_path: str) -> None:
    """Remove a workspace directory."""
    if os.path.isdir(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=True)
        logger.info("Cleaned up workspace: %s", workspace_path)


async def cleanup_old_workspaces(retention_hours: int = 24) -> int:
    """Remove workspaces for runs older than retention_hours.

    Returns the number of workspaces cleaned up.
    """
    from app.models import AgentRun

    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    old_runs = await AgentRun.filter(
        workspace_path__isnull=False,
        finished_at__lt=cutoff,
    ).all()

    cleaned = 0
    for run in old_runs:
        if run.workspace_path and os.path.isdir(run.workspace_path):
            cleanup_workspace(run.workspace_path)
            cleaned += 1
        await AgentRun.filter(id=run.id).update(workspace_path=None)

    if cleaned:
        logger.info("Cleaned up %d old workspaces (retention=%dh)", cleaned, retention_hours)
    return cleaned
