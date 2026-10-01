# Site Addresses

Status: **Proposed design** — not yet decided or scheduled. Open questions are
listed at the end; once settled they should be promoted to `DECISIONS.md`.
One of several command-model questions under consideration; expect sibling
docs rather than growth of this one. Shares its foundation with
`docs/SUBDOMAINS.md` (on ice) — see Open Decisions #6.

## Goal

Make these work the way the custom-domain version already works:

```
mimeo create example.com          # custom-domain site (today, unchanged)
mimeo create tepiton.github.io    # the org's root site
mimeo create tepiton.github.io/x  # a project site under a path
mimeo create example.com --repo foo   # custom domain on a differently-named repo
```

One command, from nothing to a live HTTPS site — including sites with no
domain of their own, served from GitHub's builtin Pages host. The larger
change: the operand of every mimeo command stops being "a domain" and
becomes "a site address."

## The Problem in One Paragraph

The argument to `mimeo create` plays five roles at once: repo name, Pages
custom domain, DNS zone, `status`/`sync` join key, and the `{domain}` value
in template manifests. `deploy_site` (`github.py:731`) ties them together —
`repo_name=domain`, `_set_custom_domain(domain)`,
`url=f"https://{domain}"` — and for every site mimeo manages today the five
values are the same string, which is what the code relies on. A
`*.github.io` site breaks that completely: the
repo is the site, the hostname is GitHub's, and there is no zone to own, no
records to write, no registrar call to make. The model underneath should be
**repo + Pages always; custom domain (and therefore a zone) optional**:

```
site address:   org.github.io/x     what the user types
repo:           x                   what the generate API creates
hostname:       org.github.io       what Pages serves under (GitHub's)
path:           /x                  project sites only
dns zone:       —                   nothing to own, check, or converge
```

## Behavior Today

The command fails cleanly, and for the same reason subdomain creates do:
the first thing `create` does after argument validation is verify ownership
(`create.py:120`), and Porkbun's answer for `tepiton.github.io` is "not
registered in this Porkbun account." Nothing is created.

Two further problems stand behind that one:

- Config load requires Porkbun credentials unconditionally (`config.py:111`)
  — even a hypothetical builtin-only operation cannot run without them.
- `deploy_site` has no branch that skips the custom-domain call; a builtin
  site would have its "custom domain" set to `org.github.io`, which is not
  ours to set.

The failure mode is safe; as with subdomains, the change is structural
because of what comes after the gate, not the gate itself.

## What Needs to Happen

Six changes, in dependency order. The first three make builtin creates
work; the rest are the fleet and plumbing work that only matters once
sites without zones exist.

**1. Parse the operand into a `SiteSpec`.** A value object
(`{repo, hostname, path, zone, mode}`) produced by one address parser used
by every command. Grammar: a `.github.io` suffix means builtin (root if
bare, project if it carries `/path` — the address names the repo either
way); anything else is a custom-domain site and parses to exactly today's
values. The suffix is unambiguous (only GitHub owns `github.io`), so the
CLI keeps a single positional argument. One optional flag, `--repo`,
decouples the repository name on custom-domain sites; the domain remains
the site's identity (URL, join key), and the repo name becomes an
implementation detail. Pointed at an existing hand-made repo, this is also
"adopt a repo and attach a domain" — the existed-repo path already
configures Pages + custom domain + DNS and warns rather than fails.

| | `example.com` | `example.com` `--repo foo` | `org.github.io` | `org.github.io/x` |
|---|---|---|---|---|
| repo | `example.com` | `foo` | `org.github.io` | `x` |
| hostname | `example.com` | `example.com` | `org.github.io` | `org.github.io` |
| path | — | — | — | `/x` |
| zone | `example.com` | `example.com` | `None` | `None` |

**2. Branch the deploy pipeline on zone presence.** Repo-from-template and
Pages-enable always run. `_set_custom_domain`, HTTPS enforcement, and the
whole registrar stage (ownership check, nameservers, records) run only when
`zone is not None`. Builtin hosts are HTTPS by default — no certificate
wait. `DeployResult.url` derives from hostname + path instead of echoing
the operand.

**3. Add a `{url}` token to the manifest grammar.** A root site works with
`{domain}` verbatim (`org.github.io`). A project site's real URL has a
path, and manifests like pandoc-resume's `https://{domain}/` would
substitute the wrong value. Add `{url}` — the full site URL, scheme +
host + path — and leave `{domain}` meaning hostname. The manifest parser
is strict, so old manifests and old mimeo binaries fail loudly rather
than silently mis-substituting; the `version` field exists for exactly
this case (DEC-024 addendum 3).

**4. Teach the fleet views builtin sites — and re-key the join.**
`status`/`sync` enumeration gains a third source: repos with Pages
enabled but no custom domain. Registrar columns render `-`, which
`status` already does for sites whose domain is absent from the
account; `sync` skips them with a reason ("builtin Pages host —
nothing to converge") rather than treating them as drift. The join
itself moves off repo-name equality (`domain in repo_names`,
`status.py:487`) onto the Pages custom-domain setting read per repo:
repo → `cname` → hostname → zone. Name membership stops matching as soon
as repo and domain decouple (change 1's `--repo` form) — and
already misses any renamed repo today — while the `cname` is what
the site actually serves. The per-repo Pages-config read this
requires is the same one that distinguishes builtin sites.

**5. Make the registrar optional.** With zone-less sites possible, Porkbun
credentials become needed only when an operation actually touches a zone.
Config validation moves from load time to registrar use, so a
GitHub-only config can manage builtin sites.

**6. Retire the repo-name invariant.** Code that assumes repo name == the
operand string — rename recovery paths, `--force` recap output, status
display — takes the `SiteSpec` instead. For project sites the repo is one
segment of the address, not the address.

## What Does NOT Need to Change

- **The templates.** The shared `pages.yml` already builds both layouts
  (its `PATHPREFIX` if/else: `.github.io` repos at `/`, everything else at
  `$REPO_NAME/` — TEMPLATES DEC-001). `tepiton.github.io` is a live root
  site from this fleet's lineage, made by hand; mimeo would standardize
  what already works.
- **The provider ABCs.** Registrar and Host are already separate; DNS is
  already conditional in practice (`--skip-dns`, and DNS is skipped when
  the repo existed). This design makes the condition explicit instead of
  incidental.
- **The existed-repo no-op.** Adopting the already-live `tepiton.github.io`
  falls out of the `repo_existed` path (DEC-027/028): warn recap, exit 0.
- **Error taxonomy, exit codes, concurrency model, output formats.**

## Open Decisions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | Whose `github.io`? Address prefix vs `--deploy-org` vs authenticated user | The prefix names the destination account (fully qualified, cf. #8): a conflicting `--deploy-org` is refused before any work; a matching one is a redundant no-op; with no flag the prefix overrides `default_org`, being explicit input. Personal sites: `user.github.io` with no flag | A repo named `tepiton.github.io` in another account never serves at `tepiton.github.io` — it becomes a path-site at `pborenstein.github.io/tepiton.github.io/`. Each fact gets one spelling |
| 2 | `{url}` within manifest version 1, or bump to 2 | Bump to 2 | An old mimeo handed a v1 manifest containing `{url}` should say "unsupported manifest version," not mis-substitute; the version field was added for precisely this |
| 3 | Are builtin sites in `status --all` / `sync --all` by default? | Yes, with `-` registrar columns; sync skips with reason | They are fleet members; hiding them recreates the "invisible hand-made site" problem `tepiton.github.io` already embodies |
| 4 | Does `{domain}` change meaning for builtin sites? | No — it stays "the hostname"; `{url}` carries the path | Grammar stability; feeds and canonical URLs want the distinction |
| 5 | Identity (DEC-021) | Record the widening when built: "Pages fleet manager; domains optional" | The wider scope becomes scope creep only if left unwritten |
| 6 | Merge with the subdomain design or stay separate? | Build `SiteSpec` now with `zone` nullable; subdomains later reuse it (`zone` = longest registered suffix) | One model, two address cases; the parked design's changes 1–2 are then already done |
| 7 | Free-form repo names on custom-domain sites (`--repo foo`)? | Allow; default stays repo = hostname | The domain is the site's identity (URL, join key); the repo name is an implementation detail. Also gives "adopt an existing repo, attach a domain" as a side effect of the existed-repo path |
| 8 | Does `--repo` apply to builtin addresses? | No — reject it | The builtin forms already name their repo in the address (`org.github.io` is the root repo; `org.github.io/x` is repo `x`); a second spelling only creates contradictions |

## Suggested Staging

Two passes, each independently landable and testable:

1. **Create path** — changes 1–3 + 5. Builtin creates work end to end
   (root and project); custom-domain behavior byte-for-byte identical.
2. **Fleet correctness** — changes 4 + 6. Enumeration, joins, skip
   reasons, and the invariant retirement, exercised against an org
   holding both kinds of site.

Sequencing note: change 1's `--repo` form stops matching in `status`
until change 4's re-keyed join lands — either ship `--repo` with pass 2
or pull the join re-key into pass 1.

Smallest shippable slice: root + project sites on the create path.

## Appendix: Code Touch-Points

Where each change lands, for implementation planning only. Referenced
against `main` at `840dfdb`.

| Change | Where | Notes |
|--------|-------|-------|
| 1 — `SiteSpec` | `mimeo/models.py` + new address parser (or `cli/_processing.py`) | parse + validate; `--repo` flag (custom-domain addresses only); used by every command's operand handling |
| 2 — pipeline branch | `mimeo/providers/host/github.py` `deploy_site` | custom-domain / HTTPS / registrar conditional on zone; `DeployResult.url` from hostname+path |
| 3 — `{url}` token | `mimeo/providers/host/template_manifest.py` | additive token + version gate (v2) |
| 4 — fleet views | `mimeo/cli/status.py`, `mimeo/cli/sync.py` | third enumeration source (Pages repos without custom domain); skip reasons; join re-keyed from repo-name membership to the Pages `cname` setting |
| 5 — registrar optional | `mimeo/config.py` | credential validation deferred from load to registrar use |
| 6 — invariant | `mimeo/cli/create.py`, `mimeo/cli/_processing.py` | thread `SiteSpec` through recap/rename/status paths |
| tests | `tests/` | Regression: custom-domain fixtures byte-identical. New: root-site adopt-existing (`tepiton.github.io`), project-site path, `{url}` substitution, zone-less sync skips |
