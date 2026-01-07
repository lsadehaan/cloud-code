"""Database models for Cloud Code."""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


# =============================================================================
# Enums
# =============================================================================


class TaskState(enum.Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(enum.Enum):
    """Task priority levels."""

    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class WorkspaceMode(enum.Enum):
    """Workspace isolation modes."""

    SHARED = "shared"
    ISOLATED = "isolated"
    COPY_ON_WRITE = "copy_on_write"


class AgentStatus(enum.Enum):
    """Agent container status."""

    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"
    ERROR = "error"


# =============================================================================
# Models
# =============================================================================


class Project(Base):
    """A GitHub/GitLab project being managed."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    # Repository info
    provider: Mapped[str] = mapped_column(String(20))  # "github" | "gitlab"
    owner: Mapped[str] = mapped_column(String(255))
    repo: Mapped[str] = mapped_column(String(255))
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    clone_url: Mapped[str] = mapped_column(String(500))

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=True)
    label_filter: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # e.g., "cloud-code"

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project")


class Task(Base):
    """A task/issue to be worked on by agents."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id")
    )

    # Issue tracking
    issue_number: Mapped[int] = mapped_column(Integer)
    issue_url: Mapped[str] = mapped_column(String(500))
    pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Task details
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(50))  # feature, bugfix, refactor, etc.
    labels: Mapped[dict] = mapped_column(JSON, default=list)
    acceptance_criteria: Mapped[dict] = mapped_column(JSON, default=list)

    # State
    state: Mapped[TaskState] = mapped_column(Enum(TaskState), default=TaskState.PENDING)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), default=TaskPriority.MEDIUM
    )

    # Branch management
    branch_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    base_commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # Cost tracking
    cost_limit: Mapped[float] = mapped_column(Float, default=2.00)
    current_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Human approval
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    # Assignment
    assigned_agent_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    workspace_mode: Mapped[WorkspaceMode] = mapped_column(
        Enum(WorkspaceMode), default=WorkspaceMode.SHARED
    )
    workspace_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Execution
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    executions: Mapped[list["TaskExecution"]] = relationship(
        "TaskExecution", back_populates="task"
    )
    logs: Mapped[list["AgentLog"]] = relationship("AgentLog", back_populates="task")


class AgentWorkstation(Base):
    """A running agent container."""

    __tablename__ = "agent_workstations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    # Container info
    container_id: Mapped[str] = mapped_column(String(100))
    agent_type: Mapped[str] = mapped_column(String(50))  # frontend, backend, etc.
    coding_cli: Mapped[str] = mapped_column(String(50))  # claude-code, aider, etc.
    name: Mapped[str] = mapped_column(String(100))  # e.g., "frontend-1"

    # Container config
    image: Mapped[str] = mapped_column(String(255))
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.STARTING)

    # Resources
    memory_limit: Mapped[str] = mapped_column(String(20), default="2g")
    cpu_limit: Mapped[float] = mapped_column(Float, default=2.0)

    # Current state
    current_task_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    workspace_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Health
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    health_status: Mapped[str] = mapped_column(String(50), default="unknown")

    # Stats
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TaskExecution(Base):
    """A single execution attempt of a task."""

    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"))
    agent_id: Mapped[str] = mapped_column(String(100))
    attempt_number: Mapped[int] = mapped_column(Integer)

    # Execution
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50))  # running, success, failed

    # LLM Usage
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Results
    files_changed: Mapped[dict] = mapped_column(JSON, default=list)
    commits: Mapped[dict] = mapped_column(JSON, default=list)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="executions")


class AgentLog(Base):
    """Structured agent activity logs."""

    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"))
    execution_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    agent_id: Mapped[str] = mapped_column(String(100))

    # Timing
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Context
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Log content
    level: Mapped[str] = mapped_column(String(20))  # debug, info, warning, error
    category: Mapped[str] = mapped_column(
        String(50)
    )  # tool_input, tool_output, llm_request, etc.
    message: Mapped[str] = mapped_column(Text)

    # Structured data
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Cost attribution
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="logs")


class CredentialRequest(Base):
    """Agent credential requests."""

    __tablename__ = "credential_requests"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"))
    agent_id: Mapped[str] = mapped_column(String(100))

    # Request details
    credential_type: Mapped[str] = mapped_column(String(50))  # npm_token, github_token, etc.
    scope: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, approved, denied, injected

    # Timestamps
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # auto or human ID
