"""Shared concurrent domain processing and output helpers."""

import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Sequence, TypeVar

import click

from ..exceptions import (
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_GENERAL,
    EXIT_PARTIAL,
    EXIT_RATE_LIMIT,
    EXIT_TRANSIENT,
    APIError,
    ConfigurationError,
    HostError,
    NetworkError,
    RegistrarError,
)

# Set by main() group before subcommands run
_log_format: str = "text"


def set_log_format(fmt: str) -> None:
    """Set the global log format."""
    global _log_format
    _log_format = fmt.lower()


def get_log_format() -> str:
    """Get the current log format."""
    return _log_format


_DOMAIN_PATTERN = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def validate_domains(domains: tuple[str, ...]) -> None:
    """Validate domain name format for all given domains.

    Args:
        domains: Tuple of domain names to validate

    Raises:
        SystemExit: If any domain name is invalid
    """
    invalid = []
    for d in domains:
        if not _DOMAIN_PATTERN.match(d.lower()):
            invalid.append(d)
    if invalid:
        for d in invalid:
            click.secho(f"Invalid domain name: {d}", fg="red", err=True)
        click.echo(
            "Domain names must consist of letters, digits, hyphens, and dots, with a valid TLD.",
            err=True,
        )
        sys.exit(EXIT_CONFIG)


def _emit(level: str, message: str, domain: str | None = None) -> None:
    """Emit a structured log line to stderr (JSON mode) or do nothing (text mode).

    In text mode callers use click.echo/secho directly. This is for JSON mode only.
    """
    if _log_format != "json":
        return
    record: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level,
        "message": message,
    }
    if domain is not None:
        record["domain"] = domain
    click.echo(json.dumps(record), err=True)


_AUTH_KEYWORDS = (
    "unauthorized",
    "authentication",
    "forbidden",
    "invalid api key",
    "bad credentials",
)
_RATE_LIMIT_KEYWORDS = ("rate limit", "429")
_TRANSIENT_KEYWORDS = ("502", "503", "500", "timeout", "connection")


def _categorize_error(exc: BaseException) -> tuple[int, str]:
    """Return (exit_code, category_label) for an exception.

    Args:
        exc: The exception to categorize

    Returns:
        Tuple of exit code and short category label for display
    """
    if isinstance(exc, ConfigurationError):
        return EXIT_CONFIG, "config"

    msg = str(exc).lower()

    if isinstance(exc, APIError):
        if exc.status_code == 429 or any(k in msg for k in _RATE_LIMIT_KEYWORDS):
            return EXIT_RATE_LIMIT, "rate-limit"
        if exc.status_code in (500, 502, 503, 504):
            return EXIT_TRANSIENT, "transient"
        if any(k in msg for k in _AUTH_KEYWORDS):
            return EXIT_AUTH, "auth"

    if isinstance(exc, NetworkError):
        return EXIT_TRANSIENT, "transient"

    if isinstance(exc, (HostError, RegistrarError)):
        if any(k in msg for k in _AUTH_KEYWORDS):
            return EXIT_AUTH, "auth"
        if any(k in msg for k in _RATE_LIMIT_KEYWORDS):
            return EXIT_RATE_LIMIT, "rate-limit"
        if any(k in msg for k in _TRANSIENT_KEYWORDS):
            return EXIT_TRANSIENT, "transient"

    return EXIT_TRANSIENT, "provider"


def load_config(config_path: Any) -> Any:
    """Load configuration, exiting on error.

    Args:
        config_path: Path to config file or None

    Returns:
        Config object
    """
    from ..config import Config

    try:
        return Config.load(config_path)
    except ConfigurationError as e:
        click.secho(f"[config] {e}", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    except Exception as e:
        click.secho(f"[config] {e}", fg="red", err=True)
        sys.exit(EXIT_GENERAL)


_CATEGORY_TO_CODE = {
    "config": EXIT_CONFIG,
    "auth": EXIT_AUTH,
    "rate-limit": EXIT_RATE_LIMIT,
    "transient": EXIT_TRANSIENT,
    "provider": EXIT_TRANSIENT,
    "partial": EXIT_PARTIAL,
}


T = TypeVar("T")


def map_items(
    items: Sequence[T],
    fn: Callable[[T], Dict[str, Any]],
    *,
    workers: int = 5,
    sequential: bool = False,
    on_error: Callable[[T, BaseException], Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Run fn over items and return one result dict per item, in input order.

    An exception escaping fn becomes an error row (via on_error) instead of
    aborting the run, so one failure cannot discard the other results.

    Args:
        items: Items to process (domains, repo dicts, ...)
        fn: Function producing a result dict for one item
        workers: Maximum concurrent workers
        sequential: Force sequential processing
        on_error: Build the error row for an item whose fn call raised.
                  Default: {"error": str(exc), "error_category": category}

    Returns:
        List of result dicts, one per item, in the order items were given
    """

    def _error_row(item: T, exc: BaseException) -> Dict[str, Any]:
        if on_error is not None:
            return on_error(item, exc)
        _, category = _categorize_error(exc)
        return {"error": str(exc), "error_category": category}

    def _guarded(item: T) -> Dict[str, Any]:
        try:
            return fn(item)
        except Exception as exc:
            return _error_row(item, exc)

    if sequential or len(items) <= 1:
        return [_guarded(item) for item in items]

    results: Dict[int, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(len(items), workers)) as executor:
        futures = {executor.submit(_guarded, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [results[i] for i in range(len(items))]


def render_results(
    results: List[Dict[str, Any]],
    output_format: str,
    *,
    csv_fields: List[str],
    csv_rows: Callable[[Dict[str, Any]], Iterable[Dict[str, Any]]] | None = None,
    text: Callable[[List[Dict[str, Any]]], None],
) -> None:
    """Render results in the requested output format.

    Args:
        results: Result dicts from map_items (or built by the command)
        output_format: "text", "json", or "csv"
        csv_fields: CSV column names
        csv_rows: Expand one result into CSV rows (flattening lists,
                  emitting one row per sub-record). Default: the result
                  itself as a single row; extra keys are ignored.
        text: Command-specific text renderer
    """
    if output_format == "json":
        click.echo(json.dumps(results, indent=2))
    elif output_format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            for row in csv_rows(result) if csv_rows is not None else [result]:
                writer.writerow(row)
    else:
        text(results)


def exit_on_errors(results: List[Dict[str, Any]]) -> None:
    """Report error-carrying rows to stderr and exit by failure taxonomy.

    For commands whose result rows use an "error" field (map_items style)
    rather than a "success" flag. No-op when every row is clean. Exits
    EXIT_PARTIAL when some rows succeeded, or by the failed rows' error
    category when every row failed.
    """
    failed = [r for r in results if r.get("error")]
    if not failed:
        return
    for r in failed:
        label = r.get("domain") or r.get("name") or "?"
        category = r.get("error_category") or "provider"
        click.secho(f"[{category}] {label}: {r['error']}", fg="red", err=True)
    if len(failed) < len(results):
        click.secho(
            f"warning: {len(failed)}/{len(results)} items failed; results are partial",
            fg="yellow",
            err=True,
        )
        sys.exit(EXIT_PARTIAL)
    codes = [
        _CATEGORY_TO_CODE.get(r.get("error_category") or "transient", EXIT_TRANSIENT)
        for r in failed
    ]
    sys.exit(min(codes))
