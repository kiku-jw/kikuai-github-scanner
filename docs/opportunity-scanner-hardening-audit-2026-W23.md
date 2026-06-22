# Opportunity Scanner Hardening Audit - 2026-W23

## Input

First controlled live scan:

- Week: `2026-W23`
- Candidates: `21`
- Sources: `github-search`, `gitlab-search`
- Original machine outcomes: `4` `proof-card`, `7` `watchlist`, `10` `park`
- Telegram digest delivery: sent after `.env` setup

## Findings

### Finding 1 - Fixed

The baseline deep-review layer promoted candidates to `proof-card` when money
and pain signals existed and there were no high-severity missing fields. This
was too generous because several candidates still had medium evidence gaps
explicitly marked as blocking for `proof-card`, especially support-load
unknowns.

Fix:

- `opportunity_scores` now records `missing_proof_blocking`.
- `opportunity_verdict` adds `proof-card-blocked-by-missing-evidence` when any
  missing-evidence item blocks `proof-card`.
- Baseline `proof-card` requires money signals, pain signals, no high missing
  evidence, and no proof-card-blocking missing evidence.

Expected effect:

- Thin heuristic deep-review should keep more candidates in `watchlist`.
- `proof-card` should become a council-backed or evidence-complete state, not a
  loose repo-description outcome.

### Finding 2 - Needs Follow-Up

GitLab search produced parked or low-context candidates in this scan. The source
is not useless, but the current generic searches are weaker than GitHub search
queries for this task.

Recommended action:

- Down-rank GitLab in weekly scans until source-specific queries improve.
- Keep GitLab caps low.
- Require stronger GitLab project text or issue evidence before deep review.

### Finding 3 - Fixed / Monitor

The deep-review baseline processed every candidate that weak labeling routed to
review, producing many council packets. This is acceptable for a small scan, but
will be too noisy for weekly runs.

Fix:

- `deep-review --max-candidates <N>` now caps the ranked review queue.
- Ranking prefers known license first, then stronger review statuses, fewer
  high-severity missing fields, money and pain signals, active source lanes, and
  GitHub source records.

Recommended action:

- Use `deep-review --max-candidates 5` for the next controlled weekly scan.
- Keep uncapped deep review only for small manual fixtures or explicit audits.

## Next Step

Run council lanes only on the best watchlist candidates from the hardened
output. Promote to `proof-card` only after `market-payment`, `pain-signal`, and
`legal-platform-risk` are clear enough for a seven-day proof.
