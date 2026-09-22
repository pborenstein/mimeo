"""GitHub Pages host provider implementation."""

import base64
import json
import re
import subprocess
import time
from typing import Any, Dict

from mimeo.exceptions import HostError
from mimeo.models import DNSRecord
from mimeo.providers.base import DeployResult, Host
from mimeo.providers.host.template_manifest import (
    DEFAULT_DEV_PATHS,
    MANIFEST_FILENAME,
    Substitution,
    TemplateManifest,
    apply_substitutions,
    parse_manifest,
)
from mimeo.utils.retry import retry_with_jitter

TEMPLATE_ORG = "tepiton"
DEFAULT_TEMPLATE = "mimeo"

# gh prints API errors as e.g. "gh: Not Found (HTTP 404)" -- the single place
# a status code is recovered from gh stderr is _run_gh_command.
_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")

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

    def __init__(
        self,
        token: str | None = None,
        default_org: str | None = None,
        template_org: str | None = None,
    ) -> None:
        """Initialize GitHub host provider.

        Args:
            token: GitHub personal access token (optional, uses gh auth if not provided)
            default_org: Default organization/user for repository creation
            template_org: Organization holding template repositories
                (defaults to TEMPLATE_ORG)

        Raises:
            HostError: If gh CLI is not available or not authenticated
        """
        self.token = token
        self.default_org = default_org
        self.template_org = template_org or TEMPLATE_ORG
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
                    error_msg = (
                        result.stderr.strip()
                        or result.stdout.strip()
                        or f"gh exited with status {result.returncode} without error output"
                    )
                    code_match = _HTTP_STATUS_RE.search(error_msg)
                    raise HostError(
                        error_msg,
                        status_code=int(code_match.group(1)) if code_match else None,
                    )
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

        try:
            output = self._run_gh_command(args, input_data=input_json)
        except HostError as e:
            raise HostError(f"{method} {endpoint}: {e}", status_code=e.status_code) from e

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
            raise HostError(
                f"Failed to get authenticated user: {e}", status_code=e.status_code
            ) from e

    def _delete_repository(self, repo_full_name: str) -> None:
        """Delete a repository.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Raises:
            HostError: If deletion fails
        """
        self._run_gh_command(["repo", "delete", repo_full_name, "--yes"])

    def _rename_repository(self, repo_full_name: str, new_name: str) -> None:
        """Rename a repository in place.

        Uses the numeric repository ID endpoint (repositories/<id>) rather
        than the name-based one (repos/<owner>/<name>) so that GitHub's
        redirect for previously-renamed repos is never an obstacle. Also
        retries once on 422 "conflicting operation in progress", which GitHub
        can return when two renames happen in quick succession.

        Args:
            repo_full_name: Full repository name (owner/repo)
            new_name: New repository name (name only, not owner/name)

        Raises:
            HostError: If rename fails
        """
        repo = self._gh_api(f"repos/{repo_full_name}")
        repo_id = repo.get("id")
        if not repo_id:
            raise HostError(f"Could not determine ID for repository {repo_full_name}")

        for attempt in range(2):
            try:
                self._gh_api(f"repositories/{repo_id}", method="PATCH", data={"name": new_name})
                return
            except HostError as e:
                if attempt == 0 and e.status_code == 422:
                    time.sleep(3)
                    continue
                raise

    def _ensure_is_template(self, repo_full_name: str) -> None:
        """Ensure a repository is flagged as a GitHub template repo.

        GitHub's generate-from-template API 404s if the source repo doesn't
        have is_template set, even though the repo otherwise exists and is
        readable. Rather than surface that as a confusing "Not Found" error,
        check the flag up front and set it if needed.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Raises:
            HostError: If the repo can't be read or the flag can't be set
        """
        repo = self._gh_api(f"repos/{repo_full_name}")
        if not repo.get("is_template"):
            self._gh_api(f"repos/{repo_full_name}", method="PATCH", data={"is_template": True})

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
            template_repo: Template repository name in the template org
            private: Whether to create a private repository
            force: If True, delete existing repo and recreate from template

        Returns:
            Tuple of (full_name, repo_created, repo_existed) where repo_created is
            False if the repo already existed and force was not set.

        Raises:
            HostError: If repository creation fails
        """
        # Validate the template's manifest (if any) before touching anything,
        # so a broken manifest fails the deploy ahead of any repo mutation.
        manifest = self._fetch_template_manifest(template_repo)

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

            # Rename the existing repo out of the way instead of deleting it
            # up front. If generate-from-template then fails (wrong template
            # flag, API hiccup, rate limit, ...), we rename it back rather
            # than leaving the repo permanently destroyed with nothing to
            # replace it.
            displaced_name = f"{repo_name}-mimeo-replaced-{int(time.time())}"
            self._rename_repository(f"{owner}/{repo_name}", displaced_name)

        data: Dict[str, Any] = {
            "owner": owner,
            "name": repo_name,
            "private": private,
        }

        try:
            self._ensure_is_template(f"{self.template_org}/{template_repo}")
            response = self._gh_api(
                f"repos/{self.template_org}/{template_repo}/generate",
                method="POST",
                data=data,
            )
            full_name = response.get("full_name")
            if not full_name:
                raise HostError(
                    f"Failed to create repository from template {self.template_org}/{template_repo}"
                )
        except HostError:
            if repo_existed:
                self._rename_repository(f"{owner}/{displaced_name}", repo_name)
            raise

        if repo_existed:
            self._delete_repository(f"{owner}/{displaced_name}")

        self._wait_for_repo(str(full_name))
        if repo_existed:
            self._delete_stale_pages_artifacts(str(full_name))
        self._set_repository_topics(str(full_name), ["mimeo", "landing-page", "github-pages"])
        self._strip_template_dev_files(
            str(full_name), manifest.dev_paths if manifest else DEFAULT_DEV_PATHS
        )

        if manifest:
            # The manifest itself is template-authoring metadata; it rides
            # along with every generate and must not be published.
            self._delete_file(str(full_name), MANIFEST_FILENAME)
            self._apply_template_manifest(str(full_name), repo_name, manifest)

        return str(full_name), True, repo_existed

    def _fetch_template_manifest(self, template_repo: str) -> TemplateManifest | None:
        """Fetch and validate a template repo's mimeo.template.json (DEC-024).

        The manifest is read from the template repo itself -- fully
        populated, so the empty-repo race that affects generated repos does
        not apply -- and validated in full, so an invalid manifest surfaces
        before any repository is created or mutated. A missing manifest is
        not an error: None means the template declares no substitutions and
        gets default dev-path stripping only.

        Args:
            template_repo: Template repository name (without org prefix)

        Returns:
            The parsed manifest, or None if the template ships none

        Raises:
            HostError: If the manifest exists but is unreadable or invalid
        """
        try:
            file_data = self._gh_api(
                f"repos/{self.template_org}/{template_repo}/contents/{MANIFEST_FILENAME}"
            )
        except HostError as e:
            if e.status_code == 404:
                return None
            raise
        if not isinstance(file_data, dict) or "content" not in file_data:
            raise HostError(
                f"{MANIFEST_FILENAME} in {self.template_org}/{template_repo} is not a readable file"
            )
        raw = base64.b64decode(file_data["content"]).decode("utf-8")
        return parse_manifest(raw)

    def _apply_template_manifest(
        self, repo_full_name: str, domain: str, manifest: TemplateManifest
    ) -> None:
        """Apply a template manifest's substitutions to a generated repo.

        Entries are grouped by file so each file is read and written once.
        A substitution that produces no change skips the write, keeping
        re-runs idempotent. Failures are loud per DEC-024: a missing target
        file, an unresolvable key, or an absent match raises rather than
        silently skipping.

        Args:
            repo_full_name: Full repository name (owner/repo)
            domain: Domain name to substitute into the values
            manifest: The template's parsed manifest

        Raises:
            HostError: If any substitution cannot be read or applied
        """
        by_file: Dict[str, list[Substitution]] = {}
        for sub in manifest.substitutions:
            by_file.setdefault(sub.file, []).append(sub)

        for path, subs in by_file.items():
            file_data = self._read_file_with_retry(repo_full_name, path)
            content = base64.b64decode(file_data["content"]).decode("utf-8")
            updated = apply_substitutions(content, subs, domain)
            if updated == content:
                continue
            self._gh_api(
                f"repos/{repo_full_name}/contents/{path}",
                method="PUT",
                data={
                    "message": f"Apply template manifest for {domain}",
                    "content": base64.b64encode(updated.encode("utf-8")).decode("ascii"),
                    "sha": file_data["sha"],
                },
            )

    def _read_file_with_retry(self, repo_full_name: str, path: str) -> Dict[str, Any]:
        """Read a file's Contents API payload, retrying the empty-repo race.

        generate-from-template can return before GitHub finishes populating
        the new repo's file tree, so the first read may 404 with "repository
        is empty" -- retry the read a few times before giving up. Unlike
        the dev-file strip (best-effort by design), a substitution target
        that stays unreadable is a hard error.

        Args:
            repo_full_name: Full repository name (owner/repo)
            path: Path to the file within the repository

        Returns:
            The Contents API payload for the file

        Raises:
            HostError: If the file cannot be read after retries
        """
        file_data = None
        last_error: HostError | None = None
        for attempt in range(5):
            try:
                file_data = self._gh_api(f"repos/{repo_full_name}/contents/{path}")
                break
            except HostError as e:
                last_error = e
                if attempt < 4:
                    time.sleep(2)
        if file_data is None:
            raise HostError(f"Could not read {path} from {repo_full_name}: {last_error}")
        return file_data

    def _strip_template_dev_files(self, repo_full_name: str, dev_paths: list[str]) -> None:
        """Delete template-development-only files/dirs from a generated repo.

        Templates carry authoring docs meant for people maintaining the
        template itself, not for the sites generated from it. Those files
        are not site content and must not be published. The paths come from
        the template manifest when it declares dev_paths, else the defaults
        (README.md, docs/, CLAUDE.md). Best-effort: a failure here should
        not fail the whole deploy.

        Args:
            repo_full_name: Full repository name (owner/repo)
            dev_paths: Paths to strip; a trailing "/" means a directory
        """
        for path in dev_paths:
            if path.endswith("/"):
                self._delete_directory(repo_full_name, path.rstrip("/"))
            else:
                self._delete_file(repo_full_name, path)

    def _delete_file(self, repo_full_name: str, path: str) -> None:
        """Delete a single file from a repository, if it exists.

        generate-from-template can return before GitHub finishes populating
        the new repo's file tree (the same race the manifest-substitution
        read path works around) -- a fresh repo's contents lookup can 404
        with "repository is empty" even when the file will exist moments
        later. Retry the existence check before concluding the file is
        genuinely absent, or a real file silently survives the strip.

        Args:
            repo_full_name: Full repository name (owner/repo)
            path: Path to the file within the repository
        """
        file_data = None
        for attempt in range(5):
            try:
                file_data = self._gh_api(f"repos/{repo_full_name}/contents/{path}")
                break
            except HostError:
                if attempt < 4:
                    time.sleep(2)
        if file_data is None:
            return  # File doesn't exist -- nothing to strip

        try:
            self._gh_api(
                f"repos/{repo_full_name}/contents/{path}",
                method="DELETE",
                data={
                    "message": f"Remove template development file: {path}",
                    "sha": file_data["sha"],
                },
            )
        except HostError:
            pass  # Best-effort

    def _delete_directory(self, repo_full_name: str, path: str) -> None:
        """Delete every file under a directory in a repository, if it exists.

        The Contents API has no recursive delete, so list the directory and
        delete each file individually. Best-effort throughout: a template
        without this directory, or a transient API failure, should not fail
        the deploy.

        Retries the listing call for the same reason _delete_file does --
        generate-from-template can return before the repo's file tree is
        populated, and a fresh repo's contents lookup can 404 even when the
        directory will exist moments later.

        Args:
            repo_full_name: Full repository name (owner/repo)
            path: Path to the directory within the repository
        """
        entries = None
        for attempt in range(5):
            try:
                entries = self._gh_api(f"repos/{repo_full_name}/contents/{path}")
                break
            except HostError:
                if attempt < 4:
                    time.sleep(2)
        if entries is None:
            return  # Directory doesn't exist -- nothing to strip

        # A single-file path would return a dict, not a list; only
        # directories are handled here.
        if not isinstance(entries, list):
            return

        for entry in entries:
            if entry.get("type") == "dir":
                self._delete_directory(repo_full_name, entry["path"])
            else:
                self._delete_file(repo_full_name, entry["path"])

    def _delete_stale_pages_artifacts(self, repo_full_name: str) -> None:
        """Delete all but the newest 'github-pages' artifact from a repository.

        When a repo is recreated from a template the old artifacts carry over.
        GitHub's Pages deploy action fails if it finds more than one artifact
        named 'github-pages' in the same workflow run. Keeping only the newest
        one unblocks the deployment.

        Args:
            repo_full_name: Full repository name (owner/repo)
        """
        try:
            data = self._gh_api(f"repos/{repo_full_name}/actions/artifacts")
        except HostError:
            return  # Best-effort; don't fail the whole operation

        artifacts = [a for a in data.get("artifacts", []) if a.get("name") == "github-pages"]
        # Sort newest first; delete everything after the first entry
        artifacts.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        for artifact in artifacts[1:]:
            try:
                self._gh_api(
                    f"repos/{repo_full_name}/actions/artifacts/{artifact['id']}",
                    method="DELETE",
                )
            except HostError:
                pass  # Best-effort

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

    def _wait_for_repo(self, repo_full_name: str, timeout: int = 30) -> None:
        """Poll until the repository is accessible, up to timeout seconds.

        Args:
            repo_full_name: Full repository name (owner/repo)
            timeout: Maximum seconds to wait

        Raises:
            HostError: If the repository is not accessible within timeout
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self._gh_api(f"repos/{repo_full_name}")
                return
            except HostError:
                time.sleep(2)
        raise HostError(f"Repository {repo_full_name} not accessible after {timeout}s")

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
        except HostError as e:
            # Only "not configured" (404) means Pages needs enabling; any
            # other failure (auth, 5xx, network) must surface, not be masked
            # by a POST that will likely fail the same way.
            if e.status_code != 404:
                raise

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
            template: Template repository name in the template org

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

        Raises:
            HostError: If the health check itself fails for any reason other
                than Pages not being configured (404)
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
        except HostError as e:
            # Only a genuine 404 means Pages is not configured; any other
            # failure is "couldn't check" and must propagate rather than be
            # reported as a broken site.
            if e.status_code != 404:
                raise
            return {
                "pages_configured": False,
                "https_enforced": False,
                "cert_state": None,
                "pages_status": None,
            }

    def validate_template(self, template_repo: str) -> None:
        """Verify a template repository exists in the template org.

        Args:
            template_repo: Template repository name (without org prefix)

        Raises:
            HostError: With a clear message if the template is not found
        """
        try:
            self._gh_api(f"repos/{self.template_org}/{template_repo}")
        except HostError:
            raise HostError(
                f"Template '{template_repo}' not found in {self.template_org}. "
                f"Check the spelling and try again."
            )

    def get_template_repository(self, repo_full_name: str) -> str | None:
        """Return the name of the template repository used to create a repo.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            Template repository name, or None if not created from a template
        """
        data = self._gh_api(f"repos/{repo_full_name}")
        tmpl = data.get("template_repository")
        return tmpl.get("name") if tmpl else None

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
