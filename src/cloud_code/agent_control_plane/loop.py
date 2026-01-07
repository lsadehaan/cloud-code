"""Agent loop - the main control loop running inside each container.

This is the heart of the Agent Control Plane. It:
1. Watches tasking.yaml for new tasks
2. Selects the highest priority pending task
3. Executes it using the configured coding CLI
4. Reports progress/completion to reporting.yaml
5. Loops until no tasks remain, then idles
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from cloud_code.core.task_interface import (
    TaskInterface,
    TaskDefinition,
    FileChange,
    CommitRecord,
    ReportingFile,
)
from cloud_code.agent_control_plane.cli_runner import CLIRunner, CLIResult

logger = logging.getLogger(__name__)


class AgentLoop:
    """Main agent loop running inside a container."""

    def __init__(
        self,
        workspace: Path,
        agent_type: str,
        agent_id: str,
        coding_cli: str = "claude-code",
        idle_poll_interval: float = 10.0,
    ):
        """Initialize the agent loop.

        Args:
            workspace: Path to the workspace directory
            agent_type: Type of agent (frontend, backend, etc.)
            agent_id: Unique identifier for this agent instance
            coding_cli: Which coding CLI to use (claude-code, aider, etc.)
            idle_poll_interval: Seconds to wait between checks when idle
        """
        self.workspace = workspace
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.coding_cli = coding_cli
        self.idle_poll_interval = idle_poll_interval

        self.task_interface = TaskInterface(workspace)
        self.running = False
        self.current_task: Optional[TaskDefinition] = None

    async def run(self) -> None:
        """Main loop - run until stopped."""
        self.running = True
        logger.info(f"Agent {self.agent_id} ({self.agent_type}) starting...")

        # Initialize reporting file
        self.task_interface.initialize_agent(self.agent_type, self.agent_id)

        while self.running:
            try:
                # Read current tasks
                tasking = self.task_interface.read_tasks()
                pending_tasks = [
                    t for t in tasking.tasks
                    if t.status == "assigned"
                ]

                # Check current status of tasks we know about
                reporting = self.task_interface.read_report()

                # Find next task to work on
                task = self._select_next_task(pending_tasks, reporting)

                if task:
                    await self._execute_task(task)
                else:
                    # Idle - wait before checking again
                    await asyncio.sleep(self.idle_poll_interval)

            except Exception as e:
                logger.error(f"Error in agent loop: {e}", exc_info=True)
                await asyncio.sleep(self.idle_poll_interval)

        logger.info(f"Agent {self.agent_id} stopped.")

    def stop(self) -> None:
        """Stop the agent loop."""
        self.running = False

    def _select_next_task(
        self,
        tasks: list[TaskDefinition],
        reporting: ReportingFile,
    ) -> Optional[TaskDefinition]:
        """Select the highest priority task that's ready to work on."""
        # Priority order (lower number = higher priority)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        # Filter to tasks we haven't completed/failed
        eligible = []
        for task in tasks:
            task_report = reporting.tasks.get(task.id)
            if task_report:
                # Skip if already done or failed
                if task_report.status in ("completed", "failed", "blocked"):
                    continue

            # Check dependencies
            if task.depends_on:
                deps_met = all(
                    reporting.tasks.get(dep, {}).status == "completed"
                    for dep in task.depends_on
                )
                if not deps_met:
                    continue

            eligible.append(task)

        if not eligible:
            return None

        # Sort by priority
        eligible.sort(key=lambda t: priority_order.get(t.priority, 2))
        return eligible[0]

    async def _execute_task(self, task: TaskDefinition) -> None:
        """Execute a single task."""
        self.current_task = task
        task_id = task.id

        logger.info(f"Starting task {task_id}: {task.title}")

        try:
            # Update status: received
            self.task_interface.update_status(
                task_id, "received", "Task acknowledged"
            )

            # Update status: planning
            self.task_interface.update_status(
                task_id, "planning", "Analyzing task requirements"
            )

            # Build the prompt for the coding CLI
            prompt = self._build_prompt(task)

            # Update status: in_progress
            self.task_interface.update_status(
                task_id, "in_progress", "Starting implementation"
            )

            # Run the coding CLI
            result = await CLIRunner.run(
                self.coding_cli,
                prompt,
                self.workspace,
            )

            # Handle result
            if result.success:
                await self._handle_success(task, result)
            elif result.needs_handoff:
                await self._handle_handoff(task, result)
            else:
                await self._handle_failure(task, result)

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}", exc_info=True)
            self.task_interface.set_task_failed(task_id, str(e))

        finally:
            self.current_task = None

    def _build_prompt(self, task: TaskDefinition) -> str:
        """Build the prompt for the coding CLI."""
        prompt_parts = [
            f"# Task: {task.title}",
            "",
            "## Description",
            task.description,
            "",
        ]

        if task.acceptance_criteria:
            prompt_parts.extend([
                "## Acceptance Criteria",
                "",
            ])
            for i, criterion in enumerate(task.acceptance_criteria, 1):
                prompt_parts.append(f"{i}. {criterion}")
            prompt_parts.append("")

        if task.context.related_files:
            prompt_parts.extend([
                "## Related Files",
                "You may find these files helpful:",
                "",
            ])
            for f in task.context.related_files:
                prompt_parts.append(f"- {f}")
            prompt_parts.append("")

        prompt_parts.extend([
            "## Instructions",
            "1. Read and understand the existing code",
            "2. Implement the changes described above",
            "3. Ensure all acceptance criteria are met",
            "4. Write or update tests if applicable",
            "5. Do NOT commit changes - just modify the files",
            "",
            f"Branch: {task.branch}",
        ])

        return "\n".join(prompt_parts)

    async def _handle_success(self, task: TaskDefinition, result: CLIResult) -> None:
        """Handle successful task completion."""
        logger.info(f"Task {task.id} completed successfully")

        # Get git status to find changed files
        files_changed = await self._get_changed_files()

        # Generate summary from output
        summary = self._extract_summary(result.output)

        # Create commits (we handle git here)
        commits = await self._commit_changes(task)

        self.task_interface.set_task_completed(
            task.id,
            summary=summary or f"Completed: {task.title}",
            changes=[f"Implemented {task.title}"],
            files=files_changed,
            commits=commits,
        )

    async def _handle_handoff(self, task: TaskDefinition, result: CLIResult) -> None:
        """Handle task that needs handoff to different agent."""
        logger.info(f"Task {task.id} requesting handoff")

        reason = f"recommend_handoff:{self._suggest_alternative_cli()}"
        self.task_interface.set_task_blocked(task.id, reason)

    async def _handle_failure(self, task: TaskDefinition, result: CLIResult) -> None:
        """Handle task failure."""
        logger.error(f"Task {task.id} failed: {result.error}")
        self.task_interface.set_task_failed(task.id, result.error or "Unknown error")

    async def _get_changed_files(self) -> list[FileChange]:
        """Get list of files changed in the workspace."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=self.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            files = []
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue
                status = line[:2].strip()
                path = line[3:].strip()

                change_type = "modified"
                if "A" in status or "?" in status:
                    change_type = "created"
                elif "D" in status:
                    change_type = "deleted"

                files.append(FileChange(
                    path=path,
                    change_type=change_type,
                ))

            return files

        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []

    async def _commit_changes(self, task: TaskDefinition) -> list[CommitRecord]:
        """Commit changes to git."""
        commits = []

        try:
            # Add all changes
            await asyncio.create_subprocess_exec(
                "git", "add", "-A",
                cwd=self.workspace,
            )

            # Commit
            message = f"feat: {task.title}\n\nTask ID: {task.id}\n\n🤖 Generated by Cloud Code"

            proc = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", message,
                cwd=self.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0:
                # Get commit SHA
                proc = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "HEAD",
                    cwd=self.workspace,
                    stdout=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                sha = stdout.decode().strip()

                commits.append(CommitRecord(
                    sha=sha[:7],
                    message=f"feat: {task.title}",
                ))

        except Exception as e:
            logger.error(f"Error committing changes: {e}")

        return commits

    def _extract_summary(self, output: str) -> str:
        """Extract a summary from the CLI output."""
        # Simple heuristic: take the last few meaningful lines
        lines = [l.strip() for l in output.split("\n") if l.strip()]
        if not lines:
            return "Task completed"

        # Look for completion indicators
        for i, line in enumerate(reversed(lines)):
            if any(word in line.lower() for word in ["completed", "done", "finished", "success"]):
                return line[:200]

        # Otherwise return last non-empty line
        return lines[-1][:200] if lines else "Task completed"

    def _suggest_alternative_cli(self) -> str:
        """Suggest an alternative CLI for handoff."""
        if self.coding_cli == "claude-code":
            return "aider"
        elif self.coding_cli == "aider":
            return "claude-code"
        return "claude-code"


async def run_agent(
    workspace: str,
    agent_type: str,
    agent_id: str,
    coding_cli: str = "claude-code",
) -> None:
    """Entry point for running an agent from command line."""
    loop = AgentLoop(
        workspace=Path(workspace),
        agent_type=agent_type,
        agent_id=agent_id,
        coding_cli=coding_cli,
    )
    await loop.run()


if __name__ == "__main__":
    import sys

    # Get config from environment
    workspace = os.environ.get("WORKSPACE", "/workspace")
    agent_type = os.environ.get("AGENT_TYPE", "backend")
    agent_id = os.environ.get("AGENT_ID", f"{agent_type}-1")
    coding_cli = os.environ.get("CODING_CLI", "claude-code")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_agent(workspace, agent_type, agent_id, coding_cli))
