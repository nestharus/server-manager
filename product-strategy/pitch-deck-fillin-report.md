# Pitch Deck Fill-In Report

## Scope

**Task:** Replace `[BRACKETED: ...]` placeholders in `product-strategy/pitch deck.md` with concrete pricing figures from `product-strategy/research/pricing-data.md`. Preserve placeholders that require user input (team credentials, specific commitment amount within range, specific design-partner count, current actual burn).

**Source of all numbers:** `product-strategy/research/pricing-data.md` (snapshot dated 2026-04-16).

## Placeholders Filled

### 1. Market Opportunity — competitor bot-stack cost (line 78)

**Before:** `Operators already pay [BRACKETED: specific monthly/annual figures. User to fill in after competitor-pricing sweep] across the current bot stack for subsets of this functionality.`

**After:** `Operators typically pay $20-$40/mo across 3-5 premium bots for subsets of this functionality, with heavier custom or security stacks running higher: [MEE6 Premium] at $5.99/mo per server, [Ticket Tool Premium] at $7.99/mo per server, [Dyno] at $5.99-$12.99/mo, [Carl-bot] at $7.99-$35.99/mo depending on server count, and [Arcane] at $7/mo.`

**Figures used:**
- $20-$40/mo stack range
- MEE6 Premium $5.99/mo per server
- Ticket Tool Premium $7.99/mo per server
- Dyno Standard/Premium/Custom $5.99-$12.99/mo
- Carl-bot $7.99-$35.99/mo by server count
- Arcane Premium $7/mo

**Sources cited:**
- https://mee6.xyz/en/premium
- https://tickettool.xyz/premium
- https://dyno.gg/premium
- https://carl.gg/get-premium
- https://arcane.bot/premium

### 2. Business / Funding Model — Cost Structure table (lines 205-215)

**Table intro added:** a one-sentence note that the OCR figures assume 2,000 screenshots/community/month across 100 communities (200,000 screenshots/month) at a blended per-screenshot rate of about $0.00160-$0.00168, so investors can rescale.

**Vultr VKE infrastructure row:**
- **Estimate filled:** `~$80-$130/mo for a realistic Phase 0 stack (VKE worker cluster, load balancer, block storage, object storage, managed PostgreSQL); ~$45-$56/mo bare floor before managed DB and object storage`
- **Sources cited:** https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost, https://www.vultr.com/pricing/, https://www.vultr.com/products/object-storage/

**OCR pipeline (Google Cloud Vision primary) row:**
- **Driver expanded:** `Per-image DOCUMENT_TEXT_DETECTION on 200,000 screenshots/mo (2,000 per community × 100 communities)`
- **Estimate filled:** `~$299/mo after the 1,000-image free tier`
- **Source cited:** https://cloud.google.com/vision/pricing

**OCR fallback (Gemini 3 Flash Preview) row:**
- **Driver expanded:** `Vision-LLM fallback on an assumed 5% of screenshots (about 10,000 calls/mo at the stated volume)`
- **Estimate filled:** `~$21-$36/mo`
- **Sources cited:** https://cloud.google.com/vertex-ai/generative-ai/pricing, https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash

**Blended OCR total row (new):**
- **Estimate filled:** `~$320-$336/mo` at 200,000 screenshots/month
- **Sources cited:** https://cloud.google.com/vision/pricing, https://cloud.google.com/vertex-ai/generative-ai/pricing

**Contributor time row:** placeholder kept, with a clearer prompt: `[BRACKETED: FTE-equivalent for the commitment period; user to fill based on final team composition]`.

### 3. Business / Funding Model — Burn, Runway, Milestone (lines 217-220)

**Current monthly burn:** placeholder clarified to `[BRACKETED: user to confirm actual current cash burn, including any already-committed contributor compensation]`.

**Projected monthly burn filled:**
- $15k-$30k/mo for a 1-2 person lean team
- $35k-$45k/mo for a 3-person founding team including infrastructure
- Sources cited: https://kruzeconsulting.com/do-founders-of-startups-that-have-raised-millions-give-themselves-paychecks-if-so-how-much-money-do-they-pay-themselves/, https://kruzeconsulting.com/startup-wages-seriesa/
- Called out explicitly as an inference from Kruze compensation benchmarks, not a direct market quote.

**Runway filled:**
- 18-24 months at a raise in the $1.5M-$3.5M range
- Specific commitment amount within the range flagged as user input
- Source cited: https://carta.com/learn/startups/fundraising/seed-funding/

### 4. The Ask — Investor variant (lines 347-353)

**Ask amount filled:** `a seed commitment in the $1.5M-$3.5M range`, with the specific commitment inside that range marked as user input.

**Runway bullet filled:** `Infrastructure and engineering runway of 18-24 months at the projected burn ($15k-$30k/mo lean, or $35k-$45k/mo for a 3-person team with infra)`.

**Design-partner target:** placeholder clarified to `[BRACKETED: target count of initial design-partner communities beyond Humility as the reference; user to fill based on Phase 2 rollout capacity]`.

**Source cited:** https://carta.com/learn/startups/fundraising/seed-funding/

### 5. The Ask — Community Sponsors variant (line 360)

**Ask filled:** three sponsor tiers stated as ranges:
- Individual: $5-$10/mo
- Supporter: $25-$50/mo
- Organizational sponsor: $100-$150+/mo

**Sources cited:**
- https://docs.github.com/en/sponsors/receiving-sponsorships-through-github-sponsors/managing-your-sponsorship-tiers
- https://blog.opencollective.com/open-collective-v2-is-live/
- https://github.com/sponsors/martincostello
- https://github.com/sponsors/joshbeckman
- https://opencollective.com/psutil

### 6. Team / Why Us (lines 319, 325-327)

**Per task guardrail:** did NOT fabricate team credentials. Intro placeholder was rewritten to be clearer and more specific about what's expected:

**Before:** `[BRACKETED: This section to be completed by the user. Suggested structure below.]`

**After:** `[BRACKETED: This section requires user input. Do not fabricate credentials. Fill in the items below with actual names, operational history at Humility or comparable communities, and any relevant engineering, design, or domain experience. If no additional contributors or advisors are committed yet, say so plainly.]`

The three sub-bullets (founder name, additional contributors, specific Discord/OCR/distributed-systems experience) remain as user-fill placeholders.

## Placeholders Intentionally Left for User Input

Per task instructions, the following remain `[BRACKETED: ...]` with clearer prompts:

1. Team / Why Us intro and all three sub-bullets (lines 319, 325-327): founder credentials must come from the user.
2. Cost Structure "Contributor time" row (line 214): depends on final team composition.
3. Burn, Runway, Milestone "Current monthly burn" (line 218): actual cash burn is user-known only.
4. Burn, Runway, Milestone "Runway under proposed raise" (line 220): specific commitment amount within $1.5M-$3.5M still user input.
5. The Ask — Investor "Ask" line (line 347): specific commitment inside the range still user input.
6. The Ask — Investor design-partner count (line 353): specific target count still user input.

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [x] Added or removed a section — added one new row to the Cost Structure table (`Blended OCR total at 200,000 screenshots/mo`) to make the OCR headline number legible at a glance. No section-level addition or removal.

No restart-from-earlier-phase trigger. All edits were inside placeholders or the sentences that introduced them.

## Ban-Violation Sweep

- Em dashes (`—`): zero in the document after edits (verified by search).
- Banned sentence openers (But, And, So, Or, Still, Yet, However, Therefore): zero at sentence start after edits (verified by regex).
- Hyphens used for numeric ranges (`$20-$40`, `$80-$130`, `18-24`) per the source research file's convention.

## Known Remaining Issues

- The new Cost Structure table has six rows (added "Blended OCR total"). A reviewer could argue the blended number duplicates the sum of the two OCR rows above it; it is kept because investors typically scan for the headline OCR monthly, and the math on per-call fallback rates is non-obvious.
- The Investor "Ask" now states a range with a flagged user-input placeholder for the specific number. A stricter reviewer may want a single number before circulation; that is deliberately deferred to the user per the task.
- Line 78 inline-cites five competitors to justify the $20-$40/mo range. The length adds a few words to an otherwise tight bullet, but the task required citing the main competitors.
