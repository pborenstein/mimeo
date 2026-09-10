"""Per-template substitution manifest: parsing, validation, and handlers.

DEC-024. A template repo may ship ``mimeo.template.json`` at its root
declaring where the template's own self-reference lives (its name or URL in
HTML titles, JS data objects, YAML frontmatter) and what the deployed site's
value should be. ``GitHubHost`` fetches the manifest from the template repo,
strips dev-only paths, then applies each substitution to the generated repo.

All failures are loud: an invalid manifest, an unresolvable key, or a missing
match raises ``HostError`` instead of silently skipping -- a declared
manifest that quietly no-ops is the misleading-outcome class this design
exists to prevent.

The ``js-key`` handler is deliberately pragmatic ("loosey goosey", per the
DEC-024 addendum): it resolves a dotted path against object literals
wherever they appear in the file -- ``export default {``, ``return {``,
function bodies, and call arguments are all path-transparent -- and requires
the path to resolve to exactly one string literal. Multi-line strings and
block comments are not supported and fail with a parse error rather than
guessing.
"""

import json
import re
from dataclasses import dataclass

from mimeo.exceptions import HostError

MANIFEST_FILENAME = "mimeo.template.json"
MANIFEST_VERSION = 1

# Stripped from every generated repo whose template ships no manifest (or
# whose manifest declares no dev_paths): authoring notes and contribution
# docs are template-development material, never site content. A manifest's
# dev_paths replaces this list wholesale when present. A trailing "/"
# strips a whole directory, matching the pre-manifest TEMPLATE_DEV_PATHS
# convention.
DEFAULT_DEV_PATHS = ["README.md", "docs/", "CLAUDE.md"]

FORMAT_STRING_REPLACE = "string-replace"
FORMAT_JS_KEY = "js-key"
FORMAT_YAML_FRONTMATTER_KEY = "yaml-frontmatter-key"
_FORMATS = (FORMAT_STRING_REPLACE, FORMAT_JS_KEY, FORMAT_YAML_FRONTMATTER_KEY)

_TOKEN_RE = re.compile(r"\{([^{}]*)\}")
_TOP_LEVEL_KEYS = {"version", "dev_paths", "substitutions"}
_ENTRY_KEYS = {"file", "format", "value", "key", "match"}


@dataclass
class Substitution:
    """One substitution entry: set ``file``'s ``key``/``match`` to ``value``."""

    file: str
    format: str
    value: str
    key: str | None = None
    match: str | None = None


@dataclass
class TemplateManifest:
    """A parsed, validated template manifest."""

    dev_paths: list[str]
    substitutions: list[Substitution]


def render_value(value: str, domain: str) -> str:
    """Substitute the ``{domain}`` token in a manifest value.

    Args:
        value: Manifest value template, containing at most ``{domain}`` tokens
        domain: The deployed site's domain

    Returns:
        The value with every ``{domain}`` token replaced
    """
    return value.replace("{domain}", domain)


def parse_manifest(raw: str) -> TemplateManifest:
    """Parse and validate a ``mimeo.template.json`` document.

    Validation is strict: unknown fields, unknown formats, a field that does
    not belong to the declared format, unknown ``{...}`` tokens in values,
    and duplicate entries are all errors. Strictness is what makes a typo
    fail loudly at deploy time instead of silently no-oping.

    Args:
        raw: The manifest file's full text

    Returns:
        The parsed manifest

    Raises:
        HostError: If the document is not valid JSON or violates the schema
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HostError(f"{MANIFEST_FILENAME} is not valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise HostError(
            f"{MANIFEST_FILENAME} must be a JSON object, got {type(data).__name__}"
        )

    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise HostError(
            f"{MANIFEST_FILENAME}: unknown field(s) {sorted(unknown)}; "
            f"expected {sorted(_TOP_LEVEL_KEYS)}"
        )

    if "version" not in data:
        raise HostError(f"{MANIFEST_FILENAME}: missing required field 'version'")
    version = data["version"]
    if version != MANIFEST_VERSION:
        raise HostError(
            f"{MANIFEST_FILENAME}: unsupported version {version!r}; "
            f"this mimeo supports version {MANIFEST_VERSION}"
        )

    dev_paths = list(DEFAULT_DEV_PATHS)
    if "dev_paths" in data:
        raw_paths = data["dev_paths"]
        if not isinstance(raw_paths, list) or not all(
            isinstance(p, str) for p in raw_paths
        ):
            raise HostError(f"{MANIFEST_FILENAME}: dev_paths must be a list of strings")
        for path in raw_paths:
            _check_path(path, f"{MANIFEST_FILENAME}: dev_paths entry")
        dev_paths = raw_paths

    raw_subs = data.get("substitutions")
    if not isinstance(raw_subs, list) or not raw_subs:
        raise HostError(f"{MANIFEST_FILENAME}: substitutions must be a non-empty list")

    subs = [_parse_entry(i, entry) for i, entry in enumerate(raw_subs)]

    seen: set[tuple[str, str, str]] = set()
    for sub in subs:
        ident = (sub.file, sub.format, sub.key or sub.match or "")
        if ident in seen:
            raise HostError(
                f"{MANIFEST_FILENAME}: duplicate substitution for "
                f"{sub.format} {sub.key or sub.match!r} in {sub.file}"
            )
        seen.add(ident)

    return TemplateManifest(dev_paths=dev_paths, substitutions=subs)


def apply_substitutions(content: str, subs: list[Substitution], domain: str) -> str:
    """Apply one file's substitution entries, in declared order.

    Args:
        content: The file's current text
        subs: The manifest entries that target this file
        domain: The deployed site's domain

    Returns:
        The file's new text (identical to ``content`` when nothing changed)

    Raises:
        HostError: If any entry cannot be applied to the content
    """
    for sub in subs:
        if sub.format == FORMAT_STRING_REPLACE:
            content = _apply_string_replace(content, sub, domain)
        elif sub.format == FORMAT_JS_KEY:
            content = _apply_js_key(content, sub, domain)
        elif sub.format == FORMAT_YAML_FRONTMATTER_KEY:
            content = _apply_yaml_frontmatter_key(content, sub, domain)
        else:
            raise HostError(f"{sub.file}: unknown format {sub.format!r}")
    return content


def _parse_entry(index: int, entry: object) -> Substitution:
    """Validate one substitutions[] entry.

    Raises:
        HostError: If the entry violates the schema
    """
    ctx = f"{MANIFEST_FILENAME}: substitutions[{index}]"
    if not isinstance(entry, dict):
        raise HostError(f"{ctx} must be an object")

    unknown = set(entry) - _ENTRY_KEYS
    if unknown:
        raise HostError(f"{ctx}: unknown field(s) {sorted(unknown)}")

    for required in ("file", "format", "value"):
        if required not in entry:
            raise HostError(f"{ctx}: missing required field '{required}'")

    file = entry["file"]
    fmt = entry["format"]
    value = entry["value"]
    _check_path(file, f"{ctx}: file")

    if fmt not in _FORMATS:
        raise HostError(f"{ctx}: unknown format {fmt!r}; expected one of {list(_FORMATS)}")

    if not isinstance(value, str) or not value:
        raise HostError(f"{ctx}: value must be a non-empty string")

    bad_tokens = sorted({m for m in _TOKEN_RE.findall(value) if m != "domain"})
    if bad_tokens:
        raise HostError(
            f"{ctx}: unknown value token(s) {bad_tokens}; only '{{domain}}' is supported"
        )

    key = entry.get("key")
    match = entry.get("match")
    if fmt == FORMAT_STRING_REPLACE:
        if "key" in entry:
            raise HostError(f"{ctx}: string-replace does not take 'key'")
        if not isinstance(match, str) or not match:
            raise HostError(f"{ctx}: string-replace requires a non-empty 'match'")
    else:
        if "match" in entry:
            raise HostError(f"{ctx}: {fmt} does not take 'match'")
        if not isinstance(key, str) or not key:
            raise HostError(f"{ctx}: {fmt} requires a non-empty 'key'")

    return Substitution(file=file, format=fmt, value=value, key=key, match=match)


def _check_path(path: object, ctx: str) -> None:
    """Reject paths that are not plain repo-relative file paths.

    Raises:
        HostError: If the path is empty, absolute, or escapes the repo root
    """
    if not isinstance(path, str) or not path:
        raise HostError(f"{ctx} must be a non-empty string")
    if path.startswith("/") or ".." in path.split("/") or "\\" in path:
        raise HostError(f"{ctx} must be a repo-relative path, got {path!r}")


def _apply_string_replace(content: str, sub: Substitution, domain: str) -> str:
    """Replace every literal occurrence of ``match`` with the rendered value.

    Raises:
        HostError: If ``match`` does not occur in the content
    """
    if sub.match is None:
        raise HostError(f"{sub.file}: string-replace entry is missing 'match'")
    rendered = render_value(sub.value, domain)
    if sub.match not in content:
        raise HostError(
            f"{sub.file}: string-replace match {sub.match!r} not found in file"
        )
    return content.replace(sub.match, rendered)


@dataclass
class _Leaf:
    """A string-literal leaf found while scanning a JS file."""

    path: str
    start: int  # index of the opening quote in the whole file
    end: int  # index just past the closing quote in the whole file
    quote: str


def _apply_js_key(content: str, sub: Substitution, domain: str) -> str:
    """Set the string value at a dotted key path, wherever it is declared.

    The path is resolved against object literals anywhere in the file:
    unkeyed braces (``export default {``, ``return {``, function bodies,
    call arguments) are path-transparent; keyed openers (``author: {``)
    extend the path. The path must resolve to exactly one string literal.

    Raises:
        HostError: If the path is missing, ambiguous, or the file won't parse
    """
    if sub.key is None:
        raise HostError(f"{sub.file}: js-key entry is missing 'key'")
    leaves = _parse_js_leaves(content, sub.file)
    matches = [leaf for leaf in leaves if leaf.path == sub.key]
    if not matches:
        available = sorted({leaf.path for leaf in leaves})
        hint = f"; available keys: {available[:8]}" if available else ""
        raise HostError(f"{sub.file}: js-key {sub.key!r} not found{hint}")
    if len(matches) > 1:
        raise HostError(
            f"{sub.file}: js-key {sub.key!r} is ambiguous "
            f"({len(matches)} string leaves share this path)"
        )
    leaf = matches[0]
    rendered = render_value(sub.value, domain).replace(leaf.quote, "\\" + leaf.quote)
    return content[: leaf.start] + leaf.quote + rendered + leaf.quote + content[leaf.end :]


def _parse_js_leaves(content: str, filename: str) -> list[_Leaf]:
    """Scan JS source for string-literal leaves with their dotted paths.

    Line-oriented and comment/string aware: ``//`` comments are ignored,
    braces inside quoted strings don't count toward nesting, and backslash
    escapes inside strings are honored. Unterminated strings and unbalanced
    braces are parse errors -- the parser refuses to guess.

    Raises:
        HostError: On unterminated strings or unbalanced braces
    """
    leaves: list[_Leaf] = []
    stack: list[str | None] = []
    offset = 0
    for lineno, line in enumerate(content.split("\n"), start=1):
        spans, comment_start = _analyze_line(line, filename, lineno)
        masked = _mask_line(line, spans, comment_start)

        keyed_positions = {m.end() - 1 for m in _JS_KEYED_OPEN_RE.finditer(masked)}
        events: list[tuple[int, str, object]] = []
        for m in _JS_KEYED_OPEN_RE.finditer(masked):
            events.append((m.end() - 1, "open", m.group(1)))
        for i, ch in enumerate(masked):
            if ch == "{":
                if i not in keyed_positions:
                    events.append((i, "open", None))
            elif ch == "}":
                events.append((i, "close", None))
        for start, end, quote in spans:
            events.append((start, "leaf", (end, quote)))
        events.sort(key=lambda event: event[0])

        for pos, kind, payload in events:
            if kind == "open":
                stack.append(payload if isinstance(payload, str) else None)
            elif kind == "close":
                if not stack:
                    raise HostError(f"{filename}:{lineno}: unbalanced braces")
                stack.pop()
            else:
                if not isinstance(payload, tuple):
                    continue
                end, quote = payload
                before = masked[:pos]
                key_match = _JS_KEY_BEFORE_RE.search(before)
                if key_match:
                    prefix = ".".join(seg for seg in stack if seg)
                    path = f"{prefix}.{key_match.group(1)}" if prefix else key_match.group(1)
                    leaves.append(
                        _Leaf(path=path, start=offset + pos, end=offset + end, quote=quote)
                    )
        offset += len(line) + 1

    if stack:
        raise HostError(f"{filename}: unbalanced braces ({len(stack)} unclosed)")
    return leaves


_JS_KEYED_OPEN_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*:\s*\{")
_JS_KEY_BEFORE_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*:\s*$")


def _analyze_line(
    line: str, filename: str, lineno: int
) -> tuple[list[tuple[int, int, str]], int | None]:
    """Find a line's quoted-string spans and its ``//`` comment start, if any.

    Returns:
        (spans, comment_start) where each span is (start, end, quote char)
        covering the full quoted literal including both quotes

    Raises:
        HostError: On an unterminated string literal
    """
    spans: list[tuple[int, int, str]] = []
    comment_start: int | None = None
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == quote:
                    break
                j += 1
            if j >= n:
                raise HostError(
                    f"{filename}:{lineno}: unterminated string literal "
                    "(multi-line strings are not supported)"
                )
            spans.append((i, j + 1, quote))
            i = j + 1
        elif ch == "/" and i + 1 < n and line[i + 1] == "/":
            comment_start = i
            break
        else:
            i += 1
    return spans, comment_start


def _mask_line(
    line: str,
    spans: list[tuple[int, int, str]],
    comment_start: int | None,
) -> str:
    """Blank out string interiors and comment tails so structure scans see only code."""
    chars = list(line)
    for start, end, _quote in spans:
        for k in range(start + 1, end - 1):
            chars[k] = " "
    if comment_start is not None:
        for k in range(comment_start, len(line)):
            chars[k] = " "
    return "".join(chars)


def _apply_yaml_frontmatter_key(content: str, sub: Substitution, domain: str) -> str:
    """Set a top-level key in a Markdown file's YAML frontmatter block.

    The new value is written double-quoted regardless of the old value's
    style. Only top-level keys are addressable; nested keys under an
    indented parent are not matched.

    Raises:
        HostError: If there is no frontmatter block or the key is absent
    """
    if sub.key is None:
        raise HostError(f"{sub.file}: yaml-frontmatter-key entry is missing 'key'")
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        raise HostError(
            f"{sub.file}: expected YAML frontmatter (file must start with '---')"
        )
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise HostError(
            f"{sub.file}: YAML frontmatter not terminated (missing closing '---')"
        ) from None
    pattern = re.compile(rf"^{re.escape(sub.key)}\s*:")
    for i in range(1, end):
        if pattern.match(lines[i]):
            rendered = render_value(sub.value, domain)
            lines[i] = f'{sub.key}: "{rendered}"'
            return "\n".join(lines)
    raise HostError(f"{sub.file}: frontmatter key {sub.key!r} not found")
