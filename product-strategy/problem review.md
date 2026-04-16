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

The problem definition says the difficulty is calibrating and maintaining trust across organizational boundaries, staff turnover, and time — not collecting signals. The proposal engages with all three dimensions. Per-scope TrustProfiles address organizational boundaries: trust in one chapter does not auto-transfer to another. Signal provenance and deterministic computation from stored evidence ensure trust assessments survive staff turnover — no single officer's departure invalidates a profile. Signal expiration with configurable decay rules and triggered recomputation handle temporal drift. TrustComputationConfig makes calibration an operator governance choice per scope, with transparent computation: operators inspect exactly how signals combine into levels, adjust weights for different governance values, and the system recomputes deterministically.

### Axis 2: Structured Intake and Adjudication

The problem definition says intake is a lifecycle under scarce staff time, not a single decision point, and identifies collision risk from concurrent reviewer access as a direct cause of wasted officer attention. The proposal models intake as a nine-state state machine with explicit transitions covering the full lifecycle. Single-reviewer claim ownership directly solves the collision problem — only one reviewer owns an application at a time, eliminating duplicated effort and conflicting decisions. Context surfacing at claim time (trust profile, prior applications, roster state) addresses "right context at the right time." Routing rules based on target scope and reviewer authority address "right person."

### Axis 3: Case Routing and State Management

The problem definition says the core difficulty is state management across a case's lifetime — a ticket has owner, status, category, history, and relationships to other operational objects — and that vendor-dependent state threatens operational continuity. The proposal models tickets with per-category configurable state machines, so each case type defines exactly the states and transitions its workflow requires. TicketTransition records create durable state history. Intra-subsystem relationships use explicit FK (`related_ticket_ids`); cross-subsystem relationships are traced through correlated AuditEntries sharing a `correlation_id`, maintaining queryable relationships without coupling the case management schema to other subsystem schemas. All state is in the community's database, eliminating vendor dependency for case data.

### Axis 4: Audit Trail and Long-term Accountability

The problem definition identifies two levels: reconstructability (any past decision examinable with full context — who decided, what inputs, what alternatives, what policy) and the tension that audit-as-hard-invariant makes audit unavailability an operational outage. The proposal's AuditEntry captures actor, action, target, policy version, context snapshot (what the decision-maker saw), previous and new state, and reason — sufficient for reconstructability independent of how system state has since changed. The `correlation_id`/`causation_id` mechanism makes causal chains navigable across subsystem boundaries. For the availability tension, the proposal makes a differentiated design choice: consequential officer decisions block when audit is unavailable (integrity over availability), while routine automated transitions proceed with deferred recording that captures both original and persistence timestamps. Officers receive explicit errors identifying blocked actions, not silent queuing.

### Axis 5: Sub-community Provisioning and Lifecycle

The problem definition says every subgroup increases future cleanup cost, permissions grow combinatorially, and succession requires transferring operational context — not just a role. The proposal addresses cleanup through an explicit archival phase that resolves pending work (applications closed or transferred, tickets resolved or reassigned, authority grants reviewed) before preserving state. Template-based provisioning constrains what each chapter creates initially. ChapterRole makes governance structure operator-configurable per chapter — communities with flat structures and communities with deep hierarchies use the same mechanism. Succession is keyed to `triggers_succession` per role, and AuthorityGrant predecessor chains transfer operational context (pending decisions, open tickets, roster state), auditing who left, who succeeded, and what was transferred.

### Axis 6: Activity Tracking and Compliance Enforcement

The problem definition says compliance criteria are per-chapter, per-game, per-season, and the system must ingest external evidence without becoming another manual data-entry burden. ComplianceRule is scoped per-chapter with a season field and configurable rule type, covering all three dimensions. Automated scheduled evaluation handles routine cases without officer involvement. OCR extraction addresses the most labor-intensive evidence type (screenshots). Officers interact only with outputs requiring judgment: violations, low-confidence extractions, and insufficient evidence. Consequence levels (notification_only, flag_for_review, auto_probation) let operators calibrate attention cost per rule.

### Axis 7: Permission Model and State Explosion

The problem definition identifies three layers: no "intended permission state" to audit against, the split between diverged-from-intent and no-intent-at-all permissions requiring fundamentally different responses, and the migration challenge of classifying unmanaged history. PermissionIntent provides the intended state with each intent recording why the permission exists. PermissionDrift's nullable `permission_intent_id` distinguishes the two drift categories: drift with intent has a clear resolution path (compare and correct), drift without intent requires operator classification. The reconciliation workflow's three options (reconcile, accept, acknowledge) provide the classification mechanism. Temporary intents with expiration prevent the "temporary becomes permanent" failure mode. Migration works through the drift detection mechanism — unmanaged permissions appear as unintended drift, classified into the managed set over time.

### Axis 8: Vendor Lock-in, Migration, and Data Portability

The problem definition says switching cost is invisible until urgent, lock-in accumulates as workflows and data accrete in vendor systems, and migration requires moving open cases, transcripts, permissions, staff habits, and policy assumptions. The proposal makes the community's database the source of truth for all operational data. Export paths exist for every data category. The data model is documented well enough for replacement system construction without reverse-engineering. Platform boundary isolation ensures the operational model is platform-agnostic. No critical operational data lives exclusively in Discord or a vendor's system.

### Axis 9: Volunteer Coordination and Staff Burnout

The problem definition identifies three burnout mechanisms: process rigor (more mandatory touchpoints accelerates burnout), notification volume (cascading informational alerts independent of decision load), and the fundamental tension that every touchpoint must justify its attention cost against the risk of not having it. The proposal engages with all three. The "attention-justified process" design principle makes automation the default, with human review added where operators judge the risk warrants the cost. Compliance automation eliminates routine cross-referencing. Claim-based review prevents duplicated effort. Causal notification grouping (`per_root_cause` batching via `correlation_id`) batches cascading effects from a single root action into one notification, directly addressing the notification volume mechanism. Configurable consequence levels let operators match process rigor to risk severity per rule and per category.

### Axis 10: Delegated Authority and Governance

The problem definition says governance requires both local autonomy and central accountability, and Discord expresses authority as global rank rather than scoped delegation — there is no native way to express "only within your chapter." AuthorityGrant replaces rank with scope — an officer's capability is the intersection of their grants and the operation's scope. Scope enforcement is hard: mismatch results in denial, not warning. ChapterRole makes per-chapter governance structure operator-configurable, so organizational hierarchy is a governance choice, not a system constraint. Emergency overrides generate enhanced audit entries capturing justification and the normal scope that would have denied the action, making overrides more visible, not less.

### Axis 11: Platform Constraints and Moving-Target Risk

The problem definition says any system built on Discord must treat platform constraints as external facts that may change, not stable foundations, and assumptions must be verified rather than inherited. The proposal isolates Discord-specific behavior behind a defined boundary layer with explicit mappings between system concepts and Discord expressions. The operational model references system concepts, never Discord specifics. Platform assumptions are verified at startup and reconnection. Degradation from missing capabilities is surfaced to operators rather than silently absorbed. The three adaptation patterns (feature deprecated, feature added, behavior changed) describe how the boundary layer absorbs platform changes without operational model changes.

### Axis 12: Cross-workflow State and Operational Continuity

The problem definition says the core difficulty is maintaining coherent state across subsystem boundaries, and cross-subsystem relationships must be first-class, not reconstructed from memory. The proposal uses event correlation as the cross-subsystem connective tissue: within subsystems, explicit FKs; across subsystem boundaries, correlated AuditEntries sharing a `correlation_id` with causal navigation via `causation_id`. The CQRS read model materializes cross-subsystem views (member operational history, causal chain views, scope-filtered projections) from the event stream. The read model degrades gracefully — operators fall back to direct AuditEntry queries, losing query convenience but not data integrity. Subsystem data models remain independent while relationships are first-class in the event stream.

### Axis 13: Live Configuration Safety and Temporal Integrity

The problem definition identifies two corruption vectors: configuration changes corrupting in-flight operations (work begun under one set of rules must complete under those rules), and concurrent configuration changes corrupting each other (an operator confirming a change based on a previewed state that another operator has since altered). PolicyVersion with version pinning ensures in-flight operations continue under their starting version — form definitions pin applications, compliance rules pin evaluations, trust computation configs pin recomputations. The preview-confirm pattern with optimistic concurrency on confirmation addresses concurrent operator changes: confirmation is rejected if the policy version changed between preview and confirm, forcing re-evaluation against the actual current state. Both vectors are engaged.

### Axis 14: Consolidated Failure Risk and Operational Availability

The problem definition identifies two dimensions of the consolidation-isolation tension: shared infrastructure (a platform-level failure takes down all domains simultaneously) and data coupling (cross-subsystem schema dependencies make evolution, replacement, and independent maintenance harder). The "subsystem independence" design principle establishes subsystems as peers with defined failure boundaries. The graceful degradation matrix specifies per-subsystem impact and unaffected operations. Event-based cross-subsystem coupling (correlation, not foreign keys) preserves subsystem schema independence while maintaining the coherence §12 requires. The CQRS read model separates query convenience from schema coupling — replacing a subsystem means updating event-emitting code and read model projections, not migrating cross-boundary foreign keys.
