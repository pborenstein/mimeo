"""Registrar commands for managing domain registrar settings."""

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any, Dict

import click

from ..exceptions import EXIT_CONFIG, EXIT_PARTIAL, ConfigurationError
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar
from ._processing import _categorize_error, _emit


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

    try:
        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as reg:
            raw_domains = reg.list_domains()

        if not raw_domains:
            if output_format == "json":
                click.echo("[]")
            elif output_format == "csv":
                fieldnames = ["domain", "tld", "expires", "auto_renew", "ns_ok", "nameservers"]
                if with_dns:
                    fieldnames.append("dns_records")
                fieldnames.append("error")
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                writer.writeheader()
            else:
                click.echo("No domains found in Porkbun account.")
            return

        total = len(raw_domains)
        indexed = [(i, d) for i, d in enumerate(raw_domains, 1)]
        enriched: Dict[int, Dict[str, Any]] = {}

        console_lock = Lock()

        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as reg2, \
                PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_prov:

            def _enrich(idx: int, domain_info: Dict[str, Any]) -> Dict[str, Any]:
                domain_name = domain_info.get("domain", "")
                auto_renew_raw = domain_info.get("autoRenew")
                auto_renew = auto_renew_raw in ("1", 1, True)

                result: Dict[str, Any] = {
                    "domain": domain_name,
                    "tld": domain_info.get("tld", ""),
                    "expires": domain_info.get("expireDate", ""),
                    "auto_renew": auto_renew,
                    "nameservers": [],
                    "ns_ok": False,
                    "dns_records": [],
                    "error": None,
                }

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
                    if result["error"]:
                        _emit("error", f"failed {domain_name} [{idx}/{total}]: {result['error']}")
                    else:
                        _emit("info", f"enriched {domain_name} [{idx}/{total}]")

                return result

            with ThreadPoolExecutor(max_workers=min(total, workers)) as executor:
                futures = {
                    executor.submit(_enrich, i, info): i
                    for i, info in indexed
                }
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        enriched[i] = future.result()
                    except Exception as exc:
                        _, category = _categorize_error(exc)
                        info = indexed[i - 1][1]
                        enriched[i] = {
                            "domain": info.get("domain", ""),
                            "tld": info.get("tld", ""),
                            "expires": info.get("expireDate", ""),
                            "auto_renew": info.get("autoRenew") in ("1", 1, True),
                            "nameservers": [],
                            "ns_ok": False,
                            "dns_records": [],
                            "error": str(exc),
                            "error_category": category,
                        }

        ordered = sorted(enriched.values(), key=lambda r: r["domain"])
        failed = [r for r in ordered if r.get("error")]

        if output_format == "json":
            click.echo(json.dumps(ordered, indent=2))

        elif output_format == "csv":
            fieldnames = ["domain", "tld", "expires", "auto_renew", "ns_ok", "nameservers"]
            if with_dns:
                fieldnames.append("dns_records")
            fieldnames.append("error")

            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in ordered:
                flat = dict(row)
                flat["nameservers"] = "|".join(row.get("nameservers") or [])
                if with_dns:
                    dns_parts = [
                        f"{r.get('type','')}:{r.get('name','')}={r.get('content','')}"
                        for r in row.get("dns_records") or []
                    ]
                    flat["dns_records"] = "|".join(dns_parts)
                writer.writerow(flat)

        else:
            if not ordered:
                click.echo("No domains found.")
                return

            domain_w = max(len(r["domain"]) for r in ordered)
            expires_w = max(len(r["expires"]) for r in ordered)
            ns_w = 60

            click.echo()
            header = f"  {'DOMAIN':<{domain_w}}  {'EXPIRES':<{expires_w}}  {'NS_OK':<5}  {'NAMESERVERS':<{ns_w}}"
            click.secho(header, bold=True)
            click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

            for row in ordered:
                if row.get("error"):
                    line = f"  {row['domain']:<{domain_w}}  {row['expires']:<{expires_w}}  "
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
                line = f"  {row['domain']:<{domain_w}}  {row['expires']:<{expires_w}}  "
                click.echo(line, nl=False)
                click.secho(f"{ns_label:<5}", fg=ns_color, nl=False)
                click.echo(f"  {ns_str}")

            click.echo()

        if failed:
            for r in failed:
                click.secho(
                    f"[{r.get('error_category', 'provider')}] {r['domain']}: {r['error']}",
                    fg="red",
                    err=True,
                )
            click.secho(
                f"warning: {len(failed)}/{total} domains failed to enrich; results are partial",
                fg="yellow",
                err=True,
            )
            sys.exit(EXIT_PARTIAL)

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
