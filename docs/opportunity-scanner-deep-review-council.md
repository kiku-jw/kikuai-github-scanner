# Opportunity Scanner Deep Review And Council Packets

## Purpose

Phase 4 uses expensive judgment only after deterministic prefiltering and weak
triage have produced a shortlist. The implementation creates opportunity cards,
clean-context council packets, and a structured council aggregation report.

## Commands

Create opportunity cards and council packets:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 deep-review
```

Limit deep review to the strongest ranked candidates:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 deep-review --max-candidates 5
```

Aggregate structured council findings:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  council-aggregate \
  --input path/to/council-findings.jsonl
```

Expected run order:

```text
run or github-search --ingest -> label -> deep-review -> council-aggregate
```

## Files

```text
data/
  ledger/opportunity_cards.jsonl
  ledger/council_packets.jsonl
  ledger/council_findings.jsonl
  ledger/aggregations.jsonl
  reports/YYYY-WW-deep-review.md
  reports/YYYY-WW-council-aggregation.md
```

The local ledger remains source of truth. Subagents or external models should
write findings into the council finding schema; they should not mutate candidate
statuses directly.

## Deep Review Contract

Input statuses:

- `codex-review`
- `watchlist-candidate`
- `watchlist`
- `proof-card-candidate`

Output statuses:

- `reject`
- `park`
- `watchlist`
- `proof-card`
- `PRD-lite`

The baseline deep-review layer creates an opportunity card with:

- project identity and ledger links
- target buyer, painful job, product angle, derivative mode
- strongest pain/money/lane signals
- what to take and what not to copy
- scoring blocks
- missing evidence
- risk hints
- recommended next validation step
- kill criteria

`proof-card` requires money and pain signals, strict Filter v3 score `>=27/34`,
and no missing-evidence item whose `blocking_for` includes `proof-card`. A
high-severity missing field blocks earlier, but medium fields such as
support-load or license clarity can also block proof-card promotion when they
are explicitly marked as proof blockers.
Stars and forks remain discovery evidence, not money evidence.

Use `--max-candidates` for weekly runs when source collection is noisy. The
ranker prefers known license first, then strict Filter v3 score, stronger
review statuses, fewer high-severity missing fields, more money and pain
signals, active source lanes, and GitHub candidates over lower-context source
records. This cap limits expensive council packet generation; it does not
delete candidates from the ledger.

## Council Packet Contract

Council packets are generated for candidates that remain `watchlist` or become
`proof-card` after deep review.

Lanes:

- `market-payment`
- `pain-signal`
- `distribution-first-100`
- `buildability-support`
- `legal-platform-risk`
- `skeptic-kill`

Each packet includes:

```yaml
packet_id:
candidate_id:
card_id:
lane:
objective:
evidence_packet:
do:
do_not:
required_output:
  candidate_id:
  lane:
  verdict: pass | caution | veto | unknown
  confidence: low | medium | high
  strongest_evidence:
  missing_evidence:
  reason_codes:
  next_check:
  notes:
```

Subagents should receive exactly one packet and return exactly one finding. They
should not see other lane conclusions before aggregation.

## Council Finding Schema

Input rows for `council-aggregate`:

```json
{
  "candidate_id": "cand_x",
  "packet_id": "pkt_x",
  "lane": "market-payment",
  "verdict": "pass",
  "confidence": "high",
  "strongest_evidence": ["Paid hosted analog exists."],
  "missing_evidence": [],
  "reason_codes": ["money-nearby"],
  "next_check": "Confirm pricing page.",
  "notes": "unknown"
}
```

The CLI validates lane, verdict, and confidence values before writing findings
to `ledger/council_findings.jsonl`.

## Aggregation Rules

The aggregator does not average lane opinions.

- First-payment-calls veto -> `reject`.
- Legal/platform veto -> `park`.
- Any high-confidence veto -> `reject`.
- Pass plus veto on the same candidate -> conflict recorded, not smoothed away.
- Pass and veto inside the same lane -> lane conflict recorded.
- `proof-card` requires strict Filter v3 score `>=27/34`.
- `proof-card` requires a `market-payment` pass.
- Strong findings with unresolved gaps remain `watchlist`.
- Operator personal fit is not inferred.

Aggregation output:

```yaml
aggregation_id:
candidate_id:
card_id:
accepted_findings:
rejected_findings:
conflicts:
vetoes:
missing_evidence:
final_machine_verdict:
reason_codes:
recommended_next_action:
telegram_summary:
ledger_links:
```

## Verification

```bash
python3 -m py_compile scripts/opportunity_scanner.py tests/test_opportunity_scanner.py
python3 -m unittest discover -s tests
```

Covered invariants:

- deep review creates an opportunity card and all six council packets
- `watchlist-candidate` can become `proof-card`
- council findings are structured and validated
- legal/platform veto parks the candidate
- veto plus pass records conflicts
- proof-card cannot be produced without a market/payment pass
