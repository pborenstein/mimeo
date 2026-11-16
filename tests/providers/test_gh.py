"""Tests for the gh CLI client."""

from unittest.mock import Mock, patch

import pytest

from mimeo.exceptions import HostError
from mimeo.providers.gh import GhCli


class TestGhCli:
    """Tests for GhCli: running gh, API calls, error parsing, retry."""

    @pytest.fixture
    def mock_gh_auth(self) -> Mock:
        """Mock successful gh auth check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            yield mock_run

    @pytest.fixture
    def gh(self, mock_gh_auth: Mock) -> GhCli:
        """Create a GhCli for testing."""
        return GhCli(token="ghp_test_token")

    def test_verify_gh_cli_not_installed(self) -> None:
        """Test initialization fails when gh CLI is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(HostError) as exc_info:
                GhCli()
            assert "not installed" in str(exc_info.value)

    def test_verify_gh_cli_not_authenticated(self) -> None:
        """Test initialization fails when gh CLI is not authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
            with pytest.raises(HostError) as exc_info:
                GhCli()
            assert "not authenticated" in str(exc_info.value)

    def test_run_gh_command_success(self, gh: GhCli) -> None:
        """Test running gh command successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="command output\n",
                stderr="",
            )
            result = gh.run(["api", "user"])
            assert result == "command output"

    def test_run_gh_command_failure(self, gh: GhCli) -> None:
        """Test running gh command that fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="API error\n",
            )
            with pytest.raises(HostError) as exc_info:
                gh.run(["api", "invalid"])
            assert str(exc_info.value) == "API error"

    def test_run_gh_command_failure_parses_status_code(self, gh: GhCli) -> None:
        """gh stderr '(HTTP <code>)' is attached to the HostError."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="gh: Invalid cname (HTTP 400)\n",
            )
            with pytest.raises(HostError) as exc_info:
                gh.run(["api", "repos/o/r/pages"])
            assert exc_info.value.status_code == 400

    def test_run_gh_command_failure_without_status_code(self, gh: GhCli) -> None:
        """Errors without an HTTP code leave status_code unset."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="connection refused\n",
            )
            with pytest.raises(HostError) as exc_info:
                gh.run(["api", "user"])
            assert exc_info.value.status_code is None

    def test_run_gh_command_failure_includes_errors_array(self, gh: GhCli) -> None:
        """The response body's `errors` detail is appended to the message."""
        body = (
            '{"message":"Invalid cname","errors":[{"resource":"Page","code":"custom",'
            '"field":"cname","message":"documentation.rodeo is already taken"}],'
            '"status":"400"}'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout=body,
                stderr="gh: Invalid cname (HTTP 400)\n",
            )
            with pytest.raises(HostError) as exc_info:
                gh.run(["api", "repos/o/r/pages"])
        assert "Invalid cname (HTTP 400)" in str(exc_info.value)
        assert "documentation.rodeo is already taken" in str(exc_info.value)
        assert exc_info.value.status_code == 400

    def test_run_gh_command_failure_errors_as_strings(self, gh: GhCli) -> None:
        """String entries in `errors`, and entries with only a code, are kept."""
        body = '{"message":"Validation Failed","errors":["name too long",{"code":"invalid"}]}'
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout=body,
                stderr="gh: Validation Failed (HTTP 422)\n",
            )
            with pytest.raises(HostError) as exc_info:
                gh.run(["api", "repos/o/r"])
        assert "name too long" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    def test_run_gh_command_failure_non_json_stdout(self, gh: GhCli) -> None:
        """Non-JSON stdout leaves the stderr message unchanged."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="not json",
                stderr="gh: Not Found (HTTP 404)\n",
            )
            with pytest.raises(HostError) as exc_info:
                gh.run(["api", "repos/o/r"])
        assert str(exc_info.value) == "gh: Not Found (HTTP 404)"

    def test_run_gh_command_with_token(self, gh: GhCli) -> None:
        """Test gh command uses token from environment."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="output\n", stderr="")
            gh.run(["api", "user"])

            # Verify token was passed in environment
            call_args = mock_run.call_args
            assert call_args[1]["env"]["GH_TOKEN"] == "ghp_test_token"

    def test_gh_api_get(self, gh: GhCli) -> None:
        """Test making a GET request via gh API."""
        with patch.object(gh, "run") as mock_cmd:
            mock_cmd.return_value = '{"login": "testuser"}'
            result = gh.api("user")

            assert result == {"login": "testuser"}
            mock_cmd.assert_called_once_with(
                ["api", "user", "--method", "GET"],
                input_data=None,
            )

    def test_gh_api_failure_preserves_status_code(self, gh: GhCli) -> None:
        """_gh_api's re-wrapped HostError keeps the parsed status code."""
        with patch.object(gh, "run") as mock_cmd:
            mock_cmd.side_effect = HostError("gh: Not Found (HTTP 404)", status_code=404)

            with pytest.raises(HostError) as exc_info:
                gh.api("repos/o/r/pages", method="PUT")

            assert exc_info.value.status_code == 404
            assert "PUT repos/o/r/pages" in str(exc_info.value)

    def test_gh_api_post_with_data(self, gh: GhCli) -> None:
        """Test making a POST request with data via gh API."""
        with patch.object(gh, "run") as mock_cmd:
            mock_cmd.return_value = '{"id": 123}'
            data = {"name": "test-repo"}
            result = gh.api("user/repos", method="POST", data=data)

            assert result == {"id": 123}
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            assert "--input" in args
            assert "-" in args

    def test_gh_api_empty_response(self, gh: GhCli) -> None:
        """Test gh API with empty response."""
        with patch.object(gh, "run") as mock_cmd:
            mock_cmd.return_value = ""
            result = gh.api("some/endpoint")
            assert result == {}

    def test_gh_api_invalid_json(self, gh: GhCli) -> None:
        """Test gh API with invalid JSON response."""
        with patch.object(gh, "run") as mock_cmd:
            mock_cmd.return_value = "not json"
            with pytest.raises(HostError) as exc_info:
                gh.api("endpoint")
            assert "parse" in str(exc_info.value).lower()

    def test_get_authenticated_user(self, gh: GhCli) -> None:
        """Test getting authenticated user."""
        with patch.object(gh, "run") as mock_cmd:
            mock_cmd.return_value = "testuser"
            username = gh.authenticated_user()
            assert username == "testuser"

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_502_error(self, mock_sleep, gh: GhCli) -> None:
        """Retries when gh CLI returns a 502 error message."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="502 Bad Gateway"),
                Mock(returncode=0, stdout='{"login":"user"}', stderr=""),
            ]
            result = gh.run(["api", "user"])
            assert result == '{"login":"user"}'
            assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_503_error(self, mock_sleep, gh: GhCli) -> None:
        """Retries when gh CLI returns a 503 error message."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="Service Unavailable 503"),
                Mock(returncode=0, stdout="ok", stderr=""),
            ]
            result = gh.run(["api", "user"])
            assert result == "ok"
            assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_rate_limit(self, mock_sleep, gh: GhCli) -> None:
        """Retries when gh CLI reports rate limit exceeded."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr="API rate limit exceeded for user"),
                Mock(returncode=0, stdout="done", stderr=""),
            ]
            result = gh.run(["api", "rate_limit"])
            assert result == "done"
            assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_no_retry_on_auth_failure(self, mock_sleep, gh: GhCli) -> None:
        """Does not retry when gh CLI reports an authentication failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="authentication required")
            with pytest.raises(Exception):
                gh.run(["api", "user"])
            # Non-transient error — subprocess called once, no retry
            assert mock_run.call_count == 1
            mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_no_retry_on_repo_already_exists(self, mock_sleep, gh: GhCli) -> None:
        """Does not retry when gh CLI reports repository already exists."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Name already exists on this account"
            )
            with pytest.raises(Exception):
                gh.run(["repo", "create", "my-repo"])
            assert mock_run.call_count == 1
            mock_sleep.assert_not_called()
