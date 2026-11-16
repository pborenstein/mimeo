"""Compare what was read about a hostname with what its site needs.

`compare` turns a Connection into a Plan: the list of changes that would
make the DNS records and host settings right, plus the problems no
change can fix. `status` prints a Plan and `sync` applies it, so the two
cannot disagree about what is wrong.
"""

from dataclasses import dataclass, field, replace
from datetime import date

from mimeo.connection import Connection
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
    action: str  # "add_record", "delete_record", "enforce_https"
    summary: str
    record: DNSRecord | None = None


@dataclass
class Plan:
    """The result of comparing a Connection with what its site needs."""

    changes: list[Change] = field(default_factory=list)
    # Things that are wrong and that no change here fixes.
    problems: list[str] = field(default_factory=list)
    # ok, missing, extra, external, unknown; None when there is nothing to compare.
    records: str | None = None
    # ok, fixable, pending, no cert, cert error, expiring, no pages; None with no site.
    site: str | None = None
    missing: list[DNSRecord] = field(default_factory=list)
    extra: list[DNSRecord] = field(default_factory=list)
    # True when any of the site's records is proxied; None when the
    # provider has no such setting or nothing was compared.
    proxied: bool | None = None

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
        plan.problems.append("the registrar reports no nameservers")

    if conn.site is None or conn.state is None:
        return plan

    _compare_records(conn, host, plan)
    _compare_site(conn, plan, today)
    return plan


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

    plan.extra = [r for r in live if r.key() not in required_keys]
    plan.missing = [r for r in required if r.key() not in live_keys]

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
    if not state.configured:
        plan.site = "no pages"
        plan.problems.append("Pages is not enabled on the repository")
        return

    cert = state.cert_state
    if cert == "approved":
        days = _days_until(state.cert_expires, today)
        if days is not None and days <= CERT_EXPIRY_WARNING_DAYS:
            plan.site = "expiring"
            plan.problems.append(
                f"certificate expires {state.cert_expires} and has not been renewed"
            )
        elif not state.https_enforced:
            plan.site = "fixable"
            plan.changes.append(Change("host", "enforce_https", "enforce HTTPS"))
        else:
            plan.site = "ok"
    elif cert in PENDING_CERT_STATES:
        plan.site = "pending"
        plan.problems.append("certificate is still being issued")
    elif cert is None:
        plan.site = "no cert"
        plan.problems.append("no certificate has been requested")
    else:
        plan.site = "cert error"
        expires = f", expires {state.cert_expires}" if state.cert_expires else ""
        plan.problems.append(f"certificate state is {cert}{expires}")


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
        done.append(change.summary)
    return done
