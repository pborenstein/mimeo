"""Tests for GitHub Pages host provider."""

import base64
from unittest.mock import Mock, patch

import pytest

from mimeo.exceptions import HostError
from mimeo.providers.host.github import DEFAULT_TEMPLATE, TEMPLATE_ORG, GitHubHost, health_status


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

    def test_initialization_without_token(self, mock_gh_auth: Mock) -> None:
        """Test GitHub host initialization without token."""
        host = GitHubHost(default_org="testorg")
        assert host.token is None
        assert host.default_org == "testorg"

    def test_verify_gh_cli_not_installed(self) -> None:
        """Test initialization fails when gh CLI is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(HostError) as exc_info:
                GitHubHost()
            assert "not installed" in str(exc_info.value)

    def test_verify_gh_cli_not_authenticated(self) -> None:
        """Test initialization fails when gh CLI is not authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
            with pytest.raises(HostError) as exc_info:
                GitHubHost()
            assert "not authenticated" in str(exc_info.value)

    def test_run_gh_command_success(self, host: GitHubHost) -> None:
        """Test running gh command successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="command output\n",
                stderr="",
            )
            result = host._run_gh_command(["api", "user"])
            assert result == "command output"

    def test_run_gh_command_failure(self, host: GitHubHost) -> None:
        """Test running gh command that fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="API error\n",
            )
            with pytest.raises(HostError) as exc_info:
                host._run_gh_command(["api", "invalid"])
            assert "API error" in str(exc_info.value)

    def test_run_gh_command_with_token(self, host: GitHubHost) -> None:
        """Test gh command uses token from environment."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="output\n", stderr="")
            host._run_gh_command(["api", "user"])

            # Verify token was passed in environment
            call_args = mock_run.call_args
            assert call_args[1]["env"]["GH_TOKEN"] == "ghp_test_token"

    def test_gh_api_get(self, host: GitHubHost) -> None:
        """Test making a GET request via gh API."""
        with patch.object(host, "_run_gh_command") as mock_cmd:
            mock_cmd.return_value = '{"login": "testuser"}'
            result = host._gh_api("user")

            assert result == {"login": "testuser"}
            mock_cmd.assert_called_once_with(
                ["api", "user", "--method", "GET"],
                input_data=None,
            )

    def test_gh_api_post_with_data(self, host: GitHubHost) -> None:
        """Test making a POST request with data via gh API."""
        with patch.object(host, "_run_gh_command") as mock_cmd:
            mock_cmd.return_value = '{"id": 123}'
            data = {"name": "test-repo"}
            result = host._gh_api("user/repos", method="POST", data=data)

            assert result == {"id": 123}
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            assert "--input" in args
            assert "-" in args

    def test_gh_api_empty_response(self, host: GitHubHost) -> None:
        """Test gh API with empty response."""
        with patch.object(host, "_run_gh_command") as mock_cmd:
            mock_cmd.return_value = ""
            result = host._gh_api("some/endpoint")
            assert result == {}

    def test_gh_api_invalid_json(self, host: GitHubHost) -> None:
        """Test gh API with invalid JSON response."""
        with patch.object(host, "_run_gh_command") as mock_cmd:
            mock_cmd.return_value = "not json"
            with pytest.raises(HostError) as exc_info:
                host._gh_api("endpoint")
            assert "parse" in str(exc_info.value).lower()

    def test_get_authenticated_user(self, host: GitHubHost) -> None:
        """Test getting authenticated user."""
        with patch.object(host, "_run_gh_command") as mock_cmd:
            mock_cmd.return_value = "testuser"
            username = host._get_authenticated_user()
            assert username == "testuser"

    def test_create_from_template_new_repo(self, host: GitHubHost) -> None:
        """Test creating a new repository from a template."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch.object(host, "_set_repository_topics") as mock_topics:
                with patch.object(host, "_customize_default_template"):
                    mock_api.side_effect = [
                        HostError("Not Found"),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/example.com"},  # template generate
                        {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                    ]

                    full_name, created, existed = host._create_from_template(
                        "example.com", "testorg"
                    )

                assert full_name == "testorg/example.com"
                assert created is True
                assert existed is False
                generate_call = mock_api.call_args_list[2]
                assert generate_call[0][0] == f"repos/{TEMPLATE_ORG}/{DEFAULT_TEMPLATE}/generate"
                assert generate_call[1]["method"] == "POST"
                assert generate_call[1]["data"]["owner"] == "testorg"
                assert generate_call[1]["data"]["name"] == "example.com"
                mock_topics.assert_called_once_with(
                    "testorg/example.com", ["mimeo", "landing-page", "github-pages"]
                )

    def test_create_from_template_existing_repo(self, host: GitHubHost) -> None:
        """Test that existing repos are returned without calling template API."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.return_value = {"full_name": "testorg/example.com"}

            full_name, created, existed = host._create_from_template("example.com", "testorg")

            assert full_name == "testorg/example.com"
            assert created is False
            assert existed is True
            assert mock_api.call_count == 1  # only the existence check

    def test_create_from_template_force_renames_then_deletes_old_repo(
        self, host: GitHubHost
    ) -> None:
        """Test force replace renames the old repo out of the way, then deletes it
        only after the new repo is successfully generated."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch.object(host, "_set_repository_topics"):
                with patch.object(host, "_customize_default_template"):
                    with patch.object(host, "_rename_repository") as mock_rename:
                        with patch.object(host, "_delete_repository") as mock_delete:
                            with patch.object(host, "_delete_stale_pages_artifacts"):
                                with patch("time.time", return_value=1000):
                                    mock_api.side_effect = [
                                        {"full_name": "testorg/example.com"},  # existence check
                                        {"is_template": True},  # is_template check
                                        {"full_name": "testorg/example.com"},  # generate
                                        {"full_name": "testorg/example.com"},  # _wait_for_repo
                                    ]

                                    full_name, created, existed = host._create_from_template(
                                        "example.com", "testorg", force=True
                                    )

                                assert full_name == "testorg/example.com"
                                assert created is True
                                assert existed is True

                                # Old repo renamed out of the way before generate was attempted.
                                mock_rename.assert_called_once_with(
                                    "testorg/example.com", "example.com-mimeo-replaced-1000"
                                )
                                # Old (renamed) repo deleted only after generate succeeded.
                                mock_delete.assert_called_once_with("testorg/example.com-mimeo-replaced-1000")

    def test_create_from_template_force_rolls_back_on_generate_failure(
        self, host: GitHubHost
    ) -> None:
        """Test that a failed generate call renames the displaced repo back,
        instead of leaving it deleted with nothing to replace it."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch.object(host, "_rename_repository") as mock_rename:
                with patch.object(host, "_delete_repository") as mock_delete:
                    with patch("time.time", return_value=1000):
                        mock_api.side_effect = [
                            {"full_name": "testorg/example.com"},  # existence check
                            {"is_template": True},  # is_template check
                            HostError("Not Found"),  # generate fails (e.g. 404)
                        ]

                        with pytest.raises(HostError):
                            host._create_from_template("example.com", "testorg", force=True)

                # Renamed away before the failed generate call...
                mock_rename.assert_any_call(
                    "testorg/example.com", "example.com-mimeo-replaced-1000"
                )
                # ...and renamed back after it failed.
                mock_rename.assert_any_call(
                    "testorg/example.com-mimeo-replaced-1000", "example.com"
                )
                assert mock_rename.call_count == 2
                # The displaced repo must never be deleted on failure.
                mock_delete.assert_not_called()

    def test_create_from_template_custom_template(self, host: GitHubHost) -> None:
        """Test using a non-default template repo."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch.object(host, "_set_repository_topics"):
                mock_api.side_effect = [
                    HostError("Not Found"),  # repo existence check
                    {"is_template": True},  # template repo is_template check
                    {"full_name": "testorg/example.com"},  # template generate
                    {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                ]

                host._create_from_template("example.com", "testorg", template_repo="pandoc-simple")

                generate_call = mock_api.call_args_list[2]
                assert generate_call[0][0] == f"repos/{TEMPLATE_ORG}/pandoc-simple/generate"

    def test_create_from_template_missing_full_name(self, host: GitHubHost) -> None:
        """Test HostError raised when template API response has no full_name."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = [
                HostError("Not Found"),
                {"is_template": True},  # template repo is_template check
                {},  # no full_name
            ]

            with pytest.raises(HostError) as exc_info:
                host._create_from_template("example.com", "testorg")

            assert "template" in str(exc_info.value).lower()

    def test_ensure_is_template_sets_flag_when_false(self, host: GitHubHost) -> None:
        """Test that a template repo missing is_template gets it set automatically."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = [
                {"full_name": "tepiton/example.com", "is_template": False},  # read
                {"is_template": True},  # PATCH
            ]

            host._ensure_is_template("tepiton/example.com")

            assert mock_api.call_count == 2
            patch_call = mock_api.call_args_list[1]
            assert patch_call[0][0] == "repos/tepiton/example.com"
            assert patch_call[1]["method"] == "PATCH"
            assert patch_call[1]["data"] == {"is_template": True}

    def test_ensure_is_template_noop_when_already_true(self, host: GitHubHost) -> None:
        """Test that an already-flagged template repo is left alone."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.return_value = {"full_name": "tepiton/example.com", "is_template": True}

            host._ensure_is_template("tepiton/example.com")

            assert mock_api.call_count == 1  # read only, no PATCH

    def test_customize_default_template_replaces_title_and_heading(
        self, host: GitHubHost
    ) -> None:
        """Test the real mimeo.lol content: plain title, letter-spaced heading."""
        content = (
            "<title>mimeo.lol</title>\n"
            "\t\t<h1>m i m e o . l o l</h1>\n"
        )
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = [
                {"content": encoded, "sha": "abc123"},  # index.html read
                {},  # index.html write
            ]

            host._customize_default_template("testorg/tantamount.rodeo", "tantamount.rodeo")

            get_call, put_call = mock_api.call_args_list
            assert get_call[0][0] == "repos/testorg/tantamount.rodeo/contents/index.html"
            assert put_call[0][0] == "repos/testorg/tantamount.rodeo/contents/index.html"
            assert put_call[1]["method"] == "PUT"
            put_data = put_call[1]["data"]
            assert put_data["sha"] == "abc123"
            decoded = base64.b64decode(put_data["content"]).decode("utf-8")
            assert "tantamount.rodeo" in decoded
            assert "t a n t a m o u n t . r o d e o" in decoded
            assert "mimeo.lol" not in decoded
            assert "m i m e o . l o l" not in decoded

    def test_customize_default_template_retries_on_empty_repo(self, host: GitHubHost) -> None:
        """Test that a 'repository is empty' 404 right after generate is retried."""
        content = "<title>mimeo.lol</title><h1>m i m e o . l o l</h1>"
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

        with patch.object(host, "_gh_api") as mock_api:
            with patch("mimeo.providers.host.github.time.sleep") as mock_sleep:
                mock_api.side_effect = [
                    HostError("This repository is empty."),
                    HostError("This repository is empty."),
                    {"content": encoded, "sha": "abc123"},
                    {},
                ]

                host._customize_default_template("testorg/example.com", "example.com")

                assert mock_api.call_count == 4
                assert mock_sleep.call_count == 2

    def test_customize_default_template_raises_if_never_readable(self, host: GitHubHost) -> None:
        """Test that a persistent read failure raises rather than being silently dropped."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch("mimeo.providers.host.github.time.sleep"):
                mock_api.side_effect = HostError("This repository is empty.")

                with pytest.raises(HostError):
                    host._customize_default_template("testorg/example.com", "example.com")

    def test_customize_default_template_skips_write_when_no_match(self, host: GitHubHost) -> None:
        """Test that no write happens when the content has already been customized."""
        content = "<title>already-custom.com</title>"
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

        with patch.object(host, "_gh_api") as mock_api:
            mock_api.return_value = {"content": encoded, "sha": "abc123"}

            host._customize_default_template("testorg/example.com", "example.com")

            assert mock_api.call_count == 1  # read only, no write

    def test_create_from_template_customizes_default_template(self, host: GitHubHost) -> None:
        """Test that _create_from_template triggers customization for the default template."""
        with patch.object(host, "_set_repository_topics"):
            with patch.object(host, "_customize_default_template") as mock_customize:
                with patch.object(host, "_gh_api") as mock_api:
                    mock_api.side_effect = [
                        HostError("Not Found"),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/example.com"},  # template generate
                        {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                    ]

                    host._create_from_template("example.com", "testorg")

                    mock_customize.assert_called_once_with("testorg/example.com", "example.com")

    def test_create_from_template_skips_customization_for_other_templates(
        self, host: GitHubHost
    ) -> None:
        """Test that non-default templates are not customized."""
        with patch.object(host, "_set_repository_topics"):
            with patch.object(host, "_customize_default_template") as mock_customize:
                with patch.object(host, "_gh_api") as mock_api:
                    mock_api.side_effect = [
                        HostError("Not Found"),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/example.com"},  # template generate
                        {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                    ]

                    host._create_from_template(
                        "example.com", "testorg", template_repo="pandoc-simple"
                    )

                    mock_customize.assert_not_called()

    def test_create_from_template_skips_customization_when_domain_is_template_name(
        self, host: GitHubHost
    ) -> None:
        """Test that mimeo.lol's own repo is never rewritten by its own template."""
        with patch.object(host, "_set_repository_topics"):
            with patch.object(host, "_customize_default_template") as mock_customize:
                with patch.object(host, "_gh_api") as mock_api:
                    mock_api.side_effect = [
                        HostError("Not Found"),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": f"testorg/{DEFAULT_TEMPLATE}"},  # template generate
                        {"full_name": f"testorg/{DEFAULT_TEMPLATE}"},  # _wait_for_repo poll
                    ]

                    host._create_from_template(DEFAULT_TEMPLATE, "testorg")

                    mock_customize.assert_not_called()

    def test_wait_for_repo_retries_until_accessible(self, host: GitHubHost) -> None:
        """Test that _wait_for_repo polls until the repo responds."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch("mimeo.providers.host.github.time.sleep") as mock_sleep:
                mock_api.side_effect = [
                    HostError("Not Found"),
                    HostError("Not Found"),
                    {"full_name": "testorg/example.com"},
                ]

                host._wait_for_repo("testorg/example.com")

                assert mock_api.call_count == 3
                assert mock_sleep.call_count == 2

    def test_wait_for_repo_timeout(self, host: GitHubHost) -> None:
        """Test that _wait_for_repo raises HostError when the deadline passes."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = HostError("Not Found")

            with pytest.raises(HostError) as exc_info:
                host._wait_for_repo("testorg/example.com", timeout=0)

            assert "not accessible" in str(exc_info.value)

    def test_enable_github_pages_new(self, host: GitHubHost) -> None:
        """Test enabling GitHub Pages for a repository."""
        with patch.object(host, "_gh_api") as mock_api:
            # First call checks if Pages exists (raises error = not enabled)
            # Second call enables Pages
            mock_api.side_effect = [
                HostError("Not Found"),
                {"status": "built"},
            ]

            host._enable_github_pages("testorg/example.com")

            assert mock_api.call_count == 2
            # Verify Pages was enabled with workflow build type
            enable_call = mock_api.call_args_list[1]
            assert enable_call[1]["data"]["build_type"] == "workflow"

    def test_enable_github_pages_already_enabled(self, host: GitHubHost) -> None:
        """Test enabling GitHub Pages when already enabled."""
        with patch.object(host, "_gh_api") as mock_api:
            # First call succeeds = Pages already enabled
            mock_api.return_value = {"status": "built"}

            host._enable_github_pages("testorg/example.com")

            # Only one call to check if Pages exists
            assert mock_api.call_count == 1

    def test_set_custom_domain(self, host: GitHubHost) -> None:
        """Test setting custom domain for GitHub Pages."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.return_value = {}

            host._set_custom_domain("testorg/example.com", "example.com")

            mock_api.assert_called_once()
            call_args = mock_api.call_args
            assert call_args[0][0] == "repos/testorg/example.com/pages"
            assert call_args[1]["method"] == "PUT"
            assert call_args[1]["data"]["cname"] == "example.com"

    def test_deploy_site_new_repo(self, host: GitHubHost) -> None:
        """Test successful deployment creates repo from template."""
        with patch.object(host, "_create_from_template") as mock_create:
            with patch.object(host, "_enable_github_pages") as mock_pages:
                with patch.object(host, "_set_custom_domain") as mock_domain:
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

    def test_deploy_site_existing_repo(self, host: GitHubHost) -> None:
        """Test deployment with existing repo returns repo_created=False."""
        with patch.object(host, "_create_from_template") as mock_create:
            with patch.object(host, "_enable_github_pages"):
                with patch.object(host, "_set_custom_domain"):
                    with patch.object(host, "enable_https_enforcement") as mock_https:
                        mock_create.return_value = ("testorg/example.com", False, True)
                        mock_https.return_value = False

                        result = host.deploy_site("example.com")

                        assert result.repo_created is False
                        assert result.repo_existed is True

    def test_deploy_site_custom_template(self, host: GitHubHost) -> None:
        """Test deployment passes custom template to _create_from_template."""
        with patch.object(host, "_create_from_template") as mock_create:
            with patch.object(host, "_enable_github_pages"):
                with patch.object(host, "_set_custom_domain"):
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
        with patch.object(host, "_create_from_template") as mock_create:
            mock_create.side_effect = Exception("Unexpected error")

            with pytest.raises(HostError) as exc_info:
                host.deploy_site("example.com")

            assert "failed to deploy" in str(exc_info.value).lower()

    def testenable_https_enforcement_success(self, host: GitHubHost) -> None:
        """Test enabling HTTPS enforcement when certificate is ready."""
        with patch.object(host, "_gh_api") as mock_api:
            result = host.enable_https_enforcement("testorg/example.com")

            assert result is True
            mock_api.assert_called_once_with(
                "repos/testorg/example.com/pages",
                method="PUT",
                data={"https_enforced": True},
            )

    def testenable_https_enforcement_certificate_not_ready(self, host: GitHubHost) -> None:
        """Test enabling HTTPS enforcement when certificate is not ready."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = HostError("The certificate does not exist yet")

            result = host.enable_https_enforcement("testorg/example.com")

            assert result is False

    def testenable_https_enforcement_other_error(self, host: GitHubHost) -> None:
        """Test that other errors during HTTPS enforcement are raised."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = HostError("Some other error")

            with pytest.raises(HostError) as exc_info:
                host.enable_https_enforcement("testorg/example.com")

            assert "Some other error" in str(exc_info.value)

    def test_set_repository_topics(self, host: GitHubHost) -> None:
        """Test setting repository topics."""
        with patch.object(host, "_gh_api") as mock_api:
            topics = ["mimeo", "landing-page", "github-pages"]
            host._set_repository_topics("testorg/example.com", topics)

            mock_api.assert_called_once_with(
                "repos/testorg/example.com/topics",
                method="PUT",
                data={"names": topics},
            )

    def test_create_from_template_sets_topics(self, host: GitHubHost) -> None:
        """Test that _create_from_template sets mimeo topics on new repos."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch.object(host, "_set_repository_topics") as mock_topics:
                with patch.object(host, "_customize_default_template"):
                    mock_api.side_effect = [
                        HostError("Not found"),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/test-repo"},  # template generate
                        {"full_name": "testorg/test-repo"},  # _wait_for_repo poll
                    ]

                    full_name, created, existed = host._create_from_template(
                        "test-repo", "testorg"
                    )

                assert full_name == "testorg/test-repo"
                assert created is True
                assert existed is False
                mock_topics.assert_called_once_with(
                    "testorg/test-repo",
                    ["mimeo", "landing-page", "github-pages"],
                )

    def test_get_pages_health_healthy(self, host: GitHubHost) -> None:
        """Test get_pages_health returns healthy data when Pages is fully configured."""
        with patch.object(host, "_gh_api") as mock_api:
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
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.return_value = {
                "https_enforced": False,
                "status": None,
            }
            result = host.get_pages_health("testorg/example.com")

            assert result["pages_configured"] is True
            assert result["https_enforced"] is False
            assert result["cert_state"] is None

    def test_get_pages_health_pages_error(self, host: GitHubHost) -> None:
        """Test get_pages_health when Pages API returns an error (404 or similar)."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = HostError("Not Found")
            result = host.get_pages_health("testorg/example.com")

            assert result["pages_configured"] is False
            assert result["https_enforced"] is False
            assert result["cert_state"] is None
            assert result["pages_status"] is None

    def test_required_dns_records(self, host: GitHubHost) -> None:
        """required_dns_records returns 4 A records + 1 CNAME."""
        from mimeo.providers.host.github import GITHUB_PAGES_IPS

        with patch.object(host, "_get_authenticated_user", return_value="testorg"):
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
        with patch.object(host, "_get_authenticated_user") as mock_user:
            records = host.required_dns_records("example.com")

        # default_org is "testorg" on the host fixture — no need to look up user
        mock_user.assert_not_called()
        cname = next(r for r in records if r.type == "CNAME")
        assert cname.content == "testorg.github.io"

    def test_list_mimeo_repositories(self, host: GitHubHost) -> None:
        """Test listing mimeo-managed repositories."""
        with patch.object(host, "_run_gh_command") as mock_gh:
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


class TestGitHubHostRetry:
    """Tests for retry behaviour in GitHubHost._run_gh_command."""

    @pytest.fixture
    def mock_gh_auth(self) -> Mock:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            yield mock_run

    @pytest.fixture
    def host(self, mock_gh_auth: Mock) -> GitHubHost:
        return GitHubHost(token="ghp_test_token", default_org="testorg")

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_502_error(self, mock_sleep, host: GitHubHost) -> None:
        """Retries when gh CLI returns a 502 error message."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="502 Bad Gateway"),
                Mock(returncode=0, stdout='{"login":"user"}', stderr=""),
            ]
            result = host._run_gh_command(["api", "user"])
            assert result == '{"login":"user"}'
            assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_503_error(self, mock_sleep, host: GitHubHost) -> None:
        """Retries when gh CLI returns a 503 error message."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="Service Unavailable 503"),
                Mock(returncode=0, stdout="ok", stderr=""),
            ]
            result = host._run_gh_command(["api", "user"])
            assert result == "ok"
            assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_rate_limit(self, mock_sleep, host: GitHubHost) -> None:
        """Retries when gh CLI reports rate limit exceeded."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="API rate limit exceeded for user"),
                Mock(returncode=0, stdout="done", stderr=""),
            ]
            result = host._run_gh_command(["api", "rate_limit"])
            assert result == "done"
            assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_no_retry_on_auth_failure(self, mock_sleep, host: GitHubHost) -> None:
        """Does not retry when gh CLI reports an authentication failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="authentication required")
            with pytest.raises(Exception):
                host._run_gh_command(["api", "user"])
            # Non-transient error — subprocess called once, no retry
            assert mock_run.call_count == 1
            mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_no_retry_on_repo_already_exists(self, mock_sleep, host: GitHubHost) -> None:
        """Does not retry when gh CLI reports repository already exists."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Name already exists on this account"
            )
            with pytest.raises(Exception):
                host._run_gh_command(["repo", "create", "my-repo"])
            assert mock_run.call_count == 1
            mock_sleep.assert_not_called()


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
