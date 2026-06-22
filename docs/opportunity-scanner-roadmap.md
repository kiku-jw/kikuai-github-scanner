# Opportunity Scanner Roadmap

## Roadmap Principle

Build the smallest vertical slice that preserves evidence and produces a useful
weekly decision surface. Do not optimize the searcher or agent orchestration
before the ledger, statuses, and report format prove useful.

## Phase 0 - Product Contracts

**Goal:** Freeze enough contracts to build without re-litigating architecture.

**Deliverables:**

- Candidate schema.
- Event schema.
- Ledger layout.
- Reason-code vocabulary.
- Status transition map.
- Sample candidate fixtures.
- Manual candidate intake format.

**Acceptance Gate:**

- A fake/manual candidate can be represented without losing raw evidence.
- Every status has one owner layer and allowed next statuses.
- Every reject requires a reason code.

**Subagent Use:**

- Use one skeptical review subagent or council pass to attack the schemas and
  status model.
- Do not split implementation yet.

## Phase 1 - Local Vertical Slice

**Goal:** Run one batch end to end without automated search.

**Deliverables:**

- Intake normalizer.
- Append-only raw ledger.
- Event ledger.
- Deterministic prefilter.
- Opportunity Filter v3 scoring shell.
- Markdown batch report.

**Acceptance Gate:**

- Manual candidates can become `machine-reject`, `needs-evidence`, or
  `codex-review`.
- Raw evidence remains immutable.
- Interpretations can be regenerated.
- The batch report explains why each candidate moved.

**Subagent Use:**

- Main Codex should implement this first slice directly.
- Use a subagent only for post-implementation review, not parallel build.

## Phase 2 - GitHub Source MVP

**Goal:** Add the first real source lane without making the system broad.

**Deliverables:**

- GitHub API/GraphQL collector for selected queries.
- Rate-limit-aware fetch policy.
- Repo metadata capture.
- Repo identity normalization into `repo_key` and `fork_family_key`.
- Issues/discussions excerpt capture when available.
- Search-lane tagging for:
  - `active-abandoned-forks`
  - `cli-to-ui-gap`
  - `commercial-intent-density`
  - `academic-hobbyist-bias`
- Source caps per weekly run.
- Local checked-registry lookup before deep review.
- Optional GitHub Projects mirror for status visibility after the local ledger
  is stable.

**Acceptance Gate:**

- One weekly run can collect candidates from GitHub and write valid candidate
  records.
- The collector does not depend on scraping private/authenticated data.
- Searcher output satisfies the post-search input contract.
- A repo found from multiple sources maps to one candidate.
- A fork maps to the same `fork_family_key` as its upstream and does not trigger
  a full duplicate review unless it adds a rescue signal.
- GitHub Projects is treated as a mirror/operator board, not the source of
  truth.

**Subagent Use:**

- Good candidate for a separate implementation subagent after Phase 0/1
  contracts are stable.
- Main Codex reviews API assumptions, rate limits, and output fixtures.

## Phase 3 - Weak LLM Labeling And Triage

**Goal:** Compress noisy text while preserving uncertainty and avoiding early
false negatives.

**Deliverables:**

- Weak LLM prompt.
- Label output schema.
- Missing-evidence schema.
- Triage policy.
- Audit check that weak LLM cannot final-reject except hard gates.

**Acceptance Gate:**

- Weak labels improve report readability.
- Unknown fields remain `unknown`, not invented.
- A low-confidence LLM result routes to `needs-evidence` or `codex-review`, not
  final reject.

**Subagent Use:**

- Use a prompt-review subagent to attack false-negative risk.
- Keep integration owned by main Codex.

## Phase 4 - Deep Review And Council Packets

**Goal:** Use expensive judgment only on the shortlist.

**Deliverables:**

- Codex deep-pass packet.
- Opportunity card output format.
- Council packet templates.
- Council lanes:
  - `market-payment`
  - `pain-signal`
  - `distribution-first-100`
  - `buildability-support`
  - `legal-platform-risk`
  - `skeptic-kill`
- Aggregator conflict/veto rules.

**Acceptance Gate:**

- A `watchlist-candidate` can become `reject`, `park`, `watchlist`,
  `proof-card`, or `PRD-lite`.
- Council outputs are structured and comparable.
- Aggregator records conflicts instead of smoothing them away.

**Subagent Use:**

- This is the highest-ROI place for subagents.
- Run subagents with clean context and one lane each.
- Main Codex inspects conflicts, verifies decisive claims, and owns the final
  verdict.

## Phase 5 - Digest And Operator Feedback Loop

**Goal:** Make the weekly output easy to consume and feed back into filters.

**Deliverables:**

- Markdown digest format.
- Telegram delivery hook.
- Candidate detail links back to ledger/evidence files.
- Operator response format.
- Ledger event writer for Operator decisions.
- Filter-update capture when a rejection reason is reusable.

**Acceptance Gate:**

- Operator can review the digest without opening raw dumps.
- Every serious candidate has one next action.
- Every Operator decision is durable.

**Subagent Use:**

- Optional review subagent for digest clarity.
- No need for parallel implementation unless Telegram integration grows.

## Phase 6 - Calibration

**Goal:** Learn which sources and criteria produce useful candidates.

**Deliverables:**

- Weekly calibration report.
- Source-lane yield table.
- Reason-code histogram.
- Proof-card conversion tracking.
- Filter drift notes.
- Rescoring command for old candidates.

**Acceptance Gate:**

- The system can answer which lanes produce proof-cards versus rejects.
- Filter changes can be applied to old candidates.
- Weak criteria are tightened or demoted based on outcomes.

**Subagent Use:**

- Use a skeptic subagent to challenge calibration conclusions.
- Avoid adding dashboards until markdown reports are insufficient.

## Phase 7 - Source Expansion

**Goal:** Broaden discovery only after the review pipeline works.

**Potential Sources:**

- GitLab projects and search.
- Curated lists and awesome-list trackers.
- GH Archive or ecosyste.ms for broader signals.
- Marketplaces and app/plugin stores.
- Reddit/Hacker News/Product Hunt only when specific query paths are defined.
- Research reports pasted by Operator.

**Acceptance Gate:**

- Each new source must satisfy the candidate input contract.
- Each source has caps and a clear reason for inclusion.
- The source produces at least one useful candidate or one reusable filter
  lesson within a bounded test window.

**Subagent Use:**

- Good fit for source-specific subagents once the source adapter interface is
  stable.
- Main Codex verifies source quality and drift risk.

## Phase 8 - Optional Operator UI

**Goal:** Add UI only when files plus Telegram become too slow.

**Possible Additions:**

- Local dashboard.
- Candidate search and filters.
- Evidence browser.
- Status transition controls.
- Calibration charts.

**Do Not Start Here:**

- The first value is evidence and decisions, not a nice UI.
- UI should follow real weekly pain, not imagined operator needs.

## Implementation Order

1. Phase 0 contracts.
2. Phase 1 local vertical slice.
3. Phase 2 GitHub source MVP.
4. Phase 3 weak LLM labeling and triage.
5. Phase 4 deep review and council packets.
6. Phase 5 digest and Operator feedback loop.
7. Phase 6 calibration.
8. Phase 7 source expansion.
9. Phase 8 optional UI.

## Current State

Phase 0/1 has a runnable local slice, and Phase 2 has a first GitHub Source MVP:

- `scripts/opportunity_scanner.py`
- `fixtures/manual-candidates.jsonl`
- `tests/test_opportunity_scanner.py`
- `docs/opportunity-scanner-local-slice.md`
- `docs/opportunity-scanner-github-source.md`
- `docs/opportunity-scanner-weak-labeling.md`
- `docs/opportunity-scanner-deep-review-council.md`
- `docs/opportunity-scanner-digest-feedback.md`
- `docs/opportunity-scanner-calibration.md`
- `docs/opportunity-scanner-source-expansion.md`
- `docs/opportunity-scanner-operator-ui.md`
- `docs/opportunity-scanner-hardening-audit-2026-W23.md`

The slice supports manual candidate intake, append-only raw observations,
candidate/event ledgers, deterministic prefiltering, evidence markdown, weak
labels, weak-label triage, and a weekly Markdown report. It normalizes
`repo_key` and `fork_family_key`, merges same-repo observations across sources,
and preserves stronger statuses when a thinner duplicate appears.

The GitHub Source MVP supports public GitHub REST search, repo detail
enrichment, recent issue excerpts, public-only provenance, source caps,
optional ingestion, identity aliasing for late fork-family enrichment, and
rescue fork reopening.

Phase 3 now has a deterministic weak-label baseline:

- `data/ledger/labels.jsonl` stores label payloads separately from queue
  statuses.
- `label` writes `weak-label-triage` events only after prefiltering.
- Weak labels can route to `needs-evidence`, `codex-review`, or
  `watchlist-candidate`.
- Weak labels skip deterministic `machine-reject` candidates and cannot create
  new `machine-reject` events.
- Reports expose confidence, uncertainty, missing evidence, triage rationale,
  and next evidence checks.

Phase 4 now has a local deep-review and council baseline:

- `deep-review` writes `data/ledger/opportunity_cards.jsonl`.
- `deep-review` writes one council packet per lane to
  `data/ledger/council_packets.jsonl`.
- `council-aggregate --input <findings.jsonl>` validates structured council
  findings, writes `data/ledger/council_findings.jsonl`, writes
  `data/ledger/aggregations.jsonl`, and records a `council-aggregator` event.
- Aggregation records vetoes and conflicts instead of smoothing them away.
- Legal/platform veto parks; first-payment-calls veto rejects; proof-card
  requires a market-payment pass.

Phase 5 now has a local digest and Operator feedback baseline:

- `digest` writes `data/reports/<week>-digest.md`.
- `digest` writes a separate human shortlist to
  `data/outbox/telegram/<week>-digest.md` as the Telegram delivery hook.
- `send-telegram-digest` sends the outbox payload through Telegram Bot API when
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are present.
- `operator-feedback --input <feedback.jsonl>` writes
  `data/ledger/operator_decisions.jsonl` and a `operator-feedback` event.
- Reusable feedback writes `data/ledger/filter_updates.jsonl`.

Phase 6 now has a local calibration and rescore baseline:

- `calibration` writes `data/reports/<week>-calibration.md`.
- Calibration stores append-only rows in `data/ledger/calibrations.jsonl`.
- Calibration reports source yield, search-lane yield, reason-code histogram,
  proof-card conversion, and filter drift notes.
- `rescore --source-week <week> --target-week <week>` reprocesses old raw
  observations with current filters and writes `data/ledger/rescore_runs.jsonl`.

Phase 7 now has a GitLab Source MVP:

- `gitlab-search` collects public GitLab projects through REST API.
- GitLab projects map into the common candidate contract.
- GitLab source records public-only provenance and skips non-public projects.
- GitLab source supports caps and optional ingestion.

Phase 7 also has a Hacker News Demand Miner MVP:

- `hn-demand` collects public HN stories and comments from capped feed scans.
- Deleted/dead HN items are skipped.
- Pain clusters score recurrence, buyer clarity, workaround clarity, no-call
  product angle, async distribution, legal/privacy safety, and hype risk.
- Strong clusters write `data/sources/hn/<week>-demand-candidates.jsonl`.
- All clusters write `data/reports/<week>-demand-miner.md`.
- Telegram remains ready-only; report-only HN clusters are not sent to Operator.

Phase 7 also has a Reddit Demand Miner MVP:

- `reddit-demand` collects public subreddit posts/comments through Reddit OAuth.
- The source requires `REDDIT_USER_AGENT` and OAuth credentials.
- Deleted/removed Reddit content is skipped.
- Collection is capped by subreddit, post, comment, total item, cluster, and
  emitted-candidate limits.
- Strong clusters write `data/sources/reddit/<week>-demand-candidates.jsonl`.
- All clusters write `data/reports/<week>-reddit-demand-miner.md`.
- Telegram remains ready-only; report-only Reddit clusters are not sent to Operator.

Phase 8 now has a minimal static operator dashboard:

- `dashboard` writes `data/reports/<week>-dashboard.html`.
- Dashboard is read-only and links back to markdown reports and evidence files.
- No server, auth layer, or status mutation is introduced.

Phase 10 now has a lightweight autonomous loop:

- `run_autonomous_loop.py` wakes up on a launchd interval and exits.
- `config/autonomous-loop.json` defines due jobs, caps, lock path, state path,
  and Telegram gates.
- The loop runs the existing GitHub monitor and HN Demand Miner only when due.
- The loop can run Reddit Demand Miner and Telegram feedback as config-gated
  jobs.
- `data/runs/autonomous-loop-state.json` prevents duplicate work on every tick.
- A lock file prevents overlapping runs.
- Telegram remains ready-only and double-gated.

Phase 11 now has a GitHub Issues mirror baseline:

- `mirror-github-issues` creates/link issues for serious candidate verdicts.
- The mirror defaults to `watchlist`, `proof-card`, `PRD-lite`, and
  `operator-proof-approved`.
- Local mirror rows live in `data/ledger/github_issue_mirrors.jsonl`.
- Issue bodies include deterministic candidate markers for remote dedupe.
- GitHub Projects v2 sync can add mirrored candidate issues to a configured
  Project board and records `data/ledger/github_project_items.jsonl`.
- GitHub Projects remains optional and downstream of local ledger plus Issues.

All roadmap phases now have local MVP implementations.

The first live scan hardening audit found that baseline deep-review was too
generous with `proof-card` promotion. The baseline now treats any
missing-evidence item that blocks `proof-card` as a promotion blocker. Council
aggregation remains the preferred promotion point for serious candidates.
Deep review also supports `--max-candidates` so noisy weekly runs can cap
council packet generation to the strongest ranked candidates. Filter v3 now
adds the strict `0..2` scorecard, where unknown proof, distribution, cost,
support, rights, or unit-economics answers score as zero.

## Recommended Subagent Strategy

Use subagents in three modes:

| Mode | When | Why |
| --- | --- | --- |
| Skeptical review | After schemas, prompts, filters, or source adapters are drafted | Finds hidden assumptions and false-negative risks |
| Independent layer build | After a layer contract and fixtures exist | Parallelizes work without schema chaos |
| Council review | For shortlist candidates only | Improves judgment where money/legal/support tradeoffs matter |

Avoid subagents in two cases:

- Before contracts stabilize.
- For tiny edits where coordination costs exceed quality gains.

The main Codex thread remains the product owner, integrator, verifier, and final
judge. Subagents produce evidence and bounded outputs; they do not own the
pipeline's final decisions.

## Next Concrete Step

Run a hardening and quality audit before adding more sources or UI:

- Review the first live scan digest and calibration output.
- Rescore the first live scan after the hardened `proof-card` gate.
- Check whether GitLab search currently produces useful candidates or mostly
  low-context parked records.
- Run clean-context council lanes only on the top proof-card/watchlist
  candidates.
- Use `deep-review --max-candidates 5` before council on the next scan.
- Tighten search queries, lane detection, and weak-label thresholds based on
  observed false positives.
- Verify live Telegram feedback with repo-local `.env`.
- Refresh GitHub auth with Projects v2 scope, create/select a Project v2 board,
  then enable `sync_github_project`.
- Add Reddit OAuth credentials and enable the weekly Reddit job only after one
  capped manual run looks useful.
- Do not add more marketplaces or a richer dashboard until the digest remains
  readable after Reddit expansion.

## Phase 9 - Autonomous GitHub Monitor Runner

Phase 9 adds a local weekly GitHub monitor:

- `config/github-monitor.json` stores enabled query lanes and caps.
- `scripts/run_github_monitor.py` runs the existing scanner pipeline for the
  current ISO week.
- The runner writes structured logs under `data/runs/`.
- Telegram send is double-gated by config and the `--send` flag.
- `ops/install_launchd.sh` installs a local weekly LaunchAgent.
- `docs/opportunity-scanner-autonomous-monitor.md` documents operation.

This phase kept GitHub Projects, new sources, and interactive Telegram feedback
out of scope until weekly quality was proven enough to add gated expansion.

## Phase 10 - Autonomous Loop Hardening

Phase 10 hardens the scanner as a low-load autonomous operator:

- `config/autonomous-loop.json` can enable failure issue reporting.
- Failed autonomous jobs create or update one durable GitHub Issue per job id.
- Successful recovery writes a GitHub Issue comment and clears local open
  failure state.
- Candidate GitHub Issues are updated on later mirror runs instead of being
  skipped forever.
- Candidate Issues receive source, verdict, needs, and risk labels.
- Candidate Issue bodies are human-readable and sanitized; they avoid local
  filesystem paths and ledger-only clutter.
- Autonomous run logs include `health_summary` counts for selected, succeeded,
  failed, skipped, command, mirror, Telegram, and failure-notification activity.

This phase still kept GitHub Projects v2, additional noisy sources, and
interactive Telegram controls out of scope. Issues became the reliable operator
backlog; Projects could then be layered on later as a workflow view.

## Phase 12 - Projects, Reddit, And Interactive Feedback

Phase 12 adds three gated autonomy layers:

- `sync-github-project` adds mirrored serious candidate issues to GitHub
  Projects v2 through GraphQL and records project item ids locally.
- `reddit-demand` mines capped Reddit demand clusters through OAuth, skips
  removed/deleted content, and reuses the existing strict filter pipeline.
- `telegram-feedback` polls Telegram updates, accepts only whitelisted commands
  or callback payloads, ignores wrong-chat/malformed updates, and writes Operator
  decisions through the existing feedback ledger path.
- `config/autonomous-loop.json` wires these as low-load jobs. Telegram feedback
  is enabled; Reddit is present but disabled until OAuth config exists; Project
  sync is present but disabled until a Project v2 target and token scope exist.

Remaining live activation work:

- refresh the GitHub token with Projects v2 scope or provide a token that can
  call the Projects GraphQL API
- keep `project_number=4` for the private `KikuAI Opportunity Scanner` Project
  or replace it with a different Project v2 id later
- add Reddit OAuth credentials and `REDDIT_USER_AGENT`
- run one manual Reddit and Project dry-run before enabling them in the loop
