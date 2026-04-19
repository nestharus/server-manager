# D5 Table Framing Fix Report: Executive Roadmap

## Scope

**Concern fixed:** D5 Table framing — ensure each table is preceded by prose that states the argument the table makes, points the reader to what to notice in the rows, and connects the table to surrounding narrative.

**Instances in analysis:** 3 tables (Risk Register, Opportunity Cost Summary, Per-Slice Scoring Detail).
**Instances strengthened:** 1 (Risk Register).
**Instances left unchanged because existing framing already works:** 2 (Opportunity Cost Summary, Per-Slice Scoring Detail).

The assigned strategy said explicitly: "Do not duplicate intros that already work." Two of the three tables already had framing prose added in earlier D3/D4 passes that satisfied the fix criteria. Adding more would have been noise.

## Assessment of each table

### 1. Risk Register (line 308) — strengthened

**Before:**

> Top risks carried through the three executive risk assessments (`plans/risk/executive-market-misread.md`, `plans/risk/executive-dependency-trap.md`, `plans/risk/executive-completeness.md`). All three assessments rate LOW overall; this register surfaces the specific findings executives should monitor.

**After:**

> This register translates the three executive risk assessments (`plans/risk/executive-market-misread.md`, `plans/risk/executive-dependency-trap.md`, `plans/risk/executive-completeness.md`) into operational monitoring. All three assessments rate LOW overall, so the argument the table makes is about monitoring rather than prediction: each row names a condition that would move the rating up and the trigger indicator that signals it firing. The Trigger indicator column is what monitoring watches for, and the Phase most affected column names where a fired trigger would land.

**What changed and why.** The original intro named the sources and rated them LOW, but did not state the argument the table makes or tell the reader what to notice. The revision:

1. States the argument explicitly ("monitoring rather than prediction"; rows are conditions plus triggers, not forecasts).
2. Points the reader to two specific columns (Trigger indicator, Phase most affected) so the reader scans the right fields.
3. Bridges to the Approval Package that follows, which commits leadership to act on the trigger indicators when they fire.

**Exit sentence.** Not added. The following Approval Package section's item 4 ("Executive commitment includes acting on those trigger indicators when they fire") already bridges from the table into the approval ask, so an exit sentence would duplicate that bridge.

### 2. Opportunity Cost Summary (line 349) — unchanged (already strong)

**Existing intro:**

> The Approval Package above names what leadership is committing to; the table below names what stays broken while the roadmap executes. Rows group value slices by the operational concern they address, and each entry traces the harm back to the problem-document section where operators describe the pattern in their own terms.

**Existing exit:**

> Every row above maps to operator testimony in the problem document, so the costs are observed rather than projected. The next section lists capabilities that sit outside this accounting because they are deferred beyond roadmap scope by design.

**Why unchanged.** The intro already does what D5 requires:

- States the argument (the table "names what stays broken while the roadmap executes" — this is the cost of the current phase ordering).
- Points the reader to how rows are organized (grouped by operational concern, traced back to `problem.md` §).
- Connects to the Approval Package above and the Deferred Subsystems below via the exit sentence.

### 3. Per-Slice Scoring Detail (appendix Section D, line 648) — unchanged (already strong)

The appendix section D does not use table markup; it uses formatted bulleted prose per slice. The D5 concern about "tables with minimal framing prose" still applies in spirit, but existing framing already covers both:

**Section-level intro (line 650):**

> Scoring detail accompanies each slice inside its phase bucket so reviewers can audit the composite priority that placed it. The four inputs (pain severity, competitive position, dependency depth, and operational risk of delay) follow the methodology in Section A, and the opportunity cost language mirrors the Opportunity Cost Summary table so the two views can be cross-checked.

**Per-phase mini-frames** (lines 654, 694, 761, 801) each state the argument that phase's scoring makes:

- Phase 1: "share dependency depth 0 and all evaluate as structural gaps; scoring ranks them by the severity and velocity of the pain each leaves unaddressed."
- Phase 2: "inherit Phase 1 capabilities and compete on markets where existing products already operate, so scoring weighs competitive pressure against the dependency cost carried from Phase 1."
- Phase 3: "willingness-to-pay pressure that makes the integrated roster-and-activity package the phase to close, with composite scores compressed by longer dependency chains inherited from Phase 2."
- Phase 4: "the deepest operational work and the longest dependency chains; scoring trades the headline pain severity of compliance against the delivery timing risk that dependency depth introduces."

**Why unchanged.** These per-phase frames already tell the reader what argument that phase's scoring makes and what to notice across the rows. Adding more prose would duplicate what's there.

## Sample Fixes

### Instance 1 (Risk Register intro, line 310)

**Before:** "Top risks carried through the three executive risk assessments ... this register surfaces the specific findings executives should monitor."
**After:** "This register translates the three executive risk assessments ... All three assessments rate LOW overall, so the argument the table makes is about monitoring rather than prediction: each row names a condition that would move the rating up and the trigger indicator that signals it firing. The Trigger indicator column is what monitoring watches for, and the Phase most affected column names where a fired trigger would land."
**Technique:** Recast the passive summary ("surfaces the specific findings") into an argument ("about monitoring rather than prediction"). Added explicit reader guidance naming two specific columns. Preserved all original citations.

## Major Changes Flag

Did this pass make any changes that could trigger the restart-from-earlier-phase rule?

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

None. Change was limited to adding ~40 words of framing prose before one table.

## Known Remaining Issues

- The Risk Register exit could be made explicit if a reviewer feels the Approval Package #4 bridge is too far downstream. Current assessment is that the bridge works because the Approval Package immediately follows the table and item 4 names the register directly.
- The per-phase scoring intros (Section D) lean slightly on a semicolon-connected pattern; if D1–D4 left any concern open about variable sentence structure, a reviewer may flag those. D5 scope excludes that concern.
- No em dashes introduced. No banned openers (But, And, So, Or, Still, Yet, However, Therefore). No triads in the revision.
