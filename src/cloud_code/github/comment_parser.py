"""Comment parser for Cloud Code commands.

Parses /cloud-code commands from GitHub issue/PR comments.
"""

import re
from typing import Optional


# Command patterns
COMMAND_PATTERN = re.compile(
    r"^/cloud-code\s+(\w+)(?:\s+(.*))?$",
    re.MULTILINE | re.IGNORECASE
)


def parse_cloud_code_command(comment_body: str) -> Optional[dict]:
    """Parse a Cloud Code command from a comment.

    Supported commands:
    - /cloud-code run [agent_type] - Start working on the issue
    - /cloud-code cancel - Cancel current task
    - /cloud-code status - Report current status
    - /cloud-code handoff <agent_type> - Hand off to different agent
    - /cloud-code retry - Retry failed task
    - /cloud-code approve - Approve pending changes
    - /cloud-code reject [reason] - Reject changes with reason

    Returns:
        dict with action and optional parameters, or None if no command found
    """
    match = COMMAND_PATTERN.search(comment_body)
    if not match:
        return None

    action = match.group(1).lower()
    args = match.group(2).strip() if match.group(2) else ""

    result = {"action": action}

    # Parse action-specific arguments
    if action == "run":
        # /cloud-code run [agent_type]
        if args:
            result["agent_type"] = args.split()[0]

    elif action == "handoff":
        # /cloud-code handoff <agent_type>
        if args:
            result["target_agent"] = args.split()[0]
        else:
            result["target_agent"] = None

    elif action == "reject":
        # /cloud-code reject [reason]
        if args:
            result["reason"] = args

    elif action == "config":
        # /cloud-code config <key> <value>
        parts = args.split(maxsplit=1)
        if len(parts) >= 1:
            result["key"] = parts[0]
        if len(parts) >= 2:
            result["value"] = parts[1]

    return result


def extract_task_context(issue_body: str) -> dict:
    """Extract task context from issue body.

    Looks for special sections in the issue body:
    - ## Context - Additional context for the task
    - ## Acceptance Criteria - List of acceptance criteria
    - ## Related Files - Files that are relevant to the task

    Returns:
        dict with extracted context
    """
    context = {
        "description": "",
        "acceptance_criteria": [],
        "related_files": [],
        "context_notes": "",
    }

    lines = issue_body.split("\n")
    current_section = "description"
    section_content = []

    for line in lines:
        # Check for section headers
        if line.startswith("## "):
            # Save previous section
            _save_section(context, current_section, section_content)
            section_content = []

            # Determine new section
            header = line[3:].strip().lower()
            if "acceptance" in header or "criteria" in header:
                current_section = "acceptance_criteria"
            elif "related" in header or "files" in header:
                current_section = "related_files"
            elif "context" in header:
                current_section = "context_notes"
            else:
                current_section = "description"
        else:
            section_content.append(line)

    # Save last section
    _save_section(context, current_section, section_content)

    return context


def _save_section(context: dict, section: str, lines: list[str]) -> None:
    """Save section content to context dict."""
    content = "\n".join(lines).strip()

    if section == "description":
        context["description"] = content
    elif section == "context_notes":
        context["context_notes"] = content
    elif section == "acceptance_criteria":
        # Parse as list (lines starting with - or *)
        criteria = []
        for line in lines:
            line = line.strip()
            if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                # Remove bullet/number
                criterion = re.sub(r"^[-*]\s*|\d+\.\s*", "", line)
                if criterion:
                    criteria.append(criterion)
        context["acceptance_criteria"] = criteria
    elif section == "related_files":
        # Parse as list of file paths
        files = []
        for line in lines:
            line = line.strip()
            if line.startswith(("-", "*")):
                path = line.lstrip("-* ").strip()
                if path and "/" in path or "." in path:
                    files.append(path)
        context["related_files"] = files
