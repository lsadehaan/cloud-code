# OpenAI Codex Agent Container
# Uses OpenAI's Codex CLI for autonomous coding
# https://github.com/openai/codex-cli (or equivalent)

FROM cloud-code/agent-base:latest

# Install OpenAI CLI tools
# Note: The exact CLI name/package may vary - update as needed
RUN pip install openai

# Install codex-cli if available via npm
# This may need to be updated based on OpenAI's actual CLI release
RUN npm install -g @openai/codex-cli 2>/dev/null || echo "Codex CLI not yet available via npm"

# Set default coding CLI
ENV CODING_CLI=codex
ENV AGENT_TYPE=general

# OpenAI Codex specific settings
ENV CODEX_MODEL=gpt-4
ENV OPENAI_MODEL=gpt-4

# OPENAI_API_KEY should be injected at runtime

# Default command - run agent loop
CMD ["python", "-m", "agent_control_plane.loop"]
