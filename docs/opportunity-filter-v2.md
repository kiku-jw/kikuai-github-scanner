# Opportunity Filter v2

## Purpose

Find solo-founder opportunities where a product, wrapper, hosted version, bot,
extension, dashboard, or maintained analog can plausibly produce a first
self-serve payment without calls, heavy selling, custom consulting, or dirty
rights.

The filter does not try to predict guaranteed income. It compresses noisy public
signals into a decision: reject, park, watchlist, proof-card, or PRD-lite.

## Core Principle

Optimize for one buyer, one painful recurring job, one reachable async channel,
one clean product angle, one fast proof, and one hard kill criterion.

GitHub/GitLab popularity is discovery evidence, not money evidence. A candidate
cannot reach `proof-card` from stars, forks, issues, or social buzz alone.

## Candidate Pipeline

1. Harvest candidate from GitHub, GitLab, marketplaces, stores, directories, or
   public discussions.
2. Enrich raw signals: repo metadata, issue/discussion pain, adoption proxies,
   paid alternatives, licensing, distribution surfaces, support burden.
3. Classify product angle and derivative mode.
4. Run hard gates before detailed scoring.
5. Score core opportunity and risks separately.
6. Apply mandatory gates, promotion rules, and demotion rules.
7. Emit one verdict and one next validation action.

For the scanner runtime architecture, use
`docs/opportunity-scanner-architecture.md`. The short version: early local and
weak-LLM layers compress and label; they do not final-reject except for
deterministic hard gates. Raw evidence stays in a ledger so candidates can be
rescored later.

## Derivative Modes

Making something similar is valid when the opportunity is clean. Score the mode,
not the moral vibe.

| Mode | Valid When | Reject When |
| --- | --- | --- |
| Clean analog | Same pain, new implementation, new positioning, clear wedge | Copies brand, code, assets, copy, private mechanics, or confusing trade dress |
| Wrapper | Existing tool has power but poor UX, setup, or workflow packaging | Value is only reselling someone else's restricted service |
| Hosted/managed version | License permits the chosen angle and self-hosting is painful | License forbids hosting, support burden is infra firefighting, or security expectations are too high |
| Maintained fork/remake | Project is abandoned but demand remains and license is compatible | Fork becomes permanent maintenance debt with no payer or channel |
| Dashboard/UI layer | Users need visibility, reporting, review, or control surface | The UI is cosmetic and does not reduce a painful recurring job |
| Bot/extension/app | Pain happens inside that native surface and purchase can be self-serve | Discovery depends on hype, spam, or constant manual community work |
| Template/one-click deploy | The buyer pays to avoid setup and repeat mistakes | One-off use has weak pricing, no channel, or high support |
| AI layer | AI compresses a real workflow with reviewable output | Output must be near-perfect across uncontrolled inputs before trust |

## Hard Gates

Reject or park before scoring if any of these are true.

- Calls, demos, procurement, enterprise relationship sales, or custom rollout
  are required before the first payment.
- The buyer, payer, or first 100 reachable async prospects are unclear.
- No self-serve distribution surface exists: marketplace, store, search intent,
  bounty board, public directory, community channel, or concrete async preview
  lane.
- The idea depends on unclear rights, no license, incompatible license,
  source-available no-hosting terms, gray scraping, shared accounts, ToS
  evasion, or copied brand/assets/copy.
- The core value depends on medical, legal, financial, investment, compliance,
  crypto-yield, or security claims without a clean operator boundary.
- Security or bug-bounty work implies testing outside authorized scope.
- Trading or arbitrage depends on profit promises instead of bounded tooling,
  analytics, alerts, or risk controls.
- The first-money MVP needs several coupled subsystems before a buyer-visible
  preview exists and has no manual or semi-manual proof path.
- Free previews, retries, failed jobs, storage, review, or third-party API costs
  are uncapped.
- Support becomes custom consulting, environment-specific debugging, bespoke
  integrations, migration firefighting, or high-touch onboarding.
- The output must be near-perfect before users trust it, and failures are not
  inspectable, bounded, or easy to flag.
- A free built-in feature or obvious platform/model update would remove the
  whole wedge, leaving no durable workflow artifact.

## Evidence Layers

Keep raw evidence separate from interpretation.

## Search Lanes

Use these lanes to discover and rescue candidates. They are soft signals, not
final verdicts.

| Lane | Detect | Why It Matters |
| --- | --- | --- |
| `active-abandoned-forks` | Original project is stale, but forks have recent commits, issues, releases, or usage | Demand may remain after upstream stopped serving it |
| `cli-to-ui-gap` | A useful CLI/library exists, but no serious UI, dashboard, extension, hosted version, or workflow surface exists | Wrapper, dashboard, bot, extension, or hosted layer may be the product |
| `commercial-intent-density` | Issues, discussions, README, docs, or web mentions repeat words like hosted, managed, cloud, pricing, SaaS alternative, deploy, support, or paid | Users may already be asking for a purchasable version |
| `academic-hobbyist-bias` | Signals are mostly educational, research, toy, student, demo, or hobbyist language | Soft demotion unless money, buyer, or production-use evidence is visible |

### Repo And Adoption Evidence

Use these to decide whether a candidate deserves enrichment, not whether it
deserves building.

- Stars and star growth.
- Forks and fork-to-star ratio.
- Release cadence and release asset downloads.
- Last commit, last activity, maintainer responsiveness.
- Dependents, package downloads, Docker pulls, extension installs, marketplace
  users, ratings, and reviews.
- Active forks when the original project is stale, especially forks with recent
  patches, releases, or support discussions.

Higher weight: dependents, installs, downloads, paid store metrics, and release
asset downloads. Lower weight: raw stars, social mentions, launch spikes.

### Pain And Gap Evidence

These are the best signals for wrapper, hosted, dashboard, bot, extension, or
template opportunities.

- Install, deploy, Docker, Helm, SSL, auth, config, migration, and setup pain.
- Bad or missing docs.
- Unanswered discussions, slow issue closure, unresolved support backlog.
- Repeated requests for hosted/cloud, API, UI, dashboard, integrations,
  browser extension, mobile companion, templates, one-click deploy, or pricing.
- Useful CLI/library projects with no serious web UI, dashboard, extension,
  hosted version, or workflow surface. Useful code clues include `argparse`,
  `click`, `commander`, `clap`, `cobra`, and similar CLI frameworks.
- Missing UX around review, reporting, alerts, monitoring, collaboration, or
  export.
- Abandoned but still requested project functionality.

### Market And Payment Evidence

These signals decide whether there is money nearby.

- Paid competitors with visible pricing.
- Marketplaces with sales, reviews, installs, ratings, or purchases.
- Search queries at the moment of pain.
- Active bounty payouts or accepted reports.
- GitHub Sponsors, Open Collective, Patreon, paid support, or hosted plans.
- Buyers discussing alternatives, pricing, hosted versions, or managed support.
- Commercial-intent density in public text: repeated hosted, managed, cloud,
  pricing, support, SaaS alternative, deploy, or paid-version language.
- A recurring job that happens daily, weekly, or monthly.

### Distribution Evidence

Do not accept "SEO", "Reddit", "Product Hunt", "GitHub", or "Telegram" as a
channel unless the exact path is named.

Valid evidence includes:

- The exact search queries a buyer uses during the painful moment.
- A marketplace/store where similar tools already get installs, reviews, or
  purchases.
- A public directory, topic, package ecosystem, or app store with buyer intent.
- A listable first 100 prospects reachable with a concrete preview and without
  spam.
- A platform-native surface where the product lives where the pain happens.

## Scoring Blocks

Score each block `0..5`.

| Block | Meaning |
| --- | --- |
| Demand | Real interest beyond hype: adoption proxies, growth, usage signals, external mentions |
| Pain | Repeated, painful, and observable friction or missing layer |
| Monetization | Clear payer, paid alternatives, recurring use, pricing angle |
| Buildability | Buyer-visible MVP in 1-4 weeks or manual/semi-manual proof sooner |
| Distribution | Concrete self-serve acquisition lane and first 100 source |
| Autonomy | No calls, no custom sales, no heavy onboarding, self-serve payment possible |
| Support Burden Inverted | Higher score means lower support burden |
| Competition And Wedge | Paid competitors prove demand, but the candidate has a narrow wedge |
| Personal Fit | Operator edge, interest, fast feedback loop, style fit, likelihood not to abandon |
| Bonus Optionality | Upsells, templates, usage tiers, marketplace listings, compounding assets |

Recommended weights:

```text
CoreScore =
  15*Demand/5 +
  15*Pain/5 +
  15*Monetization/5 +
  13*Buildability/5 +
  10*Distribution/5 +
   8*Autonomy/5 +
   8*SupportBurdenInverted/5 +
   6*CompetitionAndWedge/5 +
  10*PersonalFit/5
```

Optional bonus: add `0..5` after the core score only when it reflects a real
compounding asset, not wishful expansion.

## Risk Score

Score risk blocks `0..5`, where `5` means high risk.

```text
RiskScore =
  35*LegalLicensingRisk/5 +
  30*PlatformApiRisk/5 +
  20*OperationalRisk/5 +
  15*MarketHypeRisk/5
```

Working final score:

```text
FinalOpportunityScore = max(0, CoreScore + BonusOptionality - 0.60 * RiskScore)
```

The coefficient is a starting heuristic. Calibrate it against real outcomes.

## Mandatory Gates For Proof-Card

A candidate cannot become `proof-card` unless all are true:

- Demand `>= 3/5`.
- Pain `>= 3/5`.
- Monetization `>= 3/5`.
- Buildability `>= 3/5`.
- Distribution `>= 2.5/5`.
- Personal fit `>= 3/5`.
- RiskScore `<= 35`.
- No hard gate fired.
- At least one money signal exists outside repo popularity.
- One 7-day proof action can produce hard evidence.

## Promotion And Demotion Rules

Promotion to `watchlist` or `proof-card` is allowed when:

- Hosted/UI/API request intensity is high.
- Self-hosting or setup complexity is high.
- A CLI/library has usage but lacks the UI, dashboard, extension, bot, or
  hosted surface where the pain is handled.
- Commercial-intent density is high enough to suggest a purchasable version.
- The upstream project is stale but active forks suggest demand survived.
- License is compatible with the chosen angle.
- MVP is a dashboard, wrapper, bot, extension, template, one-click deploy, or
  narrow hosted layer.
- Popularity is modest, but pain and payer evidence are strong.

Demote when:

- Stars/social mentions are high but Monetization `< 2/5`.
- Personal Fit `< 2/5`.
- The buyer is mostly students, hobbyists, or free-first users.
- Academic, research, demo, or hobbyist positioning dominates and no production
  use, paid analog, or buyer evidence offsets it.
- The product is one-off and has no clear one-time purchase economics.
- Competitors exist but no narrow wedge is visible.
- Channel evidence is generic rather than specific.
- Support burden is uncertain or likely hidden manual repair.
- The MVP needs heavy user-data storage, 24/7 infrastructure, or
  environment-specific firefighting before a buyer-visible proof.

## Verdicts

| Verdict | Use When | Next Action |
| --- | --- | --- |
| reject | Hard gate fired or final score `< 50` | Store reason code only |
| park | Interesting but blocked by rights, platform, buyer, channel, or timing | Revisit only if blocker changes |
| watchlist | Some strong evidence, but one major block remains weak | Track signals or enrich manually |
| proof-card | Passes gates and can be tested in 7 days | Run one proof experiment |
| PRD-lite | Proof signal exists and the next blocker is scoped implementation | Write a narrow implementation brief |

Avoid `build` as an initial verdict. Use `proof-card` first.

## Opportunity Card Fields

```yaml
project_name:
project_url:
repo_key:
fork_family_key:
source:
license:
license_angle_compatibility: compatible | review_needed | incompatible | unknown
category:
short_description:
target_buyer:
painful_recurring_job:
current_workaround:
product_angle:
derivative_mode:
what_we_take:
what_we_do_not_copy:
existing_user_base:
  stars:
  forks:
  dependents:
  downloads_or_installs:
  releases:
  last_activity:
raw_signals:
  search_lanes:
    active_abandoned_forks:
    cli_to_ui_gap:
    commercial_intent_density:
    academic_hobbyist_bias:
  repo_adoption:
  issues:
  discussions:
  registry_or_store:
  market:
  text_evidence:
interpreted_signals:
  demand_evidence:
  pain_evidence:
  monetization_evidence:
  distribution_evidence:
  buildability_notes:
  support_burden_notes:
risks:
  legal_licensing:
  platform_api:
  operational:
  market_hype:
monetization_hypotheses:
recommended_mvp:
minimum_subsystems_before_preview:
preview_cost_cap:
failed_job_cost_cap:
ordinary_quality_failure:
built_in_substitution_residue:
scoring:
  demand:
  pain:
  monetization:
  buildability:
  distribution:
  autonomy:
  support_burden_inverted:
  competition_and_wedge:
  personal_fit:
  bonus_optionality:
  core_score:
  risk_score:
  final_opportunity_score:
final_verdict:
next_validation_step:
kill_criteria:
```

## Seven-Day Proof Protocol

Every `proof-card` gets one bounded proof, not a product build.

Required fields:

- Buyer: who pays without a call.
- Paid trigger: why they pay now.
- Preview: what can be shown before payment.
- Proof channel: exact async path.
- Offer: fixed package, price, or waitlist/payment-intent mechanism.
- Cost cap: maximum time, compute, storage, retries, and manual review.
- Success metric: payment, paid click, purchase, accepted report, repeat buyer,
  or direct payment intent from a qualified buyer.
- Kill criterion: what result ends the idea.

Default proof options:

- Manual or semi-manual sample report.
- Landing page with concrete preview and payment/waitlist CTA.
- Marketplace listing draft or limited listing.
- Extension/demo video with external payment path.
- Bounty/program proof sprint within authorized scope.
- Paid template or one-click package test.

## Source Priorities

Use sources in this order for the first scanner version.

Tier A:

- GitHub Search, Topics, Issues, Discussions.
- VS Code Marketplace.
- Chrome Web Store.
- AlternativeTo.
- Curated awesome lists.

Tier B:

- GitLab Explore/API.
- Product Hunt.
- Hacker News.
- Stack Overflow.
- Docker Hub.
- deps.dev/libraries.io.

Tier C:

- Reddit.
- AppSumo.
- Gumroad.
- Flippa/Acquire-style marketplaces.
- Telegram/Discord directories.
- MCP catalogs.

Tier C is useful but noisy. Do not let it dominate verdicts.

## Short Checklist

Use this before spending implementation time.

- Who pays without a call?
- What repeated pain do they already feel?
- What workaround proves the pain exists?
- What visible result are they buying?
- What clean derivative mode applies?
- What exact channel reaches the first 100?
- What paid competitors or payment signals exist?
- What does the MVP avoid building?
- What is the preview and failed-job cost cap?
- Can the MVP avoid heavy user-data storage, 24/7 infrastructure, and
  environment-specific firefighting?
- What support will happen after payment?
- What license, rights, ToS, and platform risks apply?
- What remains valuable if the platform ships the obvious feature?
- What is the 7-day proof and kill criterion?
