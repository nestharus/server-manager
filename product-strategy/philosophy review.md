# Philosophy Alignment Review

Review of the proposal against the product philosophy. Each axis that passed Stage 1 is evaluated for whether the proposal's design decisions embody, violate, or lack grounding in the philosophy's principles.

---

## Violations

### 1. Trust Computation Not Operator-Configurable

- **Axis:** Trust Calibration and Identity Verification (Axis 1)
- **Design decision:** TrustProfile level is computed deterministically from TrustSignals. The proposal provides no operator-configurable mechanism for signal weighting. No schema object exists for trust computation parameters.
- **Principle violated:** Principle 11 — Configuration by Operators, Not Developers
- **How it's violated:** The proposal provides explicit operator-configurable parameters for every other operational domain: ComplianceRule has `parameters: jsonb` for thresholds and periods, FormDefinition has `fields: jsonb` for form structure, TicketCategory has `state_machine: jsonb` for workflow customization. Trust computation — which determines how five signal types (`identity_verification`, `chapter_tenure`, `officer_endorsement`, `compliance_history`, `incident_record`) combine into a numeric trust level — has no equivalent configuration surface. Different communities will weight these signal types differently based on their governance values. Without configurable weights, adjusting how trust is computed requires code changes.
- **Why this matters:** Trust computation weights are operational parameters analogous to compliance thresholds. A community that values officer endorsement over tenure makes a fundamentally different governance choice than one that doesn't. If this choice is hardcoded, communities cannot align trust calibration with their values without developer intervention — the exact failure mode Principle 11 exists to prevent. This also creates a secondary Principle 1 concern: operators can inspect signals and the resulting level, but cannot see or modify the formula that connects them, limiting their ability to fully reconstruct the chain of cause and effect.

---

## Ungrounded Decisions

None identified. All design decisions in the proposal trace to one or more philosophy principles.

---

## Structural Concerns

### 1. Audit Subsystem as Blocking Dependency

The proposal deliberately makes audit integrity a prerequisite for consequential decisions: officer-initiated actions (approvals, denials, escalations) block when audit storage is unavailable. This creates a structural dependency where the audit subsystem's availability determines the system's operational capacity for high-stakes decisions across all other subsystems. Routine automated transitions (scheduled compliance evaluations) proceed with queued audit entries, but officer decisions wait.

This is a coherent design choice that prioritizes Principle 6 (reconstructable decisions) over Principle 12 (subsystem independence). It is not an oversight — the proposal explicitly acknowledges the trade-off. But the operational consequence is that audit downtime is not "audit isn't recording" — it is "officers can't make decisions." The proposal does not describe what operators see during audit unavailability, how blocked operations are surfaced, or what recovery looks like for queued entries. As the system grows, this coupling means audit subsystem reliability has outsized importance relative to other subsystems.

### 2. Ticket Category State Machine Extensibility Ambiguity

The proposal defines base ticket states (`open`, `triaged`, `assigned`, `escalated`, `resolved`, `closed`) and says categories "may extend" this base. The TicketCategory schema stores the state machine as `jsonb`, which structurally allows arbitrary customization. But the language "may extend" suggests categories can add states but not omit base states.

If extension means only addition, then every ticket category — including routine ones like account linking requests — requires human triage as a mandatory step. Principle 9 requires that every mandatory human touchpoint justify its attention cost. For categories where routing and priority are deterministic (e.g., all account linking tickets go to the same queue at the same priority), mandatory triage is a touchpoint without a clear risk justification.

If extension means full customization (categories can define any state machine), this concern dissolves. The ambiguity should be resolved: either clarify that categories can define arbitrary state machines, or justify why base states are mandatory for all categories.

### 3. Member Suspension Without Described Workflow

The Member schema includes `status: suspended` alongside `active` and `departed`. No workflow in the proposal describes how suspension occurs, what triggers it, what its operational effects are (does it block roster participation? ticket filing? application submission?), or who can initiate it. The schema object exists without a corresponding lifecycle mechanism.

This is a gap rather than a contradiction — suspension is a natural governance state traceable to Principle 6 (trust and safety). But the proposal's other lifecycle objects (Application, Ticket, Chapter, RosterEntry) all have described state machines with explicit transition rules, triggers, and governance. Member status lacks this treatment, leaving the operational semantics of suspension unspecified.

---

## Per-Axis Summary

| # | Axis | Assessment | Notes |
|---|---|---|---|
| 1 | Trust Calibration and Identity Verification | **Violation** | Trust computation weights not operator-configurable (P11) |
| 2 | Structured Intake and Adjudication | Embodied | Form versioning (P2), claim ownership (P9), context surfacing (P1), scoped routing (P7) |
| 3 | Case Routing and State Management | Embodied | Per-category state machines (P11), privacy levels (P6), durable transitions (P10). See structural concern #2 |
| 4 | Audit Trail and Long-term Accountability | Embodied | Context snapshots (P1), immutable entries (P6), unlimited retention (P5/P10). See structural concern #1 |
| 5 | Sub-community Provisioning and Lifecycle | Embodied | Template provisioning (P11), archival process (P10), succession chains (P7) |
| 6 | Activity Tracking and Compliance Enforcement | Embodied | Configurable rules (P11), severity-scaled consequences (P6/P9), OCR as extraction not decision (anti-goal) |
| 7 | Permission Model and State Explosion | Embodied | Declarative intent (P1), drift detection (P1), temporary expiration (P1), reconciliation (P9) |
| 8 | Vendor Lock-in, Migration, and Data Portability | Embodied | Database as truth (P10/P5), export paths (P5), platform boundary (P8/P3) |
| 9 | Volunteer Coordination and Staff Burnout | Embodied | Automation-first defaults (P9), minimal notifications (P9/P1 tension resolution), collision prevention (P9) |
| 10 | Delegated Authority and Governance | Embodied | Scoped authority (P7), enhanced override audit (P6), hard denial (P7), succession (P7) |
| 11 | Platform Constraints and Moving-Target Risk | Embodied | Platform boundary (P8/P3), assumption verification (P12/P1), agnostic operational model (P5) |
| 12 | Cross-workflow State and Operational Continuity | Embodied | FK relationships (P1), subsystem independence (P12), queued cross-subsystem effects (P12). See philosophy surface |
