# List Command Reference

Quick reference for using `mimeo list` with different output formats.

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
