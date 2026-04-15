# Philosophy Decisions Needed

Concerns from the philosophy expansion that require user input before the philosophy can be updated.

---

## Tension Resolutions Needed

### P5 (Low Lock-in) vs. P8 (Platform-Native Interaction)

- **Principles in tension:** Principle 5 (Low Lock-in) — minimize dependencies that are hard to exit; every external dependency must justify itself against the switching cost it introduces. Principle 8 (Platform-Native Interaction) — work with Discord's interaction model, not against it; the system extends Discord rather than replacing it.
- **Context where they conflict:** Going fully platform-native (P8) deepens the dependency that P5 warns against. A system that uses Discord's modals, threads, forums, buttons, and component model is more coupled to Discord than one that uses minimal Discord features. The philosophy presents these principles as compatible (P3 + P8 is listed as reinforcing) without acknowledging their tension.
- **Option A: Optimize for P5 (Low Lock-in).** Build a platform-abstraction layer with swappable interaction backends. The system defines its own interaction model; Discord is one renderer among potential others. Switching platforms means writing a new renderer, not rebuilding business logic or interaction flows. Cost: violates P8's "extend Discord, don't replace it" — the abstraction layer is effectively a parallel UI system.
- **Option B: Optimize for P8 (Platform-Native Interaction).** Use Discord-native constructs throughout, including storing Discord-native references (channel IDs, message IDs, role IDs) as first-class operational state. Maximum leverage of Discord's current capabilities. Cost: switching platforms requires rebuilding not just the interaction layer but untangling Discord constructs from operational state.
- **Option C: Boundary-based resolution (proposal's current approach).** Accept interaction-level coupling (the Discord layer must be rebuilt to switch platforms) but prevent data-level and logic-level coupling (operational data and business rules do not depend on Discord constructs). The operational model is platform-agnostic; the Discord layer translates. Cost: the interaction layer is a full rebuild on platform switch, but data and logic are portable.
- **Recommendation:** Option C is the strongest resolution. It draws a principled boundary: coupling is acceptable where it buys real platform leverage (interaction design) and unacceptable where it creates data captivity (operational state and business rules). This should be articulated in the Principle Tensions section of the philosophy so future design decisions can apply the same boundary. The philosophy should state: *P5 and P8 are resolved by isolating platform coupling to the interaction layer. The operational model, business rules, and stored data remain platform-agnostic. Interaction design goes fully native within the platform layer.*

---

## New Axes Requiring Direction

### Cross-subsystem Relational Integrity

- **Concern:** How should operational objects relate to each other across subsystem boundaries? Should the relationships between objects in different subsystems be explicit, first-class, and directly queryable — or implicit and reconstructable from separate queries across independent data stores?
- **Why the philosophy is silent:** Principle 10 (Durable State) addresses *where* state lives but not *how* state relates across boundaries. Principle 12 (Graceful Degradation) addresses *how subsystems handle each other's failures* but not how they share relational context during normal operation. Principle 1 (Operator Clarity) addresses *whether state transitions are observable* but not whether connections between state transitions in different subsystems are queryable as first-class relationships. A system could satisfy all three principles with fragmented relationships: everything stored durably (P10), subsystems fail independently (P12), each subsystem's transitions individually observable (P1) — but tracing a member's full operational history requires manually correlating records across subsystems.
- **Possible stances:**
  1. **Prescriptive relational integrity.** Operational objects must maintain explicit relationships across subsystem boundaries. The data model enforces FK relationships across domains. Consequence: strong traceability and queryability, but tighter coupling between subsystems at the data layer — a schema change in one subsystem can require migrations in others. May tension with P12 (Graceful Degradation) if subsystem independence is compromised at the data level.
  2. **Outcome-oriented traceability.** An operator should be able to trace any operational event's full causal chain without leaving the system. The implementation mechanism is unconstrained — explicit FKs, event correlation IDs, or reconstructable joins are all acceptable as long as the operator experience meets the bar. Consequence: more flexibility in subsystem design, but weaker guarantee — "reconstructable" can mean slow, complex, or fragile queries that technically work but practically frustrate operators.
  3. **Subsystem-bounded relationships.** Relationships within a subsystem are first-class; relationships across subsystem boundaries are event-based (correlated through audit events or shared reference IDs, not direct FKs). Consequence: maximizes subsystem independence (supports P12), but cross-subsystem queries require joining through an event/audit layer rather than direct relational navigation. The traceability bar depends on audit system quality.
  4. **No principle needed.** This is a data modeling decision, not a philosophical stance. The proposal's choice of explicit FKs is a reasonable implementation, but the philosophy should remain silent on data architecture. Consequence: future proposals may make different choices without philosophical guidance, potentially leading to inconsistent traceability across subsystems.
- **What each stance implies for the proposal:**
  - Stance 1: The proposal's unified data model with explicit FK relationships is directly aligned. No changes needed.
  - Stance 2: The proposal's approach is one valid implementation. The philosophy would validate the outcome (operators can trace causal chains) without prescribing the mechanism.
  - Stance 3: The proposal's direct FK relationships across subsystems may need to be reconsidered in favor of event-based correlation, particularly where cross-subsystem FKs create migration coupling.
  - Stance 4: The proposal proceeds as-is with no philosophical backing for this design choice. Future subsystems may or may not follow the same pattern.
- **Question for the user:** Should cross-subsystem relational integrity be a principle in the philosophy? If so, should it prescribe the mechanism (explicit relational links) or the outcome (operators can trace full causal chains)? Or is this a data modeling concern that should remain outside the philosophy?
