# Troubleshooting

For mimeo 2.0. Start with these two commands:

```bash
mimeo doctor                  # tools, config, credentials
mimeo status example.com      # what connects the hostname to its site, and what is wrong
```

`status` states each problem in a sentence and prints the steps that fix it, or lists the change as `sync would:` when `mimeo sync` can make it. Follow what it prints. This page covers what `status` does not print: what each value in its table means, why a command refused or failed, and things that go wrong outside what mimeo reads.

- [Reading a status row](#reading-a-status-row)
- [Certificates and HTTPS](#certificates-and-https)
- [The site loads the wrong thing](#the-site-loads-the-wrong-thing)
- [A command refused](#a-command-refused)
- [mimeo cannot find a site](#mimeo-cannot-find-a-site)
- [Configuration](#configuration)
- [GitHub access](#github-access)
- [Porkbun](#porkbun)
- [Cloudflare](#cloudflare)
- [Exit codes and partial failures](#exit-codes-and-partial-failures)

## Reading a status row

```
  HOSTNAME    EXPIRES     DNS          RECORDS   SITE        REPO
  xhosi.com   2027-08-31  cloudflare*  ok        cert error  mimeo-sites/xhosi.com
```

The detail lines (`sync would:`, `problem:`, `to fix:`) appear when hostnames are named or with `--problems`. After `mimeo status --all`, run `mimeo status --all --problems` to see them for every hostname that needs attention.

### DNS

| Value | Meaning | What to do |
|:------|:--------|:-----------|
| `porkbun`, `cloudflare` | The nameservers set at the registrar belong to that provider, and mimeo reads and writes the records there | Nothing |
| trailing `*` | At least one of the site's records is proxied through Cloudflare | Nothing; a proxied record is not a problem |
| `external` | The nameservers belong to a provider mimeo is not configured for, so it cannot read the records | To let mimeo manage a Cloudflare zone, add the `[cloudflare]` section to the config (see `config.toml.example`). For any other provider, manage the records there by hand |
| `none` | The registrar reports no nameservers | `status` prints the `mimeo delegate ... --empty` command |
| `-` | The hostname is not in the Porkbun account, or the row could not be read (the error is printed at the end of the row) | See [`no domain`](#site) below, and [Porkbun](#porkbun) for read errors |

### RECORDS

| Value | Meaning | What to do |
|:------|:--------|:-----------|
| `ok` | Every address record the site needs is there, and no other address record sits at the site's names | Nothing |
| `missing` | A needed record is absent | `mimeo sync HOSTNAME` |
| `extra` | An address record at one of the site's names is not one the site needs (for example Porkbun's parking `ALIAS`) | `mimeo sync HOSTNAME` removes it |
| `external` | Not compared, because the DNS provider cannot be read | See `external` above |
| `unknown` | Not compared, because the registrar reports no nameservers | See `none` above |
| `-` | Nothing to compare: no site, or the domain is not at the registrar | |

The records a site needs are listed in the README under [Which records mimeo touches](../README.md#which-records-mimeo-touches). `mimeo status HOSTNAME --records` prints every record in the zone.

### SITE

| Value | Meaning | What to do |
|:------|:--------|:-----------|
| `ok` | Certificate approved, HTTPS enforced | Nothing |
| `fixable` | Certificate approved, HTTPS not enforced | `mimeo sync HOSTNAME` |
| `pending` | GitHub is issuing the certificate | Wait; check again within the hour |
| `no cert` | GitHub has no certificate for the hostname | `mimeo sync HOSTNAME`; see [Certificates and HTTPS](#certificates-and-https) |
| `cert error` | A certificate request or renewal failed | Same |
| `expiring` | The certificate is approved but expires within 14 days, so renewal is not happening | Same |
| `no pages` | The repository has Pages turned off | `status` prints the settings page to open |
| `no domain` | The hostname has a repository but is not in the Porkbun account, and public DNS has no nameservers for it. The registration has most likely lapsed | `status` prints four choices: `mimeo unlink`, `mimeo delete`, GitHub's transfer page, or registering the domain again |
| `no site` | A registered domain with no repository serving it. Not a problem | `mimeo create` or `mimeo link` if it should have one |

A site whose hostname is not in the Porkbun account but does answer in DNS (registered in another account or elsewhere) shows dashes for `EXPIRES`, `DNS` and `RECORDS` and is judged on its certificate alone. mimeo cannot read or fix its records.

## Certificates and HTTPS

GitHub requests a certificate for a custom domain at the moment the domain is saved in the repository's Pages settings, and issues it only if it can reach the site directly at records that point to GitHub. Renewal works the same way. Two things follow.

- **Records must be right first.** A certificate requested while the records were wrong is not requested again by GitHub.
- **Cloudflare's proxy blocks it.** A proxied record resolves to Cloudflare's addresses, not GitHub's.

`mimeo sync HOSTNAME` handles both. With the records right, it removes the custom domain and sets it again. When the records are proxied, it first switches them to DNS-only, waits for the certificate, and switches them back.

### `sync` says to run it again

```
problem: There is no HTTPS certificate for example.com, so https://example.com does not open. ...
to fix:
  1. Run: mimeo sync example.com
  2. Wait 5 minutes, then run: mimeo sync example.com again. ...
```

The records were wrong. One run fixes the records and a later run requests the certificate, because a record just written is not answered for immediately (seen on Porkbun, 2026-11-16: its own nameserver returned nothing for a new name for a few seconds). After the certificate is approved, one more `mimeo sync` enforces HTTPS. So a new site with wrong records can take three runs.

### "The certificate for example.com was not issued within 15 minutes"

`sync` switched the proxied records to DNS-only and the certificate did not arrive. The records were left DNS-only on purpose: switching them back would block the certificate again. The site keeps working; visitors reach GitHub directly.

1. Run `mimeo status example.com` every few minutes until `SITE` says `ok` or `fixable`.
2. If it says `cert error` or `no cert` instead, run `mimeo sync example.com`. The records are no longer proxied, so this is the plain request and returns at once.
3. When it says `ok` or `fixable`, open the Cloudflare dashboard, then the zone, then DNS > Records, and switch the records the error named back to Proxied.
4. If it said `fixable`, run `mimeo sync example.com` to enforce HTTPS.

### "The custom domain example.com was removed from ... and could not be set again"

`sync` removed the custom domain and the call that sets it again failed. The site is not served at the hostname until it is set. Run the command the error prints:

```bash
mimeo link example.com github:OWNER/REPO
```

### `https://` shows a certificate for `*.github.io`, or a browser warning

GitHub has no approved certificate for the hostname. `mimeo status HOSTNAME` shows which of the states above it is in.

### `http://` does not redirect to `https://`

HTTPS is not enforced. `status` shows `fixable`; run `mimeo sync HOSTNAME`. Right after enforcement, a plain `http://` request can still return 200 for a short while before it returns 301 (seen 2026-11-16 on one of five sites).

## The site loads the wrong thing

### GitHub's 404 page at the custom domain

No repository has that hostname as its Pages custom domain, or the repository's Pages build has never succeeded.

1. `mimeo status HOSTNAME`. If `REPO` is `-`, no repository claims the hostname: `mimeo link HOSTNAME github:OWNER/REPO`.
2. If `REPO` is filled in, open `https://github.com/OWNER/REPO/actions` and look at the latest run. A failed build is fixed in the repository, not in mimeo.

### Old content after a push

Content never goes through mimeo. Pushing to `main` runs the template's GitHub Actions workflow, which builds and deploys. Look at the repository's Actions tab. A commit message containing `[skip ci]` does not deploy.

### A parking page, or another site

An address record at the hostname points somewhere else. `mimeo status HOSTNAME` shows `RECORDS` as `extra` or `missing`; `mimeo sync HOSTNAME` puts it right. If `status` shows `ok` and the browser still shows the old page, a resolver is holding the old answer; it lets go when the record's TTL runs out (600 seconds for records mimeo writes on Porkbun).

### After `delegate`, DNS lookups still show the old nameservers

Expected. `delegate` sets the nameservers at the registrar, and resolvers keep the old answer until it expires. `mimeo status` reads the registrar, so it shows the new provider at once; `dig NS example.com` can lag (seen 2026-11-16 and 2026-11-17, still the old answer minutes later). The site stays up meanwhile, because `delegate` leaves the old provider's records in place and both providers give the same answers.

## A command refused

Each message says why. The table adds what to do.

| Command | Message contains | Why | What to do |
|:--------|:-----------------|:----|:-----------|
| `sync` | `skipped: no site` | No repository claims the hostname | `mimeo link` or `mimeo create`, or nothing |
| `sync` | `DNS is at a provider that is not configured` | The zone is `external` | Add the provider to the config, or fix the records by hand |
| `sync` | `not fixable by sync` | Only problems with printed steps remain | Follow the steps under it |
| `link`, `create` | `is already linked to` | Another repository has the hostname as its custom domain | `mimeo unlink HOSTNAME`, then run the command again |
| `create` | `is not covered by a domain registered in this account` | Nothing is created for a hostname no registered domain covers | Register the domain at Porkbun first |
| `create` | `was left at porkbun. Moving it to cloudflare would stop:` | Not a failure. The site was created and the zone stayed where it was, because moving it would stop the listed service | To move it anyway, run the `mimeo delegate` command it prints and answer the question |
| `create` | `--repo names one repository, so it takes one hostname` | `--repo` with several hostnames | One hostname per `--repo` |
| `unlink` | `No site is linked to` | No repository claims the hostname | Nothing to unlink |
| `delegate` | `DNSSEC is enabled` | The registry's DS records point at the current provider's keys, so changing nameservers would stop the domain resolving | Turn DNSSEC off at Porkbun, wait for the registry to drop the DS records, then delegate |
| `delegate` | `is a name inside` | `delegate` moves whole zones | Run it on the parent domain it names |
| `delegate` | `is not configured` | The target provider has no section in the config | Add `[cloudflare]` to the config |
| `delegate` | `which mimeo cannot read, so there is nothing to copy` | The zone is at a provider mimeo is not configured for | Copy the records by hand first, or pass `--empty` to move the zone with no records and add them after |
| `delegate` | `not copied (cloudflare has no ALIAS type)` | Cloudflare cannot hold an `ALIAS` record | Usually nothing: Porkbun's parking `ALIAS` is not wanted. Otherwise add an equivalent record by hand |
| `delegate` | `record(s) did not arrive ... so the nameservers were not changed` | A copied record could not be read back | Nothing was switched. Run `delegate` again; it copies only what is missing |
| `delegate` | `Moving example.com to porkbun would stop:` then `Move example.com anyway?` | A record points at a service the current provider runs only for zones it serves (Cloudflare Email Routing, Cloudflare's proxy) | Answer no unless that service has been moved or is no longer wanted. `--yes` skips the question |
| `delegate` | `was not moved. Moving it to ... would stop:` | The question was answered no, or there was no terminal to ask on | Same |
| `delete` | HTTP 403 on deleting the repository | The `gh` token lacks the `delete_repo` scope | `gh auth refresh -h github.com -s delete_repo` |

`delegate` warns about three services only: Cloudflare Email Routing, Cloudflare proxied records, and Porkbun mail (worded "may stop"). Anything else that depends on the old provider moves without a question. That Email Routing stops when the zone leaves Cloudflare, and how Porkbun's mail forwarding behaves, are not checked against the vendors' documentation (as of 2026-11-17).

## mimeo cannot find a site

mimeo keeps the pairs of hostname and repository it has found in `~/.cache/mimeo/sites.json`. The repository's custom-domain setting is the authority; a cached pair is confirmed against it before use.

| What you see | Why | What to do |
|:-------------|:----|:-----------|
| `no site` for a hostname that has a repository | The repository was linked outside mimeo, or its organization was added to `github.organizations` after the last scan. The cache does not record which organizations it was built from | `mimeo scan` |
| `scan` warns that two repositories claim one hostname | Both have it as their custom domain; the cache keeps the first | Remove the custom domain from the one that should not have it (repository Settings > Pages) and run `mimeo scan` |
| A private repository is not found | `scan` sees private repositories only in the authenticated account and in organizations it belongs to | Add the account to the organization, or make the repository public |

## Configuration

The config file is `~/.config/mimeo/config.toml`. `config.toml.example` in the repository root lists every key. Any key can be overridden by a `MIMEO_*` environment variable, and `--template-org` and `--deploy-org` override both.

| Message | What to do |
|:--------|:-----------|
| `Configuration file not found` | `mkdir -p ~/.config/mimeo && cp config.toml.example ~/.config/mimeo/config.toml && chmod 600 ~/.config/mimeo/config.toml`, then fill in the Porkbun keys and `github.default_org` |
| `Failed to parse config file` | The file is not valid TOML. The message gives the line |
| `Missing required configuration` | Add the keys it lists. Section names are `[porkbun]`, `[github]`, `[cloudflare]`, `[defaults]`; the Porkbun keys are `api_key` and `secret_key` |
| `Invalid schema_version` | `schema_version` at the top of the file must be a positive integer; `2` for this version |
| `github.organizations ... must be a list` | Write `organizations = ["one", "two"]` |
| `defaults.dns ... must be one of` | `dns = "porkbun"` or `dns = "cloudflare"` |
| `defaults.dns is cloudflare but ... has no cloudflare.api_token` | Add the `[cloudflare]` section, or set `dns = "porkbun"` |
| `defaults.ignore_domains ... must be a list` | Write `ignore_domains = ["a.com", "b.net"]` |

`defaults.dns` decides where `create` and `delegate` put a zone when `--dns` is not given. With `dns = "cloudflare"`, `mimeo create` on a domain at Porkbun moves the zone to Cloudflare first. Pass `--dns porkbun` to keep one where it is.

## GitHub access

mimeo calls GitHub through the `gh` command, using its login. `mimeo doctor` checks each of these.

| `doctor` line or message | What to do |
|:-------------------------|:-----------|
| `gh installed` fails; `GitHub CLI (gh) is not installed` | `brew install gh` |
| `gh authenticated` fails; `GitHub CLI (gh) is not authenticated` | `gh auth login` |
| `workflow scope` fails; `create` fails with `refusing to allow` | The template's workflow file under `.github/workflows/` cannot be written without the `workflow` scope: `gh auth refresh -h github.com -s workflow` |
| `delete` fails with HTTP 403 | `gh auth refresh -h github.com -s delete_repo` |
| `Not Found (HTTP 404)` while creating a repository | The logged-in account cannot create repositories in `github.default_org`. Check the login with `gh api user --jq .login` and the organization's permissions |
| `create` rejects the template | A template is offered only while the repository's "Template repository" setting is on, in the organization named by `github.template_org` |
| `Pages IPs` fails | GitHub's published Pages addresses differ from the eight mimeo writes. Do not run `sync` until mimeo is updated: it would write addresses GitHub no longer lists |

## Porkbun

| Message | Why | What to do |
|:--------|:----|:-----------|
| `Porkbun keys` fails in `doctor`; `Porkbun API error:` on every domain | The keys are wrong, or were revoked | Make new keys at https://porkbun.com/account/api and put them in the config |
| `Porkbun API error` naming one domain while others work | API access is switched off for that domain. Porkbun has a per-domain "API Access" setting (carried over from the 1.x guide; not rechecked for 2.0) | Turn it on in the domain's details at Porkbun |
| `Failed to communicate with Porkbun API: HTTP 503` on one or two rows of `status --all` | Porkbun answered 503 for longer than the retries lasted. mimeo spaces its Porkbun requests 0.25 seconds apart and retries five times over about 30 seconds | Run the command again, or `mimeo status` for the hostnames that failed |
| `status --all` takes about a minute | The spacing above, over two requests per domain | Nothing; name hostnames to check a few quickly |

A row that fails to read is shown with dashes and the error at the end of the line, the command ends with `N of M domains failed`, and the exit code is 6. The other rows are complete.

## Cloudflare

The token needs three permissions on the zones mimeo manages: Zone: Read and DNS: Edit to read and write records, and Zone: Edit to let `delegate` create a zone. In Cloudflare's token editor the zone permissions appear only after the scope is changed from "Entire Account" to "All Domains" (seen 2026-11-16).

| Message | What to do |
|:--------|:-----------|
| `Cloudflare token` fails in `doctor` | The token is wrong, revoked or expired. Make a new one with the three permissions and put it in `[cloudflare] api_token`. For a token owned by the account (not a user), also set `account_id`: `doctor` verifies such a token through the account |
| `Creating a Cloudflare zone needs cloudflare.account_id in the config` | Add `account_id` under `[cloudflare]`. It is in the Cloudflare dashboard's URL and on the account's overview page |
| `Cloudflare has no zone example.com` | The registrar's nameservers name Cloudflare, but the token cannot see the zone: it is in another Cloudflare account, or the token is limited to other zones |
| `Cloudflare API error:` followed by Cloudflare's text | Cloudflare refused the call; its text says why. A permission error means the token lacks one of the three permissions |

After `delegate` moves a zone away from Cloudflare, the zone and its records stay in the Cloudflare account. mimeo has no command that deletes a zone; remove it in the dashboard if it is not wanted.

## Exit codes and partial failures

| Code | Meaning |
|:-----|:--------|
| 0 | Done. Problems that `status` finds are findings, not failures, and still exit 0 |
| 1 | A provider refused, or mimeo refused (the message says why) |
| 2 | Configuration error |
| 3 | Authentication or permission error (HTTP 401 or 403) |
| 4 | Rate limited (HTTP 429) |
| 5 | A temporary failure that outlasted the retries (HTTP 500, 502, 503, 504, or the network) |
| 6 | Some hostnames failed and some succeeded |

When a run over several hostnames fails for some, the rows that succeeded are complete and their changes stay made. Run the command again for the hostnames that failed. Every command can be run again safely: `sync`, `link` and `delegate` change only what is still wrong, and `create` leaves an existing repository as it is unless `--force` is given.

For one hostname at a time with nothing running concurrently, `create` takes `--sequential`.
