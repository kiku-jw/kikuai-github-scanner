# Opportunity Scanner Digest And Operator Feedback

## Purpose

Phase 5 turns the weekly machine output into two separate surfaces:

- a local technical report for audit and debugging
- a short human Telegram shortlist for Operator

The Telegram hook is a local outbox markdown file that the sender can deliver
unchanged. It must not be a raw ledger dump.

## Commands

Write the weekly digest and Telegram outbox:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 digest
```

Apply Operator feedback:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W23 \
  operator-feedback \
  --input path/to/operator-feedback.jsonl
```

Apply Telegram feedback commands/callbacks:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  telegram-feedback
```

Preview parsing without mutating the ledger:

```bash
python3 scripts/opportunity_scanner.py \
  --week 2026-W24 \
  telegram-feedback \
  --dry-run
```

Preview Telegram delivery without sending:

```bash
python3 scripts/opportunity_scanner.py --week 2026-W23 send-telegram-digest --dry-run
```

Send the digest through Telegram Bot API:

```bash
# Either export these variables or put them in the repo-local .env file.
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python3 scripts/opportunity_scanner.py --week 2026-W23 send-telegram-digest
```

Expected run order:

```text
run/github-search -> label -> deep-review -> council-aggregate -> digest -> send-telegram-digest -> operator-feedback
```

`digest` can run before council aggregation; it will use the best available
opportunity card or aggregation.

## Files

```text
data/
  reports/YYYY-WW-digest.md
  outbox/telegram/YYYY-WW-digest.md
  ledger/operator_decisions.jsonl
  ledger/filter_updates.jsonl
```

The report and Telegram outbox intentionally do not contain the same payload.
The report can include candidate ids, reason codes, evidence paths, parks, and
rejects. The Telegram outbox is a human-only decision feed capped to candidates
that are ready for proof or PRD follow-up.

`send-telegram-digest` reads the outbox file, splits long digest text into
Telegram-sized plain-text messages, and sends it with `sendMessage`. The token
is read only from `TELEGRAM_BOT_TOKEN` or `TG_BOT_TOKEN`; the chat id is read
from `TELEGRAM_CHAT_ID`, `TG_CHAT_ID`, or `--chat-id`. Do not commit tokens or
write them into reports. The CLI auto-loads repo-local `.env` values when the
variables are not already present in the process environment.

## Digest Format

Technical report sections:

- proof-card candidates
- watchlist
- parked
- rejects
- other

Each serious report candidate includes:

- candidate id
- verdict
- product angle
- buyer
- painful job
- reason codes
- next action
- evidence link
- opportunity card link

Machine rejects are compacted by reason code when they do not have deeper
review artifacts.

Telegram shortlist rules:

- maximum five candidates
- only `proof-card`, `PRD-lite`, or `operator-proof-approved` candidates
- no watchlist fallback; watchlist remains local-only
- if no candidate passes, send a short "no ready ideas" status
- no raw, needs-evidence, park, reject, candidate ids, ledger paths, or reason
  code dumps
- each item shows project, URL, strict score, buyer, pain, angle, money signal,
  first-100 lane, main blocker, and next action

GitHub Issues are the durable backlog surface for serious candidates, but they
are not the Telegram surface. Issues may include watchlist candidates and
operator labels; Telegram remains capped to proof-ready or Operator-approved ideas.

## Operator Feedback Schema

Input row:

```json
{
  "candidate_id": "cand_x",
  "decision": "operator-reject",
  "reason_codes": ["not-close-to-me"],
  "notes": "Operator would not use this.",
  "reusable_filter_update": true,
  "filter_update": {
    "proposed_change": "Down-rank this reusable pattern.",
    "target_doc": "docs/opportunity-filter-v3.md"
  }
}
```

Allowed decisions:

- `operator-reject`
- `operator-park`
- `operator-watchlist`
- `operator-proof-approved`
- `filter-update-needed`

Every decision writes:

- one row in `ledger/operator_decisions.jsonl`
- one `operator-feedback` event in `ledger/events.jsonl`

When `reusable_filter_update=true` or decision is `filter-update-needed`, the
system also writes an open row to `ledger/filter_updates.jsonl`.

## Telegram Feedback

Telegram feedback is inbound-only. It does not change the ready-only digest
rules and does not send raw candidates to Operator.

Allowed text commands:

```text
/reject <candidate_id> [notes]
/park <candidate_id> [notes]
/watchlist <candidate_id> [notes]
/proof <candidate_id> [notes]
/filter <candidate_id> [notes]
```

Allowed callback payloads:

```text
osfb|reject|<candidate_id>
osfb|park|<candidate_id>
osfb|watchlist|<candidate_id>
osfb|proof|<candidate_id>
osfb|filter|<candidate_id>
```

Short callback codes are also accepted:

```text
osfb:rj:<candidate_id>
osfb:pk:<candidate_id>
osfb:wl:<candidate_id>
osfb:pf:<candidate_id>
osfb:fu:<candidate_id>
```

The handler ignores unknown commands, malformed callbacks, and messages from a
different chat id. Valid rows are written through the same Operator feedback path:

- `ledger/operator_decisions.jsonl`
- `ledger/events.jsonl`
- `ledger/filter_updates.jsonl` when the decision is `/filter`
- `ledger/telegram_feedback_updates.jsonl`
- `ledger/telegram_feedback_state.json`

For callback queries the handler calls Telegram `answerCallbackQuery` after the
ledger write succeeds.

On the first live poll with no local offset state, the handler primes
`telegram_feedback_state.json` and does not apply old updates. This prevents a
newly enabled bot from replaying stale commands. Dry-runs also avoid ledger
mutation.

Live polling requires both a bot token and an allowed chat id. If
`TELEGRAM_CHAT_ID`/`TG_CHAT_ID` is missing, the autonomous loop skips feedback
instead of accepting commands from any chat.

## Verification

```bash
python3 -m py_compile scripts/opportunity_scanner.py tests/test_opportunity_scanner.py
python3 -m unittest discover -s tests
```

Covered invariants:

- digest and Telegram outbox are both written
- digest and Telegram outbox are intentionally different
- Telegram dry-run does not require a token
- Telegram chunks stay under the Bot API message limit
- technical digest includes candidate links and next action
- Telegram digest excludes ledger links and candidate ids
- Operator feedback creates a durable event
- reusable feedback creates a filter-update row
- Telegram feedback ignores wrong-chat and malformed updates
