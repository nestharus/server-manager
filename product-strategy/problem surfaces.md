# Problem Surfaces

New problem surfaces discovered during the problem alignment review. These are gaps in the problem definition, not problems with the proposal.

---

## Proposal-originated Surfaces

### Single-system consolidation introduces unified failure risk

- **What the proposal does:** Consolidates all operational subsystems (intake, cases, compliance, permissions, audit, governance) into a single platform with subsystem independence and graceful degradation mechanisms.
- **What problem it addresses:** When all operational state lives in one system, a system-level failure (database outage, deployment failure, hosting disruption) could take down all operational workflows simultaneously — unlike the current fragmented bot architecture where individual bot failures affect only their specific domain.
- **Why it's not in the problem definition:** The problem definition describes the fragmentation of operational state across vendor systems (§8) and the dependency on individual vendors (§8, §11), but does not describe the inverse risk: that consolidation creates a single point of failure for the entire operational stack.
- **Evidence it's real:** The proposal itself dedicates a substantial section (Graceful Degradation) to this concern, designing explicit failure boundaries between subsystems, defining what remains operational during partial failures, and specifying differential availability guarantees (audit may block consequential actions while low-consequence automation proceeds). The engineering investment in failure isolation indicates this is a genuine architectural concern, not a hypothetical.

---

## Emergent Surfaces

### §4 — Audit integrity creates an availability cost

- **Axis:** Audit Trail and Long-term Accountability (§4)
- **What the problem definition says:** Reconstructability requires durable storage under community control. Past decisions must be examinable with full context: who decided, what inputs they had, what alternatives existed, and what policy governed the decision.
- **What the proposal reveals:** When reconstructability is enforced as a hard invariant, audit storage availability becomes a precondition for consequential operations. Officer decisions (approvals, denials, escalations) block when audit is unavailable. The audit subsystem's reliability directly constrains the community's ability to operate — an audit outage becomes an operational outage for all decisions that require accountability.
- **Why it matters:** The problem definition describes audit entirely as a missing capability. It does not articulate that achieving full reconstructability introduces a new operational cost: the system must either accept that audit failures block operations (sacrificing availability for integrity) or allow operations to proceed without audit (sacrificing the reconstructability the system was built to provide). This tension does not exist in the current state — where there is no audit trail to speak of — and only becomes visible when audit is elevated to a hard requirement.

### §2 — Concurrent reviewer access creates collision risk

- **Axis:** Structured Intake and Adjudication (§2)
- **What the problem definition says:** Intake is a lifecycle where each transition requires the right person to see the right context at the right time. Staff time is scarce and applications compete for attention with every other operational task.
- **What the proposal reveals:** When multiple reviewers have authority over the same intake queue, concurrent access to pending applications creates a collision risk: two officers may independently begin reviewing the same application without knowing the other has started. This wastes scarce staff time (two officers doing the same work) and, if they reach different conclusions, creates a resolution conflict that itself requires officer attention.
- **Why it matters:** The problem definition's treatment of §2 focuses on the lifecycle nature of intake and the context required for good decisions. It does not articulate that shared reviewer queues introduce a mutual-exclusion problem — a sub-problem that connects directly to §9 (volunteer burnout) by wasting officer time on duplicated or conflicting review work. Without this framing, a solution could correctly implement the intake lifecycle but still fail to prevent the attention waste that shared queues create.
