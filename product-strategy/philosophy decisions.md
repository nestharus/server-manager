# Philosophy Decisions Needed

Concerns from the philosophy expansion that require user input before the philosophy can be updated.

---

## Tension Resolutions Needed

### Deferred execution safety: P12 (Graceful Degradation) + P9 (Volunteer-Aware Design) vs P2 (Live-Server Safety)

**Principles in tension:** P12 (Graceful Degradation), P9 (Volunteer-Aware Design), and P2 (Live-Server Safety)

**Context where they conflict:** When a cross-subsystem effect fails because the target subsystem is unavailable and the effect is queued for retry. The queued effect's preconditions may change while it waits — an application withdrawn, a member departed, a chapter archived. This is distinct from deferred *recording* (the operation already happened; only the record is delayed, which is safe by construction). Deferred *execution* means the operation hasn't happened yet, and conditions may have changed.

The philosophy already resolves the specific case of audit unavailability (P6 vs P12): "consequential decisions block when audit storage is unavailable." But this resolution covers deferred recording, not deferred execution. The general question — what happens when an automated cross-subsystem effect is queued and its triggering conditions become invalid before retry — has no philosophical guidance.

**Option A: Precondition validation on retry** — optimize for P2 (safety). The retry mechanism checks that triggering conditions still hold before executing. Preserves safety but introduces coupling: the retry logic must understand the preconditions of every effect type, potentially undermining P12's subsystem independence. Each subsystem must expose precondition-check interfaces for every effect it can receive.

**Option B: Consequence-graduated deferral** — balance P2, P9, and P12. Mirror the audit pattern: consequential effects (roster creation, authority grants, membership state changes) block or require operator confirmation on retry; low-consequence effects (notification generation, read model updates) auto-retry freely. Preserves P2 for high-consequence effects while preserving P9 for low-consequence ones. Requires classifying effects by consequence level, which adds a design dimension to every cross-subsystem interaction.

**Option C: Compensating actions** — optimize for P12 and P9. Auto-retry freely, but detect when a retried effect's preconditions were invalid and surface the inconsistency for operator correction. Accepts transient inconsistency bounded by detection and correction. This is a P2 relaxation: the system may briefly be in an unsafe state, but it self-detects and alerts. Preserves subsystem independence and minimizes officer burden for the common case (retries succeed), at the cost of occasional cleanup for the uncommon case (preconditions changed).

**Recommendation:** Option B (consequence-graduated deferral) aligns most naturally with the philosophy's existing pattern. The philosophy already graduates by consequence for audit (P6 vs P12 resolution) and for review gates (P6 vs P9 resolution). Extending this pattern to all deferred effects is consistent and avoids both the coupling cost of Option A and the transient-inconsistency risk of Option C. The classification effort is real but bounded — each cross-subsystem effect type is classified once at design time, not evaluated dynamically at runtime.

**Question for the user:** Should the philosophy distinguish between deferred recording (safe by construction) and deferred execution (safety conditional on preconditions) as a general principle? If so, should the resolution follow a consequence-graduated pattern (matching the existing audit and review-gate precedents), or should a different approach apply?
