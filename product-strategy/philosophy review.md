# Philosophy Alignment Review

Review of the proposal against the product philosophy. Each axis that passed Stage 1 is evaluated for whether the proposal's design decisions embody, violate, or lack grounding in the philosophy's principles.

---

## Violations

### 1. Trust Profile Recomputation Not Audited

- **Axis:** Trust Calibration and Identity Verification (Axis 1)
- **Design decision:** TrustProfile stores the current computed trust level and a `computed_at` timestamp. When underlying signals change or a TrustComputationConfig is updated, the profile is recomputed and the `level` field is overwritten. No AuditEntry is generated for the recomputation, and the previous level is not preserved.
- **Principle violated:** Principle 1 — Operator Clarity ("Every state transition is observable") and Principle 6 — Trust and Safety ("Sensitive actions require audit trails")
- **How it's violated:** The AuditEntry `action_type` enum includes action types for application decisions, ticket escalations, chapter transitions, compliance evaluations, permission reconciliations, member status changes, and authority grants — but no `trust_level_changed` or `trust_recomputed` type. TrustProfile is not listed in the AuditEntry `target_type` enum. When a trust profile is recomputed, the previous level is overwritten. An operator cannot query "when did this member's trust level change?" or "what was this member's trust level on a specific past date?" without replaying the computation from historical signals and the TrustComputationConfig version that was active at that time.
- **Why this matters:** Trust profiles are surfaced to reviewers during application intake as decision context. If a member's trust level changes between submission and review — because a signal expired, a new signal was recorded, or TrustComputationConfig weights were updated — the reviewer sees the current level without knowing it recently changed. An appeals officer reviewing a denied application cannot verify what trust level the original reviewer saw unless the application decision's AuditEntry context snapshot happened to include it. The inputs to trust computation are individually auditable (signal recordings, config version changes), but the derived transition — the moment a member's trust level changes from one value to another — is not. The proposal designs trust computation for transparency (deterministic formula, inspectable signals, configurable weights) but leaves the recomputation lifecycle itself opaque. This is a silent state mutation: operational state that influences decisions changes without generating a first-class audit record.

### 2. RosterEntry Lacks First-Class Audit and Lifecycle Governance

- **Axis:** Sub-community Provisioning and Lifecycle (Axis 5) and Delegated Authority and Governance (Axis 10)
- **Design decision:** RosterEntry tracks chapter membership with a status lifecycle (`active`, `on_leave`, `under_review`, `removed`). However: (a) `RosterEntry` is absent from the AuditEntry `target_type` enum (`Application`, `Ticket`, `Chapter`, `Member`, `ComplianceRule`, `PermissionIntent`, `AuthorityGrant`, `PolicyVersion`); (b) RosterEntry has no dedicated transition record analogous to ChapterTransition, TicketTransition, or ApplicationReview; (c) RosterEntry lacks a `changed_by` or `removed_by` field — the only actor-adjacent fields are `removed_at` and `removal_reason`, which record the fact and justification but not the responsible officer.
- **Principle violated:** Principle 6 — Trust and Safety ("Sensitive actions require audit trails") and Principle 7 — Delegated Authority with Accountability ("An officer's actions within their scope are autonomous but recorded")
- **How it's violated:** The proposal describes roster management as including "direct add by authorized officer" alongside application-based intake. When an officer directly adds or removes a member from a chapter roster, this action has no dedicated audit path. The officer's identity is not recorded on the RosterEntry, and no AuditEntry targets the roster change. RosterEntry changes from other sources are captured indirectly — compliance auto-probation is recorded in ComplianceEvaluation's `consequence_applied` field, member suspension effects are captured in the Member status AuditEntry — but direct officer roster actions, the most operationally common case for chapter-level roster management, pass through no audit mechanism. Additionally, the proposal's design principle "Lifecycle-first objects" promises that operational entities have defined state machines with explicit transitions, but RosterEntry's status lifecycle has no state machine diagram, no transition rules, and no transition record — an inconsistency with how Applications (9 states, full state machine), Tickets (per-category state machines), Chapters (6 states, full state machine), and Members (3 states, full lifecycle description) are treated.
- **Why this matters:** Chapter roster management is a core operational action that directly affects members' standing. An auditor asking "who removed this member from the chapter?" cannot answer the question from the audit system. An officer who disputes a roster change has no attribution trail to examine. P7 requires that officer actions within their scope be recorded — roster modification within a chapter scope is the paradigmatic case of scoped officer action, yet it is the least-audited operational action in the proposal.

---

## Ungrounded Decisions

None identified. All design decisions in the proposal are traceable to one or more philosophy principles through direct application or principled combination.

---

## Structural Concerns

### 1. Notification Model Does Not Account for Causal Event Chains

The NotificationRule model triggers on individual state transition events. When a single operational action produces a cascade of events across subsystems — an application approval creates a RosterEntry, which activates compliance rules, which may generate an initial evaluation — each event independently matches against notification rules. There is no concept of causal grouping, root-cause attribution, or notification batching for related events.

An operator who configures notification rules for application decisions, roster changes, and compliance activations will receive independent notifications for what is, from their perspective, a single action's consequences. At scale — when an officer approves multiple applications in a session, each generating cascading downstream events — this produces notification patterns that can train officers to ignore alerts, undermining the attention-justified process design principle. The model cannot currently express "notify me about the outcome of this action" vs. "notify me about each downstream effect independently."

This is not a principle violation in the current design — notification rules are operator-configured, defaults are minimal, and operators can avoid configuring redundant rules. But it is a governance gap in the notification model: the model's triggering granularity does not match the operational reality that events are causally connected across subsystem boundaries.

### 2. Chapter `configuration` Field Outside PolicyVersion Governance

The Chapter object includes a `configuration: jsonb` field described as "chapter-local settings, overrides of template defaults." This field is mutable and not governed by PolicyVersion. The PolicyVersion model covers form definitions, compliance thresholds, ticket routing, authority templates, and notification rules — but Chapter.configuration is a separate, unversioned mechanism.

If chapter-local configuration overrides affect operational behavior — how compliance rules are parameterized, what intake routing applies, what notification thresholds are active — then changes to this field could alter the operational context of in-flight operations without the preview-confirm pattern, version pinning, or audit mechanisms that PolicyVersion provides. The proposal does not specify what settings `configuration` contains, so the boundary between "settings governed by PolicyVersion" and "settings in Chapter.configuration" is unclear.

This is a design-level ambiguity rather than a current violation. But as the system grows and chapter officers customize their chapters, this field is the most likely accumulation point for unversioned operational configuration that should be versioned. If the field is intended only for non-operational settings (display preferences, descriptions), the proposal should clarify that boundary. If it can hold operational settings, it needs PolicyVersion governance.

---

## Per-Axis Summary

| # | Axis | Assessment | Notes |
|---|---|---|---|
| 1 | Trust Calibration and Identity Verification | **Violation** | Trust profile recomputation not audited (P1, P6) |
| 2 | Structured Intake and Adjudication | Embodied | Form versioning (P2), claim ownership (P9), context surfacing (P1), scoped routing (P7) |
| 3 | Case Routing and State Management | Embodied | Per-category state machines (P11/P9), privacy levels (P6), durable transcripts (P10) |
| 4 | Audit Trail and Long-term Accountability | Embodied | Context snapshots (P1), immutable entries (P6), unlimited retention (P5/P10), chain traceability (P1) |
| 5 | Sub-community Provisioning and Lifecycle | **Violation** | RosterEntry lacks audit infrastructure (P6, P7). Template provisioning (P11), archival process (P10), succession chains (P7) otherwise well-aligned |
| 6 | Activity Tracking and Compliance Enforcement | Embodied | Configurable rules (P11), graduated consequences (P6/P9), OCR as extraction not decision (anti-goal), rule version pinning (P2) |
| 7 | Permission Model and State Explosion | Embodied | Declarative intent (P1), drift detection (P1), temporary expiration (P1), three-option reconciliation (P9/P1) |
| 8 | Vendor Lock-in, Migration, and Data Portability | Embodied | Database as truth (P10/P5), export paths (P5), platform boundary (P8/P3) |
| 9 | Volunteer Coordination and Staff Burnout | Embodied | Automation-first defaults (P9), minimal notifications (P9), collision prevention (P9). See structural concern #1 |
| 10 | Delegated Authority and Governance | **Violation** | RosterEntry roster management not attributed (P7). Scoped authority (P7), enhanced override audit (P6), succession (P7) otherwise well-aligned |
| 11 | Platform Constraints and Moving-Target Risk | Embodied | Platform boundary (P8/P3), assumption verification (P12/P1), agnostic operational model (P5) |
| 12 | Cross-workflow State and Operational Continuity | Embodied | FK relationships (P1/P10), subsystem independence (P12), queued cross-subsystem effects (P12) |
| 13 | Live Configuration Safety and Temporal Integrity | Embodied | PolicyVersion pinning (P2), preview-confirm pattern (P1), blast radius surfacing (P1/P2), no-restart application (P11). See structural concern #2 |
