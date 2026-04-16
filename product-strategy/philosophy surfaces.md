# Philosophy Surfaces

New philosophical concerns discovered during the Stage 2 philosophy alignment review. These are inputs for the philosophy expansion agent — they describe concerns the current philosophy does not fully address.

---

## Implicit Principles

### Time-bound obligation enforcement

**Axis:** 3 (Case Routing and State Management)

**Design decision:** TicketCategory includes `sla_rules: jsonb?` described as "time-based escalation thresholds" — a configuration field that asserts the system monitors elapsed time against configured deadlines and acts when thresholds are breached.

**Implicit principle:** "Time-bound operational obligations should be system-monitored, with configurable graduated consequences for elapsed-time violations." The system treats elapsed time as observable evidence (analogous to activity evidence in compliance), applies configurable rules to it, and triggers proportional responses when thresholds are crossed.

**Relationship to existing principles:** Extends P13 (Derived State Transparency) and P14 (Graduated Consequence) into the temporal dimension. P13 governs how operational state is derived from observable evidence — elapsed time is evidence. P14 governs proportional responses — SLA breach responses should be graduated. But neither principle explicitly addresses active deadline monitoring as a system responsibility. The implicit principle also intersects with P9 (Volunteer-Aware Design): automated deadline enforcement can either reduce officer attention cost (the system catches aging tickets before they become crises) or increase it (auto-escalation creates mandatory touchpoints). The balance depends on whether the consequence mechanism is operator-configurable.

**Strength of evidence:** Weak — only the `sla_rules` field follows this implicit principle. No other design decision in the proposal introduces time-based obligation enforcement. If the mechanism were fully specified, additional supporting decisions (graduated SLA thresholds, SLA-triggered notifications, SLA state in the ticket lifecycle) would likely reinforce the pattern.

---

## Principle Tensions

### P12 (Graceful Degradation) + P9 (Volunteer-Aware Design) vs P2 (Live-Server Safety) for deferred cross-subsystem effects

**Axis:** 12 (Cross-workflow State and Operational Continuity) and 14 (Consolidated Failure Risk and Operational Availability)

**Principles in tension:** Principle 12 (Graceful Degradation), Principle 9 (Volunteer-Aware Design), and Principle 2 (Live-Server Safety)

When a cross-subsystem effect fails because the target subsystem is unavailable, three principles pull in different directions:
- **P12** requires that the upstream operation succeeds and the failure doesn't cascade. The solution is queuing the downstream effect for retry.
- **P9** requires that the system minimize officer attention cost. Automated retry is preferable to requiring officers to manually re-initiate every routine effect after a transient subsystem outage.
- **P2** requires that state changes are safe. A queued effect's safety depends on preconditions that may change while the effect waits — an application withdrawn, a member departed, a chapter archived. Executing the effect against invalid preconditions is not a safe state change.

P12 and P9 together favor automatic retry. P2 favors precondition validation or human confirmation before execution. These cannot all be satisfied simultaneously.

**How the proposal resolves it:** The proposal applies automatic retry for cross-subsystem effects: "the downstream effect retries until the target subsystem recovers." This prioritizes P12 (no cascade) and P9 (no operator burden) over P2 (safe state changes). Operators "see the pending state and can intervene if recovery takes too long" — but intervention is framed as a timeout concern, not a precondition-validity concern.

For the specific case of audit unavailability, the proposal makes a different choice: officer decisions block entirely and must be re-initiated manually, because "conditions changed before recovery" makes stale-context execution unsafe. This careful treatment recognizes the deferred-execution risk but applies it only to audit, not to general cross-subsystem effects.

**What the philosophy doesn't say:** The philosophy resolves the P6 vs P12 tension for audit storage specifically: "consequential decisions block when audit storage is unavailable." It does not address the broader question of deferred automated effects whose preconditions may change. The P12 principle text says "Cross-subsystem effects that fail are queued" but does not qualify what makes a queued effect safe to execute on retry.

The philosophy needs guidance for distinguishing:
- **Deferred recording** (the operation already executed; only the record is delayed — safe by construction)
- **Deferred execution** (the operation hasn't happened; conditions may have changed — safety is conditional)

The proposal correctly identifies this distinction for audit but does not generalize it. Without philosophical guidance, the distinction remains an ad hoc design choice made in one subsystem rather than a consistent principle applied across all deferred effects.

**Resolution options the philosophy could adopt:**
1. **Precondition validation on retry:** The retry mechanism checks that triggering conditions still hold. Preserves P2 but introduces coupling — the retry logic must understand the preconditions of every effect type, potentially undermining P12's subsystem independence.
2. **Consequence-graduated deferral:** Mirror the audit pattern — consequential effects (roster creation, authority grants) block or require confirmation on retry; low-consequence effects (notification generation, read model updates) auto-retry freely. Preserves P2 for high-consequence effects while preserving P9 for low-consequence ones. Requires classifying effects by consequence level.
3. **Compensating actions:** Auto-retry freely, but detect when a retried effect's preconditions were invalid and surface the inconsistency for operator correction. Preserves P12 and P9 at the cost of accepting transient inconsistency — a P2 relaxation bounded by detection and correction.

**Questions for the user:** Should the philosophy distinguish between deferred recording and deferred execution as a general principle? If so, should the resolution depend on the consequence level of the deferred effect (mirroring the audit pattern), or should a single approach apply to all deferred effects? What level of transient inconsistency is acceptable for automated cross-subsystem effects?
