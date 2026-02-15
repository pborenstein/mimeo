"""Tests for GitHub Pages host provider."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

from mimeo.exceptions import HostError
from mimeo.providers.host.github import GitHubHost


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

    def test_create_repository_new(self, host: GitHubHost) -> None:
        """Test creating a new repository."""
        with patch.object(host, "_gh_api") as mock_api:
            # First call checks if repo exists (raises error = doesn't exist)
            # Second call creates the repo
            mock_api.side_effect = [
                HostError("Not Found"),
                {"full_name": "testorg/example.com"},
            ]

            result = host._create_repository("example.com", org="testorg")

            assert result == "testorg/example.com"
            assert mock_api.call_count == 2

    def test_create_repository_already_exists(self, host: GitHubHost) -> None:
        """Test creating a repository that already exists."""
        with patch.object(host, "_gh_api") as mock_api:
            # Repo exists, first call succeeds
            mock_api.return_value = {"full_name": "testorg/example.com"}

            result = host._create_repository("example.com", org="testorg")

            assert result == "testorg/example.com"
            # Only one call to check if repo exists
            assert mock_api.call_count == 1

    def test_create_repository_in_user_account(self, host: GitHubHost) -> None:
        """Test creating a repository in user account (not org)."""
        with patch.object(host, "_gh_api") as mock_api:
            with patch.object(host, "_get_authenticated_user") as mock_user:
                mock_user.return_value = "testuser"
                mock_api.side_effect = [
                    HostError("Not Found"),
                    {"full_name": "testuser/example.com"},
                ]

                result = host._create_repository("example.com", org=None)

                assert result == "testuser/example.com"
                # Check that correct endpoint was used
                calls = mock_api.call_args_list
                assert calls[1][0][0] == "user/repos"

    def test_create_repository_private(self, host: GitHubHost) -> None:
        """Test creating a private repository."""
        with patch.object(host, "_gh_api") as mock_api:
            mock_api.side_effect = [
                HostError("Not Found"),
                {"full_name": "testorg/example.com"},
            ]

            host._create_repository("example.com", org="testorg", private=True)

            # Check that private flag was passed
            create_call = mock_api.call_args_list[1]
            assert create_call[1]["data"]["private"] is True

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

    def test_enable_github_pages_fallback(self, host: GitHubHost) -> None:
        """Test enabling GitHub Pages with fallback when workflow not supported."""
        with patch.object(host, "_gh_api") as mock_api:
            # First call: check (not found)
            # Second call: try with workflow (fails)
            # Third call: retry without workflow (succeeds)
            mock_api.side_effect = [
                HostError("Not Found"),
                HostError("build_type not supported"),
                {"status": "built"},
            ]

            host._enable_github_pages("testorg/example.com")

            assert mock_api.call_count == 3
            # Verify fallback didn't include build_type
            fallback_call = mock_api.call_args_list[2]
            assert "build_type" not in fallback_call[1]["data"]

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

    def test_init_and_push_repository(self, host: GitHubHost) -> None:
        """Test initializing and pushing a repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir)
            (content_path / "index.html").write_text("<h1>Test</h1>")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout=b"main",
                    stderr=b"",
                )

                host._init_and_push_repository("testorg/example.com", content_path)

                # Verify git commands were called
                calls = [call[0][0] for call in mock_run.call_args_list]
                assert ["git", "init"] in calls
                assert ["git", "add", "-A"] in calls
                assert any("commit" in call for call in calls)
                assert any("push" in call for call in calls)

    def test_init_and_push_repository_branch_rename(self, host: GitHubHost) -> None:
        """Test repository initialization with branch rename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir)
            (content_path / "index.html").write_text("<h1>Test</h1>")

            with patch("subprocess.run") as mock_run:
                # Simulate git branch --show-current returning "master"
                def run_side_effect(*args, **kwargs):
                    cmd = args[0]
                    if "branch" in cmd and "--show-current" in cmd:
                        return Mock(returncode=0, stdout="master\n", stderr="")
                    return Mock(returncode=0, stdout=b"", stderr=b"")

                mock_run.side_effect = run_side_effect

                host._init_and_push_repository("testorg/example.com", content_path)

                # Verify branch rename was called
                calls = [call[0][0] for call in mock_run.call_args_list]
                assert ["git", "branch", "-M", "main"] in calls

    def test_init_and_push_repository_git_error(self, host: GitHubHost) -> None:
        """Test git error handling during repository initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir)

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(
                    1, ["git", "init"], stderr=b"git error"
                )

                with pytest.raises(HostError) as exc_info:
                    host._init_and_push_repository("testorg/example.com", content_path)

                assert "git" in str(exc_info.value).lower()

    def test_deploy_site_success(self, host: GitHubHost) -> None:
        """Test successful site deployment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir)
            (content_path / "index.html").write_text("<h1>Test</h1>")

            with patch.object(host, "_create_repository") as mock_create:
                with patch.object(host, "_init_and_push_repository") as mock_push:
                    with patch.object(host, "_enable_github_pages") as mock_pages:
                        with patch.object(host, "_set_custom_domain") as mock_domain:
                            mock_create.return_value = "testorg/example.com"

                            url = host.deploy_site("example.com", content_path)

                            assert url == "https://example.com"
                            mock_create.assert_called_once_with("example.com")
                            mock_push.assert_called_once_with(
                                "testorg/example.com", content_path
                            )
                            mock_pages.assert_called_once_with("testorg/example.com")
                            mock_domain.assert_called_once_with(
                                "testorg/example.com", "example.com"
                            )

    def test_deploy_site_nonexistent_path(self, host: GitHubHost) -> None:
        """Test deployment fails with nonexistent content path."""
        content_path = Path("/nonexistent/path")

        with pytest.raises(HostError) as exc_info:
            host.deploy_site("example.com", content_path)

        assert "does not exist" in str(exc_info.value)

    def test_deploy_site_not_a_directory(self, host: GitHubHost) -> None:
        """Test deployment fails when content path is not a directory."""
        with tempfile.NamedTemporaryFile() as tmpfile:
            content_path = Path(tmpfile.name)

            with pytest.raises(HostError) as exc_info:
                host.deploy_site("example.com", content_path)

            assert "not a directory" in str(exc_info.value)

    def test_deploy_site_error_handling(self, host: GitHubHost) -> None:
        """Test error handling during deployment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir)

            with patch.object(host, "_create_repository") as mock_create:
                mock_create.side_effect = Exception("Unexpected error")

                with pytest.raises(HostError) as exc_info:
                    host.deploy_site("example.com", content_path)

                assert "failed to deploy" in str(exc_info.value).lower()

    def test_configure_custom_domain(self, host: GitHubHost) -> None:
        """Test configuring custom domain."""
        with patch.object(host, "_get_authenticated_user") as mock_user:
            with patch.object(host, "_set_custom_domain") as mock_set:
                mock_user.return_value = "testorg"

                host.configure_custom_domain("example.com")

                mock_set.assert_called_once_with("testorg/example.com", "example.com")

    def test_configure_custom_domain_with_default_org(self, host: GitHubHost) -> None:
        """Test configuring custom domain uses default_org."""
        with patch.object(host, "_set_custom_domain") as mock_set:
            # host fixture has default_org="testorg"
            host.configure_custom_domain("example.com")

            mock_set.assert_called_once_with("testorg/example.com", "example.com")

    def test_configure_custom_domain_error(self, host: GitHubHost) -> None:
        """Test error handling in configure_custom_domain."""
        with patch.object(host, "_set_custom_domain") as mock_set:
            mock_set.side_effect = Exception("Unexpected error")

            with pytest.raises(HostError) as exc_info:
                host.configure_custom_domain("example.com")

            assert "failed to configure" in str(exc_info.value).lower()
