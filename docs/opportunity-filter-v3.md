# Opportunity Filter v3

## Purpose

Select repo-derived product ideas only when a solo developer can plausibly get
the first paying customer without calls, then repeat the sale with low support.

This filter does not optimize for TAM, novelty, technical beauty, stars, or
venture-scale upside. Repo popularity is discovery evidence only.

## Core Formula

Take the idea only when there is:

- one buyer
- one painful recurring job
- one moment of search or discovery
- one visible result
- one self-serve payment path
- one cheap proof
- one clear kill criterion

Everything else is raw material, not a build candidate.

## Hard Gates

Reject or park before scoring when any item is true:

- Calls, demos, procurement, custom B2B sales, or custom rollout are required
  before first payment.
- The first 100 reachable async prospects are unclear.
- The buyer cannot be reached through one specific async channel.
- Fulfillment looks like custom consulting, hidden manual repair, migration
  firefighting, bespoke integrations, high-touch onboarding, or moderation.
- The MVP is already a multi-subsystem product before a buyer-visible preview.
- Rights, license, data, model, media, font, asset, or ToS boundaries are
  unclear.
- AGPL/GPL/server-side license risk blocks a closed or hosted derivative angle.
- The core demand is copyright-adjacent downloader behavior.
- The product gives medical, legal, financial, investment, compliance, or
  security advice without a safe operator boundary.
- Product mistakes can cause disproportionate harm.
- Sensitive data is required without a credible local/private path.
- The idea is a feature with no pain, money, reputation, or required artifact.
- Free templates or built-in features squeeze the bottom while mature products
  or APIs squeeze the top.
- The idea depends on one API, model, platform rule, loophole, or platform
  omission.
- Unit economics are unknown after compute, support, refunds, commissions, and
  failed jobs.
- Free preview, failed-job, retry, compute, storage, or review costs are
  uncapped.
- One ordinary quality failure would destroy trust.
- If a platform ships the obvious feature, no durable workflow artifact remains.

## First Payment Checks

Before proof-card scoring, answer:

1. Which subsystems must work before a useful preview exists?
2. Can payment be checked manually or semi-manually?
3. What is the maximum free-preview cost?
4. What is the maximum failed-job cost?
5. Which ordinary error would immediately destroy trust?
6. What remains valuable if Google, OpenAI, Apple, GitHub, or another platform
   ships the obvious feature?
7. Can input size, retries, compute, storage, and review be bounded?
8. Can the result be shown before payment?
9. What exactly is being sold: file, report, export, monitoring, unlock, or
   template?

Unknown answers count as zero in the strict scorecard.

## Distribution Proof

Do not accept generic channel names such as SEO, App Store, Telegram, GitHub,
Reddit, or Google.

Valid distribution proof must name at least one:

- exact search query at the painful moment
- marketplace/store where competitors already show installs, reviews, or sales
- listable first 100 async prospects reachable with a concrete preview and
  without spam
- directory/feed/ecosystem where the buyer already searches for this job

## Roast Fields

Every surviving idea must answer:

- buyer
- painful job
- current workaround
- promised result
- smallest one-function wedge
- first no-call channel
- self-serve payment path
- visible demand proof
- nearest free substitute
- nearest paid substitute
- wedge against substitutes
- automated fulfillment path
- repeatability
- downside cap
- legal, rights, license, and ToS flags
- platform dependency and fallback
- expected support load
- seven-day proof experiment
- hard proof sought
- kill criteria
- exact acquisition lane
- proof the lane exists
- first 100 without calls or ads
- minimum subsystem map
- manual or semi-manual proof path
- preview and failed-job cost caps
- ordinary quality failure
- residue after obvious platform substitution

## Strict Scorecard

Each item scores `0..2`:

- `0`: failed or unknown
- `1`: plausible but weak
- `2`: clean or confirmed

Items:

1. urgent recurring pain
2. clear buyer-visible result
3. one small function
4. demand proof
5. no-call revenue path
6. provable online reachability
7. speed to first money
8. cheap seven-day proof
9. automated fulfillment
10. repeatability
11. scales without proportional manual work
12. limited downside
13. clean rights and ToS
14. resilience to platform changes
15. unit economics
16. simple support
17. proof quality: payment, paid click, purchase, accepted report, or repeat
    buyer

Verdicts:

- `27+`: full proof-card candidate
- `22-26`: challenger; keep active but do not build
- `16-21`: watchlist or reshape
- `<16`: park

`build` is not a first verdict. `proof-card` means prove payment or hard
purchase intent before product implementation.

## Telegram Contract

The local technical report may include ids, paths, reason codes, rejects, and
parks. Telegram must not.

Telegram shows at most five human-readable ready candidates:

- only `proof-card`, `PRD-lite`, or `operator-proof-approved` candidates
- no `watchlist` fallback; if no candidate passes, send a short "no ready ideas"
  status instead of candidate details
- no raw, needs-evidence, park, reject, candidate ids, ledger paths, or reason
  code dumps

Each Telegram item shows:

- project and URL
- verdict plus strict score
- buyer
- pain
- product angle
- money signal
- first-100 lane
- main blocker
- next action
