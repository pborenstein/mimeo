#!/usr/bin/env python3
"""Quick smoke test for Porkbun API integration."""

import os
import tomllib
from pathlib import Path

from mimeo.providers.registrar.porkbun import PorkbunRegistrar


def main() -> None:
    """Run smoke test."""
    print("Loading configuration...")
    config_path = Path.home() / ".config" / "mimeo" / "config.toml"

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    porkbun = data.get("porkbun", {})
    api_key = porkbun.get("api_key", "")
    secret_key = porkbun.get("secret_key", "")

    if not api_key or not secret_key:
        print("Error: Porkbun credentials not found in config file")
        return

    print(f"API Key: {api_key[:10]}... (truncated)")
    print(f"Secret Key: {secret_key[:10]}... (truncated)")

    print("\nInitializing Porkbun registrar...")
    registrar = PorkbunRegistrar(
        api_key=api_key,
        secret_key=secret_key,
    )

    # Test with a domain you own - let's ask which one to test
    print("\nWhich domain would you like to test with?")
    print("(This will only READ existing DNS records, not modify anything)")
    domain = input("Domain name: ").strip()

    if not domain:
        print("No domain provided, exiting.")
        return

    print(f"\nFetching DNS records for {domain}...")
    try:
        records = registrar._get_domain_records(domain)
        print(f"✓ Successfully retrieved {len(records)} DNS records")

        if records:
            print("\nExisting records:")
            for record in records[:5]:  # Show first 5 records
                print(f"  - {record.get('type'):6} {record.get('name'):20} -> {record.get('content')}")
            if len(records) > 5:
                print(f"  ... and {len(records) - 5} more records")
    except Exception as e:
        print(f"✗ Error: {e}")
        return

    print("\n✓ Smoke test passed! Porkbun API integration is working.")
    registrar.close()


if __name__ == "__main__":
    main()
