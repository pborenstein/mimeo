#!/usr/bin/env bash
# End-to-end smoke test against a live junk domain.
#
# Moves the domain's zone to the other DNS provider and back, checking
# after each step that mimeo reads it as healthy. Writes to Porkbun,
# Cloudflare and nothing else; the GitHub repository is only read.
# Not run by pytest. Run it by hand when the fleet has gone quiet:
#
#   scripts/e2e_smoke.sh 002370.xyz
#
# The domain must be registered at Porkbun, have a site, read `ok` in
# `mimeo status`, have no MX records and no proxied records, and be
# a domain nobody minds breaking for a few minutes.

set -euo pipefail

domain="${1:?usage: scripts/e2e_smoke.sh DOMAIN}"
mimeo=(uv run mimeo)
step=0

say() { printf '\n== %s\n' "$*"; }
fail() { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }

# Print one field of the domain's status row.
field() {
  "${mimeo[@]}" status "$domain" --format json | jq -r ".[0].$1"
}

# Require dns, records and site to read as expected.
expect() {
  local want_dns="$1" dns records site
  step=$((step + 1))
  dns="$(field dns)"
  records="$(field records)"
  site="$(field site_status)"
  printf '   dns=%s records=%s site=%s\n' "$dns" "$records" "$site"
  [[ "$dns" == "$want_dns" ]] || fail "check $step: dns is $dns, wanted $want_dns"
  [[ "$records" == "ok" ]] || fail "check $step: records is $records, wanted ok"
  [[ "$site" == "ok" ]] || fail "check $step: site is $site, wanted ok"
}

say "doctor"
"${mimeo[@]}" doctor "$domain"

say "starting state"
start="$(field dns)"
case "$start" in
  porkbun) other=cloudflare ;;
  cloudflare) other=porkbun ;;
  *) fail "$domain is served by '$start'; it must be porkbun or cloudflare" ;;
esac
expect "$start"

say "sync --dry-run plans nothing"
plan="$("${mimeo[@]}" sync "$domain" --dry-run)"
printf '%s\n' "$plan"
grep -q "0 would change" <<<"$plan" || fail "sync --dry-run planned changes on a healthy site"

say "delegate to $other (dry run, then for real)"
"${mimeo[@]}" delegate "$domain" --dns "$other" --dry-run
"${mimeo[@]}" delegate "$domain" --dns "$other"
expect "$other"

say "delegate back to $start"
"${mimeo[@]}" delegate "$domain" --dns "$start"
expect "$start"

say "public DNS (may lag behind the registrar; informational only)"
dig +short NS "$domain" || true

printf '\nPASS: %s moved %s -> %s -> %s and read ok at each step\n' "$domain" "$start" "$other" "$start"
