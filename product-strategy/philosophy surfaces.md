# Philosophy Surfaces

New philosophical concerns discovered during the Stage 2 philosophy alignment review. These are inputs for the philosophy expansion agent — they describe concerns the current philosophy does not fully address.

---

## Implicit Principles

### Organizational uniformity across sub-communities

**Axis:** 5 (Sub-community Provisioning and Lifecycle)

**Design decision:** RosterEntry defines a fixed three-value role enum (`member`, `officer`, `leader`) that applies to all chapters. Organizational structure is the only governance dimension where the proposal enforces a uniform, non-configurable model — compliance rules, trust computation, form definitions, and notification rules are all per-chapter configurable.

**Implicit principle:** Chapter governance should follow a fixed, uniform set of organizational positions across all sub-communities to maintain cross-chapter legibility and prevent governance fragmentation.

**Relationship to existing principles:** Independent of existing principles. P7 (Delegated Authority) governs authority scope mechanics but does not address whether organizational positions should be uniform or configurable. P11 (Configuration by Operators) would pull toward configurability. P1 (Operator Clarity) is served by legibility but does not require uniformity. This implicit principle would be a new concern about organizational design standardization.

**Strength of evidence:** Weak. Only the RosterEntry role enum follows this implicit principle. ChapterTemplate provides structural uniformity for initial provisioning, but templates are operator-configurable and not fixed. No other design decision in the proposal enforces cross-chapter organizational uniformity.

---

## Principle Tensions

### P15 (Traceability as Outcome) vs P1 (Operator Clarity) for cross-subsystem queries

**Axis:** 12 (Cross-workflow State and Operational Continuity)

**Principles in tension:** Principle 15 (Traceability as Outcome) and Principle 1 (Operator Clarity)

P1 requires operators to be able to understand and query the system's operational state — including cross-subsystem views like "what is this member's full operational history?" P15 requires that cross-subsystem connections use event correlation with shared identifiers rather than foreign key navigation at the data layer.

**How the proposal resolves it:** The proposal chose FK-based cross-subsystem joins, prioritizing P1's query ergonomics over P15's subsystem independence. The Cross-workflow State Coherence section explicitly states: "The data model is designed so that 'what is this member's full operational history?' is a single query joining across subsystems." This serves P1 well — operators get simple, fast, complete queries — but violates P15.

**What the philosophy doesn't say:** The philosophy lists P15+P1 as reinforcing: "operators can reconstruct any causal chain, satisfying clarity's demand for explainable cause and effect." This assumes event-based traceability is equally ergonomic for operators as FK navigation. In practice, event correlation may require more complex query tooling, multiple query steps, or a dedicated aggregation layer to achieve the same operator-facing simplicity that FK joins provide.

The philosophy needs guidance for this tension: when the subsystem independence that P15 protects imposes query complexity costs on operators, how should the system resolve the tradeoff? Options include:

- A read-optimized event aggregation layer that provides FK-join-equivalent query performance over correlated events (preserving both principles at the cost of system complexity).
- Accepting that operators use event-correlation queries that are more complex but preserve subsystem independence.
- Defining which cross-subsystem queries are common enough to warrant materialized views or query abstractions, and which are rare enough to tolerate event-correlation complexity.

Without this guidance, proposers will predictably choose FK joins (as this proposal did) because P1's demand for operator-facing simplicity is more immediately felt than P15's demand for architectural independence.
