# Risk: Shortcut — Activity/Audit Model

**Rating: LOW**

## Does the proposal replace one shortcut with another?

No. The proposal makes a genuine structural change. The old model
couples concurrency control, audit history, and business state in one
mutable row. The proposed model separates these into distinct storage
layers with clear authority boundaries: append-only streams for history,
`aggregate_heads` for concurrency, and projection tables for reads.

The architecture is not symptom-masking. It is a clean decomposition of
three concerns that were previously tangled in the entity row.

## Findings by focus area

### Hidden compatibility shims

None. The proposal explicitly mandates a single cutover: no dual support
for body `version` and `If-Match`, no row-version columns coexisting
with activity-derived heads. Section 7 states this plainly. Section 10
lists "introducing a second compatibility path" as out of scope. This is
the right stance.

### Duplicated audit/versioning paths

The action vs state-change split is clean and well-motivated. One action
maps to zero or many state changes. Failed actions are auditable but do
not advance concurrency. There is no duplicated versioning path.

One minor denormalization exists: `diff_json` is stored at write time
alongside `payload_json` in `activity_state_changes`. The proposal
correctly identifies `payload_json` as authoritative and `diff_json` as
derived. However, because the table is append-only, a bad `diff_json`
cannot be corrected in place — it would require either a correction
record or a bulk recompute across immutable rows. This is a manageable
operational concern, not a structural flaw, but it means the team must
decide during implementation whether `diff_json` is stored eagerly
(write-time) or computed lazily (read-time). The proposal assumes
write-time; that choice should be confirmed with an eye toward
append-only immutability.

### Vague "canonical diff/hash" language

The proposal uses the word "canonical" frequently, but it is precise
about what it defers and why:

- Phase 1 uses monotonic sequence numbers for concurrency. No hash, no
  canonical serialization problem.
- Phase 2 may introduce hash-chain heads, at which point canonical
  serialization (JCS/RFC 8785, key ordering, null handling, numeric
  precision, hash algorithm) must be specified.

This is not vague postponement. The Phase 1 mechanism is complete and
self-contained. The deferral is clearly scoped to corruption-detection
and cross-system verification needs that do not exist yet.

The one soft spot: `payload_json` is called "the canonical accepted
fact" but its schema and serialization rules are not specified for
Phase 1 either. For a single aggregate (chapters) this is fine — the
shape is implicit from the business domain. For a second aggregate, the
platform will need to decide whether `payload_json` follows a
per-aggregate schema contract or remains free-form JSON. This is a
design task, not a risk.

### Source-vs-artifact confusion

The authority boundaries are clearly drawn:

- `activity_state_changes` is the source of truth for history
- `activity_actions` is the source of truth for actor attribution
- Business tables are derived projections
- `aggregate_heads` is an infrastructure helper
- `diff_json` is a derived artifact of `payload_json`

No confusion between sources and artifacts.

### Symptom-masking rather than structural change

The Phase 1 concurrency primitive — a monotonic sequence number in
`aggregate_heads` — is mechanically identical to the old row-level
`version` integer. The structural improvement is not the primitive
itself but where it lives and what it is decoupled from. Business rows
no longer carry concurrency metadata. History is no longer inferred
from mutable state. Actor attribution is no longer absent.

This is a real separation of concerns, not a relocation of the same
shortcut.

## Risks that could elevate the rating

1. **Phase 2 never arrives.** If no second aggregate ever adopts the
   model, the platform carries append-only complexity without the full
   payoff. The sequence-number concurrency is then structurally similar
   to what it replaced, just in a different table. Mitigation: treat the
   second-aggregate adoption as a committed follow-on, not an open-ended
   "maybe."

2. **`diff_json` becomes a de facto second source of truth.** If audit
   UI reads `diff_json` directly and no one ever cross-checks it against
   `payload_json`, divergence will go unnoticed. Mitigation: rebuild
   tooling (even manual for Phase 1) should verify `diff_json`
   consistency, or `diff_json` should be computed at read time.

3. **Projection rebuild is deferred but described as mandatory.** The
   proposal correctly calls rebuild tooling "a required capability for
   production safety" but defers its implementation. For chapters (small
   table, first aggregate), manual rebuild is acceptable. The risk is
   that "manual is sufficient" becomes permanent. Mitigation: the
   second-aggregate initiative must deliver automated rebuild as a
   prerequisite, not a follow-on.

## What LOW requires

- The single-cutover rule (no body `version` + `If-Match` coexistence)
  is enforced during implementation, not softened into a migration
  period.
- `diff_json` storage strategy is confirmed before implementation:
  either accept the append-only immutability consequence of write-time
  storage, or compute diffs at read time.
- `payload_json` schema expectations for the chapters aggregate are
  documented during implementation design, even if a formal
  cross-aggregate serialization spec is deferred.
- Second-aggregate adoption has a concrete trigger or timeline, not an
  open-ended deferral.
- Projection rebuild (even manual) is delivered alongside the first
  aggregate, not after it.
