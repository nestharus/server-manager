# Problem Alignment Review

Review of the proposal against the problem definition. Each axis is evaluated for whether the proposal's approach engages with the core difficulty as described.

---

## Unaddressed Axes

None. All fourteen axes have substantive treatment in the proposal.

---

## Misalignments

None identified.

---

## Constraint-driven Blind Spots

None. The proposal's four constraint acknowledgments (external evidence reliability, Discord platform dependency, single-community scope, in-game identity binding) are complete. Each states what capability is lost, what mitigation exists, and what residual risk remains. No consequences are misunderstood or unaddressed.

---

## Axes Aligned (Stage 2 Handoff)

All fourteen axes proceed to philosophy alignment review.

| # | Axis | Assessment |
|---|---|---|
| 1 | Trust Calibration and Identity Verification | Aligned |
| 2 | Structured Intake and Adjudication | Aligned |
| 3 | Case Routing and State Management | Aligned |
| 4 | Audit Trail and Long-term Accountability | Aligned |
| 5 | Sub-community Provisioning and Lifecycle | Aligned |
| 6 | Activity Tracking and Compliance Enforcement | Aligned |
| 7 | Permission Model and State Explosion | Aligned |
| 8 | Vendor Lock-in, Migration, and Data Portability | Aligned |
| 9 | Volunteer Coordination and Staff Burnout | Aligned |
| 10 | Delegated Authority and Governance | Aligned |
| 11 | Platform Constraints and Moving-Target Risk | Aligned |
| 12 | Cross-workflow State and Operational Continuity | Aligned |
| 13 | Live Configuration Safety and Temporal Integrity | Aligned |
| 14 | Consolidated Failure Risk and Operational Availability | Aligned |

---

## Per-axis Alignment Notes

### Axis 1: Trust Calibration and Identity Verification

The problem definition says the difficulty is calibrating and maintaining trust across organizational boundaries, staff turnover, and time — not collecting signals. The proposal engages with all three dimensions. Per-scope TrustProfiles address organizational boundaries: trust in one chapter does not auto-transfer to another. Signal provenance and deterministic computation from stored evidence ensure trust assessments survive staff turnover — no single officer's departure invalidates a profile. Signal expiration with decay rules and triggered recomputation handle temporal drift. TrustComputationConfig makes calibration an operator governance choice per scope, with transparent computation: operators inspect exactly how signals combine into levels, adjust weights for different governance values, and the system recomputes deterministically.

### Axis 2: Structured Intake and Adjudication

The problem definition says intake is a lifecycle under scarce staff time, not a single decision point, and identifies collision risk from concurrent reviewer access. The proposal models intake as a nine-state state machine with explicit transitions covering the full lifecycle. Single-reviewer claim ownership directly solves the collision problem — only one reviewer owns an application at a time, eliminating duplicated effort and conflicting decisions. Context surfacing at claim time (trust profile, prior applications, roster state) addresses "right context at the right time." Routing rules based on target scope and reviewer authority address "right person."

### Axis 3: Case Routing and State Management

The problem definition says the core difficulty is state management across a case's lifetime — a ticket has owner, status, category, history, and relationships to other operational objects. The proposal models tickets with per-category configurable state machines, so each case type defines exactly the states and transitions its workflow requires. TicketTransition records create durable state history. Intra-subsystem relationships use explicit FK (`related_ticket_ids`); cross-subsystem relationships (a ticket about an application appeal, a chapter dispute) are traced through correlated AuditEntries sharing a `correlation_id`, maintaining queryable relationships without coupling the case management schema to other subsystem schemas. All state is in the community's database, eliminating vendor dependency.

### Axis 4: Audit Trail and Long-term Accountability

The problem definition identifies two levels: reconstructability (any past decision examinable with full context — who decided, what inputs, what alternatives, what policy) and the tension that audit-as-hard-invariant makes audit unavailability an operational outage. The proposal's AuditEntry captures actor, action, target, policy version, context snapshot (what the decision-maker saw), previous and new state, and reason — sufficient for reconstructability independent of how system state has since changed. The `correlation_id`/`causation_id` mechanism makes causal chains navigable across subsystem boundaries. For the availability tension, the proposal makes a deliberate design choice: consequential officer decisions block when audit is unavailable (integrity over availability), while routine automated transitions proceed with deferred entries that record both original and persistence timestamps. Officers receive explicit errors identifying blocked actions, not silent queuing.

### Axis 5: Sub-community Provisioning and Lifecycle

The problem definition says every subgroup increases future cleanup cost, permissions grow combinatorially, and succession requires transferring operational context — not just a role. The proposal addresses cleanup through an explicit archival phase that resolves pending work (applications closed or transferred, tickets resolved or reassigned, authority grants reviewed) before preserving state. Template-based provisioning constrains what each chapter creates. ChapterRole makes governance structure operator-configurable per chapter — communities with flat structures and communities with deep hierarchies use the same mechanism. Succession is keyed to `triggers_succession` per role, and AuthorityGrant predecessor chains transfer operational context (pending decisions, open tickets, roster state), auditing who left, who succeeded, and what was transferred.

### Axis 6: Activity Tracking and Compliance Enforcement

The problem definition says compliance criteria are per-chapter, per-game, per-season, and the system must ingest external evidence without becoming another manual data-entry burden. ComplianceRule is scoped per-chapter with a season field and configurable rule type, covering all three dimensions. Automated scheduled evaluation handles routine cases without officer involvement. OCR extraction addresses the most labor-intensive evidence type. Officers interact only with outputs requiring judgment: violations, low-confidence extractions, and insufficient evidence. Consequence levels (notification_only, flag_for_review, auto_probation) let operators calibrate attention cost per rule.

### Axis 7: Permission Model and State Explosion

The problem definition identifies three layers: no "intended permission state" to audit against, the split between diverged-from-intent and no-intent-at-all permissions, and the migration challenge. PermissionIntent provides the intended state with each intent recording why the permission exists. PermissionDrift's nullable `permission_intent_id` distinguishes the two drift categories: drift with intent has a clear resolution path, drift without intent requires operator classification. The reconciliation workflow's three options (reconcile, accept, acknowledge) provide the classification mechanism. Temporary intents with expiration prevent the "temporary becomes permanent" failure mode. Migration works through the drift detection mechanism — unmanaged permissions appear as unintended drift, classified into the managed set over time.

### Axis 8: Vendor Lock-in, Migration, and Data Portability

The problem definition says switching cost is invisible until urgent, lock-in accumulates as workflows and data accrete in vendor systems, and migration requires moving open cases, transcripts, permissions, and policy assumptions. The proposal makes the community's database the source of truth for all operational data. Export paths exist for every data category. The data model is documented for replacement system construction without reverse-engineering. Platform boundary isolation ensures the operational model is platform-agnostic. No critical operational data lives exclusively in Discord or a vendor's system.

### Axis 9: Volunteer Coordination and Staff Burnout

The problem definition says adding process accelerates burnout, the system must reduce total attention cost not just redistribute it, and every mandatory human touchpoint must justify itself against the risk of not having it. The "attention-justified process" design principle directly states this tension: automation is the default, human review is added where the operator judges the risk warrants the cost. Compliance automation handles routine cases. Claim-based review eliminates duplicated effort. Causal notification grouping batches cascading effects from a single root action into one notification, preventing alert patterns that train officers to ignore alerts. Configurable consequence levels let operators match process rigor to risk severity.

### Axis 10: Delegated Authority and Governance

The problem definition says governance requires both local autonomy and central accountability, and Discord expresses authority as global rank rather than scoped delegation. AuthorityGrant replaces rank with scope — an officer's capability is the intersection of their grants and the operation's scope. Scope enforcement is hard: mismatch results in denial, not warning. ChapterRole makes per-chapter governance structure operator-configurable, so organizational hierarchy is a governance choice, not a system constraint. Emergency overrides generate enhanced audit entries capturing justification and the normal scope that would have denied the action, making overrides more visible.

### Axis 11: Platform Constraints and Moving-Target Risk

The problem definition says any system built on Discord must treat platform constraints as external facts that may change and verify assumptions rather than inherit them. The proposal isolates Discord-specific behavior behind a defined boundary layer with explicit mappings between system concepts and Discord expressions. The operational model references system concepts, never Discord specifics. Platform assumptions are verified at startup and reconnection. Degradation from missing capabilities is surfaced to operators rather than silently absorbed.

### Axis 12: Cross-workflow State and Operational Continuity

The problem definition says the core difficulty is maintaining coherent state across subsystem boundaries, and cross-subsystem relationships must be first-class, not reconstructed from memory. The proposal's architecture uses event correlation as the cross-subsystem connective tissue: within subsystems, explicit FKs; across subsystem boundaries, correlated AuditEntries sharing a `correlation_id`. The CQRS read model materializes cross-subsystem views (member operational history, causal chain views, scope-filtered projections) from the event stream. The read model degrades gracefully — operators fall back to direct AuditEntry queries, losing convenience but not data integrity. Subsystem data models remain independent while relationships are first-class in the event stream.

### Axis 13: Live Configuration Safety and Temporal Integrity

The problem definition says configuration changes can silently corrupt the semantic integrity of in-flight operations, and work begun under one set of rules must complete under those same rules. PolicyVersion with version pinning ensures in-flight operations continue under their starting version. Form definitions pin applications to submission-time versions. Compliance rules pin evaluations to the rule version at evaluation time. Trust computation configs pin in-flight recomputations to the previous version. The preview-confirm pattern shows blast radius before changes take effect, and optimistic concurrency on confirmation prevents confirming against a stale preview when another operator has changed the same policy in the interim.

### Axis 14: Consolidated Failure Risk and Operational Availability

The problem definition says consolidation inverts the failure model and the system must maintain meaningful operational independence between subsystems sharing infrastructure. The "subsystem independence" principle establishes subsystems as peers with defined failure boundaries. The graceful degradation matrix specifies per-subsystem impact and unaffected operations, including CQRS read model failure as a distinct scenario (fallback to direct AuditEntry correlation queries). Cross-subsystem effects that fail are queued and surfaced. The audit subsystem is a deliberate exception where failure may cascade to consequential operations — a choice made explicitly with defined operator experience during degraded state, not an uncontrolled cascade.
