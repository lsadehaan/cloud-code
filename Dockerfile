# Cloud Code Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
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
