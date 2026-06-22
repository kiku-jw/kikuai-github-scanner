# Opportunity Scanner Weak Labeling And Triage

## Purpose

Phase 3 compresses noisy candidate evidence into labels, missing-evidence
checks, uncertainty notes, and a cheap triage recommendation. It is intentionally
not a final judge.

The current implementation uses a deterministic heuristic baseline:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 label
```

Run it after `run --input ...` or `github-search --ingest`.

## Files

```text
data/
  ledger/labels.jsonl
  ledger/events.jsonl
  reports/YYYY-WW-batch-report.md
```

`labels.jsonl` stores the weak-label payload. `events.jsonl` stores only the
queue triage transition.

## State Contract

Layer 4 processing labels are not global candidate statuses. Do not write
statuses such as `llm-labeled` or `llm-low-confidence` into the main status
timeline.

Allowed Phase 3 triage statuses:

- `needs-evidence`
- `codex-review`
- `watchlist-candidate`

`machine-reject` can only be created by `layer=deterministic-prefilter`.
Candidates already in `machine-reject` are skipped by the label command.

Low-confidence labels cannot downgrade an existing `codex-review`,
`watchlist-candidate`, `watchlist`, `proof-card`, or `PRD-lite` status.

## Label Schema

Each label row contains:

- `label_id`
- `candidate_id`
- `created_at`
- `actor`
- `layer`
- `model`
- `confidence`
- `confidence_score`
- `summary`
- `product_angles`
- `buyer_labels`
- `pain_phrases`
- `money_signals`
- `risk_hints`
- `missing_evidence`
- `inferred_fields`
- `uncertainty_notes`
- `status_recommendation`
- `reason_codes`

Every `inferred_fields` entry has:

```json
{
  "value": "unknown",
  "confidence": "none",
  "evidence_refs": [],
  "unknown_allowed": true
}
```

Known fields may use `low`, `medium`, or `high` confidence and must reference
the candidate evidence file. Unknown is valid output; the labeler must not
invent buyers, payment signals, support load, or distribution evidence.

## Missing Evidence Schema

Each missing-evidence item has:

```json
{
  "type": "target_buyer",
  "field": "target_buyer",
  "severity": "high",
  "blocking_for": ["watchlist-candidate", "proof-card"],
  "next_check": "Find public evidence for target buyer.",
  "unknown_allowed": true
}
```

High-severity missing fields are buyer, painful job, and monetization. Medium
fields are distribution, support load, license, and demo/proof. Triage must
prefer severity and blockingness over a raw missing-field count.

## Prompt Contract For Future Weak LLM

Use this when replacing the heuristic baseline with Gemini or another cheap
model:

```text
You label OSS opportunity candidates for a no-call solo-founder scanner.

Input: one candidate with raw public evidence, current deterministic status,
reason codes, and evidence refs.

Task: return only valid JSON matching the Phase 3 label schema.

Rules:
- Preserve uncertainty. Unknown is better than a confident guess.
- Every inferred field must include value, confidence, evidence_refs, and
  unknown_allowed.
- Use only supplied evidence. Do not infer a buyer, willingness to pay, legal
  safety, or support load from popularity alone.
- You may recommend needs-evidence, codex-review, or watchlist-candidate.
- You may not recommend reject, park, proof-card, PRD-lite, or machine-reject.
- If evidence is thin or conflicting, use confidence=low and recommend
  needs-evidence unless an existing stronger status must be preserved.
- Do not judge Operator's personal fit.
- Do not produce a PRD, build recommendation, or final business verdict.
```

Invalid or partial LLM output must be converted to low-confidence
`needs-evidence` while preserving candidate visibility.

## Report Additions

The weekly report now includes:

- weak label confidence
- weak summary
- missing evidence
- uncertainty
- triage rationale
- next evidence check

These fields are there so weak-label damage is visible during review instead of
hidden behind a single queue status.

## Verification

```bash
python3 -m py_compile scripts/opportunity_scanner.py tests/test_opportunity_scanner.py
python3 -m unittest discover -s tests
```

Covered invariants:

- weak layer writes no `machine-reject` events
- unknown fields remain explicit
- sparse rescue candidates stay visible
- low-confidence labels do not downgrade existing review statuses
- forbidden weak statuses fall back safely
