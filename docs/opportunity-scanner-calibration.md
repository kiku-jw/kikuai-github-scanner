# Opportunity Scanner Calibration

## Purpose

Phase 6 tracks which sources, lanes, and reason codes produce useful candidates,
and provides a rescore command so old raw observations can be reprocessed after
filter changes.

## Commands

Write weekly calibration:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 calibration
```

Rescore an old raw week into a target week:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  rescore \
  --source-week 2026-W23 \
  --target-week 2026-W24
```

Skip weak-label rerun if needed:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  rescore \
  --source-week 2026-W23 \
  --target-week 2026-W24 \
  --no-labels
```

## Files

```text
data/
  ledger/calibrations.jsonl
  ledger/rescore_runs.jsonl
  reports/YYYY-WW-calibration.md
```

## Calibration Report

The report includes:

- source yield by final status
- search-lane yield by final status
- reason-code histogram
- proof-card conversion count
- proof-card candidate ids
- open filter drift notes from `ledger/filter_updates.jsonl`

This answers which lanes are producing proof-cards, watchlists, parks, rejects,
or weak candidates.

## Rescore Contract

`rescore` reads:

```text
data/raw/<source-week>/candidates.jsonl
```

and reprocesses those raw observations into:

```text
data/raw/<target-week>/candidates.jsonl
```

The command uses the current normalizer, deterministic prefilter, and, by
default, weak-label layer. It writes an append-only row to
`ledger/rescore_runs.jsonl` and writes a target-week calibration report.

Raw evidence remains append-only. Rescore does not delete old interpretations;
it creates new events and reports so filter changes can be audited.

## Verification

```bash
python3 -m py_compile scripts/opportunity_scanner.py tests/test_opportunity_scanner.py
python3 -m unittest discover -s tests
```

Covered invariants:

- calibration report includes source/lane yield
- reason-code histogram is generated
- open filter updates become filter drift notes
- rescore writes a new target-week raw batch
- rescore writes a durable rescore run row
