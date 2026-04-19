# Engineering — Strategic Feasibility Risk Assessment

**Rating: LOW**

The engineering roadmap is magnitude-coherent, sequencing-feasible, and consistent with every locked decision in `DECISIONS.md`. Phase magnitudes are defensible at the order-of-magnitude level. The strict Phase 0 → 1 → 2 → 3 → 4 ordering is technically possible given the foundations Phase 0 commits to. No locked-decision conflicts are present.

Per the roadmap risk rubric, per-slice T-shirt sizes, per-slice ownership splits, and effort buffers are implementation-phase outputs and are not flagged here.

---

## Findings

### F-1. Phase magnitude signals are present and order-of-magnitude correct

**Severity: NONE**

Each phase carries a phase-level magnitude indicator, and each slice carries a rough magnitude band. Phase 0 is aggregate XL with L-XL items concentrated in persistence, permission-intent, scheduler, and deployable-substrate foundations. Phase 1 is aggregate XL across four governance slices (one L, three M-L/M). Phase 2 is aggregate high-XL across seven slices (with one XL slice at VS-008 and one L-XL at VS-005). Phase 3 is aggregate low-XL across four extension slices. Phase 4 is aggregate XL dominated by VS-016 (XL, OCR/compliance pipeline).

These magnitudes are consistent with the codebase state described in `engineering research.md`: greenfield persistence, empty Discord command/handler/task packages, no migrations, no OCR adapters, and an API surface where only one aggregate is wired through the intended layered path. A phase claimed as S-M with this amount of greenfield substrate would be magnitude-off; the roadmap does not make that mistake.

**Recommendation:** no action required.

---

### F-2. Phase 0 foundations cover the capabilities Phase 1–4 consume

**Severity: NONE**

Phase 0 deliverables map cleanly onto downstream slice needs:

- Persistence substrate with migrations → required by every durable slice (VS-001 through VS-018).
- Single write-path mutation primitive → VS-002/VS-003/VS-004 and all later mutation surfaces.
- Audit and notification event contract → VS-003, VS-009, VS-015.
- Authority grant foundation → VS-002 and every later authority-gated mutation.
- Permission intent foundation → VS-008 (drift detection/reconciliation) and VS-014 (temporary permissions).
- Chapter role and roster entry foundation → VS-005, VS-011, VS-017, VS-018.
- Policy version framework → VS-004 and every policy-backed subsystem downstream.
- Scheduler → VS-013 (SLA), VS-014 (expiry), VS-016 (scheduled compliance), and any background/deferred effect.
- Discord interaction framework → every operator-facing slice.
- Graceful degradation mechanics, data portability, shared test harness, deployable substrate → cross-cutting across all later phases.

The split between the Phase 0 "permission intent foundation" (schema/reconciliation-engine seed) and the Phase 2 VS-008 slice (drift diffing, Discord readers, reconcile surface) is a reasonable foundation/feature boundary rather than a duplication. Same pattern for Phase 0 policy-version framework → VS-004 policy versioning slice.

**Recommendation:** no action required.

---

### F-3. Phase ordering is technically possible

**Severity: NONE**

Each phase's declared substrate need is satisfied by prior phases:

- Phase 1 (VS-001/002/003/004) consumes persistence, write-path primitive, audit contract, authority foundation, and policy-version framework — all Phase 0 deliverables.
- Phase 2 (VS-005–010, 015) additionally consumes Discord interaction framework, scheduler, permission-intent foundation, and chapter/roster foundation — all Phase 0 deliverables — plus the Phase 1 governance surfaces it explicitly builds on.
- Phase 3 (VS-011/012/013/014) extends Phase 2 contracts: VS-011 extends chapter/roster, VS-012 extends VS-006 state machine, VS-013 composes scheduler + VS-009 notifications + VS-007 categories, VS-014 extends VS-008's declared-intent model. All upstream pieces land before Phase 3 begins.
- Phase 4 (VS-016/017/018) depends on chapter/roster maturity, scheduler, notifications, and audit — all available by Phase 3 completion.

No "Phase N slice requires capability that only Phase N+K delivers" case is present at the strategic level.

**Recommendation:** no action required.

---

### F-4. No conflicts with locked decisions in `DECISIONS.md`

**Severity: NONE**

Checked against D1–D6:

- **D1 (research-first workflow):** Every slice references the AGENTS.md research → proposal → risk → hookpoints → test/code pipeline. Consistent.
- **D2 (no SQLite/local-first canonical store):** Phase 0 commits to "persistence substrate with migrations" and the Technical Landscape Summary explicitly treats in-memory/SQLite as draft-state requiring replacement. The roadmap does not treat SQLite as a canonical target. Consistent.
- **D3 (preserve, do not delete, pre-research drafts):** The roadmap explicitly positions `daemon/`, `forms/`, and related artifacts as hookpoint input, not approved implementation surface. Consistent.
- **D4 (MVP subsystems are applications, tickets, chapter provisioning):** VS-005 (chapter provisioning), VS-006 (applications), VS-007 (tickets) are all Phase 2 — the earliest operator-facing phase. Consistent. D4 does not lock a specific phase ordering within the MVP set; the executive roadmap determines that.
- **D5 (activity tracking/OCR is a first-class in-scope subsystem):** VS-016 is present and scoped as a committed slice (in Phase 4, per the approved executive ordering). "First-class" in D5 is a scope commitment, not a phase placement commitment. Consistent.
- **D6 (Google Cloud Vision primary, Gemini fallback):** VS-016 magnitude note explicitly states "Google Cloud Vision primary plus Gemini fallback is locked." Consistent.

The roadmap frames hosting as "as configured in `infra/`" with formalization as a Phase 0 completion requirement. `DECISIONS.md` has no locked hosting decision, so this is not a conflict; the roadmap correctly treats it as an open item to lock rather than a settled constraint.

**Recommendation:** no action required.

---

### F-5. Phase 0 aggregate magnitude is defensible

**Severity: INFO**

Phase 0 aggregates 13 foundation items, three of which lean L-XL (persistence, permission intent, deployable substrate / hosting formalization) and several M-L items. The XL-aggregate label is appropriate; a smaller label (L) would be magnitude-off given greenfield persistence plus greenfield scheduler plus greenfield Discord command/handler/task plumbing.

Prototyping is flagged for the specific foundations where it is warranted (permission intent reconciliation, scheduler, deployable substrate conditional). This is a reasonable roadmap-level signal; the exact prototyping outputs are implementation-phase detail.

**Recommendation:** no action required at roadmap level. Per the rubric, per-foundation T-shirt sizes and prototyping outputs belong to Phase 0 implementation proposals, not this risk gate.

---

## Summary table

| ID  | Finding                                                                 | Severity |
|-----|-------------------------------------------------------------------------|----------|
| F-1 | Phase magnitude signals are present and order-of-magnitude correct       | NONE     |
| F-2 | Phase 0 foundations cover the capabilities Phase 1–4 consume             | NONE     |
| F-3 | Phase ordering is technically possible                                   | NONE     |
| F-4 | No conflicts with locked decisions in `DECISIONS.md`                     | NONE     |
| F-5 | Phase 0 aggregate magnitude is defensible                                | INFO     |

---

## What LOW requires

LOW remains valid as long as each of the following holds:

1. Phase 0 continues to list, at minimum, persistence substrate + migrations, single write-path primitive, audit/notification event contract, authority grant foundation, permission intent foundation, chapter/roster foundation, policy version framework, scheduler, Discord interaction framework, graceful degradation mechanics, data portability, shared test harness, and deployable service substrate. Removing any of these without a replacement would leave a Phase 1–4 slice without its foundation.
2. The strict phase dependency (Phase 0 → 1 → 2 → 3 → 4) is preserved, OR any relaxation is accompanied by an explicit acknowledgement of which foundations cross phase boundaries.
3. VS-005 (chapter provisioning), VS-006 (applications), VS-007 (tickets), and VS-016 (compliance/OCR) remain in the roadmap as scoped slices — these carry D4/D5/D6 commitments.
4. `DECISIONS.md` is not updated with a new locked decision (e.g., a locked hosting target, a locked scheduler technology, a locked persistence engine) that the roadmap would then contradict. If such a decision is added, the roadmap must be re-checked against it.
5. Phase 4 continues to state Google Cloud Vision primary + Gemini fallback as locked, or that anchor migrates to a Phase 0 DECISIONS.md entry without being weakened.
6. No phase magnitude is silently downgraded from XL to S/M without scope reduction — the current magnitudes reflect the greenfield state described in `engineering research.md`.
