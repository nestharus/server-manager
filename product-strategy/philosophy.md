# Product Philosophy

This document defines the principles and anti-goals that govern design decisions for the guild-management platform. Every design decision in the proposal must be traceable to one or more principles. When principles tension against each other, the tension must be surfaced and resolved — not silently resolved by the proposer.

---

## Principle 1: Operator Clarity

Operators — server administrators and chapter officers — must always understand what the system is doing, why it is doing it, and what will happen next. The system must never take action that an operator cannot explain to a member who asks.

Every automated action has a visible trigger and a logged reason. Every state transition is observable. Configuration options describe their effects in operational terms, not implementation terms. When the system makes a decision (routes a ticket, flags a member, transitions an application), the operator can reconstruct the full chain of cause and effect.

Anti-goal: "smart" defaults that silently override operator intent. The system may suggest; it must not presume.

---

## Principle 2: Live-Server Safety

A running community server is a live system with real members, active cases, and in-flight workflows. Changes to configuration, schema, or behavior must be safe to apply without disrupting ongoing operations.

No migration requires server downtime. No configuration change invalidates in-flight state. No update silently changes the meaning of existing data. When a destructive or irreversible action is requested, the system requires explicit confirmation and logs the decision.

Anti-goal: "just restart the bot" as an operational recovery path. If the system cannot apply a change safely, it must refuse and explain, not apply it and hope.

---

## Principle 3: No Compatibility Shims

The platform does not maintain backward compatibility with legacy bot configurations, stale Discord patterns, or deprecated platform features. When a Discord feature is superseded (e.g., welcome screens replaced by community onboarding), the system adopts the current mechanism and does not emulate the old one.

No import paths from old bot dashboards. No reaction-role emulation when onboarding exists. No adapters that translate between old and new models. When a clean break is the right answer, take it. Migration tooling may exist to help communities transition, but the operational system itself does not carry shim debt.

Anti-goal: building bridges that become permanent load-bearing structures. A shim that works today becomes tomorrow's unmaintained liability.

---

## Principle 4: Research Before Implementation

No subsystem is implemented before the problem it solves has been researched, the problem definition has been written, and the proposal has cleared alignment review. Understanding why a problem is hard precedes building a solution.

The project follows a phased pipeline (research → synthesis → proposal → review → implementation). Schema objects trace to researched problems. Mechanisms are justified by the difficulty they address, not copied from other bots or assumed from convention.

Anti-goal: "build it and see if it works" as a design methodology. The cost of building the wrong thing is higher than the cost of understanding the problem first.

---

## Principle 5: Low Lock-in

The system minimizes dependencies that are hard to exit. Operational data is stored in formats and systems the community controls. Configuration is portable. No critical workflow depends on a vendor whose disappearance would create an operational emergency.

Transcripts, application records, audit logs, and configuration are stored in the community's own database, not in external dashboards. Export paths exist for all critical data. The system's data model is documented well enough that a replacement system could be built from the stored data without reverse-engineering.

Anti-goal: convenience features that silently create vendor entanglement. Every external dependency must justify itself against the switching cost it introduces.

---

## Principle 6: Trust and Safety

The system handles sensitive operations: membership decisions, harassment reports, officer accountability, member privacy, and community governance. Design decisions must account for the possibility that any actor — including officers — may act in bad faith, make mistakes, or be compromised.

Sensitive actions require audit trails. Member-facing operations preserve privacy boundaries. Report workflows protect reporter identity from the accused. Officer actions within their scope are logged and reviewable by central staff. The system does not assume that elevated permissions imply trustworthiness.

Anti-goal: trust hierarchies where higher rank means less accountability. Accountability requirements increase with authority, not decrease.

---

## Principle 7: Delegated Authority with Accountability

Officers operate within defined scopes. A chapter officer manages their chapter — not other chapters, not server-wide configuration. Central staff retain override access and audit visibility across all scopes.

Authority is scoped, not ranked. An officer's actions within their scope are autonomous but recorded. Actions outside their scope are denied, not just discouraged. When an officer leaves, their successor inherits the scope and the history — the system does not lose operational context during transitions.

Anti-goal: "admin can do anything" as the only privilege model. Authority without boundaries is not delegation — it is abdication of governance.

---

## Principle 8: Platform-Native Interaction

The system works with Discord's interaction model, not against it. Workflows use Discord's current component capabilities (modals, selects, buttons, threads, forums) as they exist today, not as they existed in stale documentation.

Interaction design starts from current Discord component documentation, not from assumptions inherited from older bot frameworks. When Discord adds capabilities (new component types, richer modals, new channel types), the system can adopt them without architectural changes. When Discord removes or changes capabilities, the system adapts without breaking.

Anti-goal: building a parallel UI system that happens to render inside Discord. The system extends Discord; it does not replace it.

---

## Principle 9: Volunteer-Aware Design

Every mandatory human touchpoint is a cost paid in volunteer attention. The system must reduce the total attention cost of maintaining operational coherence, not increase it through process for its own sake.

Notifications are actionable, not informational. Review steps exist because the decision they gate has real consequences, not because "someone should look at this." Automation handles routine state transitions; human review is reserved for judgment calls. When a workflow can be completed without officer intervention, it should be — unless the community explicitly configures a review gate.

Anti-goal: mandatory approval workflows that exist because "we should have oversight" without a concrete risk they mitigate. Every gate must justify its attention cost.

---

## Principle 10: Durable State over Ephemeral State

Operational decisions are stored in the system's database, not in Discord messages, reactions, pinned posts, or channel topics. Discord is the interaction surface; the database is the source of truth.

Membership status, application history, ticket transcripts, activity records, and configuration live in persistent storage under the community's control. If a Discord channel is deleted, the operational state it represented is still queryable. If the bot reconnects after downtime, it can reconstruct its operational context from the database, not from channel history.

Anti-goal: "check the pins in #staff-chat" as an operational lookup. If it matters, it is in the database.

---

## Principle 11: Configuration by Operators, Not Developers

Operational configuration — chapter thresholds, form definitions, ticket categories, activity rules — is managed by operators through Discord commands or a web interface, not by editing config files, environment variables, or code.

Adding a chapter, changing an activity threshold, or modifying an application form does not require a code deployment. Configuration changes are logged, take effect without restart, and are reversible. The system's behavior is a function of its stored configuration, not its source code.

Anti-goal: "edit the config file and restart" as a workflow for operational changes. Operators should never need to touch the codebase.

---

## Principle 12: Graceful Degradation

If a subsystem fails or an external dependency is unavailable, unrelated subsystems continue operating. A ticket system outage does not block application processing. An OCR backend failure does not prevent chapter management.

Subsystems are peers, not a chain. Failure in one subsystem produces a clear error for operations that depend on it, but does not cascade. The system surfaces degraded state to operators rather than silently dropping functionality.

Anti-goal: monolithic coupling where a single failure mode brings down all community operations. Each subsystem must be independently resilient.

---

## Principle Interactions

Principles reinforce each other in predictable ways:

- **1 + 6**: Operator clarity supports trust and safety — when operators understand what the system does, they can verify it is doing the right thing for member safety.
- **2 + 12**: Live-server safety and graceful degradation both serve operational continuity — changes must be safe, and failures must be contained.
- **5 + 10**: Low lock-in and durable state both ensure the community owns its operational history — data is portable because it is stored in a controlled, durable format.
- **7 + 6**: Delegated authority with accountability directly serves trust and safety — scoped authority with audit trails prevents both over-centralization and unchecked power.
- **9 + 11**: Volunteer-aware design and operator configuration both reduce the human cost of running the system — automation handles routine work, and configuration changes don't require developer involvement.
- **3 + 8**: No compatibility shims and platform-native interaction both prevent technical debt accumulation — the system stays current rather than maintaining bridges to deprecated patterns.
- **4 + 1**: Research before implementation supports operator clarity — when the problem is understood first, the resulting system is explainable because its design traces to real difficulties.

---

## Principle Tensions

Some principles can pull in different directions in specific contexts:

- **1 vs 9**: Operator clarity (make everything visible) can conflict with volunteer-aware design (don't overwhelm with notifications). Resolution: visibility is available on demand, not pushed by default. Operators can inspect any state, but notifications are reserved for states requiring action.
- **2 vs 3**: Live-server safety (don't break running systems) can conflict with no compatibility shims (don't maintain old patterns). Resolution: migration tooling makes the transition safe, but the system does not maintain the old path indefinitely. Safe doesn't mean permanent.
- **7 vs 9**: Delegated authority (require scoped approval) can conflict with volunteer-aware design (minimize approval gates). Resolution: delegation reduces total approval load by distributing it — officers approve within their scope without central bottleneck, reducing both individual and aggregate attention cost.
- **6 vs 9**: Trust and safety (audit everything, require review) can conflict with volunteer-aware design (minimize friction). Resolution: the level of review scales with the severity of the action. Low-risk state transitions (e.g., routine activity flagging) are automated; high-risk decisions (e.g., membership denial, officer removal) require human judgment.
- **6 vs 12**: Trust and safety (audit trails for consequential actions) can conflict with graceful degradation (subsystem failure doesn't cascade). Resolution: audit enforcement scales with action severity. Consequential decisions — approvals, denials, escalations — block when audit storage is unavailable rather than proceed unrecorded. Routine automated transitions proceed with deferred audit entries, tolerating temporary audit unavailability without cascading the outage.

---

## Anti-goals

These are things the system explicitly does not pursue:

- **General-purpose bot framework.** The system is a guild-management platform, not a toolkit for building arbitrary Discord bots.
- **Multi-tenant SaaS.** The system serves one community. Multi-server or multi-tenant architecture is not a design goal.
- **Moderation-first design.** The system supports moderation workflows, but it is not a moderation bot. The primary focus is operational management: intake, provisioning, tracking, and governance.
- **Feature parity with existing bots.** The system does not attempt to replicate every feature of every bot it replaces. It addresses the underlying operational problems; some bot features may have no equivalent because they addressed symptoms rather than causes.
- **AI-driven decision-making.** The system may use AI for extraction (OCR, parsing), but operational decisions (approve, deny, flag, promote) are made by humans with the system providing information, not recommendations.

---

## Expansion Guidance

When the proposal encounters a problem surface not covered by these principles:

1. Check whether the surface is addressed by combining existing principles. Many specific design questions are resolved by applying two or three principles together.
2. If no combination of existing principles addresses the surface, identify the implicit principle and surface it through the philosophy alignment review process.
3. New principles are added through the expansion process, not by the proposer. The proposer flags the gap; the expansion agent evaluates whether the philosophy should grow.
