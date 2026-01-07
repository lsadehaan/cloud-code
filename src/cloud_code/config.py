"""Configuration management for Cloud Code."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Cloud Code"
    debug: bool = False
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        description="Secret key for encryption",
    )

    # Database
    database_url: str = Field(
        default="postgresql://localhost/cloud_code",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for task queue",
    )

    # AI/LLM (these are defaults, actual keys stored in Vault)
    anthropic_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Anthropic API key (fallback, prefer Vault)",
    )
    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="OpenAI API key (fallback, prefer Vault)",
    )
    google_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Google API key (fallback, prefer Vault)",
    )
    default_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default Claude model to use",
    )

    # GitHub (legacy - prefer GitHub App via Vault)
    github_token: Optional[SecretStr] = Field(
        default=None,
        description="GitHub personal access token (legacy)",
    )
    github_webhook_secret: Optional[str] = Field(
        default=None,
        description="GitHub webhook secret (legacy)",
    )

    # GitHub App (stored in Vault, these are just for reference)
    github_app_name: str = Field(
        default="cloud-code",
        description="GitHub App slug name",
    )

    # Vault (for credential management)
    vault_url: str = Field(
        default="http://vault:8200",
        description="HashiCorp Vault URL",
    )
    vault_token: Optional[SecretStr] = Field(
        default=None,
        description="Vault token for authentication",
    )

    # Paths
    workspaces_path: Path = Field(
        default=Path("/var/cloud-code/workspaces"),
        description="Path to store git workspaces",
    )
    prompts_path: Path = Field(
        default=Path("prompts"),
        description="Path to agent prompt files",
    )

    # Agent settings
    max_task_attempts: int = Field(
        default=3,
        description="Maximum retry attempts for failed tasks",
    )
    agent_timeout_seconds: int = Field(
        default=3600,
        description="Maximum time for agent execution (1 hour)",
    )
    default_coding_cli: str = Field(
        default="claude-code",
        description="Default coding CLI to use",
    )

    # Web UI
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
