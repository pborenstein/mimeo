#!/usr/bin/env bash
#
# Turn a plain-English query into a jq filter with Claude (Haiku), then run
# that filter against a Porkbun export.
#
# Usage:
#   porkbun-query.sh [-f FILE] [-q] QUERY...
#
# Options:
#   -f FILE  Porkbun JSON export (default: porkbun+dns.2026.10.26.json
#            next to this script)
#   -q       print the generated jq filter and stop without running it
#   -h       show this help
#
# Examples:
#   porkbun-query.sh "domains that renew and use non-Porkbun nameservers"
#   porkbun-query.sh -q "domains expiring before 2027 with auto_renew off"
#
# Requires jq and the claude CLI.

set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
file="$script_dir/porkbun+dns.2026.10.26.json"
show_only=false

usage() {
  cat <<'EOF'
Usage: porkbun-query.sh [-f FILE] [-q] QUERY...

Options:
  -f FILE  Porkbun JSON export (default: porkbun+dns.2026.10.26.json
           next to this script)
  -q       print the generated jq filter and stop without running it
  -h       show this help
EOF
}

while getopts ":f:qh" opt; do
  case $opt in
    f) file=$OPTARG ;;
    q) show_only=true ;;
    h) usage; exit 0 ;;
    \?) echo "Unknown option: -$OPTARG" >&2; usage >&2; exit 1 ;;
    :) echo "Option -$OPTARG needs an argument" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 1
fi

query="$*"

if [[ ! -f $file ]]; then
  echo "File not found: $file" >&2
  exit 1
fi

for cmd in jq claude; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd is required but was not found in PATH" >&2
    exit 1
  fi
done

read -r -d '' prompt <<EOF || true
You write jq filters for a Porkbun domain export.

The input is a JSON array. Each element looks like this:

{
  "domain": "example.com",
  "tld": "com",
  "expires": "2027-01-04 22:25:52",
  "auto_renew": true,
  "nameservers": ["curitiba.ns.porkbun.com", "fortaleza.ns.porkbun.com"],
  "ns_ok": true,
  "dns_records": [
    {"id": "...", "name": "www.example.com", "type": "CNAME",
     "content": "example.github.io", "ttl": "600", "prio": "0", "notes": ""}
  ],
  "error": null
}

Notes:
- ns_ok is false when the domain uses nameservers other than Porkbun's.
- dns_records lists every record for the domain. "type" is the record type
  (A, AAAA, CNAME, ALIAS, NS, TXT, MX, and so on). "name" is the full host
  name, so a bare apex domain has name equal to the domain. "content" is the
  record value (the target for CNAME and ALIAS).

Write one jq filter that answers this request:

$query

Rules:
- The filter runs against the whole array, so start from .[] or map(...).
- Output plain values or @tsv rows, not whole objects, unless the request
  asks for whole objects.
- Output only the filter. No explanation and no code fences.
EOF

filter=$(claude --model haiku -p "$prompt")

# Strip any code fences the model added anyway
filter=$(printf '%s\n' "$filter" | sed -e '/^```/d')

if [[ -z ${filter//[[:space:]]/} ]]; then
  echo "Claude returned an empty filter" >&2
  exit 1
fi

if ! jq_err=$(printf '[]' | jq "$filter" 2>&1 >/dev/null); then
  echo "Claude returned an invalid jq filter:" >&2
  printf '%s\n' "$filter" >&2
  printf 'jq: %s\n' "$jq_err" >&2
  exit 1
fi

if [[ $show_only == true ]]; then
  printf '%s\n' "$filter"
  exit 0
fi

echo "filter: $filter" >&2
jq -r "$filter" "$file"
