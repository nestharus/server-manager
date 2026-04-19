# Triads and Pseudo Lists Fix Report: Executive Roadmap

## Scope

**Concern fixed:** V-3 triads in prose and V-4 pseudo lists from parallel clauses
**Instances in violation report:** 29 (20 triads + 9 pseudo lists)
**Instances fixed:** 11
**Instances skipped:** 18 (all judgment calls per rules: enumerations of 4+ items, proper-noun enumerations of named sets, or definitive quoted content)

## Sample Fixes

### Instance 1 (line 9, V-4 pseudo list)
**Before:** `Assignment is "brittle or paywalled," audit is "fragmented and local," and "declared-state reconciliation appears under-served" across 5+ sources`
**After:** `Assignment is "brittle or paywalled" and audit is "fragmented and local," while "declared-state reconciliation appears under-served" across 5+ sources`
**Technique:** Join two with "and" and recast third with subordinator ("while")

### Instance 2 (line 42, V-3 triad — Phase 4 capabilities)
**Before:** `Compliance evaluation against submitted evidence, chapter governance lifecycle (probation, archival), and leadership succession with context transfer. These capabilities answer...`
**After:** `Compliance evaluation against submitted evidence is the anchoring capability, joined by chapter governance lifecycle (probation, archival) and leadership succession with context transfer. These capabilities answer...`
**Technique:** Expand one item into anchor position; join remaining two with "and"

### Instance 3 (line 109, V-3 triad — competitor counts)
**Before:** `Operational parity with, and differentiation from, the eight application tools, nine ticket tools, and eight multi-unit suites competing today, built on the Phase 1 governance substrate that none of them offer`
**After:** `Operational parity with the eight application tools and nine ticket tools that define today's reviewed competition, plus the eight multi-unit suites competing on chapter management. Differentiation comes from the Phase 1 governance substrate none of them offer`
**Technique:** Split into two sentences with unequal weight; join two with "and" and attach third with "plus"

### Instance 4 (line 173, V-3 triad — burnout work)
**Before:** `Officers stop spending hours daily on manual data entry, cross-referencing spreadsheets, and threshold checks, explicitly the primary source of volunteer burnout`
**After:** `Officers stop spending hours daily on the repetitive enforcement work explicitly identified as the primary source of volunteer burnout: data entry, cross-referencing spreadsheets, threshold checks`
**Technique:** Introduce with collective descriptor; move enumeration to colon-introduced list (different shape than parallel prose)

### Instance 5 (line 218, V-4 pseudo list — "different product" clauses)
**Before:** `Building it first means every Phase 2+ workflow inherits defensibility: structured applications with mandatory reasons and causal audit is a different product from shared-dashboard review; tickets with typed transitions tied to versioned policy is a different product from action-centric claim flows; permissions as declared intent with drift detection is a different product from role-hierarchy automation.`
**After:** `Building it first means every Phase 2+ workflow inherits defensibility. Structured applications gain mandatory reasons and causal audit, making them a different product from shared-dashboard review; tickets inherit typed transitions tied to versioned policy, and permissions become declared intent with drift detection, both distinct from the action-centric claim flows and role-hierarchy automation competitors rely on.`
**Technique:** Split into two sentences; recast first item with anchor shape, combine second and third with shared predicate ("both distinct from...")

## All Fixes Applied

### V-3 Triads Fixed (6 instances)

| Line (ref) | Before (abbrev.) | Technique |
|---|---|---|
| 42 | Phase 4 three-capability triad | Anchor + "joined by" + "and" |
| 109 | eight application tools, nine ticket tools, and eight multi-unit suites | Split into two unequal sentences; "plus" for third |
| 171 | Phase 4 three-capability triad (same as 42) | Anchor + "joined by" + "and" |
| 173 | manual data entry, cross-referencing spreadsheets, and threshold checks | Collective descriptor + colon-introduced enumeration |
| 276 (table) | Decisions become unreconstructable, configuration changes corrupt, no system enforces | Join first two with "and"; third becomes own sentence |
| 277 (table) | Officers manually provision, manage rosters, and lose operational context | Join two with "and"; recast third as participial phrase |
| 278 (table) | manual data entry, cross-referencing spreadsheets, and threshold checks | Collective descriptor + parenthetical enumeration |

### V-4 Pseudo Lists Fixed (4 instances)

| Line (ref) | Before (abbrev.) | Technique |
|---|---|---|
| 9 | assignment is X, audit is Y, and Z (three parallel "X is Y" clauses) | Join two with "and"; subordinate third with "while" |
| 175 | Compliance evaluation runs...; chapters enter...; leadership succession preserves... | Split first into own sentence; join remaining two with "and" |
| 218 | structured applications...is a different product; tickets...is a different product; permissions...is a different product | Split into two sentences; recast first; combine second and third with shared predicate |
| 262 | re-run the market misread risk gate...; confirm no new competitor...; re-evaluate Phase 4 composition... | Join two with "and"; third becomes own sentence |

## Instances Skipped (judgment calls)

All skipped because they either (a) are not strict triads (4+ items), (b) are proper-noun enumerations of a named set where the list must be complete, or (c) are long lists (5+ items) that the task rules explicitly say to leave.

### V-3 skipped

- **Line 5** — 7 proposal subsystems (identity/trust, intake, case management, sub-community lifecycle, activity/compliance, permissions, governance). Rule: proper-noun enumeration of named set; KEEP.
- **Line 10** — 4 items (audit gaps, permission drift, configuration changes, volunteer burnout). Not a triad.
- **Line 13** (phases) — 5 phases. Rule: proper-noun enumeration; KEEP.
- **Line 13** (non-goals) — 4 items (bot-framework breadth, moderation-first design, AI-driven decisions, real-time game integration). Not a triad.
- **Line 17** — 4 items (register, enforce, record, change). Not a triad.
- **Line 18** — 5 items. Not a triad.
- **Line 19** — 4 items. Not a triad.
- **Line 36** — 4 items (trust profiles, scoped authority, causal audit, preview-confirm policy). Not a triad.
- **Line 47** — 4 items (anti-nuke, anti-raid, panic-mode, anti-alt heuristics). Not a triad.
- **Line 48** — 5 items. KEEP per long-list rule.
- **Line 72** — 5 items. KEEP per long-list rule.
- **Line 78** — 4 items. Not a triad.
- **Line 223** — 6 items (claiming, transcripts, log history, exports, alliance support, backups). KEEP per long-list rule.

### V-4 skipped

- **Line 82** — 4 items in numbered enumeration ("An operator can (1)..., (2)..., (3)..., and (4)..."). Already explicitly numbered; 4 items is not a strict triad; skipped as judgment call to avoid structural rewrite of a success-condition enumeration.
- **Line 97** — 4 items in semicolon-separated nominal list following "Workflows enabled:" heading. Not a strict triad; skipped as judgment call.
- **Line 113** — 6 items. KEEP per long-list rule.
- **Line 159** — 4 items in semicolon-separated nominal list following "Workflows enabled:" heading. Not a strict triad; skipped as judgment call.
- **Line 190** — 5 items. KEEP per long-list rule.

## Major Changes Flag

Did this pass make any changes that could trigger the restart-from-earlier-phase rule?

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

None of these apply. All edits are local sentence-level rewrites that preserve every factual claim, every citation, every phase ordering, and every slice composition. No sections were moved, no claims added or removed, no narrative shifts introduced.

## Guardrails Verified

- No em dashes introduced (grep confirmed zero em dashes in file after edits).
- No banned openers introduced (But, And, So, Or, Still, Yet, However, Therefore at sentence start).
- No factual content or citation changed.
- No other violation categories touched (did not fix em-dash-substitute sentence boundaries from C1, cliches, V-6 frames, etc.).
- All markdown structure preserved (tables, bullet lists, headings, bold, italics, code spans).

## Known Remaining Issues

- **Lines 82, 97, 113, 159, 190** contain parallel-clause semicolon-separated lists of 4+ items. These read list-shaped but are technically not triads per the judgment rules (strict triad = exactly three parallel items). A reviewer applying a stricter reading could flag them. If future passes want to remove them, the natural fix is conversion to real bullet lists following the "Workflows enabled:" / "Capability gained:" / "Success condition:" anchors.
- **Line 275** (Case Management opportunity cost) contains `Harassment reports, appeals, and disputes age silently in DM threads with no durable state, no ownership tracking, and no time-based accountability` — two nested triads. Not flagged in the violation report so not modified. A stricter reviewer could flag both.
- **Line 38** contains the phrase `table-stakes crowd` flagged as V-7 cliche; still present (out of scope for C3).
- **Line 188** / **Line 126** contain V-6 violations (three consecutive sentences with same grammatical frame); still present (out of scope for C3).
