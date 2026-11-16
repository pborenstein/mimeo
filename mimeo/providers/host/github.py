"""GitHub Pages host provider implementation."""

from typing import Any

from mimeo.exceptions import HostError
from mimeo.models import DNSRecord, Site, SiteState
from mimeo.providers.base import Host
from mimeo.providers.gh import GhCli
from mimeo.providers.repo.github import DEFAULT_TEMPLATE, TEMPLATE_ORG, GitHubRepoProvider

__all__ = [
    "DEFAULT_TEMPLATE",
    "GITHUB_PAGES_IPS",
    "GITHUB_PAGES_IPV6",
    "TEMPLATE_ORG",
    "GitHubHost",
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
        self._login: str | None = None
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

    def _pages_repositories(self, org: str) -> list[str]:
        """Full names of the repositories in an organization that have Pages on.

        GitHub lists repositories through three endpoints, and only two
        of them include private ones: `user/repos` for the authenticated
        account and `orgs/{org}/repos` for an organization the account
        belongs to. `users/{name}/repos` covers any other account and
        shows public repositories only.

        Raises:
            HostError: If listing fails for a reason other than the
                account not being an organization
        """
        select = ".[] | select(.has_pages) | .full_name"
        if self._login is None:
            self._login = self.gh.authenticated_user()
        if org.lower() == self._login.lower():
            endpoints = ["user/repos?affiliation=owner&per_page=100"]
        else:
            endpoints = [f"orgs/{org}/repos?per_page=100", f"users/{org}/repos?per_page=100"]
        for i, endpoint in enumerate(endpoints):
            try:
                listing = self.gh.run(["api", "--paginate", endpoint, "--jq", select])
            except HostError as e:
                if e.status_code == 404 and i + 1 < len(endpoints):
                    continue
                raise
            return [line.strip() for line in listing.splitlines() if line.strip()]
        return []

    def scan(self) -> dict[str, list[Site]]:
        """Find every Pages site with a custom domain in the listed organizations.

        Raises:
            HostError: If an API call fails for a reason other than 404
        """
        found: dict[str, list[Site]] = {}
        for org in self.organizations:
            for ref in self._pages_repositories(org):
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
        if hostname is not None:
            # The repository's Website field (DEC-032). Not worth failing a
            # link over.
            try:
                self.repos.set_homepage(site.ref, hostname)
            except HostError:
                pass

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

    def __enter__(self) -> "GitHubHost":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        pass
