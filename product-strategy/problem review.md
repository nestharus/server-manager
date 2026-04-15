# Problem Alignment Review

Review of the proposal against the problem definition. Each axis is evaluated for whether the proposal's approach engages with the core difficulty as described.

---

## Unaddressed Axes

None. All thirteen axes have substantive treatment in the proposal.

---

## Misalignments

None identified.

---

## Constraint-driven Blind Spots

None. The proposal's four constraint acknowledgments (external evidence reliability, Discord platform dependency, single-community scope, in-game identity binding) are complete. Each states what capability is lost, what mitigation exists, and what residual risk remains. No consequences are misunderstood or unaddressed.

---

## Axes Aligned (Stage 2 Handoff)

All thirteen axes proceed to philosophy alignment review.

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

---

## Per-axis Alignment Notes

### Axis 1: Trust Calibration and Identity Verification

The problem definition says the difficulty is calibrating and maintaining trust across organizational boundaries, staff turnover, and time — not collecting trust signals. The proposal engages with all three dimensions of the maintenance problem: per-scope trust profiles address organizational boundaries, signal provenance and deterministic computation survive staff turnover, and signal expiration with recomputation handles change over time. Trust is modeled as a gradient computed from individually stored evidence, which means trust assessments are derived from durable evidence rather than any single officer's judgment.

### Axis 2: Structured Intake and Adjudication

The problem definition says intake is a lifecycle under scarce staff time, not a single decision point. The proposal models intake as an explicit state machine with nine states, context surfacing at review time (trust profile, prior applications, roster state), collision prevention through single-reviewer claim ownership, and routing rules that direct applications to the right reviewer scope. Each transition requires the right person to see the right context — the proposal engages with this directly rather than treating intake as form submission.

### Axis 3: Case Routing and State Management

The problem definition says the core difficulty is state management across a case's lifetime — tickets have owners, categories, histories, and relationships to other operational objects. The proposal models tickets with per-category state machines, durable transition records, explicit FK relationships to other operational objects, and visibility controls that separate reporter-facing from staff-facing communication. Ticket state lives in the system's database, directly addressing the problem of operational continuity depending on vendor availability.

### Axis 4: Audit Trail and Long-term Accountability

The problem definition says the difficulty is reconstructability — examining any past decision with full context — not merely logging. The proposal's AuditEntry captures actor, action, target, policy version, context snapshot (relevant state at decision time), previous state, and new state. The context snapshot is the key mechanism: it preserves what the decision-maker saw at the time, independent of how the system's current state has since changed. Retention is unlimited and under community control, addressing the 45-day Discord cap.

### Axis 5: Sub-community Provisioning and Lifecycle

The problem definition says every subgroup created today increases future cleanup cost, and succession requires transferring operational context — not just a role. The proposal addresses cleanup cost through an explicit lifecycle with archival processes that close out pending work before preserving state. Succession is handled through AuthorityGrant predecessor chains that transfer scope, pending decisions, and operational history to the successor. The template-based provisioning standardizes what each subgroup creates, reducing variance in the permission surface.

### Axis 6: Activity Tracking and Compliance Enforcement

The problem definition says compliance criteria are per-chapter, per-game, and per-season, and the system must not become another manual data-entry burden. The proposal's ComplianceRule is scoped to a chapter with a season field and configurable rule type, covering all three dimensions. Automated scheduled evaluation with OCR for screenshot evidence directly addresses the data-entry burden. Officers interact only with outputs requiring judgment: violations, low-confidence extractions, and insufficient evidence.

### Axis 7: Permission Model and State Explosion

The problem definition identifies three layers of difficulty: the absence of an intended permission state, the split between permissions that diverged from intent and permissions with no intent at all, and the migration challenge of bringing existing unmanaged permissions into a declared-intent model. The proposal engages with all three. PermissionIntent is the missing intended-state concept. PermissionDrift with a nullable intent FK distinguishes the two drift categories — divergence from intent vs. permissions with no declared intent. The reconciliation workflow's resolution options (reconcile, accept, acknowledge) provide the classification mechanism that unmanaged permissions require. Temporary intents with expiration prevent the temporary-becomes-permanent failure mode.

### Axis 8: Vendor Lock-in, Migration, and Data Portability

The problem definition says switching cost is invisible until urgent and lock-in accumulates as workflows and data accrete in vendor systems. The proposal addresses this by making the community's database the source of truth for all operational data, with documented export paths for every data category. The platform boundary isolation ensures the operational model is expressed in platform-agnostic terms, reducing coupling to Discord-specific constructs. Critical operational data does not live exclusively in Discord or in external vendor systems.

### Axis 9: Volunteer Coordination and Staff Burnout

The problem definition says the system must reduce total attention cost, not redistribute it, and every mandatory human touchpoint must justify itself. The proposal's attention-justified process principle directly engages with this tension: the default is automation for routine transitions, and human review is added only where the operator judges the risk warrants the cost. The compliance workflow exemplifies this — automated evaluation handles routine cases, officers intervene only for judgment calls. Collision prevention in application review and queue-based routing reduce wasted effort.

### Axis 10: Delegated Authority and Governance

The problem definition says governance requires both local autonomy and central accountability, and Discord's role hierarchy expresses authority as global rank rather than scoped delegation. The proposal replaces rank-based authority with scope-based AuthorityGrants. An officer's capability is the intersection of their grants and the operation's scope — they cannot exceed their permission set even within their chapter. Central staff hold global-scoped grants with emergency override that generates enhanced audit entries, ensuring overrides are more visible rather than less.

### Axis 11: Platform Constraints and Moving-Target Risk

The problem definition says any system built on Discord must treat platform constraints as external facts that may change, not as stable foundations. The proposal isolates Discord-specific behavior behind defined boundaries with an explicit mapping between system concepts and Discord expressions. The operational model references system concepts, not Discord specifics. Platform assumptions are verified at startup and reconnection, and feature changes affect the Discord layer without altering the operational model.

### Axis 12: Cross-workflow State and Operational Continuity

The problem definition says the core difficulty is maintaining coherent state across subsystem boundaries, with cross-subsystem relationships as first-class rather than reconstructed from memory. The proposal's unified data model with explicit FK relationships across all operational domains directly addresses this. A member's full operational history — applications, tickets, roster entries, compliance evaluations, trust signals, authority grants, and audit entries — is a single query across subsystems, not a manual reconstruction from fragmented sources.

### Axis 13: Live Configuration Safety and Temporal Integrity

The problem definition says configuration changes on a live system can silently corrupt the semantic integrity of in-flight operations, and that this is an operational safety problem — not a versioning problem. The proposal engages with this directly through PolicyVersion objects that pin in-flight operations to the version active when they started. Form definitions, compliance rules, ticket routing, authority templates, and trust computation configurations are all versioned with this pinning behavior. The preview-confirm pattern for configuration changes surfaces the blast radius before the operator commits, addressing the problem definition's observation that the set of affected in-flight operations is not obvious until the change is attempted.
