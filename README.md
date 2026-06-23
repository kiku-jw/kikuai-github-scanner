# KikuAI GitHub Scanner

Local-first opportunity scanner for public GitHub/GitLab repositories, public
discussion demand signals, and no-call solo-founder idea filtering.

The scanner collects public project candidates, preserves raw evidence in a
local ledger, applies conservative filters, writes Markdown reports, and can
send a ready-only Telegram digest. Telegram output is intentionally restricted
to ideas that survive the final filters.

**[Run the fixture scanner locally](#quick-start)**

[Docs](#what-it-does) · [Examples](#quick-start) · [Reports](#quick-start)

```bash
python3 scripts/opportunity_scanner.py --week 2026-W24 init
python3 scripts/opportunity_scanner.py --week 2026-W24 run --input fixtures/manual-candidates.jsonl
```

Expected result: a local ledger and Markdown opportunity report under `data/`.

## What It Does

- Collects public GitHub repositories through the GitHub REST API.
- Collects public GitLab projects through the GitLab REST API.
- Mines capped Hacker News and OAuth-authenticated Reddit demand signals.
- Imports `oss-bounty-radar` reports as a paid-output source lane.
- Normalizes candidates into an append-only local ledger.
- Deduplicates repositories and fork families.
- Applies deterministic hard gates and weak-label triage.
- Creates opportunity cards and council-review packets.
- Captures bounded repository digest metadata for shortlisted candidates.
- Builds capped GH Archive-style public momentum candidates from local event
  fixtures before any live BigQuery work.
- Captures small attributed ecosyste.ms derived metadata for GitHub candidates.
- Writes calibration reports and a static local dashboard.
- Runs a low-load GitHub monitor from `config/github-monitor.json`.
- Runs an optional autonomous control loop from `config/autonomous-loop.json`.
- Mirrors serious candidates and autonomous loop failures into GitHub Issues
  without duplicating existing issues.
- Optionally syncs mirrored candidate issues into a GitHub Projects v2 board.
- Applies explicit Telegram feedback commands/callbacks back into the ledger.

## Quick Start

```bash
python3 scripts/opportunity_scanner.py --week 2026-W24 init
python3 scripts/opportunity_scanner.py --week 2026-W24 run --input fixtures/manual-candidates.jsonl
python3 -m unittest discover -s tests
```

## Expected Output

The local run writes ignored runtime artifacts such as:

```text
data/ledger/
data/reports/
data/runs/
```

Reports are candidate evidence, not build instructions or revenue proof.

Collect and ingest public GitHub candidates:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  github-search \
  --query 'hosted dashboard language:Python stars:>50 pushed:>2025-01-01' \
  --max-candidates 10 \
  --issues-per-repo 3 \
  --ingest
```

Run the low-load monitor:

```bash
python3 scripts/run_github_monitor.py
```

The GitHub monitor writes a Telegram dry-run by default. Real outbound
Telegram should normally be handled by the autonomous loop's final
`send-telegram-digest --skip-empty` step, not by the intermediate monitor.
If you deliberately enable monitor-level sending, it is still double-gated by
config and CLI:

```bash
python3 scripts/run_github_monitor.py --send
```

Run the autonomous control loop:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json
```

Check whether the autonomous loop is healthy or stale without running jobs:

```bash
/usr/bin/python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --health-check
```

The loop keeps state in `data/runs/autonomous-loop-state.json`, uses a lock to
avoid overlapping runs, and only executes jobs whose interval is due. Scheduling
is intentionally left to the operator's environment.

Mirror serious candidates into GitHub Issues:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  mirror-github-issues \
  --repo kiku-jw/kikuai-github-scanner
```

The mirror is idempotent. It writes local mirror state under
`data/ledger/github_issue_mirrors.jsonl` and adds a deterministic candidate
marker to each GitHub issue body. Existing mirrored issues are updated with a
human-readable body, stable labels, and transition comments when the verdict
changes.

Autonomous loop failures can also be mirrored into GitHub Issues when
`failure_issue_reporting.enabled` is set in `config/autonomous-loop.json`.
Repeated failures update the same issue, and recovery is recorded as a comment.

Optionally sync mirrored candidate issues into GitHub Projects v2:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  sync-github-project \
  --repo kiku-jw/kikuai-github-scanner \
  --project-owner kiku-jw \
  --project-number 4
```

Project sync is a mirror only. The local ledger and GitHub Issues remain the
durable source of truth. The command requires a GitHub token with Projects v2
GraphQL access.

Capture a bounded repository digest for a serious candidate:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  repo-digest \
  --candidate-id cand_example \
  --source-path /path/to/local/repo \
  --tool builtin
```

`repo-digest` refuses non-serious candidates unless `--force` is supplied. It
writes metadata under `data/repo_digests/<candidate_id>/` and links that context
into future opportunity cards and council packets. It does not send digest text
to Telegram. If Repomix is run externally, pass its output with `--digest-file`
and record `--tool repomix --tool-version <version>`.

Capture bounded repository digests for a capped batch of serious GitHub
candidates:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  repo-digest-batch \
  --max-candidates 1 \
  --max-files 80 \
  --max-bytes 500000
```

`repo-digest-batch` shallow-clones only selected serious GitHub candidates,
isolates per-candidate clone/digest failures, skips already-digested candidates
unless `--force` is supplied, and never sends digest text to Telegram.

Collect capped GH Archive-style momentum candidates from a local public event
fixture:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  gh-archive-momentum \
  --input data/sources/gh-archive/sample-events.jsonl \
  --max-events 1000 \
  --max-repos 20 \
  --min-events 2 \
  --ingest
```

The current command is fixture/file based. Live BigQuery or hourly archive
fetching should be added only behind explicit scan budgets.

Capture small attributed ecosyste.ms metadata:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  ecosystems-enrich \
  --candidate-id cand_example
```

The enrichment layer stores derived fields and attribution under
`data/ledger/ecosystems_enrichments.jsonl`; it does not vendor ecosyste.ms code
or mirror raw API responses into candidate rows.

Mine capped Reddit demand signals:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  reddit-demand \
  --subreddits webdev SaaS indiehackers \
  --max-posts-per-subreddit 8 \
  --comments-per-post 4 \
  --max-total-items 60 \
  --ingest
```

Reddit collection requires OAuth credentials and a descriptive `REDDIT_USER_AGENT`.
There is no logged-out `.json` scraping fallback.

Import paid-output candidates from `oss-bounty-radar`:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W25 \
  oss-bounty-radar \
  --input ../oss-bounty-radar/reports/latest.json \
  --ingest
```

The autonomous loop can run `../oss-bounty-radar/scripts/run_radar.sh` from a
sibling checkout and import its `latest.json` output as `oss-bounty-radar-daily`.
This replaces the standalone bounty LaunchAgent; the bounty source remains
conservative and does not use the product-opportunity post-pipeline unless that
job explicitly sets `post_pipeline: true`.

Apply Telegram feedback commands/callbacks:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W24 telegram-feedback
```

Allowed text commands are `/reject`, `/park`, `/watchlist`, `/proof`, and
`/filter` followed by a candidate id and optional notes.

## Data And Secrets

Runtime data is written under `data/` and is ignored by Git. Put local secrets
in `.env`; never commit tokens.

Supported optional environment variables:

```text
GITHUB_TOKEN=
GH_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_ACCESS_TOKEN=
REDDIT_USER_AGENT=
```

## Documentation

- `docs/opportunity-scanner-prd.md`
- `docs/opportunity-scanner-roadmap.md`
- `docs/opportunity-scanner-github-source.md`
- `docs/opportunity-scanner-autonomous-monitor.md`
- `docs/opportunity-filter-v3.md`

## License

MIT
