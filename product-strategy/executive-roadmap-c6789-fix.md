# C6-C9 Fix Report: Executive Roadmap

## Scope

**Concerns fixed:** V-6 (grammatical frame), V-10 (cliches), V-11 (moralizing/status language), V-12 (performative intent)

| Category | In violation report | Fixed | Skipped (false positive) | Extra (caught during rescan) |
|---|---|---|---|---|
| V-6 grammatical frame | 2 | 2 | 0 | 0 |
| V-10 cliches | 6 | 6 | 0 | 1 |
| V-11 moralizing/status | 6 | 2 | 4 | 0 |
| V-12 performative intent | 7 | 7 | 0 | 1 |
| **Total** | **21** | **17** | **4** | **2** |

The four V-11 skips are all uses of `table-stakes` as a defined classification term in the Appendix A scoring methodology. Rationale in "Instances skipped" below.

Two extra instances of the same patterns were caught during rescan (one V-10, one V-12) and fixed for consistency with the flagged rewrites.

---

## Fixes by Category

### V-6 Three consecutive sentences with same grammatical frame (2 fixed)

#### Instance 1 — Phase 2 Capability gained bullets (old line 126, now ~151–153)
**Before:**
```
- Officers process structured applications with single-reviewer ownership
- Tickets progress through category-specific state machines with privacy controls
- New chapters are provisioned from templates through approval gates
```
All three shared the `[plural subject] [verb] [prep-phrase] [with/through prep-phrase]` frame.

**After:**
```
- Officers process structured applications with single-reviewer ownership
- Each ticket category has its own state machine with privacy controls
- New chapters are provisioned from templates through approval gates
```
**Technique:** Recast bullet #2 to a different frame (`Each X has its own Y`), breaking the run.

#### Instance 2 — Phase 4 Success condition bullets (old line 188, now ~235–237)
**Before:**
```
- Compliance evaluation runs on schedule with OCR-parsed evidence and graduated consequences
- Chapters enter probation and archival with formal state transitions
- Leadership succession preserves pending work and authority with predecessor-linked grants
```
All three shared the `[abstract subject] [verb] [prep-phrase with "with"]` frame.

**After:**
```
- Compliance evaluation runs on schedule with OCR-parsed evidence and graduated consequences
- Probation and archival become formal chapter states with defined transitions
- Leadership succession preserves pending work and authority with predecessor-linked grants
```
**Technique:** Recast bullet #2 so the subject shifts from "chapters" (an actor) to "probation and archival" (the states themselves) and the verb becomes a different shape.

---

### V-10 Cliches (6 fixed + 1 extra)

#### Instance 1 — Line 9 "Competitive window is open"
**Before:** `- **Competitive window is open.** Gather is deprecated and Guilded is shut down...`
**After:** `- **Vendors are departing while market gaps remain unfilled.** Gather is deprecated and Guilded is shut down...`
**Technique:** Replace "window of opportunity" cliche with a direct observation of the two conditions that matter (vendor departures + unfilled gaps).

#### Instance 2 — Line 34 "one coherent story"
**Before:** `The four phases tell one coherent story, not four independent tracks but a single sequence in which each phase unlocks operational leverage the prior phase could not deliver and reduces a class of risk the prior phase could not contain.`
**After:** `The four phases are a single sequence, not four independent tracks. Each phase unlocks operational leverage the prior phase could not deliver and reduces a class of risk the prior phase could not contain.`
**Technique:** Replace "tell one coherent story" (narrative cliche) with plain assertion "are a single sequence". Period split for readability.

#### Instance 3 — Line 38 "table-stakes crowd"
**Before:** `**Phase 2. Capture the operational table-stakes crowd.** With the governance substrate in place...`
**After:** `**Phase 2. Reach parity on the operational workflows competitors already monetize.** With the governance substrate in place...`
**Technique:** Replace jargon heading with a direct description of the move (reach parity + what's contested).

#### Instance 4 — Line 40 "strongest willingness-to-pay signal" (Strategic Narrative Phase 3)
**Before:** `...complete the "integrated roster plus activity plus analytics" package that the market research identifies as the strongest willingness-to-pay signal (``market research.md`` §5).`
**After:** `...complete the "integrated roster plus activity plus analytics" package that six market research sources identify as the integration operators most readily pay for (``market research.md`` §5).`
**Technique:** Replace marketing cliche with direct behavioral claim (operators pay for it) and cite the source count (six).

#### Instance 5 — Old line 140, now ~186 "strongest willingness-to-pay signal in the market" (Phase 3 Business outcome)
**Before:** `**Business outcome.** The "integrated roster plus activity plus analytics" package that six sources show as the strongest willingness-to-pay signal in the market (``market research.md`` §5).`
**After:** `**Business outcome.** The "integrated roster plus activity plus analytics" package that six sources identify as the integration operators most readily pay for (``market research.md`` §5).`
**Technique:** Same substitution as Instance 4.

#### Instance 6 — Old line 574, now ~725 (VS-011 Pain severity)
**Before:** `The strongest willingness-to-pay signal is for integrated roster plus activity plus analytics (6 sources).`
**After:** `Six sources identify integrated roster plus activity plus analytics as the integration operators most readily pay for.`
**Technique:** Same substitution. Source-count citation retained. The direct quotation of the source phrase at the end of the line (in quotes, as a citation) is preserved unchanged.

#### Extra instance (caught during rescan) — Line 19 "strongest willingness-to-pay signal" (Executive Summary bullet)
Not in the original violation report, but the same cliche phrase.
**Before:** `...the integrated-roster-plus-activity package that "six sources" show as the strongest willingness-to-pay signal (``market research.md`` §5).`
**After:** `...the integrated-roster-plus-activity package that "six sources" identify as the integration operators most readily pay for (``market research.md`` §5).`
**Technique:** Same substitution as Instances 4–6. Fixed for consistency with the flagged rewrites.

---

### V-11 Moralizing or status language (2 fixed + 4 false positives)

#### Instance 1 — Old line 148, now ~194 "table-stakes or gap pain" (Phase 3 Confidence)
**Before:** `**Confidence.** Likely for VS-011 (roster) and VS-013 (SLA): table-stakes or gap pain with clear dependency chain. Aspirational for VS-012...`
**After:** `**Confidence.** Likely for VS-011 (roster) and VS-013 (SLA) given strong competitive pressure and direct dependency chains. Aspirational for VS-012...`
**Technique:** Replace jargon shorthand with concrete operational claim (strong competitive pressure, direct dependency chains).

#### Instance 2 — Old line 528, now ~679 "non-viable for multi-chapter organizations" (VS-005)
**Before:** `A guild management platform without chapter support is non-viable for multi-chapter organizations.`
**After:** `A guild management platform without chapter support cannot serve organizations running multiple chapters.`
**Technique:** Replace status-judgment phrase ("non-viable") with a direct statement of what the platform cannot do.

#### Instances skipped (4 false positives)
- **Old line 510 / now ~661** (VS-007 Competitive position): `table-stakes`
- **Old line 519 / now ~670** (VS-006 Competitive position): `table-stakes`
- **Old line 575 / now ~726** (VS-011 Competitive position): `table-stakes`
- **Old line 613 / now ~764** (VS-016 Competitive position): `table-stakes`

**Reason:** `table-stakes` is a defined classification label in the scoring methodology (Appendix A):
> `Competitive position: gap (no competitor offers this; weight 1.5) / parity (1–2 competitors offer similar but limited; weight 1.0) / table-stakes (3+ competitors offer this, must-have; weight 2.0).`

Each of the four flagged instances is a per-slice `**Competitive position:** table-stakes` field that maps the slice to the scoring weight. These are references to the defined term, not prose moralizing. Renaming `table-stakes` in these fields would require renaming the classification across the methodology, Risk Register mention (Row 3 trigger indicator), review cadence ("reclassified a gap as parity or table-stakes"), and all per-slice scoring entries — a broader factual change to the scoring scheme, which falls outside this pass's scope.

---

### V-12 Performative intent sentences (7 fixed + 1 extra)

#### Instance 1 — Line 20 "completing the proposal scope"
**Before:** `- **After Phase 4:** Chapters have full governance lifecycle (probation, archival) with leadership succession and evidence-based compliance evaluation, completing the proposal scope.`
**After:** `- **After Phase 4:** Chapters have full governance lifecycle (probation, archival) with leadership succession and evidence-based compliance evaluation.`
**Technique:** Delete the trailing clause; the phase-completion framing was rhetorical, not informational.

#### Instance 2 — Line 42 "Phase 4 completes the proposal scope." (Strategic Narrative)
**Before:** `...("general-purpose compliance engine is still missing"; "succession and delegated-local-authority continuity remain implicit rather than modeled") (``market research.md`` §4, §5). Phase 4 completes the proposal scope.`
**After:** `...("general-purpose compliance engine is still missing"; "succession and delegated-local-authority continuity remain implicit rather than modeled") (``market research.md`` §4, §5).`
**Technique:** Delete the closing summary sentence; citations stand.

#### Instance 3 — Line 72 "The executive roadmap identifies this phase but does not detail its contents."
**Before:** `...and platform assumption verification at startup. The executive roadmap identifies this phase but does not detail its contents.`
**After:** `...and platform assumption verification at startup.`
**Technique:** Delete. The heading ("engineering-defined") and the surrounding content already convey that contents are engineering-scoped.

#### Instance 4 — Old line 177, now ~239 "Completes proposal scope." (Phase 4 Value realization window)
**Before:** `**Value realization window.** Completes proposal scope.`
**After:** `**Value realization window.** Officers move off manual compliance work, chapters gain formal lifecycle states, and leadership transitions preserve operational context.`
**Technique:** Replace performative one-liner with concrete operator-visible outcomes, matching the depth of the other phases' Value realization windows.

#### Instance 5 — Old line 192, now ~259 "All proposal capabilities are delivered at Phase 4 completion."
**Before (field):**
```
**Not yet built:** All proposal capabilities are delivered at Phase 4 completion.

**Prerequisites:** Phase 3
```
**After:**
```
**Prerequisites:** Phase 3
```
**Technique:** Delete the "Not yet built" field entirely. At Phase 4 nothing remains in this category; a field with no content carries only performative weight.

#### Instance 6 — Old line 218, now ~289 "The proposal's differentiation is not any single feature — it is the integration pattern..."
**Before:** `Both of those distinguish the system from the action-centric claim flows and role-hierarchy automation competitors rely on. The proposal's differentiation is not any single feature. It is the integration pattern, and the integration pattern requires the Phase 1 substrate to exist first.`
**After:** `Both of those distinguish the system from the action-centric claim flows and role-hierarchy automation competitors rely on. None of these distinctions hold without the Phase 1 substrate underneath.`
**Technique:** Cut the two summary sentences and replace with one sentence that carries the load-bearing claim (dependency on Phase 1) without the rhetorical "it is the integration pattern" framing.

#### Instance 7 — Old line 224, now ~294 "The window exists because the market has not closed it, not because no one has tried."
**Before:** `- **Market gaps are documented, not speculative.** Every ``gap`` classification in the scoring traces to an explicit "Gap Analysis" section in the source research (``plans/risk/executive-market-misread.md`` F-3). The window exists because the market has not closed it, not because no one has tried.`
**After:** `- **Market gaps are documented, not speculative.** Every ``gap`` classification in the scoring traces to an explicit "Gap Analysis" section in the source research (``plans/risk/executive-market-misread.md`` F-3).`
**Technique:** Delete the closing rhetorical flourish. The prior sentence (with citation) already establishes the claim.

#### Extra instance (caught during rescan) — "Phase 4 completes the proposal scope." (Phase Structure > Phase 4 > Business outcome, line ~229)
Not in the original violation report. The same closing rhetorical pattern as Instance 2.
**Before:** `These capabilities the reviewed market has not addressed; Phase 4 completes the proposal scope.`
**After:** `The reviewed market has not addressed any of these capabilities.`
**Technique:** Rewrite the sentence so the performative tail is removed and the substantive claim (market hasn't addressed them) stands on its own.

---

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [x] Added or removed a section — **technically yes:** removed the "**Not yet built:**" field from Phase 4 (it held only performative content per V-12 Instance 5).

The "Not yet built" field deletion is localized and does not change phase ordering, slice composition, risk verdicts, opportunity cost claims, or evidence citations. Other phases' "Not yet built" fields are untouched. Flagging here so the orchestrator can decide whether this qualifies under the "Added or removed a section" restart trigger. My read: this is a field removal, not a section removal, and the surrounding Phase 4 structure is unchanged.

## Known Remaining Issues

- **`table-stakes` classification term.** The four false-positive skips rely on the premise that `table-stakes` is a legitimate domain-specific term because it is defined in the scoring methodology. A stricter reviewer could argue that the methodology itself should rename the term (it still contains "must-have" moralizing in parenthetical definition). Renaming would cascade across the Risk Register, review cadence, scoring methodology, and all 18 slice scoring entries — treat as a separate, broader pass if desired.
- **"willingness-to-pay signal" in direct-quote citations (VS-011 line ~725).** The phrase survives inside a `""..."" Strong evidence, 6 sources` citation where it is quoted verbatim from `market research.md` §5. Preserving citations verbatim is an explicit guardrail, so this was kept.
- **"must-have"** appears in Appendix A scoring methodology definition (`table-stakes (3+ competitors offer this, must-have; weight 2.0)`). Not flagged in the violation report; left alone to keep classification definitions stable. A future V-11 pass might revisit.
