#!/bin/bash
# Build all Cloud Code agent container images

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building Cloud Code agent containers..."
echo "Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# Build base image first
echo ""
echo "=========================================="
echo "Building base agent image..."
echo "=========================================="
docker build -t cloud-code/agent-base:latest -f docker/agents/base/Dockerfile .

# Build Claude Code agent
echo ""
echo "=========================================="
echo "Building Claude Code agent image..."
echo "=========================================="
docker build -t cloud-code/claude-code-agent:latest -f docker/agents/claude-code/Dockerfile .

# Build Aider agent
echo ""
echo "=========================================="
echo "Building Aider agent image..."
echo "=========================================="
docker build -t cloud-code/aider-agent:latest -f docker/agents/aider/Dockerfile .

# Build Codex agent
echo ""
echo "=========================================="
echo "Building OpenAI Codex agent image..."
echo "=========================================="
docker build -t cloud-code/codex-agent:latest -f docker/agents/codex/Dockerfile .

# Build Gemini agent
echo ""
echo "=========================================="
echo "Building Google Gemini agent image..."
echo "=========================================="
docker build -t cloud-code/gemini-agent:latest -f docker/agents/gemini/Dockerfile .

echo ""
echo "=========================================="
echo "All agent images built successfully!"
echo "=========================================="
echo ""
echo "Available images:"
docker images | grep cloud-code
