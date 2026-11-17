"""Compare what was read about a hostname with what its site needs.

`compare` turns a Connection into a Plan: the list of changes that would
make the DNS records and host settings right, plus the problems no
change can fix. `status` prints a Plan and `sync` applies it, so the two
cannot disagree about what is wrong.
"""

from dataclasses import dataclass, field, replace
from datetime import date

from mimeo.connection import Connection
from mimeo.exceptions import HostError
from mimeo.models import ADDRESS_TYPES, DNSRecord
from mimeo.providers.base import Host

# Certificate states GitHub reports while it is still issuing.
PENDING_CERT_STATES = frozenset({"new", "authorization_created", "authorization_pending", "issued"})

# GitHub renews well before this many days remain, so a certificate this
# close to expiry means renewal is not happening.
CERT_EXPIRY_WARNING_DAYS = 14


@dataclass
class Change:
    """One change that would bring a hostname's connection into agreement."""

    target: str  # "dns" or "host"
    action: str  # "add_record", "delete_record", "enforce_https", "request_certificate"
    summary: str
    record: DNSRecord | None = None


@dataclass
class Plan:
    """The result of comparing a Connection with what its site needs."""

    changes: list[Change] = field(default_factory=list)
    # Things that are wrong and that no change here fixes, in plain words.
    problems: list[str] = field(default_factory=list)
    # What to do about the problems, by hand, in order.
    fixes: list[str] = field(default_factory=list)
    # True when the fixes are alternatives to pick one from, not steps.
    fixes_are_choices: bool = False
    # ok, missing, extra, external, unknown; None when there is nothing to compare.
    records: str | None = None
    # ok, fixable, pending, no cert, cert error, expiring, no pages, no domain;
    # None with no site.
    site: str | None = None
    missing: list[DNSRecord] = field(default_factory=list)
    extra: list[DNSRecord] = field(default_factory=list)
    # True when any of the site's records is proxied; None when the
    # provider has no such setting or nothing was compared.
    proxied: bool | None = None
    # The site's records that are proxied now.
    proxied_records: list[DNSRecord] = field(default_factory=list)

    @property
    def has_problem(self) -> bool:
        """True when anything needs attention."""
        return bool(self.changes or self.problems)

    @property
    def fixable(self) -> bool:
        """True when applying the changes would fix something."""
        return bool(self.changes)


def _days_until(day: str | None, today: date) -> int | None:
    """Days from today to an ISO date; None when it cannot be read."""
    if not day:
        return None
    try:
        return (date.fromisoformat(day[:10]) - today).days
    except ValueError:
        return None


def compare(conn: Connection, host: Host, today: date | None = None) -> Plan:
    """Work out what is wrong with a hostname's connection and what would fix it.

    Args:
        conn: What Fleet.read returned for the hostname
        host: The host serving the site
        today: The date certificate expiry is measured from (default: today)
    """
    plan = Plan()
    today = today or date.today()

    if conn.zone is not None and not conn.nameservers:
        plan.records = "unknown"
        plan.problems.append(
            f"{conn.zone} has no nameservers set at the registrar, so nothing answers for it"
        )
        plan.fixes.append(
            f"Run: mimeo delegate {conn.zone} --dns porkbun --empty"
            "  (or --dns cloudflare). The zone starts with no records."
        )
        if conn.site is not None:
            plan.fixes.append(f"Run: mimeo sync {conn.hostname}")

    if conn.site is None or conn.state is None:
        return plan

    if conn.zone is None and conn.public_nameservers == []:
        _domain_is_gone(conn, plan)
        return plan

    _compare_records(conn, host, plan)
    _compare_site(conn, plan, today)
    return plan


def _domain_is_gone(conn: Connection, plan: Plan) -> None:
    """A site whose hostname is not at the registrar and has no DNS at all.

    The certificate is not judged: with no domain there is nothing to
    issue one for, and the choice to make is about the repository.
    """
    assert conn.site is not None
    name = conn.hostname
    plan.site = "no domain"
    plan.problems.append(
        f"{name} is not in the registrar account and nothing answers for it in DNS, so"
        f" the registration has most likely lapsed. The repository {conn.site.ref} is"
        " still set up to serve it."
    )
    plan.fixes_are_choices = True
    plan.fixes.extend(
        [
            f"Keep the repository and take the domain off it: mimeo unlink {name}",
            f"Delete the repository: mimeo delete {name}",
            f"Move the repository to another account: open {_repo_settings(conn)},"
            " scroll to Danger Zone, click Transfer ownership",
            f"Get the domain back: register {name} again, then run: mimeo sync {name}",
        ]
    )


def _repo_settings(conn: Connection) -> str:
    """The repository's own settings page, as something to open."""
    assert conn.site is not None
    if conn.site.host == "github":
        return f"https://github.com/{conn.site.ref}/settings"
    return f"the settings of {conn.site}"


def _compare_records(conn: Connection, host: Host, plan: Plan) -> None:
    """Compare the address records at the site's names with what the host needs."""
    assert conn.site is not None
    if conn.zone is None or plan.records == "unknown":
        return
    if conn.dns is None or conn.records is None:
        # Another provider answers for the zone and mimeo cannot read it (DEC-037).
        plan.records = "external"
        return

    required = host.required_records(conn.site, conn.label)
    names = {r.name for r in required}
    live = [r for r in conn.records if r.name in names and r.type in ADDRESS_TYPES]
    live_keys = {r.key() for r in live}
    required_keys = {r.key() for r in required}
    if any(r.proxied is not None for r in live):
        plan.proxied = any(r.proxied for r in live)
        plan.proxied_records = [r for r in live if r.proxied]

    plan.extra = [r for r in live if r.key() not in required_keys]
    plan.missing = [r for r in required if r.key() not in live_keys]

    # A proxied name is answered by the DNS provider itself, over IPv4 and
    # IPv6, whatever address records sit behind it. Once such a name has
    # some of its required records, the rest of the same kind add nothing.
    proxied_names = {
        r.name for r in live if r.proxied and r.key() in required_keys
    }
    plan.missing = [
        r for r in plan.missing if not (r.name in proxied_names and r.type in ("A", "AAAA"))
    ]

    # Removals come first: a name holds one CNAME, and an ALIAS at the
    # apex blocks A records.
    for record in plan.extra:
        plan.changes.append(
            Change("dns", "delete_record", f"remove {record.describe()}", record)
        )
    for record in plan.missing:
        # A new record takes the proxy setting already in use at its name,
        # so adding one never changes how the name is served (DEC-043).
        at_name = [r for r in live if r.name == record.name]
        if any(r.proxied is not None for r in at_name):
            record = replace(record, proxied=any(r.proxied for r in at_name))
        plan.changes.append(Change("dns", "add_record", f"add {record.describe()}", record))

    if plan.missing:
        plan.records = "missing"
    elif plan.extra:
        plan.records = "extra"
    else:
        plan.records = "ok"


def _compare_site(conn: Connection, plan: Plan, today: date) -> None:
    """Judge the site's certificate and HTTPS setting."""
    state = conn.state
    assert state is not None
    name = conn.hostname
    if not state.configured:
        plan.site = "no pages"
        plan.problems.append(
            f"Pages is turned off for the repository, so nothing is served at {name}"
        )
        plan.fixes.extend(
            [
                f"Open {_settings(conn)}",
                'Under "Build and deployment", set Source to "GitHub Actions"',
                f"Run: mimeo status {name}",
            ]
        )
        return

    cert = state.cert_state
    if cert == "approved":
        days = _days_until(state.cert_expires, today)
        if days is not None and days <= CERT_EXPIRY_WARNING_DAYS:
            plan.site = "expiring"
            plan.problems.append(
                f"The HTTPS certificate {_expiry(state.cert_expires, today)} and has not been"
                f" renewed. After that date browsers will refuse to open https://{name}."
            )
            plan.fixes.extend(_certificate_steps(conn, plan))
        elif not state.https_enforced:
            plan.site = "fixable"
            plan.changes.append(Change("host", "enforce_https", "enforce HTTPS"))
        else:
            plan.site = "ok"
    elif cert in PENDING_CERT_STATES:
        plan.site = "pending"
        plan.problems.append(
            "The HTTPS certificate is being issued. Nothing to do but wait; it usually"
            " takes under an hour."
        )
    elif cert is None:
        plan.site = "no cert"
        dns_changes = any(c.target == "dns" for c in plan.changes)
        if conn.zone is not None and plan.records == "ok" and not plan.proxied:
            # The records point at the site and nothing is in the way, so
            # saving the custom domain again gets the certificate requested.
            plan.changes.append(
                Change(
                    "host",
                    "request_certificate",
                    "request the HTTPS certificate (removes the custom domain and sets it again)",
                )
            )
            return
        plan.problems.append(
            f"There is no HTTPS certificate for {name}, so https://{name} does not open."
            " A certificate is requested only at the moment the custom domain is saved."
        )
        if conn.zone is not None and dns_changes and not plan.proxied:
            plan.fixes.extend(
                [
                    f"Run: mimeo sync {name}",
                    f"Wait 5 minutes, then run: mimeo sync {name} again. With the records"
                    " right, that run requests the certificate.",
                ]
            )
        else:
            plan.fixes.extend(_certificate_steps(conn, plan))
    else:
        plan.site = "cert error"
        days = _days_until(state.cert_expires, today)
        if days is not None and days < 0:
            plan.problems.append(
                f"The HTTPS certificate could not be renewed. It expired"
                f" {(state.cert_expires or '')[:10]}, so browsers refuse to open https://{name}."
            )
        elif state.cert_expires:
            plan.problems.append(
                f"The HTTPS certificate could not be renewed. It"
                f" {_expiry(state.cert_expires, today)}; after that date browsers refuse"
                f" to open https://{name}."
            )
        else:
            plan.problems.append(
                f"The HTTPS certificate for {name} could not be issued, so https://{name}"
                " does not open."
            )
        plan.fixes.extend(_certificate_steps(conn, plan))


def _expiry(day: str | None, today: date) -> str:
    """`expires 2026-12-12` or `expired 2026-11-14`."""
    days = _days_until(day, today)
    verb = "expired" if days is not None and days < 0 else "expires"
    return f"{verb} {(day or '')[:10]}"


def _settings(conn: Connection) -> str:
    """Where the site's custom domain is set, as something to open."""
    assert conn.site is not None
    if conn.site.host == "github":
        return f"https://github.com/{conn.site.ref}/settings/pages"
    return f"the settings of {conn.site}"


def _certificate_steps(conn: Connection, plan: Plan) -> list[str]:
    """The steps, by hand, that get a certificate issued or renewed.

    The certificate is issued only when the host can reach the site
    directly at records that point to it, and the request is made when
    the custom domain is saved. So: put the records right, take any
    proxy out of the way, save the custom domain again, wait.
    """
    assert conn.site is not None and conn.state is not None
    name = conn.hostname
    domain = conn.state.custom_domain or name
    steps: list[str] = []

    if conn.zone is None:
        steps.append(
            f"{name} is not in the registrar account, so its DNS cannot be read from here."
            f" If the registration lapsed and you do not want it back, open"
            f" {_settings(conn)}, click Remove under Custom domain, and stop here."
        )
        steps.append(
            f"Otherwise, wherever its DNS is managed, make sure {name} points at the"
            " site, then continue."
        )
    elif plan.records == "external":
        steps.append(
            f"The DNS for {conn.zone} is at a provider mimeo is not set up for. There,"
            f" make sure {name} points at the site, then continue."
        )
    elif any(c.target == "dns" for c in plan.changes):
        steps.append(f"Run: mimeo sync {name}")

    proxied = plan.proxied_records
    if proxied:
        assert conn.dns is not None
        which = ", ".join(sorted({f"{r.type} {r.name or '@'}" for r in proxied}))
        steps.append(
            f"In the {conn.dns.name.capitalize()} dashboard, open {conn.zone} > DNS > Records"
        )
        steps.append(
            f"Edit each of these and switch Proxy status to DNS only: {which}."
            " The proxy is what blocks the certificate."
        )

    steps.append(f"Open {_settings(conn)}")
    steps.append("Under Custom domain, click Remove")
    steps.append(f"Type {domain} back into Custom domain and click Save")
    steps.append(
        f"Wait 15 minutes, then run: mimeo status {name}. Repeat until SITE says"
        " ok or fixable; it can take an hour."
    )
    if not conn.state.https_enforced:
        steps.append(f"When it says fixable, run: mimeo sync {name}")
    if proxied:
        steps.append("Switch the same records back to Proxied")
    return steps


def apply(conn: Connection, plan: Plan, host: Host) -> list[str]:
    """Carry out a plan's changes, in order.

    Returns:
        The summary of each change made

    Raises:
        Whatever the provider raises; changes already made stay made
    """
    done: list[str] = []
    for change in plan.changes:
        if change.target == "dns":
            assert conn.dns is not None and conn.zone is not None and change.record is not None
            if change.action == "delete_record":
                conn.dns.delete_record(conn.zone, change.record)
            else:
                conn.dns.add_record(conn.zone, change.record)
        elif change.action == "enforce_https":
            assert conn.site is not None
            if not host.enforce_https(conn.site):
                continue
        elif change.action == "request_certificate":
            assert conn.site is not None and conn.state is not None
            domain = conn.state.custom_domain or conn.hostname
            host.set_custom_domain(conn.site, None)
            try:
                host.set_custom_domain(conn.site, domain)
            except Exception as exc:
                raise HostError(
                    f"The custom domain {domain} was removed from {conn.site} and could not"
                    f" be set again ({exc}). Put it back with: mimeo link {domain} {conn.site}",
                    status_code=getattr(exc, "status_code", None),
                ) from exc
        done.append(change.summary)
    return done
