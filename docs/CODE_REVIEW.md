# Mimeo Code Review

A critical review of the mimeo codebase, written for both human contributors
and LLM agents. Findings are self-contained: each states the claim, the exact
location (pinned to the commit below), the evidence, and a suggested fix.
Line numbers drift as the code changes; re-locate by symbol name if a line no
longer matches.

**Date**: 2026-09-08
**Pinned to commit**: `0c3c6ba` (main)
**Scope**: All source in `mimeo/` (~4,250 lines), all tests in `tests/`,
prior `docs/CODE_REVIEW.md` (2026-03-28), `docs/DECISIONS.md` DEC-001..DEC-026.
**Method**: Full read of every source file; cross-checked claims against
`grep` where noted; test suite executed (`uv run pytest -q`): 296 passed in
0.49s.
**Supersedes**: the 2026-03-28 review. Disposition of its findings is in the
last section.

**Session note (2026-09-08, same day)**: BUG 1, 2, 3, 5 fixed; the dead-code
table's `verify_dns` chain, `--stop-on-error`, `HTTPClient` duplication/dead
params, and the stale `config.py` comment are addressed inline in their
sections below (search "FIXED"/"REMOVED"). `default_registrar`/`default_host`
(D2) and `ProviderError` were deliberately left open -- see the table.
Full suite re-run after these changes: 289 passed (was 296; -7 net from
deleting `verify_dns`-only tests), mypy clean, ruff shows the same 5
pre-existing errors this pass didn't touch. Line numbers elsewhere in this
document are from before these edits and will have drifted; re-locate by
symbol name.

---

## Purpose and Verdict

Mimeo's stated purpose (DEC-021): a fleet manager for domain-to-GitHub-Pages
sites -- one command takes a domain from nothing to a live HTTPS site
(Porkbun registrar/DNS + GitHub Pages host), then `status`/`sync` observe and
converge the fleet. The current CLI surface is `create`, `status`, `sync`,
`doctor` (DEC-025 collapse, merged as `56d75bd`), with `template lint` planned
as Stage 6.

**Verdict: the tool achieves its purpose, and the architecture is the right
shape for its scale.** The provider seam (`Registrar`/`DNSProvider`/`Host`
ABCs in `mimeo/providers/base.py`) sits where the real concerns split, and the
DEC-025 verb collapse required zero provider-layer changes -- evidence the seam
is real. The safety engineering (DEC-022/023/026) is incident-hardened rather
than speculative. The problems below are second-order: seven small verified
bugs, one systemic brittleness (GitHub error semantics recovered by
string-matching `gh` stderr), and accumulated dead weight from the verb
collapse. Nothing threatens the core flows.

### What is working well -- do not "fix" these

An LLM making changes should treat the following as deliberate design, not
incidents to correct:

- **Declarative scope line**: `sync` never touches site content, never deletes
  DNS records it does not manage, never creates repos. This is DEC-021's
  "content is a choice, not drift" decision, restated in `sync`'s help text.
- **Rename-then-generate-then-delete** in `_create_from_template`
  (`mimeo/providers/host/github.py`), with rename-back on generate failure
  (DEC-022) and numeric-ID renames (DEC-023). This exists because
  delete-first destroyed `tepiton/laptopistan.com` once (see DEC-022 context).
- **`create`'s ownership gate and DNS-skipping** (DEC-026):
  `domain_exists` check before any GitHub work; DNS only touched when
  `deploy.repo_created` is true. The implementation of the gate has a bug
  (bug 4 below) -- fix the bug, keep the gate.
- **`map_items` fan-out engine** (`mimeo/cli/_processing.py`): ordered partial
  results, exceptions become error rows, one dispatch for text/json/csv.
  Successor commands should use it, not hand-roll thread pools.
- **Exit-code taxonomy** (`mimeo/exceptions.py` + `_categorize_error`):
  better than most CLIs. The fallthrough default is wrong (bug 5) but the
  taxonomy itself is sound.
- **`gh` CLI as the GitHub auth mechanism**: delegating token handling to `gh`
  is a legitimate choice for a personal tool. The criticism below is about
  *error parsing*, not about using `gh`.
- **Dropped propagation polls**: `create` and `sync` intentionally do not wait
  for DNS propagation (DEC-025/026). Do not re-add polling calls; `verify_dns`
  itself was dead code and has since been removed (see Dead Code).

---

## Bugs (verified)

Ordered by user impact, not severity of code damage.

### BUG 1: `domain_exists` conflates "not owned" with "API broken" -- FIXED (2026-09-08)

- **Where**: `PorkbunRegistrar.domain_exists`,
  `mimeo/providers/registrar/porkbun.py` (~line 125).
- **Claim**: the method catches *every* `RegistrarError` and returns `False`.
  `_PorkbunClient._make_request` raises `RegistrarError` for invalid
  credentials ("Porkbun API error: ..."), network failures, and rate limits
  alike -- `retry_with_jitter` re-raises the last transient error after
  retries are exhausted.
- **Consequence**: `create`'s ownership gate
  (`mimeo/cli/create.py` ~line 115) reports
  `"{domain} is not registered in this Porkbun account -- refusing to create"`
  when the real problem is an expired API key or a network outage. Every
  domain in a batch fails with the same misleading message, sending the user
  to debug ownership instead of credentials. Most user-misleading bug in the
  repo.
- **Fix applied**: `domain_exists` now only maps a `RegistrarError` whose
  message contains "domain not found" (case-insensitive) to `False`; every
  other `RegistrarError` (auth failure, network error, rate limit) propagates.
  The match string was confirmed against this repo's own Porkbun test fixtures
  (`tests/providers/registrar/test_porkbun.py`), which use `"Domain not
  found"` consistently across `updateNs`/`dns/retrieve` mocked responses --
  no live-API confirmation was done for the `getNs` endpoint specifically, so
  re-verify against real Porkbun output if `domain_exists` starts
  misclassifying again.

### BUG 2: `create --force` help text says "DNS records are not modified" -- false -- FIXED (2026-09-08)

- **Where**: `create` command docstring, `mimeo/cli/create.py` ~line 269-273.
- **Claim**: with `--force`, `repo_created` is True, so execution falls
  through to the DNS block (~line 159) and `configure_dns` deletes-then-
  recreates every managed record. DEC-026's own text says DNS is touched "on
  first creation or explicit `--force` replace."
- **Cause**: the sentence is a leftover from `template apply`'s help text that
  survived the Stage 5A merge (`template apply` was content-only and did skip
  DNS).
- **Fix applied**: corrected the sentence to say DNS records are also
  reconfigured on `--force`, unless `--skip-dns` is also passed.

### BUG 3: `status --source dns --problems` exits 0 on API errors -- FIXED (2026-09-08)

- **Where**: `_status_dns_check`, `mimeo/cli/status.py` (~line 858-927).
- **Claim**: error rows are built (both the internal `except` around
  `check_dns_drift` and `_on_error` set `error`/`error_category`), the text
  renderer prints them, but the function never calls `exit_on_errors`.
  Verified by grep: `exit_on_errors` is called at status.py lines 611
  (`_status_full`), 786 (`_status_porkbun`), 855 (`_status_dns_show`) -- and
  nowhere in `_status_dns_check` or after its `render_results`.
- **Consequence**: contradicts the documented contract ("API errors exit
  nonzero with partial results", ARCHITECTURE.md) and silently breaks scripts
  that branch on `$?`.
- **Fix applied**: added `exit_on_errors(results)` after `render_results` in
  `_status_dns_check`, matching `_status_dns_show`. `_status_github` was left
  alone, as noted below -- its semantics are a separate decision.
- **Note kept**: `_status_github` still lacks the call, but that is
  defensible-by-design -- its health-fetch failures become `health:
  "pages_error"` rows with no `error` field (treated as findings, not command
  errors), and a `list_mimeo_repositories` failure raises to the
  command-level handler. Do not "fix" `_status_github` without deciding its
  semantics first.

### BUG 4: unexpected exceptions (programming errors) categorized as "transient"

- **Where**: `_categorize_error` fallthrough, `mimeo/cli/_processing.py`
  ~line 129 (`return EXIT_TRANSIENT, "provider"`); also the command-level
  `except Exception` handlers in `status` (~line 461) and `sync` (~line 283).
- **Claim**: a `KeyError` from a dict-shape change (e.g., Porkbun or GitHub
  API response changes a field name) prints `[provider] ...` and exits 5 --
  claiming a transient network condition. Misleads both users and any
  automation retrying on exit code 5.
- **Fix**: unknown exception types should map to `EXIT_GENERAL` (1) with
  category `"error"`; reserve `EXIT_TRANSIENT` for `NetworkError`/`APIError`
  5xx/429 and the matched provider cases. `EXIT_GENERAL` currently has almost
  no users (`load_config`'s catch-all only), which is itself a smell.

### BUG 5: `--stop-on-error` flag on `create` is accepted and ignored -- FIXED (2026-09-08)

- **Where**: declared `mimeo/cli/create.py` ~line 213, bound to parameter at
  ~line 256, referenced nowhere else. Verified by grep across `mimeo/`.
- **Consequence**: users who pass it get silent continue-on-error while
  believing they requested stop-on-error.
- **Fix applied**: deleted the option and its parameter, consistent with how
  DEC-025 treated dead surface. Also removed its mentions from `README.md`
  and `docs/TROUBLESHOOTING.md` (no test referenced it).

### BUG 6: missing-`schema_version` warning is invisible to actual users

- **Where**: `Config.load`, `mimeo/config.py` ~lines 58-63 uses
  `warnings.warn(..., DeprecationWarning)`.
- **Claim**: Python hides `DeprecationWarning` outside `__main__` by default;
  CLI users never see it, only pytest does (hence the 15 warnings in the test
  run). The nudge ("Add 'schema_version = 1' to suppress this warning")
  reaches an audience of zero.
- **Fix**: print a visible line to stderr, or drop the check. Related stale
  comment at ~line 90: "GitHub username (use default_org from config, or get
  from gh CLI)" -- there is no gh fallback; `github_username` is a hard
  requirement (missing-config error at ~line 101).

### BUG 7: `get_pages_health` cannot distinguish "no Pages" from "couldn't check"

- **Where**: `GitHubHost.get_pages_health`, `mimeo/providers/host/github.py`
  ~lines 695-710: any `HostError` returns `pages_configured: False`, which
  `health_status` maps to `pages_error` (red `error` in `status`).
- **Consequence**: a transient network blip during a fleet sweep paints
  healthy sites as broken -- exactly the false alarm a monitoring tool must
  avoid, and it erodes trust in the SITE column.
- **Fix**: let the caller distinguish. Minimal: propagate unexpected
  `HostError`s and only map genuine 404 ("Pages not configured") to the
  `pages_configured: False` shape. This requires structured status codes --
  see the systemic section next; fixing this well is blocked on that.

---

## Systemic weakness: error semantics via string matching over `gh` stderr

Every GitHub operation is a subprocess (`subprocess.run(["gh", ...])`), and
the meaning of failures is recovered by substring-matching error text in
three separate places:

1. `"422" in str(e)` for rename conflicts -- `_rename_repository`,
   `github.py` ~line 228.
2. `"certificate does not exist" in str(e).lower()` for HTTPS enforcement --
   `enable_https_enforcement`, `github.py` ~line 631.
3. Keyword tuples `("502", "503", "500", "rate limit", "timeout")` in
   `mimeo/utils/retry.py` (`_TRANSIENT_HOST_KEYWORDS`, ~line 16) and again,
   differently, in `_processing.py` (`_TRANSIENT_KEYWORDS` adds
   "connection", ~line 93).

This works today because it was validated against live `gh` output, but it is
brittle across `gh` versions (error wording has changed before) and it is the
root cause shape behind BUG 1 (Porkbun), BUG 7, and the keyword lists' gradual
divergence.

**Recommended fix, incremental**: give `HostError` a `status_code` attribute
(mirror `APIError` in `mimeo/exceptions.py`); parse `HTTP <code>` from `gh`
stderr in exactly one place (`_run_gh_command`/`_gh_api` in `github.py` -- gh
prints e.g. `gh: Not Found (HTTP 404)`); make all three call sites branch on
the code instead of the text.

**Recommended fix, full**: replace the `gh` subprocess with `requests` +
`GH_TOKEN`. `GitHubHost.__init__` already accepts a `token` parameter but only
forwards it as an env var to the subprocess -- the seam exists. This also
buys speed: every GitHub call is currently a process spawn, so `status --all`
costs several spawns per domain, and every `GitHubHost` construction runs
`gh auth status` (~line 73). `create` constructs one `GitHubHost` per domain
plus one at CLI level for `validate_template`. The trade-off is taking on
token management that `gh` currently handles; for a single-user tool that is
a real cost, so the incremental fix is acceptable indefinitely.

Adjacent data-freshness risks (document nowhere; consider a `doctor` check or
a README note):

- `GITHUB_PAGES_IPS` is hardcoded (`github.py` ~line 24). GitHub publishes
  the current set at `api.github.com/meta` (`pages` field) and has changed
  them historically. A wrong list means silently pointing new domains at
  stale IPs while `status` reports "ok" against the same stale expectations.
- Fleet discovery rides `gh search repos topic:mimeo`
  (`list_mimeo_repositories`, `github.py` ~line 742). GitHub's search index
  is eventually consistent: a site created seconds ago may not appear in
  `status`, which reads as a bug to a user who doesn't know. There is also
  the search API's 1000-result cap.

---

## Design concerns (not bugs)

### D1: `sync`'s "apply N missing records" rewrites more than N

`_sync_domain` (`mimeo/cli/sync.py` ~lines 222-228) calls
`check_dns_drift`, and if anything is missing calls `configure_dns(domain,
expected)`. But `configure_dns` (`porkbun.py` ~line 232) deletes *all*
existing records whose (type, normalized-name) is in the managed set, then
recreates the full expected set. One missing record churns four correct apex
A records and the www CNAME through a delete/recreate cycle, with a brief
degraded window (TTL 600 caching masks it in practice). The action message
("apply 1 missing DNS record(s)") also under-describes what happens.
`configure_dns` also re-fetches the record list that `check_dns_drift`
just fetched (double fetch).

**Improvement**: a create-only-missing path for `sync` (Porkbun's
`/dns/create` per record needs no delete first). Keep delete-then-recreate
for `create`'s first-provision case, where clearing conflicts is the point.

### D2: provider pluggability is advertised but not wired

`Config` loads and keeps `default_registrar` / `default_host`
(`mimeo/config.py` ~lines 121-122), but every command instantiates
`PorkbunRegistrar` / `PorkbunDNSProvider` / `GitHubHost` by name. The config
fields suggest a provider factory that does not exist. Either wire one (a
simple dict lookup keyed on those fields) or drop the fields -- a config
option that does nothing is worse than no option, because it implies
support.

Related: `DNSProvider.verify_dns` is an *abstract* method (`base.py`
~line 67) that no production code calls anymore (both callers dropped in
DEC-025/026). Every future DNS provider must implement dead code. See Dead
Code below.

### D3: one `requests.Session` shared across worker threads

`status` and `sync` construct one `PorkbunRegistrar`/`PorkbunDNSProvider`
and pass them into `map_items` closures running on up to 5 threads; each
provider holds one `HTTPClient` with one `requests.Session`
(`_PorkbunClient.__init__`). urllib3's connection pool is thread-safe, but
`requests.Session` cookie handling is not formally guaranteed thread-safe.
Porkbun responses set no cookies, so the practical risk today is near zero --
this is a latent landmine, not an active bug. A per-thread client or a lock
around `_make_request` would make it a non-thought. (Note: the 2026-03-28
review's item 15 pushed *toward* shared sessions from the opposite problem --
per-domain session creation -- which was fixed; the fix overshot into the
sharing case.)

### D4: triplicated generate-race retry loop in `github.py`

The "contents API 404s on a freshly generated repo until GitHub populates the
file tree" workaround (5 attempts x 2s) is copy-pasted three times:
`_customize_default_template` (~line 356), `_delete_file` (~line 417),
`_delete_directory` (~line 457). Extract one helper (e.g.
`_get_contents_with_retry(repo, path) -> Dict | None`). Any future
contents-API consumer will otherwise copy-paste a fourth.

### D5: silently ignored flag combinations

`status --health` without `--source github` and `--problems` with
`--source github`/`porkbun` are accepted and ignored (`mimeo/cli/status.py`,
flag parsing ~lines 440-460). A one-line "ignored here" warning on stderr
would prevent confusion. Similarly `doctor` exits `EXIT_CONFIG` even for
nameserver-mismatch failures, which are not config problems.

---

## Dead code / dead surface (pre-1.0 is the cheap time to cut)

| Item | Where | Note |
|:--|:--|:--|
| `verify_dns` chain | `base.py` ABC slot, `porkbun.py` impl (only raiser of `DNSError`), ~7 mock setups in `tests/test_cli.py` | **REMOVED (2026-09-08)**. Deleted the ABC slot, the `PorkbunDNSProvider` implementation, and its now-dead imports (`time`, `Callable`, `DNSError`) from `porkbun.py`. Also deleted 6 direct unit tests in `tests/providers/registrar/test_porkbun.py`, the stub + test in `tests/test_providers_base.py`, and 10 dead `mock_dns_provider.verify_dns` preset/assert lines across `tests/test_cli.py`. Test count dropped from 296 to 289 (net -7, all `verify_dns`-only tests). |
| `--stop-on-error` | `create.py` | **REMOVED (2026-09-08)**. See BUG 5. |
| `HTTPClient.get/put/delete` | `mimeo/utils/http.py` | **PARTIALLY ADDRESSED (2026-09-08)**. Kept the public `get`/`put`/`delete` methods (still exercised by real, working tests in `tests/utils/test_http.py` -- not just dead surface), but collapsed all four verbs onto one `_request(method, ...)` helper, removing the ~90-line duplication. `post` remains the only one called by production code (`_PorkbunClient`). |
| `max_retries`/`backoff_factor` params | `http.py` `__init__` | **REMOVED (2026-09-08)**. Dropped both dead constructor params; updated `tests/utils/test_http.py::test_initialization` to match. Nothing external imported this class, and nothing passed these params in production code. |
| `default_registrar`/`default_host` | `config.py` | D2. **Deliberately left open** -- this is documented, user-facing config surface (`config.toml.example`'s `[defaults]` section, covered by `tests/test_config.py`), and the fix requires a real decision (wire a provider factory vs. drop the fields), not mechanical sweeping. Revisit as its own task. |
| `ProviderError` | `exceptions.py` | **Left as-is** -- it's the real parent of `RegistrarError`/`HostError`, not literally unreachable code; the review's own text frames this as a taxonomy-grew-ahead-of-use note, not a removal recommendation. |
| stale comment "or get from gh CLI" | `config.py` ~line 90 | **FIXED (2026-09-08)**. Comment now says the GitHub username is required with no `gh` CLI fallback. The `warnings.warn(..., DeprecationWarning)` visibility problem itself (BUG 6) is unfixed -- that's a behavior change, out of scope for this pass. |

---

## Minor and cosmetic

- Full-join EXPIRES column width computed from the untruncated date string
  but displays `[:10]` (`status.py` `_text`, ~lines 95 vs 115) -- column is
  permanently ~9 chars too wide.
- `create`'s dry-run duplicates `required_dns_records` logic
  (`create.py` ~lines 89-101) instead of calling it. It does this to avoid
  constructing a `GitHubHost` (whose `__init__` spawns `gh auth status`) --
  itself a symptom of the constructor side effect. Either accept the
  duplication with a comment or make record-construction a module function.
- `doctor` runs `gh auth status` twice (auth check + scope check) --
  `_check_gh_auth` and `_check_gh_workflow_scope` each spawn it.
- `mimeo/cli/__init__.py` exports underscore-private `_check_*` functions
  (and `_categorize_error`, `_emit`) purely for tests, via `__all__`. Works,
  but every consumer of privacy is a test is a signal the functions want a
  home (e.g., a `checks` module for doctor).
- `_check_gh_workflow_scope` parses human-readable `gh auth status` output
  ("Token scopes: ..."). Pragmatic; `gh` offers no structured scope query.
  Leave unless the full API-client migration happens.
- `_handle_response`'s `isinstance(e, requests.HTTPError): raise` branch in
  `http.py` `get/post/put/delete` is unreachable -- `_handle_response`
  converts `HTTPError` to `APIError` before it can escape.
- Domain validation regex (`_processing.py` ~line 42) is ASCII-only; IDNs
  must be punycoded by the user. Acceptable; worth a help-text mention at
  most.

---

## Test suite assessment

- 296 tests, 0.49s, fully mocked (`responses`, `unittest.mock`,
`CliRunner`). Provider layer coverage is genuinely good -- DEC-022 rollback
paths, drift math, normalization, retry behavior all have direct tests.
- The blind spot is integration reality: every incident in the decision log
  (DEC-022's destroyed repo, DEC-026's DNS-rewrite-on-existing-repo, the
  Stage 5C drift-reporting bug) was found by live testing, not by the suite.
  This is the strongest argument for Track B's E2E lane (blocked on a test
  account/org per CONTEXT.md). Priority should track unblocking it.
- `tests/test_cli.py` (1,266 lines) still has the mock-setup duplication the
  March review flagged (~163 `MagicMock`/`patch` occurrences). The March fix
  suggestion (shared "all providers mocked OK" fixture) still applies.
- Stale mock surface tracks dead code: `verify_dns` appears in ~7 test setups
  that assert nothing about it. Deleting dead code should sweep these.

---

## Recommendations (priority order)

1. ~~**Fix misleading-diagnosis bugs**: BUG 1 (`domain_exists` conflation),
   BUG 2 (`--force` help text), BUG 3 (missing `exit_on_errors`).~~ **Done
   2026-09-08.**
2. **Structure the error path**: `status_code` on `HostError`, parse gh's
   `HTTP <code>` in one place, replace keyword matching in
   `_rename_repository` / `enable_https_enforcement` / `retry.py` /
   `_processing.py`; route unexpected exceptions to `EXIT_GENERAL` (BUG 4).
   Unblocks a proper fix for BUG 7. **Not started.**
3. ~~**Land DEC-024 -- and give the manifest `TEMPLATE_DEV_PATHS` too**.~~
   **Done 2026-09-09.** `TEMPLATE_DEV_PATHS = ["README.md", "docs/"]`
   (`github.py` ~line 22) was the same class of template-specific knowledge
   as `mimeo.lol`'s hardcoded title: per-template fact encoded in mimeo's
   source. Both now live in the `mimeo.template.json` manifest
   (`template_manifest.py`, DEC-024 + addendum): dev-paths via
   `dev_paths` (defaults `README.md`/`docs/`/`CLAUDE.md`, overridable per
   template), substitution via three format handlers. Templates' own
   manifests are pending in mimeo-sites; Stage 6 (`template lint`) is
   gated on the first real manifest landing.
4. ~~**Cut the dead surface** (table above); `verify_dns`'s ABC slot is the
   one that taxes the future most.~~ **Mostly done 2026-09-08** -- `verify_dns`,
   `--stop-on-error`, `HTTPClient`'s dead ctor params and get/put/delete
   duplication, and the stale `config.py` comment are cleared. Still open:
   `default_registrar`/`default_host` (D2) and `ProviderError` -- both
   deliberately left, see the dead-code table.
5. **Track B E2E lane** -- the mocked suite's blind spot is precisely where
   every real incident has come from. **Not started; blocked on a test
   account/org per `docs/CONTEXT.md`.**
6. Longer term: fetch Pages IPs from `api.github.com/meta` (cache + hardcoded
   fallback); gentler `sync` apply path (D1); provider factory or config-field
   removal (D2). **Not started.**

---

## Disposition of the 2026-03-28 review

That review (244 tests, v0.1.0) is superseded; its findings were triaged as
part of this pass:

- **Fixed since**: README `--force-dns-update` phantom flag; env var name in
  `config.toml.example`; README structure; domain validation at CLI layer
  (`validate_domains`); ownership check (DEC-026); public
  `health_status`/provider methods for CLI-facing operations (DEC-020);
  `GITHUB_PAGES_IPS` moved to `github.py`; `check_nameservers` deduplicated
  into `PorkbunRegistrar` only; per-domain HTTP session churn in fleet
  commands (now shared -- see D3 for the new nuance); DNS-propagation silence
  (polls since dropped entirely per DEC-025/026); `NSMismatchError` and
  `Domain` dead classes (deleted with the models' slimming); destructive
  `--force` confirmation prompt (Stage 5A).
- **Still open in new form**: mock duplication in `test_cli.py`; exit-code
  edge cases (was "exit 1 never used" -- now BUG 4); `configure_dns`
  non-transactionality (accepted with re-run mitigation; D1 narrows the
  blast radius for `sync`); search-API 1000 cap (noted under systemic
  weakness); TTL-blind drift comparison (still accepted -- TTL is not part
  of desired state by design).
