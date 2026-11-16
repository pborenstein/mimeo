"""GitHub repository provider: creates and removes site repositories."""

import base64
import time
from typing import Any, Dict

from mimeo.exceptions import HostError
from mimeo.providers.base import RepoProvider
from mimeo.providers.gh import GhCli
from mimeo.providers.host.template_manifest import (
    DEFAULT_DEV_PATHS,
    MANIFEST_FILENAME,
    Substitution,
    TemplateManifest,
    apply_substitutions,
    parse_manifest,
)

TEMPLATE_ORG = "mimeo-templates"
DEFAULT_TEMPLATE = "mimeo"


class GitHubRepoProvider(RepoProvider):
    """Repository work for a site: create from a template, rename, delete.

    Holds nothing about how the site is served. A host (GitHub Pages
    today) uses it to obtain the repository it then configures.
    """

    def __init__(self, gh: GhCli, template_org: str | None = None) -> None:
        """Initialize the repository provider.

        Args:
            gh: The gh client to make requests with
            template_org: Organization holding template repositories
                (defaults to TEMPLATE_ORG)
        """
        self.gh = gh
        self.template_org = template_org or TEMPLATE_ORG

    def delete_repository(self, repo_full_name: str) -> None:
        """Delete a repository.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Raises:
            HostError: If deletion fails
        """
        self.gh.run(["repo", "delete", repo_full_name, "--yes"])

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
        repo = self.gh.api(f"repos/{repo_full_name}")
        repo_id = repo.get("id")
        if not repo_id:
            raise HostError(f"Could not determine ID for repository {repo_full_name}")

        for attempt in range(2):
            try:
                self.gh.api(f"repositories/{repo_id}", method="PATCH", data={"name": new_name})
                return
            except HostError as e:
                if attempt == 0 and e.status_code == 422:
                    time.sleep(3)
                    continue
                raise

    def _require_is_template(self, repo_full_name: str) -> None:
        """Require a repository to be flagged as a GitHub template repo.

        Generate-from-template 404s on a source repo without is_template.
        An unset flag is how a template is retired, so mimeo rejects the
        repo rather than setting the flag itself.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Raises:
            HostError: If the repo can't be read or lacks the flag
        """
        repo = self.gh.api(f"repos/{repo_full_name}")
        if not repo.get("is_template"):
            raise HostError(
                f"Template repository {repo_full_name} is not flagged as a "
                f"template (is_template unset); it may have been retired"
            )

    def create_from_template(
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
            self.gh.api(f"repos/{owner}/{repo_name}")
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
            self._require_is_template(f"{self.template_org}/{template_repo}")
            response = self.gh.api(
                f"repos/{self.template_org}/{template_repo}/generate",
                method="POST",
                data=data,
            )
            full_name = response.get("full_name")
            if not full_name:
                raise HostError(
                    f"Failed to create repository from template {self.template_org}/{template_repo}"
                )
        except HostError as e:
            if repo_existed:
                self._rename_repository(f"{owner}/{displaced_name}", repo_name)
            if e.status_code == 307:
                # GitHub redirects requests for a transferred repo, and gh
                # does not follow the redirect on POST (Entry 89).
                raise HostError(
                    f"Template {self.template_org}/{template_repo} has moved to "
                    f"another owner (GitHub answered with a redirect). Set "
                    f"github.template_org in the config to the org that holds "
                    f"it now.",
                    status_code=307,
                ) from e
            raise

        if repo_existed:
            self.delete_repository(f"{owner}/{displaced_name}")

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
            file_data = self.gh.api(
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
            self.gh.api(
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
                file_data = self.gh.api(f"repos/{repo_full_name}/contents/{path}")
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
                file_data = self.gh.api(f"repos/{repo_full_name}/contents/{path}")
                break
            except HostError:
                if attempt < 4:
                    time.sleep(2)
        if file_data is None:
            return  # File doesn't exist -- nothing to strip

        try:
            self.gh.api(
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
                entries = self.gh.api(f"repos/{repo_full_name}/contents/{path}")
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
            data = self.gh.api(f"repos/{repo_full_name}/actions/artifacts")
        except HostError:
            return  # Best-effort; don't fail the whole operation

        artifacts = [a for a in data.get("artifacts", []) if a.get("name") == "github-pages"]
        # Sort newest first; delete everything after the first entry
        artifacts.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        for artifact in artifacts[1:]:
            try:
                self.gh.api(
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

        self.gh.api(
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
                self.gh.api(f"repos/{repo_full_name}")
                return
            except HostError:
                time.sleep(2)
        raise HostError(f"Repository {repo_full_name} not accessible after {timeout}s")

    def set_homepage(self, repo_full_name: str, domain: str) -> None:
        """Set the repository's Website field to the site URL.

        Puts the site link in the repo's About sidebar. The dialog's
        "Include in the home page" checkboxes (releases/packages/
        deployments) are UI-only state with no REST or GraphQL
        surface and are deliberately not attempted (DEC-032).

        Args:
            repo_full_name: Full repository name (owner/repo)
            domain: Site domain; the Website field becomes
                https://{domain}/

        Raises:
            HostError: If the API call fails
        """
        self.gh.api(
            f"repos/{repo_full_name}",
            method="PATCH",
            data={"homepage": f"https://{domain}/"},
        )

    def validate_template(self, template_repo: str) -> None:
        """Verify a template repository exists and is offered as a template.

        Args:
            template_repo: Template repository name (without org prefix)

        Raises:
            HostError: With a clear message if the template is not found
                or not flagged as a template repository
        """
        try:
            repo = self.gh.api(f"repos/{self.template_org}/{template_repo}")
        except HostError:
            raise HostError(
                f"Template '{template_repo}' not found in {self.template_org}. "
                f"Check the spelling and try again."
            )
        if not repo.get("is_template"):
            raise HostError(
                f"Template '{template_repo}' in {self.template_org} is not "
                f"flagged as a template repository (is_template unset); "
                f"it may have been retired"
            )

    def delete_repository_if_exists(self, repo_full_name: str) -> bool:
        """Delete a repository through the REST endpoint.

        Uses the REST endpoint rather than `gh repo delete` so a missing
        repository surfaces as a structured 404 instead of CLI text.

        Args:
            repo_full_name: Full repository name (owner/repo)

        Returns:
            True if the repository was deleted, False if it did not exist

        Raises:
            HostError: If the API call fails for a reason other than 404
        """
        try:
            self.gh.api(f"repos/{repo_full_name}", method="DELETE")
        except HostError as e:
            if e.status_code != 404:
                raise
            return False
        return True
