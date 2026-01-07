"""Base Agent class for Cloud Code."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from anthropic import Anthropic
from pydantic import BaseModel

from cloud_code.config import settings


class AgentSession(BaseModel):
    """Tracks an agent execution session."""

    id: UUID
    agent_type: str
    task_id: Optional[UUID] = None
    project_id: UUID

    state: str = "running"
    started_at: datetime
    ended_at: Optional[datetime] = None

    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    output: Optional[dict] = None
    error: Optional[str] = None


class AgentLog(BaseModel):
    """Single log entry from agent execution."""

    id: UUID
    session_id: UUID
    timestamp: datetime

    level: str  # debug, info, warning, error
    message: str
    data: Optional[dict] = None

    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all Cloud Code agents.

    Provides common functionality for:
    - LLM API calls with logging
    - Tool execution
    - Workspace management
    - Session tracking
    """

    def __init__(
        self,
        project_id: UUID,
        task_id: Optional[UUID] = None,
        model: str = settings.default_model,
    ):
        self.project_id = project_id
        self.task_id = task_id
        self.model = model

        # Initialize Anthropic client
        self.client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

        # Session tracking
        self.session: Optional[AgentSession] = None
        self.logs: list[AgentLog] = []

        # Workspace
        self.workspace_path: Optional[Path] = None

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Unique identifier for this agent type (e.g., 'coder', 'reviewer')."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        pass

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """
        Execute the agent's main task.

        Args:
            input_data: Task-specific input data

        Returns:
            Result dictionary with agent output
        """
        pass

    async def start_session(self) -> AgentSession:
        """Initialize a new agent session."""
        self.session = AgentSession(
            id=uuid4(),
            agent_type=self.agent_type,
            task_id=self.task_id,
            project_id=self.project_id,
            started_at=datetime.utcnow(),
            model=self.model,
        )
        await self.log("info", f"Started {self.agent_type} agent session")
        return self.session

    async def end_session(
        self,
        output: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> AgentSession:
        """Complete the agent session."""
        if self.session:
            self.session.ended_at = datetime.utcnow()
            self.session.output = output
            self.session.error = error
            self.session.state = "failed" if error else "completed"

            await self.log(
                "error" if error else "info",
                f"Ended {self.agent_type} session: {self.session.state}",
            )

        return self.session

    async def log(
        self,
        level: str,
        message: str,
        data: Optional[dict] = None,
        tool_name: Optional[str] = None,
        tool_input: Optional[dict] = None,
        tool_output: Optional[str] = None,
    ) -> AgentLog:
        """Add a log entry."""
        log_entry = AgentLog(
            id=uuid4(),
            session_id=self.session.id if self.session else uuid4(),
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            data=data,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
        )
        self.logs.append(log_entry)

        # Also print for development
        print(f"[{self.agent_type}] [{level.upper()}] {message}")

        # TODO: Persist to database
        # TODO: Broadcast via WebSocket for real-time UI

        return log_entry

    async def call_llm(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Make an LLM API call with logging.

        Args:
            messages: Conversation messages
            tools: Available tools for the model
            max_tokens: Maximum tokens in response

        Returns:
            API response dictionary
        """
        await self.log("debug", "Calling LLM", data={"message_count": len(messages)})

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": self.system_prompt,
                "messages": messages,
            }

            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            # Track token usage
            if self.session:
                self.session.input_tokens += response.usage.input_tokens
                self.session.output_tokens += response.usage.output_tokens

            await self.log(
                "debug",
                "LLM response received",
                data={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "stop_reason": response.stop_reason,
                },
            )

            return response.model_dump()

        except Exception as e:
            await self.log("error", f"LLM call failed: {e}")
            raise

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute a tool and return result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool parameters

        Returns:
            Tool execution result as string
        """
        await self.log(
            "info",
            f"Executing tool: {tool_name}",
            tool_name=tool_name,
            tool_input=tool_input,
        )

        try:
            # Import tool implementations dynamically
            from cloud_code.tools import execute_tool

            result = await execute_tool(
                tool_name,
                tool_input,
                workspace_path=self.workspace_path,
            )

            await self.log(
                "info",
                f"Tool completed: {tool_name}",
                tool_name=tool_name,
                tool_output=result[:500] if len(result) > 500 else result,
            )

            return result

        except Exception as e:
            error_msg = f"Tool execution failed: {e}"
            await self.log(
                "error",
                error_msg,
                tool_name=tool_name,
            )
            return f"Error: {error_msg}"

    async def setup_workspace(self, repo_url: str, branch: str = "main") -> Path:
        """
        Clone or update repository workspace.

        Args:
            repo_url: GitHub repository URL
            branch: Branch to checkout

        Returns:
            Path to workspace directory
        """
        from cloud_code.tools.git import clone_or_update_repo

        workspace_name = f"project-{self.project_id}"
        if self.task_id:
            workspace_name += f"/task-{self.task_id}"

        self.workspace_path = settings.workspaces_path / workspace_name

        await self.log("info", f"Setting up workspace: {self.workspace_path}")

        await clone_or_update_repo(
            repo_url=repo_url,
            target_path=self.workspace_path,
            branch=branch,
        )

        return self.workspace_path

    def load_prompt_template(self, template_name: str) -> str:
        """Load a prompt template from the prompts directory."""
        prompt_path = settings.prompts_path / f"{template_name}.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""

    def render_prompt(self, template: str, **kwargs) -> str:
        """Render a prompt template with variables."""
        result = template
        for key, value in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
