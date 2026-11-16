"""Data models for Mimeo."""

from dataclasses import dataclass

# Record types that say where a name is served from. mimeo owns these at a
# site's own names and nothing else in a zone (DEC-045).
ADDRESS_TYPES = frozenset({"A", "AAAA", "CNAME", "ALIAS"})


@dataclass
class DNSRecord:
    """A DNS record in a zone.

    `name` is relative to the zone: "" for the apex, "www", "service".
    `id`, `priority` and `proxied` are filled in on records read from a
    provider; `proxied` only by providers that have the setting.
    """

    type: str
    name: str
    content: str
    ttl: int = 600
    priority: int | None = None
    proxied: bool | None = None
    id: str | None = None

    def __post_init__(self) -> None:
        """Validate DNS record."""
        if self.ttl < 0:
            raise ValueError(f"TTL must be non-negative, got {self.ttl}")
        if not self.content:
            raise ValueError("DNS record content cannot be empty")

    def key(self) -> tuple[str, str, str]:
        """Identity used to compare records across providers.

        Type, name and content, with content lowercased and stripped of
        a trailing dot and of the quotes some providers put around TXT
        values. TTL, priority and proxy setting are not part of it.
        """
        content = self.content.strip()
        if self.type == "TXT":
            content = content.strip('"')
        else:
            content = content.rstrip(".").lower()
        name = "" if self.name == "@" else self.name.lower()
        return (self.type.upper(), name, content)

    def describe(self) -> str:
        """One-line form for output: `A @ -> 185.199.108.153`."""
        return f"{self.type} {self.name or '@'} -> {self.content}"


@dataclass(frozen=True)
class Site:
    """A site at a host, written `host:ref` (`github:owner/repo`)."""

    host: str
    ref: str

    def __str__(self) -> str:
        return f"{self.host}:{self.ref}"

    @classmethod
    def parse(cls, text: str) -> "Site":
        """Parse `host:ref`.

        Raises:
            ValueError: If the text has no host prefix or no reference
        """
        host, sep, ref = text.partition(":")
        if not sep or not host or not ref:
            raise ValueError(f"Site must be written host:reference (github:owner/repo), got {text!r}")
        return cls(host=host, ref=ref)


@dataclass
class SiteState:
    """What a host reports about a site."""

    configured: bool
    custom_domain: str | None = None
    https_enforced: bool = False
    cert_state: str | None = None
    cert_expires: str | None = None


def relative_name(fqdn: str, zone: str) -> str:
    """Turn a provider's record name into a name relative to the zone.

    Providers return the apex as "", "@" or the zone itself, and other
    names either bare ("www") or fully qualified ("www.example.com").
    """
    name = fqdn.rstrip(".").lower()
    zone = zone.lower()
    if name in ("", "@", zone):
        return ""
    if name.endswith(f".{zone}"):
        return name[: -len(zone) - 1]
    return name
