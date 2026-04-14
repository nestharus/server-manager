# Product Philosophy

These principles govern how this system thinks about problems and makes design decisions. They are not a description of what to build. They are constraints on how to think about building.

Every principle is derived from the problem definition and the concrete realities of Humility's operating environment: a live Discord server, a single administrator, fragmented state across a dozen tools, and real community members whose experience changes immediately when the system acts.

## Principles

### Principle 1 — Live System, Real Consequences

The system operates on a live Discord server with real users. Every action that changes something visible to members must be safe by default: confirmable before execution and reversible after it. When safety and speed conflict, safety wins.

**Because:** A mistake in this system is not a failed test. It is a real person seeing wrong information, losing access to a channel, or receiving a notification they should not have received. The cost of a visible error in a small community is disproportionately high because everyone notices.

**Applies when:** Any feature creates, modifies, or deletes something visible to server members. Any automation that acts without a human in the loop for a specific execution.

### Principle 2 — Reduce the Operator's Burden

Every feature must decrease the total operational work required to run the server. If a feature requires ongoing attention to function correctly — manual syncs, periodic cleanups, configuration babysitting — it has shifted burden rather than reduced it. The measure is not whether the feature is useful in the moment, but whether it creates net time savings over its lifetime.

**Because:** Humility has one administrator. The system exists to make their life sustainable. A sophisticated dashboard that requires daily feeding is worse than a crude tool that runs unattended. The operator's scarcest resource is attention, not capability.

**Applies when:** Evaluating whether a feature genuinely reduces work or merely changes its shape. Any feature that introduces a new recurring obligation for the admin or officers.

### Principle 3 — Bounded Delegation

Officers receive real authority within explicit, system-enforced scope. Delegation is safe because the system prevents actions outside the boundary, not because people are trusted to self-limit. The boundary is structural, not social.

**Because:** Officers are also players, friends, and community members. Interpersonal dynamics, burnout, and turnover mean that relying on social trust alone for scoping authority is fragile. Discord's native permission model can grant "too much" accidentally because roles are global and hierarchy is coarse. The system must make partial authority a first-class design concept.

**Applies when:** Any feature grants a non-admin user power to change state. Any design decision about what officers can see, modify, or approve within their chapter versus server-wide.

### Principle 4 — Cross-System Truth

No single source owns all truth. State lives in Discord (roles, channels, permissions), the database (applications, transcripts, activity logs), external games (rosters, scores, guild membership), and human memory (context, exceptions, intent). The system must handle the reality that these sources can disagree, and must make divergence visible rather than silently picking a winner.

**Because:** A Discord role says someone is a Chapter Member. The game roster says they left the guild last week. The activity spreadsheet says they were active yesterday. These are not bugs — they are the inherent state of a system that spans platforms with no shared transaction boundary. Pretending one source is canonical creates silent lies.

**Applies when:** Any feature that reads or writes state that also exists in another system. Any feature that must reconcile Discord state with database state or game state.

### Principle 5 — Temporal Honesty

The system represents time explicitly. Membership, activity, chapter status, officer assignments, and configuration all change. The system records when things happened, when they were valid, and when they ended. Current state and historical fact are distinct and must not be conflated.

**Because:** Gaming communities are temporal systems. Games rotate, members go inactive, chapters rise and collapse, seasons reset. A system that stores only current state will accumulate phantom members, ghost chapters, and stale configurations that no one can safely clean up because no one knows when they became obsolete. Humility's existing server already shows layers of historical configuration spanning 2022-2026 with unclear validity.

**Applies when:** Any feature that stores state which changes over time. Any query that needs to distinguish "is now" from "was once." Any feature dealing with lifecycle transitions (chapter creation, archival, member departure, officer rotation).

### Principle 6 — Traceable Actions

When the system changes state, it records what changed, who caused it (human or automated), what the prior state was, and when. For actions with significant consequences — role changes, application decisions, moderation actions — the record includes the reason or triggering event. The audit trail is a first-class data structure, not a log file.

**Because:** In a community, "who did that and why?" is a routine question with real stakes. Disputes about application decisions, role changes, and moderation actions cannot be resolved if the system does not remember what happened. Humility already suffers from actions that are untraceable because they were performed through bot dashboards, DMs, or manual role edits that left no durable record inside the server.

**Applies when:** Any feature that creates, modifies, or deletes persistent state. Any automated action that changes something a human will later need to understand or audit.

### Principle 7 — Evidence Over Inference

When the system derives data — OCR from screenshots, activity scores from raw observations, membership status from role state — it preserves the evidence alongside the conclusion. Derived facts carry their source, the method of derivation, and confidence level when applicable. A conclusion without accessible evidence is an assertion, not a finding.

**Because:** Disputes are settled by evidence, not by system authority. "The system says you scored 40 points" is not persuasive if the member cannot see the screenshot, the OCR output, and the matching logic that produced that number. In a small community, legitimacy depends on members believing the system's conclusions are checkable, not just that they are produced by software.

**Applies when:** Any feature that extracts, computes, or infers state from raw inputs. Any feature where the system's output could be disputed by a member or officer. OCR, activity calculations, role-based status derivations, and automated flagging.

### Principle 8 — Human Authority Over Outcomes

The system prepares, presents, and executes, but does not decide. For membership, moderation, governance, and appeals, a human makes the final call. The system may recommend, flag, or surface information, but it does not resolve judgment calls autonomously.

**Because:** The important decisions in a community — whether to admit someone, how to handle a conflict, when to archive a chapter, whether an exception is warranted — require context, empathy, and political judgment that the system cannot possess. Automating these outcomes does not reduce burden; it creates a system that makes decisions the community does not trust and the admin cannot explain.

**Applies when:** Any feature that could resolve a judgment call (accept/deny, warn/ban, flag/ignore) without human input. Any workflow where the system's recommendation could be mistaken for the system's decision.

### Principle 9 — Consolidate Operational Truth

The system should be the single place operators go to understand what is happening across applications, tickets, chapters, and activity. It should consolidate operational state that is currently scattered across bot dashboards, spreadsheets, DMs, and human memory. It must not become another silo alongside the existing fragmentation.

**Because:** Humility's current operational state is spread across 12 bots, external spreadsheets, stale embeds, and the admin's memory. Each tool owns one slice of reality. No tool owns the whole picture. The system's value is not in being a better version of one tool — it is in being the one place where the operational picture is complete. Adding a 13th partial source would make the problem worse.

**Applies when:** Any feature that introduces new state storage. Any design choice about where operational data lives and how operators access it. Any feature that could fragment the operational picture by creating its own silo.

### Principle 10 — Legibility Over Cleverness

The system's state and behavior must be inspectable by the people who use it. When choosing between a more efficient approach that hides state and a simpler approach that makes state visible, choose the simpler approach. Operators must be able to answer "what is the system doing and why?" without reading code.

**Because:** The admin and officers need to trust the system enough to let it manage real operations. Trust requires understanding. A system that produces correct outputs through opaque logic is one debugging session away from being distrusted and abandoned. Humility already suffers from opaque bot state — embed panels that imply workflow without exposing it. The replacement must not repeat this pattern.

**Applies when:** Any design choice between efficiency and transparency. Any feature that maintains internal state operators need to understand. UI and reporting decisions where information density competes with clarity.

### Principle 11 — Right-Sized Design

This is ~88 members, not enterprise infrastructure. But "small" does not mean "simple" — the operational problems are real, the cross-system state is genuinely complex, and the admin is genuinely overloaded. Design for the actual scale: solve the real complexity without imposing overhead that only pays off at scales this community will never reach.

**Because:** Enterprise patterns — complex RBAC matrices, multi-tenant isolation, horizontal scaling, eventual consistency trade-offs — impose cognitive and maintenance costs that are only justified at enterprise scale. But dismissing the problems as "too small to matter" ignores that the admin is drowning in manual work right now. The correct level of design sophistication is the one that solves the actual problems at the actual scale.

**Applies when:** Evaluating technology choices, abstraction levels, and design patterns. Any decision where the complexity of the solution could outweigh the complexity of the problem.

### Principle 12 — Graceful Decay

The system should detect, represent, and surface decay rather than ignoring it. When chapters go dormant, members go inactive, configurations go stale, or integrations stop responding, the system should make that visible to operators. Decay is not an error condition — it is a normal state that the system must handle explicitly.

**Because:** Discord accumulates structure and never tells you when it becomes obsolete. Humility's existing server contains layers of scaffolding from 2022 through 2026, and no one can say with confidence which pieces are active policy, which are historical record, and which are abandoned. A management system that creates persistent structures (chapters, configurations, workflows) without tracking their vitality will reproduce exactly this problem.

**Applies when:** Any feature that creates persistent structure — chapters, roles, configurations, recurring workflows — that could become stale. Any feature that needs to distinguish "inactive" from "broken" from "not yet started."

## Principle Interactions

### Principle 2 (Reduce Burden) and Principle 3 (Bounded Delegation)

**Tension:** Making delegation safe requires building and maintaining boundaries — scope definitions, permission models, escalation paths. That is itself work for the admin. If the delegation system is too complex to configure, it adds burden rather than reducing it.

**Guidance:** The system provides sensible defaults for delegation boundaries that match Humility's actual structure (chapter officers manage their chapter, staff manages cross-chapter concerns, admin manages everything). The admin only configures boundaries when the defaults do not fit. Delegation should reduce total work from day one, not after a setup phase.

### Principle 2 (Reduce Burden) and Principle 8 (Human Authority)

**Tension:** If every consequential decision requires a human, the admin gets overloaded — which is the exact problem the system is supposed to solve. But if the system makes decisions autonomously, it undermines human authority and community trust.

**Guidance:** The system automates preparation, not judgment. It gathers evidence, presents options, surfaces flags, and executes the human's decision. The goal is to reduce the time and effort per decision (from "dig through three systems and a spreadsheet" to "review a summary and click approve"), not to eliminate the human from the decision. Volume reduction comes from delegation (Principle 3), not from automation replacing judgment.

### Principle 4 (Cross-System Truth) and Principle 9 (Consolidate Truth)

**Tension:** The system should be the single operational truth, but it cannot actually own all truth because some state lives in Discord, games, and external services that the system does not control. Full consolidation is impossible when truth is inherently distributed.

**Guidance:** The system is the authoritative record of decisions and derived state: who was approved, what the activity score was, when a chapter was archived. It is not the authoritative source of Discord's live role state or a game's current roster. When it observes external state, it records the observation with a timestamp, not a claim of permanent truth. Consolidation means "one place to look for the operational picture," not "one system that owns all underlying state."

### Principle 5 (Temporal Honesty) and Principle 10 (Legibility)

**Tension:** Full temporal state — every version of every record, complete history of every transition — creates information overload. Operators who need to see "what is true now" should not have to wade through years of history to find it.

**Guidance:** Current state is the default view. History is accessible on demand, not in the way. The system shows "this member is active in Chapter X" by default, and offers "show me the full membership history for this member" as a drill-down. Temporal honesty is about what the system stores and can answer, not about what it puts in front of operators unprompted.

### Principle 7 (Evidence Over Inference) and Principle 10 (Legibility)

**Tension:** Carrying full evidence for every derived fact creates noise. If every activity score shows the raw screenshot, OCR output, matching logic, and confidence score inline, the officer's review screen becomes unusable.

**Guidance:** The default view shows the conclusion. Evidence is stored and one interaction away — accessible but not displayed unless requested. The principle requires that evidence exists and is reachable, not that it is always visible. Think of it as an audit layer beneath the operational layer.

### Principle 3 (Bounded Delegation) and Principle 8 (Human Authority)

**Reinforcement:** These principles reinforce each other. Bounded delegation defines what an officer can do within their scope. Human authority ensures that the system does not replace the officer's judgment within that scope — it supports it. Together, they mean: officers have real power within their boundary, and within that boundary, the system helps them decide rather than deciding for them.

**Edge case:** When an officer encounters a situation that exceeds their boundary (a cross-chapter dispute, a server-level concern), the system should provide a clear escalation path rather than silently blocking the action. Escalation is how bounded delegation and human authority coexist at the boundary.

### Principle 1 (Live System) and Principle 6 (Traceable Actions)

**Reinforcement:** On a live system, traceability is not just an audit feature — it is a safety mechanism. If an action can be traced, it can be understood. If it can be understood, it can be reversed or corrected. Traceability makes the live system safer to operate.

### Principle 12 (Graceful Decay) and Principle 5 (Temporal Honesty)

**Reinforcement:** Temporal honesty provides the data that makes graceful decay possible. If the system records when things happened and when they were last active, it can surface decay automatically. Without temporal data, decay detection would require manual inspection — which returns to the burden the system is supposed to eliminate.

## Expansion Guidance

When the system encounters new problem surfaces not yet covered by the problem definition, apply these principles as follows:

**Start with Principle 1.** Any new capability that touches the live server must respect safety defaults. If the new surface involves visible actions, it inherits the confirmability and reversibility requirements.

**Check against Principle 2.** Does the new capability reduce total operational burden? If it introduces new recurring obligations without eliminating existing ones, it is adding burden regardless of how useful it seems in isolation.

**Apply Principle 8 conservatively.** New capabilities are tempted to automate decisions because automation feels like progress. For any new surface where the system could decide autonomously, ask: would the community accept this decision from software? If the answer is not clearly yes, the system should present and let a human decide.

**Use Principle 9 as a litmus test.** If a new capability would introduce state that lives outside the system's consolidated operational picture, that is a design smell. The new capability should integrate into the existing operational view, not create a satellite.

**Apply Principle 11 as a brake.** New surfaces will tempt sophisticated solutions. Check whether the actual scale and frequency of the problem justify the complexity. A problem that occurs twice a month does not need real-time streaming infrastructure.

**Watch for Principle 4 implications.** New surfaces often involve new external systems (new games, new bots, new APIs). Each new external system is a new source of truth that can disagree with the database. The system's approach to that new source should match how it handles existing cross-system truth: observe, record with timestamps, surface divergence, do not pretend to own the external state.

**When principles conflict on the new surface,** use the interaction guidance above to navigate. If the conflict is novel — not covered by existing interaction guidance — that is a signal that the philosophy may need a new interaction entry, not that the principles should be overridden.
