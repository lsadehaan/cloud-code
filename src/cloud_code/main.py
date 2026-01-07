"""Cloud Code - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cloud_code.config import settings
from cloud_code.github.webhook import router as github_webhook_router
from cloud_code.api.auth import router as auth_router
from cloud_code.api.credentials import router as credentials_router
from cloud_code.core.container_manager import get_container_manager
from cloud_code.core.vault import get_vault_client

logger = logging.getLogger(__name__)

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "web" / "templates"
STATIC_DIR = Path(__file__).parent / "web" / "static"

# Global instances
_container_manager = None
_vault_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global _container_manager, _vault_client

    # Startup
    logger.info(f"Starting {settings.app_name}...")

    # Create workspaces directory if it doesn't exist
    settings.workspaces_path.mkdir(parents=True, exist_ok=True)

    # Initialize Vault client
    try:
        _vault_client = get_vault_client()
        if _vault_client.is_available():
            logger.info("Vault client connected")
        else:
            logger.warning("Vault not available - running in limited mode")
    except Exception as e:
        logger.warning(f"Failed to connect to Vault: {e}")

    # Initialize container manager
    try:
        _container_manager = get_container_manager()
        logger.info("Container manager initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize container manager: {e}")
        logger.warning("Running without Docker support (development mode)")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")

    # Cleanup containers
    if _container_manager:
        try:
            await _container_manager.cleanup_all()
            logger.info("All agent containers cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up containers: {e}")


app = FastAPI(
    title=settings.app_name,
    description="Autonomous AI-Powered Development Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include routers
app.include_router(github_webhook_router)
app.include_router(auth_router)
app.include_router(credentials_router)


# =============================================================================
# Web UI Routes
# =============================================================================


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    # Check if setup is complete
    vault = get_vault_client()
    if not vault.is_available():
        return RedirectResponse(url="/setup")

    github_creds = vault.get_github_app_credentials()
    if not github_creds:
        return RedirectResponse(url="/setup")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Dashboard",
            "projects": [],  # TODO: Load from database
            "recent_activity": [],  # TODO: Load recent logs
        },
    )


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Setup wizard page."""
    return templates.TemplateResponse(
        "setup.html",
        {"request": request, "title": "Setup"},
    )


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_view(request: Request, project_id: str):
    """Project detail page."""
    return templates.TemplateResponse(
        "project.html",
        {
            "request": request,
            "title": "Project",
            "project": None,  # TODO: Load from database
        },
    )


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_view(request: Request, task_id: str):
    """Task detail page."""
    return templates.TemplateResponse(
        "task.html",
        {
            "request": request,
            "title": "Task",
            "task": None,  # TODO: Load from database
        },
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_view(request: Request):
    """Agent logs page."""
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "title": "Logs",
        },
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request):
    """Settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "title": "Settings",
        },
    )


# =============================================================================
# API Routes
# =============================================================================


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    vault = get_vault_client()

    return {
        "status": "healthy",
        "version": "0.1.0",
        "vault_available": vault.is_available() if vault else False,
        "container_manager": _container_manager is not None,
    }


@app.get("/api/agents")
async def list_agents():
    """List running agent containers."""
    if not _container_manager:
        return {"agents": [], "error": "Container manager not available"}

    try:
        agents = await _container_manager.list_agents()
        return {
            "agents": [
                {
                    "container_id": a.container_id,
                    "container_name": a.container_name,
                    "agent_type": a.agent_type,
                    "coding_cli": a.coding_cli,
                    "is_busy": a.is_busy,
                }
                for a in agents
            ]
        }
    except Exception as e:
        return {"agents": [], "error": str(e)}


# =============================================================================
# Development server
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    uvicorn.run(
        "cloud_code.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
