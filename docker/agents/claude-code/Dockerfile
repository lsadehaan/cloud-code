# Claude Code Agent Container
# Uses Anthropic's Claude Code CLI for autonomous coding

FROM cloud-code/agent-base:latest

# Install Claude Code CLI via npm
# https://docs.anthropic.com/en/docs/claude-code
RUN npm install -g @anthropic-ai/claude-code

# Verify installation
RUN claude --version || echo "Claude CLI installed (version check may require auth)"

# Set default coding CLI
ENV CODING_CLI=claude-code
ENV AGENT_TYPE=general

# Claude Code specific settings
# These can be overridden at runtime
ENV CLAUDE_CODE_MODEL=claude-sonnet-4-20250514
ENV CLAUDE_CODE_MAX_TOKENS=8192

# The ANTHROPIC_API_KEY should be injected at runtime via:
# - Docker secrets
# - Environment variable from orchestrator
# - Vault credential injection

# Default command - run agent loop
CMD ["python", "-m", "agent_control_plane.loop"]
