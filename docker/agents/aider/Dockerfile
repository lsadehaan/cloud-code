# Aider Agent Container
# Uses Aider (open source) for autonomous coding
# https://aider.chat/

FROM cloud-code/agent-base:latest

# Install Aider via pip
# https://aider.chat/docs/install.html
RUN pip install aider-chat

# Verify installation
RUN aider --version

# Set default coding CLI
ENV CODING_CLI=aider
ENV AGENT_TYPE=general

# Aider specific settings
# These can be overridden at runtime
ENV AIDER_MODEL=claude-3-5-sonnet-20241022
ENV AIDER_AUTO_COMMITS=false
ENV AIDER_DIRTY_COMMITS=false

# Aider supports multiple LLM providers:
# - ANTHROPIC_API_KEY for Claude
# - OPENAI_API_KEY for GPT
# - AZURE_API_KEY for Azure OpenAI
# Credentials injected at runtime

# Default command - run agent loop
CMD ["python", "-m", "agent_control_plane.loop"]
