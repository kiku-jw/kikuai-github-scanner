# Opportunity Scanner Local Slice

## Purpose

This started as the Phase 0/1 local slice and now includes Phase 2 GitHub/GitLab
source MVPs, Phase 3 weak-label baseline, Phase 4 deep-review/council baseline,
Phase 5 digest/feedback loop, Phase 6 calibration/rescore loop, and Phase 7
source expansion with HN Demand Miner, and Phase 8 static operator dashboard. It proves the local
control plane before live Telegram sending or live council subagent
orchestration.

## What Exists

- `scripts/opportunity_scanner.py` - local CLI.
- `fixtures/manual-candidates.jsonl` - three manual fixture candidates.
- `tests/test_opportunity_scanner.py` - verification for ledger, events,
  prefilter, GitHub collection contracts, weak labels, evidence files, and
  report generation.

## Commands

Initialize the local data layout:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 init
```

Run the manual fixture batch:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 run --input fixtures/manual-candidates.jsonl
```

Collect and ingest public GitHub repositories:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  github-search \
  --query 'hosted dashboard language:Python stars:>50' \
  --max-candidates 10 \
  --issues-per-repo 3 \
  --ingest
```

Collect and ingest public GitLab projects:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  gitlab-search \
  --search 'dashboard' \
  --max-candidates 10 \
  --issues-per-project 3 \
  --ingest
```

Mine public Hacker News demand clusters:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  hn-demand \
  --max-stories 80 \
  --comments-per-story 20 \
  --max-clusters 10 \
  --max-candidates 5
```

Collect and ingest only strong Hacker News demand clusters:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  hn-demand \
  --max-stories 80 \
  --comments-per-story 20 \
  --max-clusters 10 \
  --max-candidates 5 \
  --ingest
```

Regenerate a report:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 report
```

Apply weak labels and batch triage:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 label
```

Create opportunity cards and council packets:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 deep-review
```

Limit deep review to the strongest ranked candidates:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 deep-review --max-candidates 5
```

Aggregate council findings:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  council-aggregate \
  --input path/to/council-findings.jsonl
```

Write weekly digest and Telegram outbox:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 digest
```

Preview Telegram delivery without sending:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 send-telegram-digest --dry-run
```

Send the digest through Telegram Bot API:

```bash
# Either export these variables or put them in the repo-local .env file.
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python3 scripts/opportunity_scanner.py --week 2026-W23 send-telegram-digest
```

Run the autonomous GitHub monitor:

```bash
python3 scripts/run_github_monitor.py
```

Allow monitor Telegram send only when `config/github-monitor.json` also has
`"send_telegram": true`:

```bash
python3 scripts/run_github_monitor.py --send
```

Apply Operator feedback:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  operator-feedback \
  --input path/to/operator-feedback.jsonl
```

Write calibration:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 calibration
```

Write static dashboard:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 dashboard
```

Rescore an older raw week:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  rescore \
  --source-week 2026-W23 \
  --target-week 2026-W24
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Output Layout

```text
data/
  raw/YYYY-WW/candidates.jsonl
  sources/hn/YYYY-WW-demand-candidates.jsonl
  ledger/candidates.jsonl
  ledger/events.jsonl
  ledger/identity_aliases.jsonl
  ledger/labels.jsonl
  ledger/opportunity_cards.jsonl
  ledger/council_packets.jsonl
  ledger/council_findings.jsonl
  ledger/aggregations.jsonl
  ledger/operator_decisions.jsonl
  ledger/filter_updates.jsonl
  ledger/calibrations.jsonl
  ledger/rescore_runs.jsonl
  ledger/evidence/<candidate_id>.md
  outbox/telegram/YYYY-WW-digest.md
  sources/github/YYYY-WW-candidates.jsonl
  sources/gitlab/YYYY-WW-candidates.jsonl
  reports/YYYY-WW-batch-report.md
  reports/YYYY-WW-deep-review.md
  reports/YYYY-WW-council-aggregation.md
  reports/YYYY-WW-digest.md
  reports/YYYY-WW-calibration.md
  reports/YYYY-WW-dashboard.html
```

## Current Layer Behavior

- Intake normalizes records and writes raw weekly observations.
- Intake derives `repo_key` and `fork_family_key` for checked-repository and
  fork-family dedupe.
- Ledger stores candidates once and appends status events.
- Evidence markdown appends observations instead of overwriting prior evidence.
- Derived labels, cards, packets, findings, aggregations, and events are scoped
  by `week` so rescored candidates do not leak stale verdicts into new digests.
- Duplicate observations do not lower an existing stronger status.
- Identity aliases preserve repo/fork-family dedupe when authoritative metadata
  appears after the first sighting.
- Rescue fork observations can reopen a previously rejected family.
- Deterministic prefilter can output:
  - `machine-reject`
  - `codex-review`
  - `needs-evidence`
- Rescue signals route candidates to `codex-review`.
- Missing URLs become deterministic `machine-reject`.
- Weak labels write separate `labels.jsonl` rows and triage events.
- Weak labels never create `machine-reject`.
- Low-confidence labels do not downgrade existing review statuses.
- Weekly reports include weak-label confidence, uncertainty, missing evidence,
  triage rationale, and next evidence checks.
- Deep review writes opportunity cards and can move shortlist candidates to
  `reject`, `park`, `watchlist`, `proof-card`, or `PRD-lite`.
- Baseline `proof-card` promotion is blocked by any missing-evidence item whose
  `blocking_for` includes `proof-card`.
- Filter v3 strict scorecard gates `proof-card` at `27/34`, active
  challenger at `22/34`, watchlist at `16/34`, and treats unknown proof,
  distribution, cost, support, rights, and unit economics as zero.
- Deep review can be capped with `--max-candidates` to avoid generating council
  packets for every weak-review candidate in noisy weekly runs.
- Deep review generates six comparable council packets for shortlist
  candidates.
- Council aggregation records accepted findings, rejected findings, conflicts,
  vetoes, missing evidence, reason codes, and one machine verdict.
- Digest writes a local technical markdown report plus a separate human
  Telegram shortlist outbox.
- Telegram sender can deliver the outbox payload when `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_CHAT_ID` are present in the environment or repo-local `.env`.
- Telegram outbox excludes raw, park, reject, candidate ids, ledger paths, and
  reason-code dumps by default.
- Operator feedback writes durable decision events and optional filter updates.
- Calibration reports source/lane yield, reason-code histogram, proof-card
  conversion, and filter drift.
- Rescore can reprocess old raw observations into a target week with current
  filters.
- GitLab source expansion collects public projects into the same candidate
  contract as GitHub.
- Dashboard writes a read-only local HTML view over reports, candidates, and
  evidence links.

## Not Yet Included

- External weak LLM integration.
- Live council subagent runtime.
- Telegram bot command handlers and interactive feedback.
- Additional source expansion beyond GitHub/GitLab.
