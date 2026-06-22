# GitHub Tool Scout - 2026-06-16

## Scope

This pass looked for GitHub/open-source tools, APIs, and datasets that could
strengthen the opportunity scanner without weakening its core constraints:

- public-only provenance;
- local ledger remains the source of truth;
- no hidden scraping, shared accounts, or Terms-of-Service bypass;
- no AGPL/GPL code ingestion into the scanner runtime;
- Telegram receives only ready human-facing opportunities, not raw candidate
  exhaust;
- expensive frontier models are reserved for shortlist interpretation, not bulk
  harvesting.

## Method

Sources checked:

- GitHub CLI search and `gh repo view` for current repository signals;
- primary GitHub repository pages;
- official project pages where available.

GitHub search was stopped once it began returning secondary-rate-limit signals.
That is a useful operational reminder: discovery expansion should reduce
pressure on GitHub Search, not depend on more aggressive polling.

## Shortlist

| Tool | Type | Current signals | Fit | Limits | Verdict |
| --- | --- | --- | --- | --- | --- |
| [yamadashy/repomix](https://github.com/yamadashy/repomix) | Repo digest / LLM context packer | 26k+ stars, active in June 2026, strong CLI/MCP surface | Best first addition for shortlist-only deep review. It can pack a repo into AI-friendly output, count tokens, respect ignore files, and run secret checks before model review. | Should run only after a candidate survives deterministic and weak-model filters. Do not pack every raw repo. | Try first |
| [igrigorik/gharchive.org](https://github.com/igrigorik/gharchive.org) / [GH Archive](https://www.gharchive.org/) | Public GitHub event archive | Long-running public dataset, hourly archives, BigQuery access | Best source expansion for repository momentum, issue/comment activity, fork/star velocity, and surfacing repos GitHub Search misses. | BigQuery cost/scan discipline needed. Start with narrow daily tables and query budgets. | Try first |
| [ecosyste-ms/repos](https://github.com/ecosyste-ms/repos) / [repos.ecosyste.ms](https://repos.ecosyste.ms/) | Repository metadata API | Active, API-oriented, many ecosystems, stated 5000 req/hour default IP limit | Good enrichment/backfill source for normalized repository metadata and possibly fork/package ecosystem context. | Code is AGPL-3.0 and API data is CC BY-SA 4.0. Use as an external API with minimal derived facts and attribution; do not vendor or self-host casually. | Try carefully |
| [coderamp-labs/gitingest](https://github.com/coderamp-labs/gitingest) | Repo digest / Python package | 14k+ stars, active in June 2026, CLI and Python package | Viable fallback if Python integration matters more than Repomix features. | Less compelling than Repomix for our current shortlist-review lane. Token digest is useful, but Repomix has stronger agent-context/security ergonomics. | Secondary |
| [pingcap/ossinsight](https://github.com/pingcap/ossinsight) / [OSS Insight](https://ossinsight.io/) | GitHub analytics / trends | Active, public trend pages, AI-builder and repository analytics surfaces | Useful benchmark and manual research reference for trend definitions, collections, and metrics. | Do not couple core autonomy to its UI. Treat as comparison/reference unless a stable API path is confirmed. | Study |
| [Trendshift](https://trendshift.io/) | Live trending repository ranking | Shows daily/weekly/monthly/yearly trending repos and live mentions | Good external sanity check for momentum candidates. Can reveal rising repositories before GitHub Trending catches them. | Terms/API surface are unclear from this pass. Avoid browser scraping as a core source until a clean access path is confirmed. | Study |
| [hanxiao/dataroom](https://github.com/hanxiao/dataroom) | Local research harness architecture | Active, MIT, structured dataroom output, Jina-driven search/read/dedup loop | Strong architectural pattern: cheap local orchestration gathers sources into a zip, frontier model only interprets the grounded bundle. | Not a direct scanner dependency yet. It assumes specific local model/GPU/Jina setup and targets general web research, not GitHub opportunity scoring. | Study architecture |
| GitHub Trending API clones | Unofficial trending wrappers | Some repos have stars, but several are stale or HTML-scrape GitHub Trending | Tempting shortcut for discovery. | Brittle, unofficial, and duplicative of cleaner GH Archive/Trendshift paths. | Avoid for now |
| GitHub issue classifier repos | ML classifiers for issues | Search results were mostly toy repos, unknown licenses, GPL, or stale experiments | The need is real: classify complaints, feature requests, support load, and payment pain. | Existing repos are weaker than our domain-specific schema and current LLM/deterministic hybrid approach. | Build ourselves |
| [librariesio/libraries.io](https://github.com/librariesio/libraries.io) | Package/dependency ecosystem database | Mature project, broad ecosystem coverage | Could help later for package-level demand and dependency graph evidence. | AGPL-3.0 code and separate API/data-rights review needed. Not a first GitHub scanner dependency. | Park |

## Recommendations

### 1. Add a shortlist-only repo digest lane with Repomix

Add a `repo-digest` command that runs only for candidates that already reached
`proof-card`, `challenger`, or deep-review shortlist status.

Expected output:

```text
data/repo_digests/<candidate_id>/repomix-output.md
data/repo_digests/<candidate_id>/digest-meta.json
```

The digest should feed council packets and clean-context subagents, not raw
Telegram. It should also record:

- candidate id;
- repo url and commit/ref used;
- digest tool and version;
- token count;
- included/excluded paths;
- secret-scan result;
- failure reason if packaging failed.

Why this matters: our deepest model pass currently reasons mostly over metadata,
issues, labels, and report text. A compact code/docs digest lets the final
review answer higher-quality questions: installation complexity, UI surface,
real API boundaries, hidden support burden, deployment shape, and whether a
managed wrapper is realistic.

### 2. Design a GH Archive momentum source before coding it

GH Archive is the best candidate for reducing dependence on GitHub Search.
Start with a design note and one capped offline query, not a daemon.

First useful queries:

- repositories with repeated issue, issue-comment, pull-request, or
  pull-request-comment activity around complaint/request language;
- repos with recent fork/star velocity but low hosted/commercial polish;
- repos with high issue/comment activity and low maintainer response;
- topic-bounded event windows for AI tooling, devtools, security, data,
  automation, Telegram/Discord bots, browser extensions, and mobile utilities.

Hard caps:

- narrow time window first;
- fixed scanned-bytes budget;
- persist query text and job stats;
- never send raw event exhaust to Telegram;
- candidates must still pass the existing hard gates.

### 3. Use ecosyste.ms as enrichment, not source of truth

The API can help with normalized repository metadata and ecosystem context, but
its license posture means we should store only small attributed derived fields
unless a deeper rights review says otherwise.

Good fields to enrich:

- repository metadata freshness;
- package/ecosystem names;
- dependency/package manager hints;
- fork/source relationships if exposed;
- related repository aliases.

Do not import AGPL code, mirror large raw datasets, or make ecosyste.ms the
canonical ledger.

## Non-Recommendations

- Do not adopt generic GitHub Trending API wrappers as a primary source. They
  are likely to be brittle, redundant, and too popularity-biased.
- Do not import issue-classifier projects. Our classifier should be domain
  specific: user pain, feature requests, support burden, install friction,
  monetization hints, legal/platform risk, and no-call revenue path.
- Do not expand Telegram output. The right direction is stricter final-report
  curation, not more raw findings.

## Suggested Implementation Order

1. `repo-digest` command with Repomix on one known candidate and a tiny test
   fixture that proves digest metadata is persisted.
2. Deep-review packet update: include digest summary path and digest meta when
   present.
3. GH Archive design doc with one example BigQuery query and byte-budget rule.
4. Optional `ecosystems-enrich` command with cache, attribution, and small-field
   storage only.
5. Calibration report section: count how often digest/enrichment changed a
   verdict.

## Evidence

- Repomix GitHub page: https://github.com/yamadashy/repomix
- Gitingest GitHub page: https://github.com/coderamp-labs/gitingest
- GH Archive GitHub page: https://github.com/igrigorik/gharchive.org
- GH Archive official site: https://www.gharchive.org/
- ecosyste.ms repos GitHub page: https://github.com/ecosyste-ms/repos
- repos.ecosyste.ms: https://repos.ecosyste.ms/
- OSS Insight GitHub page: https://github.com/pingcap/ossinsight
- OSS Insight: https://ossinsight.io/
- Trendshift: https://trendshift.io/
- Dataroom GitHub page: https://github.com/hanxiao/dataroom
- Libraries.io GitHub page: https://github.com/librariesio/libraries.io

## Open Questions

- Does Repomix produce stable enough output for deterministic diffing across
  runs, or should we store only metadata plus the latest digest artifact?
- Which GH Archive access path is cheapest and simplest for this machine:
  BigQuery, hourly JSON download, or a small third-party mirror?
- What exact attribution and storage boundary is acceptable for ecosyste.ms API
  data under CC BY-SA 4.0?
- Should repo digest generation clone candidate repositories locally, use
  remote packing, or support both with strict caps?
