# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Cloud Code is a VPS-based autonomous development platform that:
1. Receives GitHub Issues via webhooks
2. Provisions Docker containers with coding CLIs
3. Runs autonomous agents to implement features/fixes
4. Creates Pull Requests with the changes

**Tech Stack:**
- Python 3.12+ with FastAPI
- Docker for agent containers
- HashiCorp Vault for secrets
- PostgreSQL for persistence
- Redis for task queue (Celery)

## Project Structure

```
src/cloud_code/
├── main.py                     # FastAPI entry point
├── config.py                   # Pydantic settings
├── core/
│   ├── container_manager.py    # Docker lifecycle (python-on-whales)
│   ├── workspace.py            # Git worktree management
│   ├── task_interface.py       # tasking.yaml/reporting.yaml
│   ├── orchestrator.py         # Task dispatch and monitoring
│   └── vault.py                # HashiCorp Vault client (hvac)
├── github/
│   ├── app.py                  # GitHub App OAuth, JWT, API client
│   ├── webhook.py              # POST /webhooks/github/
│   ├── events.py               # Issue/PR event handlers
│   ├── comment_parser.py       # Parse /cloud-code commands
│   └── task_creator.py         # Create tasks from issues
├── api/
│   ├── auth.py                 # OAuth flow, sessions
│   └── credentials.py          # CLI/GitHub credential management
├── agent_control_plane/        # Runs INSIDE containers
│   ├── loop.py                 # Main agent loop
│   └── cli_runner.py           # CLI abstraction (claude, aider, etc)
├── db/
│   └── models.py               # SQLAlchemy models
└── web/
    └── templates/              # Jinja2 templates
```

## Key Concepts

### File-Based Task Interface
Agents communicate via YAML files in the workspace:
- `tasking.yaml` - Orchestrator writes tasks here
- `reporting.yaml` - Agent writes status/progress here

This avoids network complexity inside containers.

### Coding CLI Abstraction
The `CLIRunner` class abstracts different coding tools:
- `claude-code` - Anthropic's Claude Code CLI
- `aider` - Open source, multi-model
- `codex` - OpenAI Codex
- `gemini` - Google Gemini

Each CLI type has its own Docker image with the CLI pre-installed.

### Container Architecture
- One container per agent instance
- Workspace mounted at /workspace
- Credentials injected as environment variables from Vault
- Agent loop runs continuously, polling tasking.yaml

## Commands

### Development
```bash
# Start all services (from repo root)
docker-compose up -d

# View logs
docker-compose logs -f app

# Build agent images
./scripts/build-agents.sh

# Run FastAPI directly (development)
cd src && python -m cloud_code.main
```

### Testing
```bash
# Run tests
pytest tests/ -v

# Type checking
mypy src/cloud_code
```

## Current Development Status

### Completed
- GitHub webhook handler with signature verification
- GitHub App OAuth flow and API client
- Vault integration for credential storage
- Container manager with python-on-whales
- Workspace manager with git worktrees
- Task interface (tasking.yaml/reporting.yaml)
- Agent control plane (loop + CLI runner)
- Web UI setup wizard
- Credential management API

### Remaining for MVP (Vertical Slice)
1. **Database Setup**
   - Alembic migrations
   - Wire up SQLAlchemy session management

2. **Celery Integration**
   - Background task for agent dispatch
   - Task monitoring/timeout handling

3. **GitHub Status Updates**
   - Post comments on issues with progress
   - Create PRs when task completes
   - Update issue labels

4. **End-to-End Testing**
   - Deploy to VPS
   - Test full Issue -> PR flow
   - Fix integration issues

### Future Enhancements
- GitLab support
- Parallel agent execution
- Agent handoff between CLIs
- Cost tracking per task
- Human approval gates

## Development Guidelines

### Adding a New Coding CLI
1. Create Dockerfile in `docker/agents/{cli-name}/`
2. Add config to `AGENT_CONFIGS` in `core/container_manager.py`
3. Add CLI class to `agent_control_plane/cli_runner.py`
4. Update `SUPPORTED_CLIS` registry
5. Add Vault credential mapping in `core/vault.py`

### Adding API Endpoints
1. Create route in `api/{module}.py`
2. Include router in `main.py`
3. Add authentication if needed (use `get_current_session`)

### Modifying Task Interface
The task interface format is critical - agents depend on it:
- `core/task_interface.py` - Pydantic models for YAML structure
- `agent_control_plane/loop.py` - Agent side that reads/writes
- Keep backward compatible when possible

## Environment Variables

Key settings (see `.env.example` for full list):
- `VAULT_URL` / `VAULT_TOKEN` - Vault connection
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis for Celery
- `GITHUB_APP_NAME` - GitHub App slug

API keys are stored in Vault, not environment variables.

## Debugging

### Container Issues
```bash
# List agent containers
docker ps -a | grep cloud-code

# View container logs
docker logs cloud-code-backend-1

# Exec into container
docker exec -it cloud-code-backend-1 /bin/bash
```

### Vault Issues
```bash
# Check Vault status
docker-compose exec vault vault status

# List secrets
docker-compose exec vault vault kv list secret/cloud-code/
```

### Task Interface Issues
Check the YAML files in the workspace:
```bash
cat /var/cloud-code/workspaces/{project}/.cloud-code/tasking.yaml
cat /var/cloud-code/workspaces/{project}/.cloud-code/reporting.yaml
```
