# System Design Proposal

This document describes the design of a guild-management platform that replaces fragmented third-party bot dependencies with a unified operational system for long-lived gaming communities. The design addresses the fourteen problem axes defined in the problem definition, governed by the fifteen principles in the product philosophy.

---

## Design Principles

These structural commitments shape every design decision in the system. Each derives from one or more product philosophy principles and is stated here in operational terms.

**Durable operational state.** The system's database is the source of truth for all operational state. Discord is the interaction surface. When Discord state and system state diverge, system state is authoritative and Discord state is reconciled. *(Philosophy: P10 Durable State, P5 Low Lock-in)*

**Scoped authority.** Every operation occurs within a defined scope. Authority is granted per-scope, not per-rank. An actor's capability is the intersection of their authority grants and the scope of the operation. *(Philosophy: P7 Delegated Authority, P6 Trust and Safety)*

**Reconstructable decisions.** Every operational decision is recorded with enough context to reconstruct it after the fact: who decided, what inputs they had, what policy version applied, and what the prior state was. *(Philosophy: P6 Trust and Safety, P1 Operator Clarity)*

**Lifecycle-first objects.** Operational entities — applications, tickets, chapters, members — have defined state machines. State transitions are explicit, audited, and governed by the policy version active when the object entered its current state. *(Philosophy: P2 Live-Server Safety, P1 Operator Clarity)*

**Attention-justified process.** Every mandatory human touchpoint has a named risk it mitigates. The system's default is automation for routine state transitions; human review is added by operator configuration where the operator judges the risk warrants the attention cost. *(Philosophy: P9 Volunteer-Aware Design)*

**Declarative intent with reconciliation.** Operators declare what should be true (permission state, chapter structure, compliance rules). The system compares intent against reality and surfaces discrepancies rather than silently accumulating drift. *(Philosophy: P1 Operator Clarity, P7 Delegated Authority)*

**Subsystem independence.** Subsystems (intake, cases, chapters, compliance, audit) are peers. Failure in one produces errors for operations that depend on it but does not cascade to unrelated operations. Cross-subsystem effects that fail are queued and surfaced to operators. *(Philosophy: P12 Graceful Degradation)*

**Platform boundary isolation.** Discord-specific behavior is isolated behind defined boundaries. The operational model is expressed in platform-agnostic terms; the Discord layer translates between the operational model and Discord's current capabilities. *(Philosophy: P8 Platform-Native Interaction, P3 No Compatibility Shims)*

---

## Constraints

- **Single community.** The system serves one Discord server. Multi-tenant architecture is not a design goal.
- **Discord as sole interaction surface.** Members and operators interact through Discord. Operator configuration may have a web interface, but operational workflows are Discord-native.
- **External evidence is unverifiable.** The system cannot authenticate external evidence (screenshots, manual reports) with certainty. Evidence provenance is recorded, but fabrication by a motivated actor cannot be ruled out.
- **Discord platform caps are external facts.** Role limits (250), channel limits (500), category limits (50), API rate limits, and modal field limits constrain what the system can express in Discord. The system designs within them and adapts when they change.
- **Discord availability dependency.** If Discord is unavailable, the interaction surface is down. Durable state is preserved and operations resume on reconnection, but the system cannot offer an alternative surface during outages.

---

## Non-goals

- **General-purpose bot framework.** The system is a guild-management platform, not a toolkit for building arbitrary Discord bots.
- **Moderation-first design.** Moderation is one category of case in the case management subsystem, not the system's primary focus. The primary focus is operational management: intake, provisioning, tracking, and governance.
- **Feature parity with existing bots.** The system addresses underlying operational problems. Some existing bot features have no equivalent because they address symptoms rather than root causes.
- **AI-driven decision-making.** AI is used for data extraction (OCR, parsing). Operational decisions — approve, deny, flag, promote — are made by humans with the system providing information and surfacing relevant context.
- **Real-time game integration.** The system ingests data from game APIs where available, but does not maintain real-time synchronization with game servers.

---

## Data Model

Schema objects are grouped by operational domain. Cross-domain relationships are noted inline; a full relationship map follows.

### Identity and Trust

#### Member

The central entity linking a Discord user to the system's operational model.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | System-assigned identifier |
| `discord_user_id` | snowflake | Discord user identity |
| `joined_at` | timestamp | When the member first entered the system's scope |
| `status` | enum | `active`, `suspended`, `departed` |

A Member record is created when a Discord user enters the system's scope (joins the server or is first referenced in an operation). The record persists even after departure — operational history is never orphaned.

**Status lifecycle:**

```
active → suspended → active (reinstated)
                   → departed
active → departed
departed → active (rejoin)
```

- `active → suspended`: Initiated by an officer with authority over the member's scope (chapter officer for chapter-level suspension, global staff for server-level). Requires a reason. Triggers: governance review outcome, trust violation, pending investigation, or compliance escalation. Suspension is always an explicit officer decision — the system does not auto-suspend members (auto-probation via compliance rules changes RosterEntry status to `under_review`, not Member status to `suspended`).
- **Operational effects of suspension:** Suspended members cannot submit new applications, file tickets, or participate in chapter rosters. Existing RosterEntries transition to `on_leave`. Open tickets where the member is reporter remain visible to staff but the member cannot add messages. The member's Discord roles are synchronized to reflect the reduced access. Trust profile recomputation includes the suspension as an `incident_record` signal.
- `suspended → active`: Reinstatement by an officer with appropriate authority. Requires a reason. RosterEntries are not automatically restored — each chapter decides whether to reinstate the member's roster position.
- `suspended → departed` / `active → departed`: Member leaves the server or is removed. All chapter RosterEntries are closed. Authority grants are revoked. Operational history is preserved.
- `departed → active`: Member rejoins the server. A new trust profile is computed. Prior operational history (applications, tickets, compliance, audit entries) is still linked — the system recognizes returning members. Chapter memberships are not automatically restored.

Every status transition generates an AuditEntry with the actor, reason, and previous state.

#### TrustProfile

Per-member per-scope trust assessment, computed deterministically from signals.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `member_id` | FK → Member | |
| `scope` | enum + FK | `global` or FK → Chapter |
| `level` | numeric | Computed from constituent signals |
| `computed_at` | timestamp | Last recomputation time |

Trust is a gradient, not binary. Trust profiles exist per-scope because trust in one chapter does not automatically transfer to another — chapters decide whether to recognize cross-scope trust during their intake process. Trust profiles are recomputed when underlying signals change, so they reflect current evidence rather than a stale snapshot.

An operator can inspect any trust profile and see the exact signals contributing to the computed level, the weights applied to each signal (from the active TrustComputationConfig for the profile's scope), and the thresholds that determined the resulting level. The computation is deterministic: same signals under the same configuration produce the same level.

When a recomputation changes the trust level, the system generates an AuditEntry (`action_type: trust_recomputed`, `target_type: TrustProfile`) capturing the previous level, the new level, the computation config version used, and the signal change that triggered recomputation (new signal recorded, signal expired, config weights updated). This makes trust level transitions observable and queryable: an operator can answer "when did this member's trust level change?" and "what was this member's trust level on a specific past date?" directly from the audit trail, without replaying the computation. An appeals officer reviewing a denied application can verify the trust level the original reviewer saw by querying trust recomputation events bracketing the review timestamp.

#### TrustSignal

Individual evidence contributing to a trust profile.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `member_id` | FK → Member | |
| `signal_type` | enum | `identity_verification`, `chapter_tenure`, `officer_endorsement`, `compliance_history`, `incident_record` |
| `scope` | enum + FK | `global` or FK → Chapter |
| `value` | jsonb | Signal-specific structured data |
| `source` | enum + FK | `system` or FK → Member (the officer who recorded it) |
| `recorded_at` | timestamp | |
| `expires_at` | timestamp? | Signals may decay; null means indefinite |

Trust signals are the durable evidence that trust computations draw from. Because signals are individually stored with provenance, a trust profile survives staff turnover — it is derived from evidence, not from any single officer's judgment. Expired signals are retained for audit but excluded from active computation.

#### TrustComputationConfig

Operator-configurable parameters governing how trust signals combine into a trust level.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `scope` | enum + FK | `global` or FK → Chapter |
| `signal_weights` | jsonb | Weight per signal type: `identity_verification`, `chapter_tenure`, `officer_endorsement`, `compliance_history`, `incident_record` |
| `decay_rules` | jsonb | Per-signal-type decay curves: how signal influence diminishes over time |
| `level_thresholds` | jsonb | Ordered thresholds mapping computed scores to discrete trust levels |
| `version` | integer | Incremented on edit |
| `created_by` | FK → Member | |
| `effective_at` | timestamp | |
| `supersedes_id` | FK → TrustComputationConfig? | Previous version |

Trust computation parameters are operational configuration — analogous to ComplianceRule parameters or TicketCategory state machines. Different communities weight signal types differently based on their governance values: a community that values officer endorsement over tenure makes a fundamentally different governance choice than one that prioritizes compliance history. These choices must be expressible without code changes.

When a TrustComputationConfig is updated, a new version is created. In-flight trust recomputations triggered before the change complete under the previous version. The new version governs subsequent recomputations. Operators can inspect the active configuration for any scope and see exactly how signals combine — the formula connecting individual signals to the resulting trust level is visible, not opaque.

Chapter-scoped configurations override the global default for trust profiles within that chapter. A chapter that has not configured its own weights inherits the global configuration.

### Intake and Adjudication

#### FormDefinition

Operator-configurable intake form template.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `name` | string | Operator-facing name |
| `target_type` | enum | `chapter_membership`, `officer_candidacy`, `role_assignment`, `custom` |
| `fields` | jsonb | Ordered field definitions: text, select, image upload, etc. |
| `routing_rules` | jsonb | Which reviewer scope and queue receives applications |
| `version` | integer | Incremented on edit |
| `status` | enum | `active`, `retired` |

Form definitions are versioned. When an operator edits a form, a new version is created. In-flight applications retain the version they were submitted against — a form change never silently alters the meaning of an existing submission.

#### Application

An intake instance with a defined lifecycle.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `applicant_id` | FK → Member | |
| `form_definition_id` | FK → FormDefinition | Pinned to the version at submission time |
| `form_version` | integer | The specific form version |
| `target_scope` | FK → Chapter or role | What the applicant is applying for |
| `responses` | jsonb | Field values including uploaded media references |
| `state` | enum | `submitted`, `queued`, `claimed`, `in_review`, `interview`, `waitlisted`, `approved`, `denied`, `withdrawn` |
| `submitted_at` | timestamp | |
| `decided_at` | timestamp? | |
| `decision_reason` | text? | Required on approve or deny |

**State machine:**

```
submitted → queued → claimed → in_review → approved
                                         → denied
                                         → interview → approved
                                                     → denied
                                                     → waitlisted
                                         → waitlisted → claimed (reactivation)
              (any pre-decision state)   → withdrawn
```

Transitions:
- `submitted → queued`: Automatic, based on routing rules. No human action required.
- `queued → claimed`: A reviewer with authority in the target scope takes ownership. Prevents collisions — only one reviewer owns an application at a time.
- `claimed → in_review`: Reviewer begins evaluation. Application context (member trust profile, prior applications, chapter roster state) is surfaced to the reviewer.
- `in_review → interview`: Reviewer requests a private conversation. System provisions a private thread or channel.
- `in_review / interview → approved/denied`: Decision recorded with mandatory reason. Downstream effects triggered (roster entry, trust signal, role assignment for approvals).
- `→ waitlisted`: Application held pending capacity or future evaluation. Can be reactivated to `claimed` state.
- `→ withdrawn`: Applicant or authorized officer withdraws. Available from any pre-decision state.

Every transition generates an AuditEntry and notifications per configured rules.

#### ApplicationReview

Review actions taken on an application.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `application_id` | FK → Application | |
| `reviewer_id` | FK → Member | Must hold AuthorityGrant for target scope |
| `action` | enum | `claim`, `add_note`, `request_interview`, `approve`, `deny`, `waitlist`, `release_claim` |
| `notes` | text? | Reviewer-visible notes |
| `timestamp` | timestamp | |

### Case Management

#### TicketCategory

Configuration for a class of cases, defining routing and workflow.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `name` | string | `appeal`, `harassment_report`, `recruitment`, `dispute`, `account_linking`, `officer_request`, etc. |
| `routing_scope` | jsonb | Which authority scopes handle this category |
| `state_machine` | jsonb | Allowed states and transitions for this category |
| `sla_rules` | jsonb? | Time-based escalation thresholds |
| `privacy_level` | enum | `reporter_and_assigned`, `category_officers`, `all_staff` |

Categories are operator-configurable. Each category defines its own state machine — a harassment report may have different states than an account linking request. Privacy levels control visibility: harassment reports protect reporter identity from all but assigned staff; recruitment tickets may be visible to all chapter officers.

#### Ticket

A case with durable state, ownership, and lifecycle tracking.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `category_id` | FK → TicketCategory | |
| `reporter_id` | FK → Member | |
| `subject_id` | FK → Member? | The member the ticket is about, if applicable |
| `state` | enum | Defined by the category's state machine |
| `priority` | enum | Set during triage |
| `owner_id` | FK → Member? | Assigned officer |
| `related_ticket_ids` | FK[] → Ticket? | Other tickets within the case management subsystem related to this ticket |
| `created_at` | timestamp | |
| `resolved_at` | timestamp? | |
| `resolution` | jsonb? | Structured: outcome, reason, actions taken |

**State machine:** Each TicketCategory defines its own complete state machine via the `state_machine` field. There is no mandatory base set of states — categories that need triage, escalation, and multi-stage resolution define those states; categories where routing and priority are deterministic (e.g., account linking requests that always go to the same queue) can define a minimal state machine that skips triage entirely. The only structural requirement is that every category's state machine includes at least one terminal state.

A **default state machine** is provided for categories that do not need customization:

```
open → triaged → assigned → resolved → closed
                          → escalated → assigned (at higher scope)
                                      → resolved → closed
```

But a simple category like account linking might define:

```
open → assigned → resolved → closed
```

This flexibility ensures that every mandatory state transition — including human touchpoints like triage — justifies its attention cost for the specific category it governs.

Within the case management subsystem, tickets carry explicit relationships to other tickets through `related_ticket_ids` — an appeal ticket can reference the original moderation ticket it appeals. Cross-subsystem relationships — a ticket about an application appeal, a ticket about a chapter dispute — are traced through correlated AuditEntries sharing a `correlation_id`, not through foreign key references to objects in other subsystems. The CQRS read model (see Cross-workflow State Coherence) materializes these event-based relationships into queryable views, so "all tickets related to this member" remains a practical operator query without coupling the case management schema to the intake or chapter subsystem schemas.

#### TicketMessage

Messages within a ticket, with visibility controls.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `ticket_id` | FK → Ticket | |
| `author_id` | FK → Member | |
| `content` | text | |
| `visibility` | enum | `reporter_visible`, `staff_only`, `category_officers_only` |
| `timestamp` | timestamp | |

Visibility levels allow staff-only coordination within a ticket without exposing internal discussion to the reporter. This is critical for sensitive categories (harassment reports, appeals) where the reporter should see updates but not internal deliberation.

#### TicketTransition

State change record for a ticket.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `ticket_id` | FK → Ticket | |
| `from_state` | enum | |
| `to_state` | enum | |
| `actor_id` | FK → Member | |
| `reason` | text? | Required for escalation and resolution |
| `timestamp` | timestamp | |

### Sub-community Lifecycle

#### ChapterTemplate

Provisioning blueprint for creating new chapters.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `name` | string | |
| `channel_structure` | jsonb | Channels and categories to create |
| `role_structure` | jsonb | Default ChapterRole definitions: names, ordinals, succession triggers, and authority templates |
| `default_compliance_rules` | jsonb | Initial activity requirements |
| `default_permission_intents` | jsonb | Initial permission state |

Templates encode the community's standard chapter structure. When a new chapter is provisioned, the template determines what Discord resources are created, what authority levels exist, and what initial compliance rules apply. Templates are operator-configurable and versioned.

**Configuration governance boundary:** The Chapter `configuration` field holds non-operational metadata — display names, descriptions, icons, and visual settings that do not affect operational behavior. All operational configuration — compliance thresholds, intake routing, notification rules, authority templates, trust computation parameters — is governed through chapter-scoped PolicyVersion records with version pinning, preview-confirm patterns, and audit. This boundary ensures that chapter officers can customize their chapter's presentation without risking the temporal integrity guarantees that PolicyVersion provides for operational settings.

#### Chapter

A sub-community with a defined lifecycle.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `name` | string | |
| `template_id` | FK → ChapterTemplate | |
| `state` | enum | `proposed`, `provisioning`, `active`, `probation`, `archiving`, `archived` |
| `discord_resources` | jsonb | Category IDs, channel IDs, role IDs — actual Discord objects |
| `configuration` | jsonb | Non-operational chapter metadata: display name, description, icon, visual settings. Does not hold operational settings |
| `created_at` | timestamp | |
| `archived_at` | timestamp? | |

**State machine:**

```
proposed → provisioning → active → probation → active (reinstated)
                                              → archiving → archived
                                 → archiving → archived
```

- `proposed → provisioning`: Requires approval from an actor with authority at the parent scope (global or designated approver). Discord resources created from template.
- `provisioning → active`: Discord resources verified as created. Chapter is operational.
- `active → probation`: Triggered by governance concerns (inactivity, leadership vacancy, policy violations). Central staff notified. Chapter operations continue but new intake may be suspended.
- `probation → active`: Issues resolved, chapter reinstated.
- `→ archiving`: Roster members notified, pending applications and tickets resolved or transferred, chapter-scoped authority grants reviewed. Discord channels marked read-only.
- `archiving → archived`: All state preserved for audit and reference. Operational history remains queryable. Discord resources may be removed or retained per operator preference.

#### ChapterTransition

State change record for a chapter.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `chapter_id` | FK → Chapter | |
| `from_state` | enum | |
| `to_state` | enum | |
| `actor_id` | FK → Member | |
| `reason` | text | |
| `timestamp` | timestamp | |

#### ChapterRole

Operator-configurable position within a chapter's governance structure.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `chapter_id` | FK → Chapter | |
| `name` | string | Operator-defined name (e.g., `leader`, `officer`, `member`, `co-leader`, `senior_member`, `trainee`) |
| `ordinal` | integer | Position in the chapter's governance hierarchy; higher ordinal = higher authority within the chapter |
| `triggers_succession` | boolean | Whether vacancy in this role triggers the succession workflow |
| `default_authority` | jsonb | Authority grant template automatically applied when a member is assigned this role |
| `version` | integer | Incremented on edit |

ChapterRoles are per-chapter, inheritable from ChapterTemplate. When a chapter is provisioned, the template's `role_structure` field seeds the chapter's initial role definitions. Chapter officers with appropriate authority can add, rename, or reconfigure roles — including adding positions the template did not include (e.g., `co-leader`, `trainee`) — without code changes or system redeployment. *(Philosophy: P11 Configuration by Operators, P7 Delegated Authority)*

Roles carry operational significance through their attributes: `triggers_succession` determines which role departures activate the succession workflow, and `default_authority` determines what AuthorityGrant is created when a member is assigned to the role. This means organizational structure is an operator governance choice, not a system-imposed constraint. A community where chapters have flat structures (one `coordinator` role and one `member` role) and a community with deep hierarchies (`guild_master`, `officer`, `sergeant`, `member`, `recruit`) both configure their structure through the same mechanism.

The `ordinal` field establishes an ordering within a chapter for governance purposes (e.g., succession candidates, authority escalation) but does not imply cross-chapter equivalence — a role with ordinal 3 in one chapter has no automatic relationship to ordinal 3 in another chapter.

#### RosterEntry

A member's position in a chapter.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `chapter_id` | FK → Chapter | |
| `member_id` | FK → Member | |
| `role_id` | FK → ChapterRole | The member's current position in the chapter's governance structure |
| `joined_at` | timestamp | |
| `status` | enum | `active`, `on_leave`, `under_review`, `removed` |
| `removed_at` | timestamp? | |
| `removal_reason` | text? | |

Roster entries are the authoritative record of chapter membership. A member's chapter affiliation is determined by their RosterEntry, not by which Discord roles they hold. Discord roles are synchronized from roster state, not the other way around. The `role_id` references the chapter's configurable governance structure (see ChapterRole), allowing each chapter to define its own positions and hierarchy.

**Status lifecycle:**

```
active → on_leave → active (returned)
                  → removed
active → under_review → active (cleared)
                      → removed
active → removed
```

- `active → on_leave`: Initiated by an officer with chapter-scoped authority, or as a downstream effect of Member suspension. Requires a reason.
- `on_leave → active`: Return from leave. Initiated by an officer or the member (per chapter configuration). Requires a reason.
- `active → under_review`: Triggered by compliance auto-probation (`consequence: auto_probation`) or by direct officer action for governance concerns. The member remains on the roster but is flagged for evaluation.
- `under_review → active`: Officer clears the review after evaluation. Requires a reason.
- `under_review → removed` / `on_leave → removed` / `active → removed`: Member removed from chapter roster. Initiated by an officer with chapter-scoped authority, or as a downstream effect of Member departure. Requires a reason.

Every status transition and role change generates a RosterTransition record and an AuditEntry (`action_type: roster_changed`, `target_type: RosterEntry`), capturing the actor, reason, previous state, and new state. Direct officer roster actions — the most operationally common case for chapter-level management — are attributed and auditable through the same mechanisms as application decisions and ticket escalations.

#### RosterTransition

State change record for a roster entry.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `roster_entry_id` | FK → RosterEntry | |
| `from_state` | enum | Previous status |
| `to_state` | enum | New status |
| `from_role_id` | FK → ChapterRole? | Previous role, if role changed |
| `to_role_id` | FK → ChapterRole? | New role, if role changed |
| `actor_id` | FK → Member | Officer who initiated the change |
| `reason` | text | Required for all transitions |
| `timestamp` | timestamp | |

### Activity and Compliance

#### ComplianceRule

Operator-configurable activity requirement scoped to a chapter.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `chapter_id` | FK → Chapter | |
| `name` | string | |
| `rule_type` | enum | `attendance`, `rank_requirement`, `activity_minimum`, `custom` |
| `parameters` | jsonb | Threshold, period, evidence source requirements |
| `consequence` | enum | `notification_only`, `flag_for_review`, `auto_probation` |
| `active` | boolean | |
| `season` | jsonb? | Time window; null means always active |
| `version` | integer | |

Compliance rules are per-chapter, per-game, and per-season — the three dimensions the problem definition identifies as core to the difficulty. Each rule specifies what evidence satisfies it, what threshold applies, and what happens on violation. The consequence levels scale from informational (notify officer) through advisory (flag for review) to automated (place member under review), with the operator choosing the level based on how much risk each rule's violation represents.

#### EvidenceSubmission

External evidence for compliance evaluation.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `member_id` | FK → Member | |
| `chapter_id` | FK → Chapter | |
| `evidence_type` | enum | `game_api`, `screenshot`, `manual_report` |
| `raw_data` | binary/jsonb | Original submission |
| `extracted_data` | jsonb? | Structured data from OCR/parsing; null if not applicable or extraction failed |
| `extraction_confidence` | numeric? | OCR confidence score |
| `submitted_by` | FK → Member | Self-report, officer, or system (for API-sourced) |
| `submitted_at` | timestamp | |

Evidence provenance is always recorded: who submitted it, when, and from what source. When evidence is a screenshot, OCR extracts structured data with a confidence score. Low-confidence extractions are flagged for officer review rather than silently accepted.

#### ComplianceEvaluation

Result of evaluating a member against a compliance rule for a period.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `member_id` | FK → Member | |
| `chapter_id` | FK → Chapter | |
| `rule_id` | FK → ComplianceRule | Pinned to version at evaluation time |
| `rule_version` | integer | |
| `period` | jsonb | Time window evaluated |
| `evidence_ids` | FK[] → EvidenceSubmission | Evidence considered |
| `result` | enum | `compliant`, `violation`, `insufficient_evidence` |
| `evaluated_at` | timestamp | |
| `consequence_applied` | jsonb? | What action was taken, if any |

Evaluations run on schedule. The system collects evidence, applies rule parameters, and generates results. Officers interact only with the outputs that require judgment: violations, low-confidence evaluations, and cases where evidence is insufficient (which may indicate a member needs to submit evidence, not that they are non-compliant).

### Permission Management

#### PermissionIntent

The declared intended permission state for a role-channel combination.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `scope` | enum + FK | `global` or FK → Chapter |
| `role_id` | snowflake | Discord role |
| `channel_id` | snowflake? | Discord channel; null means server-level |
| `permission_bits` | bigint | Intended permission state |
| `reason` | text | Why this permission exists |
| `temporary` | boolean | |
| `expires_at` | timestamp? | Required if temporary |
| `set_by` | FK → Member | |
| `set_at` | timestamp | |

PermissionIntents are the declarative model of what permissions should exist. Operators work with intents, not with raw Discord permission bits. Each intent records why the permission exists — this is the "intended state" that the problem definition identifies as missing from Discord's native model.

Temporary intents have explicit expiration. When an intent expires, the system generates a PermissionDrift entry, surfacing the expired override for operator action. This directly prevents the "temporary override becomes permanent" failure mode.

#### PermissionDrift

A detected discrepancy between intended and actual Discord permission state.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `permission_intent_id` | FK → PermissionIntent? | Null if drift is from an unknown source (permission exists in Discord with no matching intent) |
| `detected_at` | timestamp | |
| `actual_bits` | bigint | What Discord has |
| `intended_bits` | bigint? | What the system expects; null if no intent exists |
| `status` | enum | `detected`, `acknowledged`, `reconciled`, `accepted` |
| `resolved_by` | FK → Member? | |
| `resolved_at` | timestamp? | |

**Resolution options:**
- `reconciled`: Apply intent to Discord (fix the drift).
- `accepted`: Update intent to match reality (acknowledge the change as intentional).
- `acknowledged`: Mark as known, defer action (for cases where the operator needs to investigate or coordinate before resolving).

Drift entries where no matching intent exists represent permissions that were set outside the system — direct Discord changes that bypassed the declared model. These are surfaced to operators as "unintended" drift requiring classification.

### Governance

#### AuthorityGrant

Scoped delegation of operational authority.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `grantee_id` | FK → Member | |
| `scope` | enum + FK | `global`, FK → Chapter, or subsystem-scoped |
| `permissions` | jsonb | Set of allowed operations within scope |
| `granted_by` | FK → Member | |
| `granted_at` | timestamp | |
| `expires_at` | timestamp? | |
| `revoked_at` | timestamp? | |
| `revoked_by` | FK → Member? | |
| `revocation_reason` | text? | |
| `predecessor_grant_id` | FK → AuthorityGrant? | For succession chains |

Authority is scoped, not ranked. An officer with a chapter-scoped grant can perform the operations listed in their `permissions` set within that chapter. They cannot act on other chapters, and they cannot exceed their permission set even within their chapter. Central staff hold global-scoped grants with override capability.

Every operation checks the actor's AuthorityGrant against the operation's scope. A scope mismatch or missing permission results in denial, not a warning.

**Succession:** When a member holding a ChapterRole with `triggers_succession: true` departs, succession creates a new AuthorityGrant for the successor linked to the predecessor grant via `predecessor_grant_id`. The successor inherits the scope definition and operational context (pending decisions, open tickets, roster state). The system does not just transfer a Discord role — it transfers the operational authority and its history.

#### PolicyVersion

Versioned governance configuration.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `policy_type` | enum | `intake_rules`, `compliance_thresholds`, `ticket_routing`, `authority_templates`, `notification_rules` |
| `scope` | enum + FK | `global` or FK → Chapter |
| `version_number` | integer | |
| `content` | jsonb | The policy configuration |
| `effective_at` | timestamp | |
| `created_by` | FK → Member | |
| `supersedes_id` | FK → PolicyVersion? | Previous version |

Every configurable policy is versioned. When an operator changes a policy, a new version is created. In-flight operations continue under the version that was active when they started. This ensures that a policy change never silently alters the meaning of in-progress work (e.g., an application submitted under one set of intake rules is reviewed under those rules, even if the rules changed after submission).

#### AuditEntry

Immutable record of an operational decision.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `timestamp` | timestamp | |
| `actor_id` | FK → Member | |
| `action_type` | enum | `application_decided`, `ticket_escalated`, `chapter_transitioned`, `role_changed`, `policy_updated`, `authority_granted`, `authority_revoked`, `compliance_evaluated`, `permission_reconciled`, `drift_resolved`, `member_status_changed`, `evidence_submitted`, `override_used`, `trust_recomputed`, `roster_changed` |
| `target_type` | enum | `Application`, `Ticket`, `Chapter`, `Member`, `ComplianceRule`, `PermissionIntent`, `AuthorityGrant`, `PolicyVersion`, `TrustProfile`, `RosterEntry` |
| `target_id` | uuid | |
| `scope` | enum + FK | `global` or FK → Chapter |
| `correlation_id` | uuid | Root causal chain identifier; all events in a causal cascade share the same correlation_id |
| `causation_id` | FK → AuditEntry? | The specific event that directly caused this event; null for root-cause events |
| `policy_version_id` | FK → PolicyVersion? | What rules governed this decision |
| `context` | jsonb | Snapshot of relevant state at decision time |
| `previous_state` | jsonb? | State before the action |
| `new_state` | jsonb | State after the action |
| `reason` | text? | Required for consequential actions |

AuditEntries are **append-only and immutable**. No entry is deleted or modified after creation. The `context` field captures enough state that a reviewer can understand the decision without access to the system's current state (which may have changed since the decision was made). This is the mechanism that makes decisions reconstructable months or years later — not just "who did what" but "what did they see and what rules applied."

**Correlation mechanism:** AuditEntries serve as the cross-subsystem event fabric. The `correlation_id` links all events in a causal chain: when an application approval triggers a roster entry creation, which triggers compliance rule activation, all three AuditEntries share the same `correlation_id`. The `causation_id` links each event to its direct cause, enabling both full-chain queries (all events sharing a `correlation_id`) and step-by-step causal navigation (following `causation_id` links). The root event in a chain has `causation_id: null`. This is the mechanism that P15 (Traceability as Outcome) requires: cross-subsystem relationships are expressed through event correlation, not foreign key navigation at the data layer. Within a subsystem, schema objects use explicit foreign keys freely; across subsystem boundaries, correlated AuditEntries are the connective tissue.

Retention is unlimited and under community control. The system does not impose a retention cap.

#### NotificationRule

Operator-configurable triggers for officer notifications.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `trigger` | jsonb | State transition type or subsystem event |
| `scope` | enum + FK | `global` or FK → Chapter |
| `recipients` | jsonb | Authority scope that determines who receives |
| `channel` | enum | `dm`, `thread`, `designated_channel` |
| `template` | jsonb | Notification content template |
| `actionable` | boolean | Whether this notification expects a response |
| `grouping` | enum | `per_event`, `per_root_cause` |

The default notification configuration is minimal. Operators add rules for the events they need to know about. Notifications are either actionable (the officer needs to do something) or explicitly informational (the operator chose to be informed). The system does not generate notifications that neither require action nor were explicitly requested.

**Causal grouping:** Operational actions frequently produce cascading events across subsystems — an application approval creates a RosterEntry, which activates compliance rules, which may generate an initial evaluation. Each AuditEntry in the cascade carries a `correlation_id` linking it to the root cause event (see AuditEntry correlation mechanism). NotificationRules with `grouping: per_root_cause` batch notifications for all AuditEntries sharing the same `correlation_id` into a single notification summarizing the root action and its downstream effects. Rules with `grouping: per_event` (the default) fire independently per event. This prevents notification patterns that train officers to ignore alerts: an officer who configures rules for application decisions, roster changes, and compliance activations receives a single grouped notification for what is, from their perspective, a single action's consequences — rather than independent notifications for each downstream effect.

---

## Operational Workflows

### Member Onboarding

1. Discord user joins the server.
2. System creates a Member record (`status: active`).
3. System creates a global TrustProfile with initial level computed from available signals (Discord account age, server join method, mutual servers — whatever the community has configured as initial trust signals) using the weights and thresholds from the active global TrustComputationConfig.
4. If the community has configured intake requirements for server-level access, the member enters the application intake flow for the relevant FormDefinition.
5. If no intake requirements are configured, the member receives base access as determined by the community's permission intents.

No action is invisible. The member's initial trust level is computable from documented signals. The operator can inspect any new member's trust profile and see exactly why they received the level they did.

### Application Intake

1. Member selects a FormDefinition and submits responses. Application created (`state: submitted`).
2. Routing rules evaluate the application's target scope and assign it to the appropriate queue. Application transitions to `queued`.
3. A reviewer with an AuthorityGrant covering the target scope claims the application. Application transitions to `claimed`. The system surfaces the applicant's context: trust profile, prior applications (if any), relevant chapter roster state.
4. Reviewer evaluates and may add notes. Application transitions to `in_review`.
5. Reviewer may request an interview — the system provisions a private thread. Application transitions to `interview`.
6. Reviewer renders a decision:
   - **Approve**: Application transitions to `approved`. Downstream effects fire: RosterEntry created (if chapter membership), trust signal recorded, Discord roles synchronized. Decision reason recorded.
   - **Deny**: Application transitions to `denied`. Decision reason required. Applicant notified per category rules.
   - **Waitlist**: Application transitions to `waitlisted`. Can be reactivated later by a reviewer claiming it.
7. At any pre-decision state, the applicant or an authorized officer can withdraw the application.

Each transition generates an AuditEntry capturing the actor, the application's state at transition time, and the policy version governing the intake process. Notifications fire per configured NotificationRules.

When reviewers claim applications, the system prevents two reviewers from claiming the same application, eliminating the "two officers reviewing the same app without knowing" collision.

### Ticket Lifecycle

The specific flow depends on the category's state machine. The following describes the default workflow for categories that use the full state machine (triage → assignment → resolution). Categories with simplified state machines (e.g., account linking: open → assigned → resolved → closed) skip steps that their state machine does not include.

1. Reporter creates a ticket by selecting a TicketCategory. System creates a Ticket in the category's initial state and routes it to the category's queue per routing rules.
2. For categories with a triage state: an officer triages the ticket — sets priority, may reclassify category. For categories without triage: the system applies deterministic routing (category defaults for priority and assignment queue) and the ticket proceeds directly to assignment.
3. Officer assigns the ticket (to self or another officer with appropriate authority). Ticket transitions to `assigned`.
4. Case work proceeds. TicketMessages are exchanged within visibility constraints (reporter-visible vs. staff-only). Related objects are linked as they become relevant.
5. If the category's state machine includes escalation and the assigned officer cannot resolve the case, they escalate. Ticket transitions to `escalated`, which follows the category's escalation path (e.g., chapter officer → global staff). Reason required.
6. Officer resolves the case. Ticket transitions to `resolved`. Resolution is structured: outcome, reason, actions taken. Required fields.
7. After a configurable resolution period (for follow-up or appeal), ticket transitions to `closed`.

The full transcript — messages, transitions, related objects — is stored in the database. If the Discord thread associated with the ticket is deleted, the operational record persists.

For sensitive categories (harassment reports), privacy levels control who sees what. The reporter's identity is protected from the accused. Staff-only messages allow internal coordination without exposing deliberation.

### Chapter Lifecycle

**Provisioning:**
1. An authorized actor proposes a new chapter, selecting a ChapterTemplate. Chapter created (`state: proposed`).
2. Approval gate: an actor with authority at the parent scope (global or designated approver) approves creation.
3. System provisions Discord resources from the template: creates channels, categories, roles. Chapter transitions to `provisioning`.
4. System verifies resource creation. Chapter transitions to `active`.

**Operations:**
- Roster management through RosterEntries (intake via application, direct add by authorized officer).
- Chapter-scoped compliance rules configured by chapter officers.
- Chapter-scoped authority grants managed by members holding roles with appropriate authority (within their delegated scope).

**Governance events:**
- If the chapter enters governance review (inactivity, leadership vacancy, policy violations), transition to `probation`. Central staff notified. Chapter operations may continue but new intake can be suspended per operator configuration.
- Probation resolved: transition back to `active`.

**Archival:**
1. Decision to close a chapter triggers transition to `archiving`.
2. System processes: roster members notified, pending applications closed or transferred, open tickets resolved or reassigned, chapter-scoped authority grants reviewed.
3. Discord resources marked read-only or removed per operator preference.
4. Chapter transitions to `archived`. All operational state preserved — roster history, compliance records, audit entries, ticket transcripts — queryable for audit and reference.

**Succession:**
When a member holding a ChapterRole with `triggers_succession: true` departs (removal, departure, term expiration):
1. System identifies pending decisions, open tickets, and in-progress operations owned by the departing member.
2. A new AuthorityGrant is created for the successor, linked to the predecessor grant. The successor inherits the scope and its operational context.
3. Pending items are transferred to the successor or flagged for review if no successor is designated.
4. The transition is audited: who left, who succeeded, what was transferred, what was flagged.

The system does not lose governance continuity during leadership transitions. The successor can review the predecessor's decisions, see the chapter's operational history, and pick up in-progress work.

### Compliance Evaluation

1. Scheduled trigger initiates evaluation for a chapter's active compliance rules.
2. For each member in the chapter roster with `status: active`:
   a. Collect EvidenceSubmissions for the evaluation period.
   b. If evidence includes screenshots: run OCR extraction, store extracted data with confidence score.
   c. Evaluate evidence against rule parameters (threshold, period, evidence type requirements).
   d. Generate ComplianceEvaluation recording the result, evidence considered, and rule version.
3. Results with `violation` or `insufficient_evidence` are processed per the rule's configured consequence:
   - `notification_only`: Officer notified. No state change.
   - `flag_for_review`: Member's RosterEntry status updated to `under_review`. Officer must review and either confirm or override.
   - `auto_probation`: Member placed under review automatically. Officer notified with full context.
4. Officers review flagged evaluations. They can confirm the violation (which may trigger further action per policy), override (marking the member compliant with reason), or request additional evidence.

The system does the cross-referencing and threshold checking that the problem definition identifies as a primary source of officer burnout. Officers intervene only for judgment calls: ambiguous evidence, edge cases, overrides. Routine compliance for members with clear evidence is processed without human intervention.

### Permission Reconciliation

1. Reconciliation runs on schedule or on manual trigger by an authorized operator.
2. System reads current Discord permission state for all managed roles and channels.
3. Compares actual state against PermissionIntent records.
4. For each discrepancy:
   a. If an intent exists but actual state differs → PermissionDrift created (intent vs. reality).
   b. If actual state exists with no matching intent → PermissionDrift created (unintended permission).
   c. If an intent is marked temporary and has expired → PermissionDrift created (expired override).
5. Drift entries surfaced to operators with authority over the affected scope.
6. Operator resolves each drift entry:
   - **Reconcile**: System applies intent to Discord.
   - **Accept**: System updates intent to match reality.
   - **Acknowledge**: Drift marked as known, deferred for later resolution.
7. All resolutions generate AuditEntries.

This workflow gives operators the "intended state" concept that the problem definition identifies as absent from Discord's native model. The system detects when accumulated permission decisions have created a state that no single person can reason about, and surfaces the discrepancies for explicit resolution rather than silent accumulation.

---

## Governance Mechanisms

### Policy Versioning

Every configurable policy — form definitions, compliance rules, ticket routing, authority templates, notification rules — is versioned through the PolicyVersion object. When an operator changes a policy:

1. The system creates a preview showing what will change and what in-flight operations will be affected.
2. The operator confirms.
3. A new PolicyVersion is created. The old version is preserved.
4. In-flight operations continue under the version active when they started.
5. New operations use the current version.

This mechanism ensures that policy changes are safe to apply on a live server. An operator can update compliance rules mid-season without retroactively changing evaluations that already ran. An operator can modify an application form without invalidating submissions already in review.

Destructive configuration changes (retiring a form definition, deactivating a compliance rule) require confirmation and preserve historical data. The old version remains queryable for audit even after retirement.

### Authority Scope Enforcement

Every system operation checks authority before execution:

1. Identify the operation's scope (which chapter, which subsystem, global).
2. Look up the actor's AuthorityGrants.
3. Check that at least one grant covers the operation's scope and includes the required permission.
4. If no matching grant: deny the operation with a clear explanation of what authority is needed.
5. If matching grant: execute and log with reference to the grant used.

This is not a suggestion system. An officer without chapter_A authority cannot act on chapter_A objects, regardless of their Discord role hierarchy. The system enforces scope boundaries, not just visibility boundaries.

**Emergency overrides:** Central staff with global-scoped authority can override scope restrictions. Overrides generate enhanced audit entries that capture the justification and the normal scope that would have denied the action. This preserves the principle that accountability increases with authority — overrides are more visible, not less.

### Audit Chain

AuditEntries form causal chains through `correlation_id` and `causation_id`. An application approval that creates a roster entry that triggers compliance rule activation is traceable as a connected sequence sharing a single `correlation_id`:

1. Application approved (AuditEntry: target=Application, correlation_id=X, causation_id=null — root cause)
2. Roster entry created (AuditEntry: target=RosterEntry, correlation_id=X, causation_id=→ entry 1)
3. Compliance rules activated (AuditEntry: target=ComplianceEvaluation, correlation_id=X, causation_id=→ entry 2)

Tracing forward: query all AuditEntries with the same `correlation_id`, ordered by timestamp. Tracing backward: follow the `causation_id` chain from any event to its root cause. An auditor asking "why was this member flagged for compliance?" follows the `causation_id` from the compliance evaluation → roster entry creation → application approval → original submission, without navigating foreign keys across subsystem schemas.

The CQRS read model materializes these chains into queryable views for common operator queries (see Cross-workflow State Coherence). The raw correlation chain in AuditEntries remains the authoritative record.

### Configuration Safety

Configuration changes follow a preview-confirm pattern:

1. Operator initiates a change (modify form, update rule, change routing).
2. System generates a preview: what changes, what existing objects are affected, what the rollback path is. The preview captures the current policy version number.
3. Operator confirms or cancels.
4. On confirmation: the system verifies that the policy version the operator previewed is still current. If another operator has confirmed a change to the same policy between preview and confirm, the confirmation is rejected with an updated preview reflecting the new current state. The operator reviews the updated preview and confirms again. This prevents decisions based on stale previews — the operator always confirms against the actual current state.
5. On successful confirmation: change takes effect immediately (no restart required), AuditEntry generated, affected operators notified per rules.

Operators never need to edit code, environment variables, or config files. All operational configuration is managed through Discord commands or the web interface and takes effect without redeployment.

---

## AI/ML Approaches

### Screenshot OCR for Compliance Evidence

**Purpose:** Extract structured activity data from screenshot evidence submitted for compliance evaluation.

**Input:** Screenshot image (PNG, JPG) uploaded as an EvidenceSubmission with `evidence_type: screenshot`.

**Processing:**
1. OCR engine extracts text regions from the image.
2. Extracted text is parsed against known game UI patterns to identify structured fields: event name, date, participant names, scores, ranks, attendance markers.
3. Structured data stored in `extracted_data` with a confidence score in `extraction_confidence`.

**Output:** Structured compliance evidence with field-level confidence scores, stored alongside the raw screenshot for verification.

**Known limitations:**
- OCR accuracy varies with screenshot quality, resolution, language, and game UI complexity.
- The system cannot verify that a screenshot is authentic, recent, or from the claimed game session.
- Game UI changes may invalidate extraction patterns until patterns are updated.
- Non-Latin text, overlapping UI elements, and low-contrast themes reduce extraction accuracy.

**Safeguards:**
- Extractions below a configurable confidence threshold are flagged for manual officer review rather than accepted automatically.
- Officers can correct extracted data; corrections are stored as overrides with attribution.
- The raw screenshot is always preserved alongside extracted data — the extraction is an aid, not a replacement for the original evidence.
- The system never auto-confirms compliance based solely on OCR output. OCR provides structured data; compliance rules evaluate that data; violations trigger officer review. The decision chain always includes a human judgment point for contested cases.

---

## Cross-cutting Concerns

### Cross-workflow State Coherence

Cross-subsystem relationships are expressed through event correlation, not foreign key navigation. Within each subsystem, schema objects reference each other freely through explicit foreign keys. Across subsystem boundaries, correlated AuditEntries — sharing a `correlation_id` — are the connective tissue that links causally related operations.

When one subsystem generates an effect in another (application approval → roster entry → compliance activation), each step emits an AuditEntry. The downstream entries carry the same `correlation_id` as the root cause and a `causation_id` pointing to the specific entry that triggered them. The operational relationship is first-class — recorded in durable, queryable events — without coupling the data models of the subsystems involved.

**CQRS read model:** The event-based write path preserves subsystem independence (P15), but operators need ergonomic cross-subsystem queries — "what is this member's full operational history?" should not require manual event correlation (P1). A read-optimized aggregation layer materializes cross-subsystem views from AuditEntries into queryable read models:

- **Member operational history:** Aggregated from AuditEntries where the member appears as `actor_id` or in `target_id` across all subsystems — applications, tickets, roster entries, compliance evaluations, trust signals, authority grants.
- **Causal chain views:** Materialized from `correlation_id` groupings, providing operators with a single view of a root action and all its downstream effects across subsystems.
- **Scope-filtered views:** Per-chapter or per-subsystem projections of operational history, supporting delegated authority (a chapter officer sees their chapter's operational history without global visibility).

The read models are derived from events and updated asynchronously. They carry no authority — the AuditEntry event stream is the source of truth for cross-subsystem relationships. If the read model is stale or unavailable, operators can still query AuditEntries directly by `correlation_id`; they lose query convenience, not data integrity. This separation ensures that subsystem data models remain independent: schema evolution in one subsystem does not affect the schemas of other subsystems, only the read model's materialization logic. Replacing or restructuring a subsystem means updating the event-emitting code and the read model projection — not migrating foreign keys across subsystem boundaries.

### Platform Boundary

The system's operational model is expressed in its own terms: Members, Applications, Tickets, Chapters, ComplianceRules. The Discord layer maps between these and Discord constructs:

| System concept | Discord expression |
|---|---|
| Member | Discord user + managed roles |
| Chapter | Category + channels + roles |
| Ticket conversation | Thread or private channel |
| Application interview | Private thread |
| Permission intent | Role permission bits + channel overwrites |
| Notification | DM, thread message, or channel message |

When Discord changes its capabilities:
- **Feature deprecated:** The Discord layer adapts its mapping. The operational model is unchanged.
- **Feature added:** The Discord layer can adopt it (e.g., a new component type for intake forms) without changing the operational model.
- **Behavior changed:** Platform assumptions documented in the boundary layer are updated. Operational logic is unaffected because it references system concepts, not Discord specifics.

The system verifies platform assumptions at startup and on reconnection. If a previously available capability is missing, the system surfaces the degradation to operators rather than silently failing.

### Graceful Degradation

Subsystems are peers with defined failure boundaries:

| Subsystem failure | Impact | Unaffected |
|---|---|---|
| Intake (applications) | New applications cannot be submitted or processed | Tickets, chapters, compliance, permissions |
| Cases (tickets) | New tickets cannot be created; open tickets cannot be transitioned | Applications, chapters, compliance, permissions |
| Compliance | Evaluations do not run on schedule | Applications, tickets, chapters, permissions |
| Permission reconciliation | Drift detection paused; intents still accepted | Applications, tickets, chapters, compliance |
| CQRS read model | Cross-subsystem queries fall back to direct AuditEntry correlation queries; slower but complete | All write-path operations, all within-subsystem queries |
| Audit | Entries queued for retry; operations that require audit confirmation may block | Varies by operation criticality |

Cross-subsystem effects (application approval → roster entry) handle downstream failure by queuing the effect and surfacing the pending state to operators. The upstream operation completes; the downstream effect retries until the target subsystem recovers. Operators see the pending state and can intervene if recovery takes too long.

The audit subsystem is special: because reconstructable decisions are a design principle, operations that generate audit entries may block if audit storage is unavailable (to prevent decisions that cannot be reconstructed). This is a deliberate choice — audit integrity is more important than availability for consequential actions. Low-consequence automated transitions (e.g., scheduled compliance evaluation) may proceed with queued audit entries, but officer decisions (approvals, denials, escalations) wait for audit confirmation.

**Operator experience during audit unavailability:**

When audit storage is unavailable, officers attempting consequential actions (approve an application, escalate a ticket, change member status) receive an explicit error stating that the action cannot proceed because audit recording is unavailable, with the specific action and target identified. The system does not silently queue the officer's action or present it as successful — the officer knows the action did not execute and can retry when audit recovers. Pending automated transitions that proceeded with queued audit entries are surfaced in a degraded-state summary visible to operators with global authority, showing the count and type of operations awaiting audit confirmation.

**Recovery:** When audit storage recovers, queued entries from automated transitions are flushed in order. Each queued entry records the timestamp of the original operation and the timestamp of audit persistence, so the audit trail reflects that the entry was deferred. No officer-initiated operations are replayed automatically — the officer must re-initiate any action that was blocked. This prevents stale decisions: if an officer attempted to approve an application during audit downtime and conditions changed before recovery, the system does not execute an approval based on outdated context.

### Data Portability

All operational data is stored in the community's database in documented, queryable formats:

- Application records with full response data and review history
- Ticket transcripts with complete message and transition history
- Chapter configuration and lifecycle history
- Compliance rules, evidence, and evaluation records
- Permission intents and drift history
- Authority grants and succession chains
- Audit entries with full decision context

Export paths exist for all data categories. The data model is documented well enough that a replacement system could be built from the exported data without reverse-engineering. No critical operational data lives exclusively in Discord (messages, pins, reactions, channel topics) or in an external vendor's system.

---

## Constraint Acknowledgments

### External Evidence Reliability (§6)

The system cannot verify the authenticity of external evidence. OCR extracts data but cannot prove a screenshot is authentic, recent, or from the claimed game session. Fabrication by a motivated member cannot be systematically detected.

**What's lost:** The system cannot provide certainty that a member's compliance record reflects actual behavior. Compliance evaluation is only as reliable as the evidence it processes.

**Mitigation:** Evidence provenance is recorded (who submitted, when, from what source). Multiple evidence sources for the same event enable cross-validation. Statistical anomalies (evidence patterns inconsistent with a member's known activity) can be flagged. But the fundamental constraint remains: the system operates on submitted evidence, not observed reality. Communities must decide how much verification effort each rule warrants, and that decision is expressed in the rule's consequence level and review requirements.

### Discord Platform Dependency (§11)

The system depends on Discord for its interaction surface. During Discord outages, operators and members cannot interact with the system.

**What's lost:** Operational workflows are unavailable during Discord outages. Time-sensitive operations (pending applications, active ticket escalations) cannot proceed.

**Mitigation:** Durable state is preserved in the database. On reconnection, the system reconciles Discord state changes that occurred during downtime. No operational history is lost. But the system cannot provide an alternative interaction surface — this is an accepted constraint of the platform-native design commitment.

### Single-Community Scope (§8)

The system serves one community. Cross-community trust transfer, federation, and multi-server coordination are not supported.

**What's lost:** Communities that span multiple Discord servers must run separate instances with no shared state. Alliance-level operations that cross server boundaries cannot be managed in a single system. Trust built in one instance does not carry to another.

**Mitigation:** The system's data portability means that migration between instances is possible (export + import), but there is no live federation. This is a deliberate scope constraint: multi-tenant and federated architectures introduce data isolation, cross-server authority, and federated identity problems that would significantly increase system complexity without benefiting single-server communities.

### In-Game Identity Binding (§1)

The system cannot cryptographically verify the link between a Discord identity and a game identity. Game platforms generally do not expose identity verification APIs suitable for third-party guild management.

**What's lost:** Identity verification has a trust floor. The system relies on officer-verified identity claims and manual attestation. A sufficiently motivated actor can present a false game identity.

**Mitigation:** Identity claims are recorded as TrustSignals with explicit source attribution (which officer verified, when, based on what evidence). Multiple signals from different sources increase confidence. But verification is ultimately social, not cryptographic. The trust profile reflects this — officer-endorsed identity is a signal with weight, not a proof.
