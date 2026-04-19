# Pitch Deck Investor Rubric Fix Report

## Scope

Single pass addressing all 53 flagged violations plus Rubrics 1, 3, 4 and editorial polish on `product-strategy/pitch deck.md`. Em dashes were already zero; confirmed zero after pass. No banned openers introduced. Factual content (economics numbers, citations, HYBRID verdict, BRACKETED placeholders) preserved.

## Hard ban fixes by category

### Triads in prose (25 flagged, 24 fixed, 1 deliberate exception)

| Line | Technique |
|---|---|
| L23 "ticket bots, application bots, spreadsheets, and DMs" | Compressed to "distributed across bots and spreadsheets that cannot be reassembled into a single lifecycle." |
| L29 "ticket bot, application bot, moderation-log bot, reaction-role bot, spreadsheet, DMs" | Converted inline list into explicit markdown bullet list (allowed) |
| L41 "applications, rosters, permissions, and compliance consequences" | Reshaped: "from intake through every downstream consequence" |
| L51 quote: "intake, cases, chapters, permissions, and compliance" | **Deliberate exception.** Verbatim source quote from `market research.md` Cross-cutting Findings; altering would misattribute research. |
| L55 "Claiming, transcript depth, log history, exports, alliance capacity, and backup/restore" | Compressed to "from claim workflow through backup/restore" (2 items, preposition-joined) |
| L57 "intent-vs-actual control plane, cross-subsystem causal audit, or policy preview-confirm semantics" | Dropped third item: "intent-vs-actual control plane or a cross-subsystem causal audit" |
| L81 "chapter operations, application review, activity compliance, and multi-officer governance" | Rewrote: "multi-officer chapter operations, handling intake and compliance on the same volunteer team" |
| L90 parenthetical "screenshot review, spreadsheet transcription, threshold comparison, individual DMs" | Rewrote: "transcribing screenshots into a spreadsheet and DMing each member behind on thresholds" |
| L111 "(intake, cases, rosters, permissions, audit)" | Dropped parenthetical: "the same operational primitives" |
| L121 "intake, cases, compliance, permissions, chapters, and governance" | Rewrote: "whose subsystems share a unified audit chain, from intake through governance" |
| L127 "actor, inputs, prior state, and governing policy version" | Split into two "and"-joined pairs: "alongside the actor and its inputs, against prior state under the policy version active at transition time" |
| L141 "application review, compliance tracking, and permission governance" | Dropped enumeration; section headings already name the three |
| L155 "(attendance minimums, rank requirements, activity thresholds)" | Compressed: "such as attendance minimums and activity thresholds" |
| L182 "roster entry, compliance activation, and permission grant" | Dropped middle item: "roster entry and permission grant" |
| L183 "permissions, policy, and compliance rules" | Dropped middle item: "permissions and compliance rules" |
| L185 "(applications, tickets, chapters, members)" | Compressed: "like applications and tickets" |
| L197 "design, problem definition, competitive landscape, and strategic roadmap" | Split: "design and strategic roadmap are complete, with problem definition and competitive landscape documented alongside" |
| L221 parenthetical "(creator teams, mod teams, fandom communities, esports organizations)" | Reference back: "documented above" |
| L242 "applications, ticket state machines, chapter provisioning, permission drift detection" | Split: "applications and per-category ticket state machines alongside chapter provisioning and drift detection" |
| L270 "(trust, authority, causal audit, policy versioning)" | Compressed: "scoped authority and causal audit with policy versioning underneath" |
| L306 "(creator teams, mod teams, fandom communities, esports organizations)" | Reference back: "documented in Market Opportunity" |
| L310 "mod teams, creator teams, fandom communities, and esports orgs" | Compressed: "serve mod teams and esports orgs as readily as they serve gaming guilds" |
| L364 "(scoped authority, causal audit, declared intent)" | Rewrote: "scoped authority and declared intent under causal audit" |
| L422 "applications, ticket state machines, chapter provisioning, permission drift detection" | Same treatment as L242 |
| L431 "(scoped authority, declared intent, causal audit...)" | Dropped causal audit: "scoped authority and declared intent work identically across these segments" |

### Pseudo lists from parallel clauses (2 / 2)

- **L147** "add notes, request a private interview, approve with a mandatory reason, deny with a mandatory reason, or place the applicant on a waitlist" → Split into two sentences with unequal weight: "Reviewers add notes or request an interview as needed, and can waitlist the applicant if a decision isn't ready. Final adjudication is approval or denial with a mandatory reason."
- **L153** six-verb chain → Split: "Every week, an officer pulls screenshots from the submission channel and transcribes the activity data into a spreadsheet. Each member is compared against chapter-specific thresholds, and violators are DMed individually."

### Throat clearing phrases (4 / 4)

All four labeled-paragraph openers removed; bodies start with content directly.

- **L75** `**Methodology note.**` removed
- **L221** `**Wedge-expansion rationale.**` removed
- **L256** `**Market-cap caveat.**` removed
- **L385** `**Market-cap caveat (repeat).**` removed

### Posturing frames (4 / 4)

- **L308** "The honest framing:" removed; content stated directly
- **L366** "This is an honest operator-economics signal:" removed; fact stated directly
- **L402** "The honest raise for a solo founder..." reshaped to "A solo founder at $9,500/mo burn, pre-product, with no traction yet raises a pre-seed round of $300k-$500k, not a seed round."
- **L424** "### Hybrid Market-Cap Framing (Read This Carefully)" → "### Hybrid Market-Cap Framing"; body already carries the weight.

### Cliches (6 / 6)

Every "competitive window" cliche replaced with concrete mechanism.

- **L47** "competitive window with a finite life" → "an opportunity that will compress as incumbents adapt"
- **L193** "A moat that lives in the architecture" → "A defense built into the architecture"
- **L268** "competitive window compresses" → "timing advantage compresses"
- **L296** "competitive window risk" → "timing-advantage risk"
- **L298** "timeline the competitive window requires" → "timeline incumbent response will force"
- **L422** "This is the de-risking event" → "This milestone validates willingness-to-pay"

### Moralizing or status language (6 / 6)

- **L308** "honest framing" — removed (see posturing)
- **L364** "A phased plan is only as credible as the person executing it." — removed; content claim now stated directly: "The governance substrate has to be designed by someone who has actually sat in the operator seat."
- **L366** "honest operator-economics signal" — removed
- **L368** "is not going to pretend full-time is already possible" → "cannot go full-time until revenue or a close makes it feasible"
- **L396** "foundation work that typically precedes implementation code" → "roughly two quarters of foundation work that shapes the implementation"
- **L402** "honest raise" — removed

### Performative intent sentences (6 / 6)

- **L23** "the rest of this deck is about why..." — removed
- **L115** "The next section describes the system that makes that possible." — removed; the architectural-requirement sentence now stands alone at section close, transitioning naturally into the next heading
- **L141** "The goal is not a feature tour; it is showing..." — merged into preceding sentence and reshaped
- **L262** "Of the seven specific risks..." meta-count — replaced with content-first open: "Four operational risks matter most to investors, and one market-cap risk sits beside them."
- **L318** "The phase sequence is how the risks above are contained in practice." — removed; the substrate-first sentence now opens the section
- **L431** "What this means for the investor decision:" — removed; "This is a hybrid bet." now opens the paragraph

## Story-beat findings (Rubric 1)

- **Hook creates tension tied to hypothesis.** Monday-morning scenario survived intact; it is the felt pain that makes "operator-owned durable state" land as a structural answer.
- **Reframe consolidated early.** "The shared failure across these patterns is that no tool owns the operational record." Unchanged position, strengthened by removing the deck-self-reference that trailed it.
- **Problem felt.** Preserved through the list of five recurring patterns, each with a concrete consequence.
- **Concrete anchor before abstraction.** Scenario → patterns → landscape → architectural answer → mechanism walkthroughs. Order preserved.
- **Hypothesis stated with confidence.** "Operator-owned durable state is the structural answer." Now ends the Problem section cleanly (performative tail removed).
- **Sections each do one job.** No section does double duty. Market Opportunity sizes; Operator-Owned Durable State specifies commitments; How It Works shows three mechanisms; Competitive Positioning stages alternatives.
- **Hidden skeleton.** Pitch-deck adaptation explicitly allows function-named headings; kept as-is, with content-named "Operator-Owned Durable State Replaces Vendor Lock-In" as the anchor section.

No section moved. No section removed. No arc altered. The restart-from-Rubric-1 rule is not triggered.

## Flow and cohesion findings (Rubric 3)

- **Paragraph unity.** Verified. Every paragraph develops one idea; no new jump-cuts introduced.
- **Known-to-new pattern.** Preserved. The replaced sentences in the "Reconstructable decisions" bullet and the "Compliance Tracking" workflow now carry prior information forward at sentence starts.
- **Every major claim has a "because".** Verified through the document: TAM/SAM/SOM basis column, pricing rationale, competitive positioning reasoning, risk mitigation structure. All load-bearing claims cite `market research.md`, `research/market-economics.md`, `executive roadmap.md`, `DECISIONS.md`, or public URLs.
- **Concrete before abstract.** Monday-morning concrete → abstract hypothesis → structural commitments → mechanism walkthroughs. Order survived.
- **Cognitive load after new-idea sequences.** The six-commitment bulleted list in Operator-Owned Durable State is the highest-density block. Each bullet now opens with a concrete contrast ("Competing products treat Discord...", "Discord's role hierarchy cannot express this..."). No additional cash-out sentence needed.
- **Borders.** Problem → Current Landscape → Why Now → Market Opportunity → Architecture → Mechanism → Competitive → Business → Risks → Roadmap → Team → Ask. Each join transitions on content, not meta-navigation.

## Adversarial robustness findings (Rubric 4)

### Pushback pass (VC objections)

- **"Pre-product, no revenue."** Made impossible as a critique by pricing the raise as pre-seed explicitly. Section "The Ask" opens: "A solo founder at $9,500/mo burn, pre-product, with no traction yet raises a pre-seed round of $300k-$500k, not a seed round." Risk Register #4 covers execution capacity explicitly.
- **"Solo founder, no team."** Preempted in Team / Why Us and Risk 4. Full-time gating conditions stated explicitly. MRR-gated hire triggers cited with Pave/Carta benchmarks.
- **"Niche market / not VC-scale."** Addressed by labeling the verdict HYBRID in bold at Market-Cap Feasibility, by dedicating Risk 5 to market-cap capacity, and by the Hybrid Market-Cap Framing subsection. Investor decision surface explicit.
- **"Adjacent expansion is hand-waved."** Addressed by tying expansion to the architectural portability of the Phase 1 substrate (scoped authority + declared intent work identically across segments) and by labeling expansion as Phase 4+, not Phase 1 scope.

### Worst-case reader (hostile skeptic of pre-seed pitches / hybrid verdicts)

The hostile reader's likeliest accusation: "They're admitting it's not a real VC opportunity and asking anyway." Preempted, not accepted: the deck frames the raise size to fit the wedge (not the expansion), tells the investor to weight expansion probability explicitly rather than assuming it, and gives the milestone ($720k Year-3 ARR + at least one adjacent design partner) that would validate the expansion bet. A hostile reader cannot pull the hybrid verdict out of context because every major reference to it is paired with the "fund the wedge; expansion is optional upside" framing.

### Quote test (3 random sentences)

1. **"Operator-owned durable state is the structural answer."** (L23 closer) — hostile misuse: "vague claim without mechanism." Survives because the next section delivers the mechanism (six commitments) and the Architecture section defines it concretely.
2. **"A 4-person team burn represents `0.39%-0.47%` of base-case SAM."** (Business Model closer) — hostile misuse: none plausible; empirical claim with citation.
3. **"This is a hybrid bet."** (Hybrid Market-Cap Framing opener) — hostile misuse: "even they admit it's not the real opportunity." Survives in context because the paragraph immediately distinguishes wedge (funded, solid) from expansion (unfunded, structurally supported, optional upside). Without context it can be weaponized; with context it preempts the weaponization.

No sentence required revision after quote test.

### Evidence toggle

Every empirical claim carries a citation or a concrete source URL. Verified categories:

- TAM/SAM/SOM bases: CNBC, Discord Guilds FAQ, Server Insights threshold, Guild Manager pricing, Shivtr, Gamer Launch, research doc §1.
- Competitor pricing: MEE6, Dyno, Carl-bot, Ticket Tool, Arcane, Guild Manager, Circle, Mighty Networks (each with URL).
- Infrastructure costs: Vultr VKE doc, Vultr pricing, Google Cloud Vision pricing, Vertex AI pricing.
- Compensation benchmarks: Pave, Carta, TopStartups (each with URL).
- Fundraising benchmarks: Carta 2025 pre-seed benchmarks, Rebel Fund dilution data.
- Competitive positioning: `market research.md` with section anchors.
- Risk register: `executive roadmap.md` with risk numbers.

No unlabeled empirical claims remain.

## Editorial findings (tempo, rationed patterns, tightening)

### Tempo

Scanned for metronomic stretches. The six-commitment bullet list is the most at-risk block; its bullets vary in sentence count (2 sentences each with uneven weight), so no flatline. The workflow "Today / With Humility" pairs use intentional parallel structure as a walkthrough device, not as accidental repetition — justified exception.

### Rationed pattern budgets

- **Staccato paragraph closers:** 2 visible. "Each tool solves one thing. Nothing connects." (Current Landscape) and the compressed "The operational core that eight application tools and nine ticket tools monetize today." (First Milestone). Within budget (1-2).
- **Parallel paragraph openings:** The six commitments and the workflow walkthroughs intentionally parallel; the Risks section's five risks use "The scenario / Why it matters / Mitigation / Milestone" which is a decision-memo pattern justified by the investor audience. No accidental parallels in prose.
- **Imperative chains:** None remain. The only imperative-feeling line is a quoted framing: "fund the wedge; the expansion bet is optional upside." 1 of 1.
- **Contrast pairs:** Used as tool at three locations (wedge vs VC-scale; Today vs With Humility; the manual status quo vs Humility's position). Not metronome.
- **Rhetorical Q+A:** 1 instance — "What is this member's full operational history?" at the end of Current Landscape. Within budget.

### Tightening

Multiple throat-clearing labels, performative meta-commentary, and redundant list enumerations removed. Net: roughly 8-10 fewer sentences in the pitch deck without losing any load-bearing claim. No "the honest X" postures survive.

### Tone consistency

Confident, evidence-grounded investor voice sustained. Hybrid verdict treated as positive signal of rigor, not apology.

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

None of the above. Individual sentence-level rewrites only. Restart-from-Rubric-1 rule is **not triggered**.

## Deliberate exceptions (documented)

- **L51 research quote preserved verbatim.** Failure mode the triad rule prevents: list-shaped prose reading as AI-generated filler. Keeping the source quote intact is the correct choice because (a) it is attributed research, and (b) altering it would misrepresent the source. The triad appears inside quotation marks, which a careful reader reads as citation, not authorial voice.
- **Workflow walkthrough parallelism ("Today / With Humility").** Failure mode parallel-opening rule prevents: inadvertent repetition as tic. This parallelism is the explicit structural scaffolding of the walkthrough, signposted to the reader; removing it would make the mechanism harder to follow, not easier.
- **Decision-memo headings per risk ("The scenario / Why it matters / Mitigation / Milestone").** Same logic: the investor audience expects and uses this structure to evaluate risk, and the style brief's pitch-deck adaptation permits function-named structure at section boundaries.

## Known remaining issues

- **Some marketing lists remain long but are inside markdown bullets or tables.** The ban counts explicit markdown list blocks as exempt. A strict reviewer could still object to the six-item premium-gating enumeration in the "Bot subscription fees" point; I left it because the six items are the research-backed features operators pay for, and compressing them loses empirical specificity the investor needs.
- **"Competitive window" appears once more as "competitive window closure" in Risk 1's heading.** The heading is load-bearing for a risk register; rewording to "timing-advantage closure" is possible but risks confusion with the risk register's external cross-reference label (`executive roadmap.md` Risk Register #3). Left in place as a heading-only reference; all prose instances of the cliche are gone.
- **Founder background bullets remain bracketed placeholders.** The prompt requires preservation. A reviewer seeing `[BRACKETED: ...]` markers should understand those are intentional fill-ins for the founder.
