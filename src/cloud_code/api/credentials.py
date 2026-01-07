"""Credentials management API for Cloud Code.

Allows configuring API keys for different coding CLIs:
- Claude Code (Anthropic)
- Aider (Anthropic/OpenAI)
- Codex (OpenAI)
- Gemini (Google)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from cloud_code.core.vault import get_vault_client
from cloud_code.api.auth import get_current_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CLICredentials(BaseModel):
    """Credentials for a coding CLI."""
    cli_name: str = Field(..., description="CLI identifier (claude-code, aider, etc.)")
    api_key: str = Field(..., description="Primary API key")
    secondary_api_key: Optional[str] = Field(None, description="Secondary API key (e.g., OpenAI for Aider)")
    model: Optional[str] = Field(None, description="Default model to use")


class CLICredentialsResponse(BaseModel):
    """Response for CLI credentials (without sensitive data)."""
    cli_name: str
    configured: bool
    model: Optional[str] = None
    has_secondary_key: bool = False


class GitHubAppCredentials(BaseModel):
    """GitHub App credentials for initial setup."""
    app_id: str = Field(..., description="GitHub App ID")
    private_key: str = Field(..., description="GitHub App private key (PEM)")
    client_id: str = Field(..., description="GitHub App OAuth client ID")
    client_secret: str = Field(..., description="GitHub App OAuth client secret")
    webhook_secret: str = Field(..., description="Webhook secret for signature verification")


class GitHubAppStatus(BaseModel):
    """GitHub App configuration status."""
    configured: bool
    app_id: Optional[str] = None
    installations: int = 0


# =============================================================================
# CLI Credentials Endpoints
# =============================================================================


@router.get("/cli")
async def list_cli_credentials(request: Request) -> list[CLICredentialsResponse]:
    """List all configured CLI credentials."""
    vault = get_vault_client()

    if not vault.is_available():
        raise HTTPException(status_code=503, detail="Vault not available")

    configured_clis = vault.list_configured_clis()

    result = []
    for cli_name in ["claude-code", "aider", "codex", "gemini", "continue", "cursor"]:
        is_configured = cli_name in configured_clis

        creds = None
        if is_configured:
            creds = vault.get_cli_credentials(cli_name)

        result.append(CLICredentialsResponse(
            cli_name=cli_name,
            configured=is_configured,
            model=creds.get("model") if creds else None,
            has_secondary_key=bool(creds.get("secondary_api_key") if creds else False),
        ))

    return result


@router.post("/cli")
async def set_cli_credentials(
    credentials: CLICredentials,
    request: Request,
) -> dict:
    """Configure credentials for a coding CLI."""
    vault = get_vault_client()

    if not vault.is_available():
        raise HTTPException(status_code=503, detail="Vault not available")

    # Build credentials dict based on CLI type
    creds_dict = {"api_key": credentials.api_key}

    if credentials.model:
        creds_dict["model"] = credentials.model

    # Handle CLI-specific fields
    if credentials.cli_name == "aider":
        # Aider can use Anthropic or OpenAI
        creds_dict["anthropic_api_key"] = credentials.api_key
        if credentials.secondary_api_key:
            creds_dict["openai_api_key"] = credentials.secondary_api_key

    success = vault.set_cli_credentials(credentials.cli_name, creds_dict)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to store credentials")

    logger.info(f"Configured credentials for CLI: {credentials.cli_name}")

    return {"status": "success", "cli_name": credentials.cli_name}


@router.delete("/cli/{cli_name}")
async def delete_cli_credentials(
    cli_name: str,
    request: Request,
) -> dict:
    """Delete credentials for a coding CLI."""
    vault = get_vault_client()

    if not vault.is_available():
        raise HTTPException(status_code=503, detail="Vault not available")

    success = vault.delete_cli_credentials(cli_name)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete credentials")

    return {"status": "deleted", "cli_name": cli_name}


@router.post("/cli/{cli_name}/test")
async def test_cli_credentials(
    cli_name: str,
    request: Request,
) -> dict:
    """Test if CLI credentials are valid."""
    vault = get_vault_client()

    if not vault.is_available():
        raise HTTPException(status_code=503, detail="Vault not available")

    creds = vault.get_cli_credentials(cli_name)
    if not creds:
        raise HTTPException(status_code=404, detail="Credentials not found")

    # TODO: Actually test the credentials by making an API call
    # For now, just verify they exist

    return {
        "status": "valid",
        "cli_name": cli_name,
        "note": "Credential validation not yet implemented",
    }


# =============================================================================
# GitHub App Credentials Endpoints
# =============================================================================


@router.get("/github-app")
async def get_github_app_status(request: Request) -> GitHubAppStatus:
    """Get GitHub App configuration status."""
    vault = get_vault_client()

    if not vault.is_available():
        return GitHubAppStatus(configured=False)

    creds = vault.get_github_app_credentials()
    installations = vault.list_github_installations()

    return GitHubAppStatus(
        configured=creds is not None,
        app_id=creds.get("app_id") if creds else None,
        installations=len(installations),
    )


@router.post("/github-app")
async def set_github_app_credentials(
    credentials: GitHubAppCredentials,
    request: Request,
) -> dict:
    """Configure GitHub App credentials.

    This is typically done once during initial setup.
    """
    vault = get_vault_client()

    if not vault.is_available():
        raise HTTPException(status_code=503, detail="Vault not available")

    success = vault.set_github_app_credentials(
        app_id=credentials.app_id,
        private_key=credentials.private_key,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        webhook_secret=credentials.webhook_secret,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to store credentials")

    logger.info("Configured GitHub App credentials")

    return {"status": "success"}


# =============================================================================
# Bulk Configuration
# =============================================================================


class BulkCredentialsRequest(BaseModel):
    """Request for bulk credential configuration."""
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None


@router.post("/bulk")
async def set_bulk_credentials(
    credentials: BulkCredentialsRequest,
    request: Request,
) -> dict:
    """Configure multiple CLI credentials at once.

    This is a convenience endpoint for setting up all CLIs
    that can use the provided API keys.
    """
    vault = get_vault_client()

    if not vault.is_available():
        raise HTTPException(status_code=503, detail="Vault not available")

    configured = []

    # Claude Code uses Anthropic
    if credentials.anthropic_api_key:
        vault.set_cli_credentials("claude-code", {
            "api_key": credentials.anthropic_api_key,
            "model": "claude-sonnet-4-20250514",
        })
        configured.append("claude-code")

    # Aider can use Anthropic and/or OpenAI
    if credentials.anthropic_api_key or credentials.openai_api_key:
        aider_creds = {}
        if credentials.anthropic_api_key:
            aider_creds["anthropic_api_key"] = credentials.anthropic_api_key
            aider_creds["api_key"] = credentials.anthropic_api_key
            aider_creds["model"] = "claude-3-5-sonnet-20241022"
        if credentials.openai_api_key:
            aider_creds["openai_api_key"] = credentials.openai_api_key
        vault.set_cli_credentials("aider", aider_creds)
        configured.append("aider")

    # Codex uses OpenAI
    if credentials.openai_api_key:
        vault.set_cli_credentials("codex", {
            "api_key": credentials.openai_api_key,
            "model": "gpt-4",
        })
        configured.append("codex")

    # Gemini uses Google
    if credentials.google_api_key:
        vault.set_cli_credentials("gemini", {
            "api_key": credentials.google_api_key,
            "model": "gemini-pro",
        })
        configured.append("gemini")

    logger.info(f"Bulk configured credentials for: {configured}")

    return {
        "status": "success",
        "configured": configured,
    }
