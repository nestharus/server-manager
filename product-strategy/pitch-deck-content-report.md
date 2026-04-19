# Pitch Deck — Content Editing Report

Report covering the revision of `product-strategy/pitch deck.md` against the communication research synthesis in `product-strategy/research/pitch-deck-communication.md`. No prose polishing was performed; the rubric pipeline handles style.

---

## Sections Added / Revised

### Added: "Why Now" (after "The Current Landscape")

**Addresses research requirement:** Synthesis §1 (missing investor spine — "why now" as core section); Market Opportunity Communication ("why now is part of market communication, not a decorative slide"); inferred framing "Discord's maturity as an operating surface, increasing complexity, fragmentation of bot tooling, and availability of OCR/AI."

**Traces to:**
- `market research.md` §2, §7, Cross-cutting Findings — Gather deprecated, Guilded shut down, SCNX documentation lag
- `market research.md` Cross-cutting Findings — "Retention and export are uneven or gated"; premium gating concentrates around ownership, retention
- `market research.md` §6, §7 Gap Analysis — declared-state reconciliation under-served
- `DECISIONS.md` D5, D6 — OCR architecture (Google Cloud Vision primary, Gemini 3 Flash Preview fallback)
- `NOTES.md` — discord.py 2.7.1 modal select components now supported
- `executive roadmap.md` Risk Register #3 — gap claims are time-bounded; refresh cadence

---

### Added: "Market Opportunity" (after "Why Now")

**Addresses research requirement:** Synthesis §2 (bottom-up wedge-expansion framing, not top-down Discord TAM) — who buys first, what they spend today, why first wedge is painful, adjacent expansion.

**Traces to:**
- `NOTES.md` — Humility community 83 members during original sweep as reference point
- `market research.md` §4 Community Management Workarounds — "the common workaround is Discord + Google Sheets/Excel + one or more bots + optional guild website"
- `market research.md` §5 User Pain Signals — weekly compliance ritual is largest recurring volunteer-time cost
- `market research.md` §3, §6, §7 Cross-cutting Findings — premium gating around claiming, transcripts, retention, exports, alliance capacity, backups
- `problem.md` §2, §3, §5, §6, §7, §9 — underlying operator pain axes
- `market research.md` §2, §3, §5 — strong evidence rating on demand signals
- `research/pitch-deck-communication.md` Market Opportunity Communication — explicit guidance against top-down "fraction of Discord servers" framing

**[BRACKETED] placeholders:**
- Specific monthly/annual dollar figures for competitor bot subscription fees — requires competitor-pricing sweep the market research did not capture at unit-price level (market research is explicit that "pricing transparency is incomplete for several products")

---

### Revised: "The Vision" → "Solution" (reframed for investor audience)

**Addresses research requirement:** Synthesis §6 ("less 'here is our vision and workflow' and more 'here is the opportunity, here is why we win'"); Writing Style ("confidence paired with candor," "storytelling leads, data as proof"). Shifted framing from user-facing commitments ("your data is yours") to structural commitments investors can evaluate against the competitive field (durable operational state as vendor lock-in replacement, declarative intent with reconciliation as differentiator).

**Traces to:**
- `proposal.md` Design Principles — all six structural commitments sourced directly
- `market research.md` Cross-cutting Findings — causal chain gap, vendor lock-in, retention gating
- `market research.md` §6 Gap Analysis — declared-intent control plane absence
- `problem.md` §9 — attention as scarcest resource; notification cascade problem

**Preserved:** The core narrative voice and the reframing keeps alignment with how the existing "How It Works" workflows read.

---

### Revised: "What Makes This Different" → "Competitive Positioning" (matrix + moat argument)

**Addresses research requirement:** Synthesis §3 (reposition away from "no competitor" language; compare against manual status quo, generic bots, point tools, potential incumbent overlap; argue why integrated system is harder to copy); Competitive Positioning research ("no direct competitor is the wrong framing"; "answer to 'what if MEE6 or Carl-bot adds this?' should be a moat argument, not a feature argument").

**Traces to:**
- `problem.md` §3, §6, §7 — manual status quo breaks at scale
- `market research.md` §1, §7 Cross-Bot Gaps — generic bot limitations
- `market research.md` §2, §7 — point tool vendor instability (Gather, Guilded)
- `market research.md` Cross-cutting Findings — shared causal chain absence
- `market research.md` §6, §7 Gap Analysis — declared-intent control plane absence
- `executive roadmap.md` Competitive Positioning — Phase 1 substrate as floor no competitor offers
- `proposal.md` Design Principles — lifecycle-first objects, scoped authority

---

### Added: "Business / Funding Model" (after "Competitive Positioning")

**Addresses research requirement:** Synthesis §4 (honest about stage, no revenue yet; show burn, runway, cost buckets, planned monetization, next de-risking milestone); Synthesis §7 (audience variants — open-source vs SaaS paths both described).

**Traces to:**
- `NOTES.md` — Humility community as design reference (pre-product honesty)
- `executive roadmap.md` Phase 0, Phase 2 — current stage and next milestone
- `market research.md` §7 — vendor instability as community-ownership value prop
- `market research.md` Cross-cutting Findings — premium gating patterns inform SaaS path
- `DECISIONS.md` D2, D5, D6 — cost buckets (Vultr infrastructure, Google Cloud Vision, Gemini fallback)
- `executive roadmap.md` Value Realization by Phase — Phase 2 as next de-risking milestone
- `research/pitch-deck-communication.md` Open Source / Community Project Patterns — sponsor value framing
- `research/pitch-deck-communication.md` Financial Communication — 12–18 month runway rule of thumb

**[BRACKETED] placeholders:**
- Monthly cost estimate for Vultr VKE infrastructure (scale dependent)
- OCR monthly cost projections (depends on screenshot volume × community count)
- OCR fallback-rate monthly cost
- Contributor-time FTE equivalent
- Current monthly burn
- Projected monthly burn under proposed commitment
- Runway under proposed raise / commitment

Reason for brackets: guardrail forbids invented financial numbers; specific figures require user input from infrastructure sizing, commitment structure, and community-size assumptions.

---

### Added: "Risks and Mitigation" (after "Business / Funding Model")

**Addresses research requirement:** Synthesis §5 (explicit top 3–4 risks, each paired with mitigation and milestone that demonstrates progress); Risk Communication ("investors want risk surfaced, not hidden"; "credible mitigation strategy is specific").

**Traces to:**
- `executive roadmap.md` Risk Register #3 — competitive window closure (market misread)
- `executive roadmap.md` Risk Register #5 — adoption friction from absent migration tooling
- `DECISIONS.md` D5, D6 — OCR architecture decisions
- `problem.md` §6, `market research.md` §5 — compliance workflow pain severity
- `executive roadmap.md` Strategic Narrative, Phase 1 — substrate-first defensibility argument
- `executive roadmap.md` Value Realization by Phase — phase-boundary milestones as de-risking events

**Selection rationale:** The executive roadmap lists seven risks; four were surfaced here as most material to investor audience (competitive, adoption, technical pipeline, contributor sustainability). The other three risks (chapter-provisioning bottleneck, Phase 0 scope ambiguity, depth-metric ambiguity) are execution/methodology risks that are load-bearing internally but less legible to external investors. Appendix reference points to full register.

---

### Added: "Team / Why Us" (before "The Ask")

**Addresses research requirement:** Synthesis §1 (missing team section in current deck); Writing Style guidance on credibility.

**Traces to:**
- `NOTES.md` — Humility community as design reference, 83 members, chapter scaffolding, applications subsystem live
- `product-strategy/problem.md` — complete 14-axis problem definition as team-produced artifact
- `product-strategy/market research.md` — 50-product, 6-category competitive analysis as team-produced artifact
- `product-strategy/executive roadmap.md` — 18-slice roadmap with risk register as team-produced artifact
- `product-strategy/proposal.md` — system design as team-produced artifact

**[BRACKETED] placeholders:**
- Founder / lead maintainer name and relevant experience
- Additional contributors or advisors
- Specific experience with Discord platform / operational workflows / relevant technical domains

Reason for brackets: guardrail forbids inventing team credentials. Structure provided with a suggested frame ("why this community, why this team, what's already produced") that the user can complete.

---

### Revised: "Get Involved" → "The Ask" (audience-variant structure)

**Addresses research requirement:** Synthesis §1 (ask / use of funds / milestone plan / runway); Synthesis §7 (audience variants — investor/backer vs contributor/community); Financial Communication ("use-of-funds slide should show how much, what for, what milestone it gets you to").

**Traces to:**
- `executive roadmap.md` Value Realization by Phase — Phase 2 as next milestone
- `market research.md` §2, §3, §4 — competitor counts (eight application tools, nine ticket tools, eight multi-unit suites)
- `executive roadmap.md` Approval Package — Non-goals boundaries for sponsor influence
- `research/pitch-deck-communication.md` Open Source / Community Project Patterns — sponsor value clarity

**[BRACKETED] placeholders:**
- Specific investment commitment amount
- Infrastructure runway months at projected burn
- Target design-partner community count beyond Humility reference
- Monthly sponsorship range or per-tier amount for open-source path

Reason for brackets: guardrail forbids invented financial numbers; specific asks require user input.

---

### Added: "Appendix / Q&A Preparation" (end of deck)

**Addresses research requirement:** "Appendix material belongs outside the core narrative. YC says the appendix should hold Q&A ammunition." Keeps core deck focused while giving investors pointers to deeper detail on demand.

**Traces to:** Pointers only — references the strategy artifacts rather than duplicating content.

---

## Preserved Without Changes

Per the user's guardrails ("Do NOT polish existing prose"; "Preserve all existing sections that work"):

- **The Problem** — Monday-morning narrative vignette and five compounding bullets
- **The Current Landscape** — bot-stack survey and fundamental-gap summary
- **How It Works** — three workflow walkthroughs (application review, compliance tracking, permission governance)
- **Roadmap** — four phases with "after this phase" and "what still hurts" framing; authoritative per `executive roadmap.md`

Section ordering of preserved sections matches the original. "How It Works" now sits between the new "Solution" section and the new "Competitive Positioning" section, which is consistent with the YC/Sequoia spine (problem → why now → market → solution → how → competition → business model → traction → team → ask).

---

## Research Requirements Status

| Synthesis requirement | Status |
|---|---|
| Standard investor spine (problem, solution, why now, market, competition, business model, traction, team, ask) | Addressed. "Traction" disclosed honestly as pre-product with Humility community as design reference. |
| Market sizing (bottom-up wedge) | Addressed. Explicit niche-first framing; adjacent expansion listed. |
| Competition (manual status quo, generic bots, point tools, incumbent overlap) | Addressed with matrix + moat argument. |
| Financials (burn, runway, cost buckets, monetization path, next milestone) | Structure provided; specific numbers marked [BRACKETED] per guardrail. |
| Risks + mitigation (top 3–4, each with milestone) | Addressed with 4 risks from executive roadmap risk register. |
| Tone (less "vision," more "opportunity / moat / risk / ask") | Addressed via Solution reframing, Competitive Positioning matrix, Risks section, The Ask section. |
| Audience variants (investor/backer vs contributor/community) | Addressed in "The Ask" with three distinct ask types. Open-source vs SaaS paths described in Business Model. |

---

## [BRACKETED] Placeholders — Summary for User

### Business / Funding Model
- Monthly Vultr VKE infrastructure cost
- Monthly Google Cloud Vision OCR cost (depends on screenshot volume and community count)
- Monthly Gemini 3 Flash Preview fallback cost
- Contributor-time FTE equivalent
- Current monthly burn
- Projected monthly burn under proposed commitment
- Runway under proposed raise / commitment

### Market Opportunity
- Specific monthly/annual dollar figures for current competitor bot subscription fees (requires a competitor-pricing sweep that market research.md did not capture at unit-price level)

### Team / Why Us
- Founder / lead maintainer name and relevant experience
- Additional contributors or advisors if applicable
- Specific experience with Discord platform, operational workflows, or relevant technical domains (OCR, distributed systems, community governance)

### The Ask
- Specific commitment amount (investor path)
- Infrastructure runway months at projected burn
- Target design-partner community count
- Monthly sponsorship range or per-tier amount (open-source path)

---

## Research Requirements Not Fully Addressed (with Reasons)

- **Specific competitor unit pricing (MEE6 Premium, Ticket Tool subscription tiers, etc.).** The prompt suggested these as concrete numbers, but `market research.md` does not report unit pricing; it only reports that "pricing transparency is incomplete for several products, especially where premium sales are routed through Discord, Patreon, or app marketplaces rather than a public price page" (Evidence Gaps). Per the guardrail against inventing financial numbers, specific dollar amounts for competitor subscriptions were not included. User can add these after an independent pricing sweep.
- **Traction signals beyond "Humility community as design reference."** No paying users, no external design partners yet. The deck names this honestly ("Pre-product. No revenue. No paying users."). The research accepts this for early stage (OpenVC: "early-stage founders without revenue should focus on unit economics and financial KPIs").
- **Exact calendar timing for phase delivery.** The executive roadmap is explicit that "no calendar dates are committed. Value realization is expressed by phase completion, not by date." The pitch deck preserves this discipline rather than inventing dates, consistent with the research recommendation to label confidence explicitly.
