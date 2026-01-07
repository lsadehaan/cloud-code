"""CLI runner for various coding agents.

Abstracts the different coding CLIs behind a common interface:
- Claude Code (Anthropic)
- Aider (open source)
- OpenAI Codex CLI
- Google Gemini CLI
- And future CLIs...

Each container has ONE coding CLI installed, but the CLIRunner
interface is the same across all containers.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol


@dataclass
class CLIResult:
    """Result from running a coding CLI."""

    success: bool
    output: str
    error: Optional[str] = None
    files_changed: list[str] = field(default_factory=list)
    needs_handoff: bool = False  # True if recommending different agent
    tokens_used: int = 0  # For cost tracking
    cost_usd: float = 0.0


class CodingCLI(Protocol):
    """Protocol for coding CLI implementations."""

    name: str  # CLI identifier

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task with the coding CLI."""
        ...

    def is_available(self) -> bool:
        """Check if the CLI is installed and available."""
        ...


class BaseCLI:
    """Base class for coding CLI implementations."""

    name: str = "base"
    binary: str = "echo"  # Override in subclass

    def is_available(self) -> bool:
        """Check if the CLI binary is available."""
        import shutil
        return shutil.which(self.binary) is not None

    def _check_needs_handoff(self, output: str, error: Optional[str]) -> bool:
        """Check if output suggests task should be handed off to another agent."""
        indicators = [
            "unable to resolve",
            "stuck",
            "cannot proceed",
            "need different approach",
            "out of my expertise",
            "i cannot",
            "beyond my capabilities",
        ]
        text = (output + (error or "")).lower()
        return any(ind in text for ind in indicators)

    async def _run_command(
        self,
        cmd: list[str],
        workspace: Path,
        timeout: int,
        env: Optional[dict] = None,
    ) -> CLIResult:
        """Run a command and return the result."""
        full_env = {**os.environ}
        if env:
            full_env.update(env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return CLIResult(
                    success=False,
                    output="",
                    error=f"Task timed out after {timeout} seconds",
                )

            success = proc.returncode == 0
            output = stdout.decode() if stdout else ""
            error_msg = stderr.decode() if stderr and not success else None

            return CLIResult(
                success=success,
                output=output,
                error=error_msg,
                needs_handoff=self._check_needs_handoff(output, error_msg),
            )

        except FileNotFoundError:
            return CLIResult(
                success=False,
                output="",
                error=f"{self.name} CLI not found. Is '{self.binary}' installed?",
            )
        except Exception as e:
            return CLIResult(
                success=False,
                output="",
                error=str(e),
            )


class ClaudeCodeCLI(BaseCLI):
    """Claude Code CLI runner (Anthropic)."""

    name = "claude-code"
    binary = "claude"

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task using Claude Code CLI."""
        cmd = [
            "claude",
            "-p", prompt,
            "--model", self.model,
            "--allowedTools", "Edit,Write,Bash,Read,Glob,Grep",
        ]
        return await self._run_command(cmd, workspace, timeout)


class AiderCLI(BaseCLI):
    """Aider CLI runner (open source, multi-model)."""

    name = "aider"
    binary = "aider"

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task using Aider CLI."""
        cmd = [
            "aider",
            "--message", prompt,
            "--model", self.model,
            "--yes",  # Auto-confirm
            "--no-git",  # We handle git separately
        ]
        return await self._run_command(cmd, workspace, timeout)


class OpenAICodexCLI(BaseCLI):
    """OpenAI Codex CLI runner.

    Uses the OpenAI CLI or codex-specific tooling.
    See: https://github.com/openai/codex-cli (or similar)
    """

    name = "codex"
    binary = "codex"  # Adjust based on actual CLI name

    def __init__(self, model: str = "gpt-4"):
        self.model = model

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task using OpenAI Codex CLI."""
        # OpenAI's coding CLI - adjust command based on actual CLI
        # This might be `openai-codex`, `codex`, or similar
        cmd = [
            "codex",
            "--prompt", prompt,
            "--model", self.model,
            "--auto-approve",
        ]
        return await self._run_command(cmd, workspace, timeout)


class GeminiCLI(BaseCLI):
    """Google Gemini CLI runner.

    Uses Google's AI Studio CLI or Gemini-specific tooling.
    See: https://ai.google.dev/
    """

    name = "gemini"
    binary = "gemini"  # Adjust based on actual CLI name

    def __init__(self, model: str = "gemini-pro"):
        self.model = model

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task using Google Gemini CLI."""
        # Google's coding CLI - adjust command based on actual CLI
        cmd = [
            "gemini",
            "code",
            "--prompt", prompt,
            "--model", self.model,
        ]
        return await self._run_command(cmd, workspace, timeout)


class ContinueCLI(BaseCLI):
    """Continue.dev CLI runner (open source IDE extension with CLI).

    See: https://continue.dev/
    """

    name = "continue"
    binary = "continue"

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task using Continue CLI."""
        cmd = [
            "continue",
            "run",
            "--prompt", prompt,
        ]
        return await self._run_command(cmd, workspace, timeout)


class CursorCLI(BaseCLI):
    """Cursor CLI runner (if available).

    Note: Cursor is primarily an IDE, CLI support may vary.
    See: https://cursor.sh/
    """

    name = "cursor"
    binary = "cursor"

    async def execute(
        self,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
    ) -> CLIResult:
        """Execute a task using Cursor CLI."""
        cmd = [
            "cursor",
            "--prompt", prompt,
        ]
        return await self._run_command(cmd, workspace, timeout)


# =============================================================================
# CLI Registry and Factory
# =============================================================================

# All supported CLIs
SUPPORTED_CLIS: dict[str, type[BaseCLI]] = {
    "claude-code": ClaudeCodeCLI,
    "aider": AiderCLI,
    "codex": OpenAICodexCLI,
    "gemini": GeminiCLI,
    "continue": ContinueCLI,
    "cursor": CursorCLI,
}


class CLIRunner:
    """Factory for getting the appropriate CLI runner."""

    _instances: dict[str, BaseCLI] = {}

    @classmethod
    def get_supported_clis(cls) -> list[str]:
        """Get list of supported CLI names."""
        return list(SUPPORTED_CLIS.keys())

    @classmethod
    def get_cli(cls, cli_name: str, **kwargs) -> BaseCLI:
        """Get or create a CLI runner instance.

        Args:
            cli_name: Name of the CLI (claude-code, aider, codex, gemini, etc.)
            **kwargs: Additional arguments passed to CLI constructor
        """
        cache_key = f"{cli_name}:{hash(frozenset(kwargs.items()))}"

        if cache_key not in cls._instances:
            if cli_name not in SUPPORTED_CLIS:
                raise ValueError(
                    f"Unknown CLI: {cli_name}. "
                    f"Supported: {', '.join(SUPPORTED_CLIS.keys())}"
                )
            cli_class = SUPPORTED_CLIS[cli_name]
            cls._instances[cache_key] = cli_class(**kwargs)

        return cls._instances[cache_key]

    @classmethod
    def is_available(cls, cli_name: str) -> bool:
        """Check if a CLI is installed and available."""
        try:
            cli = cls.get_cli(cli_name)
            return cli.is_available()
        except ValueError:
            return False

    @classmethod
    def get_available_clis(cls) -> list[str]:
        """Get list of CLIs that are actually installed."""
        return [name for name in SUPPORTED_CLIS.keys() if cls.is_available(name)]

    @classmethod
    async def run(
        cls,
        cli_name: str,
        prompt: str,
        workspace: Path,
        timeout: int = 3600,
        **kwargs,
    ) -> CLIResult:
        """Run a task with the specified CLI.

        Args:
            cli_name: Name of the CLI to use
            prompt: The task prompt
            workspace: Path to the workspace directory
            timeout: Maximum execution time in seconds
            **kwargs: Additional arguments passed to CLI
        """
        cli = cls.get_cli(cli_name, **kwargs)

        if not cli.is_available():
            return CLIResult(
                success=False,
                output="",
                error=f"{cli_name} CLI is not installed or not in PATH",
            )

        return await cli.execute(prompt, workspace, timeout)
