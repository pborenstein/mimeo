"""Shared concurrent domain processing and output helpers."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List

import click

from ..exceptions import (
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_PARTIAL,
    EXIT_RATE_LIMIT,
    EXIT_TRANSIENT,
    APIError,
    ConfigurationError,
    HostError,
    NetworkError,
    RegistrarError,
)

# Lock for thread-safe console output
_console_lock = Lock()

# Set by main() group before subcommands run
_log_format: str = "text"


def set_log_format(fmt: str) -> None:
    """Set the global log format."""
    global _log_format
    _log_format = fmt.lower()


def get_log_format() -> str:
    """Get the current log format."""
    return _log_format


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


_AUTH_KEYWORDS = ("unauthorized", "authentication", "forbidden", "invalid api key", "bad credentials")
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
        click.echo("Loading configuration...")
        return Config.load(config_path)
    except ConfigurationError as e:
        click.secho(f"[config] {e}", fg="red", err=True)
        sys.exit(EXIT_CONFIG)


def process_domains_concurrent(
    domains: tuple[str, ...],
    process_fn: Callable[[str], dict],
    workers: int,
    sequential: bool,
    stop_on_error: bool,
    dry_run: bool = False,
) -> list[dict]:
    """Process multiple domains either sequentially or concurrently.

    Args:
        domains: Tuple of domain names
        process_fn: Function that takes a domain and returns a result dict
                   with at least 'domain', 'success', 'error' keys
        workers: Max concurrent workers
        sequential: Force sequential processing
        stop_on_error: Stop on first error
        dry_run: Whether this is a dry run (forces sequential)

    Returns:
        List of result dicts in original domain order
    """
    results: List[dict] = []

    if dry_run or sequential or len(domains) == 1:
        for idx, domain in enumerate(domains, 1):
            if len(domains) > 1 and _log_format == "text":
                click.echo()
                click.secho(f"[{idx}/{len(domains)}] Processing {domain}", fg="cyan", bold=True)
                click.secho("=" * 60, fg="cyan")

            result = process_fn(domain)
            results.append(result)

            if stop_on_error and not result["success"]:
                if _log_format == "text":
                    click.echo()
                    click.secho(f"Stopping due to error with {domain}", fg="red")
                else:
                    _emit("error", f"Stopping due to error with {domain}")
                break
    else:
        if _log_format == "text":
            click.echo()

        with ThreadPoolExecutor(max_workers=min(len(domains), workers)) as executor:
            future_to_domain = {}
            for domain in domains:
                future = executor.submit(process_fn, domain)
                future_to_domain[future] = domain
                if _log_format == "text":
                    click.secho(f"-> {domain} started", fg="cyan")
                else:
                    _emit("info", f"{domain} started", domain=domain)

            if _log_format == "text":
                click.echo()

            for future in as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    result = future.result()
                    results.append(result)

                    if _log_format == "text":
                        if result["success"]:
                            click.secho(f"ok {domain} completed", fg="green")
                        else:
                            click.secho(f"xx {domain} failed: {result.get('error', 'Unknown error')}", fg="red")
                    else:
                        level = "info" if result["success"] else "error"
                        msg = f"{domain} completed" if result["success"] else f"{domain} failed: {result.get('error', 'Unknown error')}"
                        _emit(level, msg, domain=domain)

                except Exception as e:
                    if _log_format == "text":
                        click.secho(f"xx {domain} failed unexpectedly: {e}", fg="red")
                    else:
                        _emit("error", f"{domain} failed unexpectedly: {e}", domain=domain)
                    results.append({
                        "domain": domain,
                        "success": False,
                        "error": str(e),
                    })

        domain_order = {domain: idx for idx, domain in enumerate(domains)}
        results.sort(key=lambda r: domain_order.get(r["domain"], 999))

    return results


def exit_on_failures(results: list[dict]) -> None:
    """Exit with appropriate code if any results failed."""
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    if success_count < total_count:
        _category_to_code = {
            "config": EXIT_CONFIG,
            "auth": EXIT_AUTH,
            "rate-limit": EXIT_RATE_LIMIT,
            "transient": EXIT_TRANSIENT,
            "provider": EXIT_TRANSIENT,
            "partial": EXIT_PARTIAL,
        }
        failed = [r for r in results if not r["success"]]
        codes = [_category_to_code.get(r.get("error_category") or "transient", EXIT_TRANSIENT) for r in failed]
        sys.exit(min(codes))
