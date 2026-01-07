# Base Dockerfile for Cloud Code Agent Containers
# All coding CLI containers inherit from this base

FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    openssh-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for many coding CLIs)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Create workspace directory
RUN mkdir -p /workspace

# Set git config for commits and safe directory
RUN git config --global user.email "cloud-code-agent@localhost" \
    && git config --global user.name "Cloud Code Agent" \
    && git config --global init.defaultBranch main \
    && git config --global --add safe.directory /workspace

# Copy the agent control plane code
WORKDIR /app
COPY src/cloud_code/agent_control_plane /app/agent_control_plane
COPY src/cloud_code/core/task_interface.py /app/core/task_interface.py
COPY src/cloud_code/__init__.py /app/__init__.py

# Create minimal __init__ files
RUN touch /app/core/__init__.py

# Install agent control plane dependencies
RUN pip install pyyaml pydantic

# Set environment variables
ENV WORKSPACE=/workspace
ENV PYTHONPATH=/app

# Default command - run the agent loop
WORKDIR /workspace
CMD ["python", "-m", "agent_control_plane.loop"]
