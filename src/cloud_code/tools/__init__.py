"""Cloud Code Tool System."""

from pathlib import Path
from typing import Any, Optional

# Tool registry
TOOLS: dict[str, dict] = {}


async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    workspace_path: Optional[Path] = None,
) -> str:
    """
    Execute a tool by name.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Tool parameters
        workspace_path: Optional workspace directory for file/git operations

    Returns:
        Tool result as string
    """
    from cloud_code.tools import files, git, shell, github

    # Tool dispatch
    tool_handlers = {
        # File operations
        "read_file": files.read_file,
        "write_file": files.write_file,
        "list_directory": files.list_directory,
        "search_code": files.search_code,

        # Git operations
        "git_status": git.git_status,
        "git_branch": git.git_branch,
        "git_commit": git.git_commit,
        "git_push": git.git_push,
        "git_diff": git.git_diff,

        # Shell commands
        "run_command": shell.run_command,

        # GitHub operations
        "github_create_pr": github.create_pr,
        "github_comment": github.add_comment,
    }

    if tool_name not in tool_handlers:
        return f"Error: Unknown tool '{tool_name}'"

    handler = tool_handlers[tool_name]

    # Add workspace path if needed
    if workspace_path and "workspace_path" not in tool_input:
        tool_input["workspace_path"] = workspace_path

    return await handler(**tool_input)


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (relative to workspace)",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates or overwrites)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (relative to workspace)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (relative to workspace)",
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List recursively",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "search_code",
        "description": "Search for a pattern in the codebase",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex supported)",
                },
                "file_type": {
                    "type": "string",
                    "description": "File extension filter (e.g., 'py', 'ts')",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "git_status",
        "description": "Get git repository status",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "git_branch",
        "description": "Create or switch git branch",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Branch name",
                },
                "create": {
                    "type": "boolean",
                    "description": "Create new branch",
                    "default": False,
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage all changes and commit",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_push",
        "description": "Push commits to remote",
        "input_schema": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch to push",
                },
                "set_upstream": {
                    "type": "boolean",
                    "description": "Set upstream tracking",
                    "default": True,
                },
            },
            "required": ["branch"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command (allowlisted commands only)",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to run",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 60,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "github_create_pr",
        "description": "Create a GitHub pull request",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "PR title",
                },
                "body": {
                    "type": "string",
                    "description": "PR description",
                },
                "head_branch": {
                    "type": "string",
                    "description": "Source branch",
                },
                "base_branch": {
                    "type": "string",
                    "description": "Target branch",
                    "default": "main",
                },
            },
            "required": ["title", "body", "head_branch"],
        },
    },
    {
        "name": "github_comment",
        "description": "Add a comment to a GitHub issue or PR",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {
                    "type": "integer",
                    "description": "Issue or PR number",
                },
                "body": {
                    "type": "string",
                    "description": "Comment text",
                },
            },
            "required": ["number", "body"],
        },
    },
]
