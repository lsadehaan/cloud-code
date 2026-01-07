"""Task creator for Cloud Code.

Creates tasks from GitHub issues and manages task lifecycle.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from cloud_code.core.task_interface import (
    TaskDefinition,
    TaskContext,
    TaskInterface,
)
from cloud_code.core.workspace import WorkspaceManager, WorkspaceMode
from cloud_code.github.comment_parser import extract_task_context
from cloud_code.db.models import Task, TaskState, TaskPriority, WorkspaceMode as DBWorkspaceMode

logger = logging.getLogger(__name__)


# Priority mapping from labels
PRIORITY_LABELS = {
    "critical": TaskPriority.CRITICAL,
    "urgent": TaskPriority.CRITICAL,
    "high": TaskPriority.HIGH,
    "high-priority": TaskPriority.HIGH,
    "medium": TaskPriority.MEDIUM,
    "low": TaskPriority.LOW,
    "low-priority": TaskPriority.LOW,
}


def _get_priority_from_labels(labels: list[str]) -> TaskPriority:
    """Determine task priority from GitHub labels."""
    labels_lower = [l.lower() for l in labels]
    for label, priority in PRIORITY_LABELS.items():
        if label in labels_lower:
            return priority
    return TaskPriority.MEDIUM


async def create_task_from_issue(
    issue_number: int,
    title: str,
    body: str,
    repo_owner: str,
    repo_name: str,
    agent_type: str,
    labels: list[str],
) -> TaskDefinition:
    """Create a task from a GitHub issue.

    Args:
        issue_number: GitHub issue number
        title: Issue title
        body: Issue body (description)
        repo_owner: Repository owner (org or user)
        repo_name: Repository name
        agent_type: Type of agent to assign (frontend, backend, etc.)
        labels: GitHub labels on the issue

    Returns:
        TaskDefinition ready to be written to tasking.yaml
    """
    # Generate unique task ID
    task_id = f"issue-{issue_number}-{uuid4().hex[:8]}"

    # Parse context from issue body
    context_data = extract_task_context(body)

    # Determine priority
    priority = _get_priority_from_labels(labels)

    # Create branch name
    branch_name = f"cloud-code/issue-{issue_number}"

    # Build task context
    task_context = TaskContext(
        related_files=context_data.get("related_files", []),
        dependencies=[],
    )

    # Build description
    description = context_data.get("description") or body
    if context_data.get("context_notes"):
        description += f"\n\n## Additional Context\n{context_data['context_notes']}"

    # Create task definition
    task = TaskDefinition(
        id=task_id,
        title=title,
        status="assigned",
        priority=priority.value,
        branch=branch_name,
        description=description,
        acceptance_criteria=context_data.get("acceptance_criteria", []),
        context=task_context,
        depends_on=[],
        workspace_mode="shared",  # Default to shared for efficiency
    )

    logger.info(f"Created task {task_id} from issue #{issue_number}")

    # TODO: Persist to database
    # TODO: Write to workspace tasking.yaml
    # TODO: Dispatch to agent via ContainerManager

    return task


async def create_review_task(
    pr_number: int,
    title: str,
    body: str,
    repo_owner: str,
    repo_name: str,
    base_branch: str,
    head_branch: str,
) -> TaskDefinition:
    """Create a code review task from a pull request.

    Args:
        pr_number: GitHub PR number
        title: PR title
        body: PR description
        repo_owner: Repository owner
        repo_name: Repository name
        base_branch: Base branch (e.g., main)
        head_branch: Head branch (feature branch)

    Returns:
        TaskDefinition for code review
    """
    task_id = f"pr-review-{pr_number}-{uuid4().hex[:8]}"

    task = TaskDefinition(
        id=task_id,
        title=f"Review: {title}",
        status="assigned",
        priority="medium",
        branch=head_branch,
        description=f"""## Code Review Request

Review the changes in PR #{pr_number}.

### PR Description
{body or 'No description provided.'}

### Review Checklist
- Code quality and readability
- Test coverage
- Security considerations
- Performance implications
- Documentation updates needed
""",
        acceptance_criteria=[
            "Review all changed files",
            "Check for potential bugs or issues",
            "Verify test coverage",
            "Provide constructive feedback",
        ],
        context=TaskContext(related_files=[], dependencies=[]),
        depends_on=[],
        workspace_mode="shared",
    )

    logger.info(f"Created review task {task_id} for PR #{pr_number}")

    return task


class TaskManager:
    """Manages task lifecycle for Cloud Code."""

    def __init__(self, workspace_manager: WorkspaceManager):
        self.workspace_manager = workspace_manager
        self._task_interfaces: dict[str, TaskInterface] = {}

    def get_task_interface(
        self,
        repo_owner: str,
        repo_name: str,
        task_id: str,
    ) -> TaskInterface:
        """Get or create TaskInterface for a task workspace."""
        key = f"{repo_owner}/{repo_name}/{task_id}"

        if key not in self._task_interfaces:
            # Get workspace path
            workspace_path = self.workspace_manager.get_workspace(
                project_owner=repo_owner,
                project_repo=repo_name,
                task_id=task_id,
                branch=f"cloud-code/{task_id}",
                mode=WorkspaceMode.SHARED,
            )
            self._task_interfaces[key] = TaskInterface(workspace_path)

        return self._task_interfaces[key]

    async def dispatch_task(
        self,
        task: TaskDefinition,
        repo_owner: str,
        repo_name: str,
        agent_type: str,
    ) -> None:
        """Dispatch a task to an agent.

        1. Ensure workspace is set up
        2. Write task to tasking.yaml
        3. Start agent container if needed
        """
        # Get task interface
        interface = self.get_task_interface(repo_owner, repo_name, task.id)

        # Write task to tasking.yaml
        interface.write_task(task)

        logger.info(f"Dispatched task {task.id} to {agent_type} agent")

        # TODO: Start agent container via ContainerManager

    async def cancel_task(
        self,
        task_id: str,
        repo_owner: str,
        repo_name: str,
    ) -> None:
        """Cancel a running task."""
        interface = self.get_task_interface(repo_owner, repo_name, task_id)
        interface.cancel_task(task_id)
        logger.info(f"Cancelled task {task_id}")

    async def get_task_status(
        self,
        task_id: str,
        repo_owner: str,
        repo_name: str,
    ) -> Optional[dict]:
        """Get current status of a task from reporting.yaml."""
        interface = self.get_task_interface(repo_owner, repo_name, task_id)
        report = interface.get_task_status(task_id)

        if not report:
            return None

        return {
            "task_id": task_id,
            "status": report.status,
            "current_step": report.current_step,
            "summary": report.summary,
            "error": report.error,
            "blocked_reason": report.blocked_reason,
            "files_modified": [f.path for f in report.files_modified],
            "commits": [c.sha for c in report.commits],
        }
