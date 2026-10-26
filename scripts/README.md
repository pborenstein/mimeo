# Mimeo Scripts

Utility and smoke test scripts for Mimeo development and domain management.

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

## smoke_test_porkbun.py

Interactive smoke test for the Porkbun API integration. Reads credentials from config, prompts for a domain, and fetches DNS records to verify the connection is working.

### Usage

```bash
uv run scripts/smoke_test_porkbun.py
```

### Requirements

- Mimeo configuration file with Porkbun credentials at `~/.config/mimeo/config.toml`

## smoke_test_github.py

Interactive smoke test for the GitHub Pages integration. Creates a temporary repository, deploys a test page, verifies Pages configuration, and optionally cleans up.

### Usage

```bash
uv run scripts/smoke_test_github.py
```

### Requirements

- `gh` CLI installed and authenticated

## Porkbun JSON exports

Two JSON snapshots of the Porkbun domain account, dated 2026-10-26. They are a different format from the CSV that `fetch_porkbun_domains.py` writes.

- `porkbun-no-dns.2026.10.26.json`: 105 domains, `dns_records` empty on every entry
- `porkbun+dns.2026.10.26.json`: same domains, `dns_records` populated

Each entry has this shape:

```json
{
  "domain": "example.com",
  "tld": "com",
  "expires": "2027-01-04 22:25:52",
  "auto_renew": true,
  "nameservers": ["curitiba.porkbun.com", "fortaleza.porkbun.com"],
  "ns_ok": true,
  "dns_records": [
    {"id": "...", "name": "www.example.com", "type": "CNAME",
     "content": "example.github.io", "ttl": "600", "prio": "0", "notes": ""}
  ],
  "error": null
}
```

- `ns_ok` is `false` when the nameservers are not Porkbun's (the export shows `dns*.p0N.nsone.net` in those cases)
- `auto_renew: false` marks domains that will not renew
- The CNAME targets in the DNS export are GitHub Pages hosts, `pixie.porkbun.com` / `uixie.porkbun.com`, and `pborenstein.micro.blog`

These files contain the full domain list and DNS records for the account. `.gitignore` excludes them (`scripts/porkbun*.json`), so they stay local.

### porkbun-domains.sh

Summarizes a JSON export with `jq`. By default it lists renewing domains with their `ns_ok` value.

```bash
scripts/porkbun-domains.sh scripts/porkbun+dns.2026.10.26.json        # domain + ns_ok, renewing only
scripts/porkbun-domains.sh -s scripts/porkbun+dns.2026.10.26.json     # names only
scripts/porkbun-domains.sh -n scripts/porkbun+dns.2026.10.26.json     # ns_ok false only
scripts/porkbun-domains.sh -a scripts/porkbun+dns.2026.10.26.json     # include non-renewals
scripts/porkbun-domains.sh -f expires scripts/porkbun+dns.2026.10.26.json
```

Requires `jq`.

### porkbun-query.sh

Takes a plain-English query, asks Claude (`claude --model haiku -p`) for a jq filter, checks that the filter compiles, then runs it against the export. The default file is `porkbun+dns.2026.10.26.json` next to the script.

```bash
scripts/porkbun-query.sh "domains that renew and use non-Porkbun nameservers"
scripts/porkbun-query.sh -q "domains with a CNAME to github.io"   # print filter only
scripts/porkbun-query.sh -f other.json "..."                      # different export
```

The script prints the generated filter to stderr before running it. Only the query text and a description of the record fields are sent to Claude. The JSON data stays local and is read by `jq`.

Requires `jq` and the `claude` CLI.

Known issue: the generated filter is not always valid. The script exits with "Claude returned an invalid jq filter" and prints the filter. Rerunning usually works.
