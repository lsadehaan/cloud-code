"""Task Orchestrator for Cloud Code.

The orchestrator is responsible for:
1. Receiving tasks from GitHub webhooks
2. Setting up workspaces for tasks
3. Dispatching tasks to appropriate agent containers
4. Monitoring task progress via reporting.yaml
5. Updating GitHub with progress/results
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from cloud_code.config import settings
from cloud_code.core.container_manager import (
    ContainerManager,
    AgentInstance,
    AGENT_CONFIGS,
    get_container_manager,
)
from cloud_code.core.workspace import WorkspaceManager, WorkspaceMode
from cloud_code.core.task_interface import (
    TaskInterface,
    TaskDefinition,
    TaskReport,
    ReportingFile,
)

logger = logging.getLogger(__name__)


class TaskOrchestrator:
    """Orchestrates task execution across agent containers."""

    def __init__(
        self,
        container_manager: Optional[ContainerManager] = None,
        workspace_manager: Optional[WorkspaceManager] = None,
    ):
        self.container_manager = container_manager or get_container_manager()
        self.workspace_manager = workspace_manager or WorkspaceManager(
            base_path=settings.workspaces_path
        )

        # Track active tasks
        self._active_tasks: dict[str, dict] = {}
        self._monitoring_task: Optional[asyncio.Task] = None

    async def dispatch_task(
        self,
        task: TaskDefinition,
        repo_owner: str,
        repo_name: str,
        agent_type: str,
        workspace_mode: WorkspaceMode = WorkspaceMode.SHARED,
    ) -> str:
        """Dispatch a task to an agent container.

        Args:
            task: The task definition
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            agent_type: Type of agent to use (frontend, backend, etc.)
            workspace_mode: Workspace isolation mode

        Returns:
            Agent container ID
        """
        logger.info(f"Dispatching task {task.id} to {agent_type} agent")

        # 1. Set up workspace
        workspace_path = await self._setup_workspace(
            task=task,
            repo_owner=repo_owner,
            repo_name=repo_name,
            workspace_mode=workspace_mode,
        )

        # 2. Write task to tasking.yaml
        task_interface = TaskInterface(workspace_path)
        task_interface.write_task(task)

        # 3. Get or create agent container
        agent = await self.container_manager.get_or_create_agent(
            agent_type=agent_type,
            workspace_path=workspace_path,
        )

        # 4. Track task
        self._active_tasks[task.id] = {
            "task": task,
            "agent": agent,
            "workspace_path": workspace_path,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "started_at": datetime.utcnow(),
        }

        logger.info(
            f"Task {task.id} dispatched to container {agent.container_id[:12]}"
        )

        return agent.container_id

    async def _setup_workspace(
        self,
        task: TaskDefinition,
        repo_owner: str,
        repo_name: str,
        workspace_mode: WorkspaceMode,
    ) -> Path:
        """Set up workspace for a task."""
        workspace_path = await asyncio.to_thread(
            self.workspace_manager.get_workspace,
            project_owner=repo_owner,
            project_repo=repo_name,
            task_id=task.id,
            branch=task.branch,
            mode=workspace_mode,
        )

        logger.info(f"Workspace set up at {workspace_path}")
        return workspace_path

    async def get_task_status(self, task_id: str) -> Optional[TaskReport]:
        """Get current status of a task from reporting.yaml."""
        if task_id not in self._active_tasks:
            return None

        task_info = self._active_tasks[task_id]
        workspace_path = task_info["workspace_path"]

        task_interface = TaskInterface(workspace_path)
        return task_interface.get_task_status(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id not in self._active_tasks:
            logger.warning(f"Task {task_id} not found in active tasks")
            return False

        task_info = self._active_tasks[task_id]
        workspace_path = task_info["workspace_path"]

        # Update tasking.yaml to cancel
        task_interface = TaskInterface(workspace_path)
        task_interface.cancel_task(task_id)

        logger.info(f"Task {task_id} cancelled")
        return True

    async def start_monitoring(self, poll_interval: float = 5.0) -> None:
        """Start monitoring active tasks for completion."""
        if self._monitoring_task and not self._monitoring_task.done():
            return

        self._monitoring_task = asyncio.create_task(
            self._monitor_tasks(poll_interval)
        )

    async def stop_monitoring(self) -> None:
        """Stop task monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    async def _monitor_tasks(self, poll_interval: float) -> None:
        """Monitor active tasks and handle completion."""
        while True:
            try:
                await self._check_tasks()
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring tasks: {e}")
                await asyncio.sleep(poll_interval)

    async def _check_tasks(self) -> None:
        """Check status of all active tasks."""
        completed_tasks = []

        for task_id, task_info in self._active_tasks.items():
            workspace_path = task_info["workspace_path"]
            task_interface = TaskInterface(workspace_path)

            report = task_interface.get_task_status(task_id)
            if not report:
                continue

            if report.status in ("completed", "failed", "blocked"):
                completed_tasks.append(task_id)
                await self._handle_task_completion(task_id, task_info, report)

        # Remove completed tasks from tracking
        for task_id in completed_tasks:
            del self._active_tasks[task_id]

    async def _handle_task_completion(
        self,
        task_id: str,
        task_info: dict,
        report: TaskReport,
    ) -> None:
        """Handle a completed/failed/blocked task."""
        logger.info(f"Task {task_id} finished with status: {report.status}")

        if report.status == "completed":
            await self._on_task_completed(task_id, task_info, report)
        elif report.status == "failed":
            await self._on_task_failed(task_id, task_info, report)
        elif report.status == "blocked":
            await self._on_task_blocked(task_id, task_info, report)

    async def _on_task_completed(
        self,
        task_id: str,
        task_info: dict,
        report: TaskReport,
    ) -> None:
        """Handle successful task completion."""
        # TODO: Create PR on GitHub
        # TODO: Post comment with summary
        # TODO: Update database
        logger.info(
            f"Task {task_id} completed successfully. "
            f"Files modified: {len(report.files_modified)}, "
            f"Commits: {len(report.commits)}"
        )

    async def _on_task_failed(
        self,
        task_id: str,
        task_info: dict,
        report: TaskReport,
    ) -> None:
        """Handle task failure."""
        # TODO: Post failure comment on GitHub
        # TODO: Update database
        logger.error(f"Task {task_id} failed: {report.error}")

    async def _on_task_blocked(
        self,
        task_id: str,
        task_info: dict,
        report: TaskReport,
    ) -> None:
        """Handle blocked task (may need handoff)."""
        # TODO: Check if handoff requested
        # TODO: Dispatch to different agent if needed
        # TODO: Post comment requesting human intervention
        logger.warning(f"Task {task_id} blocked: {report.blocked_reason}")

        # Check for handoff request
        if report.blocked_reason and "recommend_handoff:" in report.blocked_reason:
            target_cli = report.blocked_reason.split("recommend_handoff:")[1].strip()
            logger.info(f"Handoff requested to {target_cli}")
            # TODO: Implement handoff logic

    def get_active_tasks(self) -> list[dict]:
        """Get list of all active tasks."""
        return [
            {
                "task_id": task_id,
                "agent_type": info["agent"].agent_type,
                "coding_cli": info["agent"].coding_cli,
                "repo": f"{info['repo_owner']}/{info['repo_name']}",
                "started_at": info["started_at"].isoformat(),
            }
            for task_id, info in self._active_tasks.items()
        ]


# Singleton instance
_orchestrator: Optional[TaskOrchestrator] = None


def get_orchestrator() -> TaskOrchestrator:
    """Get the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TaskOrchestrator()
    return _orchestrator
