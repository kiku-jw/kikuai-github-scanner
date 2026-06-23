# Evidence

## AC1

PASS. `scripts/opportunity_scanner.py` now has an `oss-bounty-radar` subcommand. The smoke command imported two candidates from the current sibling `oss-bounty-radar` report into a temporary output file.

## AC2

PASS. `scripts/run_autonomous_loop.py` now accepts `oss-bounty-radar` jobs, runs an optional external scan command, runs the scanner import command, and only appends post-pipeline commands when both `ingest` and `post_pipeline` are true.

## AC3

PASS. `config/autonomous-loop.json` includes `oss-bounty-radar-daily` with `ingest: true`, `post_pipeline: false`, and `send_telegram: false`.

## AC4

PASS. `rg -n "/Users/nick" README.md config scripts tests` only reports the pre-existing test assertion that GitHub issue bodies must not contain `/Users/nick`.

## AC5

PASS. Verification commands passed:

```bash
python3 -m unittest discover -s tests
```

78 tests passed.

```bash
python3 -m py_compile scripts/opportunity_scanner.py scripts/run_autonomous_loop.py
```

Passed.

```bash
python3 scripts/run_autonomous_loop.py --config config/autonomous-loop.json --health-check
```

Passed with `status: ok` and `stale_job_count: 0`.

```bash
python3 scripts/opportunity_scanner.py --week 2026-W26 oss-bounty-radar --input ../oss-bounty-radar/reports/latest.json --output /tmp/kikuai-github-scanner-oss-bounty-candidates-relative.jsonl --max-candidates 2 --min-score 14 --verdicts candidate watchlist
```

Passed with `candidate_count: 2`, `input_count: 36`, and `skipped_count: 0`.

```bash
git diff --check
```

Passed.
