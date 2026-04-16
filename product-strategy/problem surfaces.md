# Problem Surfaces

New problem surfaces discovered during problem alignment review. These are gaps in the problem definition, not problems with the proposal.

---

## Proposal-originated Surfaces

None identified. All proposal mechanisms address difficulties described in the problem definition.

---

## Emergent Surfaces

### 1. Notification volume as a distinct burnout vector

- **Axis:** §9 Volunteer Coordination and Staff Burnout
- **What the problem definition says:** Adding process (more review steps, more approval gates, more notifications) accelerates burnout. Every mandatory human touchpoint must justify itself against the risk of not having it. The system must reduce total attention cost, not redistribute it.
- **What the proposal reveals:** Informational notification volume is a separate attention cost vector from mandatory human touchpoints. A system could have perfectly justified touchpoints — every human decision earns its attention cost — and still overwhelm officers through cascading notifications about downstream effects. An application approval triggering a roster entry triggering compliance activation could produce three independent notifications for what is, from the officer's perspective, one event. The proposal addresses this through causal grouping (`per_root_cause` batching of notifications sharing a `correlation_id`), but the problem definition doesn't distinguish between "too many decisions required" (process overhead) and "too much information delivered about decisions already made" (notification overhead). These are different problems: the first is solved by reducing mandatory touchpoints, the second by controlling information delivery patterns.
- **Why it matters:** A proposer following the problem definition's framing could focus entirely on reducing mandatory human touchpoints while ignoring notification design — and still produce a system that causes burnout through information overload rather than decision overload. The problem definition's §9 would be more complete if it articulated notification volume as a distinct burnout mechanism alongside process rigor.

### 2. Concurrent operator configuration changes

- **Axis:** §13 Live Configuration Safety and Temporal Integrity
- **What the problem definition says:** A configuration change on a live system can silently corrupt the semantic integrity of in-flight operations. Work begun under one set of rules must complete under those same rules. The set of affected in-flight operations is not obvious until the change is attempted.
- **What the proposal reveals:** Configuration changes can also corrupt other configuration changes. When two operators attempt to modify the same policy concurrently, the second operator may confirm a change based on a previewed state that is no longer current — the first operator's confirmed change was not part of the second operator's decision context. The proposal addresses this through optimistic concurrency on the preview-confirm pattern (confirmation is rejected if the policy version changed between preview and confirm). This is a distinct sub-problem from in-flight operation corruption: the affected entity is the configuration itself, not an operation running under it. The failure mode is an operator making a governance decision based on stale information about the current governance state.
- **Why it matters:** The problem definition frames temporal integrity as a relationship between configuration changes and in-flight operations. It does not extend this to the relationship between concurrent configuration changes. A proposer could build version pinning for in-flight operations (solving the stated problem) without addressing the concurrent modification problem (which the problem definition doesn't describe), leaving operators vulnerable to governance decisions based on stale previews.

### 3. Cross-subsystem coherence vs. subsystem independence tension

- **Axis:** §12 Cross-workflow State and Operational Continuity, §14 Consolidated Failure Risk and Operational Availability
- **What the problem definition says:** §12: The core difficulty is maintaining coherent state across subsystem boundaries; cross-subsystem relationships must be first-class, not reconstructed by officers from memory. §14: The system must maintain meaningful operational independence between subsystems even though they share a platform.
- **What the proposal reveals:** These two requirements are in direct tension, but the problem definition presents them as independent concerns. Making cross-subsystem relationships first-class through direct foreign key references couples subsystem schemas — schema evolution in one subsystem breaks queries in others, and replacing a subsystem requires migrating cross-boundary foreign keys. This coupling undermines the operational independence that §14 requires. The proposal resolves the tension through event correlation (relationships are first-class in the AuditEntry event stream via `correlation_id`/`causation_id`) plus a CQRS read model (ergonomic cross-subsystem queries without schema coupling). But the tension itself — that coherence implies coupling while independence implies isolation — is a problem surface that neither §12 nor §14 articulates.
- **Why it matters:** A proposer solving §12 through cross-subsystem foreign keys would satisfy the coherence requirement while undermining the independence requirement of §14. A proposer solving §14 through strict subsystem isolation would satisfy independence while making the coherence of §12 unreachable. The problem definition would be more complete if it acknowledged this tension explicitly, so that proposals are evaluated against both requirements simultaneously rather than each in isolation.
