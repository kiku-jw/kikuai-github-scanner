# Opportunity Scanner Source Expansion

## Purpose

Phase 7 broadens discovery only after the ledger, labels, deep review,
aggregation, digest, and calibration layers work. Every new source must satisfy
the same candidate input contract and must preserve public-only provenance.

## GitLab Source MVP

Collect public GitLab projects:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  gitlab-search \
  --search 'dashboard' \
  --max-candidates 10 \
  --issues-per-project 3
```

Collect and ingest:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  gitlab-search \
  --search 'dashboard' \
  --max-candidates 10 \
  --issues-per-project 3 \
  --ingest
```

By default the output path is:

```text
data/sources/gitlab/<week>-candidates.jsonl
```

Set `GITLAB_TOKEN` or `GL_TOKEN` only to improve public API access. The
collector still uses `visibility=public` and records `auth_required=false`.

## Source Contract

The GitLab source uses public REST API endpoints:

- `GET /projects`
- `GET /projects/:id/issues`

Candidate metadata includes:

```yaml
raw_metadata:
  provider: gitlab
  id:
  path_with_namespace:
  repo_key:
  fork_family_key:
  forked_from_path_with_namespace:
  fork:
  visibility:
  archived:
  star_count:
  forks_count:
  open_issues_count:
  last_activity_at:
  topics:
  collection:
    api_surface: gitlab-rest
    api_version: v4
    visibility: public
    auth_required: false
    endpoint_kinds:
      - projects
      - project-issues
```

`repo_key` is normalized from `web_url`. `fork_family_key` uses
`forked_from_project.path_with_namespace` when available, then the project
itself.

## Caps

- `--max-candidates` limits candidates per run.
- `--per-page` is clamped to `1..100`.
- `--issues-per-project` limits issue excerpts.
- Projects whose API `visibility` is not `public` are skipped.

## Current Source Set

Implemented:

- GitHub public REST source.
- GitLab public REST source.
- Hacker News public demand source.
- Reddit OAuth demand source.
- GH Archive-style local momentum fixture source.
- ecosyste.ms derived metadata enrichment.
- Shortlist-only repository digest metadata.

Future sources should be added only after a source contract doc and tests:

- curated lists / awesome lists
- live GH Archive / BigQuery jobs
- marketplaces and plugin stores
- Product Hunt only with specific query paths
- pasted research reports from Operator

## Verification

```bash
python3 -m py_compile scripts/opportunity_scanner.py tests/test_opportunity_scanner.py
python3 -m unittest discover -s tests
```

Covered invariants:

- GitLab source enforces public visibility
- GitLab source caps collection
- GitLab source maps candidates into the common contract
- GitLab source captures project issue excerpts
- GitLab source contributes repo/fork-family identity keys

Live smoke test performed on 2026-06-02:

```bash
python3 scripts/opportunity_scanner.py \
  --data-dir /tmp/opportunity-gitlab-live \
  --week 2026-W23 \
  gitlab-search \
  --search 'dashboard' \
  --max-candidates 1 \
  --per-page 1 \
  --issues-per-project 0 \
  --ingest
```

Result: one public GitLab project collected, ingested, and reported.

## Repository Digest Layer

Capture a bounded local digest for a candidate that already reached a serious
status:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  repo-digest \
  --candidate-id cand_example \
  --source-path /path/to/local/repo \
  --tool repomix \
  --tool-version 1.14.1 \
  --max-files 80 \
  --max-bytes 500000
```

Output:

```text
data/repo_digests/<candidate_id>/digest.md
data/repo_digests/<candidate_id>/digest-meta.json
data/ledger/repo_digest_meta.jsonl
```

The command refuses non-serious candidates unless `--force` is used. Serious
means the candidate is already in a shortlist/deep-review status such as
`codex-review`, `watchlist-candidate`, `watchlist`, `proof-card`, `PRD-lite`,
or `operator-proof-approved`.

Current implementation includes a bounded built-in text packer so the ledger
contract is testable without installing dependencies. If Repomix is run
externally, pass its generated artifact with `--digest-file` and record
`--tool repomix --tool-version <version>`; do not add raw digest output to
Telegram.

## GH Archive Momentum Groundwork

Collect public GH Archive-style event fixtures into normal candidate rows:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  gh-archive-momentum \
  --input data/sources/gh-archive/sample-events.jsonl \
  --max-events 1000 \
  --max-repos 20 \
  --min-events 2 \
  --issue-excerpts-per-repo 4 \
  --ingest
```

Default output:

```text
data/sources/gh-archive/<week>-momentum-candidates.jsonl
```

Candidate metadata includes:

```yaml
raw_metadata:
  provider: gh-archive
  repo_name:
  repo_key:
  fork_family_key:
  event_count:
  event_counts:
  last_event_at:
  collection:
    api_surface: gh-archive-fixture
    visibility: public
    auth_required: false
    raw_events_stored: false
```

This command intentionally starts with local JSON/JSONL fixtures. Live GH
Archive activation should come later through a capped BigQuery/hourly-archive
adapter with fixed scanned-byte or downloaded-byte budgets, persisted query
text, and no raw event exhaust in Telegram.

## ecosyste.ms Enrichment Layer

Capture small attributed derived metadata for GitHub candidates:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  ecosystems-enrich \
  --candidate-id cand_example
```

Use a fixture for deterministic tests or offline review:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  ecosystems-enrich \
  --candidate-id cand_example \
  --fixture data/sources/ecosystems/sample-response.json
```

Output:

```text
data/ledger/ecosystems_enrichments.jsonl
```

The enrichment row stores only derived fields such as repository name,
description, license, language, topics, stars, forks, open issue count,
metadata-file hints, attribution URL, and data license. It records
`raw_response_stored=false` and does not mutate the canonical candidate intake
row.

Boundary:

- do not vendor or self-host ecosyste.ms AGPL code in this scanner;
- do not mirror large raw ecosyste.ms datasets into the ledger;
- keep attribution and `CC-BY-SA-4.0` metadata with every enrichment row;
- treat ecosyste.ms as enrichment, not source of truth.

## Hacker News Demand Miner MVP

Mine public Hacker News discussions for repeated user pain before spending
frontier-agent time on interpretation:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  hn-demand \
  --max-stories 80 \
  --comments-per-story 20 \
  --max-clusters 10 \
  --max-candidates 5
```

Collect and ingest only strong clusters:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  hn-demand \
  --max-stories 80 \
  --comments-per-story 20 \
  --max-clusters 10 \
  --max-candidates 5 \
  --ingest
```

By default the output paths are:

```text
data/sources/hn/<week>-demand-candidates.jsonl
data/reports/<week>-demand-miner.md
```

The collector uses the public Hacker News Firebase API:

- `/v0/askstories.json`
- `/v0/showstories.json`
- `/v0/newstories.json` when explicitly requested
- `/v0/item/<id>.json`

Candidate metadata includes:

```yaml
source: hn-demand
source_url: https://news.ycombinator.com/item?id=<story_id>
project_url: https://news.ycombinator.com/item?id=<story_id>
repository: ""
license: unknown
raw_metadata:
  provider: hacker-news
  source_type: demand-cluster
  cluster_id:
  story_ids:
  comment_ids:
  story_count:
  comment_count:
  points_total:
  score:
    total:
    verdict:
    dimensions:
    hard_reasons:
  collection:
    api_surface: hacker-news-api
    visibility: public
    auth_required: false
search_lanes:
  demand_pain_cluster: true
```

Scoring is intentionally conservative and transparent. Each dimension is
`0..2`:

- pain recurrence
- buyer clarity
- current workaround clarity
- no-call product angle
- async distribution hint
- legal/privacy safety
- not hype/novelty-only

Clusters scoring `10+` become candidates unless a hard reject fires. Clusters
scoring `7..9` stay report-only. Lower-scoring clusters are noise. Hard rejects
include sensitive/legal/financial/crypto/trading/copyright/downloader/ToS
patterns and unclear buyer signals.

Telegram behavior does not change. HN report-only clusters and raw candidates
do not appear in Telegram. The digest still sends only ideas that survive the
existing final filters as `proof-card`, `PRD-lite`, or Operator-approved proof.

## Reddit Demand Miner MVP

Mine OAuth-authenticated public Reddit discussions for repeated user pain:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  reddit-demand \
  --subreddits webdev SaaS indiehackers \
  --sort hot \
  --max-posts-per-subreddit 8 \
  --comments-per-post 4 \
  --max-total-items 60 \
  --max-clusters 5 \
  --max-candidates 2
```

Collect and ingest only strong clusters:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  reddit-demand \
  --subreddits webdev SaaS indiehackers \
  --ingest
```

Required environment:

```text
REDDIT_USER_AGENT=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
# or REDDIT_ACCESS_TOKEN=
```

By default the output paths are:

```text
data/sources/reddit/<week>-demand-candidates.jsonl
data/reports/<week>-reddit-demand-miner.md
```

The collector uses Reddit's OAuth API only:

- `POST https://www.reddit.com/api/v1/access_token` for client credentials
- `GET https://oauth.reddit.com/r/<subreddit>/<sort>`
- `GET https://oauth.reddit.com/r/<subreddit>/comments/<post_id>`

No logged-out `.json` scraping fallback is allowed. The collector requires a
descriptive `REDDIT_USER_AGENT`, skips `[removed]` and `[deleted]` content, and
records `auth_required=true` in candidate metadata.

Candidate metadata includes:

```yaml
source: reddit-demand
source_url: https://www.reddit.com/r/<subreddit>/comments/<post_id>/...
project_url: https://www.reddit.com/r/<subreddit>/comments/<post_id>/...
repository: ""
license: unknown
raw_metadata:
  provider: reddit
  source_type: demand-cluster
  cluster_id:
  subreddits:
  post_count:
  comment_count:
  score:
    total:
    verdict:
    dimensions:
    hard_reasons:
  collection:
    api_surface: reddit-oauth-api
    visibility: public
    auth_required: true
search_lanes:
  demand_pain_cluster: true
```

Telegram behavior does not change. Reddit report-only clusters and raw
candidates do not appear in Telegram. The digest still sends only ideas that
survive the existing final filters as `proof-card`, `PRD-lite`, or
Operator-approved proof.
