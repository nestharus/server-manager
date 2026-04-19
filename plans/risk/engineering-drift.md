# Risk: Engineering Roadmap — Drift from Executive Priorities

Assessed against: `product-strategy/engineering roadmap.md`
Cross-referenced with: `product-strategy/executive roadmap.md`

## Overall verdict: LOW

Every executive initiative in the 18-slice, four-phase sequence is present in
engineering output and in its approved phase. Engineering explicitly states
"No engineering pushback changes the executive phase assignments. All 18 value
slices remain in their approved phases." Phase 0 elaboration stays within the
latitude executive explicitly delegated to engineering ("Engineering
decomposition of Phase 0" is flagged as flexible in the Approval Package). No
executive initiative is silently dropped, and no unauthorized scope is added
beyond technical foundations.

Five findings are recorded below, all LOW or INFO. None warrant blocking.

---

## Initiative-to-engineering map

### Phase 0 (executive: engineering-defined)

Executive lists Phase 0 candidates and requires the shared schemas
(`AuditEntry`, `PolicyVersion`, `PermissionIntent`, `AuthorityGrant`) before
Phase 1 begins. Engineering decomposition:

| Executive item | Engineering deliverable | Classification |
|---|---|---|
| Database schema and migration framework | Persistence substrate with migrations | present |
| Discord gateway / platform boundary + Base API framework | Discord interaction framework | merged |
| Subsystem isolation / graceful degradation | Graceful degradation mechanics | present |
| Deferred effect queue infrastructure | Scheduler | present |
| Data portability design | Data portability as a schema design property | present |
| Shared schema: `AuditEntry` | Audit and notification event contract | present |
| Shared schema: `PolicyVersion` | Policy version framework | present |
| Shared schema: `PermissionIntent` | Permission intent foundation | present |
| Shared schema: `AuthorityGrant` | Authority grant foundation | present |
| Platform assumption verification at startup | (implicit in "Deployable service substrate" + hosting formalized in `DECISIONS.md`) | present-implicit |
| (new — engineering-added) | Single write-path mutation primitive | added-substrate |
| (new — engineering-added) | Chapter role and roster entry foundation | added-substrate |
| (new — engineering-added) | Shared test harness | added-substrate |
| (new — engineering-added) | Deployable service substrate aligned to `infra/` | added-substrate |

### Phase 1 (executive: VS-001..VS-004)

| Executive slice | Engineering | Classification |
|---|---|---|
| VS-001 member onboarding with initial trust | VS-001 (Phase 1) | present |
| VS-002 scoped authority with enforcement | VS-002 (Phase 1) | present |
| VS-003 audit trail with causal correlation | VS-003 (Phase 1) | present |
| VS-004 policy versioning with configuration safety | VS-004 (Phase 1) | present |

### Phase 2 (executive: VS-005..VS-010, VS-015)

All seven slices present in Phase 2: VS-005, VS-006, VS-007, VS-008, VS-009,
VS-010, VS-015.

### Phase 3 (executive: VS-011..VS-014)

All four slices present in Phase 3: VS-011, VS-012, VS-013, VS-014.

### Phase 4 (executive: VS-016..VS-018)

All three slices present in Phase 4: VS-016, VS-017, VS-018.

### Pushback / reordering

Engineering roadmap states none. Executive phase ordering and intra-phase
membership are preserved exactly. Executive's intra-phase parallelism
flexibility (up to four concurrent slices in Phases 1–2; two in Phase 3) is
inherited verbatim.

---

## Findings

### F-1. Four engineering-added Phase 0 substrate items — LOW

Engineering Phase 0 adds four items not listed in the executive Phase 0
candidate list: **Single write-path mutation primitive**, **Chapter role and
roster entry foundation**, **Shared test harness**, and **Deployable service
substrate aligned to `infra/`**.

**Risk**: scope inflation at Phase 0 delays Phase 1 start.

**Assessment**: within executive-delegated latitude. The executive Approval
Package explicitly names "Engineering decomposition of Phase 0" as flexible,
and each added item is either substrate-level infrastructure (test harness,
deployable substrate) or a cross-cutting primitive derived from executive
Phase 1 requirements (single write-path primitive enforces the audit and
policy-version invariants executive demands; chapter role/roster foundation
is schema-level substrate for VS-005 and VS-011, not their feature surface).
None of these items pull Phase 2+ user-visible capability forward. No
deviation from executive intent.

### F-2. "Platform assumption verification at startup" not called out explicitly — INFO

Executive Phase 0 text includes "platform assumption verification at
startup" alongside hosting/deployable substrate. Engineering Phase 0
acceptance criteria list "Hosting decision is formalized in `DECISIONS.md`"
and "Deployable service substrate is operational against the `infra/`
baseline" and "Secret management is operational," but do not explicitly
require startup-time assumption checks (DB reachable, Discord API reachable,
required secrets present).

**Risk**: a startup check omission could let a misconfigured deploy come up
silently, which the executive roadmap explicitly wanted guarded against.

**Assessment**: documentation-level gap. The Phase 0 AGENTS.md proposal pass
should name a minimum startup-assertion surface to make the executive
requirement auditable. Not a scope deviation.

### F-3. Deferred Subsystems reappearing only by implication — LOW

Executive Deferred Subsystems name three items that engineering is expected
to absorb inside slices:

- **Permission migration tooling** is supposed to be scoped inside VS-008
  engineering.
- **Emergency override workflow** is supposed to be scoped inside VS-002 /
  authority grant implementation.
- **Seasonal compliance schema support** is supposed to be present in VS-016
  from day one (evaluation logic deferred).

Engineering slice descriptions for VS-008, VS-002, and VS-016 do not
explicitly name these three items. They are plausibly covered by the
general scope language, but they are not separately tracked.

**Risk**: a deferred item that was "assigned to" a slice can silently fall
out if neither the executive nor the engineering roadmap tracks it at the
slice level.

**Assessment**: LOW because the executive Deferred Subsystems section
remains the authoritative source and phase-boundary review is committed to
run at each transition. The engineering proposals for VS-002, VS-008, and
VS-016 should each acknowledge the deferred-subsystem line item they
inherit, but the roadmap-level omission does not constitute drift.

### F-4. Critical-path framing differs from executive Risk Register — LOW

Executive Risk Register row 1 names **VS-005** as the highest-fanout
bottleneck (transitively blocking VS-011, VS-016, VS-017, VS-018).
Engineering Critical Path Summary names **VS-002, VS-008, VS-016**, then
**VS-017, VS-018** as the narrowest chain and does not name VS-005.

**Risk**: if engineering tracks VS-002/VS-008/VS-016 as the schedule-risk
chain while executive tracks VS-005 as the cascade-risk slice, the two
monitoring surfaces could miss the other's signal.

**Assessment**: not a drift — the two framings answer different questions
(control-surface dependency vs. fanout cascade) and both are valid. Both
VS-005 and VS-008 are labeled "Strategic risk: High" in engineering Phase 2,
so the slice is not understated at the slice level. Recommendation:
engineering critical-path paragraph should add one sentence acknowledging
VS-005 as the executive-tracked fanout bottleneck so the two registers
reconcile on the page.

### F-5. No scope reductions flagged as pushback — LOW (confirmatory)

Executive approved "the 18 value slices in their current phase assignments"
and explicitly forbids composition or phase-placement changes "without
re-running the dependency analysis and market misread risk gate."
Engineering confirms zero reductions: every slice is present and in its
approved phase, and no slice is reframed, split, or merged. "Scope
exclusions" in executive (Non-goals: bot-framework breadth,
moderation-first, feature parity, AI-driven decisions, real-time game
integration, full-server cloning, public community-surface features) are
not contradicted by any engineering slice description.

**Assessment**: no finding; confirms LOW.

---

## What LOW requires

For this rating to hold, the following must be true when each phase begins:

1. **Phase 0 proposal passes name deferred-subsystem assignments explicitly.**
   VS-002 engineering proposal acknowledges emergency override audit
   surface; VS-008 proposal scopes permission migration tooling; VS-016
   proposal confirms schema-level season support even as evaluation logic
   is deferred.
2. **Phase 0 acceptance criteria include a minimum startup-assumption
   check** (F-2), even if its shape is a one-line assertion surface.
3. **Engineering Phase 0 additions stay substrate-level.** Single
   write-path primitive, chapter role/roster foundation, shared test
   harness, and deployable substrate must not accrete Phase 1+
   user-visible capability. If any Phase 0 item begins describing
   operator-facing behavior, it has crossed into a Phase 1+ slice and
   requires executive re-approval.
4. **Engineering critical-path communication cross-references VS-005**
   (F-4), or the executive Risk Register is updated to reflect the
   engineering chain. The two registers must not diverge on which slice
   is the primary schedule risk.
5. **Phase-boundary review** (executive cadence) confirms no slice has
   been silently dropped, reframed, or merged during implementation, and
   re-evaluates whether engineering's intra-phase ordering has introduced
   implicit scope changes the roadmap no longer tracks.
