# Cloud Code Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Copy project files first (for dependency caching)
COPY pyproject.toml .
COPY README.md .

# Copy source code BEFORE install (required for -e editable install)
COPY src/ src/
COPY prompts/ prompts/

# Install dependencies (now source exists for editable install)
RUN uv pip install --system -e .

# Set PYTHONPATH to find the cloud_code package
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Create workspaces directory
RUN mkdir -p /var/cloud-code/workspaces

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "cloud_code.main:app", "--host", "0.0.0.0", "--port", "8000"]
