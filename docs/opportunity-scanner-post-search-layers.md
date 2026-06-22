# Opportunity Scanner Post-Search Layers

## Scope

This document designs every layer after candidate discovery. It deliberately
does not define the searcher, source queries, or harvesting strategy. The
searcher only has to provide candidate records that satisfy the intake contract.

## Control Plane

Use a local file-based ledger as the control plane. Do not use Paperclip for the
first version. The system should optimize for auditability, cheap iteration,
and low operational drag.

Default path:

```text
searcher output
  -> intake normalizer
  -> immutable raw ledger
  -> deterministic prefilter
  -> weak LLM labeler
  -> batch triage
  -> Codex deep pass
  -> council review for shortlist
  -> aggregator
  -> Telegram digest
  -> Operator personal-fit gate
  -> Codex proof-card / PRD-lite follow-up
```

## Input Contract From Searcher

Each candidate handed to the post-search pipeline must include enough raw data
to avoid immediate re-search.

```yaml
candidate_id:
observed_at:
source:
source_url:
project_url:
project_name:
repository:
repo_key:
fork_family_key:
license:
short_description:
raw_metadata:
raw_text:
  readme_excerpt:
  issue_excerpts:
  discussion_excerpts:
  marketplace_or_store_text:
  external_mentions:
search_lanes:
  active_abandoned_forks:
  cli_to_ui_gap:
  commercial_intent_density:
  academic_hobbyist_bias:
collector_notes:
```

`candidate_id` should be deterministic from normalized `fork_family_key` when
available, then `repo_key`, then normalized `project_url`. It must not depend on
the discovery source. If the same project appears from multiple sources, or a
fork appears inside an already known fork family, merge it into one candidate
with multiple evidence entries.

## Layer 1: Intake Normalizer

Purpose: convert searcher output into stable candidate records.

Responsibilities:

- Normalize URLs, names, source labels, license strings, timestamps, repo keys,
  fork-family keys, and tags.
- Assign deterministic `candidate_id`.
- Deduplicate same project across sources and merge fork-family observations.
- Store missing fields as `unknown`, not guessed values.
- Preserve all raw evidence chunks with source URLs.

Forbidden:

- No scoring.
- No final reject.
- No rewriting raw evidence into conclusions.

Output status: `raw`.

## Layer 2: Immutable Raw Ledger

Purpose: keep evidence durable so filters can change without losing old
candidates.

Recommended layout:

```text
data/
  raw/YYYY-WW/candidates.jsonl
  ledger/candidates.jsonl
  ledger/events.jsonl
  ledger/evidence/
    <candidate_id>.md
```

Ledger rules:

- Raw evidence is append-only.
- Interpretations live separately from raw evidence.
- Every status change writes an event.
- Every reject, park, rescue, and promotion has a reason code.
- Old candidates can be rescored when filter rules change.

## Layer 3: Deterministic Prefilter

Purpose: remove only obvious hard failures before spending LLM/Codex time.

Allowed reject reasons:

- `missing-url`
- `banned-category`
- `clear-scam`
- `no-usable-data`
- `known-incompatible-license`
- `unauthorized-security-testing`
- `copied-brand-or-assets`
- `first-payment-requires-calls`

Rules:

- This layer can produce `machine-reject` only for deterministic hard gates.
- It cannot reject for weak monetization, taste, low stars, boring category, or
  uncertain market.
- If a candidate has any rescue lane, move it to `prefilter-pass` unless a hard
  gate is certain.

## Layer 4: Weak LLM Labeler

Purpose: compress noisy text into tags and missing-field hints.

Allowed outputs:

- short candidate summary
- inferred product angle candidates
- search-lane tags
- pain phrases
- possible buyer labels
- possible money signals
- risk hints
- missing evidence list
- uncertainty notes

Forbidden:

- No final reject without a deterministic hard gate.
- No confident conclusions from thin evidence.
- No personal-fit judgment.
- No PRD or build recommendation.

Output storage:

- `data/ledger/labels.jsonl` label payloads.
- `weak-label-triage` events for queue routing.

Layer 4 processing states such as `llm-labeled` or `llm-low-confidence` must
not be written as global candidate statuses. They belong inside the label
payload as confidence and uncertainty fields.

## Layer 5: Batch Triage

Purpose: rank batches cheaply before deep Codex review.

Triage inputs:

- deterministic hard gate result
- weak LLM labels
- Opportunity Filter v3 strict scoring fields
- rescue signals
- missing evidence count

Outputs:

- `machine-reject`: hard gate only
- `needs-evidence`: promising but too thin
- `codex-review`: enough signal for deep review
- `watchlist-candidate`: strong rescue or pain signal

Triage rule: only `layer=deterministic-prefilter` may create
`machine-reject`. Weak labels can only route visible candidates to
`needs-evidence`, `codex-review`, or `watchlist-candidate`; low-confidence
labels must not downgrade an existing review status.

Triage should prefer false positives over false negatives. It is cheaper for
Codex to kill a few weak candidates than to lose a weird strong one early.

## Layer 6: Codex Deep Pass

Purpose: turn machine labels into real opportunity cards.

Responsibilities:

- Verify the most important current facts from primary/public sources.
- Separate repo popularity from money evidence.
- Score the candidate with Opportunity Filter v3.
- Decide whether council review is worth the cost.
- Produce one of: `reject`, `park`, `watchlist`, `proof-card-candidate`.

Codex may reject candidates, but only with explicit reason codes and evidence.
The local baseline writes opportunity cards to
`data/ledger/opportunity_cards.jsonl` and writes `codex-deep-pass` events.

## Layer 7: Council Review On Shortlist

Purpose: use clean-context subagents only where judgment quality matters.

Run council only for:

- `proof-card-candidate`
- high-upside `watchlist`
- candidates with strong conflict between pain, market, license, and support

Default council lanes:

| Lane | Question | Output |
| --- | --- | --- |
| `market-payment` | Is money nearby and who pays? | paid analogs, payer, pricing angle, money-confidence |
| `pain-signal` | Is the pain real, repeated, and urgent? | pain evidence, weak signals, strongest quotes |
| `distribution-first-100` | Can the first 100 be reached without calls? | exact channels, prospect source, spam risk |
| `buildability-support` | Can an MVP avoid support traps? | MVP shape, support risks, cost caps |
| `legal-platform-risk` | Is the product angle clean enough? | license, ToS, API/platform, clone-risk verdict |
| `skeptic-kill` | Why should this be killed? | decisive objections, missing proof, kill test |

Council packet contract:

```yaml
candidate_id:
lane:
objective:
evidence_packet:
do:
do_not:
required_output:
  verdict: pass | caution | veto | unknown
  confidence: low | medium | high
  strongest_evidence:
  missing_evidence:
  reason_codes:
  next_check:
```

Subagents must return structured findings, not broad opinions. They should not
see each other's conclusions until aggregation.

The local baseline writes packet rows to `data/ledger/council_packets.jsonl`.
Each subagent should receive one packet and return one council finding row.

## Layer 8: Aggregator

Purpose: synthesize council findings into one operational verdict.

Aggregation rules:

- Legal/platform hard veto can reject or park.
- First-payment calls/custom consulting veto rejects.
- No money signal outside repo popularity prevents `proof-card`.
- Strong pain plus weak distribution becomes `watchlist`, not `proof-card`.
- Strong market plus high support risk becomes `park` or `watchlist`.
- Conflicting council findings require source inspection before final verdict.
- Operator personal-fit is not inferred by the aggregator.
- A `proof-card` requires a `market-payment` pass.
- Council findings are written to `data/ledger/council_findings.jsonl`.
- Aggregations are written to `data/ledger/aggregations.jsonl`.

Output fields:

```yaml
candidate_id:
accepted_findings:
rejected_findings:
conflicts:
vetoes:
missing_evidence:
final_machine_verdict:
recommended_next_action:
telegram_summary:
```

## Layer 9: Digest And Telegram Outbox

Purpose: keep a technical audit report locally and give Operator a compact weekly
Telegram review surface.

Technical report sections:

- top `proof-card` candidates
- `watchlist` candidates
- parked candidates with revisit trigger
- compact rejects by reason code
- filter drift notes

Each serious report candidate should include:

- one-line product angle
- buyer and painful job
- strongest money/pain signal
- biggest risk or veto
- next proof action
- link to ledger entry

Telegram outbox rules:

- maximum five candidates
- only `proof-card`, `PRD-lite`, or `operator-proof-approved` candidates
- no watchlist fallback; if none pass, send a short "no ready ideas" status
- no raw candidates, parks, rejects, candidate ids, ledger paths, or reason-code
  dumps
- include strict score, buyer, pain, angle, money signal, first-100 lane, main
  blocker, and next action

The local baseline writes:

- `data/reports/YYYY-WW-digest.md`
- `data/outbox/telegram/YYYY-WW-digest.md`

The outbox file is the Telegram delivery hook. It is intentionally shorter than
the local report.

## Layer 10: Operator Personal-Fit Gate

Purpose: preserve the human-only filters.

Operator decides:

- Would I use this?
- Do I care enough not to abandon it?
- Does this fit my autonomous work style?
- Is there taste, ethical, spiritual, or personal discomfort?
- Would I rather spend a week proving this than another candidate?

Allowed outcomes:

- `operator-reject`
- `operator-park`
- `operator-watchlist`
- `operator-proof-approved`
- `filter-update-needed`

Every Operator decision writes a `operator-feedback` event plus a row in
`data/ledger/operator_decisions.jsonl`. Reusable decisions also write an open row to
`data/ledger/filter_updates.jsonl`.

## Layer 11: Codex Follow-Up

Purpose: convert Operator's reaction into a bounded next artifact.

If Operator approves proof:

- write a seven-day proof-card
- define success metric and kill criterion
- define cost caps
- define exact async channel
- define what not to build

If Operator rejects or parks:

- write reason code
- update filter if the reason is reusable
- preserve candidate for future rescoring only when appropriate

If proof succeeds:

- promote to `PRD-lite`
- keep scope narrow
- do not create a SaaS shell unless the proof demands it

## Minimum MVP Without Searcher

Build these pieces before improving the searcher:

1. Ledger directory and candidate schema.
2. Deterministic prefilter reason codes.
3. Weak LLM label schema and prompt.
4. Batch triage report.
5. Council packet templates.
6. Aggregator report format.
7. Telegram digest markdown format.
8. Operator personal-fit response format.

Searcher quality matters, but the post-search pipeline must first prove that it
can preserve, rescue, rank, and explain candidates without becoming a noisy
automation factory.
