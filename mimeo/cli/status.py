"""Status command: cross-provider view of the whole fleet."""

import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..providers.host.github import GitHubHost, health_status
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar, lookup_nameservers
from ..providers.registrar.porkbun import PORKBUN_NAMESERVERS
from ..exceptions import EXIT_CONFIG
from ._processing import (
    _categorize_error,
    exit_on_errors,
    load_config,
    map_items,
    render_results,
    validate_domains,
)

_CSV_FIELDS = [
    "domain",
    "registered",
    "expires",
    "auto_renew",
    "ns_ok",
    "repo",
    "dns_status",
    "site_health",
    "https_enforced",
    "cert_state",
    "error",
]

_DNS_COLORS = {"ok": "green", "drift": "yellow", "missing": "red", "error": "red"}
_SITE_COLORS = {
    "healthy": "green",
    "fixable": "yellow",
    "cert_pending": "yellow",
    "no_cert": "red",
    "pages_error": "red",
}
_SITE_LABELS = {
    "healthy": "ok",
    "fixable": "fixable",
    "cert_pending": "pending",
    "no_cert": "no cert",
    "pages_error": "error",
}


def _has_problem(row: Dict[str, Any]) -> bool:
    """True when anything about the domain needs attention."""
    if row.get("error"):
        return True
    if not row["registered"] or not row["repo"]:
        return True
    if not row["ns_ok"]:
        return True
    if row["dns_status"] not in ("ok", None):
        return True
    if row["site_health"] not in ("healthy", None):
        return True
    return False


def _fixable_by_sync(row: Dict[str, Any]) -> bool:
    """True when `mimeo sync` can act on this domain's problem.

    Missing/drifted DNS, NS mismatch, and HTTPS-enforceable certs are all
    things sync converges. Missing repos, unregistered domains, other
    site-health states (no_cert, cert_pending, pages_error), and API
    errors are not -- sync has nothing to do for those.
    """
    if row.get("error"):
        return False
    if not row["registered"] or not row["repo"]:
        return False
    if row["ns_ok"] is False:
        return True
    if row["dns_status"] in ("drift", "missing"):
        return True
    if row["site_health"] == "fixable":
        return True
    return False


def _text(rows: List[Dict[str, Any]], with_dns: bool = False, show_template: bool = False) -> None:
    if not rows:
        click.echo("Nothing to report.")
        return

    domain_w = max(max(len(r["domain"]) for r in rows), len("DOMAIN"))
    expires_w = max(max(len(r["expires"] or "-") for r in rows), len("EXPIRES"))
    tmpl_w = max(len(r.get("template") or "-") for r in rows) if show_template else 0

    click.echo()
    header = f"  {'DOMAIN':<{domain_w}}  {'EXPIRES':<{expires_w}}  {'NS':<4}  {'DNS':<8}  SITE"
    if show_template:
        header += f"  {'TEMPLATE':<{tmpl_w}}"
    click.secho(header, bold=True)
    click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

    problems = 0
    fixable = 0
    for row in rows:
        if _has_problem(row):
            problems += 1
            if _fixable_by_sync(row):
                fixable += 1

        click.echo(f"  {row['domain']:<{domain_w}}  ", nl=False)

        expires = (row["expires"] or "-")[:10] if row["registered"] else "-"
        click.echo(f"{expires:<{expires_w}}  ", nl=False)

        if not row["registered"]:
            click.secho(f"{'-':<4}", fg="red", nl=False)
        elif row["ns_ok"]:
            click.secho(f"{'ok':<4}", fg="green", nl=False)
        else:
            click.secho(f"{'no':<4}", fg="red", nl=False)
        click.echo("  ", nl=False)

        dns_status = row["dns_status"]
        if dns_status is None:
            click.echo(f"{'-':<8}", nl=False)
        else:
            click.secho(f"{dns_status:<8}", fg=_DNS_COLORS.get(dns_status, "white"), nl=False)
        click.echo("  ", nl=False)

        if not row["repo"]:
            click.secho("no repo", fg="red" if row["registered"] else "white", nl=False)
        else:
            site = row["site_health"] or "pages_error"
            click.secho(
                _SITE_LABELS.get(site, site), fg=_SITE_COLORS.get(site, "white"), nl=False
            )

        if show_template:
            click.echo(f"  {(row.get('template') or '-'):<{tmpl_w}}", nl=False)

        if row.get("error"):
            click.secho(f"  [{row['error']}]", fg="red", nl=False)
        click.echo()

        if (
            with_dns
            and row["registered"]
            and not row.get("dns_records")
            and row["ns_ok"] is False
            and row["nameservers"]
        ):
            click.secho(
                f"      (no records at Porkbun; nameservers point to "
                f"{', '.join(row['nameservers'])})",
                fg="yellow",
            )

        if with_dns and row.get("dns_records"):
            recs = row["dns_records"]
            type_w = max(len(r.get("type", "")) for r in recs)
            name_w = max(len(r.get("name", "")) for r in recs)
            ttl_w = max(len(str(r.get("ttl", ""))) for r in recs)
            for rec in recs:
                click.secho(
                    f"      {rec.get('type',''):<{type_w}}  {rec.get('name',''):<{name_w}}  "
                    f"{str(rec.get('ttl','')):<{ttl_w}}  {rec.get('content','')}",
                    dim=True,
                )

    click.echo()
    color = "green" if problems == 0 else "yellow"
    summary = f"{len(rows)} domain(s), {problems} with issues"
    if fixable:
        summary += f" ({fixable} fixable with: mimeo sync)"
    click.secho(summary, fg=color)
    click.echo()


def _text_github(rows: List[Dict[str, Any]], show_template: bool = False) -> None:
    if not rows:
        click.echo("No mimeo-managed sites found.")
        click.echo()
        click.echo("Create your first site with: mimeo create example.com")
        return

    name_w = max(len(r["domain"]) for r in rows)
    site_w = max(len(r["site"]) for r in rows)
    tmpl_w = max(len(r.get("template") or "-") for r in rows) if show_template else 0

    click.echo()

    header = f"  {'NAME':<{name_w}}  {'SITE':<{site_w}}  {'UPDATED':<10}"
    if show_template:
        header += f"  {'TEMPLATE':<{tmpl_w}}"
    header += "  HEALTH"
    click.secho(header, bold=True)
    click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

    for row in rows:
        line = f"  {row['domain']:<{name_w}}  {row['site']:<{site_w}}  {row['updated']:<10}"
        click.echo(line, nl=False)
        if show_template:
            tmpl = row.get("template") or "-"
            click.echo(f"  {tmpl:<{tmpl_w}}", nl=False)
        status_ = row.get("health", "pages_error")
        color = _SITE_COLORS.get(status_, "white")
        label = _SITE_LABELS.get(status_, status_)
        click.echo("  ", nl=False)
        click.secho(f"{label:<8}", fg=color)

    click.echo()


def _text_porkbun(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        click.echo("No domains found in Porkbun account.")
        return

    domain_w = max(len(r["domain"]) for r in rows)
    expires_w = max(len(r["expires"]) for r in rows)
    ns_w = 60

    click.echo()
    header = f"  {'DOMAIN':<{domain_w}}  {'EXPIRES':<{expires_w}}  {'NS_OK':<5}  {'NAMESERVERS':<{ns_w}}"
    click.secho(header, bold=True)
    click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

    for row in rows:
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


def _text_dns_show(rows: List[Dict[str, Any]]) -> None:
    click.echo()
    for entry in rows:
        click.secho(f"  {entry['domain']}", bold=True)
        if entry["error"]:
            click.secho(f"    error: {entry['error']}", fg="red")
            click.echo()
            continue
        if not entry["records"]:
            if entry.get("note"):
                click.secho(f"    ({entry['note']})", fg="yellow")
            else:
                click.echo("    (no records)")
            click.echo()
            continue

        recs = [
            (
                rec.get("type", ""),
                rec.get("name", ""),
                str(rec.get("ttl", "")),
                rec.get("content", ""),
            )
            for rec in entry["records"]
        ]
        type_w = max(len("TYPE"), max(len(r[0]) for r in recs))
        name_w = max(len("NAME"), max(len(r[1]) for r in recs))
        ttl_w = max(len("TTL"), max(len(r[2]) for r in recs))

        click.secho(
            f"    {'TYPE':<{type_w}}  {'NAME':<{name_w}}  {'TTL':<{ttl_w}}  CONTENT",
            dim=True,
        )
        for type_, name, ttl, content in recs:
            click.echo(f"    {type_:<{type_w}}  {name:<{name_w}}  {ttl:<{ttl_w}}  {content}")
        click.echo()


def _text_dns_check(rows: List[Dict[str, Any]]) -> None:
    click.echo()
    _ns_colors = {True: "green", False: "red"}

    for r in rows:
        click.secho(f"  {r['domain']}", bold=True)
        ns_label = (
            "ok (porkbun)"
            if r["ns_ok"]
            else ", ".join(r["nameservers"])
            if r["nameservers"]
            else "unknown"
        )
        click.echo("    NS: ", nl=False)
        click.secho(ns_label, fg=_ns_colors.get(r["ns_ok"], "white"))

        click.echo("    DNS: ", nl=False)
        click.secho(r["dns_status"], fg=_DNS_COLORS.get(r["dns_status"], "white"))

        for rec in r.get("missing", []):
            click.secho(
                f"      missing: {rec['type']} {rec['name']} -> {rec['content']}", fg="red"
            )
        for rec in r.get("extra", []):
            click.secho(
                f"      extra:   {rec['type']} {rec['name']} -> {rec['content']}",
                fg="yellow",
            )
        if r.get("error"):
            click.secho(f"      error: {r['error']}", fg="red")
        click.echo()


@click.command()
@click.argument("domains", nargs=-1)
@click.option(
    "--all",
    "status_all",
    is_flag=True,
    help="Report on every domain in the fleet (required when no domains are given)",
)
@click.option(
    "--source",
    type=click.Choice(["github", "porkbun", "dns"], case_sensitive=False),
    default=None,
    help="Report on a single provider instead of the full cross-provider join",
)
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
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
@click.option(
    "--problems",
    is_flag=True,
    help="Show only domains that need attention (with --source dns, compares live "
    "records against expected instead of just showing them)",
)
@click.option(
    "--with-dns",
    is_flag=True,
    help="Include the full live DNS records for each registered domain",
)
@click.option(
    "--health",
    is_flag=True,
    help="With --source github, check Pages configuration health for each site",
)
@click.option(
    "--show-template",
    is_flag=True,
    help="Show the template each site was created from",
)
def status(
    domains: tuple[str, ...],
    status_all: bool,
    source: str | None,
    config: Path | None,
    output_format: str,
    workers: int,
    problems: bool,
    with_dns: bool,
    health: bool,
    show_template: bool,
) -> None:
    """Show fleet status: registrar, DNS, and site health in one view.

    Joins the Porkbun account against mimeo-managed GitHub repositories.
    With --all, covers the union of both: registered domains with no
    site show as "no repo"; sites whose domain is not in the account
    show "-" on the registrar side. A fleet sweep makes several API
    calls per domain, so it takes a while on large accounts — name
    domains for a quick check.

    --source narrows the report to a single provider instead of the
    cross-provider join:

    \b
        github    mimeo-managed repositories only (like the old `list`)
        porkbun   registered domains only (like the old `registrar list`)
        dns       live DNS records ("dns show"), or with --problems,
                  drift against expected records ("dns check")

    \b
    Columns (full join):
        EXPIRES  registration expiry ("-" if not in Porkbun account)
        NS       nameservers point to Porkbun
        DNS      live records vs GitHub Pages expectations
                 ("-" when there is no repo: no desired state to compare)
        SITE     Pages health (ok / fixable / pending / no cert / error)

    \b
    Examples:
        mimeo status example.com           # one domain
        mimeo status --all                 # whole fleet (takes a while)
        mimeo status --all --problems      # only what needs attention
        mimeo status --all --format json | jq '.[] | select(.dns_status == "drift")'
        mimeo status example.com --with-dns --format json | jq '.[0].dns_records'
        mimeo status --source github --all --health
        mimeo status --source porkbun --all --with-dns
        mimeo status --source dns example.com --problems
    """
    if domains and status_all:
        click.secho("Give either domain names or --all, not both.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if not domains and not status_all:
        click.secho(
            "A whole-fleet sweep takes several API calls per domain. "
            "Name the domains to check, or pass --all to do the full fleet.",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)
    if domains:
        validate_domains(domains)

    try:
        if source == "github":
            _status_github(domains, config, output_format, workers, health, show_template)
        elif source == "porkbun":
            _status_porkbun(domains, config, output_format, workers, with_dns)
        elif source == "dns":
            if problems:
                _status_dns_check(domains, config, output_format, workers)
            else:
                _status_dns_show(domains, config, output_format)
        else:
            _status_full(
                domains,
                status_all,
                config,
                output_format,
                workers,
                problems,
                with_dns,
                show_template,
            )
    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)


def _status_full(
    domains: tuple[str, ...],
    status_all: bool,
    config: Path | None,
    output_format: str,
    workers: int,
    problems: bool,
    with_dns: bool,
    show_template: bool,
) -> None:
    cfg = load_config(config)
    owner = cfg.github_username

    with GitHubHost(default_org=owner) as host, \
            PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar, \
            PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_provider:

        registered_map: Dict[str, Dict[str, Any]] = {
            d.get("domain", ""): d for d in registrar.list_domains()
        }
        repo_names = {r.get("name", "") for r in host.list_mimeo_repositories()}

        if domains:
            targets = list(domains)
        else:
            # Explicitly named domains are always checked; the config
            # ignore list only trims fleet-wide sweeps.
            ignored = (set(registered_map) | repo_names) & set(cfg.ignore_domains)
            targets = sorted((set(registered_map) | repo_names) - ignored)
            if ignored:
                click.secho(
                    f"({len(ignored)} domain(s) ignored per config: "
                    f"{', '.join(sorted(ignored))})",
                    fg="white",
                    dim=True,
                    err=True,
                )

        def _status_row(domain: str) -> Dict[str, Any]:
            info = registered_map.get(domain)
            row: Dict[str, Any] = {
                "domain": domain,
                "registered": info is not None,
                "expires": info.get("expireDate", "") if info else "",
                "auto_renew": info.get("autoRenew") in ("1", 1, True) if info else None,
                "ns_ok": None,
                "nameservers": [],
                "repo": domain in repo_names,
                "dns_status": None,
                "missing": [],
                "extra": [],
                "site_health": None,
                "https_enforced": None,
                "cert_state": None,
                "dns_records": [],
                "template": None,
                "error": None,
            }

            try:
                if row["registered"]:
                    ns_result = registrar.check_nameservers(domain)
                    row["ns_ok"] = ns_result.ok
                    row["nameservers"] = ns_result.actual

                live_records = None
                if with_dns and row["registered"]:
                    live_records = dns_provider.get_domain_records(domain)
                    row["dns_records"] = live_records

                if row["repo"]:
                    health = host.get_pages_health(f"{owner}/{domain}")
                    row["site_health"] = health_status(health)
                    row["https_enforced"] = health["https_enforced"]
                    row["cert_state"] = health["cert_state"]

                    if show_template:
                        row["template"] = host.get_template_repository(f"{owner}/{domain}")

                    if row["registered"]:
                        expected = host.required_dns_records(domain)
                        drift = dns_provider.check_dns_drift(
                            domain, expected, live_records=live_records
                        )
                        row["dns_status"] = drift["status"]
                        row["missing"] = drift.get("missing", [])
                        row["extra"] = drift.get("extra", [])
            except Exception as exc:
                _, category = _categorize_error(exc)
                row["error"] = str(exc)
                row["error_category"] = category

            return row

        def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
            _, category = _categorize_error(exc)
            return {
                "domain": domain,
                "registered": domain in registered_map,
                "expires": "",
                "auto_renew": None,
                "ns_ok": None,
                "nameservers": [],
                "repo": domain in repo_names,
                "dns_status": None,
                "missing": [],
                "extra": [],
                "site_health": None,
                "https_enforced": None,
                "cert_state": None,
                "dns_records": [],
                "template": None,
                "error": str(exc),
                "error_category": category,
            }

        results = map_items(targets, _status_row, workers=workers, on_error=_on_error)

    if problems:
        results = [r for r in results if _has_problem(r)]

    csv_fields = list(_CSV_FIELDS)
    csv_rows = None
    if show_template:
        csv_fields.insert(-1, "template")
    if with_dns:
        csv_fields.insert(-1, "dns_records")

    if with_dns:
        def csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
            flat = dict(row)
            flat["dns_records"] = "|".join(
                f"{r.get('type','')}:{r.get('name','')}={r.get('content','')}"
                for r in row.get("dns_records") or []
            )
            return [flat]

    render_results(
        results,
        output_format,
        csv_fields=csv_fields,
        csv_rows=csv_rows,
        text=lambda rows: _text(rows, with_dns=with_dns, show_template=show_template),
    )
    exit_on_errors(results)


def _status_github(
    domains: tuple[str, ...],
    config: Path | None,
    output_format: str,
    workers: int,
    health: bool,
    show_template: bool,
) -> None:
    cfg = load_config(config)
    owner = cfg.github_username

    csv_fields = ["domain", "repository", "site", "updated"]
    if show_template:
        csv_fields += ["template"]
    if health:
        csv_fields += ["health", "https_enforced", "cert_state"]

    with GitHubHost(default_org=owner) as host:
        repos = host.list_mimeo_repositories()

        rows = []
        for repo in repos:
            name = repo.get("name", "")
            if domains and name not in domains:
                continue
            rows.append(
                {
                    "domain": name,
                    "repository": repo.get("url", ""),
                    "site": repo.get("homepage") or f"https://{name}",
                    "updated": repo.get("updatedAt", "")[:10],
                }
            )

        if not rows:
            render_results(
                [], output_format, csv_fields=csv_fields,
                text=lambda rows: _text_github(rows, show_template=show_template),
            )
            return

        if health:

            def _with_health(row: Dict[str, Any]) -> Dict[str, Any]:
                h = host.get_pages_health(f"{owner}/{row['domain']}")
                return {
                    **row,
                    "health": health_status(h),
                    "https_enforced": h["https_enforced"],
                    "cert_state": h["cert_state"],
                }

            def _on_error(row: Dict[str, Any], exc: BaseException) -> Dict[str, Any]:
                return {
                    **row,
                    "health": "pages_error",
                    "https_enforced": False,
                    "cert_state": None,
                }

            rows = map_items(rows, _with_health, workers=workers, on_error=_on_error)

        if show_template:

            def _with_template(row: Dict[str, Any]) -> Dict[str, Any]:
                tmpl = host.get_template_repository(f"{owner}/{row['domain']}")
                return {**row, "template": tmpl}

            def _on_template_error(row: Dict[str, Any], exc: BaseException) -> Dict[str, Any]:
                return {**row, "template": None}

            rows = map_items(rows, _with_template, workers=workers, on_error=_on_template_error)

    _status_order = {
        "pages_error": 0,
        "no_cert": 1,
        "cert_pending": 2,
        "fixable": 3,
        "healthy": 4,
    }
    if health:
        rows.sort(key=lambda r: (_status_order.get(r.get("health", "pages_error"), 0), r["domain"]))
    else:
        rows.sort(key=lambda r: r["domain"])

    render_results(
        rows, output_format, csv_fields=csv_fields,
        text=lambda rows: _text_github(rows, show_template=show_template),
    )


def _status_porkbun(
    domains: tuple[str, ...],
    config: Path | None,
    output_format: str,
    workers: int,
    with_dns: bool,
) -> None:
    cfg = load_config(config)

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

    with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as reg:
        raw_domains = reg.list_domains()

    if domains:
        raw_domains = [d for d in raw_domains if d.get("domain", "") in domains]

    if not raw_domains:
        render_results([], output_format, csv_fields=csv_fields, text=_text_porkbun)
        return

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
        ordered, output_format, csv_fields=csv_fields, csv_rows=_csv_rows, text=_text_porkbun
    )
    exit_on_errors(ordered)


def _status_dns_show(
    domains: tuple[str, ...],
    config: Path | None,
    output_format: str,
) -> None:
    if not domains:
        click.secho(
            "Name the domains to check; --source dns has no fleet-wide mode.",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)

    cfg = load_config(config)

    def _csv_rows(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "domain": entry["domain"],
                "type": rec.get("type", ""),
                "name": rec.get("name", ""),
                "ttl": rec.get("ttl", ""),
                "prio": rec.get("prio", ""),
                "content": rec.get("content", ""),
            }
            for rec in entry["records"]
        ]

    with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_provider:

        def _fetch(domain: str) -> Dict[str, Any]:
            records = dns_provider.get_domain_records(domain)
            note = None
            if not records:
                ns = lookup_nameservers(domain)
                if ns and ns != sorted(PORKBUN_NAMESERVERS):
                    note = (
                        f"no records at Porkbun; nameservers point to "
                        f"{', '.join(ns)} -- records are managed there"
                    )
            return {
                "domain": domain,
                "records": records,
                "note": note,
                "error": None,
            }

        def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
            _, category = _categorize_error(exc)
            return {
                "domain": domain,
                "records": [],
                "note": None,
                "error": str(exc),
                "error_category": category,
            }

        results = map_items(domains, _fetch, sequential=True, on_error=_on_error)

    render_results(
        results,
        output_format,
        csv_fields=["domain", "type", "name", "ttl", "prio", "content"],
        csv_rows=_csv_rows,
        text=_text_dns_show,
    )
    exit_on_errors(results)


def _status_dns_check(
    domains: tuple[str, ...],
    config: Path | None,
    output_format: str,
    workers: int,
) -> None:
    if not domains:
        click.secho(
            "Name the domains to check; --source dns has no fleet-wide mode.",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)

    cfg = load_config(config)

    def _csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
        flat = dict(row)
        flat["nameservers"] = "|".join(row.get("nameservers") or [])
        return [flat]

    with GitHubHost(default_org=cfg.github_username) as host, \
            PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar, \
            PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_provider:

        def _check_domain(domain: str) -> Dict[str, Any]:
            expected = host.required_dns_records(domain)
            ns_result = registrar.check_nameservers(domain)
            try:
                drift = dns_provider.check_dns_drift(domain, expected)
            except Exception as exc:
                drift = {
                    "status": "error",
                    "missing": [],
                    "extra": [],
                    "error": str(exc),
                }

            return {
                "domain": domain,
                "ns_ok": ns_result.ok,
                "nameservers": ns_result.actual,
                "dns_status": drift["status"],
                "missing": drift.get("missing", []),
                "extra": drift.get("extra", []),
                "error": drift.get("error"),
            }

        def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
            _, category = _categorize_error(exc)
            return {
                "domain": domain,
                "ns_ok": False,
                "nameservers": [],
                "dns_status": "error",
                "missing": [],
                "extra": [],
                "error": str(exc),
                "error_category": category,
            }

        results = map_items(domains, _check_domain, workers=workers, on_error=_on_error)

    render_results(
        results,
        output_format,
        csv_fields=["domain", "ns_ok", "nameservers", "dns_status"],
        csv_rows=_csv_rows,
        text=_text_dns_check,
    )
    exit_on_errors(results)
