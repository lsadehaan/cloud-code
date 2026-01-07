"""Agent Control Plane - runs inside each agent container.

This is the thin wrapper that:
1. Reads tasking.yaml for new tasks
2. Executes tasks using the configured coding CLI
3. Writes status to reporting.yaml
4. Handles credential requests
"""

from cloud_code.agent_control_plane.loop import AgentLoop
from cloud_code.agent_control_plane.cli_runner import CLIRunner, CLIResult

__all__ = ["AgentLoop", "CLIRunner", "CLIResult"]
