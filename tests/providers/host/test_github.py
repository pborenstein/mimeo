"""Tests for GitHub Pages host provider."""

import base64
import json
from unittest.mock import Mock, call, patch

import pytest

from mimeo.exceptions import HostError
from mimeo.models import Site
from mimeo.providers.host.github import DEFAULT_TEMPLATE, TEMPLATE_ORG, GitHubHost, health_status
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

    def test_set_custom_domain(self, host: GitHubHost) -> None:
        """Test setting custom domain for GitHub Pages."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.return_value = {}

            host._set_custom_domain("testorg/example.com", "example.com")

            mock_api.assert_called_once()
            call_args = mock_api.call_args
            assert call_args[0][0] == "repos/testorg/example.com/pages"
            assert call_args[1]["method"] == "PUT"
            assert call_args[1]["data"]["cname"] == "example.com"

    def test_deploy_site_new_repo(self, host: GitHubHost) -> None:
        """Test successful deployment creates repo from template."""
        with patch.object(host.repos, "create_from_template") as mock_create:
            with patch.object(host, "_enable_github_pages") as mock_pages:
                with patch.object(host, "_set_custom_domain") as mock_domain:
                    with patch.object(host.repos, "set_homepage") as mock_homepage:
                        with patch.object(host, "enable_https_enforcement") as mock_https:
                            mock_create.return_value = ("testorg/example.com", True, False)
                            mock_https.return_value = True

                            result = host.deploy_site("example.com")

                            assert result.url == "https://example.com"
                            assert result.repo_created is True
                            assert result.repo_existed is False
                            assert result.https_enabled is True
                            mock_create.assert_called_once_with(
                                repo_name="example.com",
                                owner="testorg",
                                template_repo=DEFAULT_TEMPLATE,
                                force=False,
                            )
                            mock_pages.assert_called_once_with("testorg/example.com")
                            mock_domain.assert_called_once_with("testorg/example.com", "example.com")
                            mock_homepage.assert_called_once_with(
                                "testorg/example.com", "example.com"
                            )

    def test_deploy_site_existing_repo(self, host: GitHubHost) -> None:
        """Test deployment with existing repo returns repo_created=False."""
        with patch.object(host.repos, "create_from_template") as mock_create:
            with patch.object(host, "_enable_github_pages"):
                with patch.object(host, "_set_custom_domain"):
                    with patch.object(host.repos, "set_homepage"):
                        with patch.object(host, "enable_https_enforcement") as mock_https:
                            mock_create.return_value = ("testorg/example.com", False, True)
                            mock_https.return_value = False

                            result = host.deploy_site("example.com")

                            assert result.repo_created is False
                            assert result.repo_existed is True

    def test_deploy_site_custom_template(self, host: GitHubHost) -> None:
        """Test deployment passes custom template to _create_from_template."""
        with patch.object(host.repos, "create_from_template") as mock_create:
            with patch.object(host, "_enable_github_pages"):
                with patch.object(host, "_set_custom_domain"):
                    with patch.object(host.repos, "set_homepage"):
                        with patch.object(host, "enable_https_enforcement", return_value=True):
                            mock_create.return_value = ("testorg/example.com", True, False)

                            host.deploy_site("example.com", template="pandoc-simple")

                            mock_create.assert_called_once_with(
                                repo_name="example.com",
                                owner="testorg",
                                template_repo="pandoc-simple",
                                force=False,
                            )

    def test_deploy_site_error_handling(self, host: GitHubHost) -> None:
        """Test unexpected errors are wrapped in HostError."""
        with patch.object(host.repos, "create_from_template") as mock_create:
            mock_create.side_effect = Exception("Unexpected error")

            with pytest.raises(HostError) as exc_info:
                host.deploy_site("example.com")

            assert "failed to deploy" in str(exc_info.value).lower()

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

    def test_get_pages_health_healthy(self, host: GitHubHost) -> None:
        """Test get_pages_health returns healthy data when Pages is fully configured."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.return_value = {
                "https_enforced": True,
                "https_certificate": {"state": "approved"},
                "status": None,
            }
            result = host.get_pages_health("testorg/example.com")

            assert result["pages_configured"] is True
            assert result["https_enforced"] is True
            assert result["cert_state"] == "approved"
            assert result["pages_status"] is None
            mock_api.assert_called_once_with("repos/testorg/example.com/pages")

    def test_get_pages_health_no_cert(self, host: GitHubHost) -> None:
        """Test get_pages_health when response has no https_certificate key."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.return_value = {
                "https_enforced": False,
                "status": None,
            }
            result = host.get_pages_health("testorg/example.com")

            assert result["pages_configured"] is True
            assert result["https_enforced"] is False
            assert result["cert_state"] is None

    def test_get_pages_health_pages_error(self, host: GitHubHost) -> None:
        """Test get_pages_health when Pages is not configured (404)."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Not Found", status_code=404)
            result = host.get_pages_health("testorg/example.com")

            assert result["pages_configured"] is False
            assert result["https_enforced"] is False
            assert result["cert_state"] is None
            assert result["pages_status"] is None

    def test_get_pages_health_check_failure_raises(self, host: GitHubHost) -> None:
        """A failed health check (non-404) propagates instead of reporting no Pages."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("gh: Server Error (HTTP 502)", status_code=502)

            with pytest.raises(HostError):
                host.get_pages_health("testorg/example.com")

    def test_required_dns_records(self, host: GitHubHost) -> None:
        """required_dns_records returns 4 A records + 1 CNAME."""
        from mimeo.providers.host.github import GITHUB_PAGES_IPS

        with patch.object(host.gh, "authenticated_user", return_value="testorg"):
            records = host.required_dns_records("example.com")

        assert len(records) == 5

        a_records = [r for r in records if r.type == "A"]
        assert len(a_records) == 4
        assert {r.content for r in a_records} == set(GITHUB_PAGES_IPS)
        for r in a_records:
            assert r.name == ""
            assert r.ttl == 600

        cname_records = [r for r in records if r.type == "CNAME"]
        assert len(cname_records) == 1
        assert cname_records[0].name == "www"
        assert cname_records[0].content == "testorg.github.io"
        assert cname_records[0].ttl == 600

    def test_required_dns_records_uses_default_org(self, host: GitHubHost) -> None:
        """required_dns_records uses default_org without calling _get_authenticated_user."""
        with patch.object(host.gh, "authenticated_user") as mock_user:
            records = host.required_dns_records("example.com")

        # default_org is "testorg" on the host fixture — no need to look up user
        mock_user.assert_not_called()
        cname = next(r for r in records if r.type == "CNAME")
        assert cname.content == "testorg.github.io"

    def test_list_mimeo_repositories(self, host: GitHubHost) -> None:
        """Test listing mimeo-managed repositories."""
        with patch.object(host.gh, "run") as mock_gh:
            mock_gh.return_value = '[{"name":"example.com","url":"https://github.com/testorg/example.com","homepage":"https://example.com","updatedAt":"2026-02-15"}]'

            repos = host.list_mimeo_repositories()

            assert len(repos) == 1
            assert repos[0]["name"] == "example.com"
            mock_gh.assert_called_once()
            call_args = mock_gh.call_args[0][0]
            assert "search" in call_args
            assert "repos" in call_args
            assert "topic:mimeo" in call_args
            assert "--limit" in call_args
            assert "1000" in call_args


class TestHealthStatus:
    """Tests for health_status helper function."""

    def test_healthy(self) -> None:
        """Returns healthy when https_enforced is True."""
        health = {
            "pages_configured": True,
            "https_enforced": True,
            "cert_state": "approved",
            "pages_status": None,
        }
        assert health_status(health) == "healthy"

    def test_fixable(self) -> None:
        """Returns fixable when cert is approved but https not enforced."""
        health = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "approved",
            "pages_status": None,
        }
        assert health_status(health) == "fixable"

    def test_cert_pending_new(self) -> None:
        """Returns cert_pending when cert state is new."""
        health = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "new",
            "pages_status": None,
        }
        assert health_status(health) == "cert_pending"

    def test_cert_pending_authorization_created(self) -> None:
        """Returns cert_pending when cert state is authorization_created."""
        health = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "authorization_created",
            "pages_status": None,
        }
        assert health_status(health) == "cert_pending"

    def test_cert_pending_issued(self) -> None:
        """Returns cert_pending when cert state is issued."""
        health = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "issued",
            "pages_status": None,
        }
        assert health_status(health) == "cert_pending"

    def test_no_cert(self) -> None:
        """Returns no_cert when cert_state is None."""
        health = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": None,
            "pages_status": None,
        }
        assert health_status(health) == "no_cert"

    def test_pages_error(self) -> None:
        """Returns pages_error when pages not configured."""
        health = {
            "pages_configured": False,
            "https_enforced": False,
            "cert_state": None,
            "pages_status": None,
        }
        assert health_status(health) == "pages_error"


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

    def test_disable_pages(self, host: GitHubHost) -> None:
        """Disabling Pages issues a DELETE against the pages endpoint."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.return_value = {}
            assert host.disable_pages("testorg/example.com") is True
            mock_api.assert_called_once_with(
                "repos/testorg/example.com/pages", method="DELETE"
            )

    def test_disable_pages_not_configured(self, host: GitHubHost) -> None:
        """A 404 (Pages not enabled) is a no-op, not an error."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Not Found", status_code=404)
            assert host.disable_pages("testorg/example.com") is False

    def test_disable_pages_other_failure_raises(self, host: GitHubHost) -> None:
        """Non-404 failures surface instead of masquerading as success."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Forbidden", status_code=403)
            with pytest.raises(HostError):
                host.disable_pages("testorg/example.com")

    def test_teardown_site_deletes_repository(self, host: GitHubHost) -> None:
        """Full teardown deletes the repo via the REST endpoint; Pages goes with it."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.return_value = {}
            result = host.teardown_site("example.com")

            mock_api.assert_called_once_with("repos/testorg/example.com", method="DELETE")
            assert result == {
                "repo_full_name": "testorg/example.com",
                "repo_existed": True,
                "repo_deleted": True,
                "pages_disabled": False,
            }

    def test_teardown_site_repository_missing(self, host: GitHubHost) -> None:
        """A missing repository is reported, not raised -- DNS may still need cleanup."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Not Found", status_code=404)
            result = host.teardown_site("example.com")

            assert result["repo_deleted"] is False
            assert result["repo_existed"] is False

    def test_teardown_site_other_failure_raises(self, host: GitHubHost) -> None:
        """A non-404 failure (auth, 5xx) must surface loudly."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Forbidden", status_code=403)
            with pytest.raises(HostError):
                host.teardown_site("example.com")

    def test_teardown_site_keep_repo_disables_pages(self, host: GitHubHost) -> None:
        """delete_repository=False spares the repo and disables Pages instead."""
        with patch.object(host.gh, "api") as mock_api:
            mock_api.return_value = {}
            result = host.teardown_site("example.com", delete_repository=False)

            mock_api.assert_called_once_with(
                "repos/testorg/example.com/pages", method="DELETE"
            )
            assert result["repo_deleted"] is False
            assert result["pages_disabled"] is True


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
        with patch.object(host.gh, "run") as run, patch.object(host.gh, "api") as api:
            run.side_effect = ["sites/a.com\nsites/plain\n", "other/odd-name\n"]
            api.side_effect = [{"cname": "a.com"}, {"cname": None}, {"cname": "b.com"}]
            found = host.scan()
        assert found == {
            "a.com": [Site("github", "sites/a.com")],
            "b.com": [Site("github", "other/odd-name")],
        }
        assert run.call_args_list[0].args[0][2] == "users/sites/repos?per_page=100"

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
