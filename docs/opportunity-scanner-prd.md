# Opportunity Scanner MVP PRD

## Overview

- **Product Name:** Opportunity Scanner
- **Author:** Operator / Codex
- **Date:** 2026-06-02
- **Status:** Draft
- **MVP Deadline:** [TBD]

## 1. Problem Statement

Operator wants a repeatable way to discover OSS and public-product opportunities
that could plausibly become autonomous, no-call, self-serve income experiments:
wrappers, hosted versions, dashboards, bots, browser extensions, templates,
mobile apps, maintained forks, and clean analogs.

Current discovery is too manual and inconsistent:

- Deep research reports may lose real URLs or mix stale and live evidence.
- GitHub/GitLab popularity is easy to collect but weak as money evidence.
- Weak models can prematurely kill unusual candidates.
- Criteria drift between chats unless stored in durable docs.
- There is no durable candidate ledger that preserves raw evidence and allows
  rescoring when filters improve.

The MVP must not predict guaranteed income. It must preserve evidence, reduce
noise, rescue weird-but-promising candidates, and produce a small weekly digest
of ideas worth human review or seven-day proof.

## 2. Target Users

### Pilot Segment

- Operator as solo operator and final personal-fit reviewer.
- Codex as deep reviewer, PRD/proof-card shaper, and filter updater.
- Optional clean-context subagents as bounded reviewers or implementers after
  contracts are stable.

### Not For MVP

- External users.
- Enterprise teams.
- General market-intelligence dashboards.
- Fully autonomous product launch, trading, or bug-bounty execution.
- Any flow requiring calls, custom sales, hidden delegation, private data, or
  unauthorized security testing.

## 3. Proposed Solution

Build a local weekly pipeline:

```text
source searcher
  -> intake normalizer
  -> immutable candidate ledger
  -> deterministic prefilter
  -> weak LLM labeler
  -> batch triage
  -> Codex deep pass
  -> optional clean-context council on shortlist
  -> aggregator
  -> Telegram/Markdown digest
  -> Operator personal-fit gate
  -> proof-card or PRD-lite follow-up
```

The MVP starts with a file-based ledger and a thin vertical slice. It should
work even when the searcher is primitive or candidates are manually supplied.
Searcher quality improves later, but the durable asset is the ledger plus
repeatable scoring and review contracts.

## 4. Goals

- Preserve raw candidate evidence with source URLs and timestamps.
- Keep raw evidence separate from model interpretation and human verdicts.
- Reject only deterministic hard failures before deep review.
- Use weak LLMs for labels, summaries, uncertainty, and missing-evidence hints,
  not final judgment.
- Apply Opportunity Filter v2 consistently.
- Produce a compact weekly digest with ranked candidates and next actions.
- Capture Operator's personal-fit response and feed it back into filters.
- Support clean-context subagent review for shortlist candidates without making
  agent orchestration the control plane.

## 5. Scope

| IN (MVP) | OUT (Post-MVP) |
| --- | --- |
| Local file-based data layout | Hosted SaaS dashboard |
| Candidate schema and append-only ledger | Multi-user accounts |
| Manual or scripted candidate ingestion | Billing, auth, public product UI |
| GitHub-first source support | Full GitLab parity on day one |
| Deterministic hard-gate prefilter | Autonomous build/deploy of product ideas |
| Weak LLM labels with no final-reject power | Weak model as final opportunity judge |
| Batch triage report | Complex queue engine |
| Codex deep-pass packet format | Paperclip as default runtime |
| Council packet templates | Generic dynamic workflow dependency |
| Aggregated weekly Markdown digest | Always-on agent swarm |
| Telegram delivery hook when ready | Real-time monitoring dashboard |
| Operator personal-fit response format | Delegating personal taste/ethics/style fit |
| Seven-day proof-card handoff | Long PRD before proof evidence exists |

## 6. P0 Requirements

- **P0-001 Candidate Schema:** The system shall store each candidate with a
  deterministic `candidate_id`, source URLs, observed timestamp, raw metadata,
  raw text excerpts, `repo_key`, `fork_family_key`, search-lane tags, and
  collector notes.
- **P0-002 Append-Only Ledger:** The system shall preserve raw candidate
  evidence append-only and store interpretations/status events separately.
- **P0-003 Dedupe:** The intake normalizer shall merge duplicate candidates
  from multiple sources by normalized `repo_key` and `fork_family_key`, not by
  source-specific observation URL.
- **P0-004 Deterministic Prefilter:** The prefilter may reject only documented
  hard gates such as missing URL, banned category, clear scam, no usable data,
  known incompatible license, unauthorized security testing, copied brand/assets,
  or first payment requiring calls.
- **P0-005 Rescue Lane:** The prefilter shall rescue candidates with strong
  signals such as active abandoned forks, CLI-to-UI gap, commercial-intent
  density, setup pain, hosted-version requests, or paid analogs unless a certain
  hard gate fires.
- **P0-006 Weak LLM Labeling:** The weak model shall output labels, summaries,
  possible buyers, pain phrases, risk hints, missing evidence, and uncertainty
  into a separate label payload. Every inferred field shall preserve
  `unknown`, confidence, and evidence refs.
- **P0-007 Batch Triage:** The system shall classify candidates into
  `machine-reject`, `needs-evidence`, `codex-review`, or
  `watchlist-candidate` before expensive review. Only deterministic hard gates
  may create `machine-reject`; weak-label triage cannot final-reject.
- **P0-008 Opportunity Scoring:** The Codex deep pass shall apply Opportunity
  Filter v3 strict `0..2` scoring and keep repo popularity separate from money
  evidence. Unknown proof, distribution, support, cost, rights, or unit
  economics answers score as zero.
- **P0-009 Council Packets:** The system shall provide structured packet
  templates for `market-payment`, `pain-signal`, `distribution-first-100`,
  `buildability-support`, `legal-platform-risk`, and `skeptic-kill` lanes.
- **P0-010 Aggregator:** The aggregator shall merge Codex and council findings
  into one verdict per candidate with accepted findings, rejected findings,
  conflicts, vetoes, missing evidence, reason codes, and next action.
- **P0-011 Digest:** The local technical weekly digest shall show proof-card
  candidates, watchlist candidates, parks, compact rejects by reason code, and
  links back to ledger/evidence files. The Telegram outbox shall be a separate
  human decision feed capped to `proof-card`, `PRD-lite`, or
  `operator-proof-approved` candidates. It shall not include watchlist fallback
  candidates and shall exclude raw candidates, parks, rejects, ids, ledger paths,
  and reason-code dumps.
- **P0-012 Personal-Fit Gate:** The system shall capture Operator-only outcomes:
  `operator-reject`, `operator-park`, `operator-watchlist`, `operator-proof-approved`, or
  `filter-update-needed`.
- **P0-013 Filter Updates:** When Operator rejects or parks for a reusable reason,
  Codex shall update the filter or reason-code vocabulary instead of losing the
  lesson in chat.

## 7. P1 Requirements

- **P1-001 GitHub Source MVP:** Add GitHub API/GraphQL source collection for
  repo metadata, fork/source metadata, issues, discussions when available,
  stars/forks/activity, and candidate search lanes.
- **P1-002 GitLab Source MVP:** Add GitLab project/search support after GitHub
  source logic is stable.
- **P1-003 Curated Source Lane:** Ingest curated lists, awesome lists, trend
  reports, marketplace pages, and manually pasted research reports.
- **P1-004 Repo Digest Enrichment:** Use a repo digest tool on shortlist
  candidates so LLM review sees structure without loading entire repositories.
- **P1-005 Telegram Bot Feedback:** Allow Operator to mark digest items directly
  from Telegram and write the response back to ledger events.
- **P1-006 Calibration Report:** Track which source lanes and scoring signals
  actually lead to proof-cards, rejects, and filter updates.
- **P1-007 Checked Registry And Projects Mirror:** Keep the local ledger as the
  source of truth for checked repositories and optionally mirror review state to
  GitHub Projects as an operator board.

## 8. User Stories

- As Operator, I want a weekly digest of evidence-backed ideas so I can review a
  few candidates instead of manually scanning GitHub/GitLab.
- As Operator, I want weird candidates rescued when they show money/pain signals so
  weak models do not delete the interesting edge cases.
- As Operator, I want each candidate linked to raw evidence so I can audit why it
  was promoted, parked, or rejected.
- As Operator, I want personal-fit decisions captured separately so the machine
  learns my taste without pretending to own it.
- As Codex, I want stable candidate packets so I can run deep review and
  subagent councils without rebuilding context every time.
- As a future implementation agent, I want small layer contracts and fixtures so
  each pipeline layer can be implemented and tested independently.

## 9. Data Contracts

### Candidate Input

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

### Candidate Event

```yaml
event_id:
candidate_id:
created_at:
actor:
layer:
from_status:
to_status:
reason_codes:
evidence_refs:
notes:
```

### Weak Label

```yaml
label_id:
candidate_id:
created_at:
actor:
layer:
model:
confidence:
confidence_score:
summary:
product_angles:
buyer_labels:
pain_phrases:
money_signals:
risk_hints:
missing_evidence:
  - type:
    field:
    severity:
    blocking_for:
    next_check:
    unknown_allowed:
inferred_fields:
  target_buyer:
    value:
    confidence:
    evidence_refs:
    unknown_allowed:
uncertainty_notes:
status_recommendation:
reason_codes:
```

### Final Candidate Verdict

```yaml
candidate_id:
final_verdict: reject | park | watchlist | proof-card | PRD-lite
accepted_findings:
rejected_findings:
conflicts:
vetoes:
missing_evidence:
scores:
reason_codes:
recommended_next_action:
telegram_summary:
ledger_links:
```

### Opportunity Card

```yaml
card_id:
candidate_id:
created_at:
actor:
layer:
source_status:
project_name:
project_url:
license:
target_buyer:
painful_job:
current_workaround:
product_angle:
derivative_mode:
what_to_take:
what_not_to_copy:
strongest_signals:
scores:
missing_evidence:
risk_hints:
verdict_recommendation:
reason_codes:
rationale:
next_validation_step:
kill_criteria:
ledger_links:
```

### Council Packet

```yaml
packet_id:
candidate_id:
card_id:
created_at:
lane:
objective:
evidence_packet:
do:
do_not:
required_output:
```

### Council Finding

```yaml
finding_id:
candidate_id:
packet_id:
created_at:
actor:
lane: market-payment | pain-signal | distribution-first-100 | buildability-support | legal-platform-risk | skeptic-kill
verdict: pass | caution | veto | unknown
confidence: low | medium | high
strongest_evidence:
missing_evidence:
reason_codes:
next_check:
notes:
```

### Council Aggregation

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

### Operator Decision

```yaml
decision_id:
candidate_id:
created_at:
actor:
decision: operator-reject | operator-park | operator-watchlist | operator-proof-approved | filter-update-needed
reason_codes:
notes:
reusable_filter_update:
filter_update:
```

### Filter Update

```yaml
update_id:
candidate_id:
created_at:
source_decision_id:
reason_codes:
proposed_change:
target_doc:
notes:
status:
```

## 10. Subagent And Council Policy

Subagents should improve judgment and isolation, not become a default swarm.

Use subagents when:

- A layer has a stable input/output contract.
- Work can be split without shared mutable state.
- A candidate reaches shortlist and needs independent lenses.
- A layer implementation needs skeptical review before integration.
- The cost of a false positive/negative is high enough to justify extra review.

Do not use subagents when:

- The schema is still changing rapidly.
- The task is a tiny mechanical edit.
- The same agent would need to coordinate across several unstable layers.
- The output cannot be tested by fixtures or acceptance checks.

Recommended model:

- Main Codex owns contracts, integration, verification, and final judgment.
- Subagents receive clean packets with one objective, one input contract, and
  one required output schema.
- Subagents do not see each other's conclusions before aggregation.
- The aggregator handles conflicts and vetoes; it does not average opinions.
- Legal/platform veto and first-payment-calls veto can park or reject.
- Operator's personal-fit gate is never delegated.

For implementation, start single-owner until the first vertical slice passes.
After that, use subagents per layer or as review lanes:

- `schema-ledger`
- `prefilter-rules`
- `source-github`
- `weak-llm-labeler`
- `digest-telegram`
- `council-review`
- `skeptic-integration-review`

## 11. Success Metrics

| Metric | Target | How Measured |
| --- | --- | --- |
| Candidate preservation | 100% of accepted source candidates have raw evidence refs | Ledger audit |
| Premature weak-model rejects | 0 final rejects by weak LLM without hard gate | Event log audit |
| Weekly digest size | Telegram shortlist stays reviewable in <= 5 minutes | Operator feedback |
| Evidence quality | Every proof-card candidate has at least one money signal outside repo popularity | Opportunity card audit |
| Personal-fit loop | Every Operator decision creates a ledger event | Event log audit |
| Proof-card throughput | [TBD] proof-card candidates per 4 weekly scans | Calibration report |
| False-positive tolerance | [TBD] acceptable weak candidates reaching Codex review | Calibration report |

## 12. Risks

- **Searcher noise:** Too many weak candidates can bury the useful ones.
  Mitigation: lane-specific source caps, deterministic prefilter, batch triage.
- **Weak LLM false negatives:** Cheap models can confidently reject unusual
  ideas. Mitigation: no final-reject power without hard gates.
- **Agent orchestration drag:** Too many subagents can create integration
  overhead. Mitigation: stable contracts first, subagents only on bounded lanes.
- **Licensing/platform mistakes:** Derivative opportunities can cross legal or
  ToS boundaries. Mitigation: legal/platform council lane and hard vetoes.
- **Support traps:** Hosted or managed versions can become custom ops work.
  Mitigation: support burden scoring, infra cost caps, hard non-goals.
- **Chat-only drift:** Decisions disappear if not written down. Mitigation:
  append-only ledger, docs, ADRs, and filter updates.

## 13. Open Questions

- Exact MVP deadline.
- First GitHub source strategy and weekly candidate cap.
- Whether Telegram feedback should be P0 or P1 for the first local slice.
- Preferred local data path.
- Whether GitLab enters the first source MVP or waits until GitHub proves useful.
- Which weak model/provider will be used first.

## 14. Acceptance Criteria

The MVP is acceptable when:

- A manually supplied or scripted batch can move through intake, ledger,
  prefilter, weak labels, triage, Codex review, aggregation, and digest.
- At least one candidate can be promoted to `proof-card` with raw evidence,
  money signal, next action, and kill criterion.
- At least one weak candidate can be rejected with a deterministic reason code.
- A weak LLM cannot final-reject without a hard gate.
- Operator's personal-fit response writes back to the ledger.
- The pipeline can be rerun after a filter change without losing raw evidence.
