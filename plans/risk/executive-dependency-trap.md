# Executive Roadmap — Dependency Trap Risk Assessment

**Rating: LOW**

## Findings

### F-1. VS-301 is the highest-fanout bottleneck in the dependency graph

**Severity: LOW**

VS-301 (Provision Chapters From Templates) transitively blocks three downstream initiatives: VS-302 (Phase 2), VS-401 (Phase 3), and VS-402 (Phase 4). This is the only node in the graph where a single initiative's delay cascades to 3+ others, reaching the MEDIUM threshold for a "fragile bottleneck."

However, every link in the chain is architecturally genuine:

- **VS-302 (roster management) requires VS-301 (chapter provisioning):** Rosters cannot exist without chapters to roster into. The proposal's `RosterEntry` references `Chapter` via foreign key, and `ChapterRole` (which VS-302 introduces) is per-chapter.
- **VS-401 (compliance evaluation) requires VS-302 (roster management):** Compliance evaluations operate on `RosterEntry` records with `status: active` and evaluate per-member-per-chapter evidence. Without roster state, there is no evaluation target.
- **VS-402 (graduated consequences) requires VS-401 (compliance evaluation):** Consequences respond to evaluation results — `ComplianceEvaluation.result = violation` triggers the consequence workflow. Without evaluations, there is nothing to enforce.

The bottleneck is not fragile because VS-301 itself has zero upstream dependencies (depth 0), sits in Phase 1, and is well-scoped: provision Discord resources from a template and create the Chapter record. It carries no inherent delay risk from upstream blockage.

Additionally, the sub-community pipeline (VS-301 → VS-302 → VS-401 → VS-402) runs on an independent subsystem track. Its delay does not block the intake pipeline (VS-101 → VS-102 → VS-103), the case pipeline (VS-201 → VS-202), the permission pipeline (VS-501 → VS-502), or the governance slice (VS-601). The four parallel tracks in Phase 1 provide structural resilience: a delay in any one track only affects that track's downstream slices.

**Recommendation:** No structural change required. The dependency chain reflects genuine architectural ordering. If schedule risk materializes on VS-301, the three downstream slices are the only items affected — the other three subsystem tracks are unblocked. Monitor VS-301 delivery as the single initiative whose delay has the widest cascade.

---

### F-2. No value-dependency inversions detected

**Severity: NONE**

Composite priority scores partition into thirds (12 slices, 4 per tier):

| Tier | Slices | Composite range |
|------|--------|-----------------|
| Top | VS-201 (15.00), VS-501 (11.25), VS-601 (9.00), VS-301 (9.00) | 9.00 -- 15.00 |
| Middle | VS-102 (7.50), VS-101 (6.00), VS-103 (5.63), VS-202 (5.63) | 5.63 -- 7.50 |
| Bottom | VS-401 (5.00), VS-502 (4.50), VS-402 (3.75), VS-302 (3.38) | 3.38 -- 5.00 |

All four top-tier initiatives are in Phase 1 with dependency depth 0. No top-tier initiative is blocked by any other initiative, let alone a bottom-tier one. The roadmap's composite formula — which divides pain score by `(depth + 1)` — structurally rewards zero-dependency slices, and the Phase 1 assignment honors this by placing them first. The ordering is value-aligned.

**Recommendation:** No action required.

---

### F-3. PolicyVersion shared state between VS-301 and VS-601 (undeclared coordination point)

**Severity: INFO**

VS-301 (Provision Chapters From Templates) lists `PolicyVersion` among its schema objects — chapter provisioning creates default policies from the template's `default_compliance_rules` and `default_permission_intents`. VS-601 (Change Live Policy Safely) delivers the `PolicyVersion` mechanism itself: preview-confirm workflow, optimistic concurrency, and version chain semantics.

Both are Phase 1 with no declared dependency between them. If the `PolicyVersion` schema and its basic write path are delivered as Phase 0 engineering foundations (as the roadmap's Phase 0 placeholder implies for cross-cutting concerns), then VS-301 can create initial policy records and VS-601 can layer the preview-confirm workflow on top independently. The two slices would share the schema but not block each other.

If `PolicyVersion` is not part of Phase 0 and is instead created entirely within VS-601, then VS-301 has an undeclared dependency on VS-601 — or at minimum a parallel-build coordination requirement to agree on the schema before either slice can ship.

The same pattern applies more weakly to `PermissionIntent` (shared between VS-301 and VS-501) and `AuthorityGrant` (shared among VS-102, VS-201, VS-302, VS-501). In each case, the schema object is a governance-layer primitive that multiple subsystem slices consume.

**Recommendation:** Confirm that Phase 0 foundations include the schema definitions for `PolicyVersion`, `PermissionIntent`, `AuthorityGrant`, and `AuditEntry`. If so, no dependency exists. If Phase 0 does not include these schemas, add an explicit note that VS-301 and VS-601 share a build-time coordination dependency on `PolicyVersion` schema definition.

---

### F-4. Phases group correctly with no intra-phase ordering constraints

**Severity: NONE**

Phase 1: All five slices (VS-201, VS-501, VS-601, VS-301, VS-101) have dependency depth 0. No intra-phase ordering.

Phase 2: All four slices (VS-102, VS-202, VS-502, VS-302) depend exclusively on Phase 1 slices, not on each other. They can be built and delivered in any order within Phase 2.

Phase 3: VS-103 depends on VS-102 (Phase 2). VS-401 depends on VS-301 (Phase 1) and VS-302 (Phase 2). Neither depends on the other. They can be built in parallel within Phase 3.

Phase 4: Single slice (VS-402). No intra-phase concern.

No initiative within a phase depends on another initiative within the same phase.

**Recommendation:** No action required.

---

### F-5. Critical path length is proportionate and structurally sound

**Severity: NONE**

The critical path is VS-301 → VS-302 → VS-401 → VS-402 (4 nodes, 3 edges). At 4 nodes out of 12 total initiatives (33%), the critical path is proportionate. The remaining 8 initiatives distribute across three independent parallel tracks:

- Intake: VS-101 → VS-102 → VS-103 (3 nodes)
- Cases: VS-201 → VS-202 (2 nodes)
- Permissions: VS-501 → VS-502 (2 nodes)
- Governance: VS-601 (1 node, standalone)

Phase 1 has maximum parallelism (5 concurrent zero-dependency slices). Each subsequent phase maintains parallelism within its tier: Phase 2 has 4 concurrent slices, Phase 3 has 2 concurrent slices. The graph is wide, not just deep.

Could the critical path be shortened? VS-401 (compliance evaluation) requires `RosterEntry` from VS-302 (roster management) — compliance evaluates per-member roster status. Removing this dependency would require compliance to operate without knowing who is in the chapter, which contradicts the capability's definition. The path cannot be meaningfully shortened without sacrificing capability coherence.

**Recommendation:** No action required.

---

### F-6. Dependency depth metric counts direct upstream only, understating transitive chain length

**Severity: INFO**

The roadmap defines dependency depth as "count of upstream value slices that must exist before the slice can function." Two slices have a declared depth that is lower than their transitive upstream count:

| Slice | Declared depth | Direct upstream | Transitive upstream set | Transitive count |
|-------|---------------|-----------------|------------------------|-----------------|
| VS-103 | 1 | VS-102 | {VS-102, VS-101} | 2 |
| VS-402 | 2 | VS-401, VS-302 | {VS-401, VS-302, VS-301} | 3 |

The composite formula uses `depth + 1` as a divisor, so the understated depth inflates composite scores:

| Slice | Declared composite | Transitive-depth composite | Delta |
|-------|--------------------|---------------------------|-------|
| VS-103 | 5.63 | 3.75 | -1.88 |
| VS-402 | 3.75 | 2.81 | -0.94 |

Neither correction changes the ordinal ranking within tiers or the phase assignment. VS-103 stays in the middle tier and VS-402 stays in the bottom tier. The effect is cosmetic, not structural.

The ambiguity lies in the definition: "upstream slices that must exist" naturally reads as transitive (all slices that must be built first), but the numbers are consistent with a direct-only interpretation.

**Recommendation:** Clarify the depth definition to explicitly state "direct upstream" or "transitive upstream." If transitive is intended, update VS-103 depth to 2 and VS-402 depth to 3. No phase restructuring is needed regardless.

---

### F-7. No cycles, no self-dependencies, no impossible orderings

**Severity: NONE**

The dependency graph is a directed acyclic graph (DAG). All edges point from earlier phases to later phases or from earlier slices to later slices within the same subsystem track. No initiative depends on itself. No pair of initiatives forms a mutual dependency. The phase ordering is physically realizable.

**Recommendation:** No action required.

---

## Summary table

| ID | Finding | Severity |
|----|---------|----------|
| F-1 | VS-301 is the highest-fanout bottleneck (blocks 3 downstream) but dependencies are genuine and VS-301 has zero upstream risk | LOW |
| F-2 | No value-dependency inversions: all top-tier initiatives are Phase 1, depth 0 | NONE |
| F-3 | PolicyVersion shared state between VS-301 and VS-601 is an undeclared coordination point resolvable by Phase 0 foundations | INFO |
| F-4 | Phases group correctly with no intra-phase ordering constraints | NONE |
| F-5 | Critical path (4 of 12 nodes) is proportionate; graph is wide with 4 parallel tracks | NONE |
| F-6 | Dependency depth metric understates transitive depth for VS-103 and VS-402; no ranking impact | INFO |
| F-7 | No cycles, self-dependencies, or impossible orderings | NONE |

## What LOW requires

The LOW rating remains valid as long as:

1. **VS-301 delivery risk stays contained.** If VS-301 (chapter provisioning) encounters significant delay, three downstream slices (VS-302, VS-401, VS-402) are blocked while the other three subsystem tracks proceed unaffected. The rating assumes VS-301's zero-dependency position and clear scope make significant delay unlikely. If VS-301's scope expands or its engineering risk increases, re-evaluate whether the three-initiative cascade warrants MEDIUM.

2. **Phase 0 foundations include shared governance schemas.** The INFO finding on PolicyVersion (F-3) assumes that Phase 0 delivers the schema definitions for cross-cutting objects (PolicyVersion, PermissionIntent, AuthorityGrant, AuditEntry). If Phase 0 does not include these, VS-301 and VS-601 have a hidden build-time dependency that could introduce an intra-Phase-1 ordering constraint, violating the clean grouping confirmed in F-4.

3. **No new dependencies are introduced between subsystem tracks.** The current graph has four independent parallel tracks that share only governance-layer primitives. If a future revision adds a cross-track dependency (e.g., ticket creation requiring trust profiles, or permission drift detection depending on chapter state), the parallelism that mitigates VS-301's bottleneck degrades and the rating should be reassessed.

4. **The depth metric ambiguity (F-6) does not mask a deeper ordering problem.** The current discrepancy is cosmetic — ordinal rankings and phase assignments are unaffected. If additional slices are added with dependencies on VS-103 or VS-402, the understated depth could cause their composite scores to be artificially high, potentially misranking them against genuinely lower-depth alternatives.
