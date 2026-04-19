# D3+D4 Fix Report: Executive Roadmap

## Scope

**Concerns fixed:** D3 Container section framing + D4 Border bridges (connective-prose concerns, fixed together).
**Instances in skeleton analysis:** 6 containers (Phase Structure, Opportunity Cost Summary, Appendix, C. Value Slice Inventory, D. Per-Slice Scoring Detail, phase buckets under scoring detail) + 4 borders (Strategic Narrative → Phase Structure; repeated Phase 1–4 endings; Approval Package → Opportunity Cost Summary; Opportunity Cost Summary → Deferred Subsystems).
**Instances fixed:** 6 containers + 4 borders (bucket framing covers Phase 1/2/3/4 scoring sub-containers as four separate paragraphs).
**Instances skipped:** 0.

## Containers Framed

### 1. `## Phase Structure`

Added a 1-sentence bridge plus framing: "The narrative above explained why this sequence. The phase structure below explains how each phase operates, naming the business outcome and success condition alongside the investment ask and phase-specific risks so contributors and approvers share a single view of what ships and what it enables."

Doubles as the D4 border from Strategic Narrative.

### 2. `## Opportunity Cost Summary`

Added framing intro before the table: "The Approval Package above names what leadership is committing to; the table below names what stays broken while the roadmap executes. Rows group value slices by the operational concern they address, and each entry traces the harm back to the problem-document section where operators describe the pattern in their own terms."

Doubles as the D4 border from Approval Package.

### 3. `## Appendix`

Added framing intro: "The appendix holds the methodology and per-slice detail supporting the phase assignments above. It is separated from the memo body because approvers do not need to read it to evaluate the proposal, yet reviewers auditing the ordering will find the composite scores, dependency depths, and opportunity-cost language for every slice here."

### 4. `### C. Value Slice Inventory`

Added framing intro: "This inventory catalogs every value slice referenced in the phase structure, naming the subsystem it belongs to, the capability it delivers, its schema objects, its state transitions, and its anti-scope boundaries. Reviewers use it to confirm phase composition; engineers use it to confirm slice boundaries before beginning build."

### 5. `### D. Per-Slice Scoring Detail`

Added framing intro: "Scoring detail accompanies each slice inside its phase bucket so reviewers can audit the composite priority that placed it. The four inputs (pain severity, competitive position, dependency depth, and operational risk of delay) follow the methodology in Section A, and the opportunity cost language mirrors the Opportunity Cost Summary table so the two views can be cross-checked."

### 6. Phase 1–4 sub-buckets under D. Per-Slice Scoring Detail

Added one framing sentence per bucket, each varied in opening and emphasis:

- **Phase 1:** "The four Phase 1 slices share dependency depth 0 and all evaluate as structural gaps; scoring ranks them by the severity and velocity of the pain each leaves unaddressed."
- **Phase 2:** "These seven slices inherit Phase 1 capabilities and compete on markets where existing products already operate, so scoring weighs competitive pressure against the dependency cost carried from Phase 1."
- **Phase 3:** "Slice placement here reflects the willingness-to-pay pressure that makes the integrated roster-and-activity package the phase to close, with composite scores compressed by longer dependency chains inherited from Phase 2."
- **Phase 4:** "This phase carries the deepest operational work and the longest dependency chains; scoring trades the headline pain severity of compliance against the delivery timing risk that dependency depth introduces."

## Border Bridges Added

### 1. Strategic Narrative → Phase Structure

Covered by the Phase Structure container intro above (why → how bridge).

### 2. Phase 1 ending (substrate-first effect on Phase 2)

**Before:** "...VS-004 (policy versioning with configuration safety). Detailed scoring rationale and opportunity cost per slice is in the Appendix."

**After:** "...VS-004 (policy versioning with configuration safety). Shipping the substrate first is what lets Phase 2 workflows inherit causal audit and scoped authority from day one rather than carrying them in as retrofits. Detailed scoring rationale and opportunity cost per slice is in the Appendix."

### 3. Phase 2 ending (operational-core effect on Phase 3)

**Before:** "...VS-015 (cross-subsystem operational views). Detailed scoring rationale and opportunity cost per slice is in the Appendix."

**After:** "...VS-015 (cross-subsystem operational views). With the operational core in place, Phase 3 extends each workflow into the depth operators actually pay for rather than opening new subsystems. Detailed scoring rationale and opportunity cost per slice is in the Appendix."

### 4. Phase 3 ending (willingness-to-pay completion effect on Phase 4)

**Before:** "...VS-014 (temporary permission management). Detailed scoring rationale and opportunity cost per slice is in the Appendix."

**After:** "...VS-014 (temporary permission management). Completing the willingness-to-pay package here frees Phase 4 to focus on operational-maturity work that has no direct competitor yet depends on every prior phase. Detailed scoring rationale and opportunity cost per slice is in the Appendix."

### 5. Phase 4 ending (proposal scope closed)

**Before:** "...VS-018 (leadership succession with context transfer). Detailed scoring rationale and opportunity cost per slice is in the Appendix."

**After:** "...VS-018 (leadership succession with context transfer). Phase 4 closes the proposal scope; no additional subsystem remains unaddressed within the committed Non-goals. Detailed scoring rationale and opportunity cost per slice is in the Appendix."

### 6. Approval Package → Opportunity Cost Summary

Covered by the Opportunity Cost Summary container intro above.

### 7. Opportunity Cost Summary → Deferred Subsystems

Added exit paragraph after the table: "Every row above maps to operator testimony in the problem document, so the costs are observed rather than projected. The next section lists capabilities that sit outside this accounting because they are deferred beyond roadmap scope by design."

## Sample Fixes

### Container framing (Phase Structure)

**Before:** Header `## Phase Structure` went straight to `### Phase 0`.
**After:** Two-sentence intro that bridges from Strategic Narrative and previews the per-phase scaffolding.
**Technique:** Why → how bridge + inventory sentence naming the per-phase fields.

### Varied phase ending (Phase 1)

**Before:** "...VS-004 (policy versioning with configuration safety). Detailed scoring rationale..."
**After:** Inserted a sentence about substrate-first's effect on Phase 2 before the Appendix pointer.
**Technique:** Pre-pointer insertion that gives the phase a distinct rhetorical landing (substrate→Phase 2 effect) without changing the pointer itself.

### Table frame + exit (Opportunity Cost Summary)

**Before:** `## Opportunity Cost Summary` → table → `---` → `## Deferred Subsystems`.
**After:** Two-sentence intro before the table + two-sentence exit after the table bridging into Deferred Subsystems.
**Technique:** Bracket the container so the reader enters and exits with known-to-new continuity.

### Bucket framing (Phase 2 under Scoring Detail)

**Before:** `#### Phase 2` went straight to `##### VS-007`.
**After:** One-sentence intro naming the scoring logic specific to Phase 2 (competitive pressure vs. dependency cost).
**Technique:** Single-sentence container frame, opener varied from adjacent buckets to avoid parallel paragraph openings.

## Major Changes Flag

Did this pass make any changes that could trigger the restart-from-earlier-phase rule?

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No restart trigger. All additions are connective prose; no sections moved, added, or removed. Phase content untouched.

## Known Remaining Issues

- The Phase 1/2/3/4 scoring-bucket intros appear close together in the document. Opening words vary ("The four", "These seven", "Slice placement here", "This phase"), but a reviewer scanning the sub-buckets back-to-back could still flag them as templated because each is a single sentence followed by slice headers. If a stricter reader flags this, expand one bucket to two sentences or drop one of the intros.
- The Phase Structure intro uses a two-pair list ("business outcome and success condition alongside the investment ask and phase-specific risks") to avoid a triad. A reviewer could read this as lightly list-shaped even though it is not a banned triad form.
- "The narrative above explained why this sequence" is a known-to-new bridge; a reviewer preferring a sharper move could want a shorter question-form bridge instead. Left as a statement because the audience is executive/approver and a question would read performative here.
