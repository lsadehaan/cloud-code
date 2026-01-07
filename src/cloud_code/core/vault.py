"""HashiCorp Vault integration for Cloud Code.

Manages secrets for:
- CLI API keys (Anthropic, OpenAI, Google, etc.)
- GitHub App private key
- User-specific tokens
- Agent runtime credentials
"""

import logging
from typing import Optional, Any
from functools import lru_cache

import hvac
from hvac.exceptions import InvalidPath, Forbidden

from cloud_code.config import settings

logger = logging.getLogger(__name__)

# Secret paths in Vault
SECRETS_BASE_PATH = "cloud-code"
CLI_SECRETS_PATH = f"{SECRETS_BASE_PATH}/cli"
GITHUB_SECRETS_PATH = f"{SECRETS_BASE_PATH}/github"
USER_SECRETS_PATH = f"{SECRETS_BASE_PATH}/users"


class VaultClient:
    """Client for HashiCorp Vault operations."""

    def __init__(
        self,
        url: str = None,
        token: str = None,
        mount_point: str = "secret",
    ):
        self.url = url or settings.vault_url
        self.token = token or (
            settings.vault_token.get_secret_value()
            if settings.vault_token
            else None
        )
        self.mount_point = mount_point

        self._client: Optional[hvac.Client] = None

    @property
    def client(self) -> hvac.Client:
        """Get or create Vault client."""
        if self._client is None:
            self._client = hvac.Client(url=self.url, token=self.token)

            if not self._client.is_authenticated():
                raise RuntimeError("Vault authentication failed")

        return self._client

    def is_available(self) -> bool:
        """Check if Vault is available and authenticated."""
        try:
            return self.client.is_authenticated()
        except Exception:
            return False

    # ==========================================================================
    # CLI Credentials (Anthropic, OpenAI, Google, etc.)
    # ==========================================================================

    def get_cli_credentials(self, cli_name: str) -> Optional[dict[str, str]]:
        """Get credentials for a specific coding CLI.

        Args:
            cli_name: CLI identifier (claude-code, aider, codex, gemini, etc.)

        Returns:
            Dict with credential keys (api_key, etc.) or None if not found
        """
        path = f"{CLI_SECRETS_PATH}/{cli_name}"
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            return response["data"]["data"]
        except InvalidPath:
            logger.warning(f"No credentials found for CLI: {cli_name}")
            return None
        except Forbidden:
            logger.error(f"Access denied to CLI credentials: {cli_name}")
            return None

    def set_cli_credentials(
        self,
        cli_name: str,
        credentials: dict[str, str],
    ) -> bool:
        """Store credentials for a coding CLI.

        Args:
            cli_name: CLI identifier
            credentials: Dict with credential keys (api_key, model, etc.)

        Returns:
            True if successful
        """
        path = f"{CLI_SECRETS_PATH}/{cli_name}"
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=credentials,
                mount_point=self.mount_point,
            )
            logger.info(f"Stored credentials for CLI: {cli_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to store CLI credentials: {e}")
            return False

    def list_configured_clis(self) -> list[str]:
        """List all CLIs with stored credentials."""
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=CLI_SECRETS_PATH,
                mount_point=self.mount_point,
            )
            return response["data"]["keys"]
        except InvalidPath:
            return []
        except Exception as e:
            logger.error(f"Failed to list CLI credentials: {e}")
            return []

    def delete_cli_credentials(self, cli_name: str) -> bool:
        """Delete credentials for a CLI."""
        path = f"{CLI_SECRETS_PATH}/{cli_name}"
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.mount_point,
            )
            logger.info(f"Deleted credentials for CLI: {cli_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete CLI credentials: {e}")
            return False

    # ==========================================================================
    # GitHub App Credentials
    # ==========================================================================

    def get_github_app_credentials(self) -> Optional[dict[str, str]]:
        """Get GitHub App credentials (app_id, private_key, etc.)."""
        path = f"{GITHUB_SECRETS_PATH}/app"
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            return response["data"]["data"]
        except InvalidPath:
            return None

    def set_github_app_credentials(
        self,
        app_id: str,
        private_key: str,
        client_id: str,
        client_secret: str,
        webhook_secret: str,
    ) -> bool:
        """Store GitHub App credentials."""
        path = f"{GITHUB_SECRETS_PATH}/app"
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret={
                    "app_id": app_id,
                    "private_key": private_key,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "webhook_secret": webhook_secret,
                },
                mount_point=self.mount_point,
            )
            logger.info("Stored GitHub App credentials")
            return True
        except Exception as e:
            logger.error(f"Failed to store GitHub App credentials: {e}")
            return False

    # ==========================================================================
    # GitHub Installation Tokens (cached by orchestrator)
    # ==========================================================================

    def get_github_installation(self, installation_id: int) -> Optional[dict]:
        """Get stored GitHub installation info."""
        path = f"{GITHUB_SECRETS_PATH}/installations/{installation_id}"
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            return response["data"]["data"]
        except InvalidPath:
            return None

    def set_github_installation(
        self,
        installation_id: int,
        account_login: str,
        account_type: str,
        repositories: list[str],
    ) -> bool:
        """Store GitHub installation info."""
        path = f"{GITHUB_SECRETS_PATH}/installations/{installation_id}"
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret={
                    "installation_id": str(installation_id),
                    "account_login": account_login,
                    "account_type": account_type,
                    "repositories": ",".join(repositories),
                },
                mount_point=self.mount_point,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store installation: {e}")
            return False

    def list_github_installations(self) -> list[int]:
        """List all stored GitHub installations."""
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=f"{GITHUB_SECRETS_PATH}/installations",
                mount_point=self.mount_point,
            )
            return [int(k) for k in response["data"]["keys"]]
        except InvalidPath:
            return []
        except Exception:
            return []

    # ==========================================================================
    # User Tokens (for multi-user scenarios)
    # ==========================================================================

    def get_user_token(self, user_id: str, provider: str) -> Optional[str]:
        """Get a user's OAuth token for a provider."""
        path = f"{USER_SECRETS_PATH}/{user_id}/{provider}"
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            return response["data"]["data"].get("token")
        except InvalidPath:
            return None

    def set_user_token(
        self,
        user_id: str,
        provider: str,
        token: str,
        refresh_token: Optional[str] = None,
    ) -> bool:
        """Store a user's OAuth token."""
        path = f"{USER_SECRETS_PATH}/{user_id}/{provider}"
        data = {"token": token}
        if refresh_token:
            data["refresh_token"] = refresh_token

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=self.mount_point,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store user token: {e}")
            return False

    # ==========================================================================
    # Agent Runtime Credentials
    # ==========================================================================

    def get_agent_env(self, agent_type: str, cli_name: str) -> dict[str, str]:
        """Get environment variables for an agent container.

        Combines CLI credentials with any agent-specific settings.
        Returns a dict ready to inject into container environment.
        """
        env = {}

        # Get CLI-specific credentials
        cli_creds = self.get_cli_credentials(cli_name)
        if cli_creds:
            # Map to environment variables
            if cli_name == "claude-code":
                if "api_key" in cli_creds:
                    env["ANTHROPIC_API_KEY"] = cli_creds["api_key"]
                if "model" in cli_creds:
                    env["CLAUDE_CODE_MODEL"] = cli_creds["model"]

            elif cli_name == "aider":
                if "anthropic_api_key" in cli_creds:
                    env["ANTHROPIC_API_KEY"] = cli_creds["anthropic_api_key"]
                if "openai_api_key" in cli_creds:
                    env["OPENAI_API_KEY"] = cli_creds["openai_api_key"]
                if "model" in cli_creds:
                    env["AIDER_MODEL"] = cli_creds["model"]

            elif cli_name == "codex":
                if "api_key" in cli_creds:
                    env["OPENAI_API_KEY"] = cli_creds["api_key"]

            elif cli_name == "gemini":
                if "api_key" in cli_creds:
                    env["GOOGLE_API_KEY"] = cli_creds["api_key"]

        return env


# Singleton instance
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get the singleton Vault client."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


def init_vault_secrets():
    """Initialize Vault with required secret paths.

    Run this once during initial setup.
    """
    client = get_vault_client()

    # Enable KV v2 secrets engine if not already enabled
    try:
        client.client.sys.enable_secrets_engine(
            backend_type="kv",
            path="secret",
            options={"version": "2"},
        )
        logger.info("Enabled KV v2 secrets engine")
    except Exception:
        # Already enabled
        pass

    logger.info("Vault initialized for Cloud Code")
