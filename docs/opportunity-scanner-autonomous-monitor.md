# Opportunity Scanner Autonomous Monitor

## Purpose

Phase 9 turns the local scanner into a weekly GitHub monitor. It does not add a
new decision layer. It runs the existing strict pipeline on a small set of
configured GitHub search lanes and keeps Telegram as a ready-only decision feed.

Phase 10 adds a lightweight autonomous loop above the batch monitor. The loop is
the scheduler/control plane. It wakes up frequently, checks job state, runs only
jobs whose interval is due, writes structured logs, and exits. This gives
continuous autonomy without a constantly running process.

## Files

```text
config/github-monitor.json
config/autonomous-loop.json
scripts/run_github_monitor.py
scripts/run_autonomous_loop.py
data/runs/<week>-github-monitor-<run-id>.json
data/runs/<week>-autonomous-loop-<run-id>.json
data/runs/autonomous-loop-state.json
ops/launchd/com.operator.opportunity-scanner.github-monitor.plist
ops/launchd/com.operator.opportunity-scanner.autonomous-loop.plist
ops/install_launchd.sh
ops/install_autonomous_loop.sh
ops/uninstall_launchd.sh
ops/uninstall_autonomous_loop.sh
```

## Manual Run

Run the weekly monitor without Telegram send:

```bash
python3 scripts/run_github_monitor.py
```

Run a specific week:

```bash
python3 scripts/run_github_monitor.py --week 2026-W23
```

Allow monitor-level Telegram send only when deliberately enabled:

```bash
python3 scripts/run_github_monitor.py --send
```

Actual Telegram send is intentionally double-gated:

- `config/github-monitor.json` must have `"send_telegram": true`
- the command must include `--send`

The default config keeps monitor-level send disabled. The preferred outbound
path is the autonomous loop's final `send-telegram-digest --skip-empty` step,
so intermediate monitor runs cannot send raw or empty status noise.

## Pipeline

For each enabled GitHub lane, the runner calls:

```text
github-search --ingest
```

Then it calls:

```text
label
ecosystems-enrich          # when enabled
repo-digest-batch          # when enabled, capped and serious candidates only
deep-review --max-candidates <deep_review_max_candidates>
digest
calibration
dashboard
send-telegram-digest --dry-run
send-telegram-digest --skip-empty   # only when explicitly allowed
```

The runner does not send raw candidates to Telegram. The scanner's Telegram
contract still allows only `proof-card`, `PRD-lite`, and
`operator-proof-approved` candidates.

## Autonomous Loop

Run one autonomous tick without real Telegram send:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json
```

Allow real Telegram send for jobs that also allow it:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --send
```

Force enabled jobs even when they are not due:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --force
```

Preview due jobs without running commands or updating state:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --dry-run
```

Check loop health without running commands or updating state:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --health-check
```

The default loop config runs:

- `github-monitor-daily`: existing GitHub monitor once every 24 hours.
- `hn-demand-daily`: capped HN demand scan once every 72 hours, then the normal
  label/enrichment/digest/deep-review/digest/calibration/dashboard pipeline.
- `telegram-feedback`: low-load Telegram command/callback intake every 4 hours.

It also includes a disabled `reddit-demand-weekly` job. Enable it only after
`REDDIT_USER_AGENT` plus OAuth credentials are present in the repo-local `.env`.

These jobs use the same ready-only Telegram contract. The loop does not make
build decisions and does not send raw candidates. Telegram feedback is inbound
only; it writes Operator decisions/filter updates and does not widen the outbound
digest.

Real Telegram sends use `send-telegram-digest --skip-empty`, so a daily
autonomous tick does not message Operator when no candidate reached the ready
shortlist. Dry-runs still report the digest size for observability.

Health checks return one JSON row per job with `due`, `stale`,
`last_success_at`, `last_run_log_path`, and any open failure issue URL. A job
is stale when its last success/finish is older than `interval_hours` plus
`health_stale_grace_hours`, or when an enabled job has never run.

## GitHub Issues Mirror

The scanner can mirror serious candidates into GitHub Issues:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  mirror-github-issues \
  --repo kiku-jw/kikuai-github-scanner
```

Default mirrored verdicts:

- `watchlist`
- `proof-card`
- `PRD-lite`
- `operator-proof-approved`

The command does not mirror raw, needs-evidence, park, reject, or
machine-reject candidates.

Duplicate protection:

- local ledger: `data/ledger/github_issue_mirrors.jsonl`
- issue body marker: `<!-- opportunity-scanner:candidate_id=... -->`
- GitHub issue search by candidate ID before creation

Existing mirrored issues are updated instead of being skipped forever. The
update path rewrites the managed issue body, applies stable labels, and adds a
transition comment when the candidate verdict changes.

Candidate issue labels include:

- `opportunity-scanner`
- `source:<source-lane>`
- `verdict:<verdict>`
- `needs:evidence`, `needs:operator-review`, `needs:proof`, or `needs:prd`
- risk labels when reason codes expose legal, platform, support,
  distribution, or payment risk

Candidate issue bodies are intentionally human-readable. They avoid local
filesystem paths, raw JSON dumps, candidate ledger paths, and Telegram-style
technical clutter. The hidden marker is retained only for deduplication.

Autonomous loop jobs can enable:

```json
"mirror_github_issues": true,
"mirror_repo": "kiku-jw/kikuai-github-scanner",
"mirror_verdicts": ["watchlist", "proof-card", "PRD-lite", "operator-proof-approved"]
```

## GitHub Projects v2 Mirror

GitHub Projects v2 is optional and stays downstream of GitHub Issues. The local
ledger remains the source of truth; GitHub Issues are the durable operator
backlog; Projects is only a workflow view.

Manual project sync:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  sync-github-project \
  --repo kiku-jw/kikuai-github-scanner \
  --project-owner kiku-jw \
  --project-number 4
```

Dry-run project sync:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  sync-github-project \
  --repo kiku-jw/kikuai-github-scanner \
  --project-owner kiku-jw \
  --project-number 4 \
  --dry-run
```

Autonomous loop jobs can enable:

```json
"sync_github_project": true,
"project_owner": "kiku-jw",
"project_number": 4
```

If `sync_github_project=true` but no project owner/number/id is configured, the
loop skips the project sync instead of failing the main monitor job. A live
sync requires a GitHub token with Projects v2 GraphQL access.

The default local config targets `KikuAI Opportunity Scanner`, project number
`4`.

## Autonomous Loop Config

Edit `config/autonomous-loop.json`.

Important fields:

- `state_path`: durable last-success state
- `lock_path`: prevents overlapping runs
- `lock_stale_minutes`: removes stale lock files after a crash
- `health_stale_grace_hours`: grace window before an enabled job is reported stale
- `command_timeout_seconds`: hard timeout for every subprocess
- `max_jobs_per_tick`: caps work per wake-up
- `send_telegram`: loop-level Telegram gate
- `jobs[].interval_hours`: due interval per job
- `jobs[].send_telegram`: job-level Telegram gate
- `jobs[].ecosystems_enrich`: capture attributed ecosyste.ms derived metadata before review
- `jobs[].ecosystems_max_candidates`: cap enrichment volume per post-pipeline run
- `jobs[].repo_digest_batch`: clone and digest a capped batch of serious GitHub candidates before review
- `jobs[].repo_digest_max_candidates`: cap repository digest clones per job
- `jobs[].repo_digest_max_files`: cap text files included per repository digest
- `jobs[].repo_digest_max_bytes`: cap source bytes included per repository digest
- `jobs[].repo_digest_clone_timeout_seconds`: cap per-repository clone time
- `jobs[].mirror_github_issues`: create/link GitHub Issues after analysis
- `jobs[].mirror_repo`: target backlog repo
- `jobs[].sync_github_project`: add mirrored issues to a configured Project v2
- `jobs[].project_owner`: Project v2 owner login
- `jobs[].project_number`: Project v2 number
- `jobs[].project_id`: Project v2 node id, optional if known

Failure issue reporting is controlled separately:

```json
"failure_issue_reporting": {
  "enabled": true,
  "repo": "kiku-jw/kikuai-github-scanner",
  "labels": ["opportunity-scanner", "autonomous-loop", "type:failure"]
}
```

When enabled, a failed autonomous job creates or updates one durable failure
issue keyed by job id. Repeated failures update that issue instead of creating
duplicates. When the job later succeeds, the loop records recovery as an issue
comment and clears the open-failure pointer from local state. The issue is not
auto-closed.

HN Demand Miner caps:

- `max_stories`
- `comments_per_story`
- `max_total_items`
- `max_clusters`
- `max_candidates`

Reddit Demand Miner caps:

- `subreddits`
- `sort`
- `max_posts_per_subreddit`
- `comments_per_post`
- `max_total_items`
- `max_clusters`
- `max_candidates`

Reddit jobs are skipped by the autonomous loop when OAuth credentials or
`REDDIT_USER_AGENT` are missing. Direct CLI runs still fail fast so missing
configuration is obvious during manual testing.

## Config

Edit `config/github-monitor.json`.

Important fields:

- `enabled`: disables the whole monitor when false
- `default_max_candidates`: default cap per query lane
- `total_candidate_cap`: hard cap across enabled lanes
- `issues_per_repo`: recent non-PR issues to collect per repo
- `deep_review_max_candidates`: cap before expensive review/card generation
- `ecosystems_enrich`: capture attributed ecosyste.ms derived metadata before review
- `ecosystems_max_candidates`: cap enrichment volume per monitor run
- `repo_digest_batch`: clone and digest a capped batch of serious GitHub candidates before review
- `repo_digest_max_candidates`: cap repository digest clones per monitor run
- `repo_digest_max_files`: cap text files included per repository digest
- `repo_digest_max_bytes`: cap source bytes included per repository digest
- `repo_digest_clone_timeout_seconds`: cap per-repository clone time
- `send_telegram`: second gate for real Telegram send
- `github_queries`: search lanes

Each lane supports:

- `id`
- `enabled`
- `query`
- `max_candidates`
- `per_page`
- `issues_per_repo`
- `sort`
- `order`
- `notes`
- `expected_signal`

Do not add secrets to this config.

## Run Logs

Every monitor run writes a structured log:

```text
data/runs/<week>-github-monitor-<run-id>.json
```

The log includes:

- status
- week
- config hash
- enabled lanes
- command outcomes
- candidate counts by lane
- Telegram dry-run/send payloads
- sanitized error summaries

Every autonomous loop run writes a structured log:

```text
data/runs/<week>-autonomous-loop-<run-id>.json
```

The autonomous log includes `health_summary` with selected, succeeded, failed,
skipped, command, enrichment, repo digest, candidate-issue mirror, Project v2,
Telegram, feedback, and failure-notification counts.

Secrets from `GITHUB_TOKEN`, `GH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TG_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, and `TG_CHAT_ID` are redacted from stdout/stderr tails.

## Launchd

Install weekly local scheduling without Telegram send:

```bash
sh ops/install_launchd.sh
```

Install weekly scheduling with Telegram send allowed:

```bash
sh ops/install_launchd.sh --send
```

Install the autonomous loop without Telegram send:

```bash
sh ops/install_autonomous_loop.sh
```

Install the autonomous loop with Telegram send allowed:

```bash
sh ops/install_autonomous_loop.sh --send
```

Uninstall:

```bash
sh ops/uninstall_launchd.sh
sh ops/uninstall_autonomous_loop.sh
```

The installed LaunchAgent runs Monday at 09:15 local time and writes shell logs:

```text
data/runs/logs/github-monitor.out.log
data/runs/logs/github-monitor.err.log
data/runs/logs/autonomous-loop.out.log
data/runs/logs/autonomous-loop.err.log
```

Before installing with `--send`, scheduled Telegram send must also be enabled in
config:

```json
"send_telegram": true
```

Keep `.env` repo-local and uncommitted:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
GITHUB_TOKEN=...
```

`GITHUB_TOKEN` or `GH_TOKEN` is optional but recommended for rate limits. The
collector still enforces public-only GitHub collection.

## Query Tuning

After each weekly run, inspect:

- `data/runs/<week>-github-monitor-*.json`
- `data/reports/<week>-calibration.md`
- `data/reports/<week>-digest.md`
- `data/outbox/telegram/<week>-digest.md`

Kill or disable lanes that repeatedly produce only parked/rejected candidates.
Do not broaden queries until at least one narrow lane produces useful watchlist
or proof-card candidates.

## Parking Lot

Do not add these until the weekly monitor proves useful:

- GitHub Projects sync
- GitLab scheduled source
- interactive Telegram feedback
- richer operator UI
- additional marketplaces
