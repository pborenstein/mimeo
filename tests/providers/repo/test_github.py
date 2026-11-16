"""Tests for the GitHub repository provider."""

import base64
import json
from unittest.mock import Mock, patch

import pytest

from mimeo.exceptions import HostError
from mimeo.providers.gh import GhCli
from mimeo.providers.host.template_manifest import (
    DEFAULT_DEV_PATHS,
    MANIFEST_FILENAME,
    Substitution,
    TemplateManifest,
)
from mimeo.providers.repo.github import DEFAULT_TEMPLATE, TEMPLATE_ORG, GitHubRepoProvider


class TestGitHubRepoProvider:
    """Tests for GitHubRepoProvider."""

    @pytest.fixture
    def mock_gh_auth(self) -> Mock:
        """Mock successful gh auth check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            yield mock_run

    @pytest.fixture
    def repos(self, mock_gh_auth: Mock) -> GitHubRepoProvider:
        """Create a GitHubRepoProvider for testing."""
        return GitHubRepoProvider(GhCli(token="ghp_test_token"))

    def test_create_from_template_new_repo(self, repos: GitHubRepoProvider) -> None:
        """Test creating a new repository from a template."""
        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_set_repository_topics") as mock_topics:
                with patch.object(repos, "_strip_template_dev_files") as mock_strip:
                    mock_api.side_effect = [
                        HostError("gh: Not Found (HTTP 404)", status_code=404),  # template has no manifest
                        HostError("Not Found", status_code=404),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/example.com"},  # template generate
                        {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                    ]

                    full_name, created, existed = repos.create_from_template(
                        "example.com", "testorg"
                    )

                    assert full_name == "testorg/example.com"
                    assert created is True
                    assert existed is False
                    generate_call = mock_api.call_args_list[3]
                    assert generate_call[0][0] == f"repos/{TEMPLATE_ORG}/{DEFAULT_TEMPLATE}/generate"
                    assert generate_call[1]["method"] == "POST"
                    assert generate_call[1]["data"]["owner"] == "testorg"
                    assert generate_call[1]["data"]["name"] == "example.com"
                    mock_topics.assert_called_once_with(
                        "testorg/example.com", ["mimeo", "landing-page", "github-pages"]
                    )
                    # No manifest: the default dev paths apply.
                    mock_strip.assert_called_once_with("testorg/example.com", DEFAULT_DEV_PATHS)

    def test_create_from_template_uses_custom_template_org(
        self, mock_gh_auth: Mock
    ) -> None:
        """Template generate targets the configured template org, not default_org."""
        repos = GitHubRepoProvider(GhCli(token="ghp_test_token"), template_org="mytemplates")
        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_set_repository_topics"):
                with patch.object(repos, "_strip_template_dev_files"):
                    mock_api.side_effect = [
                        HostError("gh: Not Found (HTTP 404)", status_code=404),  # template has no manifest
                        HostError("Not Found", status_code=404),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/example.com"},  # template generate
                        {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                    ]

                    full_name, created, existed = repos.create_from_template(
                        "example.com", "testorg"
                    )

                    assert full_name == "testorg/example.com"
                    assert created is True
                    generate_call = mock_api.call_args_list[3]
                    assert (
                        generate_call[0][0]
                        == f"repos/mytemplates/{DEFAULT_TEMPLATE}/generate"
                    )
                    assert generate_call[1]["data"]["owner"] == "testorg"

    def test_create_from_template_existing_repo(self, repos: GitHubRepoProvider) -> None:
        """Test that existing repos are returned without calling template API."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [
                HostError("gh: Not Found (HTTP 404)", status_code=404),  # template has no manifest
                {"full_name": "testorg/example.com"},  # repo existence check
            ]

            full_name, created, existed = repos.create_from_template("example.com", "testorg")

            assert full_name == "testorg/example.com"
            assert created is False
            assert existed is True
            assert mock_api.call_count == 2  # manifest fetch + existence check only

    def test_create_from_template_force_renames_then_deletes_old_repo(
        self, repos: GitHubRepoProvider
    ) -> None:
        """Test force replace renames the old repo out of the way, then deletes it
        only after the new repo is successfully generated."""
        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_set_repository_topics"):
                with patch.object(repos, "_strip_template_dev_files"):
                    with patch.object(repos, "_rename_repository") as mock_rename:
                        with patch.object(repos, "delete_repository") as mock_delete:
                            with patch.object(repos, "_delete_stale_pages_artifacts"):
                                with patch("time.time", return_value=1000):
                                    mock_api.side_effect = [
                                        HostError("gh: Not Found (HTTP 404)", status_code=404),  # no manifest
                                        {"full_name": "testorg/example.com"},  # existence check
                                        {"is_template": True},  # is_template check
                                        {"full_name": "testorg/example.com"},  # generate
                                        {"full_name": "testorg/example.com"},  # _wait_for_repo
                                    ]

                                    full_name, created, existed = repos.create_from_template(
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
                                mock_delete.assert_called_once_with(
                                    "testorg/example.com-mimeo-replaced-1000"
                                )

    def test_create_from_template_force_rolls_back_on_generate_failure(
        self, repos: GitHubRepoProvider
    ) -> None:
        """Test that a failed generate call renames the displaced repo back,
        instead of leaving it deleted with nothing to replace it."""
        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_rename_repository") as mock_rename:
                with patch.object(repos, "delete_repository") as mock_delete:
                    with patch("time.time", return_value=1000):
                        mock_api.side_effect = [
                            HostError("gh: Not Found (HTTP 404)", status_code=404),  # no manifest
                            {"full_name": "testorg/example.com"},  # existence check
                            {"is_template": True},  # is_template check
                            HostError("Not Found"),  # generate fails (e.g. 404)
                        ]

                        with pytest.raises(HostError):
                            repos.create_from_template("example.com", "testorg", force=True)

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

    def test_create_from_template_custom_template(self, repos: GitHubRepoProvider) -> None:
        """Test using a non-default template repo."""
        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_set_repository_topics"):
                with patch.object(repos, "_strip_template_dev_files"):
                    mock_api.side_effect = [
                        HostError("gh: Not Found (HTTP 404)", status_code=404),  # template has no manifest
                        HostError("Not Found", status_code=404),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/example.com"},  # template generate
                        {"full_name": "testorg/example.com"},  # _wait_for_repo poll
                    ]

                    repos.create_from_template(
                        "example.com", "testorg", template_repo="pandoc-simple"
                    )

                    generate_call = mock_api.call_args_list[3]
                    assert generate_call[0][0] == f"repos/{TEMPLATE_ORG}/pandoc-simple/generate"

    def test_create_from_template_missing_full_name(self, repos: GitHubRepoProvider) -> None:
        """Test HostError raised when template API response has no full_name."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [
                HostError("gh: Not Found (HTTP 404)", status_code=404),  # no manifest
                HostError("Not Found", status_code=404),  # repo existence check
                {"is_template": True},  # template repo is_template check
                {},  # no full_name
            ]

            with pytest.raises(HostError) as exc_info:
                repos.create_from_template("example.com", "testorg")

            assert "template" in str(exc_info.value).lower()

    def test_require_is_template_rejects_when_flag_false(self, repos: GitHubRepoProvider) -> None:
        """An unflagged template repo is rejected, never re-flagged by mimeo."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"full_name": "tepiton/example.com", "is_template": False}

            with pytest.raises(HostError) as exc_info:
                repos._require_is_template("tepiton/example.com")

            assert "retired" in str(exc_info.value)
            assert mock_api.call_count == 1  # read only, no PATCH

    def test_require_is_template_passes_when_already_true(self, repos: GitHubRepoProvider) -> None:
        """Test that an already-flagged template repo passes the check."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"full_name": "tepiton/example.com", "is_template": True}

            repos._require_is_template("tepiton/example.com")

            assert mock_api.call_count == 1  # read only, no PATCH

    def test_validate_template_rejects_unflagged_repo(self, repos: GitHubRepoProvider) -> None:
        """A repo that exists but lacks is_template is retired -- reject it."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"full_name": "tepiton/example.com", "is_template": False}

            with pytest.raises(HostError) as exc_info:
                repos.validate_template("example.com")

            assert "retired" in str(exc_info.value)

    def test_validate_template_accepts_flagged_repo(self, repos: GitHubRepoProvider) -> None:
        """A repo flagged as a template validates cleanly."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"full_name": "tepiton/example.com", "is_template": True}

            repos.validate_template("example.com")

            mock_api.assert_called_once_with(f"repos/{TEMPLATE_ORG}/example.com")

    def test_validate_template_not_found_message(self, repos: GitHubRepoProvider) -> None:
        """A missing template repo raises HostError with a spelling hint."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = HostError("gh: Not Found (HTTP 404)", status_code=404)

            with pytest.raises(HostError) as exc_info:
                repos.validate_template("nope")

            assert "not found" in str(exc_info.value)
            assert "spelling" in str(exc_info.value)

    def test_fetch_template_manifest_parses_valid_manifest(self, repos: GitHubRepoProvider) -> None:
        """A valid manifest is fetched from the template repo, decoded, and parsed."""
        raw = json.dumps(
            {
                "version": 1,
                "substitutions": [
                    {
                        "file": "index.html",
                        "format": "string-replace",
                        "match": "mimeo.lol",
                        "value": "{domain}",
                    },
                ],
            }
        )
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")

        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"content": encoded, "sha": "manifest-sha"}

            manifest = repos._fetch_template_manifest("mimeo.lol")

        assert manifest is not None
        assert manifest.dev_paths == DEFAULT_DEV_PATHS
        assert manifest.substitutions[0].match == "mimeo.lol"
        mock_api.assert_called_once_with(
            f"repos/{TEMPLATE_ORG}/mimeo.lol/contents/{MANIFEST_FILENAME}"
        )

    def test_fetch_template_manifest_absent_returns_none(self, repos: GitHubRepoProvider) -> None:
        """A template without a manifest is not an error -- None means defaults apply."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = HostError("gh: Not Found (HTTP 404)", status_code=404)

            assert repos._fetch_template_manifest("pandoc-simple") is None

    def test_fetch_template_manifest_invalid_fails_loud(self, repos: GitHubRepoProvider) -> None:
        """An unparseable manifest raises rather than being treated as absent."""
        encoded = base64.b64encode(b"{not json").decode("ascii")

        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"content": encoded, "sha": "manifest-sha"}

            with pytest.raises(HostError) as exc_info:
                repos._fetch_template_manifest("mimeo.lol")

            assert "not valid JSON" in str(exc_info.value)

    def test_apply_template_manifest_replaces_and_writes_once(
        self, repos: GitHubRepoProvider
    ) -> None:
        """Entries are grouped by file: one read, one write per file."""
        html = "<title>mimeo.lol</title>\n<h1>mimeo.lol</h1>\n"
        encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
        manifest = TemplateManifest(
            dev_paths=list(DEFAULT_DEV_PATHS),
            substitutions=[
                Substitution(
                    file="index.html",
                    format="string-replace",
                    match="mimeo.lol",
                    value="{domain}",
                ),
            ],
        )

        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [
                {"content": encoded, "sha": "sha1"},  # index.html read
                {},  # index.html write
            ]

            repos._apply_template_manifest(
                "testorg/tantamount.rodeo", "tantamount.rodeo", manifest
            )

            read_call, put_call = mock_api.call_args_list
            assert read_call[0][0] == "repos/testorg/tantamount.rodeo/contents/index.html"
            assert put_call[0][0] == "repos/testorg/tantamount.rodeo/contents/index.html"
            assert put_call[1]["method"] == "PUT"
            assert put_call[1]["data"]["sha"] == "sha1"
            decoded = base64.b64decode(put_call[1]["data"]["content"]).decode("utf-8")
            assert decoded == (
                "<title>tantamount.rodeo</title>\n<h1>tantamount.rodeo</h1>\n"
            )

    def test_apply_template_manifest_retries_on_empty_repo(self, repos: GitHubRepoProvider) -> None:
        """A 'repository is empty' 404 right after generate is retried, not fatal."""
        html = "<title>mimeo.lol</title><h1>mimeo.lol</h1>"
        encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
        manifest = TemplateManifest(
            dev_paths=[],
            substitutions=[
                Substitution(
                    file="index.html",
                    format="string-replace",
                    match="mimeo.lol",
                    value="{domain}",
                ),
            ],
        )

        with patch.object(repos.gh, "api") as mock_api:
            with patch("mimeo.providers.repo.github.time.sleep") as mock_sleep:
                mock_api.side_effect = [
                    HostError("This repository is empty."),
                    HostError("This repository is empty."),
                    {"content": encoded, "sha": "abc123"},
                    {},
                ]

                repos._apply_template_manifest("testorg/example.com", "example.com", manifest)

                assert mock_api.call_count == 4
                assert mock_sleep.call_count == 2

    def test_apply_template_manifest_raises_if_never_readable(self, repos: GitHubRepoProvider) -> None:
        """A target that stays unreadable is a hard error, not a silent skip."""
        manifest = TemplateManifest(
            dev_paths=[],
            substitutions=[
                Substitution(
                    file="index.html",
                    format="string-replace",
                    match="mimeo.lol",
                    value="{domain}",
                ),
            ],
        )

        with patch.object(repos.gh, "api") as mock_api:
            with patch("mimeo.providers.repo.github.time.sleep"):
                mock_api.side_effect = HostError("This repository is empty.")

                with pytest.raises(HostError):
                    repos._apply_template_manifest(
                        "testorg/example.com", "example.com", manifest
                    )

    def test_apply_template_manifest_self_deploy_is_noop(self, repos: GitHubRepoProvider) -> None:
        """Deploying a template to its own domain changes nothing (no write).

        Supersedes the old repo_name != DEFAULT_TEMPLATE gate: mimeo.lol
        deployed to mimeo.lol renders match == replacement, the no-op guard
        skips the write, and the template's own repo is never rewritten.
        """
        html = "<title>mimeo.lol</title><h1>mimeo.lol</h1>"
        encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
        manifest = TemplateManifest(
            dev_paths=[],
            substitutions=[
                Substitution(
                    file="index.html",
                    format="string-replace",
                    match="mimeo.lol",
                    value="{domain}",
                ),
            ],
        )

        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {"content": encoded, "sha": "abc123"}

            repos._apply_template_manifest("testorg/mimeo.lol", "mimeo.lol", manifest)

            assert mock_api.call_count == 1  # read only, no write

    def test_create_from_template_applies_manifest(self, repos: GitHubRepoProvider) -> None:
        """A present manifest drives dev-path stripping and substitution."""
        raw = json.dumps(
            {
                "version": 1,
                "dev_paths": ["NOTES.md"],
                "substitutions": [
                    {
                        "file": "index.html",
                        "format": "string-replace",
                        "match": "mimeo.lol",
                        "value": "{domain}",
                    },
                ],
            }
        )
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")

        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_set_repository_topics"):
                with patch.object(repos, "_strip_template_dev_files") as mock_strip:
                    with patch.object(repos, "_delete_file") as mock_delete:
                        with patch.object(repos, "_apply_template_manifest") as mock_apply:
                            mock_api.side_effect = [
                                {"content": encoded},  # manifest fetch
                                HostError("Not Found", status_code=404),  # repo existence check
                                {"is_template": True},  # is_template check
                                {"full_name": "testorg/example.com"},  # generate
                                {"full_name": "testorg/example.com"},  # _wait_for_repo
                            ]

                            repos.create_from_template("example.com", "testorg")

                            manifest = mock_apply.call_args[0][2]
                            assert manifest is not None
                            assert manifest.dev_paths == ["NOTES.md"]
                            mock_apply.assert_called_once_with(
                                "testorg/example.com", "example.com", manifest
                            )
                            mock_strip.assert_called_once_with(
                                "testorg/example.com", ["NOTES.md"]
                            )
                            # The manifest itself is authoring metadata: always stripped.
                            mock_delete.assert_called_once_with(
                                "testorg/example.com", MANIFEST_FILENAME
                            )

    def test_create_from_template_invalid_manifest_fails_before_mutation(
        self, repos: GitHubRepoProvider
    ) -> None:
        """An invalid manifest aborts before the existence check -- no partial work."""
        raw = json.dumps({"version": 2, "substitutions": []})
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")

        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [{"content": encoded}]  # manifest fetch

            with pytest.raises(HostError) as exc_info:
                repos.create_from_template("example.com", "testorg")

            assert "unsupported version" in str(exc_info.value)
            assert mock_api.call_count == 1  # manifest fetch only, nothing else touched

    def test_strip_template_dev_files_deletes_readme_and_docs(self, repos: GitHubRepoProvider) -> None:
        """Test that README.md and every file under docs/ are deleted."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [
                {"content": "", "sha": "readme-sha"},  # README.md read
                {},  # README.md delete
                [  # docs/ listing
                    {"type": "file", "name": "AUTHORING.md", "path": "docs/AUTHORING.md"},
                    {"type": "dir", "name": "guides", "path": "docs/guides"},
                ],
                {"content": "", "sha": "authoring-sha"},  # docs/AUTHORING.md read
                {},  # docs/AUTHORING.md delete
                [  # docs/guides/ listing
                    {"type": "file", "name": "setup.md", "path": "docs/guides/setup.md"},
                ],
                {"content": "", "sha": "setup-sha"},  # docs/guides/setup.md read
                {},  # docs/guides/setup.md delete
            ]

            repos._strip_template_dev_files("testorg/example.com", ["README.md", "docs/"])

            calls = [c[0][0] for c in mock_api.call_args_list]
            assert "repos/testorg/example.com/contents/README.md" in calls
            assert "repos/testorg/example.com/contents/docs" in calls
            assert "repos/testorg/example.com/contents/docs/AUTHORING.md" in calls
            assert "repos/testorg/example.com/contents/docs/guides" in calls
            assert "repos/testorg/example.com/contents/docs/guides/setup.md" in calls

    def test_strip_template_dev_files_missing_paths_are_noop(self, repos: GitHubRepoProvider) -> None:
        """Test that a template without README.md/docs/ is left untouched."""
        with patch.object(repos.gh, "api") as mock_api, \
                patch("mimeo.providers.repo.github.time.sleep"):
            mock_api.side_effect = HostError("Not Found")

            repos._strip_template_dev_files("testorg/example.com", ["README.md", "docs/"])

            # Each path's existence check retries 5x before giving up.
            assert mock_api.call_count == 10

    def test_delete_file_retries_transient_repo_empty_404(self, repos: GitHubRepoProvider) -> None:
        """A fresh repo's contents lookup can 404 before generate-from-template
        finishes populating the tree (the same race the manifest-substitution
        read path works around). _delete_file must retry rather than
        concluding the file doesn't exist and silently leaving it in place."""
        with patch.object(repos.gh, "api") as mock_api, \
                patch("mimeo.providers.repo.github.time.sleep") as mock_sleep:
            mock_api.side_effect = [
                HostError("This repository is empty"),  # not populated yet
                HostError("This repository is empty"),  # still not populated
                {"content": "", "sha": "readme-sha"},  # now it exists
                {},  # delete succeeds
            ]

            repos._delete_file("testorg/example.com", "README.md")

            assert mock_api.call_count == 4
            mock_api.assert_called_with(
                "repos/testorg/example.com/contents/README.md",
                method="DELETE",
                data={"message": "Remove template development file: README.md", "sha": "readme-sha"},
            )
            assert mock_sleep.call_count == 2

    def test_delete_file_best_effort_on_delete_failure(self, repos: GitHubRepoProvider) -> None:
        """Test that a failed delete does not raise -- stripping is best-effort."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [
                {"content": "", "sha": "readme-sha"},  # read succeeds
                HostError("locked"),  # delete fails
            ]

            repos._delete_file("testorg/example.com", "README.md")  # must not raise

    def test_wait_for_repo_retries_until_accessible(self, repos: GitHubRepoProvider) -> None:
        """Test that _wait_for_repo polls until the repo responds."""
        with patch.object(repos.gh, "api") as mock_api:
            with patch("mimeo.providers.repo.github.time.sleep") as mock_sleep:
                mock_api.side_effect = [
                    HostError("Not Found"),
                    HostError("Not Found"),
                    {"full_name": "testorg/example.com"},
                ]

                repos._wait_for_repo("testorg/example.com")

                assert mock_api.call_count == 3
                assert mock_sleep.call_count == 2

    def test_wait_for_repo_timeout(self, repos: GitHubRepoProvider) -> None:
        """Test that _wait_for_repo raises HostError when the deadline passes."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = HostError("Not Found")

            with pytest.raises(HostError) as exc_info:
                repos._wait_for_repo("testorg/example.com", timeout=0)

            assert "not accessible" in str(exc_info.value)

    def test_rename_repository_retries_once_on_422(self, repos: GitHubRepoProvider) -> None:
        """A 422 conflicting-operation error is retried once, then succeeds."""
        with patch.object(repos.gh, "api") as mock_api, \
                patch("mimeo.providers.repo.github.time.sleep") as mock_sleep:
            mock_api.side_effect = [
                {"id": 123},  # repo lookup
                HostError("gh: Conflict (HTTP 422)", status_code=422),  # first attempt
                {"ok": True},  # retry succeeds
            ]

            repos._rename_repository("testorg/old", "new")

            assert mock_api.call_count == 3
            mock_sleep.assert_called_once_with(3)

    def test_rename_repository_other_errors_raise_immediately(self, repos: GitHubRepoProvider) -> None:
        """Non-422 rename failures are not retried."""
        with patch.object(repos.gh, "api") as mock_api, \
                patch("mimeo.providers.repo.github.time.sleep") as mock_sleep:
            mock_api.side_effect = [
                {"id": 123},  # repo lookup
                HostError("gh: Not Found (HTTP 404)", status_code=404),
            ]

            with pytest.raises(HostError):
                repos._rename_repository("testorg/old", "new")

            assert mock_api.call_count == 2
            mock_sleep.assert_not_called()

    def test_set_homepage(self, repos: GitHubRepoProvider) -> None:
        """The Website field becomes the site URL with trailing slash."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.return_value = {}
            repos.set_homepage("testorg/example.com", "example.com")
            mock_api.assert_called_once_with(
                "repos/testorg/example.com",
                method="PATCH",
                data={"homepage": "https://example.com/"},
            )

    def test_set_repository_topics(self, repos: GitHubRepoProvider) -> None:
        """Test setting repository topics."""
        with patch.object(repos.gh, "api") as mock_api:
            topics = ["mimeo", "landing-page", "github-pages"]
            repos._set_repository_topics("testorg/example.com", topics)

            mock_api.assert_called_once_with(
                "repos/testorg/example.com/topics",
                method="PUT",
                data={"names": topics},
            )

    def test_create_from_template_sets_topics(self, repos: GitHubRepoProvider) -> None:
        """Test that _create_from_template sets mimeo topics on new repos."""
        with patch.object(repos.gh, "api") as mock_api:
            with patch.object(repos, "_set_repository_topics") as mock_topics:
                with patch.object(repos, "_strip_template_dev_files"):
                    mock_api.side_effect = [
                        HostError("gh: Not Found (HTTP 404)", status_code=404),  # no manifest
                        HostError("Not found", status_code=404),  # repo existence check
                        {"is_template": True},  # template repo is_template check
                        {"full_name": "testorg/test-repo"},  # template generate
                        {"full_name": "testorg/test-repo"},  # _wait_for_repo poll
                    ]

                    full_name, created, existed = repos.create_from_template(
                        "test-repo", "testorg"
                    )

        assert full_name == "testorg/test-repo"
        assert created is True
        assert existed is False
        mock_topics.assert_called_once_with(
            "testorg/test-repo",
            ["mimeo", "landing-page", "github-pages"],
        )

    def test_create_from_template_redirect_names_template_org(
        self, repos: GitHubRepoProvider
    ) -> None:
        """A 307 on generate (template repo transferred) says to fix template_org."""
        with patch.object(repos.gh, "api") as mock_api:
            mock_api.side_effect = [
                HostError("gh: Not Found (HTTP 404)", status_code=404),  # no manifest
                HostError("Not Found", status_code=404),  # repo existence check
                {"is_template": True},  # is_template check
                HostError("POST repos/x/generate: gh: HTTP 307", status_code=307),
            ]
            with pytest.raises(HostError) as exc_info:
                repos.create_from_template("example.com", "testorg")

            assert exc_info.value.status_code == 307
            assert "github.template_org" in str(exc_info.value)
