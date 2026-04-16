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

The problem definition says the difficulty is calibrating and maintaining trust across organizational boundaries, staff turnover, and time — not collecting trust signals. The proposal engages with all three dimensions. Per-scope TrustProfiles address organizational boundaries: trust in one chapter does not transfer automatically to another. Signal provenance (each TrustSignal records who submitted it, when, and from what source) and deterministic computation from stored evidence ensure trust assessments survive staff turnover — no single officer's departure invalidates a member's trust profile. Signal expiration with decay rules and triggered recomputation handle temporal drift. The TrustComputationConfig makes the calibration itself operator-configurable per scope, so communities with different governance values can weight signals differently without code changes.

### Axis 2: Structured Intake and Adjudication

The problem definition says intake is a lifecycle under scarce staff time, not a single decision point, and identifies two specific sub-problems: each transition requires the right person to see the right context, and concurrent reviewer access to shared queues creates a mutual-exclusion problem that wastes staff effort. The proposal models intake as a nine-state state machine with explicit transitions. Context surfacing at review time (trust profile, prior applications, roster state) addresses the "right context" requirement. Single-reviewer claim ownership directly solves the collision problem — only one reviewer owns an application at a time, eliminating duplicated effort and conflicting decisions. Routing rules based on target scope direct applications to reviewers with the appropriate authority, addressing the "right person" requirement.

### Axis 3: Case Routing and State Management

The problem definition says tickets have an owner, status, category, history, and relationships to other operational objects, and the core difficulty is state management across a case's lifetime. The proposal models tickets with per-category configurable state machines, meaning each case type defines exactly the states and transitions its workflow requires — a harassment report can have different states than an account linking request. TicketTransition records create durable state history. Explicit FK relationships (to Application, Chapter, Member, other Tickets via `related_objects`) make cross-subsystem connections queryable rather than reconstructed from channel history. Ticket state lives in the community's database, so operational continuity no longer depends on a third-party vendor's availability or data model.

### Axis 4: Audit Trail and Long-term Accountability

The problem definition identifies two levels of difficulty. First, reconstructability: any past decision must be examinable with full context — who decided, what inputs they had, what alternatives existed, what policy governed the decision. Second, audit-as-precondition: when reconstructability is enforced as a hard invariant, audit unavailability becomes an operational outage for consequential decisions. The proposal's AuditEntry captures actor, action, target, policy version, previous state, new state, and a context snapshot preserving what the decision-maker saw at the time — independent of how system state has since changed. Entries are append-only and immutable with unlimited, community-controlled retention. For the availability tension, the proposal makes an explicit design choice: consequential officer decisions (approvals, denials, escalations) block when audit is unavailable, while routine automated transitions proceed with deferred entries. Officers attempting blocked actions receive explicit errors identifying what cannot proceed and why. Deferred entries record both the original operation timestamp and the audit persistence timestamp, preserving temporal accuracy even during degraded operation.

### Axis 5: Sub-community Provisioning and Lifecycle

The problem definition says every subgroup created today increases future cleanup cost, permissions grow combinatorially with the number of subgroups, and succession requires transferring operational context — not just a role. The proposal addresses cleanup cost through an explicit chapter lifecycle with an archival phase that resolves pending work (applications closed or transferred, tickets resolved or reassigned, authority grants reviewed) before preserving state. Template-based provisioning standardizes what each chapter creates in Discord, constraining the permission surface. Succession is handled through AuthorityGrant predecessor chains: the successor inherits the scope and its operational context — pending decisions, open tickets, roster state — and the transition itself is audited. The chapter lifecycle's probation state provides a governance path for chapters with problems (inactivity, leadership vacancy, policy violations) that is less drastic than immediate archival.

### Axis 6: Activity Tracking and Compliance Enforcement

The problem definition says compliance criteria are per-chapter, per-game, and per-season, and the system must ingest external evidence and apply configurable rules without itself becoming another data-entry burden. The proposal's ComplianceRule is scoped to a chapter with a season field and configurable rule type, covering all three dimensions. Automated scheduled evaluation collects evidence, applies rules, and generates results without officer involvement for routine cases. OCR extraction for screenshot evidence addresses the data-entry burden for the most labor-intensive evidence type. Officers interact only with outputs requiring judgment: violations, low-confidence extractions, and insufficient evidence cases. The consequence levels (notification_only, flag_for_review, auto_probation) let operators calibrate how much attention each rule's violations deserve, tying back to the problem definition's observation that the system must not become a manual burden.

### Axis 7: Permission Model and State Explosion

The problem definition identifies three layers of difficulty: the absence of an "intended permission state" against which actual state can be audited, the split between permissions that diverged from intent and permissions with no intent at all, and the migration challenge of classifying unmanaged permissions into a declared-intent model. The proposal engages with all three. PermissionIntent is the declared intended state, with each intent recording why the permission exists. PermissionDrift's nullable `permission_intent_id` distinguishes the two drift categories: drift with an intent (divergence) has a clear resolution path, while drift without an intent (direct Discord change bypassing the system) requires operator classification before resolution. The reconciliation workflow's three resolution options — reconcile, accept, acknowledge — provide the classification mechanism. Temporary intents with expiration and drift detection on expiry prevent the "temporary override becomes permanent" failure mode. The migration path exists through the drift detection mechanism itself: unmanaged permissions appear as unintended drift, which operators classify and bring into the managed set over time.

### Axis 8: Vendor Lock-in, Migration, and Data Portability

The problem definition says switching cost is invisible until urgent, lock-in accumulates as workflows and data accrete in vendor systems, and when migration is forced the community must move open cases, transcripts, permissions, staff habits, and policy assumptions. The proposal makes the community's database the authoritative source of truth for all operational data, with Discord as the interaction surface rather than the data store. Export paths exist for every data category. The data model is documented to enable replacement system construction without reverse-engineering. Platform boundary isolation ensures the operational model is expressed in platform-agnostic terms, so that Discord-specific behavior can be swapped without rebuilding business logic. No critical operational data lives exclusively in Discord or in an external vendor's system.

### Axis 9: Volunteer Coordination and Staff Burnout

The problem definition says the system must reduce the total attention cost of maintaining operational coherence, not just redistribute it, and every mandatory human touchpoint must justify itself against the risk of not having it. The proposal's "attention-justified process" design principle directly engages with this tension: the default is automation for routine state transitions, and human review is added only where the operator judges the risk warrants the attention cost. The compliance workflow exemplifies the principle — automated evaluation handles routine cases, officers intervene only for judgment calls. Application claim ownership eliminates wasted effort from duplicated reviews. NotificationRule design distinguishes actionable from informational notifications, with causal grouping that batches cascading effects from a single root action into one notification — preventing alert patterns that train officers to ignore alerts. Configurable consequence levels let operators match process rigor to risk severity.

### Axis 10: Delegated Authority and Governance

The problem definition says governance requires both local autonomy and central accountability, and Discord's role hierarchy expresses authority as global rank rather than scoped delegation. The proposal replaces rank-based authority with scope-based AuthorityGrants. An officer's capability is the intersection of their grants and the operation's scope — they cannot act on chapters outside their scope and cannot exceed their permission set within it. Scope enforcement is hard: a scope mismatch results in denial, not a warning. Central staff hold global-scoped grants with emergency override capability. Overrides generate enhanced audit entries that capture justification and the normal scope that would have denied the action, making overrides more visible rather than less — directly supporting the problem definition's implied requirement that accountability increases with authority.

### Axis 11: Platform Constraints and Moving-Target Risk

The problem definition says any system built on Discord must treat platform constraints as external facts that may change, not as stable foundations, and that platform assumptions must be verified rather than inherited. The proposal isolates Discord-specific behavior behind a defined boundary layer with an explicit mapping between system concepts (Member, Chapter, Ticket) and Discord expressions (user + roles, category + channels + roles, thread). The operational model references system concepts, never Discord specifics. When Discord changes — feature deprecated, added, or behavior changed — the Discord layer adapts without altering the operational model. Platform assumptions are verified at startup and on reconnection; degradation from missing capabilities is surfaced to operators rather than silently absorbed.

### Axis 12: Cross-workflow State and Operational Continuity

The problem definition says the core difficulty is maintaining coherent state across subsystem boundaries, and that cross-subsystem relationships must be first-class rather than reconstructed by officers from memory. The proposal's unified data model with explicit FK relationships across operational domains directly addresses this. A member's full operational history — applications, tickets, roster entries, compliance evaluations, trust signals, authority grants, and audit entries — is queryable through the data model, not reconstructed from fragmented sources. Cross-subsystem effects (application approval creating a roster entry triggering compliance activation) carry correlation identifiers linking each downstream event to the originating action. Subsystem independence is preserved — a compliance failure doesn't prevent querying application history — while the relationships between subsystems remain explicit and queryable.

### Axis 13: Live Configuration Safety and Temporal Integrity

The problem definition says a configuration change on a live system can silently corrupt the semantic integrity of in-flight operations, and that this is an operational safety problem — work begun under one set of rules must complete under those same rules. The proposal engages with this through PolicyVersion objects with version pinning: every configurable policy is versioned, and in-flight operations continue under the version active when they started. Form definitions pin submitted applications to their submission-time version. Compliance rules pin evaluations to the rule version at evaluation time. Trust computation configurations pin in-flight recomputations to the previous version when parameters change. The preview-confirm pattern shows operators the blast radius of a change — what will change, what in-flight operations are affected, and what the rollback path is — before the change takes effect. This addresses the problem definition's observation that the set of affected in-flight operations is not obvious until the change is attempted.

### Axis 14: Consolidated Failure Risk and Operational Availability

The problem definition says consolidation solves the fragmentation problem but inverts the failure model — when all operational subsystems share a platform, a platform-level failure can take down every workflow simultaneously. The core difficulty is that consolidation and failure isolation pull in opposite directions, and the system must maintain meaningful operational independence between subsystems even though they share infrastructure. The proposal engages with this tension as a first-class design concern. The "subsystem independence" design principle establishes that subsystems are peers with defined failure boundaries: failure in one produces errors for operations that depend on it but does not cascade to unrelated operations. The graceful degradation matrix specifies per-subsystem impact and unaffected operations. Cross-subsystem effects that fail are queued and surfaced to operators, so the upstream operation completes while the downstream effect retries. The audit subsystem is treated as a deliberate exception where failure may cascade to consequential operations — a choice the proposal makes explicitly and with defined operator experience during degraded state, rather than an uncontrolled cascade.
