# Executive Roadmap — Market Misread Risk Assessment

**Rating: LOW**

## Findings

### F-1. All composite priority calculations are arithmetically correct

**Severity: NONE**

Every value slice's composite priority was verified against the stated formula `pain * competitive_weight * delay_weight / (depth + 1)`. All 12 value slices produce the exact numbers stated in the roadmap. No arithmetic errors.

**Recommendation:** No action required.

---

### F-2. All market research citations exist and are accurately characterized

**Severity: NONE**

Every pain severity justification in the roadmap cites a specific subsystem section in `market research.md`. Every cited finding was located in that section and the characterization in the roadmap matches the synthesis. Spot-checked claims were further traced to `market-data/` raw reports:

- VS-201 cites "assignment is brittle/paywalled" — confirmed in `research-tickets.md` (Ticket Tool Premium claiming, Modmail broken claim plugin, Discord Tickets aggressive claim behavior).
- VS-501 cites "hierarchy friction breaks real workflows" — confirmed in `research-permissions.md` (Dyno/Carl-bot role-order complaints, YAGPDB 20-reaction limit).
- VS-102 cites "reviewer collision prevention is essentially absent" — confirmed in `research-applications.md` (Gather, Appy, Application Bot, ApplicationForms all lack claim-lock; Gap Analysis explicitly calls this out).
- VS-401 cites "spreadsheet fatigue" — confirmed in `research-activity.md` (Gap Analysis, Community Management Workarounds in `research-platforms.md`).
- VS-601 cites "direct-mutation dashboards are the norm" — confirmed in `research-permissions.md` Gap Analysis ("no public evidence of policy versioning, diff previews, compare-and-swap edits").

**Recommendation:** No action required.

---

### F-3. All competitive position classifications match raw competitor data

**Severity: NONE**

Each `table-stakes`, `gap`, and `parity` classification was verified against the competitor counts in the market data:

- **table-stakes claims (VS-201, VS-102, VS-401):** VS-201 cites 8 ticket tools; raw data confirms Ticket Tool, Helper.gg, SCNX, Discord Tickets, Modmail, Mava, Oapps, DiscoDesk — 8 products offering core ticket creation. VS-102 cites 6 application tools; raw data confirms Gather, Appy, Application Bot, ApplicationForms, Guildbase, Guild Manager. Both exceed the 3+ threshold. VS-401 is addressed separately in F-5.
- **gap claims (VS-501, VS-502, VS-601, VS-301, VS-101, VS-202, VS-103, VS-402):** For each, the roadmap identifies a specific capability form that no reviewed competitor offers. Cross-referenced against `research-permissions.md` Gap Analysis (no intent-vs-actual reconciliation), `research-applications.md` Gap Analysis (no waitlist, no claim-lock), `research-tickets.md` Gap Analysis (no per-category state machines), `research-activity.md` Gap Analysis (no general-purpose compliance engine), and `research-platforms.md` Gap Analysis (no shared lifecycle-first governance model). All gap classifications are supported.

**Recommendation:** No action required.

---

### F-4. VS-301 roadmap language overstates evidence strength classification

**Severity: INFO**

The VS-301 pain justification says "strong signals show chapter lifecycle automation is still missing." The cited section in `market research.md` (Sub-community Lifecycle) rates the **individual pain signals** about lifecycle automation as "strong" and the workaround pain as "strong" — but rates the **overall evidence strength** for the subsystem as **moderate**, not strong. The overall moderate rating reflects that lifecycle-grade chapter administration is under-monetized (only 2 sources, moderate strength) and the evidence gaps section explicitly notes "chapter succession, archival, and delegated local-governance transfer are under-documented in the market inputs."

The roadmap is technically citing the individual signal ratings correctly, but the phrasing "strong signals" could be read as claiming strong overall evidence when the synthesis itself assessed the subsystem as moderate. The pain severity of 4 remains defensible under the scoring methodology ("strong signal or moderate signal plus active harm" — the operational risk is active-harm per `problem.md §5`), so the composite priority is unaffected.

**Recommendation:** No action required for scoring. If the roadmap is reviewed for prose accuracy, consider changing "strong signals show" to "the market confirms" or "evidence shows" to avoid implying the overall evidence classification is strong.

---

### F-5. VS-401 table-stakes classification conflates category breadth with specific capability

**Severity: LOW**

VS-401 is classified as `table-stakes` with the justification that "multiple products monetize attendance/activity tracking, so Humility needs a credible compliance baseline to be viable for chapter operations." The `market research.md` confirms 9 sources compete in attendance/activity tracking (strong evidence count).

However, the specific capability VS-401 delivers — evidence-based compliance **evaluation** against chapter-specific rules — is classified as a gap in the same market research: "A general-purpose compliance engine is still missing" (strong evidence, `research-activity.md` Gap Analysis). The 9 competing products track activity; they do not evaluate compliance from evidence.

The table-stakes classification applies the 2.0 competitive weight instead of the 1.5 gap weight, inflating VS-401's composite from 3.75 (gap) to 5.00 (table-stakes) — a 33% increase. This does not change VS-401's phase placement (Phase 3 is dependency-driven) or its ordering relative to VS-103 (5.63), which remains the higher-priority Phase 3 item regardless. The practical impact on roadmap execution is nil.

**Recommendation:** If the roadmap undergoes revision, consider whether VS-401 should be classified as `gap` (the specific capability is absent) or `table-stakes` (the broader category is crowded). The current classification is defensible as a viability argument but is the least conservative competitive assessment in the roadmap.

---

### F-6. All opportunity cost statements trace to specific problem axes

**Severity: NONE**

Every opportunity cost in the roadmap cites specific `problem.md` sections. Each was verified:

- VS-201 → §3 (case routing, harassment reports stalling in ad hoc channels). Accurate.
- VS-501 → §7 (permission drift accumulating invisibly). Accurate.
- VS-601 → §13 (live config safety) and §9 (volunteer burnout from notification cascades). Accurate.
- VS-301 → §5 (sub-community provisioning, cleanup cost compounding). Accurate.
- VS-101 → §1 (trust calibration, over-trust and over-gatekeeping). Accurate.
- VS-102 → §2 (structured intake, duplicate reviews) and §9 (volunteer coordination overhead). Accurate.
- VS-202 → §3 (case aging invisibly, category-specific consequences). Accurate.
- VS-502 → §7 (unmanaged permission exceptions staying ambiguous). Accurate.
- VS-302 → §5 (succession) and §10 (delegated authority governance gap). Accurate.
- VS-103 → §2 (applicants in limbo) and §4 (audit trail, reconstructable decisions). Accurate.
- VS-401 → §6 (activity tracking, repetitive data entry) and §9 (burnout). Accurate.
- VS-402 → §6 (compliance enforcement) and §9 (burnout from hand-run enforcement). Accurate.

All consequences are specific, not vague. All severity assessments are proportionate to the problem descriptions.

**Recommendation:** No action required.

---

### F-7. Dependency-driven phasing is structurally sound

**Severity: NONE**

Phase structure follows from schema and capability dependencies, not arbitrary grouping:

- **Phase 1** contains all depth-0 slices (no upstream dependencies). This is structurally necessary.
- **Phase 2** contains depth-1 slices whose upstream slices are in Phase 1 (VS-102→VS-101, VS-202→VS-201, VS-502→VS-501, VS-302→VS-301). All dependencies verified against schema object listings.
- **Phase 3** contains slices depending on Phase 2 outputs (VS-103→VS-102, VS-401→VS-301+VS-302). Dependencies are structurally required — VS-103 needs the review workflow from VS-102; VS-401 needs chapter rosters from VS-301/VS-302.
- **Phase 4** contains VS-402 depending on VS-401+VS-302. Graduated consequences require compliance evaluation (VS-401) and roster transitions (VS-302).

No value slice could move to an earlier phase without violating a data dependency.

**Recommendation:** No action required.

---

### F-8. Ordering is stable under alternative market readings

**Severity: LOW**

Tested whether defensible alternative readings of the same market data would produce materially different ordering:

1. **VS-301 pain downgrade from 4 to 3** (based on overall moderate evidence): Composite drops from 9.00 to 6.75. Still above VS-101 (6.00), still in Phase 1. No phase change.
2. **VS-601 pain downgrade from 4 to 3** (demand is inferred from absence, not from spending): Composite drops from 9.00 to 6.75. Falls below VS-301 (9.00) but remains in Phase 1. No phase change.
3. **VS-401 reclassification from table-stakes to gap** (per F-5): Composite drops from 5.00 to 3.75. Ties with VS-402. Still in Phase 3 (dependency-constrained). No phase change.
4. **VS-101 pain downgrade from 4 to 3** (overall evidence is moderate, operational risk is static-gap): Composite drops from 6.00 to 4.50. VS-101 must remain in Phase 1 because VS-102 depends on it. No phase change.

Under the most aggressive combination of all four alternative readings simultaneously, the phase groupings remain identical and the within-phase ordering changes are minor (VS-601 and VS-301 could swap within Phase 1). No initiative moves between phases.

**Recommendation:** No action required. The phasing is robust because it is dependency-driven rather than score-driven.

---

## Summary table

| ID | Finding | Severity |
|----|---------|----------|
| F-1 | Composite calculations verified | NONE |
| F-2 | Market citations verified | NONE |
| F-3 | Competitive positions verified | NONE |
| F-4 | VS-301 "strong signals" vs moderate overall evidence | INFO |
| F-5 | VS-401 table-stakes conflates category with capability | LOW |
| F-6 | Opportunity cost citations verified | NONE |
| F-7 | Dependency phasing is sound | NONE |
| F-8 | Ordering stable under alternative readings | LOW |

## What LOW requires

The LOW rating remains valid as long as:

1. The market research synthesis accurately represents the raw market data. (Verified: spot-checked claims in all six `market-data/` reports trace correctly.)
2. No new competitor has entered the market with capabilities that would reclassify a `gap` as `parity` or `table-stakes` since the research date (April 16, 2026). This is inherently time-bounded.
3. The pain severity scoring methodology continues to be applied consistently — specifically, that "strong signal" in pain justifications refers to individual signal ratings within subsections, not to the overall evidence strength classification of the subsystem. If the methodology is tightened to require overall-section-level evidence strength, VS-301 and VS-101 would need re-examination.
4. The dependency graph in the schema object listings remains accurate. If schema dependencies change during implementation (e.g., VS-102 no longer requires TrustProfile from VS-101), the phasing rationale would need to be re-validated against the new dependency structure.
