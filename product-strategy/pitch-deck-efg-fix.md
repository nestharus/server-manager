# Pitch Deck E+F+G Fix Report

## Scope

**Concerns combined:** Rubric 3 (flow/cohesion), Rubric 4 (adversarial robustness), Editorial (tempo, rationed patterns, tightening, soft tells).

Confined to surgical wording fixes. No section moves, no factual changes, no scope shifts. All `[BRACKETED:...]` placeholders preserved. All citations preserved.

---

## Rubric 3: Flow and Cohesion

### Findings

- **Paragraph unity:** Each paragraph already develops one idea; no rewrites needed.
- **Known-to-new pattern:** Sentences chain familiar-to-new across the deck.
- **Major-claim because lines:** Every major claim has a "because" backed by a citation (`market research.md`, `problem.md`, `proposal.md`, `executive roadmap.md`, `DECISIONS.md`).
- **Concrete before abstract:** Opening narrative anchors before bullets abstract; How It Works grounds each subsystem with a "Today" scene before the proposed flow.
- **Borders:** Section borders carry bridges (e.g., the "operational profile resolves to a single architectural requirement" bridge into Operator-Owned Durable State).

### Fixes

**Line 23 — split overloaded compound sentence (cognitive load).**

- Before: "...scattered across ticket bots, application bots, spreadsheets, and DMs, and none of them can reconstruct what actually happened across the whole lifecycle of a member or a case."
- After: "...scattered across ticket bots, application bots, spreadsheets, and DMs. None of them can reconstruct the whole lifecycle of a member or a case."
- Technique: Period split. Reduces the comma load and lets the second claim land on its own.
- Also dropped redundant "all of these patterns" → "these patterns" and "what actually happened across" → direct reference.

---

## Rubric 4: Adversarial Robustness

### Pushback pass — VC objections

| Objection | Where addressed | Verdict |
|---|---|---|
| "You have no traction." | Business / Funding Model → Current Stage: "Pre-product. No revenue. No paying users." | Honest acknowledgement, narrowed to commitment ask, not revenue ask. Passes. |
| "This is niche." | Market Opportunity → First Wedge → Adjacent Expansion + explicit Scope subsection rejecting top-down TAM. | Wedge framing preempts; adjacent segments named; refusal to overclaim signals discipline. Passes. |
| "What if MEE6 / Carl-bot adds these features?" | Risk 1 (Competitive window closure) + Competitive Positioning row 4 + "Why the integration is harder to copy than any single feature." | Narrowed: incumbents can copy a single feature, not the substrate. The architectural choices required are enumerated. Passes. |
| "How do you make money?" | Business / Funding Model → Path A (open source community) + Path B (hosted SaaS, future) + Cost Structure + Burn/Runway/Milestone. | Two paths, neither overclaimed; explicit "neither is validated yet". Passes. |
| "Who is the team?" | Team / Why Us section with explicit `[BRACKETED]` placeholders + concrete list of strategic artifacts already produced. | Honest acknowledgement of placeholders; produced-work list provides real signal. Passes for the pre-fill stage; user must complete brackets before sending. |

### Worst-case reader test

Hostile reader profile: an officer skeptical of open-source funding promises ("they'll abandon it"), allergic to "niche" framing, burned by bot vendors that overpromise.

- **Open-source abandonment fear:** Risk 4 (Volunteer contributor sustainability) names this directly, not as a footnote. Phase scoping ensures coherent stopping points instead of a half-built substrate.
- **"Niche" allergy:** Adjacent segments are named (creator teams, mod teams, fandom communities, esports orgs) without claiming them as today's market.
- **Vendor-overpromise fear:** Pre-product framing is unambiguous. Cost buckets are listed with `[BRACKETED]` instead of fabricated numbers; the deck refuses to invent revenue projections.

### Quote test (3 random sentences)

1. **"Pre-product. No revenue. No paying users."**
   - Hostile read: "By their own admission they have nothing." This is the intent — honest framing. The next sentence redirects: the ask at this stage is commitment, not revenue.
   - Verdict: Passes. Hostile read confirms intent.

2. **"A community-owned codebase cannot be deprecated by a vendor decision."**
   - Hostile read: "But it can be abandoned by contributors." This is exactly the failure mode Risk 4 names. The deck does not leave the claim un-defended.
   - Verdict: Passes. Adjacent risk register absorbs the rebuttal.

3. **"The reference community is Humility itself (83 members during the operational sweep, per `NOTES.md`)."**
   - Hostile read: "They're pitching a platform on 83 members of validation." Defended by Market Opportunity §First Wedge stating the buyer profile is 50–500 members, putting Humility squarely in the wedge as a *design reference*, not a TAM claim.
   - Verdict: Passes when read in context. Standalone pull-quote is contained because the explicit "design reference" framing is repeated in the Team section.

### Evidence toggle

Every empirical claim is either cited, scoped to a specific community, or labeled as a hypothesis:

- Competitor capability claims → `market research.md` with section reference.
- Operator pain claims → `problem.md` with axis number.
- Phase sequencing claims → `executive roadmap.md` Phase Structure / Risk Register.
- Infrastructure claims → `DECISIONS.md` D2/D5/D6.
- Cost figures → `[BRACKETED]` placeholders, not fabricated numbers.
- Team experience → `[BRACKETED]` placeholders, not invented.

No new uncited empirical claims introduced.

---

## Editorial: Tempo, Rationed Patterns, Tightening, Soft Tells

### Tempo

- Sentence-length distribution varies through narrative paragraphs. The opening Monday-morning vignette is one long-form scene; the Patterns bullets keep the prose from flatlining.
- The roadmap and risks sections use structured per-phase / per-risk formatting that some readers will find metronomic, but for a pitch deck that structure is what the audience expects (per WRITING_SKILL_MASTER pitch-deck adaptation: closure is allowed at section boundaries).
- Risk 4 deliberately breaks the four-subheading pattern of Risks 1–3 by switching to prose. Kept this deliberate variation; it's the correct break in rhythm.

### Rationed pattern budgets

| Pattern | Budget | Used | Status |
|---|---|---|---|
| Staccato closers | 1–2 | 2 ("Each tool solves one thing. Nothing connects." / "Pre-product. No revenue. No paying users.") | At budget. |
| Parallel paragraph openings | rare | The Ask intro had 3 parallel "[Audience] [verb] [object]" sentences; broken below. Roadmap "After Phase X, you can:" labels are structural per-phase summary, not prose openings. | Fixed. |
| Imperative chains | 1 | The Ask → For Contributors / Design Partners (Review / Describe / Test). | At budget. |
| Contrast pairs | tool, not metronome | "Today vs With Humility" used 3 times across How It Works subsections; explicit walkthrough device, not rhetorical tic. | Acceptable use. |
| Rhetorical Q+A | 1 | None in prose. "What still hurts:" / "What sponsors get:" are declarative section labels, not Q+A. | Within budget. |

### Tightening

| Line | Before | After | Why |
|---|---|---|---|
| 13 | "is a primary source of volunteer burnout" | "drives volunteer burnout" | Removes the "is a [adjective] [noun] of" construction. |
| 23 | "and none of them can reconstruct what actually happened across the whole lifecycle" | "None of them can reconstruct the whole lifecycle" | Period split + drops "what actually happened across" filler. |
| 48 | "competitive window that is open but finite" | "competitive window with a finite life" | Removes the open/opens repetition with the prior verb. |
| 49 | "actively evaluating replacements right now" | "evaluating replacements now" | "actively" + "right now" doubled the same idea. |
| 99 | "would not be credible for this stage" | "lacks credibility at this stage" | Removes modal hedge; positive verb. |
| 133 | "the questions that were actually asked" | "the questions originally asked" | Drops "actually" filler. |
| 141 | "judgment calls, not on data entry" | "judgment calls, not data entry" | Drops the second "on". |
| 157 | "specific weaknesses Humility is designed to address" | "specific weaknesses the design addresses" | Active verb; drops "is designed to". |

### Soft AI tells removed

- **Default-negative posturing:** Most negatives in the deck exclude plausible misreadings (e.g., "no concept of intended state to audit against", "no reviewed product exposes a declared-intent control plane") rather than postur. Kept those as load-bearing.
- **Comma-heavy list-like sentences:** The closer in The Problem (line 23) was the worst offender; split.
- **Performative summary:** No final "in conclusion" beats anywhere; the deck closes on call-to-action subsections without a wrap-up paragraph.

### Parallel-structure fix in The Ask intro

**Before:**

> Investors fund infrastructure and engineering runway. Community sponsors fund operational continuity for a codebase vendors cannot deprecate. Contributors and design partners trade time and feedback for early influence on Phase 1 and Phase 2 design.

Three sentences with the same `[Audience] [verb] [object]` frame. Trips the "three consecutive sentences with the same grammatical frame" guard.

**After:**

> Investors fund infrastructure and engineering runway. The community-sponsorship path secures operational continuity for a codebase vendors cannot deprecate. For contributors and design partners, time and feedback buys early influence on Phase 1 and Phase 2 design.

The second sentence now leads with the path (object as subject); the third inverts to "For [audience], [exchange object] buys [outcome]". Each sentence has a different shape.

### Wording fix: "volunteer" → "officer" burnout (line 76)

The phrase "volunteer burnout is the dominant churn mechanism" sat next to "Officer attention is the scarcest resource" and could be misread as referring to Humility's own contributors (the subject of Risk 4), not to officers in target communities. Changed to "officer burnout" to disambiguate.

### Grammar fix

- Line 332: "A 18-value-slice" → "An 18-value-slice" (vowel sound).

---

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No major changes. All edits are surgical wording adjustments. Restart-from-Rubric-1 not triggered.

---

## Known Remaining Concerns

- **Team / Why Us is still placeholder-heavy.** The user must populate the `[BRACKETED]` blocks before sending the deck. Until then, "Who is the team?" survives only on the produced-artifacts list.
- **Cost / burn / runway are all `[BRACKETED]`.** A sophisticated investor will skim straight to those numbers. The fix report does not invent them; the user must fill before sending.
- **The "What still hurts:" label appears in Phases 1, 2, 3 (Phase 4 uses "What's deferred:").** Three identical labels is borderline metronomic, but for a roadmap section the consistency aids readability; left alone.
- **Bullet lists across Operator-Owned Durable State (six bullets) and Competitive Positioning (four-row table + four numbered sub-points) are list-heavy.** Pitch-deck format sustains this; reviewers may flag it on a stricter pass.
- **"Officers do not buy Humility against a single rival." opens Competitive Positioning with a structural negative.** Kept because it sets up the four-class taxonomy in the next sentence; flipping it would weaken the frame.
