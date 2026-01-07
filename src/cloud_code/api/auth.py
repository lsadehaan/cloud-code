"""Authentication and OAuth routes for Cloud Code.

Handles:
- GitHub App OAuth flow
- GitHub App installation callbacks
- Session management
"""

import secrets
import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from cloud_code.config import settings
from cloud_code.core.vault import get_vault_client
from cloud_code.github.app import GitHubAppAuth, GitHubAppClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory session store (use Redis in production)
_sessions: dict[str, dict] = {}
_oauth_states: dict[str, dict] = {}


class SetupStatus(BaseModel):
    """Current setup status."""
    github_app_configured: bool
    github_installations: int
    cli_credentials_configured: list[str]
    vault_available: bool


def get_github_app_client() -> Optional[GitHubAppClient]:
    """Get GitHub App client if configured."""
    vault = get_vault_client()

    if not vault.is_available():
        return None

    creds = vault.get_github_app_credentials()
    if not creds:
        return None

    auth = GitHubAppAuth(
        app_id=creds["app_id"],
        private_key=creds["private_key"],
        client_id=creds.get("client_id"),
        client_secret=creds.get("client_secret"),
    )

    return GitHubAppClient(auth)


@router.get("/status")
async def get_setup_status() -> SetupStatus:
    """Get current setup/configuration status."""
    vault = get_vault_client()
    vault_available = vault.is_available()

    github_configured = False
    github_installations = 0
    cli_credentials = []

    if vault_available:
        # Check GitHub App
        github_creds = vault.get_github_app_credentials()
        github_configured = github_creds is not None

        # Count installations
        github_installations = len(vault.list_github_installations())

        # List configured CLIs
        cli_credentials = vault.list_configured_clis()

    return SetupStatus(
        github_app_configured=github_configured,
        github_installations=github_installations,
        cli_credentials_configured=cli_credentials,
        vault_available=vault_available,
    )


@router.get("/github/install")
async def github_install_redirect(request: Request):
    """Redirect to GitHub App installation page."""
    client = get_github_app_client()

    if not client:
        raise HTTPException(
            status_code=400,
            detail="GitHub App not configured. Please configure the app first.",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created_at": datetime.utcnow(),
        "type": "installation",
    }

    install_url = client.get_installation_url()
    return RedirectResponse(url=f"{install_url}?state={state}")


@router.get("/github/callback")
async def github_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    installation_id: Optional[int] = None,
    setup_action: Optional[str] = None,
    state: Optional[str] = None,
):
    """Handle GitHub OAuth/installation callback.

    This handles multiple callback types:
    1. App installation: installation_id + setup_action
    2. OAuth login: code + state
    """
    # Handle app installation callback
    if installation_id and setup_action:
        return await _handle_installation_callback(installation_id, setup_action)

    # Handle OAuth callback
    if code and state:
        return await _handle_oauth_callback(code, state, request)

    raise HTTPException(status_code=400, detail="Invalid callback parameters")


async def _handle_installation_callback(
    installation_id: int,
    setup_action: str,
) -> RedirectResponse:
    """Handle GitHub App installation callback."""
    logger.info(f"GitHub App installed: {installation_id}, action: {setup_action}")

    client = get_github_app_client()
    if not client:
        raise HTTPException(status_code=500, detail="GitHub App not configured")

    # Get installation details
    try:
        installation = await client.get_installation(installation_id)
        repos = await client.list_installation_repos(installation_id)

        # Store in Vault
        vault = get_vault_client()
        vault.set_github_installation(
            installation_id=installation_id,
            account_login=installation["account"]["login"],
            account_type=installation["account"]["type"],
            repositories=[r["full_name"] for r in repos],
        )

        logger.info(
            f"Stored installation {installation_id} for "
            f"{installation['account']['login']} with {len(repos)} repos"
        )

    except Exception as e:
        logger.error(f"Failed to process installation: {e}")
        return RedirectResponse(url="/setup?error=installation_failed")

    return RedirectResponse(url="/setup?success=installed")


async def _handle_oauth_callback(
    code: str,
    state: str,
    request: Request,
) -> RedirectResponse:
    """Handle OAuth login callback."""
    # Verify state
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")

    state_data = _oauth_states.pop(state)

    # Check expiry (5 minutes)
    if datetime.utcnow() - state_data["created_at"] > timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="State expired")

    client = get_github_app_client()
    if not client:
        raise HTTPException(status_code=500, detail="GitHub App not configured")

    # Exchange code for token
    try:
        redirect_uri = str(request.url_for("github_oauth_callback"))
        token_data = await client.exchange_code_for_token(code, redirect_uri)

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data["error_description"])

        access_token = token_data["access_token"]

        # Get user info
        user = await client.get_authenticated_user(access_token)

        # Create session
        session_id = secrets.token_urlsafe(32)
        _sessions[session_id] = {
            "user_id": str(user["id"]),
            "username": user["login"],
            "access_token": access_token,
            "created_at": datetime.utcnow(),
        }

        response = RedirectResponse(url="/dashboard")
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400 * 7,  # 7 days
        )

        return response

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/github/login")
async def github_login(request: Request):
    """Initiate GitHub OAuth login flow."""
    client = get_github_app_client()

    if not client:
        raise HTTPException(
            status_code=400,
            detail="GitHub App not configured",
        )

    # Generate state
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created_at": datetime.utcnow(),
        "type": "login",
    }

    redirect_uri = str(request.url_for("github_oauth_callback"))
    auth_url = client.get_oauth_authorize_url(state, redirect_uri)

    return RedirectResponse(url=auth_url)


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Log out the current user."""
    session_id = request.cookies.get("session_id")

    if session_id and session_id in _sessions:
        del _sessions[session_id]

    response.delete_cookie("session_id")
    return {"status": "logged_out"}


def get_current_session(request: Request) -> Optional[dict]:
    """Get current session from request cookies."""
    session_id = request.cookies.get("session_id")

    if not session_id or session_id not in _sessions:
        return None

    session = _sessions[session_id]

    # Check expiry (7 days)
    if datetime.utcnow() - session["created_at"] > timedelta(days=7):
        del _sessions[session_id]
        return None

    return session
