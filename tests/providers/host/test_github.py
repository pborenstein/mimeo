"""Tests for GitHub Pages host provider."""

import base64
import json
from unittest.mock import Mock, call, patch

import pytest

from mimeo.exceptions import HostError
from mimeo.models import Site
from mimeo.providers.host.github import DEFAULT_TEMPLATE, TEMPLATE_ORG, GitHubHost
from mimeo.providers.host.template_manifest import (
    DEFAULT_DEV_PATHS,
    MANIFEST_FILENAME,
    Substitution,
    TemplateManifest,
)


class TestGitHubHost:
    """Tests for GitHubHost class."""

    @pytest.fixture
    def mock_gh_auth(self) -> Mock:
        """Mock successful gh auth check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            yield mock_run

    @pytest.fixture
    def host(self, mock_gh_auth: Mock) -> GitHubHost:
        """Create GitHubHost for testing."""
        return GitHubHost(token="ghp_test_token", default_org="testorg")

    def test_initialization(self, mock_gh_auth: Mock) -> None:
        """Test GitHub host initialization."""
        host = GitHubHost(token="ghp_test_token", default_org="testorg")
        assert host.token == "ghp_test_token"
        assert host.default_org == "testorg"
        assert host.template_org == TEMPLATE_ORG

    def test_initialization_with_custom_template_org(self, mock_gh_auth: Mock) -> None:
        """A custom template_org overrides the default, independent of default_org."""
        host = GitHubHost(
            token="ghp_test_token", default_org="testorg", template_org="mytemplates"
        )
        assert host.default_org == "testorg"
        assert host.template_org == "mytemplates"

    def test_initialization_without_token(self, mock_gh_auth: Mock) -> None:
        """Test GitHub host initialization without token."""
        host = GitHubHost(default_org="testorg")
        assert host.token is None
        assert host.default_org == "testorg"

    def test_enable_github_pages_new(self, host: GitHubHost) -> None:
        """Test enabling GitHub Pages for a repository."""
        with patch.object(host.gh, "api") as mock_api:
            # First call checks if Pages exists (raises error = not enabled)
            # Second call enables Pages
            mock_api.side_effect = [
                HostError("Not Found", status_code=404),
                {"status": "built"},
            ]

            host._enable_github_pages("testorg/example.com")

            assert mock_api.call_count == 2
            # Verify Pages was enabled with workflow build type
            enable_call = mock_api.call_args_list[1]
            assert enable_call[1]["data"]["build_type"] == "workflow"

    def test_enable_github_pages_already_enabled(self, host: GitHubHost) -> None:
        """Test enabling GitHub Pages when already enabled."""
        with patch.object(host.gh, "api") as mock_api:
            # First call succeeds = Pages already enabled
            mock_api.return_value = {"status": "built"}

            host._enable_github_pages("testorg/example.com")

            # Only one call to check if Pages exists
            assert mock_api.call_count == 1

    def test_enable_github_pages_probe_failure_raises(self, host: GitHubHost) -> None:
        """Only a 404 probe means Pages needs enabling; other errors raise."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("gh: Server Error (HTTP 502)", status_code=502)

            with pytest.raises(HostError):
                host._enable_github_pages("testorg/example.com")

            # Never fell through to the enable POST
            assert mock_api.call_count == 1

    def testenable_https_enforcement_success(self, host: GitHubHost) -> None:
        """Test enabling HTTPS enforcement when certificate is ready."""
        with patch.object(host.gh, "api") as mock_api:
            result = host.enable_https_enforcement("testorg/example.com")

            assert result is True
            mock_api.assert_called_once_with(
                "repos/testorg/example.com/pages",
                method="PUT",
                data={"https_enforced": True},
            )

    def testenable_https_enforcement_certificate_not_ready(self, host: GitHubHost) -> None:
        """Test enabling HTTPS enforcement when certificate is not ready."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("The certificate does not exist yet")

            result = host.enable_https_enforcement("testorg/example.com")

            assert result is False

    def testenable_https_enforcement_other_error(self, host: GitHubHost) -> None:
        """Test that other errors during HTTPS enforcement are raised."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Some other error")

            with pytest.raises(HostError) as exc_info:
                host.enable_https_enforcement("testorg/example.com")

            assert "Some other error" in str(exc_info.value)


class TestHealthStatus:
    """Tests for health_status helper function."""


class TestTeardownSite:
    """Tests for teardown_site and disable_pages."""

    @pytest.fixture
    def mock_gh_auth(self) -> Mock:
        """Mock successful gh auth check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            yield mock_run

    @pytest.fixture
    def host(self, mock_gh_auth: Mock) -> GitHubHost:
        """Create GitHubHost for testing."""
        return GitHubHost(token="ghp_test_token", default_org="testorg")


class TestGitHubHostInterface:
    """The Host interface methods added for 2.0."""

    @pytest.fixture
    def host(self) -> GitHubHost:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            return GitHubHost(default_org="sites", organizations=["sites", "other"])

    def test_organizations_default_to_default_org(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            assert GitHubHost(default_org="sites").organizations == ["sites"]

    def test_find_site_tries_each_organization(self, host: GitHubHost) -> None:
        with patch.object(host.gh, "api") as api:
            api.side_effect = [HostError("Not Found", status_code=404), {"cname": "Example.com"}]
            assert host.find_site("example.com") == Site("github", "other/example.com")
        assert [c.args[0] for c in api.call_args_list] == [
            "repos/sites/example.com/pages", "repos/other/example.com/pages",
        ]

    def test_find_site_ignores_a_repo_serving_another_hostname(self, host: GitHubHost) -> None:
        with patch.object(host.gh, "api", return_value={"cname": "different.com"}):
            assert host.find_site("example.com") is None

    def test_find_site_surfaces_other_failures(self, host: GitHubHost) -> None:
        with patch.object(host.gh, "api", side_effect=HostError("Forbidden", status_code=403)):
            with pytest.raises(HostError):
                host.find_site("example.com")

    def test_scan_reads_custom_domain_of_every_pages_repo(self, host: GitHubHost) -> None:
        with patch.object(host.gh, "authenticated_user", return_value="someone"), patch.object(
            host.gh, "run"
        ) as run, patch.object(host.gh, "api") as api:
            run.side_effect = ["sites/a.com\nsites/plain\n", "other/odd-name\n"]
            api.side_effect = [{"cname": "a.com"}, {"cname": None}, {"cname": "b.com"}]
            found = host.scan()
        assert found == {
            "a.com": [Site("github", "sites/a.com")],
            "b.com": [Site("github", "other/odd-name")],
        }
        assert run.call_args_list[0].args[0][2] == "orgs/sites/repos?per_page=100"

    def test_scan_lists_own_account_through_the_endpoint_that_shows_private_repos(
        self, host: GitHubHost
    ) -> None:
        host.organizations = ["Someone"]
        with patch.object(host.gh, "authenticated_user", return_value="someone"), patch.object(
            host.gh, "run", return_value=""
        ) as run:
            host.scan()
        assert run.call_args.args[0][2] == "user/repos?affiliation=owner&per_page=100"

    def test_scan_falls_back_to_the_user_endpoint_for_a_non_organization(
        self, host: GitHubHost
    ) -> None:
        host.organizations = ["a-user"]
        with patch.object(host.gh, "authenticated_user", return_value="someone"), patch.object(
            host.gh, "run"
        ) as run:
            run.side_effect = [HostError("Not Found", status_code=404), ""]
            host.scan()
        assert run.call_args_list[1].args[0][2] == "users/a-user/repos?per_page=100"

    def test_state(self, host: GitHubHost) -> None:
        with patch.object(host.gh, "api") as api:
            api.return_value = {
                "cname": "example.com",
                "https_enforced": True,
                "https_certificate": {"state": "bad_authz", "expires_at": "2026-12-12"},
            }
            state = host.state(Site("github", "sites/example.com"))
        assert (state.configured, state.custom_domain, state.https_enforced) == (True, "example.com", True)
        assert (state.cert_state, state.cert_expires) == ("bad_authz", "2026-12-12")

    def test_state_without_pages(self, host: GitHubHost) -> None:
        with patch.object(host.gh, "api", side_effect=HostError("Not Found", status_code=404)):
            assert host.state(Site("github", "sites/example.com")).configured is False

    def test_set_custom_domain_enables_pages_first(self, host: GitHubHost) -> None:
        with patch.object(host, "_enable_github_pages") as enable, patch.object(host.gh, "api") as api:
            host.set_custom_domain(Site("github", "sites/x"), "example.com")
        enable.assert_called_once_with("sites/x")
        assert api.call_args_list[0] == call(
            "repos/sites/x/pages", method="PUT", data={"cname": "example.com"}
        )
        assert api.call_args_list[1] == call(
            "repos/sites/x", method="PATCH", data={"homepage": "https://example.com/"}
        )

    def test_removing_custom_domain_sends_null(self, host: GitHubHost) -> None:
        with patch.object(host, "_enable_github_pages") as enable, patch.object(host.gh, "api") as api:
            host.set_custom_domain(Site("github", "sites/x"), None)
        enable.assert_not_called()
        api.assert_called_once_with("repos/sites/x/pages", method="PUT", data={"cname": None})

    def test_required_records_for_apex(self, host: GitHubHost) -> None:
        records = host.required_records(Site("github", "Other/example.com"), "")
        assert [r.type for r in records] == ["A"] * 4 + ["AAAA"] * 4 + ["CNAME"]
        assert records[-1].name == "www"
        assert records[-1].content == "other.github.io"

    def test_required_records_for_subdomain(self, host: GitHubHost) -> None:
        records = host.required_records(Site("github", "sites/service.example.com"), "service")
        assert [(r.type, r.name, r.content) for r in records] == [("CNAME", "service", "sites.github.io")]
