# Google Gemini Agent Container
# Uses Google's Gemini CLI for autonomous coding
# https://ai.google.dev/

FROM cloud-code/agent-base:latest

# Install Google Cloud SDK and AI tools
RUN pip install google-generativeai google-cloud-aiplatform

# Install gemini-cli if available
# Note: Google's CLI tooling may evolve - update as needed
RUN npm install -g @google/gemini-cli 2>/dev/null || echo "Gemini CLI not yet available via npm"

# Set default coding CLI
ENV CODING_CLI=gemini
ENV AGENT_TYPE=general

# Gemini specific settings
ENV GEMINI_MODEL=gemini-pro
ENV GOOGLE_AI_MODEL=gemini-pro

# GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS should be injected at runtime

# Default command - run agent loop
CMD ["python", "-m", "agent_control_plane.loop"]
