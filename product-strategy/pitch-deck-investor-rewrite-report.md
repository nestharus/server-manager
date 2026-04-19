# Pitch Deck Investor Rewrite Report

## Scope

Rewrote `product-strategy/pitch deck.md` to reframe the deck from a generic investor-or-contributor pitch targeting a $1.5M-$3.5M seed round into a **pre-seed investor deck** targeting **$300k-$500k**. The rewrite reflects the researched economics in `product-strategy/research/market-economics.md` and the honest operator reality: solo founder, $9,500/mo burn, self-funded via contract work, no traction yet, pre-product.

## Sections Preserved (No Changes)

These sections were strong in the prior draft and remain intact:

- **The Problem** — opening monologue, fourteen-axis pain framing
- **The Current Landscape** — five-category competitive survey
- **Why Now** — five timing dynamics with citations
- **Market Opportunity → The First Wedge** and **Adjacent Expansion** subsections — bottoms-up wedge narrative
- **Operator-Owned Durable State Replaces Vendor Lock-In** — six structural commitments
- **How It Works** — three workflow walkthroughs
- **Competitive Positioning** — four-class alternative table and integration moat
- **Roadmap** — Phase 1 through Phase 4 descriptions (authoritative from executive roadmap)
- **Risks 1-3** — competitive window, adoption friction, OCR quality
- **Appendix / Q&A Preparation** — pointers to supporting artifacts

## Sections Changed

### 1. Market Opportunity — TAM / SAM / SOM added (new subsection)

**Before:** Bottoms-up wedge narrative only; no explicit TAM/SAM/SOM numbers.

**After:** New `TAM / SAM / SOM` subsection placed at the top of Market Opportunity, with:

- **TAM $1.1B-$2.3B** (Discord bot software ceiling)
- **SAM ~$150M** base case (modeled range $46M-$274M) for the guild-management wedge
- **SOM ~$720k ARR** realistic 3-year capture at ~2,000 paying guilds
- Methodology note explaining why the SAM stays inside the guild-management category
- **HYBRID market-cap feasibility verdict** explicitly stated

**Sources:** `research/market-economics.md` §1 Discord bot industry, §1 Guild management tool market, §1 Bottoms-up SAM calculation; `research/pitch-deck-communication.md` Market Opportunity Communication (bottom-up framing requirement).

### 2. Business Model — replaces "Business / Funding Model"

**Before:** Open-source Path A / Hosted SaaS Path B framing; neither validated. Framed as "commitment, not revenue" ask.

**After:** Direct SaaS business model with explicit pricing architecture and ARR trajectory:

- **Pricing:** $29/mo individual guild, $79/mo multi-chapter org, $50/mo design-partner tier (time-limited with white-glove onboarding)
- **Pricing rationale:** positioned above generic bots (Carl-bot, Dyno, Ticket Tool) and below purpose-built guild software (Guild Manager) / broader community OS (Circle, Mighty Networks)
- **ARR Trajectory table:** Year 1 $25k-$60k, Year 2 $72k-$240k, Year 3 $360k-$720k with explicit assumptions
- **Wedge-expansion rationale:** Year-1/2 from gaming-guild wedge; Year-3 upper end depends on adjacent-segment expansion (Phase 4+)

**Sources:** `research/market-economics.md` §2 Pricing benchmarks, §2 Plausible trajectory; `research/pricing-data.md` (competitor pricing citations: [Carl-bot](https://carl.gg/get-premium), [Dyno](https://dyno.gg/premium), [Ticket Tool](https://tickettool.xyz/billing), [Guild Manager](https://guildmanager.app/pricing), [Circle](https://circle.so/pricing), [Mighty Networks](https://www.mightynetworks.com/pricing)).

### 3. Cost Structure + Burn/Runway — replaces prior "Cost Structure" and "Burn, Runway, and Milestone"

**Before:** Bracketed "user to confirm" burn; projected $15k-$30k lean or $35k-$45k 3-person team burn; 18-24 month runway at $1.5M-$3.5M seed raise; target contributor FTE unspecified.

**After:**

- **Current burn $9,500/mo** (solo + contract-work-funded) — stated explicitly
- **Current capacity ~0.3-0.5 FTE** (remainder on contract work)
- **Runway under $300k-$500k raise: 24-36 months** at current burn plus modest scale-up
- **Month-12 milestone:** MVP + 20-50 design partners + $15k MRR
- Infrastructure cost table preserved (Vultr VKE, Google Cloud Vision OCR, Gemini fallback)
- Added **Team Expansion Plan** with MRR-gated hire triggers (UI engineer $15k-$25k MRR, product partner $25k-$40k MRR, marketing $35k-$50k MRR, 4-person team $60k-$75k MRR)
- **Market-cap caveat** restated inline

**Sources:** `research/market-economics.md` §3 Valuation math for this project (runway math), §4 Team expansion thresholds, §4 Market-cap feasibility check. Cost-bucket infrastructure table carries forward from prior draft with citations to `DECISIONS.md` D2, D5, D6.

### 4. Risk 4 — solo-founder execution capacity (replaces "volunteer contributor sustainability")

**Before:** Volunteer contributor sustainability framing, consistent with the prior open-source / community-project posture.

**After:** Solo-founder execution capacity risk. Scenario: founder cannot transition to full-time without revenue or pre-seed close; Phase 1 → Phase 2 schedule slips; competitive window risk compounds. Mitigation: explicit gate at $15k-$25k MRR OR pre-seed close; phase design is decomposable; first UI hire triggers at $15k-$25k MRR once bandwidth is the binding constraint.

**Sources:** `research/market-economics.md` §3 Valuation math (burn $9,500/mo, runway math), §4 Team expansion thresholds.

### 5. Risk 5 — market-cap capacity (hybrid outcome) — NEW

**Before:** Did not exist.

**After:** New risk explicitly stating the HYBRID verdict. `$10M ARR` requires `4.9%-9.8%` of modeled SAM and is not reachable on the pure gaming-guild wedge. Mitigation: Phase 1 substrate is designed as adjacent-community portable; expansion into creator/mod/fandom/esports segments is Phase 4+ and optional upside. Investors should read the ask as "fund the wedge; the expansion bet is optional upside that depends on wedge validation."

**Sources:** `research/market-economics.md` §4 Market-cap feasibility check (explicit hybrid verdict).

### 6. Team / Why Us — honest solo-founder framing

**Before:** Generic team template with bracketed placeholders for multiple contributors and advisors.

**After:** Explicit solo-founder framing:

- "Current team: solo founder. No additional team members are committed."
- Current burn $9,500/mo stated inline
- ~0.3-0.5 FTE capacity on project
- Full-time commitment **gated on $15k-$25k MRR OR pre-seed close**, stated explicitly
- Founder bio with [BRACKETED: founder name, Humility operator since 2022-04-04, engineering background, Discord/OCR/distributed-systems experience]
- Team expansion plan cross-referenced from Business Model section
- Market-cap caveat repeated
- "What the founder has already produced solo" — strategic artifacts produced at ~0.3-0.5 FTE over roughly two quarters

**Sources:** `research/market-economics.md` §3 (burn + runway), §4 (team expansion thresholds); task prompt (solo-founder framing, Humility operator since 2022-04-04, full-time gating criteria).

### 7. The Ask — pre-seed, $300k-$500k, hybrid framing

**Before:** Three-audience ask (investors $1.5M-$3.5M seed, community sponsors $5-$150+/mo, contributors time/feedback). Seed framing.

**After:** Single-audience pre-seed investor ask with:

- **$300k-$500k pre-seed** (bracketed specific target with $400k midpoint suggestion)
- **SAFE with $7.5M-$10M post-money cap** as preferred structure (Carta benchmark)
- **Alternative: priced round at $4M-$8M pre-money** with 15-25% dilution (Rebel Fund benchmark)
- **24-36 months runway** at current burn
- **First milestone (Month 12):** MVP + 20-50 design partners + $15k MRR
- **Use-of-funds breakdown** by months 1-12 / 13-24 / 25-36 tied to MRR triggers
- **Hybrid market-cap framing** restated: wedge = solid small-business; expansion bet = unfunded VC-scale upside

**Sources:** `research/market-economics.md` §3 Equity Ask and Dilution (Carta pre-seed benchmarks, SAFE dominance, dilution benchmarks, recommended raise $300k-$500k, implied valuation $4M-$8M pre-money / $7.5M-$10M SAFE cap); §4 Market-cap feasibility check (hybrid verdict).

## Citations Added / Retained

The rewrite adds these new external citations (not in prior draft):

- [CNBC 19M weekly active servers](https://www.cnbc.com/2021/05/08/what-is-discord-chat-service-fosters-community-expands-beyond-gaming.html)
- [Discord Guilds FAQ](https://support.discord.com/hc/en-us/articles/23187611406999-Guilds-FAQ)
- [Discord Server Insights FAQ](https://support.discord.com/hc/en-us/articles/360032807371-Server-Insights-FAQ)
- [MEE6 pricing](https://mee6.xyz/en/pro), [Dyno pricing](https://dyno.gg/premium), [Carl-bot pricing](https://carl.gg/get-premium), [Ticket Tool billing](https://tickettool.xyz/billing)
- [Guild Manager pricing](https://guildmanager.app/pricing), [Circle pricing](https://circle.so/pricing), [Mighty Networks pricing](https://www.mightynetworks.com/pricing)
- [Carta pre-seed benchmarks Q2 2025](https://carta.com/data/state-of-pre-seed-q2-2025/), [Carta state of pre-seed 2025](https://carta.com/data/state-of-pre-seed-2025/)
- [Carta SAFE dominance](https://carta.com/learn/startups/fundraising/convertible-securities/pre-money-vs-post-money-safes/)
- [Rebel Fund dilution benchmarks](https://www.rebelfund.vc/blog-posts/founder-dilution-benchmarks-seed-2025-stay-under-18-percent)
- [Pave first-engineer comp](https://www.pave.com/blog-posts/how-much-comp-should-the-first-engineer-get)
- [Carta startup compensation H1 2025](https://carta.com/data/startup-compensation-h1-2025/)
- [TopStartups marketing examples](https://topstartups.io/startup-salary-equity-database/?title=Marketing%20manager)

Existing infrastructure-cost citations ([Google Cloud Vision pricing](https://cloud.google.com/vision/pricing), [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [Vultr pricing](https://www.vultr.com/pricing/), etc.) were preserved.

## Research Requirements Addressed

Cross-check against `research/pitch-deck-communication.md` Synthesis:

| Requirement | How addressed |
|---|---|
| Why now | Preserved (unchanged) |
| Market opportunity with bottoms-up TAM/SAM/SOM or wedge-expansion framing | **Strengthened** — new TAM/SAM/SOM subsection with explicit numbers |
| Business model or funding model | **Replaced** — explicit two-tier SaaS pricing + ARR trajectory |
| Traction or proof proxies | Addressed — "what founder has produced solo" + pre-product acknowledgment |
| Team / why us | **Replaced** — honest solo-founder framing with [BRACKETED] founder bio |
| Ask / use of funds / milestone plan / runway | **Replaced** — pre-seed $300k-$500k, SAFE/priced alternatives, month-by-month use of funds, month-12 milestone |
| Explicit competitive positioning against substitutes and incumbents | Preserved (unchanged) |
| Risk ownership and mitigation | **Strengthened** — added Risk 5 (market-cap capacity), replaced Risk 4 with solo-founder execution capacity |

## Known Gaps / Deferred

Items the rewrite could not fill:

- **Founder name and bio specifics.** Preserved as [BRACKETED] per guardrail "Do NOT invent team credentials." User must fill: founder name, full engineering background, specific Discord/OCR/distributed-systems experience.
- **Specific pre-seed amount.** Preserved as [BRACKETED] inside $300k-$500k range with $400k midpoint suggestion per prompt instruction.
- **Design-partner contact list.** The deck targets 20-50 design partners by month 12 but does not name specific communities (none are committed yet).

## Guardrail Compliance

- **Did not invent team credentials.** Founder bio items remain [BRACKETED].
- **Did not contradict researched economics.** All numbers trace back to `research/market-economics.md` or cited external benchmarks.
- **Did not polish prose.** Left stylistic polish to rubric pipeline.
- **Preserved citations and markdown structure.** All prior citations retained; new citations added with source URLs.
- **Did not inflate the market-cap verdict.** Hybrid verdict appears three times: Market Opportunity TAM/SAM/SOM, Business Model → Team Expansion, Risk 5, and The Ask → Hybrid Market-Cap Framing. All say "hybrid," none claim guaranteed VC-scale.
