"""GitHub event handlers for Cloud Code.

Processes GitHub events and creates/updates tasks accordingly.
"""

import logging
import re
from typing import Any, Optional

from cloud_code.github.task_creator import create_task_from_issue
from cloud_code.github.comment_parser import parse_cloud_code_command

logger = logging.getLogger(__name__)


# Agent type labels mapping
AGENT_LABELS = {
    "frontend": ["frontend", "ui", "react", "vue", "angular", "css", "html"],
    "backend": ["backend", "api", "server", "database", "python", "node", "go"],
    "devops": ["devops", "ci", "cd", "infrastructure", "docker", "kubernetes"],
    "testing": ["testing", "test", "qa", "e2e", "unit-test"],
    "database": ["database", "db", "sql", "migration", "schema"],
    "reviewer": ["review", "code-review"],
}


def infer_agent_type(labels: list[str], title: str, body: str) -> str:
    """Infer the best agent type from issue labels and content."""
    labels_lower = [l.lower() for l in labels]
    content = f"{title} {body}".lower()

    # Check explicit labels first
    for agent_type, keywords in AGENT_LABELS.items():
        if any(kw in labels_lower for kw in keywords):
            return agent_type

    # Infer from content
    for agent_type, keywords in AGENT_LABELS.items():
        if any(kw in content for kw in keywords):
            return agent_type

    # Default to backend for general tasks
    return "backend"


async def handle_issue_opened(
    issue: dict[str, Any],
    repo_owner: str,
    repo_name: str,
) -> dict:
    """Handle a new issue being opened.

    Creates a task from the issue if it has the cloud-code label
    or if auto-assign is enabled for the repository.
    """
    issue_number = issue.get("number")
    title = issue.get("title", "")
    body = issue.get("body", "")
    labels = [l.get("name", "") for l in issue.get("labels", [])]

    logger.info(f"Issue opened: {repo_owner}/{repo_name}#{issue_number} - {title}")

    # Check if this issue should be processed
    if "cloud-code" not in labels and "auto-code" not in labels:
        logger.info(f"Issue #{issue_number} does not have cloud-code label, skipping")
        return {"status": "skipped", "reason": "no cloud-code label"}

    # Infer agent type
    agent_type = infer_agent_type(labels, title, body)

    # Create task
    task = await create_task_from_issue(
        issue_number=issue_number,
        title=title,
        body=body,
        repo_owner=repo_owner,
        repo_name=repo_name,
        agent_type=agent_type,
        labels=labels,
    )

    return {
        "status": "task_created",
        "task_id": task.id,
        "agent_type": agent_type,
        "issue_number": issue_number,
    }


async def handle_issue_assigned(
    issue: dict[str, Any],
    repo_owner: str,
    repo_name: str,
    assignee: str,
) -> dict:
    """Handle an issue being assigned.

    Can be used to assign to specific agent types:
    - @cloud-code-frontend -> frontend agent
    - @cloud-code-backend -> backend agent
    - etc.
    """
    issue_number = issue.get("number")

    # Check if assigned to a cloud-code bot account
    if not assignee.startswith("cloud-code"):
        return {"status": "ignored", "reason": "not assigned to cloud-code"}

    # Extract agent type from assignee name
    parts = assignee.split("-")
    if len(parts) >= 3:
        agent_type = parts[2]  # cloud-code-frontend -> frontend
    else:
        agent_type = "backend"

    logger.info(f"Issue #{issue_number} assigned to {agent_type} agent")

    # TODO: Update existing task or create new one
    return {
        "status": "assigned",
        "agent_type": agent_type,
        "issue_number": issue_number,
    }


async def handle_issue_comment(
    comment: dict[str, Any],
    issue: dict[str, Any],
    repo_owner: str,
    repo_name: str,
) -> dict:
    """Handle a comment on an issue.

    Processes Cloud Code commands in comments:
    - /cloud-code run -> Start working on the issue
    - /cloud-code cancel -> Cancel current task
    - /cloud-code status -> Report current status
    - /cloud-code handoff <agent> -> Hand off to different agent
    - /cloud-code retry -> Retry failed task
    """
    comment_body = comment.get("body", "")
    comment_author = comment.get("user", {}).get("login", "")
    issue_number = issue.get("number")

    # Parse command from comment
    command = parse_cloud_code_command(comment_body)
    if not command:
        return {"status": "ignored", "reason": "no command found"}

    logger.info(f"Command from {comment_author}: {command}")

    # Process command
    if command["action"] == "run":
        return await _handle_run_command(issue, repo_owner, repo_name, command)
    elif command["action"] == "cancel":
        return await _handle_cancel_command(issue_number, repo_owner, repo_name)
    elif command["action"] == "status":
        return await _handle_status_command(issue_number, repo_owner, repo_name)
    elif command["action"] == "handoff":
        return await _handle_handoff_command(
            issue_number, repo_owner, repo_name, command.get("target_agent")
        )
    elif command["action"] == "retry":
        return await _handle_retry_command(issue_number, repo_owner, repo_name)

    return {"status": "unknown_command", "command": command["action"]}


async def handle_pull_request(
    pr: dict[str, Any],
    repo_owner: str,
    repo_name: str,
    action: str,
) -> dict:
    """Handle pull request events.

    Triggers code review when a PR is opened or updated.
    """
    pr_number = pr.get("number")
    title = pr.get("title", "")

    logger.info(f"PR #{pr_number} {action}: {title}")

    # Check if this PR was created by Cloud Code
    is_cloud_code_pr = "cloud-code" in pr.get("user", {}).get("login", "").lower()

    if is_cloud_code_pr:
        # Do not review our own PRs
        return {"status": "skipped", "reason": "cloud-code pr"}

    # TODO: Create review task
    return {
        "status": "review_requested",
        "pr_number": pr_number,
        "action": action,
    }


# Command handlers

async def _handle_run_command(
    issue: dict,
    repo_owner: str,
    repo_name: str,
    command: dict,
) -> dict:
    """Handle /cloud-code run command."""
    issue_number = issue.get("number")
    title = issue.get("title", "")
    body = issue.get("body", "")
    labels = [l.get("name", "") for l in issue.get("labels", [])]

    # Get agent type from command or infer
    agent_type = command.get("agent_type") or infer_agent_type(labels, title, body)

    task = await create_task_from_issue(
        issue_number=issue_number,
        title=title,
        body=body,
        repo_owner=repo_owner,
        repo_name=repo_name,
        agent_type=agent_type,
        labels=labels,
    )

    return {
        "status": "task_started",
        "task_id": task.id,
        "agent_type": agent_type,
    }


async def _handle_cancel_command(
    issue_number: int,
    repo_owner: str,
    repo_name: str,
) -> dict:
    """Handle /cloud-code cancel command."""
    # TODO: Find and cancel active task for this issue
    return {"status": "cancelled", "issue_number": issue_number}


async def _handle_status_command(
    issue_number: int,
    repo_owner: str,
    repo_name: str,
) -> dict:
    """Handle /cloud-code status command."""
    # TODO: Get status of active task for this issue
    return {"status": "status_requested", "issue_number": issue_number}


async def _handle_handoff_command(
    issue_number: int,
    repo_owner: str,
    repo_name: str,
    target_agent: Optional[str],
) -> dict:
    """Handle /cloud-code handoff command."""
    # TODO: Hand off task to different agent type
    return {
        "status": "handoff_requested",
        "issue_number": issue_number,
        "target_agent": target_agent,
    }


async def _handle_retry_command(
    issue_number: int,
    repo_owner: str,
    repo_name: str,
) -> dict:
    """Handle /cloud-code retry command."""
    # TODO: Retry failed task
    return {"status": "retry_requested", "issue_number": issue_number}
