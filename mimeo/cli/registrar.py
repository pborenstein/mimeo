"""Registrar commands for managing domain registrar settings."""

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any, Dict

import click

from ..exceptions import EXIT_CONFIG, ConfigurationError
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
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                writer.writeheader()
            else:
                click.echo("No domains found in Porkbun account.")
            return

        total = len(raw_domains)
        indexed = [(i, d) for i, d in enumerate(raw_domains, 1)]
        enriched: Dict[int, Dict[str, Any]] = {}

        console_lock = Lock()

        def _enrich(idx: int, domain_info: Dict[str, Any]) -> Dict[str, Any]:
            domain_name = domain_info.get("domain", "")
            auto_renew_raw = domain_info.get("autoRenew")
            auto_renew = auto_renew_raw in ("1", 1, True)

            result: Dict[str, Any] = {
                "domain": domain_name,
                "tld": domain_info.get("tld", ""),
                "expires": domain_info.get("expireDate", ""),
                "auto_renew": auto_renew,
            }

            with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as r:
                ns_result = r.check_nameservers(domain_name)
            result["nameservers"] = ns_result.actual
            result["ns_ok"] = ns_result.ok

            if with_dns:
                with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_prov:
                    result["dns_records"] = dns_prov._get_domain_records(domain_name)
            else:
                result["dns_records"] = []

            with console_lock:
                _emit("info", f"enriched {domain_name} [{idx}/{total}]")

            return result

        with ThreadPoolExecutor(max_workers=min(total, workers)) as executor:
            futures = {
                executor.submit(_enrich, i, info): i
                for i, info in indexed
            }
            for future in as_completed(futures):
                i = futures[future]
                enriched[i] = future.result()

        ordered = sorted(enriched.values(), key=lambda r: r["domain"])

        if output_format == "json":
            click.echo(json.dumps(ordered, indent=2))

        elif output_format == "csv":
            fieldnames = ["domain", "tld", "expires", "auto_renew", "ns_ok", "nameservers"]
            if with_dns:
                fieldnames.append("dns_records")

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

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
