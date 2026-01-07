"""GitHub App integration for Cloud Code.

Handles GitHub App authentication, installation, and API interactions.
Using a GitHub App (vs OAuth App) because:
- Webhooks are configured at the app level (automatic)
- Acts as a bot, not as the user
- Granular permissions per repo
- Higher rate limits
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import httpx
import jwt

from cloud_code.config import settings

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"
GITHUB_URL = "https://github.com"


class GitHubAppAuth:
    """Handles GitHub App JWT and installation token generation."""

    def __init__(
        self,
        app_id: str,
        private_key: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.client_id = client_id
        self.client_secret = client_secret

        # Cache for installation tokens
        self._installation_tokens: dict[int, tuple[str, datetime]] = {}

    def generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        JWTs are used for app-level operations like listing installations.
        Valid for 10 minutes max.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago (clock drift)
            "exp": now + (9 * 60),  # Expires in 9 minutes
            "iss": self.app_id,
        }

        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_token(
        self,
        installation_id: int,
        force_refresh: bool = False,
    ) -> str:
        """Get an installation access token for a specific installation.

        Installation tokens are used for repo-level operations.
        Cached until near expiry.
        """
        # Check cache
        if not force_refresh and installation_id in self._installation_tokens:
            token, expires_at = self._installation_tokens[installation_id]
            if datetime.utcnow() < expires_at - timedelta(minutes=5):
                return token

        # Generate new token
        app_jwt = self.generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()

        token = data["token"]
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))

        # Cache token
        self._installation_tokens[installation_id] = (token, expires_at.replace(tzinfo=None))

        return token


class GitHubAppClient:
    """Client for GitHub App API operations."""

    def __init__(self, auth: GitHubAppAuth):
        self.auth = auth

    async def get_app_info(self) -> dict:
        """Get information about the GitHub App."""
        app_jwt = self.auth.generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/app",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def list_installations(self) -> list[dict]:
        """List all installations of this GitHub App."""
        app_jwt = self.auth.generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/app/installations",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_installation(self, installation_id: int) -> dict:
        """Get details of a specific installation."""
        app_jwt = self.auth.generate_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def list_installation_repos(self, installation_id: int) -> list[dict]:
        """List repositories accessible to an installation."""
        token = await self.auth.get_installation_token(installation_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/installation/repositories",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json().get("repositories", [])

    def get_installation_url(self) -> str:
        """Get URL for users to install the GitHub App."""
        return f"{GITHUB_URL}/apps/{settings.github_app_name}/installations/new"

    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str:
        """Get OAuth authorization URL for user authentication.

        This is used to identify the user, separate from app installation.
        """
        params = {
            "client_id": self.auth.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GITHUB_URL}/login/oauth/authorize?{query}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange OAuth code for user access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_URL}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_authenticated_user(self, user_token: str) -> dict:
        """Get the authenticated user's information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/user",
                headers={
                    "Authorization": f"token {user_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()


class GitHubRepoClient:
    """Client for repository-level GitHub operations."""

    def __init__(self, auth: GitHubAppAuth, installation_id: int):
        self.auth = auth
        self.installation_id = installation_id

    async def _get_token(self) -> str:
        return await self.auth.get_installation_token(self.installation_id)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> httpx.Response:
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{GITHUB_API_URL}{endpoint}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                **kwargs,
            )
            return response

    # Issue operations

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """Get an issue."""
        response = await self._request(
            "GET", f"/repos/{owner}/{repo}/issues/{issue_number}"
        )
        response.raise_for_status()
        return response.json()

    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> dict:
        """Create a comment on an issue."""
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()

    async def add_labels(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        labels: list[str],
    ) -> list[dict]:
        """Add labels to an issue."""
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
            json={"labels": labels},
        )
        response.raise_for_status()
        return response.json()

    # Branch operations

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict:
        """Get branch information."""
        response = await self._request(
            "GET", f"/repos/{owner}/{repo}/branches/{branch}"
        )
        response.raise_for_status()
        return response.json()

    async def create_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        from_sha: str,
    ) -> dict:
        """Create a new branch from a commit SHA."""
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": from_sha,
            },
        )
        response.raise_for_status()
        return response.json()

    # Pull request operations

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
    ) -> dict:
        """Create a pull request."""
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": draft,
            },
        )
        response.raise_for_status()
        return response.json()

    async def update_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        **kwargs,
    ) -> dict:
        """Update a pull request."""
        response = await self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            json=kwargs,
        )
        response.raise_for_status()
        return response.json()

    async def create_pr_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",  # APPROVE, REQUEST_CHANGES, COMMENT
    ) -> dict:
        """Create a review on a pull request."""
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json={
                "body": body,
                "event": event,
            },
        )
        response.raise_for_status()
        return response.json()

    # Repository operations

    async def get_repo(self, owner: str, repo: str) -> dict:
        """Get repository information."""
        response = await self._request("GET", f"/repos/{owner}/{repo}")
        response.raise_for_status()
        return response.json()

    async def get_default_branch(self, owner: str, repo: str) -> str:
        """Get the default branch of a repository."""
        repo_info = await self.get_repo(owner, repo)
        return repo_info["default_branch"]

    async def get_latest_commit(self, owner: str, repo: str, branch: str) -> str:
        """Get the latest commit SHA of a branch."""
        branch_info = await self.get_branch(owner, repo, branch)
        return branch_info["commit"]["sha"]
