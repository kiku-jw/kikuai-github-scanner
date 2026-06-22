# Required Documents - Opportunity Scanner

## Context

- Product: local opportunity scanner for GitHub/GitLab/OSS/product signals that finds evidence-backed no-call solo-founder income candidates.
- Stage: Discovery to MVP.
- Team: solo operator with Codex-assisted implementation and optional clean-context subagents.
- Audience: Operator, Codex, future implementation agents.
- Regulatory: none identified, but legal/licensing/platform-risk gates are central to the product.
- Save path: `docs/`

## Documents

1. **PRD** (MVP) - done: `docs/opportunity-scanner-prd.md`
2. **Roadmap** (Implementation Roadmap) - done: `docs/opportunity-scanner-roadmap.md`

## Order Rationale

The MVP PRD defines the product boundary, non-goals, user stories, contracts,
success metrics, and quality gates. The roadmap then sequences implementation
by thin vertical slices and only introduces subagents once layer contracts are
stable enough for independent work.

## Existing Documents

- `docs/opportunity-filter-v3.md` - detailed strict scoring, gates, Telegram shortlist rules, and opportunity card logic.
- `docs/opportunity-scanner-architecture.md` - weekly architecture and status model.
- `docs/opportunity-scanner-post-search-layers.md` - post-search pipeline design and council lanes.
- `docs/adr/ADR-001-no-paperclip-control-plane.md` - accepted control-plane decision.
