"""Registrar commands for managing domain registrar settings."""

import sys
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

import click

from ..exceptions import EXIT_CONFIG, ConfigurationError
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar
from ._processing import (
    _categorize_error,
    _emit,
    exit_on_errors,
    map_items,
    render_results,
)


@click.group()
def registrar() -> None:
    """Manage domain registrar settings."""
    pass


@registrar.command(name="list")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "csv"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format",
)
@click.option("--with-dns", is_flag=True, help="Fetch DNS records for each domain")
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
def registrar_list(config: Path | None, output_format: str, with_dns: bool, workers: int) -> None:
    """List all domains in the Porkbun account.

    \b
    Basic usage:
        mimeo registrar list
        mimeo registrar list --format json
        mimeo registrar list --format csv

    \b
    Pipeline examples:
        mimeo registrar list --format json | jq '.[].domain'
        mimeo registrar list --format csv --with-dns > domains.csv
    """
    from ..config import Config

    try:
        cfg = Config.load(config)
    except ConfigurationError as e:
        click.secho(f"[config] {e}", fg="red", err=True)
        sys.exit(EXIT_CONFIG)

    csv_fields = ["domain", "tld", "expires", "auto_renew", "ns_ok", "nameservers"]
    if with_dns:
        csv_fields.append("dns_records")
    csv_fields.append("error")

    def _csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
        flat = dict(row)
        flat["nameservers"] = "|".join(row.get("nameservers") or [])
        if with_dns:
            dns_parts = [
                f"{r.get('type','')}:{r.get('name','')}={r.get('content','')}"
                for r in row.get("dns_records") or []
            ]
            flat["dns_records"] = "|".join(dns_parts)
        return [flat]

    def _text(ordered: List[Dict[str, Any]]) -> None:
        if not ordered:
            click.echo("No domains found in Porkbun account.")
            return

        domain_w = max(len(r["domain"]) for r in ordered)
        expires_w = max(len(r["expires"]) for r in ordered)
        ns_w = 60

        click.echo()
        header = f"  {'DOMAIN':<{domain_w}}  {'EXPIRES':<{expires_w}}  {'NS_OK':<5}  {'NAMESERVERS':<{ns_w}}"
        click.secho(header, bold=True)
        click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

        for row in ordered:
            line = f"  {row['domain']:<{domain_w}}  {row['expires']:<{expires_w}}  "
            if row.get("error"):
                click.echo(line, nl=False)
                click.secho(f"{'error':<5}", fg="red", nl=False)
                click.secho(f"  {row['error']}", fg="red")
                continue
            ns_ok = row["ns_ok"]
            ns_label = "yes" if ns_ok else "no"
            ns_color = "green" if ns_ok else "red"
            ns_str = ", ".join(row.get("nameservers") or [])
            if len(ns_str) > ns_w:
                ns_str = ns_str[:ns_w - 3] + "..."
            click.echo(line, nl=False)
            click.secho(f"{ns_label:<5}", fg=ns_color, nl=False)
            click.echo(f"  {ns_str}")

        click.echo()

    try:
        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as reg:
            raw_domains = reg.list_domains()

        if not raw_domains:
            render_results([], output_format, csv_fields=csv_fields, text=_text)
            return

        total = len(raw_domains)
        console_lock = Lock()

        def _base_row(domain_info: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "domain": domain_info.get("domain", ""),
                "tld": domain_info.get("tld", ""),
                "expires": domain_info.get("expireDate", ""),
                "auto_renew": domain_info.get("autoRenew") in ("1", 1, True),
                "nameservers": [],
                "ns_ok": False,
                "dns_records": [],
                "error": None,
            }

        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as reg2, \
                PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_prov:
            progress = {"done": 0}

            def _enrich(domain_info: Dict[str, Any]) -> Dict[str, Any]:
                result = _base_row(domain_info)
                domain_name = result["domain"]

                try:
                    ns_result = reg2.check_nameservers(domain_name)
                    result["nameservers"] = ns_result.actual
                    result["ns_ok"] = ns_result.ok

                    if with_dns:
                        result["dns_records"] = dns_prov.get_domain_records(domain_name)
                except Exception as exc:
                    _, category = _categorize_error(exc)
                    result["error"] = str(exc)
                    result["error_category"] = category

                with console_lock:
                    progress["done"] += 1
                    idx = progress["done"]
                    if result["error"]:
                        _emit("error", f"failed {domain_name} [{idx}/{total}]: {result['error']}")
                    else:
                        _emit("info", f"enriched {domain_name} [{idx}/{total}]")

                return result

            def _on_error(domain_info: Dict[str, Any], exc: BaseException) -> Dict[str, Any]:
                _, category = _categorize_error(exc)
                result = _base_row(domain_info)
                result["error"] = str(exc)
                result["error_category"] = category
                return result

            results = map_items(raw_domains, _enrich, workers=workers, on_error=_on_error)

        ordered = sorted(results, key=lambda r: r["domain"])
        render_results(
            ordered, output_format, csv_fields=csv_fields, csv_rows=_csv_rows, text=_text
        )
        exit_on_errors(ordered)

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
