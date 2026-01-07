"""GitHub integration for Cloud Code.

Handles GitHub webhooks, creates tasks from issues/PRs,
and posts status updates back to GitHub.
"""

from cloud_code.github.webhook import router as webhook_router
from cloud_code.github.task_creator import (
    create_task_from_issue,
    create_review_task,
    TaskManager,
)
from cloud_code.github.comment_parser import (
    parse_cloud_code_command,
    extract_task_context,
)

__all__ = [
    "webhook_router",
    "create_task_from_issue",
    "create_review_task",
    "TaskManager",
    "parse_cloud_code_command",
    "extract_task_context",
]
