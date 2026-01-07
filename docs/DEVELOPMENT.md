# Cloud Code Development Guide

## Current Status

The core infrastructure is complete. This document outlines remaining work and how to continue development.

## Remaining Tasks for MVP

### 1. Database Migrations

**Priority: High**

Set up Alembic for database migrations:

```bash
# In src/cloud_code/
alembic init alembic
```

Tasks:
- [ ] Configure Alembic with async SQLAlchemy
- [ ] Create initial migration from models.py
- [ ] Add migration to docker-compose startup

Files to modify:
- `alembic.ini`
- `alembic/env.py`
- Create `db/session.py` for async session management

### 2. Celery Background Tasks

**Priority: High**

The worker service is configured but tasks aren't defined yet.

Tasks:
- [ ] Create `queue/tasks.py` with task definitions
- [ ] `dispatch_task` - Provision container and write tasking.yaml
- [ ] `monitor_task` - Poll reporting.yaml and update GitHub
- [ ] `cleanup_container` - Remove idle containers

Files to create/modify:
- `queue/tasks.py`
- `queue/celery.py` (app configuration)
- Wire up in `core/orchestrator.py`

### 3. GitHub Status Updates

**Priority: High**

Post progress back to GitHub issues and create PRs.

Tasks:
- [ ] Post comment when task is received
- [ ] Update comment with progress
- [ ] Create PR when task completes
- [ ] Handle failures gracefully

Files to modify:
- `github/app.py` - Add PR creation methods
- `core/orchestrator.py` - Call GitHub API on status changes

### 4. End-to-End Testing

**Priority: Critical**

Test the full flow on a VPS:

```
Issue Created → Webhook → Task → Container → PR
```

Tasks:
- [ ] Deploy to VPS
- [ ] Create test issue
- [ ] Debug any integration issues
- [ ] Document findings

## Future Enhancements

### Agent Handoff

When one CLI gets stuck, hand off to another:

```python
# In cli_runner.py
if result.needs_handoff:
    suggest_cli = self._suggest_alternative_cli()
    # Orchestrator picks this up and dispatches to different container
```

### Parallel Execution

Run multiple agents simultaneously:

```python
# In orchestrator.py
async def dispatch_parallel(self, tasks: list[TaskDefinition]):
    await asyncio.gather(*[
        self.dispatch_task(task) for task in tasks
    ])
```

### Cost Tracking

Track token usage per task:

```python
# In models.py
class Task:
    tokens_used: int = 0
    cost_usd: float = 0.0
    cost_limit: float = 10.0  # Max cost before human approval
```

### Human Approval Gates

For expensive or sensitive tasks:

```python
# In orchestrator.py
if task.estimated_cost > task.cost_limit:
    await self._request_human_approval(task)
    # Wait for approval via GitHub comment
```

### GitLab Support

Add GitLab as a provider:

1. Create `gitlab/` module mirroring `github/`
2. Implement webhook handler
3. Add OAuth flow
4. Create merge request instead of PR

## Development Workflow

### Local Development

```bash
# Start dependencies only
docker compose up -d postgres redis vault

# Run FastAPI with reload
cd src
python -m cloud_code.main

# In another terminal, run worker
celery -A cloud_code.queue worker -l info
```

### Testing Webhooks Locally

Use ngrok to expose local server:

```bash
ngrok http 8000

# Update GitHub App webhook URL temporarily
# https://xxxxx.ngrok.io/webhooks/github/
```

### Adding a New Feature

1. Create issue describing the feature
2. Create branch: `git checkout -b feature/description`
3. Implement with tests
4. Test locally with ngrok
5. Deploy to VPS for final testing
6. Create PR

## Dogfooding

Once the MVP works, use Cloud Code to develop Cloud Code!

1. Install Cloud Code on this repository
2. Create issues for remaining tasks
3. Add `cloud-code` label
4. Let it implement and create PRs
5. Review and merge

This creates a virtuous cycle where:
- Bugs are found and fixed
- UX issues are discovered
- The system improves itself

## Code Style

- Python 3.12+ with type hints
- Async/await for I/O operations
- Pydantic for data validation
- FastAPI for web endpoints
- SQLAlchemy 2.0 async style

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=cloud_code

# Type checking
mypy src/cloud_code
```

## Debugging Tips

### View Container Environment

```bash
docker exec cloud-code-backend-1 env | grep -E "ANTHROPIC|OPENAI|GOOGLE"
```

### Check Task Interface Files

```bash
# On VPS
cat /var/cloud-code/workspaces/owner/repo/.cloud-code/tasking.yaml
cat /var/cloud-code/workspaces/owner/repo/.cloud-code/reporting.yaml
```

### Vault Secrets

```bash
# List all CLI credentials
docker compose exec vault vault kv list secret/cloud-code/cli/

# Read specific credential (careful with output!)
docker compose exec vault vault kv get secret/cloud-code/cli/claude-code
```

### Database Queries

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U cloudcode cloudcode

# List tables
\dt

# Query tasks
SELECT id, title, status FROM tasks ORDER BY created_at DESC LIMIT 10;
```

## Getting Help

- Check existing issues on GitHub
- Review the architecture docs
- Look at similar implementations in the codebase
- Ask Claude Code for help (it has context from CLAUDE.md)
