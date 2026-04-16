# Philosophy Alignment Review

Review of the proposal against the product philosophy. Each of the fourteen axes that passed Stage 1 (problem alignment) is evaluated for whether the proposal's design decisions embody, violate, or lack grounding in the philosophy's fifteen principles.

---

## Violations

None identified. The proposal's design decisions are traceable to philosophy principles across all fourteen axes. Prior-cycle violations (cross-subsystem FK joins violating P15, fixed role enum lacking philosophical basis) have been resolved: cross-subsystem traceability now uses event correlation through AuditEntry `correlation_id`/`causation_id` with a CQRS read model for operator ergonomics, and ChapterRole provides operator-configurable governance positions per chapter.

---

## Ungrounded Decisions

### 1. SLA rules mechanism

**Axis:** 3 (Case Routing and State Management)

**Design decision:** TicketCategory includes `sla_rules: jsonb?` described as "time-based escalation thresholds." The field appears in the schema as an optional configuration for each ticket category.

**Observation:** No workflow in the proposal describes what the system does when an SLA threshold is reached. The ticket lifecycle workflow describes only officer-initiated escalation ("If the assigned officer cannot resolve the case, they escalate"). The schema field implies automated time-based behavior — the word "thresholds" suggests the system monitors elapsed time and acts when a threshold is crossed — but the mechanism, consequences, and operator visibility for SLA enforcement are entirely unspecified.

This is not traceable to a principle because the behavior isn't defined. The field's presence asserts "time-based escalation exists" without grounding it in how the system thinks about time-bound obligations.

**Implementation check (existing-principle review per procedure 4a):** If SLA rules trigger automated escalation:
- P14 (Graduated Consequence) requires proportional response options. A single threshold-to-escalation mapping with no intermediate options would violate P14. If multiple thresholds with graduated responses are intended (notification at 24h, flag at 48h, auto-escalate at 72h), this pattern mirrors the ComplianceRule consequence graduation but isn't described.
- P9 (Volunteer-Aware Design) requires that auto-escalation justify its attention cost. Escalation creates a mandatory touchpoint for the recipient. The justification depends on the category — an SLA-triggered escalation for a harassment report has different risk calculus than one for an account linking request.
- P1 (Operator Clarity) requires that the system's SLA behavior be predictable. An operator configuring SLA rules cannot predict the system's response because the response mechanism is unspecified.
- P11 (Configuration by Operators) requires that the consequence mechanism be operator-configurable, not baked into code.

**Implicit principle:** "Time-bound operational obligations should be system-monitored, with configurable graduated consequences for elapsed-time violations." This extends P13 (elapsed time as observable evidence for derived state) combined with P14 (graduated responses to that derivation). It is distinct from temporal integrity (P2/PolicyVersion, which ensures rule consistency for in-flight work) — this is about the system actively enforcing deadlines, not about protecting semantic integrity.

**Question:** What does the system do when an SLA threshold is reached? The proposer should specify:
- Whether SLA consequences are configurable per-category (notification, flag, auto-escalation) in the same pattern as ComplianceRule consequences.
- Whether multiple graduated thresholds exist per SLA rule.
- How SLA-triggered state transitions interact with the category's state machine.
- Whether SLA enforcement generates AuditEntries and participates in the notification system.

If SLA enforcement is purely informational (surfacing aging tickets without automated action), the field description should say so rather than using "escalation thresholds" language.

---

## Structural Concerns

### 1. TrustComputationConfig governance duplication

TrustComputationConfig carries fields (`version`, `supersedes_id`, `created_by`, `effective_at`) that structurally duplicate PolicyVersion's governance mechanism. Both objects implement the same pattern: version chain, authorship, temporal effectiveness, and predecessor linkage. The Chapter configuration governance boundary explicitly includes "trust computation parameters" in the set of operational configuration governed through PolicyVersion records.

This creates ambiguity about the governance path for trust computation changes:
- If changes go through the PolicyVersion preview-confirm workflow (as the governance boundary states they should), TrustComputationConfig's governance-equivalent fields are redundant. An operator or auditor encounters two sets of version/authorship/temporal metadata for the same configuration change.
- If changes use TrustComputationConfig's own governance fields and bypass PolicyVersion, the preview-confirm safety pattern and optimistic concurrency check that PolicyVersion provides are absent for trust computation configuration. This is a P2 (Live-Server Safety) gap: a class of operational configuration that the proposal designates as requiring PolicyVersion governance can circumvent it.

No other versioned schema object has this ambiguity. FormDefinition, ComplianceRule, and ChapterRole have simple `version` integer counters used for pinning (applications reference `form_version`, evaluations reference `rule_version`). TrustComputationConfig's fields go beyond pinning — they constitute a self-contained governance model.

The proposer should clarify whether TrustComputationConfig changes go through PolicyVersion (in which case the governance-equivalent fields should be removed or explicitly designated as derived) or use a separate governance path (in which case the governance boundary statement needs revision and the preview-confirm safety mechanism needs to be replicated).

### 2. Initial trust signal type coverage

The Member Onboarding workflow describes initial trust computation from platform-origin metadata: "Discord account age, server join method, mutual servers — whatever the community has configured as initial trust signals." These signals are computed at member creation time by the system, not recorded by officers or generated by operational activity.

The TrustSignal `signal_type` enum covers five types: `identity_verification`, `chapter_tenure`, `officer_endorsement`, `compliance_history`, `incident_record`. None of these correspond to platform-origin metadata the system would automatically record.

P13 (Derived State Transparency) requires that all inputs to the trust computation are inspectable. If initial trust draws from signals not stored as TrustSignal records — or stored under a type not present in the enum — the derivation has inputs the schema cannot express. An operator inspecting a new member's trust profile to understand "why did this member receive this initial trust level?" needs to see the platform-origin signals alongside their contribution to the computation. The TrustProfile description says operators can "see the exact signals contributing to the computed level" — this guarantee requires that the signals actually exist as stored, typed records.

The design intent is clearly P13-compliant. The schema gap is narrow: the signal type enum needs to cover the full signal space that the onboarding workflow describes. But until it does, the onboarding workflow and the trust computation schema describe different signal inventories.

### 3. Queued cross-subsystem effect validity on retry

The proposal handles downstream subsystem failure by queuing effects and retrying: "The upstream operation completes; the downstream effect retries until the target subsystem recovers. Operators see the pending state and can intervene if recovery takes too long."

For audit unavailability, the proposal makes a careful, principled distinction: officer decisions block (because the context that informed them may become stale), while routine automated transitions proceed with deferred recording (because the operation already executed validly — only the record is deferred). This distinction correctly separates "deferred recording" (safe by construction) from "deferred execution" (potentially unsafe).

The general cross-subsystem effect mechanism does not make this distinction. When an application approval triggers a roster entry creation and the chapter subsystem is temporarily unavailable, the roster creation is deferred — it hasn't executed yet. If the application is subsequently withdrawn, the member departs, or the chapter enters archival while the effect is queued, the retry would execute a roster entry against invalid preconditions. The queued effect auto-retries on subsystem recovery without the precondition validation that the proposal requires for officer decisions during audit recovery.

The proposal's audit recovery design articulates why this matters: "if an officer attempted to approve an application during audit downtime and conditions changed before recovery, the system does not execute an approval based on outdated context." The same reasoning applies to deferred cross-subsystem effects — the conditions that warranted the downstream effect may no longer hold. But the proposal applies this reasoning only to audit, not to the general queuing mechanism.

This concern is also surfaced as a principle tension in the philosophy surfaces document (see P12 + P9 vs P2 tension).

---

## Per-Axis Summary

| # | Axis | Assessment | Notes |
|---|---|---|---|
| 1 | Trust Calibration and Identity Verification | Embodied | Deterministic computation (P13), recomputation audited (P1, P6), operator-configurable weights (P11), per-scope profiles (P7). See structural concern #2 re: signal type coverage |
| 2 | Structured Intake and Adjudication | Embodied | Form versioning (P2), claim ownership (P9), context surfacing (P1), scoped routing (P7), decision reasons required (P6) |
| 3 | Case Routing and State Management | Embodied | Per-category configurable state machines (P11/P9), privacy levels (P6), durable transcripts (P10), intra-subsystem FK for related tickets (P15-compliant). See ungrounded #1 re: SLA rules |
| 4 | Audit Trail and Long-term Accountability | Embodied | Context snapshots (P1), immutable entries (P6), correlation/causation chains (P15), audit-availability tradeoff explicit (P12 + P6 tension), stale-decision prevention in recovery (P1/P2) |
| 5 | Sub-community Provisioning and Lifecycle | Embodied | Operator-configurable ChapterRole (P11/P7), template provisioning (P11), archival process (P10), succession chains with predecessor linkage (P7), configurable succession triggers (P7) |
| 6 | Activity Tracking and Compliance Enforcement | Embodied | Per-chapter per-season configurable rules (P11), graduated consequences (P14), OCR as extraction not decision (anti-goal), rule version pinning (P2), operator review for judgment calls only (P9) |
| 7 | Permission Model and State Explosion | Embodied | Declarative intent with reason (P1), drift detection (P13), temporary expiration (P1), three-option reconciliation (P14), unintended drift distinguished from deviated drift (P1) |
| 8 | Vendor Lock-in, Migration, and Data Portability | Embodied | Database as truth (P10/P5), export paths for all data (P5), documented data model (P5), platform boundary isolation (P8/P3) |
| 9 | Volunteer Coordination and Staff Burnout | Embodied | Automation-first defaults (P9), causal notification grouping via correlation_id (P9/P15), collision prevention via claim (P9), configurable consequence levels (P9/P14) |
| 10 | Delegated Authority and Governance | Embodied | Scoped authority grants (P7), hard enforcement on scope mismatch (P7), enhanced override audit (P6), configurable governance hierarchy per chapter (P7/P11), succession chains (P7) |
| 11 | Platform Constraints and Moving-Target Risk | Embodied | Platform boundary isolation (P8/P3), assumption verification at startup/reconnect (P12/P1), agnostic operational model (P5/P8), degradation surfaced to operators (P12/P1) |
| 12 | Cross-workflow State and Operational Continuity | Embodied | Event correlation via correlation_id/causation_id (P15), CQRS read model for operator ergonomics (P1), read model degradation to direct event queries (P12), subsystem data models independent (P15/P12). See structural concern #3 |
| 13 | Live Configuration Safety and Temporal Integrity | Embodied | PolicyVersion pinning for in-flight operations (P2), preview-confirm with optimistic concurrency (P1/P2), blast radius surfacing (P1), no-restart application (P11). See structural concern #1 re: TrustComputationConfig |
| 14 | Consolidated Failure Risk and Operational Availability | Embodied | Subsystem independence (P12), per-subsystem failure boundaries defined (P12), cross-subsystem effect queuing (P12), audit-availability design choice explicit with operator experience specified (P12 + P6 tension) |
