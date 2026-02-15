#!/usr/bin/env python3
"""Fetch domain information from Porkbun API and export to CSV.

This utility uses the Porkbun API to fetch all domains and their DNS records,
then exports them to a CSV file similar to the web export format.

Usage:
    uv run scripts/fetch_porkbun_domains.py [--output FILE]
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path to import mimeo modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mimeo.config import Config
from mimeo.utils.http import HTTPClient


PORKBUN_API_BASE = "https://api-ipv4.porkbun.com/api/json/v3"


def get_credentials() -> tuple[str, str]:
    """Load Porkbun credentials from mimeo config.

    Returns:
        Tuple of (api_key, secret_key)

    Raises:
        SystemExit: If credentials are not found
    """
    try:
        config = Config.load()
        api_key = config.porkbun_api_key
        secret_key = config.porkbun_secret

        if not api_key or not secret_key:
            print("Error: Porkbun credentials not found in config", file=sys.stderr)
            print("Please set PORKBUN_API_KEY and PORKBUN_SECRET_KEY", file=sys.stderr)
            sys.exit(1)

        return api_key, secret_key
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


def list_all_domains(api_key: str, secret_key: str) -> List[Dict[str, Any]]:
    """Fetch all domains from Porkbun API.

    Args:
        api_key: Porkbun API key
        secret_key: Porkbun secret key

    Returns:
        List of domain objects
    """
    client = HTTPClient(PORKBUN_API_BASE)

    try:
        response = client.post(
            "/domain/listAll",
            json={
                "apikey": api_key,
                "secretapikey": secret_key,
            }
        )

        if response.get("status") != "SUCCESS":
            error_msg = response.get("message", "Unknown error")
            print(f"Error: Porkbun API error: {error_msg}", file=sys.stderr)
            sys.exit(1)

        domains = response.get("domains", [])
        return domains
    finally:
        client.close()


def get_nameservers(domain: str, api_key: str, secret_key: str) -> List[str]:
    """Get nameservers for a domain.

    Args:
        domain: Domain name
        api_key: Porkbun API key
        secret_key: Porkbun secret key

    Returns:
        List of nameserver hostnames
    """
    client = HTTPClient(PORKBUN_API_BASE)

    try:
        response = client.post(
            f"/domain/getNs/{domain}",
            json={
                "apikey": api_key,
                "secretapikey": secret_key,
            }
        )

        if response.get("status") != "SUCCESS":
            return []

        return response.get("ns", [])
    finally:
        client.close()


def get_dns_records(domain: str, api_key: str, secret_key: str) -> List[Dict[str, Any]]:
    """Get DNS records for a domain.

    Args:
        domain: Domain name
        api_key: Porkbun API key
        secret_key: Porkbun secret key

    Returns:
        List of DNS record objects
    """
    client = HTTPClient(PORKBUN_API_BASE)

    try:
        response = client.post(
            f"/dns/retrieve/{domain}",
            json={
                "apikey": api_key,
                "secretapikey": secret_key,
            }
        )

        if response.get("status") != "SUCCESS":
            return []

        return response.get("records", [])
    finally:
        client.close()


def export_to_csv(domains: List[Dict[str, Any]], output_file: Path) -> None:
    """Export domain information to CSV.

    Args:
        domains: List of enriched domain objects
        output_file: Output CSV file path
    """
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
            # Convert boolean/int fields to yes/no
            locked = "yes" if domain_info.get("securityLock") in ("1", 1, True) else "no"
            privacy = "yes" if domain_info.get("whoisPrivacy") in ("1", 1, True) else "no"
            auto_renew = "yes" if domain_info.get("autoRenew") in ("1", 1, True) else "no"

            # Join nameservers with pipe
            nameservers = "|".join(domain_info.get("nameservers", []))

            # Format DNS records
            dns_records = []
            for record in domain_info.get("dns_records", []):
                record_type = record.get("type", "")
                name = record.get("name", "")
                content = record.get("content", "")
                dns_records.append(f"{record_type}:{name}={content}")
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
        "--output",
        "-o",
        type=Path,
        default=Path("data/porkbun-domains.csv"),
        help="Output CSV file (default: data/porkbun-domains.csv)",
    )
    parser.add_argument(
        "--with-dns",
        action="store_true",
        help="Include DNS records (slower but more complete)",
    )
    args = parser.parse_args()

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Get credentials
    api_key, secret_key = get_credentials()

    # Fetch domains
    print("Fetching domain list...")
    domains = list_all_domains(api_key, secret_key)
    print(f"Found {len(domains)} domains")

    # Enrich with nameservers and optionally DNS records
    enriched_domains = []
    for i, domain_info in enumerate(domains, 1):
        domain_name = domain_info.get("domain", "")
        print(f"[{i}/{len(domains)}] Processing {domain_name}...", end="")

        # Get nameservers
        nameservers = get_nameservers(domain_name, api_key, secret_key)
        domain_info["nameservers"] = nameservers

        # Get DNS records if requested
        if args.with_dns:
            dns_records = get_dns_records(domain_name, api_key, secret_key)
            domain_info["dns_records"] = dns_records
            print(f" {len(nameservers)} NS, {len(dns_records)} records")
        else:
            domain_info["dns_records"] = []
            print(f" {len(nameservers)} NS")

        enriched_domains.append(domain_info)

    # Export to CSV
    print(f"\nExporting to {args.output}...")
    export_to_csv(enriched_domains, args.output)
    print(f"Done! Exported {len(enriched_domains)} domains")


if __name__ == "__main__":
    main()
