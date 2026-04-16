# Product Problem Definition

This document defines the problem space for a guild-management platform that replaces brittle third-party Discord bot dependencies with a unified operational system for long-lived gaming communities, alliance servers, and multi-chapter organizations.

The problems described here are not feature requests. Each section describes a core difficulty — why the problem is hard and resists solution — and the operational consequences of leaving it unaddressed. The platform must remain game-agnostic and should support future stakeholder-facing product definition beyond the initial operator workflows.

---

## §1 Trust Calibration and Identity Verification

The underlying problem is deciding who should be trusted with what, not welcome messaging. Communities need to determine who may see what, when a newcomer becomes eligible for participation, and how much manual review is worth spending on low-trust arrivals.

Discord's built-in verification levels and rules screening handle coarse anti-spam filtering, but guild-style communities need identity, roster, faction, platform, or chapter-fit checks that are social and operational. Trust is not binary (verified / unverified) — it is a gradient that changes over time as members demonstrate reliability, and it varies by context: a trusted member in one chapter may be unknown in another.

The difficulty is not collecting trust signals — it is calibrating and maintaining them across organizational boundaries, staff turnover, and time, without either over-trusting (security failure) or over-gatekeeping (community death).

---

## §2 Structured Intake and Adjudication

The problem is adjudication under limited staff time, not form construction. Applications are a mechanism to standardize who gets admitted, promoted, or assigned to a subgroup while making decisions reviewable by more than one officer.

Discord's built-in server member applications cover server-level join gating but are narrow: no image uploads, no application history, no reviewer notes, no waitlists, no chapter-specific routing. Communities that need structured intake for chapter membership, officer candidacy, or specialized roles outgrow the built-in model quickly.

The core difficulty is that intake is not a single decision point — it is a lifecycle. An application may be pending, claimed by a reviewer, in interview, waitlisted, approved, denied, or withdrawn. Each transition requires the right person to see the right context at the right time. When staff time is scarce, applications that require manual review compete for the same attention as every other operational task.

When multiple officers have authority over the same intake queue, concurrent access introduces a mutual-exclusion problem. Two reviewers may independently begin evaluating the same application without knowing the other has started — duplicating scarce staff effort. If they reach different conclusions, the conflict itself requires officer attention to resolve. This collision risk connects directly to volunteer burnout (§9): every duplicated review or conflicting decision is attention spent on coordination overhead rather than adjudication.

---

## §3 Case Routing and State Management

A "ticket" is a private case that may need triage, reassignment, escalation, transcripts, and closure rules. Gaming communities use tickets for appeals, harassment reports, recruitment issues, chapter disputes, account linking, and officer requests.

Discord has no native end-to-end ticket system. The platform's own safety guidance frames this as a bot-mediated workflow because staff need private conversations, coordination, and logs. The operational need is not "open a channel" — it is ensuring the right humans see the right case, with enough context, without collisions, and with a durable record of what happened.

The core difficulty is state management across a case's lifetime. A ticket is not a message thread — it has an owner, a status, a category, a history of who touched it, and potentially a relationship to other operational objects (an application, a chapter, a member record). When ticket state lives in a third-party dashboard, the community's operational continuity depends on that vendor's availability and data model.

---

## §4 Audit Trail and Long-term Accountability

The deeper problem is proving what happened after the fact. Staff teams need to know who approved an applicant, who changed a role, whether a punishment followed policy, and whether one officer overrode another.

Discord's server audit log has a 45-day retention cap, which is too short for seasonal guild operations, officer misconduct reviews, or disputes that resurface months later. Third-party bots fill the gap with transcripts and logs, but then retention becomes a commercial or operational policy owned by someone else.

The core difficulty is not logging — it is reconstructability. A complete audit trail means any past decision can be examined with its full context: who decided, what inputs they had, what alternatives existed, and what policy governed the decision. This requires durable storage under the community's control, not a vendor's retention policy.

When reconstructability is enforced as a hard invariant rather than a best-effort goal, audit storage availability becomes a precondition for consequential operations. An officer approval, denial, or escalation that cannot be recorded cannot proceed — an audit outage becomes an operational outage for every decision that requires accountability. The system must either accept that audit failures block operations (sacrificing availability for integrity) or allow operations to proceed without audit (sacrificing the reconstructability the system was built to provide). This tension does not exist in the current state, where there is no audit trail to speak of, and only becomes visible when audit is elevated to a hard requirement.

---

## §5 Sub-community Provisioning and Lifecycle

The real problem is repeated creation, change, and retirement of semi-private organizational units within a single server. Multi-group communities need to spin up spaces for a new chapter, grant leaders local authority, manage rosters, and later archive or transfer ownership without breaking global governance.

Discord offers channels, categories, roles, and forums, but each new subgroup consumes scarce namespace (250 roles, 500 channels, 50 categories). Provisioning is not one action — it is a lifecycle with intake, activation, roster drift, inactivity, succession, and archival.

The core difficulty is that every subgroup created today increases future cleanup cost. Permissions are compositional, so the complexity of reasoning about who can see what grows combinatorially with the number of subgroups. And when a chapter's leader leaves, the succession problem is not just "transfer a role" — it is "transfer operational context, pending decisions, and member trust without a gap in governance."

---

## §6 Activity Tracking and Compliance Enforcement

The problem is enforcing rules that are external to Discord's native activity metrics. Gaming groups care about in-game event attendance, response time, rank requirements, chapter minimums, or "inactive until reviewed" states. Discord exposes Discord-side activity signals, but cannot express business rules like "member is compliant for this chapter but not that one" or "member missed two required events and should enter review."

Communities fall back to spreadsheets, manual tags, and bot-driven status roles. The daily cost is officer time spent on data entry, cross-referencing, and threshold checks — work that is repetitive, error-prone, and a primary source of volunteer burnout.

The core difficulty is that compliance criteria are per-chapter, per-game, and per-season. The system must ingest evidence from outside Discord (screenshots, game APIs, manual reports), apply configurable rules, and surface violations to the right officers — without the system itself becoming another manual data-entry burden.

---

## §7 Permission Model and State Explosion

The actual problem is managing access in a system that composes it from roles plus channel overwrites. Discord's permission model is powerful but complexity compounds when many roles overlap, and every urgent exception during a crisis becomes tomorrow's inherited baseline.

A multi-chapter server with officer tiers, special squads, archive spaces, bot roles, and temporary campaigns pushes against Discord's caps and creates permission configurations that no single person can fully reason about. "Permission drift" is not a bug in one permission bit — it is accumulated unreviewed history.

The core difficulty is that Discord provides tools to set permissions but no tools to reason about the aggregate effect of accumulated permission decisions over time. There is no native concept of "intended permission state" against which actual state can be audited, and no mechanism to detect when a temporary override has become permanent.

This single-phenomenon description understates the difficulty. When an "intended permission state" is introduced, permission discrepancies split into two distinct categories that require fundamentally different operational responses. Permissions that have diverged from a declared intent have a clear resolution path: compare actual state to intended state and correct the discrepancy. But permissions that were set directly in Discord without any corresponding intent have no resolution path at all — the operator must first determine whether the permission should exist, then either create an intent to formalize it or remove it.

The migration challenge is itself significant. Any community that adopts a declared-intent model inherits the full history of unmanaged permission decisions. These existing permissions must be individually classified and brought into the managed set before the system can provide complete coverage. Until that migration completes, the community operates in a hybrid state where some permissions are managed and others are not — and the boundary between the two must be visible to operators or it becomes a new source of confusion.

---

## §8 Vendor Lock-in, Migration, and Data Portability

The real problem is operational dependence on external systems with different data models, dashboards, and failure modes. Communities accumulate bots — one for tickets, one for applications, one for moderation logs, one for reaction roles — each adding another role, another permission surface, and another place where critical records may live.

When a service is abandoned, reworked, rate-limited, or paywalled, the guild must migrate during an active operational workload. Migration is painful because communities are not just moving configuration — they are moving open cases, transcripts, permissions, staff habits, and policy assumptions. If the old and new systems do not share a model, migration is partly organizational retraining.

The core difficulty is that the switching cost is invisible until it becomes urgent. Lock-in accumulates gradually as workflows, muscle memory, and data accrete in a vendor's system. By the time the vendor disappears, the community's operational continuity depends on an export path that may not exist.

---

## §9 Volunteer Coordination and Staff Burnout

Most operational workflows in gaming communities are run by volunteers. Ticket queues, application review, roster cleanup, and appeal handling all compete for the same officer attention. Burnout shows up when the system requires constant human arbitration to stay coherent.

The core difficulty is that adding process (more review steps, more approval gates, more notifications) makes governance more rigorous but also accelerates burnout. The system must reduce the total attention cost of maintaining operational coherence, not just redistribute it. Every mandatory human touchpoint is a cost that must justify itself against the risk of not having it.

Notification volume is a distinct burnout mechanism from process rigor. A system can have well-justified mandatory touchpoints — every human decision earns its attention cost — and still overwhelm officers through informational notifications about downstream effects of decisions already made. When a single officer action triggers a cascade of operational consequences — roster updates, compliance re-evaluations, permission changes — each consequence may independently notify affected officers. From the officer's perspective, these are all one event; from the system's perspective, they are independent state changes. The officer who approved an application does not need three separate notifications that the approval triggered a roster addition, a compliance activation, and a permission grant. Reducing mandatory decision touchpoints does not solve this problem — notification volume from automated cascades is an attention cost that exists independently of how many decisions require human involvement.

---

## §10 Delegated Authority and Governance

The central tension is bounded delegation. Chapter officers need to recruit, manage local spaces, and resolve routine issues without waiting on global admins. Central staff still need emergency override, audit visibility, and consistency enforcement.

Discord's hierarchy model supports "higher roles can manage lower roles," but that is not the same as scoped authority. It often pushes communities toward either over-centralization (every action needs admin approval) or over-granting (officers have more access than they need because the permission model can't express "only within your chapter").

The core difficulty is that governance requires both local autonomy and central accountability, and Discord's role hierarchy expresses authority as a global rank, not as a scoped delegation. There is no native way to say "this officer can manage these channels and these members, but not those."

---

## §11 Platform Constraints and Moving-Target Risk

Discord's platform capabilities change without notice. Features are deprecated, new features replace old ones, caps shift, and API behavior evolves. Communities that build operational workflows on platform assumptions must absorb these changes without service interruption.

The core difficulty is designing against a substrate that moves. Any system built on Discord must treat platform constraints as external facts that may change, not as stable foundations. Assumptions about modals, threads, permissions, components, or audit log behavior must be verified rather than inherited from stale documentation or community lore.

---

## §12 Cross-workflow State and Operational Continuity

Across all operational domains, the recurring issue is that decisions span multiple subsystems but state is fragmented. An application leads to a membership decision that affects chapter rosters, which affects activity tracking, which may trigger a ticket. These relationships exist in the community's operational logic but not in any single bot or built-in feature.

The core difficulty is not building individual subsystems — it is maintaining coherent state across their boundaries. When application data lives in one bot, ticket data in another, and roster data in a spreadsheet, no single system can answer "what is this member's full operational history?" Operational continuity requires that cross-subsystem relationships are first-class, not reconstructed by officers from memory.

---

## §13 Live Configuration Safety and Temporal Integrity

Communities change their operational rules while operations are in progress. Application forms are updated mid-review cycle, compliance thresholds are adjusted while evaluations are running, ticket routing is modified while cases are open, and authority templates shift as staff availability changes. These changes are routine and necessary — communities learn and adapt continuously.

The core difficulty is that a configuration change on a live system can silently corrupt the semantic integrity of in-flight operations. When an application form's fields change while submissions are pending review, the submitted responses may no longer correspond to the questions that were asked. When compliance rules change mid-season, evaluations that already ran correctly under the old parameters become inconsistent with evaluations that haven't run yet. The operation didn't fail — its meaning changed underneath it.

This is not a versioning problem in the storage sense. It is an operational safety problem: ensuring that work begun under one set of rules completes under those same rules, while new work begins under the updated rules. The difficulty is compounded by the fact that configuration changes are not isolated — a single policy update may affect multiple subsystems simultaneously, and the set of in-flight operations affected is not obvious until the change is attempted.

Configuration changes can also corrupt other configuration changes, not only in-flight operations. When multiple operators have authority over the same policy domain, concurrent modifications introduce a decision-integrity problem distinct from the in-flight operation problem. An operator who previews the effect of a proposed change, deliberates, and then confirms the change is making a governance decision — but the state they deliberated against may no longer be current if another operator confirmed a different change in the interval. The second operator's decision was informed by a state that no longer exists, and the confirmed change may have consequences the operator did not evaluate. Unlike the in-flight operation problem — where the affected entity is work proceeding under configuration — the affected entity here is the configuration itself, and the failure mode is a governance decision made against a phantom state. This is especially dangerous because the change succeeds silently: there is no error, no corruption of running operations, just an operator who believed they were modifying one policy state when they were actually modifying a different one.

---

## §14 Consolidated Failure Risk and Operational Availability

When operational state is fragmented across many independent systems, a single system's failure affects only its domain — a ticket bot outage doesn't stop application review, and an application bot outage doesn't stop compliance tracking. Each failure is contained because the systems share nothing.

Consolidation solves the fragmentation problem (§8, §12) but inverts the failure model. When all operational subsystems — intake, cases, compliance, permissions, audit, governance — share a platform, a platform-level failure (database outage, deployment failure, hosting disruption) can take down every operational workflow simultaneously. The blast radius of any single failure expands from one domain to all domains.

The core difficulty is that consolidation and failure isolation pull in opposite directions. A unified system provides cross-workflow coherence (§12) and eliminates vendor fragmentation (§8), but achieving that coherence means subsystems share infrastructure, state dependencies, or both. The system must maintain meaningful operational independence between subsystems even though they share a platform — so that an outage in one domain does not cascade into a total operational shutdown.

The consolidation-isolation tension has a second dimension beyond shared infrastructure: data coupling. Cross-workflow coherence (§12) requires that relationships between subsystems are first-class — an application approval that triggers a roster entry must maintain that causal link. But making these relationships first-class through shared data contracts means that subsystem schemas become interdependent. Schema evolution in one subsystem may invalidate queries or references in others, and replacing a subsystem requires migrating every cross-boundary relationship that other subsystems depend on. This is not a failure-propagation risk — both subsystems may be running perfectly — it is a change-propagation risk. The more tightly subsystem data is linked to achieve the coherence that §12 requires, the more difficult it becomes to evolve, replace, or independently maintain any single subsystem. The independence that this section requires is not only about surviving outages in isolation but about changing in isolation — and coherence-through-coupling makes both harder.
