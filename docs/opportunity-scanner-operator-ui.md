# Opportunity Scanner Operator UI

## Purpose

Phase 8 adds a minimal optional operator UI only after the file-based pipeline
exists. It is a static HTML dashboard generated from ledger and report files.
There is no server, auth layer, state mutation, or new dependency.

## Command

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 dashboard
```

Output:

```text
data/reports/YYYY-WW-dashboard.html
```

## Dashboard Contents

- status counts
- links to existing markdown reports
- candidate table
- source
- current status
- machine verdict
- next action
- evidence link

The dashboard is read-only. Status changes still go through ledger commands such
as `operator-feedback`, not through the UI.

## Verification

```bash
python3 -m py_compile scripts/opportunity_scanner.py tests/test_opportunity_scanner.py
python3 -m unittest discover -s tests
```

Covered invariants:

- dashboard HTML is generated
- dashboard includes candidate rows
- dashboard links to evidence files using relative paths
- dashboard requires no web server
