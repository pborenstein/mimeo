#!/usr/bin/env python3
"""Fetch domain information from Porkbun API and export to CSV.

This utility uses the Porkbun API to fetch all domains and their DNS records,
then exports them to a CSV file similar to the web export format.

Usage:
    uv run scripts/fetch_porkbun_domains.py [--output FILE] [--workers N] [--with-dns]
"""

import argparse
import csv
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path to import mimeo modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mimeo.config import Config
from mimeo.utils.http import HTTPClient
from mimeo.utils.retry import retry_with_jitter


PORKBUN_API_BASE = "https://api-ipv4.porkbun.com/api/json/v3"

_print_lock = threading.Lock()


def safe_print(msg: str) -> None:
    with _print_lock:
        print(msg)


def get_credentials() -> tuple[str, str]:
    """Load Porkbun credentials from mimeo config."""
    try:
        config = Config.load()
        api_key = config.porkbun_api_key
        secret_key = config.porkbun_secret

        if not api_key or not secret_key:
            print("Error: Porkbun credentials not found in config", file=sys.stderr)
            sys.exit(1)

        return api_key, secret_key
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


def list_all_domains(api_key: str, secret_key: str) -> List[Dict[str, Any]]:
    """Fetch all domains from Porkbun API."""
    client = HTTPClient(PORKBUN_API_BASE)
    try:
        response = client.post(
            "/domain/listAll",
            json={"apikey": api_key, "secretapikey": secret_key},
        )
        if response.get("status") != "SUCCESS":
            print(f"Error: Porkbun API error: {response.get('message', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)
        return response.get("domains", [])
    finally:
        client.close()


def get_nameservers(domain: str, api_key: str, secret_key: str) -> List[str]:
    """Get nameservers for a domain."""
    client = HTTPClient(PORKBUN_API_BASE)
    try:
        response = retry_with_jitter(
            lambda: client.post(
                f"/domain/getNs/{domain}",
                json={"apikey": api_key, "secretapikey": secret_key},
            )
        )
        if response.get("status") != "SUCCESS":
            return []
        return response.get("ns", [])
    finally:
        client.close()


def get_dns_records(domain: str, api_key: str, secret_key: str) -> List[Dict[str, Any]]:
    """Get DNS records for a domain."""
    client = HTTPClient(PORKBUN_API_BASE)
    try:
        response = retry_with_jitter(
            lambda: client.post(
                f"/dns/retrieve/{domain}",
                json={"apikey": api_key, "secretapikey": secret_key},
            )
        )
        if response.get("status") != "SUCCESS":
            return []
        return response.get("records", [])
    finally:
        client.close()


def enrich_domain(
    domain_info: Dict[str, Any],
    api_key: str,
    secret_key: str,
    with_dns: bool,
    index: int,
    total: int,
) -> Dict[str, Any]:
    """Fetch NS (and optionally DNS records) for a single domain."""
    domain_name = domain_info.get("domain", "")

    nameservers = get_nameservers(domain_name, api_key, secret_key)
    domain_info["nameservers"] = nameservers

    if with_dns:
        dns_records = get_dns_records(domain_name, api_key, secret_key)
        domain_info["dns_records"] = dns_records
        safe_print(f"[{index}/{total}] {domain_name}: {len(nameservers)} NS, {len(dns_records)} records")
    else:
        domain_info["dns_records"] = []
        safe_print(f"[{index}/{total}] {domain_name}: {len(nameservers)} NS")

    return domain_info


def export_to_csv(domains: List[Dict[str, Any]], output_file: Path) -> None:
    """Export domain information to CSV."""
    fieldnames = [
        "DOMAIN",
        "TLD",
        "CREATE DATE",
        "EXPIRE DATE",
        "LOCKED",
        "PRIVACY",
        "AUTO RENEW",
        "NAMESERVERS",
        "DNS_RECORDS",
    ]

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for domain_info in domains:
            locked = "yes" if domain_info.get("securityLock") in ("1", 1, True) else "no"
            privacy = "yes" if domain_info.get("whoisPrivacy") in ("1", 1, True) else "no"
            auto_renew = "yes" if domain_info.get("autoRenew") in ("1", 1, True) else "no"

            nameservers = "|".join(domain_info.get("nameservers", []))

            dns_records = []
            for record in domain_info.get("dns_records", []):
                dns_records.append(f"{record.get('type', '')}:{record.get('name', '')}={record.get('content', '')}")
            dns_records_str = "|".join(dns_records) if dns_records else ""

            writer.writerow({
                "DOMAIN": domain_info.get("domain", ""),
                "TLD": domain_info.get("tld", ""),
                "CREATE DATE": domain_info.get("createDate", ""),
                "EXPIRE DATE": domain_info.get("expireDate", ""),
                "LOCKED": locked,
                "PRIVACY": privacy,
                "AUTO RENEW": auto_renew,
                "NAMESERVERS": nameservers,
                "DNS_RECORDS": dns_records_str,
            })


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch Porkbun domain information and export to CSV"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/porkbun-domains.csv"),
        help="Output CSV file (default: data/porkbun-domains.csv)",
    )
    parser.add_argument(
        "--with-dns",
        action="store_true",
        help="Include DNS records (more complete but doubles API calls per domain)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=5,
        help="Number of concurrent workers (default: 5)",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    api_key, secret_key = get_credentials()

    print("Fetching domain list...")
    domains = list_all_domains(api_key, secret_key)
    total = len(domains)
    print(f"Found {total} domains — enriching with {args.workers} workers...")

    # Assign stable indices before concurrent processing
    indexed = list(enumerate(domains, 1))

    enriched: Dict[int, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(enrich_domain, info, api_key, secret_key, args.with_dns, i, total): i
            for i, info in indexed
        }
        for future in as_completed(futures):
            i = futures[future]
            enriched[i] = future.result()

    # Restore original order
    ordered = [enriched[i] for i in range(1, total + 1)]

    print(f"\nExporting to {args.output}...")
    export_to_csv(ordered, args.output)
    print(f"Done! Exported {len(ordered)} domains")


if __name__ == "__main__":
    main()
