# Philosophy Alignment Review

Review of the proposal against the product philosophy. Each of the fourteen axes that passed Stage 1 (problem alignment) is evaluated for whether the proposal's design decisions embody, violate, or lack grounding in the philosophy's fifteen principles.

---

## Violations

### 1. Cross-subsystem traceability via foreign keys rather than event correlation

**Axis:** 12 (Cross-workflow State and Operational Continuity)

**Design decision:** The Cross-workflow State Coherence section states: "Every operational object maintains explicit foreign key relationships to related objects in other subsystems. The data model is designed so that 'what is this member's full operational history?' is a single query joining across subsystems, not a reconstruction from fragmented sources." The Ticket schema includes `related_objects` (jsonb FKs to Application, Chapter, Member, and other Tickets across subsystem boundaries). Cross-subsystem relationships are recorded at creation time in downstream objects' fields. The audit chain traces events through `target_id` and `context` fields using FK-style navigation.

**Principle violated:** Principle 15 — Traceability as Outcome

**How it's violated:** P15 states: "Each subsystem emits well-defined events with correlation identifiers. Tracing a member's operational history across subsystems means correlating events that share identifiers or causal links, not navigating foreign keys across subsystem boundaries. Within a subsystem, explicit relationships are unconstrained; across subsystem boundaries, events are the connective tissue." The anti-goal is explicit: "cross-subsystem foreign keys as the traceability mechanism. Queryable traceability must not come at the cost of subsystem coupling at the data layer."

The proposal uses exactly the approach P15 prohibits. Cross-subsystem operational history is traced through FK joins across subsystem tables rather than through event correlation. Ticket.related_objects stores direct FK references to Intake objects (Applications) and Chapter objects. The explicit design intent — "single query joining across subsystems" — is the anti-pattern P15 identifies.

The proposal partially embodies P15 through AuditEntries, which function as events with `target_id` and `context` fields. But AuditEntries serve as the audit trail mechanism, not the primary traceability mechanism. The primary cross-subsystem query path is FK navigation through the operational data model.

**Why this matters:** The philosophy identifies three reinforcing interactions that cross-subsystem FKs undermine:

- **P15 + P12 (Graceful Degradation):** "Event-based correlation avoids cross-subsystem data coupling, preserving subsystem independence." FK-based coupling means subsystem data models are not independent — schema evolution in one subsystem can affect queries and constraints in referencing subsystems.
- **P15 + P5 (Low Lock-in):** "Event-based correlation keeps subsystem data models independent, reducing the blast radius of replacing or restructuring a subsystem." With FK coupling, replacing or restructuring one subsystem requires updating all subsystems that reference its objects.
- **P15 + P10 (Durable State):** "Events are durably stored, and the traceability guarantee depends on durable event storage rather than cross-subsystem schema dependencies." FK-based traceability depends on schema stability across subsystems.

The proposal's own "subsystem independence" design principle — "Subsystems are peers. Failure in one produces errors for operations that depend on it but does not cascade to unrelated operations" — is also weakened by data-layer coupling that FK relationships create between subsystem schemas.

---

## Ungrounded Decisions

### 1. Fixed RosterEntry role enum

**Axis:** 5 (Sub-community Provisioning and Lifecycle)

**Design decision:** RosterEntry defines `role` as a fixed enum with three values: `member`, `officer`, `leader`. The role carries operational significance — succession logic triggers on leader departure, and the proposal distinguishes leader-level from officer-level chapter authority in several workflows.

**Observation:** No principle dictates that chapter governance should follow a uniform three-tier model. P7 (Delegated Authority) governs how authority is scoped and bounded but does not prescribe organizational structure. P11 (Configuration by Operators) suggests that operational configuration should be manageable without code changes, but adding a new position type (e.g., "co-leader," "senior member," "trainee") requires schema and logic changes to the succession and authority workflows that depend on the role enum. P1 (Operator Clarity) is served by legible structure, but any clear structure — including an operator-configurable one — would satisfy it.

The proposal allows per-chapter customization for compliance rules, trust computation parameters, form definitions, and notification rules. Organizational structure is the one governance dimension where the proposal enforces a fixed, cross-chapter uniform model. The philosophical basis for treating organizational structure differently from other configurable governance dimensions is not articulated.

**Implementation concern (existing-principle check per review procedure 4a):** The operational significance of the role enum — succession triggers on `leader`, specific authority patterns for `officer` vs `leader` — means the fixed roles are not just labels but load-bearing governance categories. Adding a new position type requires not only an enum extension but changes to every workflow that branches on role value. This implementation pattern bakes the three-tier assumption into the system's operational logic, making it harder to modify if the assumption proves wrong. This does not violate a specific principle but amplifies the cost of the ungrounded assumption.

**Question:** Is the three-tier model a deliberate design constraint (all chapters share the same organizational structure for cross-chapter legibility and governance consistency), or an assumption about how gaming communities organize chapters? If the former, the constraint should be justified — what goes wrong with operator-configurable positions? If the latter, the proposer should consider whether this assumption holds for the communities the system serves.

**Implicit principle (for expansion agent):** "Chapter governance should follow a fixed, uniform set of organizational positions across all sub-communities to maintain cross-chapter legibility and prevent governance fragmentation." This would be independent of P7 (which governs authority scope mechanics) and P1 (which governs system transparency). It addresses organizational design standardization — a concern the philosophy does not currently treat.

---

## Structural Concerns

### 1. Notification causal grouping depends on undefined correlation mechanism

The NotificationRule `per_root_cause` grouping requires identifying which events share a causal chain. The proposal describes this: "Each event in the cascade carries a correlation identifier linking it to the root cause event." This is the right approach per P15 — correlation identifiers linking causally related events.

However, no operational object or event in the data model includes an explicit correlation identifier field. The AuditEntry schema has `target_id` (which identifies the object acted upon, not the causal chain) and `context` (a jsonb field that could contain a correlation identifier but does not define one structurally). Without an explicit, schema-level correlation identifier, the `per_root_cause` grouping mechanism has no defined data contract.

This gap means either:
- The correlation identifier is implicit in the `context` jsonb field, which obscures the causal-chain mechanism in unstructured data (weakening P1's demand for inspectable cause and effect).
- The correlation mechanism is left as an implementation detail, which means the proposal's notification grouping description promises behavior the schema cannot yet support.

This is not a principle violation — it is a gap between a described mechanism and the data model that supports it. The proposer should specify where correlation identifiers live in the schema and how the `per_root_cause` grouping evaluates them.

### 2. Concurrent configuration edits under the preview-confirm pattern

The preview-confirm pattern generates a preview showing "what changes, what existing objects are affected, what the rollback path is." The operator confirms based on this preview. But the preview captures a point-in-time snapshot of current state. If two officers with overlapping authority preview changes to the same policy concurrently:

1. Both officers see version N in their previews.
2. Officer A confirms, creating version N+1.
3. Officer B confirms — but B's preview was based on version N, not N+1. B may not know A's change exists.

The PolicyVersion system handles this correctly at the data level (each change creates a new version with `supersedes_id`). But the operator experience conflicts with P1 (Operator Clarity): Officer B made a decision based on a stale preview. The system did not surface that the underlying state changed between preview and confirm.

This does not require a complex concurrency control mechanism. A version check at confirm time — "the state you previewed has changed since your preview; here is the current state" — would close the gap. The concern is that the proposal describes the preview-confirm pattern without addressing this edge case.

---

## Per-Axis Summary

| # | Axis | Assessment | Notes |
|---|---|---|---|
| 1 | Trust Calibration and Identity Verification | Embodied | Deterministic computation (P13), recomputation audited (P1, P6), operator-configurable weights (P11), per-scope profiles (P7) |
| 2 | Structured Intake and Adjudication | Embodied | Form versioning (P2), claim ownership (P9), context surfacing (P1), scoped routing (P7) |
| 3 | Case Routing and State Management | Embodied | Per-category state machines (P11/P9), privacy levels (P6), durable transcripts (P10) |
| 4 | Audit Trail and Long-term Accountability | Embodied | Context snapshots (P1), immutable entries (P6), unlimited retention (P5/P10), audit-availability tradeoff (P12 + P6 tension) |
| 5 | Sub-community Provisioning and Lifecycle | **Ungrounded** | Fixed role enum (see ungrounded #1). Template provisioning (P11), archival process (P10), succession chains (P7) otherwise well-aligned |
| 6 | Activity Tracking and Compliance Enforcement | Embodied | Configurable rules (P11), graduated consequences (P14), OCR as extraction not decision (anti-goal), rule version pinning (P2) |
| 7 | Permission Model and State Explosion | Embodied | Declarative intent (P1), drift detection (P13), temporary expiration (P1), three-option reconciliation (P14) |
| 8 | Vendor Lock-in, Migration, and Data Portability | Embodied | Database as truth (P10/P5), export paths (P5), platform boundary (P8/P3) |
| 9 | Volunteer Coordination and Staff Burnout | Embodied | Automation-first defaults (P9), causal notification grouping (P9/P15), collision prevention (P9) |
| 10 | Delegated Authority and Governance | Embodied | Scoped authority (P7), enhanced override audit (P6), roster transitions attributed (P7), succession chains (P7) |
| 11 | Platform Constraints and Moving-Target Risk | Embodied | Platform boundary (P8/P3), assumption verification (P12/P1), agnostic operational model (P5) |
| 12 | Cross-workflow State and Operational Continuity | **Violation** | Cross-subsystem FK joins violate P15. See violation #1. See structural concern #1 |
| 13 | Live Configuration Safety and Temporal Integrity | Embodied | PolicyVersion pinning (P2), preview-confirm pattern (P1), blast radius surfacing (P1/P2), no-restart application (P11). See structural concern #2 |
| 14 | Consolidated Failure Risk and Operational Availability | Embodied | Subsystem independence (P12), failure boundaries defined (P12), audit-availability design choice (P12 + P6 tension explicit) |
