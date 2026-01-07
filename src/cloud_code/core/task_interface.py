"""Task interface for file-based communication between orchestrator and agents.

Uses two files:
- tasking.yaml: Orchestrator writes, Agent reads
- reporting.yaml: Agent writes, Orchestrator reads
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


# =============================================================================
# Tasking File (Orchestrator → Agent)
# =============================================================================


class TaskContext(BaseModel):
    """Context provided with a task."""

    related_files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class TaskDefinition(BaseModel):
    """A task definition in tasking.yaml."""

    id: str
    title: str
    status: str = "assigned"  # assigned | cancelled
    priority: str = "medium"  # critical | high | medium | low
    branch: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    context: TaskContext = Field(default_factory=TaskContext)
    depends_on: list[str] = Field(default_factory=list)
    workspace_mode: str = "shared"  # shared | isolated | copy_on_write


class TaskingFile(BaseModel):
    """The tasking.yaml file structure (Orchestrator writes)."""

    version: int = 1
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    workspace: Optional[str] = None
    tasks: list[TaskDefinition] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "TaskingFile":
        """Load tasking file from disk."""
        if not path.exists():
            return cls()
        content = path.read_text()
        data = yaml.safe_load(content) or {}
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save tasking file to disk (atomic write)."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        self.updated_at = datetime.utcnow()

        # Atomic write via temp file
        tmp_path = path.with_suffix(".tmp")
        content = yaml.dump(
            self.model_dump(mode="json"),
            default_flow_style=False,
            sort_keys=False,
        )
        tmp_path.write_text(content)
        tmp_path.rename(path)

    def add_task(self, task: TaskDefinition) -> None:
        """Add or update a task."""
        # Remove existing task with same ID
        self.tasks = [t for t in self.tasks if t.id != task.id]
        self.tasks.append(task)

    def cancel_task(self, task_id: str) -> None:
        """Mark a task as cancelled."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = "cancelled"
                break


# =============================================================================
# Reporting File (Agent → Orchestrator)
# =============================================================================


class ProgressEntry(BaseModel):
    """A progress log entry."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class FileChange(BaseModel):
    """A file change record."""

    path: str
    change_type: str  # created | modified | deleted
    lines_added: int = 0
    lines_removed: int = 0


class CommitRecord(BaseModel):
    """A commit record."""

    sha: str
    message: str


class AcceptanceCriterionStatus(BaseModel):
    """Status of an acceptance criterion."""

    criterion: str
    status: str  # pending | in_progress | done | blocked


class CredentialRequestRecord(BaseModel):
    """A credential request from the agent."""

    id: str
    type: str  # npm_token, github_token, database_url, etc.
    scope: str
    reason: str
    status: str = "pending"  # pending | approved | denied | injected
    requested_at: datetime = Field(default_factory=datetime.utcnow)


class TaskReport(BaseModel):
    """Report for a single task."""

    status: str = "waiting"  # waiting | received | planning | in_progress | blocked | completed | failed
    started_at: Optional[datetime] = None
    current_step: Optional[str] = None

    # Human-readable summary for GitHub comments
    summary: Optional[str] = None

    # Progress log
    progress: list[ProgressEntry] = Field(default_factory=list)

    # Changes summary for PR description
    changes_summary: list[str] = Field(default_factory=list)

    # File changes
    files_modified: list[FileChange] = Field(default_factory=list)

    # Commits
    commits: list[CommitRecord] = Field(default_factory=list)

    # Acceptance criteria status
    acceptance_criteria: list[AcceptanceCriterionStatus] = Field(default_factory=list)

    # Error info
    error: Optional[str] = None
    blocked_reason: Optional[str] = None

    # Credential requests
    credential_requests: list[CredentialRequestRecord] = Field(default_factory=list)


class ReportingFile(BaseModel):
    """The reporting.yaml file structure (Agent writes)."""

    version: int = 1
    agent_type: str = "unknown"
    agent_id: str = "unknown"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "idle"  # idle | working | error

    tasks: dict[str, TaskReport] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ReportingFile":
        """Load reporting file from disk."""
        if not path.exists():
            return cls()
        content = path.read_text()
        data = yaml.safe_load(content) or {}
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save reporting file to disk (atomic write)."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        self.updated_at = datetime.utcnow()

        # Atomic write via temp file
        tmp_path = path.with_suffix(".tmp")
        content = yaml.dump(
            self.model_dump(mode="json"),
            default_flow_style=False,
            sort_keys=False,
        )
        tmp_path.write_text(content)
        tmp_path.rename(path)

    def get_task_report(self, task_id: str) -> TaskReport:
        """Get or create a task report."""
        if task_id not in self.tasks:
            self.tasks[task_id] = TaskReport()
        return self.tasks[task_id]

    def update_task_status(
        self,
        task_id: str,
        status: str,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Update task status and add progress entry."""
        report = self.get_task_report(task_id)
        report.status = status

        if status == "received" and report.started_at is None:
            report.started_at = datetime.utcnow()

        if message:
            report.current_step = message
            report.progress.append(
                ProgressEntry(
                    status=status,
                    message=message,
                    details=details or {},
                )
            )

    def add_credential_request(
        self,
        task_id: str,
        request_id: str,
        cred_type: str,
        scope: str,
        reason: str,
    ) -> None:
        """Add a credential request."""
        report = self.get_task_report(task_id)
        report.credential_requests.append(
            CredentialRequestRecord(
                id=request_id,
                type=cred_type,
                scope=scope,
                reason=reason,
            )
        )


# =============================================================================
# Task Interface (combines both files)
# =============================================================================


class TaskInterface:
    """Interface for task communication via files.

    Provides a unified interface for both orchestrator (writes tasking, reads reporting)
    and agent (reads tasking, writes reporting).
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.cloud_code_dir = workspace_path / ".cloud-code"
        self.tasking_path = self.cloud_code_dir / "tasking.yaml"
        self.reporting_path = self.cloud_code_dir / "reporting.yaml"

    # -------------------------------------------------------------------------
    # Orchestrator methods (write tasking, read reporting)
    # -------------------------------------------------------------------------

    def write_task(self, task: TaskDefinition) -> None:
        """Write a task to tasking.yaml (orchestrator)."""
        tasking = TaskingFile.load(self.tasking_path)
        tasking.workspace = str(self.workspace_path)
        tasking.add_task(task)
        tasking.save(self.tasking_path)

    def cancel_task(self, task_id: str) -> None:
        """Cancel a task in tasking.yaml (orchestrator)."""
        tasking = TaskingFile.load(self.tasking_path)
        tasking.cancel_task(task_id)
        tasking.save(self.tasking_path)

    def read_report(self) -> ReportingFile:
        """Read reporting.yaml (orchestrator)."""
        return ReportingFile.load(self.reporting_path)

    def get_task_status(self, task_id: str) -> Optional[TaskReport]:
        """Get status of a specific task (orchestrator)."""
        report = self.read_report()
        return report.tasks.get(task_id)

    # -------------------------------------------------------------------------
    # Agent methods (read tasking, write reporting)
    # -------------------------------------------------------------------------

    def read_tasks(self) -> TaskingFile:
        """Read tasking.yaml (agent)."""
        return TaskingFile.load(self.tasking_path)

    def get_pending_tasks(self) -> list[TaskDefinition]:
        """Get all pending/assigned tasks (agent)."""
        tasking = self.read_tasks()
        return [t for t in tasking.tasks if t.status == "assigned"]

    def update_status(
        self,
        task_id: str,
        status: str,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Update task status in reporting.yaml (agent)."""
        report = ReportingFile.load(self.reporting_path)
        report.status = "working" if status == "in_progress" else "idle"
        report.update_task_status(task_id, status, message, details)
        report.save(self.reporting_path)

    def set_task_completed(
        self,
        task_id: str,
        summary: str,
        changes: list[str],
        files: list[FileChange],
        commits: list[CommitRecord],
    ) -> None:
        """Mark task as completed with full details (agent)."""
        report = ReportingFile.load(self.reporting_path)
        report.status = "idle"

        task_report = report.get_task_report(task_id)
        task_report.status = "completed"
        task_report.summary = summary
        task_report.changes_summary = changes
        task_report.files_modified = files
        task_report.commits = commits
        task_report.progress.append(
            ProgressEntry(status="completed", message="Task completed successfully")
        )

        report.save(self.reporting_path)

    def set_task_failed(self, task_id: str, error: str) -> None:
        """Mark task as failed (agent)."""
        report = ReportingFile.load(self.reporting_path)
        report.status = "idle"

        task_report = report.get_task_report(task_id)
        task_report.status = "failed"
        task_report.error = error
        task_report.progress.append(
            ProgressEntry(status="failed", message=f"Task failed: {error}")
        )

        report.save(self.reporting_path)

    def set_task_blocked(self, task_id: str, reason: str) -> None:
        """Mark task as blocked (agent)."""
        report = ReportingFile.load(self.reporting_path)
        report.status = "idle"

        task_report = report.get_task_report(task_id)
        task_report.status = "blocked"
        task_report.blocked_reason = reason
        task_report.progress.append(
            ProgressEntry(status="blocked", message=f"Task blocked: {reason}")
        )

        report.save(self.reporting_path)

    def request_credential(
        self,
        task_id: str,
        cred_type: str,
        scope: str,
        reason: str,
    ) -> str:
        """Request a credential (agent). Returns request ID."""
        from uuid import uuid4

        request_id = f"cred-{uuid4().hex[:8]}"

        report = ReportingFile.load(self.reporting_path)
        report.add_credential_request(task_id, request_id, cred_type, scope, reason)
        report.save(self.reporting_path)

        return request_id

    def initialize_agent(self, agent_type: str, agent_id: str) -> None:
        """Initialize reporting file for an agent."""
        report = ReportingFile(
            agent_type=agent_type,
            agent_id=agent_id,
            status="idle",
        )
        report.save(self.reporting_path)
