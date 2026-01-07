# Cloud Code Architecture

## System Overview

Cloud Code consists of three main components:

1. **Orchestrator** - FastAPI application that manages the platform
2. **Agent Containers** - Docker containers running coding CLIs
3. **Supporting Services** - Vault, PostgreSQL, Redis

```
┌─────────────────────────────────────────────────────────────────┐
│                           GitHub                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                          │
│  │  Issue  │  │   PR    │  │ Comment │                          │
│  └────┬────┘  └────▲────┘  └────┬────┘                          │
└───────┼────────────┼────────────┼───────────────────────────────┘
        │            │            │
        │ Webhook    │ API        │ Webhook
        ▼            │            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Webhook    │  │  Task        │  │  Container   │           │
│  │   Handler    │──▶  Orchestrator│──▶  Manager     │           │
│  └──────────────┘  └──────────────┘  └──────┬───────┘           │
│                                              │                   │
│  ┌──────────────┐  ┌──────────────┐         │                   │
│  │   Vault      │  │  Workspace   │         │                   │
│  │   Client     │  │  Manager     │         │                   │
│  └──────────────┘  └──────────────┘         │                   │
└─────────────────────────────────────────────┼───────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────┐
                    │     Docker Network      │                 │
                    │  ┌──────────────────────▼───────────────┐ │
                    │  │         Agent Container              │ │
                    │  │  ┌─────────────┐  ┌───────────────┐  │ │
                    │  │  │ Agent Loop  │  │  Coding CLI   │  │ │
                    │  │  │             │──▶ (claude, etc) │  │ │
                    │  │  └─────────────┘  └───────────────┘  │ │
                    │  │         │                            │ │
                    │  │         ▼                            │ │
                    │  │  ┌─────────────────────────────────┐ │ │
                    │  │  │         /workspace              │ │ │
                    │  │  │  tasking.yaml  reporting.yaml   │ │ │
                    │  │  └─────────────────────────────────┘ │ │
                    │  └──────────────────────────────────────┘ │
                    └───────────────────────────────────────────┘
```

## Component Details

### Orchestrator (FastAPI)

The central controller running on the VPS:

**Responsibilities:**
- Receive and validate GitHub webhooks
- Manage task lifecycle (create, dispatch, monitor)
- Provision and manage Docker containers
- Fetch credentials from Vault
- Update GitHub (comments, PRs, labels)

**Key Modules:**
- `main.py` - FastAPI app, routes, lifespan
- `core/orchestrator.py` - Task dispatch logic
- `core/container_manager.py` - Docker operations
- `github/webhook.py` - Webhook endpoint
- `github/app.py` - GitHub App API client

### Agent Containers

Isolated Docker containers running coding CLIs:

**Lifecycle:**
1. Orchestrator provisions container with workspace mount
2. Credentials injected as environment variables
3. Agent loop starts, reads `tasking.yaml`
4. Coding CLI executes task
5. Agent writes progress to `reporting.yaml`
6. Container stays running for next task (or gets recycled)

**Container Types:**
- `cloud-code/agent-base` - Base image with Python, Node, git
- `cloud-code/claude-code-agent` - Claude Code CLI
- `cloud-code/aider-agent` - Aider CLI
- `cloud-code/codex-agent` - OpenAI Codex
- `cloud-code/gemini-agent` - Google Gemini

### File-Based Task Interface

Communication between orchestrator and agents via YAML files:

**tasking.yaml** (Orchestrator writes):
```yaml
version: 1
updated_at: 2024-01-15T10:30:00Z
workspace: /var/cloud-code/workspaces/owner/repo
tasks:
  - id: issue-123-abc12345
    title: Add user authentication
    status: assigned
    priority: high
    branch: cloud-code/issue-123
    description: |
      Implement user login and registration...
    acceptance_criteria:
      - Users can register with email
      - Users can log in
    context:
      related_files:
        - src/auth/
        - src/models/user.py
```

**reporting.yaml** (Agent writes):
```yaml
version: 1
agent_type: backend
agent_id: backend-1
updated_at: 2024-01-15T10:35:00Z
status: working
tasks:
  issue-123-abc12345:
    status: in_progress
    current_step: Implementing login endpoint
    progress:
      - timestamp: 2024-01-15T10:31:00Z
        status: received
        message: Task acknowledged
      - timestamp: 2024-01-15T10:32:00Z
        status: planning
        message: Analyzing requirements
    files_modified:
      - path: src/auth/login.py
        change_type: created
    commits:
      - sha: abc1234
        message: "feat: add login endpoint"
```

### Supporting Services

**HashiCorp Vault:**
- Stores API keys (Anthropic, OpenAI, Google)
- Stores GitHub App credentials
- Stores installation tokens
- Accessed by orchestrator, credentials injected into containers

**PostgreSQL:**
- Projects and repositories
- Tasks and executions
- Agent workstations
- Activity logs

**Redis:**
- Celery task queue
- Session storage (future)
- Rate limiting (future)

## Security Model

### Container Isolation

Agents run in isolated Docker containers:
- No network access to orchestrator internals
- Read-only access to workspace (except .cloud-code/)
- Credentials as environment variables (not files)
- Resource limits (CPU, memory)

### Credential Management

API keys never touch disk unencrypted:
1. User enters keys in web UI
2. Keys stored in Vault (encrypted at rest)
3. Orchestrator fetches from Vault
4. Injected into container environment
5. Container process uses keys
6. Keys never written to files

### GitHub App Security

- Webhook signatures verified (HMAC-SHA256)
- Installation tokens scoped to specific repos
- JWTs expire after 10 minutes
- OAuth state parameter prevents CSRF

## Data Flow: Issue to PR

```
1. User creates issue with 'cloud-code' label
   │
2. GitHub sends webhook to /webhooks/github/
   │
3. Webhook handler validates signature
   │
4. Event handler parses issue, infers agent type
   │
5. Task created in database
   │
6. Orchestrator dispatches task:
   │  a. Get/create workspace (git worktree)
   │  b. Write task to tasking.yaml
   │  c. Get/create agent container
   │  d. Inject credentials from Vault
   │
7. Agent loop picks up task:
   │  a. Read tasking.yaml
   │  b. Build prompt for CLI
   │  c. Run coding CLI
   │  d. Commit changes
   │  e. Write to reporting.yaml
   │
8. Orchestrator monitors reporting.yaml:
   │  a. Post progress comments to issue
   │  b. On completion: create PR
   │  c. On failure: post error, retry or escalate
   │
9. User reviews PR, merges or requests changes
```

## Scaling Considerations

### Horizontal Scaling

- **Orchestrator:** Stateless, can run multiple instances behind load balancer
- **Agents:** Multiple containers can run in parallel
- **Vault:** Clustered deployment for HA
- **PostgreSQL:** Read replicas for queries
- **Redis:** Clustered for queue distribution

### Resource Management

- Agent containers have memory/CPU limits
- Idle containers recycled after timeout
- Workspace cleanup for completed tasks
- Cost tracking per task (tokens used)

## Extension Points

### Adding New Git Providers (GitLab, Bitbucket)

1. Create provider-specific client in `providers/`
2. Implement webhook handler
3. Add OAuth flow
4. Register in orchestrator

### Adding New Coding CLIs

1. Create Dockerfile in `docker/agents/`
2. Add CLI class in `cli_runner.py`
3. Add config in `container_manager.py`
4. Add Vault credential mapping
