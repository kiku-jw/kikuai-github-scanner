## ADR-001: Do Not Use Paperclip As The Opportunity Scanner Control Plane

**Date:** 2026-06-02
**Status:** accepted

**Context:** The opportunity scanner needs to find, preserve, filter, review,
and report autonomous no-call income candidates from public project/product
signals. The current goal is a narrow evidence ledger and decision pipeline,
not a large agent factory or general research platform.

**Options considered:**
- Plain local ledger plus Codex review: lightweight, auditable, easy to change;
  weaker dashboards and queue management.
- Paperclip control plane: richer state, queues, dispositions, and agent
  routing; higher setup, routing, and "busy factory" risk.
- Generic dynamic workflow skill: useful orchestration scaffold; overlaps with
  existing local skills and does not add a new required runtime.

**Decision:** Use a plain local pipeline as the control plane:
`weekly script -> ledger -> deterministic prefilter -> weak LLM labels -> Codex
deep pass -> council/subagents on shortlist -> Telegram digest -> Operator
personal-fit gate -> Codex follow-up`. Paperclip is parked for this project.

**Consequences:** The first implementation stays small and file-based. The
ledger remains the durable asset. We can still reuse Paperclip-like concepts
such as statuses, dispositions, and reason codes, but not its runtime as the
default control plane.

**Revisit if:** Candidate volume outgrows a file ledger, review queues become
hard to manage, evidence attachments need richer indexing, multiple long-lived
agents run every week, or Telegram plus local docs stop being enough as the
operator interface.
