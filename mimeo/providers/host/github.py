"""GitHub Pages host provider implementation."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from mimeo.exceptions import HostError
from mimeo.providers.base import Host


class GitHubHost(Host):
    """GitHub Pages host provider for static site hosting.

    Uses the GitHub CLI (gh) to interact with the GitHub API for:
    - Repository creation
    - GitHub Pages configuration
    - Custom domain setup

    Requires:
    - gh CLI installed and authenticated
    - GitHub token with 'repo' and 'workflow' scopes
    """

    def __init__(self, token: str | None = None, default_org: str | None = None) -> None:
        """Initialize GitHub host provider.

        Args:
            token: GitHub personal access token (optional, uses gh auth if not provided)
            default_org: Default organization/user for repository creation

        Raises:
            HostError: If gh CLI is not available or not authenticated
        """
        self.token = token
        self.default_org = default_org
        self._verify_gh_cli()

    def _verify_gh_cli(self) -> None:
        """Verify gh CLI is installed and authenticated.

        Raises:
            HostError: If gh CLI is not available or not authenticated
        """
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise HostError(
                    "GitHub CLI (gh) is not authenticated. Run 'gh auth login' first."
                )
        except FileNotFoundError:
            raise HostError(
                "GitHub CLI (gh) is not installed. Install it from https://cli.github.com"
            )

    def _run_gh_command(self, args: list[str], input_data: str | None = None) -> str:
        """Run a gh CLI command.

        Args:
            args: Command arguments (without 'gh' prefix)
            input_data: Optional stdin data

        Returns:
            Command stdout

        Raises:
            HostError: If command fails
        """
        try:
            env = None
            if self.token:
                import os
                env = os.environ.copy()
                env["GH_TOKEN"] = self.token

            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                check=False,
                input=input_data,
                env=env,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                raise HostError(f"GitHub CLI command failed: {error_msg}")

            return result.stdout.strip()
        except FileNotFoundError:
            raise HostError("GitHub CLI (gh) is not installed")
        except Exception as e:
            if isinstance(e, HostError):
                raise
            raise HostError(f"Failed to run gh command: {e}") from e

    def _gh_api(
        self,
        endpoint: str,
        method: str = "GET",
        data: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Make a GitHub API request using gh CLI.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            data: Request body data

        Returns:
            API response as dictionary

        Raises:
            HostError: If API request fails
        """
        args = ["api", endpoint, "--method", method]

        input_json = None
        if data:
            input_json = json.dumps(data)
            args.extend(["--input", "-"])

        output = self._run_gh_command(args, input_data=input_json)

        if not output:
            return {}

        try:
            result: Dict[str, Any] = json.loads(output)
            return result
        except json.JSONDecodeError as e:
            raise HostError(f"Failed to parse GitHub API response: {e}") from e

    def _get_authenticated_user(self) -> str:
        """Get the authenticated GitHub username.

        Returns:
            GitHub username

        Raises:
            HostError: If unable to get username
        """
        try:
            output = self._run_gh_command(["api", "user", "--jq", ".login"])
            return output
        except HostError as e:
            raise HostError(f"Failed to get authenticated user: {e}") from e

    def _create_repository(
        self,
        repo_name: str,
        org: str | None = None,
        private: bool = False,
    ) -> str:
        """Create a GitHub repository.

        Args:
            repo_name: Repository name
            org: Organization name (uses authenticated user if None)
            private: Whether to create a private repository

        Returns:
            Full repository name (owner/repo)

        Raises:
            HostError: If repository creation fails
        """
        owner = org or self.default_org or self._get_authenticated_user()

        # Check if repository already exists
        try:
            self._gh_api(f"repos/{owner}/{repo_name}")
            # Repository exists, we can use it
            return f"{owner}/{repo_name}"
        except HostError:
            # Repository doesn't exist, create it
            pass

        # Create repository
        data: Dict[str, Any] = {
            "name": repo_name,
            "private": private,
            "auto_init": False,  # We'll initialize it ourselves
        }

        if org and org != self._get_authenticated_user():
            # Create in organization
            endpoint = f"orgs/{org}/repos"
        else:
            # Create in user account
            endpoint = "user/repos"

        response = self._gh_api(endpoint, method="POST", data=data)
        full_name = response.get("full_name")
        if not full_name:
            raise HostError("Repository created but full_name not in response")

        return str(full_name)

    def _enable_github_pages(
        self,
        repo_full_name: str,
        branch: str = "main",
    ) -> None:
        """Enable GitHub Pages for a repository.

        Args:
            repo_full_name: Full repository name (owner/repo)
            branch: Branch to deploy from

        Raises:
            HostError: If GitHub Pages configuration fails
        """
        # Check if Pages is already enabled
        try:
            self._gh_api(f"repos/{repo_full_name}/pages")
            # Pages already enabled
            return
        except HostError:
            # Pages not enabled yet, continue to enable it
            pass

        # Enable GitHub Pages with GitHub Actions as build source
        data = {
            "source": {
                "branch": branch,
                "path": "/",
            },
            "build_type": "workflow",
        }

        try:
            self._gh_api(
                f"repos/{repo_full_name}/pages",
                method="POST",
                data=data,
            )
        except HostError as e:
            # If it fails because of "workflow" build_type not being accepted yet,
            # try with legacy build type
            if "build_type" in str(e).lower() or "workflow" in str(e).lower():
                data = {
                    "source": {
                        "branch": branch,
                        "path": "/",
                    },
                }
                self._gh_api(
                    f"repos/{repo_full_name}/pages",
                    method="POST",
                    data=data,
                )
            else:
                raise

    def _set_custom_domain(self, repo_full_name: str, domain: str) -> None:
        """Set custom domain for GitHub Pages.

        Args:
            repo_full_name: Full repository name (owner/repo)
            domain: Custom domain name

        Raises:
            HostError: If custom domain configuration fails
        """
        data = {
            "cname": domain,
        }

        self._gh_api(
            f"repos/{repo_full_name}/pages",
            method="PUT",
            data=data,
        )

    def _init_and_push_repository(
        self,
        repo_full_name: str,
        content_path: Path,
        branch: str = "main",
    ) -> None:
        """Initialize local repository and push to GitHub.

        Args:
            repo_full_name: Full repository name (owner/repo)
            content_path: Path to content directory
            branch: Branch name to push to

        Raises:
            HostError: If git operations fail
        """
        try:
            # Initialize git repository
            subprocess.run(
                ["git", "init"],
                cwd=content_path,
                capture_output=True,
                check=True,
            )

            # Configure git user if not set globally
            subprocess.run(
                ["git", "config", "user.name", "Mimeo"],
                cwd=content_path,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "config", "user.email", "mimeo@example.com"],
                cwd=content_path,
                capture_output=True,
                check=False,
            )

            # Create initial commit
            subprocess.run(
                ["git", "add", "-A"],
                cwd=content_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit from Mimeo"],
                cwd=content_path,
                capture_output=True,
                check=True,
            )

            # Rename to main branch if needed
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=content_path,
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()
            if current_branch != branch:
                subprocess.run(
                    ["git", "branch", "-M", branch],
                    cwd=content_path,
                    capture_output=True,
                    check=True,
                )

            # Add origin remote
            remote_url = f"https://github.com/{repo_full_name}.git"
            subprocess.run(
                ["git", "remote", "add", "origin", remote_url],
                cwd=content_path,
                capture_output=True,
                check=True,
            )

            # Configure git to use gh as credential helper for GitHub authentication
            subprocess.run(
                ["git", "config", "--local", "credential.helper", ""],
                cwd=content_path,
                capture_output=True,
                check=False,  # May not exist, that's ok
            )
            subprocess.run(
                ["git", "config", "--local", "credential.https://github.com.helper", "!gh auth git-credential"],
                cwd=content_path,
                capture_output=True,
                check=True,
            )

            # Push to GitHub
            subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=content_path,
                capture_output=True,
                check=True,
            )

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else ""
            raise HostError(f"Git operation failed: {stderr}") from e

    def deploy_site(self, domain: str, content_path: Path) -> str:
        """Deploy a site to GitHub Pages.

        This will:
        1. Create a GitHub repository (domain name as repo name)
        2. Initialize local git repository in content_path
        3. Push content to GitHub
        4. Enable GitHub Pages
        5. Configure custom domain

        Args:
            domain: Domain name for the site
            content_path: Path to site content directory

        Returns:
            Live URL of the deployed site (e.g., https://example.com)

        Raises:
            HostError: If deployment fails
        """
        if not content_path.exists():
            raise HostError(f"Content path does not exist: {content_path}")

        if not content_path.is_dir():
            raise HostError(f"Content path is not a directory: {content_path}")

        try:
            # Convert domain to repository name (replace dots with hyphens if needed)
            # For GitHub, we can actually use the domain name directly
            repo_name = domain

            # Create repository
            repo_full_name = self._create_repository(repo_name)

            # Initialize and push content
            self._init_and_push_repository(repo_full_name, content_path)

            # Enable GitHub Pages
            self._enable_github_pages(repo_full_name)

            # Configure custom domain
            self._set_custom_domain(repo_full_name, domain)

            return f"https://{domain}"

        except Exception as e:
            if isinstance(e, HostError):
                raise
            raise HostError(f"Failed to deploy site for {domain}: {e}") from e

    def configure_custom_domain(self, domain: str) -> None:
        """Configure custom domain in GitHub Pages settings.

        This sets the custom domain in the repository settings and creates
        a CNAME file in the repository.

        Args:
            domain: Custom domain to configure

        Raises:
            HostError: If custom domain configuration fails
        """
        try:
            # Repository name is the domain
            repo_name = domain
            owner = self.default_org or self._get_authenticated_user()
            repo_full_name = f"{owner}/{repo_name}"

            # Set custom domain in Pages settings
            self._set_custom_domain(repo_full_name, domain)

        except Exception as e:
            if isinstance(e, HostError):
                raise
            raise HostError(
                f"Failed to configure custom domain {domain}: {e}"
            ) from e
