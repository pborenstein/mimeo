# List Command Reference

Quick reference for `mimeo list` (GitHub-managed sites) and `mimeo registrar list` (all Porkbun account domains).

## Basic Usage

```bash
# Default text format (human-readable)
mimeo list

# JSON format
mimeo list --format json

# CSV format
mimeo list --format csv
```

## Output Formats

### Text Format (Default)

Human-readable output with colors and formatting:

```
Mimeo-managed sites (63):

  • example.com
    Repository: https://github.com/user/example.com
    Site: https://example.com
    Updated: 2026-02-15
```

### JSON Format

Structured JSON array for programmatic processing:

```json
[
  {
    "name": "example.com",
    "repository": "https://github.com/user/example.com",
    "site": "https://example.com",
    "updated": "2026-02-15"
  }
]
```

### CSV Format

Comma-separated values with headers:

```csv
name,repository,site,updated
example.com,https://github.com/user/example.com,https://example.com,2026-02-15
```

## Common Use Cases

### Extract Domain Names Only

```bash
mimeo list --format csv | tail -n +2 | cut -d, -f1
```

Output:
```
example.com
test.com
site.org
```

### Extract Site URLs Only

```bash
mimeo list --format json | jq -r '.[].site'
```

Output:
```
https://example.com
https://test.com
https://site.org
```

### Extract Repository URLs Only

```bash
mimeo list --format csv | tail -n +2 | cut -d, -f2
```

Output:
```
https://github.com/user/example.com
https://github.com/user/test.com
https://github.com/user/site.org
```

### Count Total Sites

```bash
mimeo list --format json | jq 'length'
```

Output:
```
63
```

### Filter by Update Date

```bash
# Sites updated on a specific date
mimeo list --format json | jq -r '.[] | select(.updated == "2026-02-15") | .name'

# Sites updated after a date
mimeo list --format json | jq -r '.[] | select(.updated >= "2026-02-01") | .name'
```

### Get Recently Updated Sites with URLs

```bash
mimeo list --format json | jq -r '.[] | select(.updated >= "2026-02-01") | "\(.name): \(.site)"'
```

Output:
```
example.com: https://example.com
test.com: https://test.com
```

### Export to File

```bash
# Export as CSV
mimeo list --format csv > sites.csv

# Export as JSON
mimeo list --format json > sites.json

# Create simple domain list
mimeo list --format csv | tail -n +2 | cut -d, -f1 > domains.txt
```

### Process in Scripts

```bash
#!/bin/bash

# Iterate over all domains
mimeo list --format csv | tail -n +2 | while IFS=, read -r name repo site updated; do
  echo "Processing $name..."
  echo "  Site: $site"
  echo "  Last updated: $updated"
done
```

### Combine with Other Tools

```bash
# Count sites by TLD
mimeo list --format csv | tail -n +2 | cut -d, -f1 | sed 's/.*\.//' | sort | uniq -c | sort -rn

# Find sites not updated recently
mimeo list --format json | jq -r '.[] | select(.updated < "2026-02-01") | .name'

# Create markdown list
mimeo list --format json | jq -r '.[] | "- [\(.name)](\(.site))"'
```

## Column Reference

### CSV Columns

1. `name` - Domain name (e.g., "example.com")
2. `repository` - GitHub repository URL
3. `site` - Live site URL
4. `updated` - Last update date (YYYY-MM-DD format)

### JSON Fields

- `name` - Domain name
- `repository` - GitHub repository URL
- `site` - Live site URL
- `updated` - Last update date (YYYY-MM-DD format)

## Tips

1. **Use CSV for simple field extraction**: Easy to parse with standard Unix tools like `cut`, `awk`
2. **Use JSON for complex filtering**: Leverage `jq` for powerful queries and transformations
3. **Use text for quick inspection**: Best for manual review and human readability
4. **Skip headers in CSV**: Use `tail -n +2` to skip the header row when extracting data
5. **Quote-safe processing**: The CSV output properly handles domains and URLs without special characters

## Examples with jq

### Pretty print specific fields

```bash
mimeo list --format json | jq '.[] | {name, site}'
```

### Create custom CSV

```bash
mimeo list --format json | jq -r '.[] | [.name, .updated] | @csv'
```

### Group by date

```bash
mimeo list --format json | jq 'group_by(.updated) | map({date: .[0].updated, count: length})'
```

### Sort by name

```bash
mimeo list --format json | jq 'sort_by(.name)'
```

### Find specific domain

```bash
mimeo list --format json | jq '.[] | select(.name == "example.com")'
```

---

## `mimeo registrar list`

Lists all domains in the Porkbun account — not filtered by mimeo management. Useful for auditing the full account inventory and checking nameserver configuration.

### Basic Usage

```bash
# Default text table
mimeo registrar list

# JSON output
mimeo registrar list --format json

# CSV output
mimeo registrar list --format csv

# Include DNS records per domain (doubles API calls)
mimeo registrar list --with-dns

# Adjust concurrent workers (default 5)
mimeo registrar list --workers 10
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `domain` | string | Domain name |
| `tld` | string | TLD only (e.g. `com`) |
| `expires` | string | Expiry date (YYYY-MM-DD) |
| `auto_renew` | bool | Whether auto-renew is enabled |
| `ns_ok` | bool | Whether NS records point to Porkbun |
| `nameservers` | list/string | Current NS records (pipe-delimited in CSV) |
| `dns_records` | list/string | DNS records (only with `--with-dns`; pipe-delimited in CSV) |

### JSON Format

```json
[
  {
    "domain": "example.com",
    "tld": "com",
    "expires": "2027-01-15",
    "auto_renew": true,
    "ns_ok": true,
    "nameservers": ["curitiba.ns.porkbun.com", "fortaleza.ns.porkbun.com"],
    "dns_records": []
  }
]
```

### CSV Format

```csv
domain,tld,expires,auto_renew,ns_ok,nameservers
example.com,com,2027-01-15,True,True,curitiba.ns.porkbun.com|fortaleza.ns.porkbun.com
```

With `--with-dns`:

```csv
domain,tld,expires,auto_renew,ns_ok,nameservers,dns_records
example.com,com,2027-01-15,True,True,curitiba.ns.porkbun.com|fortaleza.ns.porkbun.com,A:@=185.199.108.153|CNAME:www=user.github.io
```

### Common Use Cases

```bash
# Find domains not pointing to Porkbun
mimeo registrar list --format json | jq '.[] | select(.ns_ok == false) | .domain'

# List expiring within 90 days (requires date math)
mimeo registrar list --format json | jq --arg cutoff "$(date -v+90d +%Y-%m-%d)" \
  '.[] | select(.expires <= $cutoff) | {domain, expires}'

# Extract all domain names
mimeo registrar list --format csv | tail -n +2 | cut -d, -f1

# Export full inventory
mimeo registrar list --format csv --with-dns > inventory.csv

# Count domains by TLD
mimeo registrar list --format json | jq 'group_by(.tld) | map({tld: .[0].tld, count: length})'
```
