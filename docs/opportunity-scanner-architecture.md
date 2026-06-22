# Opportunity Scanner Architecture

## Goal

Run a weekly local opportunity scan that preserves raw evidence, avoids early
false negatives from weak models, and escalates only the best candidates to
deep Codex review, clean-context subagents, and Operator's personal-fit gate.

## Design Principle

Early layers compress and label. They do not kill ideas except for deterministic
hard gates. Weak LLMs are classifiers, not final judges.

## Control Plane Decision

Do not use Paperclip as the first control plane. Use a local file-based ledger
plus explicit status transitions. See `docs/adr/ADR-001-no-paperclip-control-plane.md`.

For the detailed post-search pipeline, use
`docs/opportunity-scanner-post-search-layers.md`. That document defines the
layers after candidate discovery and intentionally leaves searcher design out.

## Pipeline

1. **Weekly local collector**
   - Runs on a schedule.
   - Pulls candidates from configured sources.
   - Stores raw repo, issue, discussion, marketplace, and market evidence.

2. **Deterministic prefilter**
   - Removes only obvious hard failures.
   - Examples: missing source URL, banned category, clear scam, no usable data,
     incompatible license for the selected angle when that is already certain.
   - Does not score taste, market quality, or personal fit.

3. **Weak LLM labeling layer**
   - Uses a cheap model to label and summarize.
   - Allowed outputs: tags, uncertainty, missing fields, reason hints.
   - Not allowed: final reject, machine reject creation, personal-fit judgment,
     or queue-status downgrade.
   - Unknowns are preserved, not converted into confident negatives.
   - Stores label payloads separately from queue status events.
   - Must preserve search-lane tags such as `active-abandoned-forks`,
     `cli-to-ui-gap`, `commercial-intent-density`, and
     `academic-hobbyist-bias`.

4. **Candidate ledger**
   - Stores every candidate as JSONL or Markdown.
   - Keeps `raw_evidence` separate from `interpreted_signals`.
   - Keeps reason codes and status transitions.
   - Allows rescoring old candidates when the filter changes.

5. **Codex weekly deep pass**
   - Reads accumulated candidates.
   - Performs deeper enrichment and Opportunity Filter v3 strict scoring.
   - Promotes candidates to `watchlist`, `proof-card`, or `park`.

6. **Clean-context subagent review**
   - Runs only on remaining strong candidates.
   - Each subagent gets one bounded review lane:
     - license and rights
     - market and payment evidence
     - support and buildability
     - distribution and first 100 reachability
   - Subagents return structured findings, not broad opinions.

7. **Aggregator**
   - Merges subagent findings.
   - Emits one verdict per candidate:
     `reject`, `park`, `watchlist`, `proof-card`, or `PRD-lite`.
   - Requires reason codes for all rejects and parks.

8. **Telegram digest**
   - Sends a short human weekly shortlist.
   - Shows at most five ready candidates: `proof-card`, `PRD-lite`, or
     `operator-proof-approved`; watchlist stays local-only.
   - Excludes raw candidates, parks, rejects, ids, ledger paths, and reason-code
     dumps by default.

9. **Operator personal-fit gate**
   - Operator reviews candidates for:
     - personal interest
     - "I would use this"
     - style fit
     - likelihood not to abandon
     - spiritual/ethical/taste discomfort
   - This gate is not delegated to the machine.

10. **Codex follow-up**
    - Operator brings reactions back to Codex.
    - Codex updates filters, writes proof-cards, or shapes PRD-lite artifacts.

## Status Model

- `raw`: collected but not enriched.
- `machine-reject`: deterministic hard gate only.
- `needs-evidence`: visible candidate with insufficient public evidence.
- `codex-review`: requires deep review.
- `watchlist-candidate`: strong weak-label or rescue signal before deep review.
- `watchlist`: promising, one major gap remains.
- `proof-card`: ready for a bounded seven-day proof.
- `PRD-lite`: proof exists and scoped implementation is now the blocker.
- `park`: blocked by timing, rights, channel, platform, or buyer uncertainty.
- `reject`: decisive hard failure with reason code.

Weak-model processing state lives in `labels.jsonl` as `confidence`,
`uncertainty_notes`, and `status_recommendation`; it is not a global status.

## Rescue Lane

A candidate must not be discarded by weak-model scoring if it has any strong
rescue signal:

- repeated install, deploy, docs, hosted, cloud, API, UI, dashboard, extension,
  integration, template, or one-click-deploy pain
- useful CLI/library with no serious UI, dashboard, extension, bot, or hosted
  workflow surface
- compatible license for a clean derivative angle
- paid competitors or other money evidence
- high commercial-intent density around hosted, managed, cloud, pricing,
  support, deploy, or paid-version language
- recurring use
- active forks around an abandoned project
- clear self-serve distribution surface
- strong personal-fit note from Operator

Rescued candidates go to `watchlist` or `codex-review`, not `reject`.
`academic-hobbyist-bias` is a soft demotion, not a weak-model reject reason,
unless a deterministic hard gate also fires.

## First MVP

Build the scanner in this order:

1. Weekly local script.
2. JSONL/Markdown candidate ledger.
3. Deterministic prefilter.
4. Weak LLM labels.
5. Manual or Codex-triggered deep pass.
6. Telegram digest.
7. Clean-context subagents only after the report format and ledger prove useful.

Do not start with full agent orchestration. The ledger is the durable asset.

## Invariants

- Raw evidence is immutable after capture.
- Interpretations can be regenerated.
- Scoring can be recalculated after filter changes.
- Weak LLMs cannot final-reject without a hard gate.
- Only `layer=deterministic-prefilter` may create `machine-reject`.
- Every reject has a reason code.
- Every proof-card has a bounded proof and kill criterion.
- Operator's personal-fit gate happens before PRD-lite.
