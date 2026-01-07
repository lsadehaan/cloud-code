"""Core modules for Cloud Code.

Contains the fundamental building blocks:
- container_manager: Docker container lifecycle management
- workspace: Git workspace and worktree management
- task_interface: File-based task communication (tasking.yaml/reporting.yaml)
- orchestrator: Task dispatching and monitoring
"""

from cloud_code.core.container_manager import (
    ContainerManager,
    AgentConfig,
    AgentInstance,
    AGENT_CONFIGS,
    get_container_manager,
)
from cloud_code.core.workspace import (
    WorkspaceManager,
    WorkspaceMode,
)
from cloud_code.core.task_interface import (
    TaskInterface,
    TaskDefinition,
    TaskContext,
    TaskingFile,
    ReportingFile,
    TaskReport,
    FileChange,
    CommitRecord,
)
from cloud_code.core.orchestrator import (
    TaskOrchestrator,
    get_orchestrator,
)

__all__ = [
    # Container management
    "ContainerManager",
    "AgentConfig",
    "AgentInstance",
    "AGENT_CONFIGS",
    "get_container_manager",
    # Workspace management
    "WorkspaceManager",
    "WorkspaceMode",
    # Task interface
    "TaskInterface",
    "TaskDefinition",
    "TaskContext",
    "TaskingFile",
    "ReportingFile",
    "TaskReport",
    "FileChange",
    "CommitRecord",
    # Orchestrator
    "TaskOrchestrator",
    "get_orchestrator",
]
