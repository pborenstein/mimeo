"""GitHub Pages host provider implementation."""

import json
import subprocess
from typing import Any, Dict

from mimeo.exceptions import HostError
from mimeo.models import DNSRecord
from mimeo.providers.base import DeployResult, Host
from mimeo.utils.retry import retry_with_jitter

TEMPLATE_ORG = "tepiton"
DEFAULT_TEMPLATE = "mimeo.lol"

GITHUB_PAGES_IPS = [
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153",
]


def health_status(health: Dict[str, Any]) -> str:
    """Derive a human-readable health status from a get_pages_health() result."""
    if not health["pages_configured"]:
        return "pages_error"
    if health["https_enforced"]:
        return "healthy"
    cert = health["cert_state"]
    if cert == "approved":
        return "fixable"
    if cert in ("new", "authorization_created", "issued"):
        return "cert_pending"
    return "no_cert"


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
                raise HostError("GitHub CLI (gh) is not authenticated. Run 'gh auth login' first.")
        except FileNotFoundError:
            raise HostError(
                "GitHub CLI (gh) is not installed. Install it from https://cli.github.com"
            )

    def _run_gh_command(self, args: list[str], input_data: str | None = None) -> str:
        """Run a gh CLI command with retry on transient errors.

        Args:
            args: Command arguments (without 'gh' prefix)
            input_data: Optional stdin data

        Returns:
            Command stdout

        Raises:
            HostError: If command fails
        """
        import os

        env = None
        if self.token:
            env = os.environ.copy()
            env["GH_TOKEN"] = self.token

        def _attempt() -> str:
            try:
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

        return retry_with_jitter(_attempt)

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

    def _delete_repository(self, repo_full_name: str) -> None:
        """Delete a repository.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Raises:
            HostError: If deletion fails
        """
        self._run_gh_command(["repo", "delete", repo_full_name, "--yes"])

    def _create_from_template(
        self,
        repo_name: str,
        owner: str,
        template_repo: str = DEFAULT_TEMPLATE,
        private: bool = False,
        force: bool = False,
    ) -> tuple[str, bool, bool]:
        """Create a repository from a GitHub template repo.

        If the repository already exists and force is False, returns it unchanged.
        If force is True and the repo exists, deletes it first then recreates.

        Args:
            repo_name: Name for the new repository
            owner: Owner (user or org) for the new repository
            template_repo: Template repository name in TEMPLATE_ORG
            private: Whether to create a private repository
            force: If True, delete existing repo and recreate from template

        Returns:
            Tuple of (full_name, repo_created, repo_existed) where repo_created is
            False if the repo already existed and force was not set.

        Raises:
            HostError: If repository creation fails
        """
        # Check if repository already exists
        repo_existed = False
        try:
            self._gh_api(f"repos/{owner}/{repo_name}")
            repo_existed = True
        except HostError:
            pass

        if repo_existed:
            if not force:
                return f"{owner}/{repo_name}", False, True
            self._delete_repository(f"{owner}/{repo_name}")

        data: Dict[str, Any] = {
            "owner": owner,
            "name": repo_name,
            "private": private,
        }

        response = self._gh_api(
            f"repos/{TEMPLATE_ORG}/{template_repo}/generate",
            method="POST",
            data=data,
        )
        full_name = response.get("full_name")
        if not full_name:
            raise HostError(
                f"Failed to create repository from template {TEMPLATE_ORG}/{template_repo}"
            )

        self._set_repository_topics(str(full_name), ["mimeo", "landing-page", "github-pages"])

        return str(full_name), True, repo_existed

    def _set_repository_topics(self, repo_full_name: str, topics: list[str]) -> None:
        """Set topics (tags) for a repository.

        Args:
            repo_full_name: Full repository name (owner/repo)
            topics: List of topic strings (lowercase, no spaces)

        Raises:
            HostError: If setting topics fails
        """
        data = {
            "names": topics,
        }

        self._gh_api(
            f"repos/{repo_full_name}/topics",
            method="PUT",
            data=data,
        )

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

        # Enable GitHub Pages with GitHub Actions workflow deployment
        data = {
            "source": {
                "branch": branch,
                "path": "/",
            },
            "build_type": "workflow",
        }

        self._gh_api(
            f"repos/{repo_full_name}/pages",
            method="POST",
            data=data,
        )

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

    def enable_https_enforcement(self, repo_full_name: str) -> bool:
        """Enable HTTPS enforcement for GitHub Pages.

        This can only be enabled after GitHub provisions an SSL certificate
        for the custom domain, which typically takes a few minutes.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            True if HTTPS enforcement was enabled, False if certificate not ready

        Raises:
            HostError: If API call fails for reasons other than missing certificate
        """
        data = {
            "https_enforced": True,
        }

        try:
            self._gh_api(
                f"repos/{repo_full_name}/pages",
                method="PUT",
                data=data,
            )
            return True
        except HostError as e:
            # Certificate not ready yet - this is expected for new sites
            if "certificate does not exist" in str(e).lower():
                return False
            # Other errors should be raised
            raise

    def deploy_site(
        self, domain: str, template: str = DEFAULT_TEMPLATE, force: bool = False
    ) -> DeployResult:
        """Deploy a site to GitHub Pages using a template repository.

        This will:
        1. Create a GitHub repository from the template (domain name as repo name)
        2. Enable GitHub Pages
        3. Configure custom domain
        4. Enable HTTPS enforcement (if certificate is ready)

        If the repository already exists, skips creation and only configures
        GitHub Pages settings and custom domain.

        Args:
            domain: Domain name for the site
            template: Template repository name in the tepiton org

        Returns:
            DeployResult with url, repo_created, and https_enabled flags

        Raises:
            HostError: If deployment fails
        """
        try:
            owner = self.default_org or self._get_authenticated_user()

            repo_full_name, repo_created, repo_existed = self._create_from_template(
                repo_name=domain,
                owner=owner,
                template_repo=template,
                force=force,
            )

            self._enable_github_pages(repo_full_name)
            self._set_custom_domain(repo_full_name, domain)
            https_enabled = self.enable_https_enforcement(repo_full_name)

            return DeployResult(
                url=f"https://{domain}",
                repo_created=repo_created,
                https_enabled=https_enabled,
                repo_existed=repo_existed,
            )

        except Exception as e:
            if isinstance(e, HostError):
                raise
            raise HostError(f"Failed to deploy site for {domain}: {e}") from e

    def get_pages_health(self, repo_full_name: str) -> Dict[str, Any]:
        """Fetch Pages configuration health for a repository.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            Dict with keys: pages_configured, https_enforced, cert_state, pages_status
        """
        try:
            data = self._gh_api(f"repos/{repo_full_name}/pages")
            cert = data.get("https_certificate") or {}
            return {
                "pages_configured": True,
                "https_enforced": data.get("https_enforced", False),
                "cert_state": cert.get("state"),
                "pages_status": data.get("status"),
            }
        except HostError:
            return {
                "pages_configured": False,
                "https_enforced": False,
                "cert_state": None,
                "pages_status": None,
            }

    def list_mimeo_repositories(self) -> list[Dict[str, Any]]:
        """List all repositories tagged with the 'mimeo' topic.

        Returns:
            List of repository data dictionaries

        Raises:
            HostError: If listing repositories fails
        """
        owner = self.default_org or self._get_authenticated_user()

        # Use GitHub search API to find repos with mimeo topic
        try:
            result = self._run_gh_command(
                [
                    "search",
                    "repos",
                    f"user:{owner}",
                    "topic:mimeo",
                    "--limit",
                    "1000",  # Maximum allowed by GitHub search API
                    "--json",
                    "name,url,homepage,updatedAt",
                    "--jq",
                    ".",
                ]
            )
            import json

            repos: list[Dict[str, Any]] = json.loads(result)
            return repos
        except Exception as e:
            raise HostError(f"Failed to list mimeo repositories: {e}") from e

    def required_dns_records(self, domain: str) -> list[DNSRecord]:
        """Return DNS records required for GitHub Pages to serve the domain.

        Args:
            domain: Domain name for the site

        Returns:
            List of DNS records: 4 A records for the apex + 1 CNAME for www
        """
        owner = self.default_org or self._get_authenticated_user()
        records: list[DNSRecord] = []

        for ip in GITHUB_PAGES_IPS:
            records.append(DNSRecord(type="A", name="", content=ip, ttl=600))

        records.append(DNSRecord(type="CNAME", name="www", content=f"{owner}.github.io", ttl=600))

        return records

    def __enter__(self) -> "GitHubHost":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        pass
