"""Tests for the per-template substitution manifest (DEC-024).

Handler fixtures mirror the real template files the schema was designed
against: eleventy-tech-blog's metadata.js (comments, nested objects, a
process.env value, a placeholder email on a neighboring line), pamphlet's
eleventy.config.js (self-reference inside an addPlugin options object),
pandoc-simple's frontmatter, and the HTML titles of mimeo.lol and
laptopistan.com.
"""

import json

import pytest

from mimeo.exceptions import HostError
from mimeo.providers.host.template_manifest import (
    DEFAULT_DEV_PATHS,
    Substitution,
    apply_substitutions,
    parse_manifest,
)

TECH_BLOG_METADATA_JS = """export default {
\t// Site metadata
\ttitle: "Tech Blog",
\turl: "https://example.com/",
\tlanguage: "en",
\tdescription: "A description of this site.",
\ttagline: "A tagline for this site.",

\t// Author information
\tauthor: {
\t\tname: "Author Name",
\t\temail: "author@example.com",
\t\turl: "https://example.com/about/",
\t\tsocial: { github: "", bluesky: "" }
\t},

\t// Feed configuration
\tfeed: {
\t\tsubtitle: "A tagline for this site.",
\t\tpath: "/feed/feed.xml",
\t\tid: "https://example.com/",
\t\tlimit: 10
\t},

\t// Build configuration
\tbuild: {
\t\tenvironment: process.env.ELEVENTY_ENV || "development"
\t}
}
"""

PAMPHLET_CONFIG_JS = """module.exports = function (eleventyConfig) {
  eleventyConfig.addPlugin(feedPlugin, {
    type: "atom",
    outputPath: "/feed/feed.xml",
    collection: {
      name: "chapters",
      limit: 10,
    },
    metadata: {
      language: "en",
      title: "My Literary Work",
      subtitle: "A description of this work",
      base: "https://example.com/",
      author: {
        name: "Your Name"
      }
    }
  });

  return {
    dir: {
      input: "content",
      includes: "../_includes",
      data: "_data",
      output: "_site"
    }
  };
};
"""

PANDOC_SIMPLE_INDEX_MD = """---
title: "Document Title"
subtitle: "Subtitle or tagline"
author: "Author Name"
date: 2026-01-01
description: "A brief description of this document and what it contains."
---

A short opening passage or epigraph.
"""

MIMEO_LOL_INDEX_HTML = """<html>
\t<head>
\t\t<title>mimeo.lol</title>
\t</head>
\t<body>
\t\t<h1>mimeo.lol</h1>
\t</body>
</html>
"""

LAPTOPISTAN_INDEX_HTML = """<html>
  <head><title>laptopistan.com</title></head>
  <body>
    <div class="lbl">laptopistan.com</div>
  </body>
</html>
"""


def _manifest_json(**overrides: object) -> str:
    """Build a minimal valid manifest, with overrides applied."""
    doc: dict[str, object] = {
        "version": 1,
        "substitutions": [
            {
                "file": "index.html",
                "format": "string-replace",
                "match": "mimeo.lol",
                "value": "{domain}",
            }
        ],
    }
    doc.update(overrides)
    return json.dumps(doc)


class TestParseManifest:
    """Validation of mimeo.template.json documents."""

    def test_minimal_manifest_defaults(self) -> None:
        """Omitted dev_paths means the default strip list applies."""
        manifest = parse_manifest(_manifest_json())
        assert manifest.dev_paths == DEFAULT_DEV_PATHS
        assert manifest.dev_paths == ["README.md", "docs/", "CLAUDE.md"]
        assert len(manifest.substitutions) == 1
        sub = manifest.substitutions[0]
        assert sub.file == "index.html"
        assert sub.match == "mimeo.lol"
        assert sub.key is None

    def test_dev_paths_override_replaces_defaults(self) -> None:
        """A declared dev_paths replaces the default list wholesale."""
        manifest = parse_manifest(_manifest_json(dev_paths=["NOTES.md", "internal/"]))
        assert manifest.dev_paths == ["NOTES.md", "internal/"]

    def test_not_json(self) -> None:
        with pytest.raises(HostError, match="not valid JSON"):
            parse_manifest("{not json")

    def test_not_an_object(self) -> None:
        with pytest.raises(HostError, match="must be a JSON object"):
            parse_manifest("[]")

    def test_unknown_top_level_field(self) -> None:
        with pytest.raises(HostError, match="unknown field.*banana"):
            parse_manifest(_manifest_json(banana=1))

    def test_missing_version(self) -> None:
        raw = json.dumps({"substitutions": []})
        with pytest.raises(HostError, match="missing required field 'version'"):
            parse_manifest(raw)

    def test_unsupported_version(self) -> None:
        with pytest.raises(HostError, match="unsupported version 2"):
            parse_manifest(_manifest_json(version=2))

    def test_substitutions_must_be_nonempty(self) -> None:
        with pytest.raises(HostError, match="substitutions must be a non-empty list"):
            parse_manifest(_manifest_json(substitutions=[]))

    def test_unknown_format(self) -> None:
        raw = _manifest_json(
            substitutions=[{"file": "a", "format": "regex-replace", "value": "{domain}"}]
        )
        with pytest.raises(HostError, match="unknown format"):
            parse_manifest(raw)

    def test_string_replace_rejects_key(self) -> None:
        raw = _manifest_json(
            substitutions=[
                {"file": "a", "format": "string-replace", "match": "x", "key": "y", "value": "z"}
            ]
        )
        with pytest.raises(HostError, match="string-replace does not take 'key'"):
            parse_manifest(raw)

    def test_js_key_rejects_match(self) -> None:
        raw = _manifest_json(
            substitutions=[
                {"file": "a", "format": "js-key", "key": "y", "match": "x", "value": "z"}
            ]
        )
        with pytest.raises(HostError, match="js-key does not take 'match'"):
            parse_manifest(raw)

    def test_string_replace_requires_match(self) -> None:
        raw = _manifest_json(
            substitutions=[{"file": "a", "format": "string-replace", "value": "z"}]
        )
        with pytest.raises(HostError, match="requires a non-empty 'match'"):
            parse_manifest(raw)

    def test_js_key_requires_key(self) -> None:
        raw = _manifest_json(substitutions=[{"file": "a", "format": "js-key", "value": "z"}])
        with pytest.raises(HostError, match="requires a non-empty 'key'"):
            parse_manifest(raw)

    def test_unknown_value_token(self) -> None:
        raw = _manifest_json(
            substitutions=[
                {"file": "a", "format": "string-replace", "match": "x", "value": "{domian}"}
            ]
        )
        with pytest.raises(HostError, match="unknown value token.*domian"):
            parse_manifest(raw)

    def test_unknown_entry_field(self) -> None:
        raw = _manifest_json(
            substitutions=[
                {"file": "a", "format": "string-replace", "match": "x", "value": "y", "z": 1}
            ]
        )
        with pytest.raises(HostError, match="unknown field.*'z'"):
            parse_manifest(raw)

    def test_duplicate_substitution_rejected(self) -> None:
        entry = {"file": "a.js", "format": "js-key", "key": "url", "value": "{domain}"}
        raw = _manifest_json(substitutions=[entry, entry])
        with pytest.raises(HostError, match="duplicate substitution"):
            parse_manifest(raw)

    def test_absolute_path_rejected(self) -> None:
        raw = _manifest_json(
            substitutions=[{"file": "/etc/passwd", "format": "js-key", "key": "k", "value": "v"}]
        )
        with pytest.raises(HostError, match="repo-relative"):
            parse_manifest(raw)

    def test_dotdot_path_rejected(self) -> None:
        raw = _manifest_json(
            substitutions=[{"file": "../secret", "format": "js-key", "key": "k", "value": "v"}]
        )
        with pytest.raises(HostError, match="repo-relative"):
            parse_manifest(raw)


class TestStringReplace:
    """The string-replace handler, against real HTML shapes."""

    def test_replaces_every_occurrence(self) -> None:
        """laptopistan.com's title and .lbl div share one literal."""
        sub = Substitution(
            file="index.html", format="string-replace", match="laptopistan.com", value="{domain}"
        )
        updated = apply_substitutions(LAPTOPISTAN_INDEX_HTML, [sub], "tantamount.rodeo")
        assert updated.count("tantamount.rodeo") == 2
        assert "laptopistan.com" not in updated

    def test_match_not_found_is_loud(self) -> None:
        sub = Substitution(
            file="index.html", format="string-replace", match="absent.example", value="{domain}"
        )
        with pytest.raises(HostError, match="not found"):
            apply_substitutions(MIMEO_LOL_INDEX_HTML, [sub], "foo.com")

    def test_noop_when_already_applied(self) -> None:
        """mimeo.lol deployed to mimeo.lol: match equals replacement."""
        sub = Substitution(
            file="index.html", format="string-replace", match="mimeo.lol", value="{domain}"
        )
        assert apply_substitutions(MIMEO_LOL_INDEX_HTML, [sub], "mimeo.lol") == (
            MIMEO_LOL_INDEX_HTML
        )

    def test_value_keeps_surrounding_paths(self) -> None:
        """A URL-valued entry replaces the host while paths survive via the template."""
        sub = Substitution(
            file="index.html",
            format="string-replace",
            match="example.com",
            value="{domain}",
        )
        content = '<a href="https://example.com/about/">about</a>'
        updated = apply_substitutions(content, [sub], "foo.com")
        assert updated == '<a href="https://foo.com/about/">about</a>'


class TestJsKey:
    """The loosey-goosey js-key handler, against real JS shapes."""

    def test_tech_blog_url_keys(self) -> None:
        """url, author.url, and feed.id all resolve; email and comments untouched."""
        subs = [
            Substitution(
                file="content/_data/metadata.js",
                format="js-key",
                key="url",
                value="https://{domain}/",
            ),
            Substitution(
                file="content/_data/metadata.js",
                format="js-key",
                key="author.url",
                value="https://{domain}/about/",
            ),
            Substitution(
                file="content/_data/metadata.js",
                format="js-key",
                key="feed.id",
                value="https://{domain}/",
            ),
        ]
        updated = apply_substitutions(TECH_BLOG_METADATA_JS, subs, "tantamount.rodeo")
        assert 'url: "https://tantamount.rodeo/"' in updated
        assert 'url: "https://tantamount.rodeo/about/"' in updated
        assert 'id: "https://tantamount.rodeo/"' in updated
        # The placeholder email on a neighboring line is never touched.
        assert 'email: "author@example.com"' in updated
        # Comments and structure survive byte-for-byte outside the edits.
        assert "// Site metadata" in updated
        assert 'title: "Tech Blog"' in updated
        assert 'environment: process.env.ELEVENTY_ENV || "development"' in updated

    def test_set_by_key_ignores_current_value(self) -> None:
        """folio/chapbook-style real-domain placeholders are overwritten."""
        content = 'export default {\n\turl: "https://orobia.net/",\n}\n'
        sub = Substitution(file="m.js", format="js-key", key="url", value="https://{domain}/")
        updated = apply_substitutions(content, [sub], "tantamount.rodeo")
        assert updated == 'export default {\n\turl: "https://tantamount.rodeo/",\n}\n'

    def test_pamphlet_config_addplugin_options(self) -> None:
        """Paths descend through unkeyed braces (function bodies, call arguments)."""
        sub = Substitution(
            file="eleventy.config.js", format="js-key", key="metadata.base", value="https://{domain}/"
        )
        updated = apply_substitutions(PAMPHLET_CONFIG_JS, [sub], "tantamount.rodeo")
        assert 'base: "https://tantamount.rodeo/"' in updated
        assert 'outputPath: "/feed/feed.xml"' in updated  # untouched

    def test_one_line_nested_object(self) -> None:
        """social: { github: "", bluesky: "" } resolves on a single line."""
        sub = Substitution(file="m.js", format="js-key", key="author.social.github", value="{domain}")
        updated = apply_substitutions(TECH_BLOG_METADATA_JS, [sub], "g.h")
        assert 'social: { github: "g.h", bluesky: "" }' in updated

    def test_single_quoted_values(self) -> None:
        content = "export default {\n\turl: 'https://example.com/',\n}\n"
        sub = Substitution(file="m.js", format="js-key", key="url", value="https://{domain}/")
        updated = apply_substitutions(content, [sub], "foo.com")
        assert updated == "export default {\n\turl: 'https://foo.com/',\n}\n"

    def test_rendered_quote_char_is_escaped(self) -> None:
        content = 'export default {\n\turl: "https://example.com/",\n}\n'
        sub = Substitution(file="m.js", format="js-key", key="url", value='{domain}"')
        updated = apply_substitutions(content, [sub], 'x"y')
        assert 'url: "x\\"y\\""' in updated

    def test_non_string_leaf_is_not_resolvable(self) -> None:
        """limit: 10 exists at feed.limit but is not a string literal."""
        sub = Substitution(file="m.js", format="js-key", key="feed.limit", value="{domain}")
        with pytest.raises(HostError, match="not found"):
            apply_substitutions(TECH_BLOG_METADATA_JS, [sub], "foo.com")

    def test_ambiguous_path_is_loud(self) -> None:
        """Two url leaves under different unkeyed braces share the path 'url'."""
        content = (
            "export default {\n"
            '\turl: "https://a.example/",\n'
            "\tsetup: () => {\n"
            '\t\turl: "https://b.example/",\n'
            "\t},\n"
            "}\n"
        )
        sub = Substitution(file="m.js", format="js-key", key="url", value="{domain}")
        with pytest.raises(HostError, match="ambiguous"):
            apply_substitutions(content, [sub], "foo.com")

    def test_not_found_lists_available_keys(self) -> None:
        sub = Substitution(file="m.js", format="js-key", key="nonexistent", value="{domain}")
        with pytest.raises(HostError, match="available keys.*url"):
            apply_substitutions(TECH_BLOG_METADATA_JS, [sub], "foo.com")

    def test_noop_when_already_set(self) -> None:
        content = 'export default {\n\turl: "https://foo.com/",\n}\n'
        sub = Substitution(file="m.js", format="js-key", key="url", value="https://{domain}/")
        assert apply_substitutions(content, [sub], "foo.com") == content

    def test_unbalanced_braces_is_a_parse_error(self) -> None:
        with pytest.raises(HostError, match="unbalanced"):
            apply_substitutions(
                'export default {\n\turl: "x",\n', [_js_key_sub()], "foo.com"
            )

    def test_unterminated_string_is_a_parse_error(self) -> None:
        with pytest.raises(HostError, match="unterminated"):
            apply_substitutions(
                'export default {\n\turl: "x,\n}\n', [_js_key_sub()], "foo.com"
            )

    def test_string_containing_braces_and_comment_marker(self) -> None:
        """https:// inside a string must not read as a // comment; braces in
        strings must not count toward nesting."""
        content = (
            "export default {\n"
            '\tdescription: "see https://example.com/{path} for // details",\n'
            '\turl: "https://example.com/",\n'
            "}\n"
        )
        sub = Substitution(file="m.js", format="js-key", key="url", value="https://{domain}/")
        updated = apply_substitutions(content, [sub], "foo.com")
        assert 'description: "see https://example.com/{path} for // details"' in updated
        assert 'url: "https://foo.com/"' in updated


def _js_key_sub() -> Substitution:
    return Substitution(file="m.js", format="js-key", key="url", value="https://{domain}/")


class TestYamlFrontmatterKey:
    """The yaml-frontmatter-key handler, against pandoc-simple's shape."""

    def test_sets_title(self) -> None:
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="title", value="{domain}")
        updated = apply_substitutions(PANDOC_SIMPLE_INDEX_MD, [sub], "tantamount.rodeo")
        assert 'title: "tantamount.rodeo"' in updated
        assert 'title: "Document Title"' not in updated
        # Body and other frontmatter keys survive.
        assert 'subtitle: "Subtitle or tagline"' in updated
        assert "A short opening passage" in updated

    def test_unquoted_old_value(self) -> None:
        content = "---\ntitle: Some Old Title\n---\nbody\n"
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="title", value="{domain}")
        updated = apply_substitutions(content, [sub], "foo.com")
        assert updated == "---\ntitle: \"foo.com\"\n---\nbody\n"

    def test_nested_key_of_same_name_not_matched(self) -> None:
        """Only top-level frontmatter keys are addressable."""
        content = "---\nauthor:\n  title: Nested\n---\nbody\n"
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="title", value="{domain}")
        with pytest.raises(HostError, match="not found"):
            apply_substitutions(content, [sub], "foo.com")

    def test_missing_frontmatter_is_loud(self) -> None:
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="title", value="{domain}")
        with pytest.raises(HostError, match="frontmatter"):
            apply_substitutions("no frontmatter here\n", [sub], "foo.com")

    def test_unterminated_frontmatter_is_loud(self) -> None:
        content = "---\ntitle: x\nbody without closing marker\n"
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="title", value="{domain}")
        with pytest.raises(HostError, match="not terminated"):
            apply_substitutions(content, [sub], "foo.com")

    def test_missing_key_is_loud(self) -> None:
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="missing", value="{domain}")
        with pytest.raises(HostError, match="'missing' not found"):
            apply_substitutions(PANDOC_SIMPLE_INDEX_MD, [sub], "foo.com")

    def test_noop_when_already_set(self) -> None:
        content = '---\ntitle: "foo.com"\n---\nbody\n'
        sub = Substitution(file="index.md", format="yaml-frontmatter-key", key="title", value="{domain}")
        assert apply_substitutions(content, [sub], "foo.com") == content
