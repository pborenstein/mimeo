"""Compare what was read about a hostname with what its site needs.

`compare` turns a Connection into a Plan: the list of changes that would
make the DNS records and host settings right, plus the problems no
change can fix. `status` prints a Plan and `sync` applies it, so the two
cannot disagree about what is wrong.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date

from mimeo.connection import Connection
from mimeo.exceptions import HostError
from mimeo.models import ADDRESS_TYPES, DNSRecord
from mimeo.providers.base import Host

logger = logging.getLogger(__name__)

# Certificate states GitHub reports while it is still issuing.
PENDING_CERT_STATES = frozenset({"new", "authorization_created", "authorization_pending", "issued"})

# GitHub renews well before this many days remain, so a certificate this
# close to expiry means renewal is not happening.
CERT_EXPIRY_WARNING_DAYS = 14


@dataclass
class Change:
    """One change that would bring a hostname's connection into agreement."""

    target: str  # "dns" or "host"
    # "add_record", "delete_record", "enforce_https", "request_certificate",
    # "renew_behind_proxy"
    action: str
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
    # Things worth saying that are not problems.
    notes: list[str] = field(default_factory=list)
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
    if conn.zone is None and conn.public_nameservers:
        # Registered outside this account but answering in DNS: the
        # records cannot be read from here, the certificate still can.
        plan.records = "external"
        plan.notes.append(
            f"{conn.hostname} is not in this registrar account. Its nameservers are"
            f" {', '.join(conn.public_nameservers)}, so mimeo cannot read or change its"
            " records."
        )

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
            _fix_certificate(
                conn,
                plan,
                f"The HTTPS certificate {_expiry(state.cert_expires, today)} and has not been"
                f" renewed. After that date browsers will refuse to open https://{name}.",
                f"renew the HTTPS certificate, which {_expiry(state.cert_expires, today)}",
            )
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
        _fix_certificate(
            conn,
            plan,
            f"There is no HTTPS certificate for {name}, so https://{name} does not open."
            " A certificate is requested only at the moment the custom domain is saved.",
            "request the HTTPS certificate",
        )
    else:
        plan.site = "cert error"
        days = _days_until(state.cert_expires, today)
        if days is not None and days < 0:
            problem = (
                f"The HTTPS certificate could not be renewed. It expired"
                f" {(state.cert_expires or '')[:10]}, so browsers refuse to open https://{name}."
            )
            what = f"renew the HTTPS certificate, which {_expiry(state.cert_expires, today)}"
        elif state.cert_expires:
            problem = (
                f"The HTTPS certificate could not be renewed. It"
                f" {_expiry(state.cert_expires, today)}; after that date browsers refuse"
                f" to open https://{name}."
            )
            what = f"renew the HTTPS certificate, which {_expiry(state.cert_expires, today)}"
        else:
            problem = (
                f"The HTTPS certificate for {name} could not be issued, so https://{name}"
                " does not open."
            )
            what = "request the HTTPS certificate again"
        _fix_certificate(conn, plan, problem, what)


def _fix_certificate(conn: Connection, plan: Plan, problem: str, what: str) -> None:
    """Add the change that gets a certificate issued, or the problem and its steps.

    The host requests a certificate when the custom domain is saved, and
    issues it only if it can reach the site directly at records that
    point to it. So `sync` can do it when it can write the zone and the
    records are already right: it sets the custom domain again, first
    taking the DNS provider's proxy out of the way when it is on
    (DEC-050). When the records are wrong, this run fixes them and a
    later run asks for the certificate, because a record just written
    is not answered for yet. When the zone cannot be written from here,
    the steps are printed for doing by hand.
    """
    name = conn.hostname
    dns_changes = any(c.target == "dns" for c in plan.changes)
    writable = conn.zone is not None and conn.dns is not None

    if writable and dns_changes:
        plan.problems.append(problem)
        plan.fixes.extend(
            [
                f"Run: mimeo sync {name}",
                f"Wait 5 minutes, then run: mimeo sync {name} again. With the records"
                " right, that run gets the certificate issued.",
            ]
        )
    elif writable and plan.records == "ok" and plan.proxied_records:
        which = _names(plan.proxied_records)
        plan.changes.append(
            Change(
                "host",
                "renew_behind_proxy",
                f"{what} (switches {which} to DNS-only, sets the custom domain again,"
                " waits for the certificate, switches them back to proxied)",
            )
        )
    elif writable and plan.records == "ok":
        plan.changes.append(
            Change(
                "host",
                "request_certificate",
                f"{what} (removes the custom domain and sets it again)",
            )
        )
    else:
        plan.problems.append(problem)
        plan.fixes.extend(_certificate_steps(conn, plan))


def _names(records: list[DNSRecord]) -> str:
    """`A @, CNAME www`: the distinct type-and-name pairs among records."""
    return ", ".join(sorted({f"{r.type} {r.name or '@'}" for r in records}))


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

    if conn.zone is None and conn.public_nameservers:
        steps.append(
            f"{name} is registered outside this account. Wherever its DNS is managed,"
            f" make sure {name} points at the site, then continue."
        )
    elif conn.zone is None:
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


# How long `sync` waits for a certificate with the proxy switched off, how
# long it gives one request before asking again, and how often it looks.
CERT_WAIT = 900
CERT_ROUND = 180
CERT_POLL = 15


def apply(
    conn: Connection,
    plan: Plan,
    host: Host,
    sleep: Callable[[float], None] | None = None,
) -> list[str]:
    """Carry out a plan's changes, in order.

    Args:
        conn: What was read for the hostname
        plan: What `compare` made of it
        host: The host serving the site
        sleep: Waits between looks at a certificate (default: time.sleep)

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
            _set_domain_again(conn, host)
        elif change.action == "renew_behind_proxy":
            _renew_behind_proxy(conn, plan, host, sleep or time.sleep)
        done.append(change.summary)
    return done


def _set_domain_again(conn: Connection, host: Host) -> None:
    """Remove the site's custom domain and set it again, which requests a certificate."""
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


def _renew_behind_proxy(
    conn: Connection, plan: Plan, host: Host, sleep: Callable[[float], None]
) -> None:
    """Get a certificate issued for a site whose records are proxied (DEC-050).

    Switches the proxied records to DNS-only, asks for the certificate,
    waits for it, and switches the records back. If anything fails
    along the way the records are switched back before the error is
    raised. If the certificate does not arrive in time the records are
    left DNS-only, because switching them back would block it again;
    the error says so and what to do.
    """
    assert conn.dns is not None and conn.zone is not None and conn.site is not None
    assert conn.state is not None
    name = conn.hostname
    records = plan.proxied_records
    which = _names(records)

    def _proxy(on: bool) -> None:
        assert conn.dns is not None and conn.zone is not None
        for record in records:
            conn.dns.set_proxied(conn.zone, record, on)

    _proxy(False)
    logger.info("%s: switched %s to DNS-only", name, which)
    try:
        approved = _wait_for_certificate(conn, host, sleep)
    except Exception:
        _proxy(True)
        raise
    if not approved:
        raise HostError(
            f"The certificate for {name} was not issued within {CERT_WAIT // 60} minutes."
            f" {which} were left DNS-only so that it still can be. Run: mimeo status"
            f" {name} until SITE says ok or fixable. Then, in the"
            f" {conn.dns.name.capitalize()} dashboard, open {conn.zone} > DNS > Records"
            f" and switch {which} back to Proxied."
        )
    _proxy(True)
    logger.info("%s: certificate issued; switched %s back to proxied", name, which)
    if not conn.state.https_enforced:
        host.enforce_https(conn.site)


def _wait_for_certificate(conn: Connection, host: Host, sleep: Callable[[float], None]) -> bool:
    """Ask for the certificate and wait, asking again when a request fails or stalls.

    The first request can fail because the host's resolver still holds
    the proxy's addresses, so one request is not the end of it.

    Returns:
        True when the certificate was approved within CERT_WAIT seconds
    """
    assert conn.site is not None
    waited = 0
    while waited < CERT_WAIT:
        _set_domain_again(conn, host)
        logger.info("%s: asked for the certificate; waiting", conn.hostname)
        this_round = 0
        while this_round < CERT_ROUND and waited < CERT_WAIT:
            sleep(CERT_POLL)
            waited += CERT_POLL
            this_round += CERT_POLL
            cert = host.state(conn.site).cert_state
            if cert == "approved":
                return True
            if cert is not None and cert not in PENDING_CERT_STATES:
                # The request failed. Give resolvers a minute before the next one.
                sleep(60)
                waited += 60
                break
    return False
