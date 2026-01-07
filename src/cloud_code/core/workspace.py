"""Workspace management for Cloud Code.

Handles git cloning, worktrees, and workspace isolation modes.
"""

import asyncio
import shutil
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from cloud_code.config import settings


class WorkspaceMode(str, Enum):
    """Workspace isolation modes."""

    SHARED = "shared"
    ISOLATED = "isolated"
    COPY_ON_WRITE = "copy_on_write"


class WorkspaceInfo(BaseModel):
    """Information about a workspace."""

    path: Path
    mode: WorkspaceMode
    project_owner: str
    project_repo: str
    branch: str
    task_id: str
    is_ready: bool = False


class WorkspaceManager:
    """Manages workspaces for agent tasks.

    Supports three modes:
    - shared: Uses git worktrees, shares .git objects (efficient)
    - isolated: Fresh clone per task (clean environment)
    - copy_on_write: Clone from cache, own copy (exploratory)
    """

    def __init__(self, workspaces_dir: Optional[Path] = None):
        self.workspaces_dir = workspaces_dir or settings.workspaces_path
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    async def get_workspace(
        self,
        project_owner: str,
        project_repo: str,
        task_id: str,
        branch: str,
        base_commit: Optional[str] = None,
        mode: WorkspaceMode = WorkspaceMode.SHARED,
        clone_url: Optional[str] = None,
    ) -> WorkspaceInfo:
        """Get or create a workspace for a task.

        Args:
            project_owner: Repository owner (e.g., "acme")
            project_repo: Repository name (e.g., "app")
            task_id: Unique task identifier
            branch: Branch to work on
            base_commit: Base commit SHA (for rebasing)
            mode: Workspace isolation mode
            clone_url: Git clone URL (with token if needed)

        Returns:
            WorkspaceInfo with path and metadata
        """
        if mode == WorkspaceMode.SHARED:
            return await self._get_shared_workspace(
                project_owner, project_repo, task_id, branch, base_commit, clone_url
            )
        elif mode == WorkspaceMode.ISOLATED:
            return await self._get_isolated_workspace(
                project_owner, project_repo, task_id, branch, clone_url
            )
        else:  # COPY_ON_WRITE
            return await self._get_cow_workspace(
                project_owner, project_repo, task_id, branch, clone_url
            )

    async def _get_shared_workspace(
        self,
        owner: str,
        repo: str,
        task_id: str,
        branch: str,
        base_commit: Optional[str],
        clone_url: Optional[str],
    ) -> WorkspaceInfo:
        """Create workspace using git worktree (shared mode)."""
        main_clone = self.workspaces_dir / f"{owner}-{repo}"
        worktree_dir = self.workspaces_dir / f"{owner}-{repo}.worktrees"
        task_worktree = worktree_dir / f"task-{task_id}"

        # Ensure main clone exists
        if not main_clone.exists():
            await self._clone_repo(clone_url or f"https://github.com/{owner}/{repo}.git", main_clone)
        else:
            await self._fetch_repo(main_clone)

        # Create worktree if doesn't exist
        if not task_worktree.exists():
            worktree_dir.mkdir(parents=True, exist_ok=True)
            await self._create_worktree(
                main_clone, task_worktree, branch, base_commit
            )

        # Create .cloud-code directory
        cloud_code_dir = task_worktree / ".cloud-code"
        cloud_code_dir.mkdir(parents=True, exist_ok=True)

        return WorkspaceInfo(
            path=task_worktree,
            mode=WorkspaceMode.SHARED,
            project_owner=owner,
            project_repo=repo,
            branch=branch,
            task_id=task_id,
            is_ready=True,
        )

    async def _get_isolated_workspace(
        self,
        owner: str,
        repo: str,
        task_id: str,
        branch: str,
        clone_url: Optional[str],
    ) -> WorkspaceInfo:
        """Create isolated workspace (fresh clone)."""
        isolated_dir = self.workspaces_dir / "isolated"
        task_dir = isolated_dir / f"task-{task_id}"

        if task_dir.exists():
            shutil.rmtree(task_dir)

        task_dir.mkdir(parents=True, exist_ok=True)

        # Clone directly into isolated directory
        await self._clone_repo(
            clone_url or f"https://github.com/{owner}/{repo}.git",
            task_dir,
            branch=branch,
        )

        # Create .cloud-code directory
        cloud_code_dir = task_dir / ".cloud-code"
        cloud_code_dir.mkdir(parents=True, exist_ok=True)

        return WorkspaceInfo(
            path=task_dir,
            mode=WorkspaceMode.ISOLATED,
            project_owner=owner,
            project_repo=repo,
            branch=branch,
            task_id=task_id,
            is_ready=True,
        )

    async def _get_cow_workspace(
        self,
        owner: str,
        repo: str,
        task_id: str,
        branch: str,
        clone_url: Optional[str],
    ) -> WorkspaceInfo:
        """Create copy-on-write workspace (clone from cache)."""
        main_clone = self.workspaces_dir / f"{owner}-{repo}"
        cow_dir = self.workspaces_dir / "copy_on_write"
        task_dir = cow_dir / f"task-{task_id}"

        # Ensure main clone exists (as cache)
        if not main_clone.exists():
            await self._clone_repo(clone_url or f"https://github.com/{owner}/{repo}.git", main_clone)
        else:
            await self._fetch_repo(main_clone)

        # Copy the main clone
        if task_dir.exists():
            shutil.rmtree(task_dir)

        cow_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(main_clone, task_dir)

        # Checkout the branch
        await self._run_git(["checkout", "-B", branch], cwd=task_dir)

        # Create .cloud-code directory
        cloud_code_dir = task_dir / ".cloud-code"
        cloud_code_dir.mkdir(parents=True, exist_ok=True)

        return WorkspaceInfo(
            path=task_dir,
            mode=WorkspaceMode.COPY_ON_WRITE,
            project_owner=owner,
            project_repo=repo,
            branch=branch,
            task_id=task_id,
            is_ready=True,
        )

    async def cleanup_workspace(self, task_id: str, mode: WorkspaceMode) -> None:
        """Clean up a workspace after task completion."""
        if mode == WorkspaceMode.SHARED:
            # Remove worktree
            for worktree_dir in self.workspaces_dir.glob("*.worktrees"):
                task_dir = worktree_dir / f"task-{task_id}"
                if task_dir.exists():
                    # First, remove from git worktree list
                    main_clone = self.workspaces_dir / worktree_dir.stem.replace(".worktrees", "")
                    if main_clone.exists():
                        await self._run_git(
                            ["worktree", "remove", "--force", str(task_dir)],
                            cwd=main_clone,
                        )
                    elif task_dir.exists():
                        shutil.rmtree(task_dir)

        elif mode == WorkspaceMode.ISOLATED:
            task_dir = self.workspaces_dir / "isolated" / f"task-{task_id}"
            if task_dir.exists():
                shutil.rmtree(task_dir)

        elif mode == WorkspaceMode.COPY_ON_WRITE:
            task_dir = self.workspaces_dir / "copy_on_write" / f"task-{task_id}"
            if task_dir.exists():
                shutil.rmtree(task_dir)

    async def _clone_repo(
        self, url: str, dest: Path, branch: Optional[str] = None
    ) -> None:
        """Clone a repository."""
        cmd = ["git", "clone"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.extend([url, str(dest)])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode()}")

    async def _fetch_repo(self, repo_dir: Path) -> None:
        """Fetch latest changes from remote."""
        await self._run_git(["fetch", "--all", "--prune"], cwd=repo_dir)

    async def _create_worktree(
        self,
        main_clone: Path,
        worktree_path: Path,
        branch: str,
        base_commit: Optional[str],
    ) -> None:
        """Create a git worktree for the task."""
        # Create new branch from base commit or HEAD
        base = base_commit or "HEAD"
        await self._run_git(
            ["worktree", "add", "-b", branch, str(worktree_path), base],
            cwd=main_clone,
        )

    async def _run_git(self, args: list[str], cwd: Path) -> str:
        """Run a git command."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {stderr.decode()}")

        return stdout.decode()

    def get_cloud_code_dir(self, workspace_path: Path) -> Path:
        """Get the .cloud-code directory for a workspace."""
        cloud_code_dir = workspace_path / ".cloud-code"
        cloud_code_dir.mkdir(parents=True, exist_ok=True)
        return cloud_code_dir
