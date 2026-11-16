"""The operations behind `link`, `unlink`, `delegate` and `create`.

Each takes a Fleet and returns the list of things it did (or, with
dry_run, would do) as plain sentences. They hold no vendor knowledge:
everything goes through the Registrar, DNSProvider, Host and
RepoProvider interfaces.
"""

import time
from dataclasses import dataclass, field, replace
from typing import Callable

from mimeo.connection import Connection, Fleet
from mimeo.exceptions import MimeoError
from mimeo.models import ADDRESS_TYPES, DNSRecord, Site, SiteState
from mimeo.plan import PENDING_CERT_STATES, Plan, apply, compare

# Record types that describe the provider itself; each provider
# generates its own (DEC-042).
_NOT_COPIED = frozenset({"NS", "SOA"})


class OperationError(MimeoError):
    """Raised when an operation refuses to proceed. The message says why."""


@dataclass
class Outcome:
    """What an operation did, as sentences, plus anything worth a warning."""

    actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Set by link: True when HTTPS could not be enforced yet.
    https_pending: bool = False


def link(
    fleet: Fleet,
    hostname: str,
    site: Site,
    dry_run: bool = False,
    wait: int = 0,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    """Connect a hostname to a site.

    Sets the host's custom domain, writes the records the host asks for
    at whichever provider serves the zone, and enforces HTTPS once a
    certificate exists.

    Args:
        fleet: The providers
        hostname: The hostname to serve the site at
        site: The site to serve
        dry_run: Describe the changes without making them
        wait: Seconds to wait for the certificate before giving up on
            enforcing HTTPS (0: do not wait)
        sleep: Called between certificate checks (replaced in tests)

    Raises:
        OperationError: If another site already serves the hostname, or
            the site is at a host mimeo does not have
    """
    hostname = hostname.lower()
    if site.host != fleet.host.name:
        raise OperationError(f"No host named {site.host!r} is available (only {fleet.host.name})")

    current, _ = fleet.site_for(hostname)
    if current is not None and current != site:
        raise OperationError(
            f"{hostname} is already linked to {current}; run 'mimeo unlink {hostname}' first"
        )

    outcome = Outcome()
    would = "would " if dry_run else ""

    if current is None:
        outcome.actions.append(f"{would}set the custom domain of {site} to {hostname}")
        if not dry_run:
            fleet.host.set_custom_domain(site, hostname)
            fleet.cache.set(hostname, site)

    conn = fleet.read(hostname)
    if dry_run and conn.site is None:
        # Compare as though the custom domain were already set.
        conn.site = site
        conn.state = SiteState(configured=True, custom_domain=hostname)
    plan = compare(conn, fleet.host)

    _note_unwritable_dns(conn, fleet, site, outcome)

    if dry_run:
        outcome.actions += [f"would {c.summary}" for c in plan.changes]
        return outcome

    outcome.actions += apply(conn, plan, fleet.host)
    if conn.zone is not None:
        fleet.forget(conn.zone)

    outcome.https_pending = _finish_https(fleet, site, plan, outcome, wait, sleep)
    return outcome


def _note_unwritable_dns(conn: Connection, fleet: Fleet, site: Site, outcome: Outcome) -> None:
    """Say which records to create by hand when mimeo cannot write them."""
    if conn.zone is not None and conn.dns is not None:
        return
    if conn.zone is None:
        reason = f"no domain at the registrar covers {conn.hostname}"
    elif conn.nameservers:
        reason = f"{conn.zone} is served by {', '.join(conn.nameservers)}, not a configured DNS provider"
    else:
        reason = f"the registrar reports no nameservers for {conn.zone}"
    outcome.notes.append(f"DNS records not written: {reason}. The site needs:")
    for record in fleet.host.required_records(site, conn.label):
        outcome.notes.append(f"  {record.describe()}")


def _finish_https(
    fleet: Fleet,
    site: Site,
    plan: Plan,
    outcome: Outcome,
    wait: int,
    sleep: Callable[[float], None],
) -> bool:
    """Enforce HTTPS if the certificate arrives within `wait` seconds.

    Returns:
        True when HTTPS is still not enforced
    """
    state = fleet.host.state(site)
    if state.https_enforced:
        return False
    waited = 0
    while state.cert_state != "approved" and waited < wait:
        if state.cert_state is not None and state.cert_state not in PENDING_CERT_STATES:
            break
        sleep(20)
        waited += 20
        state = fleet.host.state(site)
    if state.cert_state == "approved" and fleet.host.enforce_https(site):
        if "enforce HTTPS" not in outcome.actions:
            outcome.actions.append("enforce HTTPS")
        return False
    outcome.notes.append(
        f"HTTPS is not enforced yet (certificate: {state.cert_state or 'not requested'}). "
        f"Run 'mimeo sync' for this hostname once the certificate is issued."
    )
    return True


def unlink(fleet: Fleet, hostname: str, dry_run: bool = False) -> tuple[Outcome, Site]:
    """Disconnect a hostname from its site.

    Removes the address records at the site's names and the host's
    custom-domain setting. The repository is not touched.

    Returns:
        The outcome, and the site that was unlinked

    Raises:
        OperationError: If no site serves the hostname
    """
    hostname = hostname.lower()
    conn = fleet.read(hostname)
    if conn.site is None:
        raise OperationError(f"No site is linked to {hostname}")

    outcome = Outcome()
    would = "would " if dry_run else ""

    if conn.zone is not None and conn.dns is not None and conn.records is not None:
        names = {r.name for r in fleet.host.required_records(conn.site, conn.label)}
        for record in conn.records:
            if record.name in names and record.type in ADDRESS_TYPES:
                if not dry_run:
                    conn.dns.delete_record(conn.zone, record)
                outcome.actions.append(f"{would}remove {record.describe()}")
        if not dry_run:
            fleet.forget(conn.zone)
    elif conn.zone is not None:
        outcome.notes.append(
            f"DNS records not removed: {conn.zone} is not served by a configured DNS provider"
        )

    outcome.actions.append(f"{would}remove the custom domain from {conn.site}")
    if not dry_run:
        fleet.host.set_custom_domain(conn.site, None)
        fleet.cache.remove(hostname)
    return outcome, conn.site


def delegate(
    fleet: Fleet,
    zone: str,
    provider_name: str,
    dry_run: bool = False,
    empty: bool = False,
) -> Outcome:
    """Move a zone to another DNS provider (DEC-042).

    Copies every record except NS and SOA from the provider serving the
    zone now, reads them back to confirm, and only then sets the
    nameservers at the registrar. The old zone's records stay in place.

    Args:
        fleet: The providers
        zone: A domain at the registrar
        provider_name: The DNS provider to move the zone to
        dry_run: Describe the changes without making them
        empty: Change nameservers even though the current records
            cannot be read (the new zone starts empty)

    Raises:
        OperationError: If the zone is not at the registrar, the provider
            is not configured, DNSSEC is on, the current records cannot
            be read (without `empty`), or the copy does not verify
    """
    zone = zone.lower()
    if zone not in fleet.registered:
        parent = fleet.zone_for(zone)
        if parent is not None:
            raise OperationError(
                f"{zone} is a name inside {parent}; delegate moves whole zones "
                f"(mimeo delegate {parent} --dns {provider_name})"
            )
        raise OperationError(f"{zone} is not registered at the registrar")

    target = fleet.provider_named(provider_name)
    if target is None:
        configured = ", ".join(p.name for p in fleet.dns_providers)
        raise OperationError(
            f"DNS provider {provider_name!r} is not configured (configured: {configured})"
        )

    nameservers = fleet.nameservers(zone)
    current = fleet.provider_for(nameservers)
    outcome = Outcome()
    if current is target:
        outcome.notes.append(f"{zone} is already served by {target.name}")
        return outcome

    if fleet.registrar.dnssec_enabled(zone):
        raise OperationError(
            f"DNSSEC is enabled for {zone}. The registry's DS records point at the "
            f"current provider's keys, so changing nameservers would stop the domain "
            f"resolving. Turn DNSSEC off at the registrar first."
        )

    would = "would " if dry_run else ""
    source: list[DNSRecord] = []
    if current is not None:
        source = [r for r in current.list_records(zone) if r.type not in _NOT_COPIED]
    elif not empty:
        served_by = ", ".join(nameservers) or "no nameservers"
        raise OperationError(
            f"{zone} is served by {served_by}, which mimeo cannot read, so there is "
            f"nothing to copy. Pass --empty to move it with no records."
        )

    copyable = [r for r in source if r.type not in target.unsupported_types]
    for record in source:
        if record.type in target.unsupported_types:
            outcome.notes.append(f"not copied ({target.name} has no {record.type} type): {record.describe()}")

    if dry_run:
        if not target.zone_exists(zone):
            outcome.actions.append(f"would create zone {zone} at {target.name}")
        outcome.actions += [f"would copy {r.describe()}" for r in copyable]
        outcome.actions.append(f"would set the nameservers of {zone} to {target.name}'s")
        return outcome

    if not target.zone_exists(zone):
        target.create_zone(zone)
        outcome.actions.append(f"create zone {zone} at {target.name}")

    already = {r.key() for r in target.list_records(zone)}
    for record in copyable:
        if record.key() in already:
            continue
        # Copies are written DNS-only; the old provider's IDs mean nothing here.
        target.add_record(zone, replace(record, id=None, proxied=None))
        already.add(record.key())
        outcome.actions.append(f"copy {record.describe()}")

    present = {r.key() for r in target.list_records(zone)}
    lost = [r for r in copyable if r.key() not in present]
    if lost:
        listing = "; ".join(r.describe() for r in lost)
        raise OperationError(
            f"{len(lost)} record(s) did not arrive at {target.name}, so the nameservers "
            f"were not changed: {listing}"
        )

    new_nameservers = target.zone_nameservers(zone)
    fleet.registrar.set_nameservers(zone, new_nameservers)
    fleet.forget(zone)
    outcome.actions.append(f"{would}set nameservers to {', '.join(new_nameservers)}")
    outcome.notes.append(
        f"The records at {current.name if current else 'the old provider'} were left in place. "
        f"The change takes effect as resolvers pick up the new nameservers."
    )
    return outcome
