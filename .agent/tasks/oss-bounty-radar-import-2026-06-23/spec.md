# OSS Bounty Radar Import - 2026-06-23

## Goal

Close the dirty autonomous-loop changes by making `oss-bounty-radar` reports a first-class, conservative paid-output source lane in `kikuai-github-scanner`.

## Acceptance Criteria

AC1. `scripts/opportunity_scanner.py` imports `oss-bounty-radar` JSON reports, filters by verdict and minimum score, writes source JSONL, and optionally ingests candidates into the ledger.

AC2. `scripts/run_autonomous_loop.py` supports an `oss-bounty-radar` job type that can run an external radar command, import the report, and keep the post-pipeline disabled unless explicitly enabled.

AC3. The default autonomous-loop config enables the bounty source without Telegram sends and without the product-opportunity post-pipeline.

AC4. Public committed docs/config avoid machine-specific `/Users/nick/...` paths for the bounty source.

AC5. Unit tests, syntax checks, health-check, and a live-safe import smoke pass.

## Constraints

- Do not expose secrets or local `.env` values.
- Keep the bounty lane conservative: paid-output source only, no automatic opportunity post-pipeline by default.
- Keep changes scoped to the scanner and autonomous-loop integration.

## Non-Goals

- No new LaunchAgent.
- No live bounty execution during this cleanup pass.
- No automatic product decision from imported bounty rows.

## Verification Plan

- `python3 -m unittest discover -s tests`
- `python3 -m py_compile scripts/opportunity_scanner.py scripts/run_autonomous_loop.py`
- `python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --health-check`
- `python3 scripts/opportunity_scanner.py --week 2026-W26 oss-bounty-radar --input ../oss-bounty-radar/reports/latest.json --output /tmp/kikuai-github-scanner-oss-bounty-candidates-relative.jsonl --max-candidates 2 --min-score 14 --verdicts candidate watchlist`
- `git diff --check`
