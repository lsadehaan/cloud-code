"""GitHub webhook handler for Cloud Code.

Handles GitHub webhook events to trigger agent tasks:
- issue.opened → Create task from issue
- issue.assigned → Assign to specific agent type
- issue_comment.created → Process commands in comments
- pull_request.opened → Trigger code review
"""

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Header

from cloud_code.config import settings
from cloud_code.github.events import (
    handle_issue_opened,
    handle_issue_assigned,
    handle_issue_comment,
    handle_pull_request,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/github", tags=["webhooks"])


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not signature.startswith("sha256="):
        return False
    
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """Handle GitHub webhook events."""
    payload = await request.body()
    
    # Verify signature if secret is configured
    if settings.github_webhook_secret:
        if not x_hub_signature_256:
            raise HTTPException(status_code=401, detail="Missing signature")
        
        if not verify_signature(payload, x_hub_signature_256, settings.github_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    logger.info(f"Received GitHub webhook: {x_github_event}")
    
    # Route to appropriate handler
    handlers = {
        "issues": handle_issues_event,
        "issue_comment": handle_issue_comment_event,
        "pull_request": handle_pull_request_event,
        "ping": handle_ping_event,
    }
    
    handler = handlers.get(x_github_event)
    if not handler:
        logger.warning(f"Unhandled GitHub event: {x_github_event}")
        return {"status": "ignored", "event": x_github_event}
    
    result = await handler(data)
    return {"status": "processed", "event": x_github_event, "result": result}


async def handle_issues_event(data: dict[str, Any]) -> dict:
    """Handle issues events (opened, assigned, etc.)."""
    action = data.get("action")
    issue = data.get("issue", {})
    repo = data.get("repository", {})
    
    if action == "opened":
        return await handle_issue_opened(
            issue=issue,
            repo_owner=repo.get("owner", {}).get("login"),
            repo_name=repo.get("name"),
        )
    elif action == "assigned":
        return await handle_issue_assigned(
            issue=issue,
            repo_owner=repo.get("owner", {}).get("login"),
            repo_name=repo.get("name"),
            assignee=data.get("assignee", {}).get("login"),
        )
    
    return {"action": action, "status": "ignored"}


async def handle_issue_comment_event(data: dict[str, Any]) -> dict:
    """Handle issue comment events."""
    action = data.get("action")
    if action != "created":
        return {"action": action, "status": "ignored"}
    
    comment = data.get("comment", {})
    issue = data.get("issue", {})
    repo = data.get("repository", {})
    
    return await handle_issue_comment(
        comment=comment,
        issue=issue,
        repo_owner=repo.get("owner", {}).get("login"),
        repo_name=repo.get("name"),
    )


async def handle_pull_request_event(data: dict[str, Any]) -> dict:
    """Handle pull request events."""
    action = data.get("action")
    pr = data.get("pull_request", {})
    repo = data.get("repository", {})
    
    if action in ("opened", "synchronize", "reopened"):
        return await handle_pull_request(
            pr=pr,
            repo_owner=repo.get("owner", {}).get("login"),
            repo_name=repo.get("name"),
            action=action,
        )
    
    return {"action": action, "status": "ignored"}


async def handle_ping_event(data: dict[str, Any]) -> dict:
    """Handle ping event (webhook setup verification)."""
    return {
        "status": "pong",
        "zen": data.get("zen"),
        "hook_id": data.get("hook_id"),
    }
