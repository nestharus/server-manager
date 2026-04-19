# C3 Triads and Pseudo-Lists Fix Report (Cycle 3): Executive Roadmap

## Scope

**Concern fixed:** 8 remaining triads and pseudo lists flagged by the C3 cycle 2 reviewer.
**Instances in violation report:** 8
**Instances fixed:** 8
**Instances skipped:** 0

## Sample Fixes

### Instance R-1 (line 46)
**Before:** `No scripting, plugin, or arbitrary-automation surface.`
**After:** `No scripting or arbitrary-automation surface.`
**Technique:** Reduce-to-two. "Plugin" is subsumed by "arbitrary-automation surface" since a plugin system is an automation surface. Meaning preserved.

### Instance R-2 (line 126)
**Before:** `**Capability gained:** Officers process structured applications with single-reviewer ownership. Tickets progress through category-specific state machines with privacy controls. New chapters are provisioned from templates through approval gates. Operators declare intended permission state and detect drift. Officers receive configurable notifications. Trust computation is customizable with officer-managed signals. Cross-subsystem history is queryable through materialized views.`
**After:**
```
**Capability gained:**
- Officers process structured applications with single-reviewer ownership
- Tickets progress through category-specific state machines with privacy controls
- New chapters are provisioned from templates through approval gates
- Operators declare intended permission state and detect drift
- Officers receive configurable notifications
- Trust computation is customizable with officer-managed signals
- Cross-subsystem history is queryable through materialized views
```
**Technique:** Convert prose run of parallel clauses into a markdown bullet list. Lists-as-bullets are not prose, so the "no triads/pseudo lists in prose" rule does not apply. All seven capabilities preserved verbatim.

### Instance R-3 (line 157)
**Before:** `**Capability gained:** Full roster lifecycle with officer direct management. Application process supports interviews and waitlists. Tickets enforce time-based SLA with graduated consequences. Temporary permissions auto-expire.`
**After:**
```
**Capability gained:**
- Full roster lifecycle with officer direct management
- Application process supports interviews and waitlists
- Tickets enforce time-based SLA with graduated consequences
- Temporary permissions auto-expire
```
**Technique:** Same bullet-list conversion as R-2.

### Instance R-4 (line 161)
**Before:** `**Not yet built:** No compliance evaluation. No chapter governance lifecycle (probation, archival). No leadership succession with context transfer.`
**After:**
```
**Not yet built:**
- Compliance evaluation
- Chapter governance lifecycle (probation, archival)
- Leadership succession with context transfer
```
**Technique:** Convert the repeated-frame "No X. No Y. No Z." pseudo list to bullets. The field label ("Not yet built:") already establishes negation, so "No" prefixes were redundant once items became bullets.

### Instance R-5 (line 188)
**Before:** `**Capability gained:** Compliance evaluation runs on schedule with evidence processing, OCR extraction, and graduated consequences. Chapters have full governance lifecycle with probation and archival. Leadership transitions preserve operational context through succession chains.`
**After:**
```
**Capability gained:**
- Compliance evaluation runs on schedule with OCR-supported evidence processing and graduated consequences
- Chapters have full governance lifecycle with probation and archival
- Leadership transitions preserve operational context through succession chains
```
**Technique:** Bullet-list conversion for the outer pseudo list, plus inner reduction within the first bullet. "Evidence processing" and "OCR extraction" were merged to "OCR-supported evidence processing" since OCR is the mechanism by which screenshot evidence is processed. This avoids leaving an inner triad inside a bullet item.

### Instance R-6 (line 190)
**Before:** `chapter archival with member notification, pending work resolution, and state preservation`
**After:** `chapter archival with member notification and preservation of pending work and state`
**Technique:** Reduce-to-two at the outer level. Two items at the top ("member notification" and "preservation of pending work and state"), with the inner conjunction carrying both sub-concepts.

### Instance R-7 (line 444)
**Before:** `screenshots with OCR, plus game-API feeds and manual reports`
**After:** `OCR-parsed screenshots and structured feeds from game APIs or manual reports`
**Technique:** Recast. Two top-level items ("OCR-parsed screenshots" and "structured feeds"), with the feed sources expressed as disjunctive clarifiers rather than a parallel third item. All three original evidence types preserved.

### Instance R-8 (line 617)
**Before:** `manual data entry, cross-referencing spreadsheets, and threshold checks`
**After:** `manual data entry and spreadsheet cross-referencing for threshold checks`
**Technique:** Reduce-to-two. Threshold checks recast as the purpose of spreadsheet cross-referencing rather than a parallel third activity, which matches how the work actually flows (cross-reference spreadsheets in order to perform threshold checks).

## Major Changes Flag

Did this pass make any changes that could trigger the restart-from-earlier-phase rule?
- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No major changes. All fixes are localized sentence-level edits or inline conversions of prose to bullet lists. No section boundaries moved, no claims added or removed, no factual content changed (items merged or recast preserve all underlying capabilities).

## Known Remaining Issues

- The first bullet in R-5 still contains the phrase "OCR-supported evidence processing and graduated consequences," which is two items joined by "and" inside a bullet. This is not a triad but a reviewer scanning aggressively for inner list-shape within bullets could flag it as list-shaped. If so, reduce to a single verb chain (e.g., "Compliance evaluation runs on schedule, processing OCR evidence to trigger graduated consequences").
- R-7's inner "from game APIs or manual reports" lists two sources with "or." This is a two-item disjunction (within budget), not a triad, but it sits inside a parenthetical so a very strict reviewer might still flag it.
- The Executive Summary "Value realization by phase" section (lines 17-20) is a bullet list, not prose, so it was not in scope for this cycle even though several bullets contain triads of their own. If C4 requires zero inner triads even within bullets, those will need a follow-up pass.
