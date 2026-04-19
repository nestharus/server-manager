# Engineering — Integration Risk Assessment

**Rating: LOW**

Applies the Strategic Integration Risk rubric from `product-strategy/roadmap risk types.md` §"Strategic Integration Risk". Per that rubric, this assessment checks only (a) unacknowledged cross-slice dependencies that break sequencing, (b) Phase 0 foundations needed by 2+ slices, and (c) structurally impossible parallelization. Detailed contract signatures, per-table ownership splits, fixture collisions, and Pydantic field sets are out of scope for roadmap-level integration risk.

## Findings

### F-1. Phase 0 covers shared foundations consumed by 2+ later slices

**Severity: NONE**

Every shared capability identified as needed by 2+ later slices in `product-strategy/engineering research.md` "Shared Infrastructure Needs" is listed as a Phase 0 deliverable in `product-strategy/engineering roadmap.md` "Phase 0 delivers":

- Canonical relational persistence + migrations → "Persistence substrate with migrations"
- Authority + durable audit foundations → "Authority grant foundation" + "Audit and notification event contract"
- Optimistic locking + policy-versioning primitives → "Policy version framework" + "Single write-path mutation primitive"
- Discord interaction framework → "Discord interaction framework"
- Notification/event dispatch + background scheduling → "Scheduler" + "Audit and notification event contract"
- Permission intent + reconciliation substrate → "Permission intent foundation" (control-plane engine is deliberately sliced into VS-008)
- Chapter role / roster foundation → "Chapter role and roster entry foundation"
- Test harness + deployment substrate → "Shared test harness" + "Deployable service substrate aligned to `infra/`"

The four proposal cross-cutting concerns (`product-strategy/proposal.md` §"Cross-cutting Concerns") also map cleanly: Cross-workflow State Coherence → "Audit and notification event contract"; Platform Boundary → "Discord interaction framework"; Graceful Degradation → "Graceful degradation mechanics"; Data Portability → "Data portability as a schema design property".

**Recommendation:** No action required.

---

### F-2. Known high-fanout cross-slice bottlenecks are acknowledged in phase risk posture

**Severity: NONE**

The executive roadmap's flagged cross-slice bottlenecks are visibly mirrored in the engineering roadmap's phase risk posture and per-slice strategic risk:

- **VS-005** (chapter provisioning) — Phase 2 risk posture calls it out as "the operational bottleneck for the chapter track"; VS-005 strategic risk explicitly says it "becomes a bottleneck for the later chapter lifecycle track". Downstream consumers (VS-011, VS-017, VS-018) each reference chapter/roster substrate reuse.
- **VS-008** (permission intent) — Phase 2 risk posture names it "the declared-intent control-plane bottleneck for permissions"; VS-014 description explicitly conditions on "if VS-008 lands cleanly".
- **VS-016** (compliance) — Phase 4 aggregate note says "VS-016 dominates the uncertainty and the rest of the phase inherits its evidence and consequence quality"; VS-017 references compliance substrates.
- **VS-001 → VS-010** (trust) — VS-010 explicitly states "once VS-001 exists this is mostly state-machine and policy-extension work".
- **VS-009 + scheduler → VS-013** — VS-013 description enumerates "scheduler, notification routing, and ticket-category semantics all holding together".

These are the dependencies the proposal calls out as system-wide fan-out risks, and they are surfaced at roadmap resolution.

**Recommendation:** No action required.

---

### F-3. Within-phase slice ordering is explicitly delegated to the implementation pipeline

**Severity: INFO**

The roadmap repeatedly states that "slice ordering is not load-bearing at roadmap time; the AGENTS.md implementation pipeline determines concrete sequencing and worktree parallelization from the codebase state that exists when the phase begins" (see "Phase-Level Dependencies", Phase 1, Phase 2, Phase 3, and Phase 4 preambles).

Cases that could plausibly matter within a phase — e.g., Member identity emerging in VS-001 being used by VS-002/VS-003 authority/audit actors in Phase 1, or VS-006 referencing chapters produced by VS-005 in Phase 2 (`product-strategy/executive roadmap.md` §C VS-006 anti-scope line 500) — are covered by this delegation, because the rubric classifies per-table ownership splits and contract signatures as implementation-phase concerns, not roadmap-phase concerns.

No intra-phase claim in the roadmap forces a structurally impossible order (e.g., no Phase N slice declares dependency on a Phase N+1 slice).

**Recommendation:** No action required. When Phase 1 begins, the AGENTS.md pipeline will materialize the Member-first → authority/audit ordering; when Phase 2 begins, it will materialize VS-005 → VS-006 ordering. Both are already the roadmap's stated mechanism.

---

### F-4. No structurally impossible parallelization claims

**Severity: NONE**

The roadmap does not assert two slices jointly own the same named capability, nor does it claim parallelism across phase boundaries. Phase-level serialization is declared strict ("Phase 0 must complete before any Phase 1 slice begins", etc.), which matches the dependency picture in `product-strategy/engineering research.md` Parallelization Analysis where cross-domain pairs (VS-501/VS-601, VS-501/VS-301, VS-601/VS-301) are marked "No" — all of those sit inside the serialized Phase 0 → Phase 1 → Phase 2 chain in this roadmap.

**Recommendation:** No action required.

---

### F-5. Permission-intent foundation vs VS-008 split is an acknowledged design boundary, not a hidden dependency

**Severity: INFO**

Phase 0 lists "Permission intent foundation" and Phase 2 ships VS-008 ("Permission intent and drift detection"). The engineering research confirms the split is intentional: Phase 0's rationale notes "the desired-vs-actual posture is conceptually clear, but the codebase has no permission-intent or reconciliation engine today" and flags prototyping as required; VS-008's strategic risk describes "novel pattern in this codebase with no preserved implementation analogue; it needs new intent tables, drift diffing, Discord readers, and a reconciliation surface". VS-014 (Phase 3) then extends VS-008 rather than duplicating intent ownership.

This is exactly the pattern the rubric endorses — a capability used by 2+ later slices placed in Phase 0 as foundation, with the operator-facing engine sliced into the earliest phase that needs it. The exact schema vs service split is correctly deferred to the implementation pipeline.

**Recommendation:** No action required.

---

## Summary table

| ID | Finding | Severity |
|----|---------|----------|
| F-1 | Phase 0 covers all shared foundations needed by 2+ later slices | NONE |
| F-2 | Known high-fanout bottlenecks (VS-005, VS-008, VS-016) are acknowledged in phase risk posture | NONE |
| F-3 | Intra-phase ordering explicitly delegated to AGENTS.md implementation pipeline | INFO |
| F-4 | No structurally impossible parallelization claims | NONE |
| F-5 | Permission-intent Phase 0 foundation / VS-008 engine split is an intentional, acknowledged design boundary | INFO |

## What LOW requires

LOW remains valid as long as each of the following holds:

1. Phase 0's "Phase 0 delivers" list continues to include every shared capability that `product-strategy/engineering research.md` "Shared Infrastructure Needs" marks as consumed by 2+ slices (persistence + migrations, authority + audit foundation, optimistic locking + policy-versioning primitives, Discord interaction framework, notification + scheduling, permission intent foundation, chapter role / roster foundation, test harness, deployment substrate).
2. The four proposal cross-cutting concerns (Cross-workflow State Coherence, Platform Boundary, Graceful Degradation, Data Portability) continue to map to a Phase 0 deliverable or an explicit per-slice constraint.
3. The flagged high-fanout bottlenecks (VS-005 for chapter track, VS-008 for permission track, VS-016 for compliance track) remain called out either in phase risk posture or as strategic risk on the slice itself.
4. No Phase N slice declares a dependency on a Phase N+1 slice, and no two slices in the roadmap jointly claim ownership of the same named capability.
5. Within-phase ordering continues to be explicitly delegated to the AGENTS.md implementation pipeline rather than asserted as free parallelism in the roadmap text.
