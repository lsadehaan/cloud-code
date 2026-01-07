# Cloud Code VPS Setup Guide

This guide walks through deploying Cloud Code on a VPS (Ubuntu 22.04+).

## Prerequisites

- VPS with public IP address
- Domain name (recommended) or use IP directly
- SSH access to the VPS
- GitHub account

## 1. Server Setup

### Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Log out and back in for group changes
exit
```

### Install Git and Clone Repository

```bash
# Install git
sudo apt install git -y

# Clone Cloud Code
git clone https://github.com/yourusername/cloud-code.git
cd cloud-code
```

### Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Generate secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Edit .env with your settings
nano .env
```

Minimum required settings in `.env`:
```bash
SECRET_KEY=<generated-secret-key>
DATABASE_URL=postgresql://cloudcode:cloudcode@postgres:5432/cloudcode
REDIS_URL=redis://redis:6379
VAULT_URL=http://vault:8200
VAULT_TOKEN=dev-token
```

## 2. Start Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

Services started:
- `app` - Cloud Code orchestrator (port 8000)
- `worker` - Celery worker for background tasks
- `postgres` - PostgreSQL database
- `redis` - Redis for task queue
- `vault` - HashiCorp Vault for secrets

## 3. Build Agent Images

```bash
# Make script executable
chmod +x scripts/build-agents.sh

# Build all agent images
./scripts/build-agents.sh
```

This builds:
- `cloud-code/agent-base`
- `cloud-code/claude-code-agent`
- `cloud-code/aider-agent`
- `cloud-code/codex-agent`
- `cloud-code/gemini-agent`

## 4. Configure GitHub App

### Create GitHub App

1. Go to https://github.com/settings/apps/new

2. Fill in the form:
   - **GitHub App name:** `cloud-code` (or your preferred name)
   - **Homepage URL:** `http://your-vps-ip:8000`
   - **Webhook URL:** `http://your-vps-ip:8000/webhooks/github/`
   - **Webhook secret:** Generate one: `python3 -c "import secrets; print(secrets.token_hex(20))"`

3. Set permissions:
   - **Repository permissions:**
     - Contents: Read and write
     - Issues: Read and write
     - Pull requests: Read and write
     - Metadata: Read-only
   - **Subscribe to events:**
     - Issues
     - Issue comment
     - Pull request

4. Create the app

5. Note down:
   - App ID
   - Client ID
   - Generate Client Secret
   - Generate Private Key (downloads .pem file)

### Configure in Cloud Code

1. Open `http://your-vps-ip:8000/setup` in browser

2. Enter GitHub App credentials:
   - App ID
   - Client ID
   - Client Secret
   - Webhook Secret
   - Private Key (paste entire .pem contents)

3. Click "Save GitHub App Configuration"

### Install on Repositories

1. Click "Install on repositories" in setup wizard
2. Select repositories Cloud Code should monitor
3. Click "Install"
4. You'll be redirected back to the setup wizard

## 5. Configure API Keys

In the setup wizard, enter API keys for the CLIs you want to use:

- **Anthropic API Key** (required for Claude Code)
  - Get from: https://console.anthropic.com/

- **OpenAI API Key** (optional, for Codex/Aider)
  - Get from: https://platform.openai.com/api-keys

- **Google API Key** (optional, for Gemini)
  - Get from: https://aistudio.google.com/app/apikey

Click "Save API Keys" to store in Vault.

## 6. Verify Setup

### Check Setup Status

```bash
curl http://localhost:8000/auth/status
```

Should return:
```json
{
  "github_app_configured": true,
  "github_installations": 1,
  "cli_credentials_configured": ["claude-code"],
  "vault_available": true
}
```

### Check Health

```bash
curl http://localhost:8000/api/health
```

### Test Webhook

Create an issue in one of your installed repositories with the `cloud-code` label.

Check logs:
```bash
docker compose logs -f app
```

## 7. Production Considerations

### Use HTTPS

For production, put Cloud Code behind a reverse proxy with SSL:

```bash
# Install Caddy (automatic HTTPS)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Configure Caddy
sudo nano /etc/caddy/Caddyfile
```

Caddyfile:
```
your-domain.com {
    reverse_proxy localhost:8000
}
```

Update GitHub App webhook URL to use HTTPS.

### Secure Vault

For production, don't use dev mode:

1. Initialize Vault properly
2. Use AppRole authentication
3. Enable audit logging
4. Set up auto-unseal

### Database Backups

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U cloudcode cloudcode > backup.sql

# Restore
cat backup.sql | docker compose exec -T postgres psql -U cloudcode cloudcode
```

### Monitoring

Consider adding:
- Prometheus for metrics
- Grafana for dashboards
- Sentry for error tracking

## Troubleshooting

### Webhook Not Received

1. Check GitHub App webhook settings
2. Verify URL is accessible from internet
3. Check webhook secret matches
4. View webhook delivery logs in GitHub

### Container Won't Start

```bash
# Check container logs
docker compose logs app

# Check for port conflicts
sudo netstat -tlnp | grep 8000
```

### Vault Connection Failed

```bash
# Check Vault is running
docker compose exec vault vault status

# Check token is valid
docker compose exec vault vault token lookup
```

### Agent Container Issues

```bash
# List agent containers
docker ps -a | grep cloud-code

# Check agent logs
docker logs <container-id>

# Check workspace files
ls -la /var/cloud-code/workspaces/
```
