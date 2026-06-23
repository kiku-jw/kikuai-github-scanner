# Implementation Notes

- Added `oss-bounty-radar` as a CLI subcommand in `scripts/opportunity_scanner.py`.
- Converted radar tasks into normal scanner candidates with the original score, verdict, amount, platform, tags, and radar metadata preserved in `raw_metadata`.
- Added autonomous-loop job support for running an optional external radar command before importing the report.
- Kept the default job conservative: `ingest: true`, `post_pipeline: false`, and `send_telegram: false`.
- Replaced machine-specific absolute paths with sibling-relative `../oss-bounty-radar/...` paths before committing because `kiku-jw/kikuai-github-scanner` is public.
