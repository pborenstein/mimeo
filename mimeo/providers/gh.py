"""The GitHub CLI (gh) as an API client, shared by the GitHub providers."""

import json
import re
import subprocess
from typing import Any, Dict

from mimeo.exceptions import HostError
from mimeo.utils.retry import retry_with_jitter

# gh prints API errors as e.g. "gh: Not Found (HTTP 404)" -- the single place
# a status code is recovered from gh stderr is _run_gh_command.
_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")


def _response_error_details(stdout: str) -> list[str]:
    """Extract the `errors` array from a failed `gh api` response body.

    gh prints only the top-level `message` to stderr ("Invalid cname");
    the cause ("... is already taken") is in the body's `errors` array,
    which gh writes to stdout. Entries are strings or objects carrying a
    `message` and/or `code`.
    """
    try:
        body = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(body, dict) or not isinstance(body.get("errors"), list):
        return []
    details: list[str] = []
    for entry in body["errors"]:
        if isinstance(entry, str):
            details.append(entry)
        elif isinstance(entry, dict):
            text = entry.get("message") or entry.get("code")
            if text:
                details.append(str(text))
    return details


class GhCli:
    """Runs gh commands and GitHub API requests through the gh CLI.

    Requires gh installed and authenticated, with a token carrying the
    'repo' and 'workflow' scopes.
    """

    def __init__(self, token: str | None = None) -> None:
        """Initialize the client and check that gh is usable.

        Args:
            token: GitHub personal access token (optional, uses gh auth if not provided)

        Raises:
            HostError: If gh CLI is not available or not authenticated
        """
        self.token = token
        self.verify()

    def verify(self) -> None:
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

    def run(self, args: list[str], input_data: str | None = None) -> str:
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
                    details = _response_error_details(result.stdout)
                    if details:
                        error_msg = f"{error_msg}: {'; '.join(details)}"
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

    def api(
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
            output = self.run(args, input_data=input_json)
        except HostError as e:
            raise HostError(f"{method} {endpoint}: {e}", status_code=e.status_code) from e

        if not output:
            return {}

        try:
            result: Dict[str, Any] = json.loads(output)
            return result
        except json.JSONDecodeError as e:
            raise HostError(f"Failed to parse GitHub API response: {e}") from e

    def authenticated_user(self) -> str:
        """Get the authenticated GitHub username.

        Returns:
            GitHub username

        Raises:
            HostError: If unable to get username
        """
        try:
            output = self.run(["api", "user", "--jq", ".login"])
            return output
        except HostError as e:
            raise HostError(
                f"Failed to get authenticated user: {e}", status_code=e.status_code
            ) from e
