# Mimeo Scripts

Utility scripts for Mimeo development and domain management.

## fetch_porkbun_domains.py

Fetch domain information from Porkbun API and export to CSV.

This utility uses the Porkbun API to quickly retrieve all domains and their DNS records, avoiding the multi-hour web export process.

### Usage

Basic usage (domain info + nameservers only):

```bash
uv run scripts/fetch_porkbun_domains.py
```

With DNS records (slower but more complete):

```bash
uv run scripts/fetch_porkbun_domains.py --with-dns
```

Custom output file:

```bash
uv run scripts/fetch_porkbun_domains.py --output my-domains.csv
```

### Output Format

The CSV includes:

- DOMAIN: Domain name
- TLD: Top-level domain
- CREATE DATE: Domain creation date
- EXPIRE DATE: Domain expiration date
- LOCKED: Domain lock status (yes/no)
- PRIVACY: WHOIS privacy status (yes/no)
- AUTO RENEW: Auto-renewal status (yes/no)
- NAMESERVERS: Nameserver list (pipe-separated)
- DNS_RECORDS: DNS records in format `TYPE:NAME=CONTENT` (pipe-separated, only with --with-dns)

### Performance

- Without DNS records: ~1 second per domain (76 domains in ~76 seconds)
- With DNS records: ~1.5 seconds per domain (76 domains in ~2 minutes)

Much faster than the web export which takes several hours.

### Requirements

- Mimeo configuration file with Porkbun credentials at `~/.config/mimeo/config.toml`
- Or environment variables: `MIMEO_PORKBUN_API_KEY` and `MIMEO_PORKBUN_SECRET`
