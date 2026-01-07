# Cloud Code

**Autonomous AI-Powered Development Platform**

Cloud Code is a VPS-based platform that turns GitHub Issues into Pull Requests using autonomous coding agents. It supports multiple coding CLIs (Claude Code, Aider, Codex, Gemini) running in isolated Docker containers.

## How It Works

```
GitHub Issue (with 'cloud-code' label)
    ↓ Webhook
Orchestrator (FastAPI)
    ↓ Provisions container
Agent Container (Docker)
    ↓ Runs coding CLI
    ↓ Commits changes
    ↓ Reports via YAML files
Orchestrator
    ↓ Creates PR
GitHub Pull Request
```

## Features

- **GitHub App Integration** - Automatic webhook setup, OAuth authentication
- **Multiple Coding CLIs** - Claude Code, Aider, Codex, Gemini, Continue, Cursor
- **Container Isolation** - Each agent runs in its own Docker container
- **Secure Credentials** - API keys stored in HashiCorp Vault
- **File-Based Communication** - Agents communicate via tasking.yaml/reporting.yaml
- **Web UI** - Setup wizard, dashboard, and credential management

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+
- A VPS with public IP (for GitHub webhooks)

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/cloud-code.git
cd cloud-code

# Copy environment file
cp .env.example .env
# Edit .env with your settings (at minimum, set SECRET_KEY)

# Start services
docker-compose up -d
```

### 2. Access Setup Wizard

Open http://your-vps-ip:8000/setup and:

1. **Create GitHub App** at github.com/settings/apps
   - Set webhook URL to http://your-vps-ip:8000/webhooks/github/
   - Enable permissions: Issues, Pull Requests, Contents (Read and Write)
   - Subscribe to: Issues, Issue comments, Pull requests
   - Generate private key

2. **Enter GitHub App credentials** in the setup wizard

3. **Configure API keys** for your preferred coding CLIs:
   - Anthropic API key (for Claude Code, Aider)
   - OpenAI API key (for Codex, Aider)
   - Google API key (for Gemini)

4. **Install on repositories** you want Cloud Code to monitor

### 3. Use It

Add the cloud-code label to any GitHub issue, or comment /cloud-code run.

## Project Structure

```
cloud-code/
├── src/cloud_code/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration management
│   ├── core/                   # Core infrastructure
│   ├── github/                 # GitHub integration
│   ├── api/                    # REST API endpoints
│   ├── agent_control_plane/    # Runs inside containers
│   └── db/                     # Database models
├── docker/agents/              # Agent container Dockerfiles
├── docker-compose.yml          # Orchestrator + dependencies
└── docs/                       # Documentation
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Detailed system architecture
- [Setup Guide](docs/SETUP.md) - VPS deployment instructions  
- [Development](docs/DEVELOPMENT.md) - Contributing and next steps

## Current Status

**Phase: Vertical Slice (MVP)**

Core infrastructure complete. See docs/DEVELOPMENT.md for remaining tasks.

## License

MIT
