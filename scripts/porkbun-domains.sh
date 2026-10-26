#!/usr/bin/env bash
#
# Summarize a Porkbun domain export.
#
# Usage:
#   porkbun-domains.sh [-a] [-s] [-n] [-f FIELD] FILE.json
#
# By default, prints one line per domain that will renew (auto_renew is true):
#   domain    ns_ok
#
# Options:
#   -a        include domains with auto_renew false (non-renewals)
#   -s        print only domain names, one per line
#   -n        print only domains where ns_ok is false
#   -f FIELD  print one field per domain (e.g. expires, tld, nameservers)
#   -h        show this help
#
# Requires jq.

set -euo pipefail

usage() {
  sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'
}

include_non_renewals=false
names_only=false
ns_false_only=false
field=""

while getopts ":asnf:h" opt; do
  case $opt in
    a) include_non_renewals=true ;;
    s) names_only=true ;;
    n) ns_false_only=true ;;
    f) field=$OPTARG ;;
    h) usage; exit 0 ;;
    \?) echo "Unknown option: -$OPTARG" >&2; usage >&2; exit 1 ;;
    :) echo "Option -$OPTARG needs an argument" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

file=$1

if [[ ! -f $file ]]; then
  echo "File not found: $file" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required (brew install jq)" >&2
  exit 1
fi

# Build the jq filter from the options
filter='.'

if [[ $include_non_renewals == false ]]; then
  filter+=' | map(select(.auto_renew == true))'
fi

if [[ $ns_false_only == true ]]; then
  filter+=' | map(select(.ns_ok == false))'
fi

if [[ $names_only == true ]]; then
  filter+=' | .[] | .domain'
elif [[ -n $field ]]; then
  filter+=" | .[] | [.domain, (.$field | tostring)] | @tsv"
else
  filter+=' | .[] | [.domain, (.ns_ok | tostring)] | @tsv'
fi

jq -r "$filter" "$file"
