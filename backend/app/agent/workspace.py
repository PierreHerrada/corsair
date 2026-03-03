from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


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
) -> None:
    """Shallow-clone a GitHub repo into the workspace directory."""
    clone_url = f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"
    cmd = [
        "git", "clone",
        "--depth", "1",
        "--branch", branch,
        clone_url,
        str(workspace),
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

    logger.info("Cloned %s (branch %s) into %s", repo_full_name, branch, workspace)


def write_claude_md(workspace: Path, content: str) -> None:
    """Write a CLAUDE.md file at the workspace root."""
    claude_md_path = workspace / "CLAUDE.md"
    claude_md_path.write_text(content, encoding="utf-8")
    logger.info("Wrote CLAUDE.md (%d chars) to %s", len(content), workspace)


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
