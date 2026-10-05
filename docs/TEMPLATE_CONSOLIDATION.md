# Template Consolidation and the Shared Content Base

Status: **Approved in outline, not scheduled** — three decisions settled
2026-10-04 (listed under Decisions). All work lands in the tepiton
template repos plus one new tepiton repo; mimeo itself needs no code
change. Verified 2026-10-04 by grep: no template name appears in
mimeo's source, config, or tests (the two textual mentions of
folio/chapbook are a point-in-time note in `docs/IMPLEMENTATION.md` and
a test docstring whose fixtures are inline strings, not the live
repos). Sibling of `NETLIFY.md` and `SITE_ADDRESS.md`; it shares no
code with them.

## Goal

| Outcome | Check |
|---------|-------|
| Six eleventy templates; folio retired and no longer offered | `create --template eleventy-folio` fails cleanly; the tepiton org's `mimeo-template` topic lists six |
| What a portable `content/` means is written down | `CONTENT-CONTRACT.md` exists and is linked from the TEMPLATES inventory |
| The contract is enforced, not asserted | CI builds one fixture corpus against all four document templates on every change |

## Background

Facts verified against the trees 2026-10-03/04:

- chapbook, folio, and pamphlet were one task given to three LLMs;
  `docs/THREE-TAKES.md` in each of the three repos records the
  comparison. The chapbook take is the complete one (three-layout
  chain, drop caps, scene and character headings); folio's is scored
  "Partial"; pamphlet's is the minimal single-layout take.
- pamphlet is the only literary template in production
  (pesach.lol, amalgamedon.com — both single-page sites). folio and
  chapbook have no production use (user-confirmed 2026-10-04).
- The trio's content machinery is already shared:
  `chapters.11tydata.js` is byte-identical in chapbook and pamphlet;
  folio's differs in whitespace only. The content trees differ only in
  demo-chapter filenames, sitemap presence (chapbook and folio have
  `content/sitemap.xml.njk`), and folio's orphaned `content/feed/`
  directory — feed support files with no feed template, left over from
  before `@11ty/eleventy-plugin-rss` was removed as unused (2026-10-03).
- The two blogs share one content shape with each other (posts, pages,
  feed, images, `_data/metadata.js` + `eleventyDataSchema.js`); they
  differ only in which demo posts survived de-personalization.
- product/service compose pages from typed section files under
  `content/sections/`; the non-eleventy templates each take a single
  input file. Neither group can share a document content base, so both
  are out of scope by structure.
- folio's only feature chapbook lacks is `dek`: one conditional at
  `chapter.njk:8`, one in the index table of contents, and two demo
  chapters using it. chapbook contains zero `dek` references.

## Decisions (2026-10-04)

1. **Retire folio.** Port `dek` to chapbook, then archive.
2. **Portable field set: extended** — `title`, `draft`, `order`,
   `date`, `tags`, `dek`. Each template keeps its genre fields; the
   contract states what happens to a field the receiving template does
   not use.
3. **Fixture: a tepiton repo** with a GitHub Actions workflow, not a
   local script and not mimeo's test suite.

## What Needs to Happen

Four changes, in dependency order. Changes 1 and 2 need nothing from
3 and 4.

<a id="change-1"></a>

**1. Port `dek` to chapbook.**

- `eleventy-chapbook/_includes/layouts/chapter.njk`: add
  `{% if dek %}<p class="chapter-dek">{{ dek }}</p>{% endif %}` where
  folio has it (`eleventy-folio/_includes/layouts/chapter.njk:8`), plus
  the `chapter-dek` CSS folio carries.
- `eleventy-chapbook/content/index.md` (or the home layout's TOC): add
  the `{{ chapter.data.dek }}` conditional folio's index has.
- Add `dek:` to one demo chapter's front matter so the feature is
  visible in the demo build.
- Build, verify the dek renders; commit and push.

<a id="change-2"></a>

**2. Retire folio.**

In order, all reversible before the archive step:

1. Delete the orphaned `content/feed/` (dead since 2026-10-03).
2. Add one line to folio's README pointing to eleventy-chapbook.
3. Uncheck `is_template` and remove the `mimeo-template` topic on
   tepiton/eleventy-folio. This is what removes it from mimeo's
   offering — `create` uses GitHub's generate-from-template API, which
   requires `is_template`, and template selection is by name plus that
   flag.
4. Archive the repo on GitHub. folio's `docs/` are point-in-time
   records and are not edited (policy, Entry 74).
5. Update the inventories that count seven eleventy templates:
   TEMPLATES/CLAUDE.md (tables, counts, the "touch all seven"
   conventions), the TEMPLATES meta-repo `docs/CONTEXT.md`, and the
   org index `tepiton.github.io/index.md`, which lists folio (drop the
   row; date bump; push — note that repo saw an out-of-band push as
   recently as 2026-10-03, so fetch first).

<a id="change-3"></a>

**3. The content contract.**

One page, `CONTENT-CONTRACT.md`, at the root of the fixture repo
(change 4) — colocated with the thing that enforces it — linked from
TEMPLATES/CLAUDE.md. Contents:

Scope:

| In | Out |
|----|-----|
| chapbook, pamphlet, prose-blog, tech-blog | product/service — typed section files, not a document sequence |
| | pandoc-simple, pandoc-resume, mimeo, laptopistan — one input file each |

Directories: `content/chapters/` (chapbook, pamphlet),
`content/posts/` (prose-blog, tech-blog). The corpus and any user
content may carry both directories; a template renders the one it
knows and applies its base layout to the other's files.

Portable fields (the extended set) and their behavior on receipt:

| Field | Used by | Behavior in a template that does not use it |
|-------|---------|---------------------------------------------|
| `title` | all four | — |
| `draft` | all four | excluded from production builds everywhere |
| `order` | chapbook, pamphlet | ignored; falls back to 999 + filename sort |
| `date` | blogs | ignored by literary templates; a dateless chapter in a blog sorts by the blogs' fallback — verify (table below) |
| `tags` | blogs | ignored by literary templates |
| `dek` | chapbook (after change 1) | ignored elsewhere |

The contract also states what portable content must not rely on:
template-specific shortcodes or filters (footnote popovers exist only
in the blogs), and optimized image output (chapbook and the blogs run
the eleventy-img transform; pamphlet copies images through unchanged).

<a id="change-4"></a>

**4. The fixture repo and its CI.**

New tepiton repo (name: open decision 1) containing:

- `CONTENT-CONTRACT.md` (change 3)
- `content/` — the corpus:

```
content/
  chapters/
    01-opening.md        # order: 1, dek set
    02-crossing.md       # order: 2, no dek
    unnumbered.md        # no order — exercises the 999 fallback
    draft-chapter.md     # draft: true
  posts/
    2026-01-01-first.md  # date, tags
    notes.md             # footnote syntax, an image reference
```

- `.github/workflows/build.yml` — matrix over the four repos; each
  job checks out the template, overlays the corpus's `content/` onto
  the template's `content/` (the corpus ships only `chapters/` and
  `posts/`; `_data/`, the `.11tydata.js` files, `index`, `about`, and
  `404` stay template-owned), then `npm ci` and `npm run build` on
  node 24, failing the job if the build fails. Triggers: push to the
  fixture repo, weekly schedule, manual dispatch.

Build success is the first-pass check. Comparing rendered output or
asserting expected `_site/` paths is a second pass, deliberately not
in the first version.

## What Does Not Change

- pamphlet, in any way. Two production sites run it.
- product/service, the non-eleventy templates, and their content
  models.
- The blogs' front matter schemas; the extended set adds no
  requirement on them.
- folio's `docs/` and history (point-in-time records; archived with
  the repo).
- mimeo source, tests, and DEC-024 manifest handling (folio's manifest
  retires with the repo; the mechanism is generic).
- DEC-004's `.npmrc`/engines conventions in the surviving templates.

## To Verify at Implementation

| Claim | How to check |
|-------|--------------|
| Eleventy ignores front matter keys a template does not use, so a chapter with `order`/`dek` builds as a post | The fixture's first run is the check |
| Files in a directory a template has no collection for still build (under `content.11tydata.js`'s base layout) rather than erroring | Same |
| `create --template eleventy-folio` fails cleanly once `is_template` is unchecked — a `HostError`, not a stack trace | Run it after change 2 step 3 |
| Removing the `mimeo-template` topic drops folio from whatever enumerates by topic (`status`, doctor) | Run `mimeo status` after change 2 step 3 |
| Footnote markdown in a template without `markdown-it-footnote` degrades to visible literal `[^1]` text, not a build failure | Fixture corpus's `notes.md`, built in chapbook and pamphlet |
| An image referenced by portable content lands in `_site/` unchanged in templates without the img transform | Same |

## Open Decisions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | Fixture repo name | `tepiton/content-fixture` | Says what it holds; matches the topic vocabulary (`mimeo`, `mimeo-template` optional on it) |
| 2 | Corpus composition | As sketched in change 4 | Two chapters plus a fallback and a draft cover the literary fields; two posts cover date/tags/footnotes/image. Confirm at implementation against the contract text |
| 3 | Actions cadence | Push + weekly + `workflow_dispatch` | Push catches corpus drift; weekly catches template drift, since template changes do not trigger the fixture's workflow |
| 4 | Output assertions beyond build success | Not in pass one | Build failure is the contract's failure mode; path assertions duplicate each template's own demo expectations |
| 5 | Edit folio's README before archiving | Yes, one line pointing at chapbook | README is living documentation, not a point-in-time record; the archive's front page should not present folio as usable |

## Suggested Staging

Two passes, each independently landable:

1. **folio retirement** — changes 1 and 2 complete: `dek` in chapbook,
   folio cleaned, flagged, archived, inventories updated. Requires no
   new repos.
2. **Contract and fixture** — the tepiton repo with the contract,
   corpus, and workflow; ends with the first green four-way run.

Smallest slice worth shipping: pass 1 alone. Pass 2 without pass 1
would test a seven-template fleet that no longer exists.

## Appendix: Touch-Points

| Change | Where | Notes |
|--------|-------|-------|
| [1 — dek](#change-1) | tepiton/eleventy-chapbook: `chapter.njk`, home TOC (`content/index.md`), `css/`, one demo chapter | source of the lines: folio `chapter.njk:8`, `content/index.md:18` |
| [2 — retire folio](#change-2) | tepiton/eleventy-folio (feed dir, README, flags, archive); TEMPLATES/CLAUDE.md; TEMPLATES/docs/CONTEXT.md; tepiton/tepiton.github.io `index.md` | fetch tepiton.github.io first (out-of-band push seen 2026-10-03) |
| [3 — contract](#change-3) | fixture repo `CONTENT-CONTRACT.md`; link from TEMPLATES/CLAUDE.md | contract text derives from the tables in this doc |
| [4 — fixture CI](#change-4) | fixture repo `content/`, `.github/workflows/build.yml` | node 24; engines floors raised 2026-10-03 make older node invalid anyway |
