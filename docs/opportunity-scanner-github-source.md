# Opportunity Scanner GitHub Source MVP

## Purpose

Phase 2 adds a narrow public GitHub REST source lane. It collects public
repository candidates, maps them into the post-search candidate contract, and
can optionally ingest them into the local ledger.

## Commands

Collect candidates to JSONL:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  github-search \
  --query 'hosted dashboard language:Python stars:>50' \
  --max-candidates 10 \
  --issues-per-repo 3
```

Collect and ingest into the ledger:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  github-search \
  --query 'hosted dashboard language:Python stars:>50' \
  --max-candidates 10 \
  --issues-per-repo 3 \
  --ingest
```

By default the output path is:

```text
data/sources/github/<week>-candidates.jsonl
```

Set `GITHUB_TOKEN` or `GH_TOKEN` only to increase public API rate limits. The
collector still enforces public-only collection and marks `auth_required=false`
in candidate provenance.

## Source Contract

The collector uses public GitHub REST endpoints:

- repository search
- repository detail
- repository issues

It does not use private repositories, browser-authenticated scraping, shared
accounts, or private GitHub data. If a candidate record claims private or
auth-required provenance, deterministic prefilter emits `non-public-source`.

Candidate metadata includes:

```yaml
raw_metadata:
  provider: github
  id:
  node_id:
  full_name:
  repo_key:
  fork_family_key:
  source_full_name:
  parent_full_name:
  fork:
  private:
  archived:
  stargazers_count:
  forks_count:
  open_issues_count:
  collection:
    api_surface: github-rest
    api_version: 2026-03-10
    visibility: public
    auth_required: false
    endpoint_kinds:
      - search/repositories
      - repos
      - issues
```

`repo_key` is the current human-readable repo identity. `id` and `node_id` are
stored for immutable GitHub identity. `fork_family_key` uses GitHub `source`
metadata when available, then `parent`, then the repo itself.

## Caps And Rate Limits

The source lane is intentionally capped:

- `--max-candidates` limits candidates per run.
- `--per-page` is clamped to `1..100`.
- `--issues-per-repo` limits issue excerpts per repository.
- Query text is forced to include `is:public`.
- Queries containing `is:private` are rejected.
- If rate limit is reached after partial collection, the current batch can
  stop with partial results instead of expanding scope.

GitHub REST docs confirm that unauthenticated public requests are allowed but
limited, authenticated requests have higher limits, and GitHub search endpoints
have more restrictive limits than general REST endpoints.

## Dedupe Behavior

GitHub source output feeds the same local identity layer as manual intake:

- same repo across sources maps by `repo_key`
- late `fork_family_key` enrichment merges through `identity_aliases.jsonl`
- fork-family observations can reopen a previously rejected family when a new
  rescue signal appears
- GitHub Projects remains a future mirror/operator board, not source of truth

## Verification

Current tests cover:

- public query enforcement
- private search rejection
- private/provenance hard gate
- GitHub candidate mapping
- source caps
- fork-family mapping
- late identity enrichment
- rescue fork reopening

Live smoke test performed on 2026-06-02:

```bash
python3 scripts/opportunity_scanner.py \
  --data-dir /tmp/opportunity-scanner-gh-live \
  --week 2026-W23 \
  github-search \
  --query 'hosted dashboard language:Python stars:>50' \
  --max-candidates 1 \
  --per-page 1 \
  --issues-per-repo 0 \
  --ingest
```

Result: one public GitHub candidate collected, ingested, and reported.
