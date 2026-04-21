# Prototype Notes: slice-013-chapter-provisioning

## Questions and answers

### Q1: Discord provisioning workflow
**Answer:** A single offline handler shape can exercise category creation, role creation, and text-channel creation with role-keyed permission overwrites. Partial failure after the first role leaves durable cleanup data if the provisioning result records every created resource as it goes.
**Evidence:** `prototype/discord_provisioning.py` runs a successful path with `create_text_channel(..., overwrites={role: overwrite})` and a failing path where the second `create_role` call raises. The failing path prints the first role id in `cleanup_required`.
**Caveats:** This uses a stub exception surface instead of importing `discord.py`, because the prototype is intentionally no-network and research noted the bare local Python environment may not import `discord`.

### Q2: Lifecycle + optimistic locking
**Answer:** The lifecycle fits a small explicit transition matrix: `proposed -> provisioning -> active -> archived`, with `provisioning -> provisioning_failed -> provisioning` for retry. Invalid paths can fail with a typed lifecycle error before any write is accepted.
**Evidence:** `prototype/lifecycle_state_machine.py` defines `Chapter(state: Literal["proposed","provisioning","active","provisioning_failed","archived"])`, `TRANSITIONS`, and `transition(current, next_state)`. The script prints valid, retry, and invalid paths.
**Caveats:** The script increments an in-memory `version` to show accepted transition shape, but does not integrate the production `mutate_entity()` OCC implementation.

### Q3: Failed provisioning deferred effect
**Answer:** The existing seam is sufficient in shape if the failure mutation calls the deferred-effect repository insert from inside `mutate_projection(connection)`. The state transition and deferred effect share the same outer transaction and rollback together if a later error occurs.
**Evidence:** `prototype/failed_provision_deferred_effect.py` uses a fake `mutate_entity()` and transaction connection. The callback catches a Discord provisioning exception, inserts a deferred effect with `consequence_level="consequential"`, `precondition_state="unchecked"`, and payload containing `chapter_id` plus `partial_resources`, then transitions the chapter to `provisioning_failed`. The rollback proof raises after enqueue and shows no deferred effect or state change persisted.
**Caveats:** This proves the transaction shape, not the real Postgres behavior. Production should call the repository-level `enqueue_effect(connection, ...)`, not the service-level wrapper that opens its own connection.

### Q4: Template instantiation model
**Answer:** Copy-on-instantiate is required for replayable provisioning. A later template edit should not change the chapter's operational configuration snapshot, while `template_id` remains useful provenance.
**Evidence:** `prototype/template_instantiation.py` deep-copies `channel_structure`, `role_structure`, and `default_permission_intents` into `Chapter.configuration`, then edits the template and prints that the chapter snapshot still has the original channel count.
**Caveats:** The prototype stores the operational snapshot in `Chapter.configuration` because that was the requested artifact. Research says the proposal currently reserves `configuration` for non-operational metadata, so production needs a proposal decision before adopting this storage location.

### Q5: Snapshot storage location
**Answer:** The snapshot can technically live on the chapter aggregate as JSON, but doing so in `Chapter.configuration` crosses the documented governance boundary. The safer production path is either revising the proposal to allow operational provisioning snapshots in `configuration` or adding a dedicated snapshot field/child table.
**Evidence:** `prototype/template_instantiation.py` shows the JSON shape is straightforward and preserves replayability.
**Caveats:** This is a governance finding, not a Python limitation.

### Q6: Idempotent retry anchor
**Answer:** Partial Discord resource IDs must be persisted with the failed chapter state and/or deferred effect payload. The prototype's cleanup effect payload is the durable retry/cleanup anchor; relying on names alone is unsafe.
**Evidence:** `prototype/failed_provision_deferred_effect.py` persists `partial_resources` in both the failed chapter record and the deferred effect payload. `prototype/discord_provisioning.py` shows the first role id is captured before the second role creation fails.
**Caveats:** Production still needs a canonical owner for partial resource state to avoid divergence between chapter state and deferred-effect payload.

## Surprises

- The deferred-effect service wrapper is the wrong abstraction for atomic composition because it opens a new connection; the repository insert is the useful seam inside `mutate_projection(connection)`.
- The lifecycle matrix is small, but deciding whether `proposed -> archived` should exist is a product decision. The prototype allowed it as an operator escape hatch before Discord resources exist.
- The requested `Chapter.configuration` snapshot works mechanically, but it directly exposes the proposal conflict noted in research.

## New questions surfaced

- Should partial resource IDs live only in a deferred effect, only on the chapter aggregate, or in a dedicated provisioning-attempt table?
- Should `provisioning_failed -> archived` trigger cleanup before archive, or should archive be blocked while consequential cleanup is unchecked?
- Should retry reuse the same idempotency key per chapter/version, or should each provisioning attempt get a separate attempt id?

## Artifacts built

- `prototype/discord_provisioning.py`: mock Discord guild provisioning with successful overwrite creation and injected second-role failure.
- `prototype/lifecycle_state_machine.py`: Pydantic chapter lifecycle model, transition matrix, valid retry path, and invalid transition errors.
- `prototype/failed_provision_deferred_effect.py`: in-memory `mutate_entity()` transaction shape for atomically degrading chapter state and enqueueing a cleanup deferred effect.
- `prototype/template_instantiation.py`: copy-on-instantiate template snapshot with later template edit proving chapter configuration stability.

## Time spent

- Roughly within the 1-2 hour prototype budget.
- No early-exit condition stopped the prototype, but the `Chapter.configuration` boundary conflict should be escalated before production implementation.
