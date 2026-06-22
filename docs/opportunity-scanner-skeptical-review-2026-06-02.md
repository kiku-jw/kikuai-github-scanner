# Opportunity Scanner Skeptical Review - 2026-06-02

## Claim Reviewed

Phase 0/1 is safe enough to build GitHub Source MVP on top of it.

## Contract

- Preserve raw evidence.
- Merge duplicate repository observations across sources.
- Avoid duplicate deep review for already checked repositories and fork
  families.
- Do not let weak or thin duplicate observations demote stronger existing
  status.
- Keep local ledger as source of truth; GitHub Projects can be an operator
  mirror later.

## Findings

### Finding 1 - Fixed

`candidate_id` previously depended on `source|project_url`. That meant the same
repository discovered from GitHub search, an awesome list, and a research report
would become separate candidates. This violated the dedupe contract and would
make Phase 2 noisy.

Fix:

- `candidate_id` now derives from `fork_family_key`, then `repo_key`, then
  normalized `project_url`.
- Tests cover cross-source same-repo merge.

### Finding 2 - Fixed

Phase 0/1 had no first-class fork-family identity. A GitHub collector would not
know that an active fork had already been checked as part of the same upstream
family.

Fix:

- Candidate records now include `repo_key` and `fork_family_key`.
- Fork-family observations merge into one candidate while preserving fork
  evidence.
- Tests cover fork-family merge.

### Finding 3 - Fixed

A thinner duplicate observation could demote a stronger existing status. For
example, a candidate promoted to `codex-review` from one source could later be
seen from a thin curated source and fall back to `needs-evidence`.

Fix:

- Duplicate observations preserve stronger statuses unless a deterministic hard
  gate fires.
- Tests cover cross-source duplicate without status downgrade.

## Residual Risk

- There is no GitHub Projects sync yet. This is intentional; Projects should be
  a mirror/operator board after local dedupe works.
- The local registry is represented by candidate ledger keys plus
  `identity_aliases.jsonl`, not a separate `checked-repositories.jsonl`
  snapshot. Add a derived checked-registry snapshot only when GitHub Projects
  sync or large source expansion needs faster lookup.

## Phase 2 Follow-Up Review

A sidecar skeptical review later found additional Phase 2 risks:

- late fork-family enrichment could split one repo into multiple candidates
- rescue forks could not reopen a rejected family
- public-only provenance was not enforceable
- source caps and rate-limit policy were not testable
- immutable GitHub ids were not preserved separately from `owner/repo`

All five were addressed in the GitHub Source MVP:

- `identity_aliases.jsonl` stores repo/family/url/GitHub id aliases
- rescue fork observations can emit `rescue-reopen`
- GitHub candidate metadata includes public-only provenance
- tests cover caps, public query enforcement, and private-source rejection
- GitHub `id` and `node_id` are stored in `raw_metadata`
