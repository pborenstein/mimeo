"""GitHub Pages host provider implementation."""

from typing import Any, Dict

from mimeo.exceptions import HostError
from mimeo.models import DNSRecord, Site, SiteState
from mimeo.providers.base import DeployResult, Host
from mimeo.providers.gh import GhCli
from mimeo.providers.repo.github import DEFAULT_TEMPLATE, TEMPLATE_ORG, GitHubRepoProvider

__all__ = [
    "DEFAULT_TEMPLATE",
    "GITHUB_PAGES_IPS",
    "GITHUB_PAGES_IPV6",
    "TEMPLATE_ORG",
    "GitHubHost",
    "health_status",
]

GITHUB_PAGES_IPV6 = [
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153",
]

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

    Configures how a repository is served: Pages, the custom domain,
    HTTPS enforcement, and health. Repository work (creation from a
    template, deletion) is done by the GitHubRepoProvider in `repos`,
    which shares this host's gh client.
    """

    def __init__(
        self,
        token: str | None = None,
        default_org: str | None = None,
        template_org: str | None = None,
        organizations: list[str] | None = None,
    ) -> None:
        """Initialize GitHub host provider.

        Args:
            token: GitHub personal access token (optional, uses gh auth if not provided)
            default_org: Default organization/user for repository creation
            organizations: Organizations and user accounts searched for
                sites (defaults to default_org alone)
            template_org: Organization holding template repositories
                (defaults to TEMPLATE_ORG)

        Raises:
            HostError: If gh CLI is not available or not authenticated
        """
        self.gh = GhCli(token)
        self.default_org = default_org
        self.organizations = list(organizations or ([default_org] if default_org else []))
        self.repos = GitHubRepoProvider(self.gh, template_org)

    name = "github"

    def find_site(self, hostname: str) -> Site | None:
        """Look for a repo named after the hostname in each listed organization.

        Returns the first one whose Pages custom domain is the hostname.
        A site in a repo with another name is found only by scan().

        Raises:
            HostError: If an API call fails for a reason other than 404
        """
        for org in self.organizations:
            ref = f"{org}/{hostname}"
            try:
                data = self.gh.api(f"repos/{ref}/pages")
            except HostError as e:
                if e.status_code == 404:
                    continue
                raise
            if str(data.get("cname") or "").lower() == hostname.lower():
                return Site(host=self.name, ref=ref)
        return None

    def scan(self) -> dict[str, list[Site]]:
        """Find every Pages site with a custom domain in the listed organizations.

        Lists each organization's repositories (the same endpoint serves
        organizations and user accounts), keeps the ones with Pages on,
        and reads each one's custom domain. Only repositories the
        endpoint lists publicly are seen.

        Raises:
            HostError: If an API call fails for a reason other than 404
        """
        found: dict[str, list[Site]] = {}
        for org in self.organizations:
            listing = self.gh.run(
                [
                    "api",
                    "--paginate",
                    f"users/{org}/repos?per_page=100",
                    "--jq",
                    ".[] | select(.has_pages) | .full_name",
                ]
            )
            for ref in listing.splitlines():
                ref = ref.strip()
                if not ref:
                    continue
                try:
                    data = self.gh.api(f"repos/{ref}/pages")
                except HostError as e:
                    if e.status_code == 404:
                        continue
                    raise
                cname = str(data.get("cname") or "").lower()
                if cname:
                    found.setdefault(cname, []).append(Site(host=self.name, ref=ref))
        return found

    def state(self, site: Site) -> SiteState:
        """Read the site's Pages configuration.

        Raises:
            HostError: If the API call fails for a reason other than 404
        """
        try:
            data = self.gh.api(f"repos/{site.ref}/pages")
        except HostError as e:
            if e.status_code != 404:
                raise
            return SiteState(configured=False)
        cert = data.get("https_certificate") or {}
        return SiteState(
            configured=True,
            custom_domain=(str(data["cname"]).lower() if data.get("cname") else None),
            https_enforced=bool(data.get("https_enforced", False)),
            cert_state=cert.get("state"),
            cert_expires=cert.get("expires_at"),
        )

    def set_custom_domain(self, site: Site, hostname: str | None) -> None:
        """Set the Pages custom domain, enabling Pages first if needed.

        With hostname None the custom domain is removed and Pages is
        left on.

        Raises:
            HostError: If an API call fails
        """
        if hostname is not None:
            self._enable_github_pages(site.ref)
        self.gh.api(f"repos/{site.ref}/pages", method="PUT", data={"cname": hostname})

    def required_records(self, site: Site, label: str) -> list[DNSRecord]:
        """Records GitHub Pages needs for a hostname.

        For an apex (label ""): four A and four AAAA records at the apex
        and a `www` CNAME. For a subdomain: one CNAME at the label. The
        CNAME target is the repository owner's github.io name.
        """
        target = f"{site.ref.split('/')[0].lower()}.github.io"
        if label:
            return [DNSRecord(type="CNAME", name=label, content=target)]
        records = [DNSRecord(type="A", name="", content=ip) for ip in GITHUB_PAGES_IPS]
        records += [DNSRecord(type="AAAA", name="", content=ip) for ip in GITHUB_PAGES_IPV6]
        records.append(DNSRecord(type="CNAME", name="www", content=target))
        return records

    def enforce_https(self, site: Site) -> bool:
        """Turn on HTTPS enforcement; False when no certificate exists yet."""
        return self.enable_https_enforcement(site.ref)

    @property
    def token(self) -> str | None:
        """The token the gh client runs with."""
        return self.gh.token

    @property
    def template_org(self) -> str:
        """Organization holding template repositories."""
        return self.repos.template_org

    def validate_template(self, template_repo: str) -> None:
        """Verify a template repository exists and is offered as a template.

        Args:
            template_repo: Template repository name (without org prefix)

        Raises:
            HostError: If the template is not found or not flagged
        """
        self.repos.validate_template(template_repo)

    def get_template_repository(self, repo_full_name: str) -> str | None:
        """Return the name of the template repository used to create a repo.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            Template repository name, or None if not created from a template
        """
        return self.repos.get_template_repository(repo_full_name)

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
            self.gh.api(f"repos/{repo_full_name}/pages")
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

        self.gh.api(
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

        self.gh.api(
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
            self.gh.api(
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
        4. Set the repository Website field to https://{domain}/ (DEC-032)
        5. Enable HTTPS enforcement (if certificate is ready)

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
            owner = self.default_org or self.gh.authenticated_user()

            repo_full_name, repo_created, repo_existed = self.repos.create_from_template(
                repo_name=domain,
                owner=owner,
                template_repo=template,
                force=force,
            )

            self._enable_github_pages(repo_full_name)
            self._set_custom_domain(repo_full_name, domain)
            self.repos.set_homepage(repo_full_name, domain)
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

    def disable_pages(self, repo_full_name: str) -> bool:
        """Disable GitHub Pages for a repository.

        Removes the Pages configuration, including any custom domain.
        Idempotent: a repository without Pages is already in the target
        state.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            True if Pages was disabled, False if it was not enabled

        Raises:
            HostError: If the API call fails for a reason other than
                Pages not being configured
        """
        try:
            self.gh.api(f"repos/{repo_full_name}/pages", method="DELETE")
        except HostError as e:
            if e.status_code != 404:
                raise
            return False
        return True

    def teardown_site(
        self, domain: str, delete_repository: bool = True
    ) -> Dict[str, Any]:
        """Tear down a site's GitHub side (inverse of deploy_site).

        Deletes the repository -- the Pages configuration and custom
        domain go with it -- or, when the repository is kept, disables
        Pages so the site stops serving. Repository deletion uses the
        REST endpoint rather than `gh repo delete` so a missing
        repository surfaces as a structured 404 instead of CLI text.

        Args:
            domain: Site domain; also the repository name (repo name ==
                domain until the site-address redesign lands)
            delete_repository: If False, keep the repository and only
                disable its Pages configuration

        Returns:
            Dict with keys: repo_full_name, repo_existed, repo_deleted,
            pages_disabled

        Raises:
            HostError: If an API call fails for a reason other than the
                target already being gone
        """
        owner = self.default_org or self.gh.authenticated_user()
        repo_full_name = f"{owner}/{domain}"
        result: Dict[str, Any] = {
            "repo_full_name": repo_full_name,
            "repo_existed": True,
            "repo_deleted": False,
            "pages_disabled": False,
        }

        if delete_repository:
            if self.repos.delete_repository_if_exists(repo_full_name):
                result["repo_deleted"] = True
            else:
                result["repo_existed"] = False
        else:
            result["pages_disabled"] = self.disable_pages(repo_full_name)

        return result

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
            data = self.gh.api(f"repos/{repo_full_name}/pages")
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

    def list_mimeo_repositories(self) -> list[Dict[str, Any]]:
        """List all repositories tagged with the 'mimeo' topic.

        Returns:
            List of repository data dictionaries

        Raises:
            HostError: If listing repositories fails
        """
        owner = self.default_org or self.gh.authenticated_user()

        # Use GitHub search API to find repos with mimeo topic
        try:
            result = self.gh.run(
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
        owner = self.default_org or self.gh.authenticated_user()
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
