# Cloud Code - Design Document

> Autonomous AI-Powered Development Platform

**Version:** 0.5.0
**Author:** Cloud Code Team
**Date:** January 2026

**Changelog:**
- v0.5.0: Workspace modes (shared/isolated), credential management (Vault), rich reporting for GitHub/GitLab
- v0.4.0: File-based task interface (tasking.yaml/reporting.yaml), coding CLI abstraction, agent handoff
- v0.3.0: Added enhanced Task/AgentLog models, LiteLLM, Vertical Slice phases, git worktree caching
- v0.2.0: Container-first security model, specialized agent workstations
- v0.1.0: Initial design

---

## Table of Contents

1. [Vision & Goals](#vision--goals)
2. [Architecture Overview](#architecture-overview)
3. [Agent Workstation Model](#agent-workstation-model)
4. [Core Components](#core-components)
5. [Data Models](#data-models)
6. [Agent System](#agent-system)
7. [Container Architecture](#container-architecture)
8. [GitHub Integration](#github-integration)
9. [Web Interface](#web-interface)
10. [API Design](#api-design)
11. [Security Model](#security-model)
12. [Deployment Architecture](#deployment-architecture)
13. [Implementation Phases](#implementation-phases)
14. [Tech Stack](#tech-stack)

---

## Vision & Goals

### What is Cloud Code?

Cloud Code is an autonomous AI-powered development platform that runs on VPS infrastructure, using GitHub/GitLab as its control plane. Unlike traditional development tools that require constant human interaction, Cloud Code agents autonomously:

- Monitor repositories for new issues and tasks
- Prioritize and assign work to specialized worker agents
- Implement features, fix bugs, and create pull requests
- Review code and iterate based on feedback
- Learn from project context via RAG-powered memory

### Core Principles

1. **GitHub-Native**: GitHub Issues, Projects, and PRs ARE the UI. No reinventing the wheel.
2. **Server-First**: Designed for VPS deployment from day one. No desktop app complexity.
3. **Containerized Agents**: Each agent runs in its own persistent container with full freedom.
4. **Autonomous but Supervised**: Agents work independently with human oversight via web dashboard.
5. **Specialized Workers**: Different agents for frontend, backend, DevOps, testing, etc.

### Key Differentiators

| Traditional Dev Tools | Cloud Code |
|-----------------------|------------|
| User initiates every action | Agents monitor and act autonomously |
| Local execution | Cloud VPS execution |
| Restricted command execution | Full container freedom |
| Single environment | Specialized agent workstations |
| Ephemeral execution | Persistent agent state & tools |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GITHUB / GITLAB                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Issues    │  │  Projects   │  │    PRs      │  │   Actions   │        │
│  │  (Tasks)    │  │ (Priority)  │  │  (Output)   │  │  (CI/CD)    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────┘
          │                │                │                │
          │ Webhooks / Polling              │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLOUD CODE ORCHESTRATOR                               │
│                          (Host VPS - Minimal)                                │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   FastAPI Web    │  │   Task Queue     │  │   PostgreSQL     │          │
│  │   Dashboard      │  │   (Redis)        │  │   (State)        │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     AGENT MANAGER (Docker API)                        │   │
│  │  - Spawns/monitors agent containers                                   │   │
│  │  - Routes tasks to appropriate specialists                            │   │
│  │  - Manages container lifecycle & health                               │   │
│  │  - Handles inter-agent communication                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ Docker Network (isolated)
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    │                             │                             │
    ▼                             ▼                             ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ FRONTEND AGENT  │   │ BACKEND AGENT   │   │ DEVOPS AGENT    │
│  Workstation    │   │  Workstation    │   │  Workstation    │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ • Node.js 20    │   │ • Python 3.12   │   │ • Docker-in-D   │
│ • npm/yarn/pnpm │   │ • uv/poetry/pip │   │ • kubectl/helm  │
│ • React/Vue/etc │   │ • FastAPI/Django│   │ • terraform     │
│ • TypeScript    │   │ • SQLAlchemy    │   │ • ansible       │
│ • Playwright    │   │ • Redis/PG CLI  │   │ • aws/gcloud    │
│ • Tailwind      │   │ • pytest        │   │ • nginx         │
│ • ESLint/Prettier│  │ • mypy/ruff     │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
    ┌────┴────┐           ┌────┴────┐           ┌────┴────┐
    │ Volume  │           │ Volume  │           │ Volume  │
    │ - tools │           │ - tools │           │ - tools │
    │ - cache │           │ - cache │           │ - cache │
    │ - config│           │ - config│           │ - config│
    └─────────┘           └─────────┘           └─────────┘

┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ DATABASE AGENT  │   │ REVIEWER AGENT  │   │ TESTING AGENT   │
│  Workstation    │   │  Workstation    │   │  Workstation    │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ • PostgreSQL    │   │ • Static analysis│  │ • pytest/jest   │
│ • MySQL         │   │ • Security scan │   │ • Playwright    │
│ • Redis         │   │ • Code review   │   │ • Cypress       │
│ • MongoDB       │   │ • Linters       │   │ • k6/locust     │
│ • Migration tools│  │ • Style checks  │   │ • Coverage      │
└─────────────────┘   └─────────────────┘   └─────────────────┘

         │                     │                     │
         └─────────────────────┴─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  SHARED WORKSPACE   │
                    │     VOLUME          │
                    │  /workspaces/{repo} │
                    └─────────────────────┘
```

---

## Agent Workstation Model

### Philosophy: Agents as Employees

Instead of treating agents as ephemeral script runners, we treat them as **employees with their own workstations**:

| Traditional Approach | Workstation Approach |
|---------------------|---------------------|
| Spin up container per task | Persistent container per agent |
| Restricted commands | Full container freedom |
| Minimal tooling | Rich, accumulated tooling |
| Stateless execution | Stateful with preferences |
| Generic environment | Specialized environments |

### Benefits

1. **No Command Restrictions**: Agent can `rm -rf /` inside container—only affects itself
2. **Tool Accumulation**: Agents install tools they need, persisted across tasks
3. **Warm Caches**: npm cache, pip cache, etc. persist—faster subsequent tasks
4. **Specialization**: Frontend agent has Node ecosystem, Backend has Python, etc.
5. **Faster Execution**: No container startup per task
6. **State Persistence**: Agent "remembers" its setup, preferences, installed tools

### Container Lifecycle

```
1. PROVISIONING
   └─ Create container from base image
   └─ Mount persistent volume for tools/cache
   └─ Configure SSH keys, git config
   └─ Start agent daemon process

2. IDLE
   └─ Container running, agent waiting for tasks
   └─ Low resource usage
   └─ Health checks active

3. WORKING
   └─ Agent receives task from orchestrator
   └─ Full freedom to execute any commands
   └─ May install additional tools as needed
   └─ Reports progress via API

4. MAINTENANCE (periodic)
   └─ Cleanup old files
   └─ Update base tools
   └─ Snapshot for backup

5. RECREATION (rare)
   └─ If corrupted or needs major update
   └─ Preserve tool volume, recreate container
```

### Workstation Specifications

| Agent Type | Base Image | Pre-installed | Resource Limits |
|------------|------------|---------------|-----------------|
| Frontend | node:20-bookworm | npm, yarn, pnpm, bun | 2GB RAM, 2 CPU |
| Backend | python:3.12-bookworm | uv, poetry, pip | 2GB RAM, 2 CPU |
| Database | ubuntu:24.04 | psql, mysql, redis-cli | 1GB RAM, 1 CPU |
| DevOps | docker:dind | kubectl, terraform, helm | 2GB RAM, 2 CPU |
| Reviewer | python:3.12-slim | ruff, mypy, eslint | 1GB RAM, 1 CPU |
| Testing | mcr.microsoft.com/playwright | pytest, jest, playwright | 4GB RAM, 2 CPU |
| Planner | python:3.12-slim | minimal | 512MB RAM, 1 CPU |

### Future: Windows Agents

For projects requiring Windows-specific tooling:

```
┌─────────────────────────────────────────────────┐
│           WINDOWS AGENT (Future)                │
│         (Separate Windows VPS/VM)               │
├─────────────────────────────────────────────────┤
│ • Windows Server 2022                           │
│ • Visual Studio Build Tools                     │
│ • .NET SDK                                      │
│ • PowerShell                                    │
│ • Windows-specific testing                      │
│                                                 │
│ Communication via:                              │
│ • SSH (OpenSSH for Windows)                     │
│ • WinRM                                         │
│ • File-based tasking/reporting interface        │
└─────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Orchestrator (Host) - The Bridge

The orchestrator is the **bridge** between human managers, task management systems (GitHub/GitLab/Linear), and agent containers. Runs on host VPS, NOT in container.

```
┌─────────────────────────────────────────────────────────────────┐
│                         HUMAN MANAGER                            │
│              (GitHub Issues / GitLab / Linear / Dashboard)       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                              │
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │   GitHub    │ │   GitLab    │ │   Linear    │ │   Vault   │ │
│  │  Connector  │ │  Connector  │ │  Connector  │ │ (secrets) │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Task Router                              │ │
│  │  • Reads issues → creates tasks                            │ │
│  │  • Routes to appropriate agent                              │ │
│  │  • Monitors reporting.yaml                                  │ │
│  │  • Posts updates to GitHub/GitLab                          │ │
│  │  • Handles credential requests                              │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │ Claude Code │     │    Aider    │     │   Codex     │
   │  Container  │     │  Container  │     │  Container  │
   └─────────────┘     └─────────────┘     └─────────────┘
```

**Responsibilities:**
- **Task Management Connectors**: Receive webhooks from GitHub/GitLab/Linear
- **Task Routing**: Route tasks to appropriate agent containers
- **Progress Monitoring**: Read reporting.yaml, post updates to GitHub/GitLab
- **Credential Management**: Handle agent credential requests via Vault
- **PR/MR Creation**: Aggregate agent work, create pull/merge requests
- **Web Dashboard**: Serve monitoring UI

**What it does NOT do:**
- Execute any code changes (delegated to agents)
- Run user project code
- Access user project files directly (agents do this)

### 2. Agent Manager

Controls the agent container fleet via Docker API.

```python
class AgentManager:
    """Manages the fleet of agent workstations."""

    async def provision_agent(self, agent_type: str) -> AgentWorkstation:
        """Create a new agent workstation container."""

    async def get_agent(self, agent_type: str) -> AgentWorkstation:
        """Get an available agent of the specified type."""

    async def execute_task(self, agent: AgentWorkstation, task: Task) -> TaskResult:
        """Send task to agent and wait for completion."""

    async def health_check(self, agent: AgentWorkstation) -> HealthStatus:
        """Check if agent is responsive."""

    async def restart_agent(self, agent: AgentWorkstation) -> None:
        """Restart a failed agent container."""

    async def scale_agents(self, agent_type: str, count: int) -> None:
        """Scale agent pool up or down."""
```

### 3. Agent Workstations

Each specialized agent runs in its own container:

#### Frontend Agent
- **Focus**: React, Vue, Angular, Svelte, HTML/CSS
- **Tools**: Node.js, npm/yarn/pnpm, TypeScript, bundlers
- **Testing**: Jest, Vitest, Playwright, Cypress
- **Linting**: ESLint, Prettier, Stylelint

#### Backend Agent
- **Focus**: Python, Node.js, Go, Rust APIs
- **Tools**: Language runtimes, package managers
- **Databases**: Client CLIs for PostgreSQL, MySQL, Redis, MongoDB
- **Testing**: pytest, unittest, go test

#### Database Agent
- **Focus**: Schema design, migrations, queries
- **Tools**: psql, mysql, mongosh, redis-cli
- **Migrations**: Alembic, Prisma, Flyway
- **Analysis**: EXPLAIN, query optimization

#### DevOps Agent
- **Focus**: Infrastructure, deployment, CI/CD
- **Tools**: Docker, kubectl, terraform, ansible
- **Clouds**: AWS CLI, gcloud, az
- **Monitoring**: Prometheus queries, log analysis

#### Reviewer Agent
- **Focus**: Code review, security, quality
- **Tools**: Static analyzers, security scanners
- **Checks**: Linting, type checking, complexity
- **Standards**: Style guides, best practices

#### Testing Agent
- **Focus**: Writing and running tests
- **Tools**: Test frameworks, coverage tools
- **Types**: Unit, integration, E2E, performance
- **Browsers**: Playwright, Puppeteer, Selenium

#### Planner Agent
- **Focus**: Task breakdown, architecture decisions
- **Tools**: Minimal (mostly LLM reasoning)
- **Output**: Implementation plans, subtasks

### 4. Task Queue (Redis)

Manages work distribution:

```python
class TaskPriority(Enum):
    CRITICAL = 0    # Production bugs, security
    HIGH = 1        # Sprint commitments
    MEDIUM = 2      # Regular features
    LOW = 3         # Nice-to-haves
    BACKGROUND = 4  # Cleanup, docs

class TaskState(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 5. Workspace Management

#### Workspace Modes

Different tasks need different workspace isolation levels. Configurable per task:

| Mode | Use Case | How it Works |
|------|----------|--------------|
| `shared` | Multiple agents collaborate | Shared volume, git worktrees for branches |
| `isolated` | Clean environment needed | Fresh clone, container-local storage |
| `copy_on_write` | Start shared, diverge if needed | Clone from cache, own copy |

```yaml
# In tasking.yaml
tasks:
  - id: task-123
    workspace_mode: shared      # shared | isolated | copy_on_write
    workspace_source: https://github.com/acme/app.git
    branch: feature/login
```

**When to use each mode:**
- `shared`: Default. Efficient for most tasks. Agents share git objects.
- `isolated`: Security-sensitive tasks, untrusted dependencies, clean-room builds
- `copy_on_write`: Exploratory tasks that might make breaking changes

#### Workspace Structure

```
/workspaces/
├── owner-repo-1/              # "Hot" main clone (never deleted)
│   ├── .git/                  # Full git history
│   ├── src/
│   └── ...
├── owner-repo-1.worktrees/    # Git worktrees for parallel tasks (shared mode)
│   ├── task-123/              # Worktree for task 123
│   │   ├── .cloud-code/
│   │   │   ├── tasking.yaml   # Orchestrator → Agent
│   │   │   ├── reporting.yaml # Agent → Orchestrator
│   │   │   └── credentials/   # Injected secrets (encrypted)
│   │   └── src/
│   ├── task-456/
│   └── ...
├── owner-repo-2/
│   └── ...
└── isolated/                  # Isolated workspaces (isolated mode)
    ├── task-789/              # Full clone, container-local
    │   ├── .cloud-code/
    │   └── ...
    └── ...
```

**Access Control:**
- Agents have read/write to their workspace only
- Each task works on a feature branch
- Orchestrator accesses only `.cloud-code/` directory
- Isolated workspaces destroyed after task completion

### 6. Credential Management

Orchestrator controls all credential distribution via HashiCorp Vault (or simpler alternatives for MVP).

```
┌─────────────────┐
│  Orchestrator   │
│                 │
│  ┌───────────┐  │         ┌─────────────────────┐
│  │ Secrets   │◀─┼─────────│ Vault / .env.enc    │
│  │ Manager   │  │         │ (encrypted store)   │
│  └─────┬─────┘  │         └─────────────────────┘
│        │        │
└────────┼────────┘
         │ Injects only what's needed
         ▼
┌─────────────────────────────────────────────────────┐
│               Agent Container                        │
│                                                      │
│  Environment Variables (scoped, short-lived):       │
│  • GITHUB_TOKEN=ghp_***     (repo-scoped)          │
│  • NPM_TOKEN=npm_***        (only if requested)    │
│  • DATABASE_URL=***         (read-only if review)  │
└─────────────────────────────────────────────────────┘
```

#### Agent Credential Requests

Agents can request credentials they need. Orchestrator reviews and provides:

```yaml
# In reporting.yaml (agent writes)
credential_requests:
  - id: cred-req-001
    type: npm_token
    scope: "@acme:registry"
    reason: "Need to install private @acme/ui-components package"
    status: pending  # pending | approved | denied | injected
    requested_at: 2026-01-07T10:35:00Z

  - id: cred-req-002
    type: database_url
    scope: "read_only"
    reason: "Need to verify schema matches migrations"
    status: injected
    injected_at: 2026-01-07T10:36:00Z
```

#### Credential Types

| Type | Scope Options | Auto-Approve? |
|------|---------------|---------------|
| `github_token` | `repo`, `read_only`, `actions` | Yes (scoped to task repo) |
| `npm_token` | `@scope:registry`, `publish` | Yes for read, No for publish |
| `database_url` | `read_only`, `read_write`, `admin` | Yes for read_only |
| `api_key` | service-specific | No (human review) |
| `ssh_key` | `git`, `deploy` | No (human review) |

#### Secrets Manager Implementation

```python
class SecretsManager:
    """Manages credential distribution to agents."""

    def __init__(self, vault_client: VaultClient):
        self.vault = vault_client
        self.auto_approve_rules = {
            "github_token": ["repo", "read_only"],
            "npm_token": ["read"],
            "database_url": ["read_only"],
        }

    async def handle_credential_request(
        self,
        request: CredentialRequest,
        task: Task
    ) -> CredentialResponse:
        """Process a credential request from an agent."""

        # Check if auto-approvable
        if self._can_auto_approve(request):
            secret = await self._get_scoped_secret(request, task)
            await self._inject_to_workspace(secret, task.workspace)
            return CredentialResponse(status="injected")

        # Needs human review
        await self._notify_human(request, task)
        return CredentialResponse(status="pending_review")

    async def _inject_to_workspace(self, secret: Secret, workspace: Path):
        """Inject secret into agent's workspace."""
        creds_dir = workspace / ".cloud-code" / "credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)

        # Write encrypted secret file (agent has decryption key)
        secret_file = creds_dir / f"{secret.name}.enc"
        secret_file.write_bytes(self._encrypt(secret.value))

        # Or inject as environment variable via Docker
        # container.update(environment={secret.name: secret.value})
```

#### Agent System Prompt for Credentials

```markdown
## Credentials

You do NOT have direct access to API keys, tokens, or secrets.

If you need credentials for external services:
1. Add a `credential_request` to reporting.yaml
2. Specify the type, scope, and reason
3. Wait for the orchestrator to approve and inject

Example:
```yaml
credential_requests:
  - id: cred-001
    type: npm_token
    scope: "@company:registry"
    reason: "Installing private @company/shared-ui package"
    status: pending
```

Common credential types: github_token, npm_token, database_url, api_key
```

### 7. Git Worktree Caching Strategy

**Problem:** Cloning entire repos for every task wastes bandwidth, disk, and time.

**Solution:** Maintain a "hot" clone per repo, use `git worktree` for parallel task isolation.

```python
class WorkspaceManager:
    """Efficient workspace management using git worktrees."""

    async def get_workspace(self, project: Project, task: Task) -> Path:
        """Get or create workspace for task."""
        main_clone = WORKSPACES_DIR / f"{project.owner}-{project.repo}"
        worktree_dir = WORKSPACES_DIR / f"{project.owner}-{project.repo}.worktrees"
        task_worktree = worktree_dir / f"task-{task.id}"

        if not main_clone.exists():
            # First time: full clone
            await self._clone_repo(project, main_clone)
        else:
            # Subsequent: just fetch latest
            await self._fetch_repo(main_clone)

        if not task_worktree.exists():
            # Create worktree for this task
            await self._create_worktree(
                main_clone,
                task_worktree,
                task.branch_name,
                task.base_commit_sha
            )

        return task_worktree

    async def _clone_repo(self, project: Project, dest: Path):
        """Full clone (only happens once per repo)."""
        token = await get_project_token(project.id)
        url = f"https://x-access-token:{token}@github.com/{project.owner}/{project.repo}.git"
        await run_command(["git", "clone", url, str(dest)])

    async def _fetch_repo(self, repo_dir: Path):
        """Fetch latest (fast, incremental)."""
        await run_command(["git", "fetch", "--all", "--prune"], cwd=repo_dir)

    async def _create_worktree(
        self,
        main_clone: Path,
        worktree_path: Path,
        branch: str,
        base_commit: str
    ):
        """Create isolated worktree for task."""
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Create new branch from base commit
        await run_command([
            "git", "worktree", "add",
            "-b", branch,
            str(worktree_path),
            base_commit
        ], cwd=main_clone)

    async def cleanup_workspace(self, task: Task):
        """Remove worktree after task completes."""
        worktree_path = self._get_worktree_path(task)
        if worktree_path.exists():
            await run_command([
                "git", "worktree", "remove", "--force", str(worktree_path)
            ])
            # Also delete the branch if PR was merged/closed
            # (or keep for reference based on config)
```

**Benefits:**
- **First clone:** ~30 seconds for large repo
- **Subsequent tasks:** ~2-5 seconds (fetch + worktree add)
- **Parallel tasks:** Multiple worktrees share same .git objects
- **Disk efficient:** No duplicate git history
- **Clean isolation:** Each task has its own working directory

---

## Data Models

### Project

```python
class Project(BaseModel):
    id: UUID
    name: str
    github_repo: str  # "owner/repo"
    github_token: str  # Encrypted

    # Monitoring
    enabled: bool = True
    watch_issues: bool = True
    watch_prs: bool = True
    auto_assign: bool = True

    # Git config
    default_branch: str = "main"
    working_branch_prefix: str = "cloud-code/"

    # Labels
    trigger_labels: list[str] = ["cloud-code"]
    ignore_labels: list[str] = ["wontfix", "human-only"]

    # Agent preferences
    preferred_agents: dict[str, str] = {}  # task_type -> agent_type

    created_at: datetime
    updated_at: datetime
```

### Task

```python
class Task(BaseModel):
    id: UUID
    project_id: UUID

    # GitHub
    github_issue_number: int
    github_issue_url: str
    github_pr_number: Optional[int]

    # Details
    title: str
    description: str
    task_type: str  # "feature", "bugfix", "refactor", "docs", "test"
    labels: list[str]

    # State
    state: TaskState
    priority: TaskPriority

    # Assignment
    assigned_agent_type: Optional[str]
    assigned_agent_id: Optional[str]

    # Planning
    plan: Optional[TaskPlan]
    subtasks: list[Subtask]

    # Branch Management
    branch_name: str              # The specific branch this task owns
    base_commit_sha: str          # Commit task started from (for rebasing)

    # Cost Tracking & Limits
    cost_limit: float = 2.00      # Max USD per task
    current_cost: float = 0.0     # Running total

    # Human-in-the-Loop Gate
    requires_human_approval: bool = False  # Set True if Unstuck agent fails

    # Execution
    attempts: int = 0
    max_attempts: int = 3

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Errors
    last_error: Optional[str]
    blocked_reason: Optional[str]
```

### AgentLog

Structured logging for debugging and observability:

```python
class AgentLog(BaseModel):
    id: UUID
    task_id: UUID
    execution_id: UUID
    agent_id: str

    # Timing
    timestamp: datetime

    # Context
    step_count: int              # Which step of the plan is this?
    tool_call_id: Optional[str]  # Links to specific tool invocation

    # Log Content
    level: str  # "debug", "info", "warning", "error"
    category: str  # "tool_input", "tool_output", "llm_request", "llm_response", "system"
    message: str

    # Structured Data (mandatory for tool calls)
    data: dict = {}  # Tool inputs/outputs, token counts, etc.

    # Cost Attribution
    tokens_used: int = 0
    cost_usd: float = 0.0
```

### AgentWorkstation

```python
class AgentWorkstation(BaseModel):
    id: str  # container ID
    agent_type: str
    name: str  # "frontend-1", "backend-2"

    # Container
    container_id: str
    image: str
    status: str  # "running", "stopped", "error"

    # Resources
    memory_limit: str = "2g"
    cpu_limit: float = 2.0

    # State
    current_task_id: Optional[UUID]
    is_busy: bool = False
    last_health_check: datetime
    health_status: str

    # Stats
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_runtime_hours: float = 0

    # Volumes
    tools_volume: str
    workspace_volume: str

    created_at: datetime
```

### TaskExecution

```python
class TaskExecution(BaseModel):
    id: UUID
    task_id: UUID
    agent_id: str
    attempt_number: int

    # Execution
    started_at: datetime
    ended_at: Optional[datetime]
    status: str  # "running", "success", "failed"

    # LLM Usage
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0

    # Results
    files_changed: list[str] = []
    commits: list[str] = []
    output_summary: Optional[str]
    error: Optional[str]

    # Logs
    log_file: str  # Path to detailed log
```

---

## Agent System

### File-Based Task Interface

Communication between orchestrator and agents uses a simple dual-file system. Each side writes to their own file, reads from the other. No HTTP APIs, no message queues, no conflicts.

```
workspace/.cloud-code/
├── tasking.yaml      # Orchestrator writes → Agent reads
├── reporting.yaml    # Agent writes → Orchestrator reads
└── config.yaml       # Read-only configuration
```

**Why this approach:**
- **No concurrent write conflicts** - Single writer per file
- **Agent-agnostic** - Works with any coding CLI (Claude Code, Aider, Codex, etc.)
- **Debuggable** - `cat tasking.yaml` shows current state
- **Resumable** - Agent restarts, reads file, continues
- **Simple** - No protocol translation, no HTTP overhead

### Tasking File (Orchestrator → Agent)

```yaml
# .cloud-code/tasking.yaml
# Orchestrator writes this, Agent only reads

version: 1
updated_at: 2026-01-07T10:30:00Z
workspace: /workspaces/acme-app.worktrees/task-123

tasks:
  - id: task-123
    title: Implement user login form
    status: assigned  # assigned | cancelled
    priority: high
    branch: feature/login-form

    description: |
      Create a login form component with email/password validation.
      Use the existing AuthContext for state management.

    acceptance_criteria:
      - Form renders with email and password fields
      - Client-side validation for email format and password length
      - Submit calls POST /api/auth/login
      - Success redirects to /dashboard
      - Error displays message from API

    context:
      related_files:
        - src/contexts/AuthContext.tsx
        - src/api/auth.ts
      dependencies: []

  - id: task-124
    title: Add unit tests for login form
    status: assigned
    priority: medium
    depends_on: [task-123]
    description: |
      Write Jest tests for the LoginForm component.
```

### Reporting File (Agent → Orchestrator)

The reporting format is rich enough for the orchestrator to post meaningful updates to GitHub/GitLab.

```yaml
# .cloud-code/reporting.yaml
# Agent writes this, Orchestrator only reads

version: 1
agent_type: claude-code
agent_id: frontend-1
updated_at: 2026-01-07T10:45:00Z

status: working  # idle | working | error

tasks:
  task-123:
    status: in_progress  # received | planning | in_progress | blocked | completed | failed
    started_at: 2026-01-07T10:31:00Z
    current_step: "Implementing form validation"

    # Human-readable summary for GitHub issue comments
    summary: |
      Implemented LoginForm component with email/password validation.
      Currently integrating with existing AuthContext for state management.

    # Structured progress log
    progress:
      - timestamp: 2026-01-07T10:31:00Z
        status: received
        message: Task acknowledged
      - timestamp: 2026-01-07T10:32:00Z
        status: planning
        message: Analyzing existing AuthContext implementation
        details:
          files_read: [src/contexts/AuthContext.tsx, src/api/auth.ts]
      - timestamp: 2026-01-07T10:35:00Z
        status: in_progress
        message: Creating LoginForm component
        details:
          files_created: [src/components/LoginForm.tsx]
          lines_added: 87
      - timestamp: 2026-01-07T10:42:00Z
        status: in_progress
        message: Implementing form validation
        details:
          files_modified: [src/components/LoginForm.tsx]
          tests_passing: true

    # For PR description generation
    changes_summary:
      - "Added LoginForm component with email/password fields"
      - "Implemented client-side validation (email format, password length)"
      - "Integrated with AuthContext for authentication state"
      - "Added unit tests (8 passing)"

    # File changes with details
    files_modified:
      - path: src/components/LoginForm.tsx
        change_type: created
        lines_added: 87
        lines_removed: 0
      - path: src/components/LoginForm.test.tsx
        change_type: created
        lines_added: 45
        lines_removed: 0
      - path: src/contexts/AuthContext.tsx
        change_type: modified
        lines_added: 12
        lines_removed: 3

    # Git commits made
    commits:
      - sha: abc1234
        message: "feat: add LoginForm component with validation"
      - sha: def5678
        message: "test: add LoginForm unit tests"

    # Acceptance criteria status
    acceptance_criteria:
      - criterion: "Form renders with email and password fields"
        status: done
      - criterion: "Client-side validation for email format and password length"
        status: done
      - criterion: "Submit calls POST /api/auth/login"
        status: in_progress
      - criterion: "Success redirects to /dashboard"
        status: pending

    # Error/blocking info
    error: null
    blocked_reason: null

    # Credential requests (see Credential Management section)
    credential_requests: []

  task-124:
    status: waiting  # Not started yet, depends on task-123
```

#### GitHub/GitLab Update Generation

The orchestrator uses the reporting data to generate updates:

```python
def generate_github_comment(task_report: dict) -> str:
    """Generate GitHub issue comment from agent report."""
    lines = [
        f"## 🤖 Agent Update",
        f"**Status:** {task_report['status']}",
        f"**Current Step:** {task_report['current_step']}",
        "",
        "### Summary",
        task_report.get('summary', 'Working on task...'),
        "",
        "### Progress",
    ]

    for p in task_report.get('progress', [])[-5:]:  # Last 5 entries
        lines.append(f"- {p['timestamp']}: {p['message']}")

    if task_report.get('acceptance_criteria'):
        lines.append("")
        lines.append("### Acceptance Criteria")
        for ac in task_report['acceptance_criteria']:
            icon = "✅" if ac['status'] == 'done' else "🔄" if ac['status'] == 'in_progress' else "⬜"
            lines.append(f"- {icon} {ac['criterion']}")

    return "\n".join(lines)

def generate_pr_body(task_report: dict, task: Task) -> str:
    """Generate PR description from agent report."""
    lines = [
        f"## Summary",
        "",
        f"Closes #{task.github_issue_number}",
        "",
    ]

    for change in task_report.get('changes_summary', []):
        lines.append(f"- {change}")

    lines.extend([
        "",
        "## Changes",
        "",
    ])

    for f in task_report.get('files_modified', []):
        lines.append(f"- `{f['path']}` ({f['change_type']}: +{f['lines_added']}/-{f['lines_removed']})")

    lines.extend([
        "",
        "---",
        "🤖 *Generated by Cloud Code*",
    ])

    return "\n".join(lines)
```

### Agent Loop

The agent runs a simple loop: check for tasks, work on them, report progress.

```python
# agent_loop.py - Runs inside each agent container

class AgentLoop:
    """Main loop running inside agent container."""

    def __init__(self, workspace: Path, agent_type: str, coding_cli: str = "claude-code"):
        self.workspace = workspace
        self.agent_type = agent_type
        self.coding_cli = coding_cli  # "claude-code", "aider", "codex-cli"
        self.tasking_file = workspace / ".cloud-code" / "tasking.yaml"
        self.reporting_file = workspace / ".cloud-code" / "reporting.yaml"

    async def run(self):
        """Main agent loop."""
        while True:
            # Read current tasks
            tasking = self.read_tasking_file()

            # Find next task to work on
            task = self.select_next_task(tasking)

            if task:
                await self.execute_task(task)
            else:
                # Idle - check less frequently
                await asyncio.sleep(10)

    def select_next_task(self, tasking: dict) -> Optional[dict]:
        """Select highest priority non-blocked task."""
        reporting = self.read_reporting_file()

        for task in sorted(tasking["tasks"], key=lambda t: t["priority"]):
            task_status = reporting.get("tasks", {}).get(task["id"], {})
            status = task_status.get("status", "pending")

            # Skip completed, failed, or blocked tasks
            if status in ("completed", "failed", "blocked"):
                continue

            # Skip if dependencies not met
            if not self.dependencies_met(task, reporting):
                continue

            return task

        return None

    async def execute_task(self, task: dict):
        """Execute a single task using the configured coding CLI."""
        task_id = task["id"]

        # Update status: received
        self.update_task_status(task_id, "received", "Task acknowledged")

        # Update status: planning
        self.update_task_status(task_id, "planning", "Analyzing task requirements")

        # Prepare task context for the coding CLI
        task_prompt = self.build_task_prompt(task)

        # Update status: in_progress
        self.update_task_status(task_id, "in_progress", "Starting implementation")

        try:
            # Run the actual coding CLI
            result = await self.run_coding_cli(task, task_prompt)

            if result.success:
                self.update_task_status(task_id, "completed", "Task completed successfully")
            elif result.needs_different_agent:
                self.update_task_status(
                    task_id, "blocked",
                    message="Needs different approach",
                    blocked_reason="recommend_handoff"
                )
            else:
                self.update_task_status(task_id, "failed", error=result.error)

        except Exception as e:
            self.update_task_status(task_id, "failed", error=str(e))

    async def run_coding_cli(self, task: dict, prompt: str) -> CLIResult:
        """Run the coding CLI (claude-code, aider, etc.)."""
        if self.coding_cli == "claude-code":
            # Claude Code CLI
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                "--allowedTools", "Edit,Write,Bash,Read",
                cwd=self.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return CLIResult(success=proc.returncode == 0, output=stdout.decode())

        elif self.coding_cli == "aider":
            # Aider CLI
            proc = await asyncio.create_subprocess_exec(
                "aider", "--message", prompt, "--yes",
                cwd=self.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return CLIResult(success=proc.returncode == 0, output=stdout.decode())

        # Add more CLIs as needed...

    def update_task_status(
        self,
        task_id: str,
        status: str,
        message: str = None,
        error: str = None,
        blocked_reason: str = None
    ):
        """Update reporting.yaml with current task status."""
        reporting = self.read_reporting_file()

        if "tasks" not in reporting:
            reporting["tasks"] = {}

        if task_id not in reporting["tasks"]:
            reporting["tasks"][task_id] = {"progress": []}

        task_report = reporting["tasks"][task_id]
        task_report["status"] = status
        task_report["progress"].append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "message": message
        })

        if error:
            task_report["error"] = error
        if blocked_reason:
            task_report["blocked_reason"] = blocked_reason

        reporting["updated_at"] = datetime.utcnow().isoformat() + "Z"

        # Atomic write
        tmp_file = self.reporting_file.with_suffix(".tmp")
        tmp_file.write_text(yaml.dump(reporting))
        tmp_file.rename(self.reporting_file)

    def read_tasking_file(self) -> dict:
        """Read tasking.yaml (written by orchestrator)."""
        if not self.tasking_file.exists():
            return {"tasks": []}
        return yaml.safe_load(self.tasking_file.read_text())

    def read_reporting_file(self) -> dict:
        """Read reporting.yaml (written by this agent)."""
        if not self.reporting_file.exists():
            return {"tasks": {}}
        return yaml.safe_load(self.reporting_file.read_text())
```

### Orchestrator Task Management

The orchestrator writes tasks and monitors progress:

```python
class TaskManager:
    """Orchestrator-side task management."""

    async def assign_task(self, task: Task, workspace: Path):
        """Assign task to an agent workspace."""
        tasking_file = workspace / ".cloud-code" / "tasking.yaml"

        # Read current tasking
        tasking = yaml.safe_load(tasking_file.read_text()) if tasking_file.exists() else {"tasks": []}

        # Add or update task
        tasking["tasks"] = [t for t in tasking["tasks"] if t["id"] != task.id]
        tasking["tasks"].append(task.to_dict())
        tasking["updated_at"] = datetime.utcnow().isoformat() + "Z"

        # Atomic write
        tmp_file = tasking_file.with_suffix(".tmp")
        tmp_file.write_text(yaml.dump(tasking))
        tmp_file.rename(tasking_file)

    async def check_progress(self, workspace: Path) -> dict:
        """Check agent progress from reporting.yaml."""
        reporting_file = workspace / ".cloud-code" / "reporting.yaml"

        if not reporting_file.exists():
            return {"status": "no_report"}

        return yaml.safe_load(reporting_file.read_text())

    async def monitor_workspaces(self, workspaces: list[Path]):
        """Monitor all agent workspaces for updates."""
        while True:
            for workspace in workspaces:
                report = await self.check_progress(workspace)

                for task_id, task_status in report.get("tasks", {}).items():
                    if task_status["status"] == "completed":
                        await self.handle_task_completed(task_id, workspace)
                    elif task_status["status"] == "failed":
                        await self.handle_task_failed(task_id, task_status)
                    elif task_status["status"] == "blocked":
                        await self.handle_task_blocked(task_id, task_status)

            await asyncio.sleep(5)  # Check every 5 seconds
```

### Inter-Agent Communication

Agents can request help from specialists. Requests go through the file system:

```yaml
# .cloud-code/requests.yaml (optional, for specialist requests)
requests:
  - id: req-001
    from_task: task-123
    to_specialist: reviewer
    status: pending  # pending | in_progress | completed
    question: |
      Please review this LoginForm component for security issues,
      especially around input validation and XSS prevention.
    response: null
```

The orchestrator monitors requests and routes to appropriate specialists:

```python
async def handle_specialist_request(request: dict):
    """Route specialist request to appropriate agent."""
    specialist_workspace = get_workspace_for_agent_type(request["to_specialist"])

    # Add as a task to the specialist's tasking.yaml
    specialist_task = Task(
        id=f"review-{request['id']}",
        title=f"Review request from {request['from_task']}",
        description=request["question"],
        priority="high",
        task_type="review"
    )

    await assign_task(specialist_task, specialist_workspace)
```

### Coding CLI Abstraction

Support multiple coding CLIs with a common interface:

```python
class CodingCLI(Protocol):
    """Interface for coding CLIs."""

    async def execute(self, prompt: str, workspace: Path) -> CLIResult: ...

class ClaudeCodeCLI(CodingCLI):
    async def execute(self, prompt: str, workspace: Path) -> CLIResult:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt,
            cwd=workspace, stdout=PIPE, stderr=PIPE
        )
        stdout, _ = await proc.communicate()
        return CLIResult(success=proc.returncode == 0, output=stdout.decode())

class AiderCLI(CodingCLI):
    async def execute(self, prompt: str, workspace: Path) -> CLIResult:
        proc = await asyncio.create_subprocess_exec(
            "aider", "--message", prompt, "--yes",
            cwd=workspace, stdout=PIPE, stderr=PIPE
        )
        stdout, _ = await proc.communicate()
        return CLIResult(success=proc.returncode == 0, output=stdout.decode())

# Factory
def get_coding_cli(name: str) -> CodingCLI:
    return {
        "claude-code": ClaudeCodeCLI(),
        "aider": AiderCLI(),
        "codex-cli": CodexCLI(),
    }[name]
```

### Agent Handoff

When one agent can't solve a task, it marks it blocked and orchestrator reassigns:

```python
# In agent: mark as blocked
self.update_task_status(
    task_id,
    status="blocked",
    message="Unable to resolve TypeScript type errors after 3 attempts",
    blocked_reason="recommend_handoff:aider"  # Suggest alternative
)

# In orchestrator: handle handoff
async def handle_task_blocked(self, task_id: str, status: dict):
    if status.get("blocked_reason", "").startswith("recommend_handoff"):
        suggested_cli = status["blocked_reason"].split(":")[1]

        # Reassign to different agent container
        new_workspace = get_workspace_for_cli(suggested_cli)
        task = await self.get_task(task_id)
        task.attempts += 1

        if task.attempts < task.max_attempts:
            await self.assign_task(task, new_workspace)
        else:
            # Escalate to human
            task.requires_human_approval = True
            await self.notify_human(task)
```

### Tool System

Tools are available to agents with NO restrictions:

```python
AGENT_TOOLS = [
    # File operations - unrestricted
    {
        "name": "run_command",
        "description": "Run ANY shell command. You have full access.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 300},
                "cwd": {"type": "string", "description": "Working directory"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to any file path",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Read any file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    },
    # Git - full access
    {
        "name": "git",
        "description": "Run any git command",
        "input_schema": {
            "type": "object",
            "properties": {
                "args": {"type": "string", "description": "Git arguments"}
            },
            "required": ["args"]
        }
    },
    # Install tools
    {
        "name": "install_tool",
        "description": "Install any tool you need (apt, npm, pip, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Install command"}
            },
            "required": ["command"]
        }
    },
    # Network
    {
        "name": "http_request",
        "description": "Make HTTP requests",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "url": {"type": "string"},
                "headers": {"type": "object"},
                "body": {"type": "string"}
            },
            "required": ["method", "url"]
        }
    },
    # GitHub API
    {
        "name": "github_api",
        "description": "Call GitHub API",
        "input_schema": {
            "type": "object",
            "properties": {
                "endpoint": {"type": "string"},
                "method": {"type": "string", "default": "GET"},
                "data": {"type": "object"}
            },
            "required": ["endpoint"]
        }
    },
    # Request help from other agents
    {
        "name": "ask_specialist",
        "description": "Ask another specialist agent for help",
        "input_schema": {
            "type": "object",
            "properties": {
                "specialist": {
                    "type": "string",
                    "enum": ["frontend", "backend", "database", "devops", "reviewer", "testing"]
                },
                "question": {"type": "string"}
            },
            "required": ["specialist", "question"]
        }
    }
]
```

---

## Container Architecture

### Base Images

Custom Dockerfiles for each agent type:

```dockerfile
# dockerfiles/frontend.Dockerfile
FROM node:20-bookworm

# System tools
RUN apt-get update && apt-get install -y \
    git curl wget jq ripgrep fd-find \
    && rm -rf /var/lib/apt/lists/*

# Node tools
RUN npm install -g \
    yarn pnpm \
    typescript ts-node \
    eslint prettier \
    @playwright/test

# Agent daemon
COPY agent_daemon /opt/agent
RUN pip install -r /opt/agent/requirements.txt

# Volumes
VOLUME /tools    # Persistent tools/cache
VOLUME /workspace  # Shared workspace

WORKDIR /workspace
EXPOSE 8080

CMD ["python", "/opt/agent/daemon.py", "--type", "frontend"]
```

```dockerfile
# dockerfiles/backend.Dockerfile
FROM python:3.12-bookworm

# System tools
RUN apt-get update && apt-get install -y \
    git curl wget jq ripgrep fd-find \
    postgresql-client redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Python tools
RUN pip install uv poetry pipx
RUN pipx install ruff mypy pytest

# Agent daemon
COPY agent_daemon /opt/agent
RUN pip install -r /opt/agent/requirements.txt

VOLUME /tools
VOLUME /workspace

WORKDIR /workspace
EXPOSE 8080

CMD ["python", "/opt/agent/daemon.py", "--type", "backend"]
```

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  # Orchestrator
  orchestrator:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://cloudcode:cloudcode@postgres:5432/cloudcode
      - REDIS_URL=redis://redis:6379
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - workspaces:/workspaces
    depends_on:
      - postgres
      - redis

  # Agent: Frontend
  agent-frontend:
    build:
      context: .
      dockerfile: dockerfiles/frontend.Dockerfile
    volumes:
      - frontend-tools:/tools
      - workspaces:/workspace
    networks:
      - agents

  # Agent: Backend
  agent-backend:
    build:
      context: .
      dockerfile: dockerfiles/backend.Dockerfile
    volumes:
      - backend-tools:/tools
      - workspaces:/workspace
    networks:
      - agents

  # Agent: Reviewer
  agent-reviewer:
    build:
      context: .
      dockerfile: dockerfiles/reviewer.Dockerfile
    volumes:
      - reviewer-tools:/tools
      - workspaces:/workspace
    networks:
      - agents

  # Infrastructure
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: cloudcode
      POSTGRES_PASSWORD: cloudcode
      POSTGRES_DB: cloudcode
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  workspaces:
  postgres_data:
  redis_data:
  frontend-tools:
  backend-tools:
  reviewer-tools:

networks:
  agents:
    driver: bridge
```

### Container Management

```python
# src/cloud_code/containers/manager.py

from python_on_whales import DockerClient

class ContainerManager:
    """Manages agent container lifecycle."""

    def __init__(self):
        self.docker = DockerClient()
        self.agents: dict[str, Container] = {}

    async def provision_agent(
        self,
        agent_type: str,
        name: Optional[str] = None
    ) -> Container:
        """Create a new agent workstation."""
        name = name or f"{agent_type}-{uuid4().hex[:8]}"

        container = self.docker.container.run(
            image=f"cloud-code-{agent_type}:latest",
            name=name,
            detach=True,
            volumes=[
                f"{agent_type}-tools:/tools",
                "workspaces:/workspace"
            ],
            networks=["cloud-code-agents"],
            mem_limit="2g",
            cpus=2.0,
            restart="unless-stopped",
            labels={
                "cloud-code.agent-type": agent_type,
                "cloud-code.managed": "true"
            }
        )

        self.agents[name] = container
        return container

    async def execute_in_agent(
        self,
        agent_name: str,
        task: Task
    ) -> TaskResult:
        """Execute task in agent container."""
        container = self.agents[agent_name]

        # Call agent's HTTP API
        response = httpx.post(
            f"http://{container.name}:8080/execute",
            json=task.dict(),
            timeout=3600  # 1 hour max
        )

        return TaskResult(**response.json())

    async def get_available_agent(self, agent_type: str) -> Optional[str]:
        """Get an idle agent of the specified type."""
        for name, container in self.agents.items():
            if not name.startswith(agent_type):
                continue

            health = httpx.get(f"http://{name}:8080/health")
            if health.json().get("busy") is False:
                return name

        return None

    async def scale(self, agent_type: str, count: int):
        """Scale agent pool to specified count."""
        current = len([n for n in self.agents if n.startswith(agent_type)])

        if count > current:
            # Scale up
            for i in range(count - current):
                await self.provision_agent(agent_type)
        elif count < current:
            # Scale down (remove idle agents)
            # ...
```

---

## Security Model

### Container Isolation (Primary Security)

**No command restrictions inside containers.** Security comes from isolation:

```
┌─────────────────────────────────────────────────────────────┐
│                      HOST VPS                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  ORCHESTRATOR                        │    │
│  │  • No access to workspace files directly            │    │
│  │  • Only communicates via Docker API                 │    │
│  │  • Stores encrypted secrets in database             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              AGENT CONTAINERS                        │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐       │    │
│  │  │ Frontend  │  │ Backend   │  │ Reviewer  │       │    │
│  │  │           │  │           │  │           │       │    │
│  │  │ FULL      │  │ FULL      │  │ FULL      │       │    │
│  │  │ FREEDOM   │  │ FREEDOM   │  │ FREEDOM   │       │    │
│  │  │           │  │           │  │           │       │    │
│  │  │ Can rm -rf│  │ Can rm -rf│  │ Can rm -rf│       │    │
│  │  │ Only kills│  │ Only kills│  │ Only kills│       │    │
│  │  │ container │  │ container │  │ container │       │    │
│  │  └───────────┘  └───────────┘  └───────────┘       │    │
│  │                                                      │    │
│  │  Network: Isolated, only reach orchestrator API     │    │
│  │  Volumes: Workspace (shared), Tools (per-agent)     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### What Agents CAN Do (Inside Container):
- Run ANY shell command
- Install ANY software
- Modify ANY file in workspace
- Make network requests
- Use full system resources (within limits)

### What Agents CANNOT Do:
- Access host filesystem (except mounted volumes)
- Access other containers' data
- Access orchestrator database
- Make changes outside workspace without going through orchestrator
- Push to GitHub without orchestrator mediation

### Network Isolation

```yaml
# docker-compose.yml
networks:
  # Agents can only talk to orchestrator
  agents:
    driver: bridge
    internal: true  # No internet access

  # Orchestrator can talk to internet
  external:
    driver: bridge
```

For agents that need internet (npm install, pip install):
- Orchestrator proxies requests
- Or: Allow specific registries via firewall rules
- Or: Use local registry mirrors

### Secrets Management

```python
# Secrets never reach agent containers directly
class SecretsManager:
    """Manages secrets for agents."""

    def get_github_token_for_task(self, task: Task) -> str:
        """Generate a scoped, short-lived token for the task."""
        # Use GitHub App installation tokens
        # Scoped to specific repo
        # Expires after task completion
        pass

    def inject_secrets(self, container: Container, task: Task):
        """Inject required secrets into container environment."""
        # Secrets injected as env vars
        # Rotated after task completion
        pass
```

### Resource Limits

```python
AGENT_RESOURCE_LIMITS = {
    "frontend": {"memory": "2g", "cpus": 2.0, "pids": 100},
    "backend": {"memory": "2g", "cpus": 2.0, "pids": 100},
    "database": {"memory": "1g", "cpus": 1.0, "pids": 50},
    "devops": {"memory": "2g", "cpus": 2.0, "pids": 200},
    "reviewer": {"memory": "1g", "cpus": 1.0, "pids": 50},
    "testing": {"memory": "4g", "cpus": 2.0, "pids": 200},
    "planner": {"memory": "512m", "cpus": 1.0, "pids": 20},
}
```

---

## GitHub Integration

### Webhook Handler

```python
@app.post("/api/webhooks/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    event = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    if event == "issues":
        await handle_issue_event(payload)
    elif event == "issue_comment":
        await handle_comment_event(payload)
    elif event == "pull_request":
        await handle_pr_event(payload)
    elif event == "pull_request_review":
        await handle_review_event(payload)

async def handle_issue_event(payload: dict):
    """Process issue events."""
    action = payload["action"]
    issue = payload["issue"]
    labels = [l["name"] for l in issue["labels"]]

    if action == "opened" and "cloud-code" in labels:
        # New task!
        task = await create_task_from_issue(issue)
        await task_queue.enqueue(task)

    elif action == "labeled":
        if "cloud-code" in labels:
            task = await create_task_from_issue(issue)
            await task_queue.enqueue(task)
```

### Task-to-Agent Routing

```python
class TaskRouter:
    """Routes tasks to appropriate agent types."""

    ROUTING_RULES = {
        # By label
        "frontend": ["frontend", "ui", "css", "react", "vue"],
        "backend": ["backend", "api", "python", "node"],
        "database": ["database", "schema", "migration", "sql"],
        "devops": ["devops", "deployment", "ci", "docker"],
        "testing": ["test", "e2e", "integration"],
    }

    async def route_task(self, task: Task) -> str:
        """Determine which agent type should handle task."""
        labels = task.labels

        for agent_type, keywords in self.ROUTING_RULES.items():
            if any(kw in labels for kw in keywords):
                return agent_type

        # Default: use planner to analyze and decide
        plan = await self.analyze_with_planner(task)
        return plan.recommended_agent
```

### PR Creation

```python
async def create_pull_request(task: Task, execution: TaskExecution):
    """Create PR after agent completes work."""
    github = Github(get_project_token(task.project_id))
    repo = github.get_repo(task.project.github_repo)

    pr = repo.create_pull(
        title=f"[Cloud Code] {task.title}",
        body=generate_pr_body(task, execution),
        head=execution.branch,
        base=task.project.default_branch
    )

    # Link to issue
    pr.create_issue_comment(f"Closes #{task.github_issue_number}")

    # Update task
    task.github_pr_number = pr.number
    task.state = TaskState.REVIEW
    await task.save()
```

---

## Web Interface

### Dashboard (htmx + Tailwind)

Minimal monitoring interface:

```
┌─────────────────────────────────────────────────────────────┐
│  Cloud Code                          [Settings] [Logs]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Agent Fleet                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Frontend │ │ Backend  │ │ Reviewer │ │ Testing  │       │
│  │    ●     │ │    ●     │ │    ○     │ │    ○     │       │
│  │ Working  │ │  Idle    │ │  Idle    │ │  Idle    │       │
│  │ Task #42 │ │          │ │          │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                             │
│  Active Tasks                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ #42  Add dark mode toggle        Frontend  ████░░ 60%│   │
│  │ #38  Fix login redirect          Backend   ██████ Done│   │
│  │ #35  Update API docs             Backend   Queued    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Recent Activity                               [View All →] │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 12:34  frontend-1  Created branch cloud-code/42     │   │
│  │ 12:33  frontend-1  Analyzing codebase...            │   │
│  │ 12:32  frontend-1  Received task #42                │   │
│  │ 12:30  backend-1   Completed task #38 ✓             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Real-time Updates

```html
<!-- Live agent status -->
<div hx-ext="sse" sse-connect="/api/stream/agents">
    <div sse-swap="agent-status" hx-swap="innerHTML">
        <!-- Updated via SSE -->
    </div>
</div>

<!-- Live logs -->
<div hx-ext="sse" sse-connect="/api/stream/logs">
    <div sse-swap="log" hx-swap="afterbegin">
        <!-- New logs prepended -->
    </div>
</div>
```

---

## Implementation Phases

> **Note:** Phases are sequential but don't include time estimates. Complexity varies based on familiarity with the stack.

### Phase 1: Foundation
**Goal: Basic orchestrator infrastructure**

- [ ] Project structure with uv, FastAPI app skeleton
- [ ] PostgreSQL models, Alembic migrations
- [ ] Docker container management (python-on-whales)
- [ ] Redis setup for task queue
- [ ] Configuration management (pydantic-settings)
- [ ] Basic health check endpoints

**Deliverable:** Orchestrator runs, can connect to DB and Redis

### Phase 2: Vertical Slice (CRITICAL)
**Goal: One complete flow end-to-end: Issue → PR**

This is the most important phase. Build a hard-coded pipeline for ONE flow before adding flexibility:

```
1. Read GitHub Issue
2. Create feature branch from base
3. Agent edits a file
4. Agent commits and pushes
5. Create PR linking to issue
```

**Tasks:**
- [ ] GitHub App setup (webhooks, permissions, authentication)
- [ ] Webhook receiver for `issues.opened` event
- [ ] Single backend agent Dockerfile with claude-code
- [ ] File-based task interface (tasking.yaml / reporting.yaml)
- [ ] Agent loop: read tasks, execute with coding CLI, report status
- [ ] Git operations: clone/fetch, branch, commit, push
- [ ] PR creation via GitHub API
- [ ] Basic error handling and retries

**Why this approach:**
- GitHub API complexity (auth, rate limits, permissions) is often underestimated
- Validates the entire architecture with real feedback
- Easier to iterate on working system than assemble pieces later

**Deliverable:** Create labeled issue → agent creates PR with changes

### Phase 3: Workspace Management
**Goal: Efficient repo handling at scale**

- [ ] Git worktree caching (avoid full clones)
- [ ] Hot repo cache with `git fetch` + `git worktree add`
- [ ] Workspace cleanup and garbage collection
- [ ] Base commit tracking for rebasing
- [ ] Conflict detection and handling

**Deliverable:** Fast workspace creation, efficient disk usage

### Phase 4: Multi-Agent Fleet
**Goal: Specialized agents for different tasks**

- [ ] Frontend agent Dockerfile (Node.js, React tooling)
- [ ] Reviewer agent Dockerfile (linting, security scanning)
- [ ] Testing agent Dockerfile (pytest, jest)
- [ ] DevOps agent Dockerfile (Docker, CI/CD tools)
- [ ] Agent pool management (spin up/down)
- [ ] Task routing by labels/content analysis
- [ ] Cost tracking per task and agent

**Deliverable:** Right agent for right task, cost visibility

### Phase 5: Inter-Agent Collaboration
**Goal: Agents work together on complex tasks**

- [ ] `ask_specialist` tool for agent-to-agent requests
- [ ] Request routing through orchestrator
- [ ] Parallel subtask execution
- [ ] Review → fix feedback loops
- [ ] Unstuck agent for blocked tasks
- [ ] Human-in-the-loop escalation

**Deliverable:** Complex tasks split across specialists

### Phase 6: Web Dashboard
**Goal: Monitoring and control UI**

- [ ] Dashboard with agent fleet status (htmx)
- [ ] Task queue view with priority
- [ ] Real-time logs via SSE
- [ ] Cost tracking dashboard
- [ ] Manual controls (stop, retry, reassign)
- [ ] Settings and configuration page

**Deliverable:** Full visibility and control

### Phase 7: Production Hardening
**Goal: Reliable, scalable deployment**

- [ ] Agent auto-scaling based on queue depth
- [ ] Graceful error recovery
- [ ] Resource monitoring and alerts
- [ ] Multi-project support
- [ ] Rate limit handling (GitHub, LLM APIs)
- [ ] Security audit
- [ ] Documentation

**Deliverable:** Production-ready system

---

## Tech Stack

### Core
| Component | Technology | Why |
|-----------|------------|-----|
| Language | Python 3.12 | AI ecosystem, rapid dev |
| Package Manager | uv | 10-100x faster installs (critical for container rebuilds) |
| Web Framework | FastAPI | Async, modern |
| Container Management | python-on-whales | Clean Docker API |
| Task Queue | Redis + Celery | Reliable |
| Database | PostgreSQL | Robust |

### Containers
| Component | Technology | Why |
|-----------|------------|-----|
| Runtime | Docker | Standard |
| Orchestration | Docker Compose (dev), Swarm/K8s (prod) | Scalable |
| Base Images | Official language images | Maintained |

### AI/LLM
| Component | Technology | Why |
|-----------|------------|-----|
| LLM Proxy | LiteLLM | Standardized API, retries/backoff, model swapping via config |
| Primary | Claude (Anthropic) | Best for code |
| Fallback | GPT-4 / Llama / Local | Second opinions, cost optimization |
| Embeddings | OpenAI / Voyage | RAG |

**LiteLLM Benefits:**
- Unified API across all providers (Anthropic, OpenAI, Azure, local models)
- Built-in retry logic with exponential backoff
- Model fallback chains (try Claude, fall back to GPT-4, then local)
- Usage tracking and cost monitoring per-request
- Swap models via config without code changes

### Frontend
| Component | Technology | Why |
|-----------|------------|-----|
| UI | htmx + Tailwind | Simple, fast |
| Real-time | SSE | Native support |

---

## File Structure (Updated)

```
cloud-code/
├── DESIGN.md
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile                    # Orchestrator
│
├── dockerfiles/                  # Agent images
│   ├── frontend.Dockerfile
│   ├── backend.Dockerfile
│   ├── database.Dockerfile
│   ├── devops.Dockerfile
│   ├── reviewer.Dockerfile
│   └── testing.Dockerfile
│
├── src/
│   └── cloud_code/
│       ├── __init__.py
│       ├── main.py               # FastAPI orchestrator
│       ├── config.py
│       │
│       ├── api/                  # REST endpoints
│       │   ├── projects.py
│       │   ├── tasks.py
│       │   ├── agents.py
│       │   └── webhooks.py
│       │
│       ├── containers/           # Docker management
│       │   ├── manager.py
│       │   ├── images.py
│       │   └── health.py
│       │
│       ├── tasks/                # Task processing
│       │   ├── queue.py
│       │   ├── router.py
│       │   └── executor.py
│       │
│       ├── github/               # GitHub integration
│       │   ├── client.py
│       │   ├── webhooks.py
│       │   └── pr.py
│       │
│       ├── db/                   # Database
│       │   ├── models.py
│       │   └── session.py
│       │
│       └── web/                  # Dashboard
│           ├── templates/
│           └── static/
│
├── agent_daemon/                 # Runs inside containers
│   ├── daemon.py
│   ├── tools.py
│   ├── llm.py
│   └── requirements.txt
│
├── prompts/                      # Agent prompts
│   ├── frontend.md
│   ├── backend.md
│   ├── database.md
│   ├── reviewer.md
│   └── testing.md
│
└── tests/
```

---

*Document version: 0.2.0*
*Last updated: January 2026*
