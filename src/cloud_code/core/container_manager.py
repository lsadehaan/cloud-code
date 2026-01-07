"""Container management for Cloud Code agent workstations.

Uses python-on-whales for Docker API interactions.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from python_on_whales import docker, DockerClient
from python_on_whales.components.container.cli_wrapper import Container

from cloud_code.config import settings


@dataclass
class AgentConfig:
    """Configuration for an agent container."""

    agent_type: str
    coding_cli: str  # claude-code, aider, codex-cli
    image: str
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    environment: dict[str, str] | None = None


# Default agent configurations
# Each agent type maps to a specific container with a coding CLI installed
AGENT_CONFIGS: dict[str, AgentConfig] = {
    # ==========================================================================
    # Specialized agents (by domain) - all use Claude Code by default
    # ==========================================================================
    "frontend": AgentConfig(
        agent_type="frontend",
        coding_cli="claude-code",
        image="cloud-code/frontend-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),
    "backend": AgentConfig(
        agent_type="backend",
        coding_cli="claude-code",
        image="cloud-code/backend-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),
    "reviewer": AgentConfig(
        agent_type="reviewer",
        coding_cli="claude-code",
        image="cloud-code/reviewer-agent:latest",
        memory_limit="1g",
        cpu_limit=1.0,
    ),
    "testing": AgentConfig(
        agent_type="testing",
        coding_cli="claude-code",
        image="cloud-code/testing-agent:latest",
        memory_limit="4g",
        cpu_limit=2.0,
    ),
    "devops": AgentConfig(
        agent_type="devops",
        coding_cli="claude-code",
        image="cloud-code/devops-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),
    "database": AgentConfig(
        agent_type="database",
        coding_cli="claude-code",
        image="cloud-code/database-agent:latest",
        memory_limit="1g",
        cpu_limit=1.0,
    ),

    # ==========================================================================
    # CLI-specific agents (for handoff scenarios)
    # ==========================================================================

    # Aider (open source, multi-model support)
    "aider": AgentConfig(
        agent_type="general",
        coding_cli="aider",
        image="cloud-code/aider-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),

    # OpenAI Codex
    "codex": AgentConfig(
        agent_type="general",
        coding_cli="codex",
        image="cloud-code/codex-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),

    # Google Gemini
    "gemini": AgentConfig(
        agent_type="general",
        coding_cli="gemini",
        image="cloud-code/gemini-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),

    # Continue.dev
    "continue": AgentConfig(
        agent_type="general",
        coding_cli="continue",
        image="cloud-code/continue-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),

    # Cursor (if CLI available)
    "cursor": AgentConfig(
        agent_type="general",
        coding_cli="cursor",
        image="cloud-code/cursor-agent:latest",
        memory_limit="2g",
        cpu_limit=2.0,
    ),
}


@dataclass
class AgentInstance:
    """A running agent container instance."""

    container_id: str
    container_name: str
    agent_type: str
    coding_cli: str
    workspace_path: Optional[Path] = None
    is_busy: bool = False


class ContainerManager:
    """Manages Docker containers for agent workstations."""

    def __init__(self, network_name: str = "cloud-code-network"):
        self.docker = DockerClient()
        self.network_name = network_name
        self.agents: dict[str, AgentInstance] = {}

        # Ensure network exists
        self._ensure_network()

    def _ensure_network(self) -> None:
        """Ensure the Docker network exists."""
        try:
            docker.network.inspect(self.network_name)
        except Exception:
            docker.network.create(self.network_name, driver="bridge")

    async def provision_agent(
        self,
        agent_type: str,
        name: Optional[str] = None,
        workspace_path: Optional[Path] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> AgentInstance:
        """Provision a new agent container.

        Args:
            agent_type: Type of agent (frontend, backend, etc.)
            name: Optional container name
            workspace_path: Path to mount as workspace
            environment: Additional environment variables

        Returns:
            AgentInstance with container info
        """
        config = AGENT_CONFIGS.get(agent_type)
        if not config:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Generate container name
        container_name = name or f"cloud-code-{agent_type}-{len(self.agents) + 1}"

        # Build environment
        env = {
            "AGENT_TYPE": config.agent_type,
            "CODING_CLI": config.coding_cli,
            "ANTHROPIC_API_KEY": settings.anthropic_api_key.get_secret_value(),
        }
        if config.environment:
            env.update(config.environment)
        if environment:
            env.update(environment)

        # Build volumes
        volumes = []
        if workspace_path:
            volumes.append((str(workspace_path), "/workspace", "rw"))

        # Run container
        container = await asyncio.to_thread(
            docker.container.run,
            config.image,
            name=container_name,
            detach=True,
            networks=[self.network_name],
            envs=env,
            volumes=volumes,
            mem_limit=config.memory_limit,
            cpus=config.cpu_limit,
            # Keep container running
            command=["tail", "-f", "/dev/null"],
        )

        instance = AgentInstance(
            container_id=container.id,
            container_name=container_name,
            agent_type=config.agent_type,
            coding_cli=config.coding_cli,
            workspace_path=workspace_path,
        )

        self.agents[container_name] = instance
        return instance

    async def get_or_create_agent(
        self,
        agent_type: str,
        workspace_path: Optional[Path] = None,
    ) -> AgentInstance:
        """Get an existing idle agent or create a new one."""
        # Look for idle agent of the right type
        for agent in self.agents.values():
            if agent.agent_type == agent_type and not agent.is_busy:
                # Update workspace if needed
                if workspace_path and agent.workspace_path != workspace_path:
                    await self._update_workspace(agent, workspace_path)
                return agent

        # Create new agent
        return await self.provision_agent(agent_type, workspace_path=workspace_path)

    async def _update_workspace(
        self, agent: AgentInstance, workspace_path: Path
    ) -> None:
        """Update the workspace mount for an agent."""
        # For simplicity, we'll exec into the container and create a symlink
        # In production, you might want to restart the container with new mounts
        agent.workspace_path = workspace_path

    async def execute_in_agent(
        self,
        agent: AgentInstance,
        command: list[str],
        workdir: Optional[str] = None,
    ) -> tuple[int, str, str]:
        """Execute a command inside an agent container.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        result = await asyncio.to_thread(
            docker.container.execute,
            agent.container_id,
            command,
            workdir=workdir or "/workspace",
        )

        # python-on-whales returns output directly
        if isinstance(result, str):
            return 0, result, ""
        return 0, str(result), ""

    async def run_coding_cli(
        self,
        agent: AgentInstance,
        prompt: str,
        workspace_path: Path,
    ) -> tuple[bool, str]:
        """Run the coding CLI in an agent container.

        Returns:
            Tuple of (success, output)
        """
        agent.is_busy = True

        try:
            if agent.coding_cli == "claude-code":
                command = [
                    "claude",
                    "-p", prompt,
                    "--allowedTools", "Edit,Write,Bash,Read",
                ]
            elif agent.coding_cli == "aider":
                command = [
                    "aider",
                    "--message", prompt,
                    "--yes",
                ]
            else:
                raise ValueError(f"Unknown coding CLI: {agent.coding_cli}")

            return_code, stdout, stderr = await self.execute_in_agent(
                agent, command, workdir=str(workspace_path)
            )

            success = return_code == 0
            output = stdout if success else stderr

            return success, output

        finally:
            agent.is_busy = False

    async def health_check(self, agent: AgentInstance) -> bool:
        """Check if an agent container is healthy."""
        try:
            container = await asyncio.to_thread(
                docker.container.inspect, agent.container_id
            )
            return container.state.running
        except Exception:
            return False

    async def stop_agent(self, agent: AgentInstance) -> None:
        """Stop an agent container."""
        try:
            await asyncio.to_thread(
                docker.container.stop, agent.container_id, time=10
            )
        except Exception:
            pass

        if agent.container_name in self.agents:
            del self.agents[agent.container_name]

    async def remove_agent(self, agent: AgentInstance) -> None:
        """Stop and remove an agent container."""
        await self.stop_agent(agent)
        try:
            await asyncio.to_thread(
                docker.container.remove, agent.container_id, force=True
            )
        except Exception:
            pass

    async def list_agents(self) -> list[AgentInstance]:
        """List all running agent containers."""
        containers = await asyncio.to_thread(
            docker.container.list,
            filters={"name": "cloud-code-"},
        )

        agents = []
        for container in containers:
            # Check if we're tracking this container
            if container.name in self.agents:
                agents.append(self.agents[container.name])
            else:
                # Reconstruct agent info from container
                env = dict(e.split("=", 1) for e in (container.config.env or []) if "=" in e)
                agents.append(
                    AgentInstance(
                        container_id=container.id,
                        container_name=container.name,
                        agent_type=env.get("AGENT_TYPE", "unknown"),
                        coding_cli=env.get("CODING_CLI", "unknown"),
                    )
                )

        return agents

    async def cleanup_all(self) -> None:
        """Stop and remove all agent containers."""
        containers = await asyncio.to_thread(
            docker.container.list,
            filters={"name": "cloud-code-"},
        )

        for container in containers:
            try:
                await asyncio.to_thread(docker.container.remove, container.id, force=True)
            except Exception:
                pass

        self.agents.clear()


# Singleton instance
_container_manager: Optional[ContainerManager] = None


def get_container_manager() -> ContainerManager:
    """Get the singleton container manager instance."""
    global _container_manager
    if _container_manager is None:
        _container_manager = ContainerManager()
    return _container_manager
