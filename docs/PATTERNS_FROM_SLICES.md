# Patterns From Slices

Reference for recurring implementation patterns extracted from the SLICE pipeline handoff. See `AGENTS.md` for workflow, review gates, and the no-compatibility rule; this doc names the durable code patterns that survived the slices.

## Atomic per-entity transaction
- **When to use**: one workflow mutates multiple aggregates or combines a `mutate_entity()` call with dependent writes that must succeed or fail together.
- **How**: open `with db.transaction() as connection:`; perform reads that establish invariants inside that transaction; pass `connection=connection` through every participating service call and `mutate_entity()`.
- **Why**: partial success creates unrecoverable forks once idempotency or OCC prevents replay from repairing the half-written state.
- **See**: `SLICE-020`, `SLICE-022`, `SLICE-024`

## Service-actor grant seeding in migrations
- **When to use**: a new worker, daemon adapter, or projector needs authority before runtime starts.
- **How**: seed the grant in the owning migration with exact permission matching (`@>` and `<@`), `revoked_at IS NULL`, and usually an active-expiry guard; keep the seed local to the workflow that introduced it.
- **Why**: lazy runtime seeding hides missing infrastructure and makes authorization depend on execution order.
- **See**: `SLICE-015`, `SLICE-017`, `SLICE-019`, `SLICE-020`, `SLICE-022`

## Spoof-proof actor attribution
- **When to use**: a request carries `originating_actor_*`, `resolved_by_*`, or similar attribution fields that should be caller-controlled only for trusted service actors.
- **How**: accept explicit values from service actors; for user callers, derive the effective actor from authentication and overwrite request-body values; reject blank fields and half-specified pairs.
- **Why**: otherwise clients can forge audit identity, ownership, or resolution metadata.
- **See**: `SLICE-014`, `SLICE-020`, `SLICE-021`, `SLICE-022`

## Member alias resolution for authority checks
- **When to use**: grants may be stored under either a member UUID or a Discord numeric id while callers can authenticate as either.
- **How**: resolve aliases through `_collect_member_aliases()`, merge all grantee ids, de-duplicate grants, then evaluate authority across the merged set.
- **Why**: exact-id lookups produce false `403` denials for legitimate holders whose grant was stored under another alias.
- **See**: `SLICE-024`

## Root audit context for scheduler workers
- **When to use**: scheduled work can run without an ambient HTTP or interaction correlation context.
- **How**: if `get_current_audit_context()` is `None`, install `use_audit_context(_root_audit_context())` before the worker calls any mutation service.
- **Why**: `mutate_entity()` needs correlation ids; without a root context the worker fails with `MissingCorrelationContextError`.
- **See**: `SLICE-019`, `SLICE-020`, `SLICE-022`

## Expected OCC conflicts are control flow
- **When to use**: background ticks or retryable concurrent operations contend on the same aggregate heads or cursor rows.
- **How**: catch `StaleMutationError`, log at debug level, and let the next tick retry rather than surfacing an error.
- **Why**: OCC contention is expected under concurrency; treating it as an exception path fills logs with false failures and obscures real incidents.
- **See**: `SLICE-017`, `SLICE-020`, `SLICE-022`

## Terminal replay idempotency
- **When to use**: a client repeats a terminal operation against an already-finalized aggregate and the correct answer is the already-computed result.
- **How**: detect the terminal state first and return the cached read/result without recomputing or mutating; preserve the existing ETag/version.
- **Why**: re-diffing or re-running side effects after terminalization can create duplicates or false conflicts.
- **See**: `SLICE-014`

## Composite aggregate id for multi-dimensional entities
- **When to use**: the domain identity is the logical tuple of scope and target fields, not a randomly generated request id.
- **How**: build the aggregate id from the stable business dimensions, for example `build_permission_intent_aggregate_id(scope_kind, scope_id, role_id, channel_id, kind)`.
- **Why**: using an ephemeral UUID breaks idempotency, OCC, and uniqueness around the actual entity being mutated.
- **See**: `SLICE-014`, `SLICE-020`

## Constants-only audit dispatch
- **When to use**: one service emits multiple `action_type` or `change_type` strings keyed by action/state names.
- **How**: keep dict constants such as `RUN_ACTION_TYPE`, `RUN_CHANGE_TYPE`, `DRIFT_RESOLUTION_ACTION_TYPE`, and look up string literals by key.
- **Why**: f-strings make typos look valid and silently produce broken audit vocabularies until a regression test catches them.
- **See**: `SLICE-014`, `SLICE-020`

## Service-layer authority enforcement
- **When to use**: a service function can be called by HTTP endpoints, workers, or other services.
- **How**: call `_require_scoped_authority(...)` in the mutating service before `mutate_entity()`; keep endpoint checks thin and non-authoritative.
- **Why**: endpoint-only checks are easy to drop during refactors and leave internal callers or moved routes unguarded.
- **See**: `SLICE-014`, `SLICE-024`

## Grep-invariant tests for legacy deletion
- **When to use**: a refactor removes legacy code in place and the project wants a hard guard against reintroduction.
- **How**: add tests like `test_no_<legacy_symbol>_remains()` that walk repo files and assert forbidden substrings are absent.
- **Why**: this turns the `AGENTS.md` no-backwards-compatibility rule into an executable invariant instead of a code-review aspiration.
- **See**: `SLICE-007`, `SLICE-013`, `SLICE-018`

## ETag without second-read race
- **When to use**: a mutation endpoint must return both the mutated body and the new ETag under concurrency.
- **How**: have the service return the read model plus `MutationResult`; use `result.version` / `result.etag` directly instead of issuing a second lookup after the mutation.
- **Why**: a second read can observe a newer version than the body you are returning, causing body/ETag mismatch.
- **See**: `SLICE-024`

## Successor id normalization
- **When to use**: transfer or handoff requests accept holder ids that may be UUIDs or Discord ids.
- **How**: normalize with a dedicated parser like `_normalize_holder_id()` that accepts only UUID or numeric Discord-id strings.
- **Why**: generic nonblank validation accepts garbage ids that cannot map to a real holder and can strand a transfer.
- **See**: `SLICE-024`

## Batch partial-success returns
- **When to use**: a batch handoff or reassign operation should make forward progress item-by-item instead of failing the entire batch.
- **How**: run each item in its own transaction; return HTTP `200` with a result object that separates `transferred`, `already_owned`, and `failed`.
- **Why**: operators need retryable progress, and one conflicting item should not erase completed work for the rest of the batch.
- **See**: `SLICE-024`

## CHECK constraints for resolution states
- **When to use**: a table has status-dependent metadata requirements such as resolution actor, timestamp, and reason.
- **How**: backfill legacy rows first, then add a CHECK constraint encoding each allowed state/field combination.
- **Why**: application-level validation alone cannot protect live databases from old rows, manual SQL, or missed code paths.
- **See**: `SLICE-014`

## Partial unique indexes for NULL-equality gaps
- **When to use**: logical uniqueness depends on a nullable column and plain `UNIQUE` would treat `NULL != NULL`.
- **How**: split uniqueness into partial indexes, typically one `WHERE channel_id IS NULL` and one `WHERE channel_id IS NOT NULL`.
- **Why**: without the split, conflict detection silently misses duplicate logical rows in the `NULL` branch.
- **See**: `SLICE-014`

## Projection insert returns newly inserted only
- **When to use**: batch projection inserts use `ON CONFLICT DO NOTHING` and downstream logic needs the full logical set.
- **How**: return only ids from the successful insert path; if the caller needs the full set, do a follow-up read keyed by the run or aggregate.
- **Why**: pretending conflict-path rows were inserted leads callers to run bootstrapping mutations like `expected_version=0` against already-existing aggregates.
- **See**: `SLICE-014`

## Atomic correction overlay
- **When to use**: one workflow corrects part of an extracted or inferred payload while the untouched fields should still count as present.
- **How**: merge corrected fields on top of the original extracted fields before downstream evaluation.
- **Why**: replacing the full extracted payload with a one-field correction makes unrelated required fields disappear and corrupts evaluation.
- **See**: `SLICE-022`

## Pluggable external-service stub
- **When to use**: a slice introduces an integration boundary before a concrete provider is ready.
- **How**: define a `Protocol`, provide a stub implementation that raises a typed `NotConfigured` error, and inject the provider through the app factory.
- **Why**: this keeps the boundary explicit, testable, and fail-fast without smuggling provider assumptions into business logic.
- **See**: `SLICE-022`

## Datetime aware-only contracts
- **When to use**: request or persistence models carry timestamps destined for `TIMESTAMPTZ` columns.
- **How**: use `AwareDatetime` in Pydantic contracts and pass timezone-aware values end to end.
- **Why**: naive datetimes can be silently converted with local-time assumptions and corrupt time-based policy or expiry logic.
- **See**: `SLICE-016`, `SLICE-020`

## Cursor min-age fence
- **When to use**: a projector resumes from a monotonic event id while writes may commit out of order relative to id visibility.
- **How**: compute the settled head with the same `MIN_AGE_SECONDS` fence both when advancing the cursor and when serving reads.
- **Why**: using a younger read fence than the projector fence makes a healthy projector look permanently stale.
- **See**: `SLICE-017`

## Cursor OCC for projector ticks
- **When to use**: multiple projector ticks or schedulers can race to advance the same `read_model_cursors` row.
- **How**: update the cursor with `expected_version=cursor.version` and treat stale conflicts as expected retries.
- **Why**: this prevents double-advance or lost-progress bugs without forcing a global singleton worker.
- **See**: `SLICE-017`

## Conftest re-seed of service actors
- **When to use**: per-test truncation wipes `authority_grants` or cursor seed rows that some workers and read models depend on.
- **How**: re-seed required grants and cursor rows inside `services/api/tests/conftest.py` after truncation.
- **Why**: otherwise tests fail for infrastructure reasons unrelated to the unit under test, and projector/worker tests become order-dependent.
- **See**: `SLICE-017`, `SLICE-022`

## CodeRabbit stale-repost skip
- **When to use**: CodeRabbit reposts findings from an earlier commit even though HEAD already contains the fix.
- **How**: verify the current file content at HEAD, cite the exact lines in a PR comment, and skip a fake fix pass when the warning is stale.
- **Why**: re-fixing an already-fixed issue churns commits and review cycles without changing the code.
- **See**: `SLICE-011`, `SLICE-019`

## Chapter-from-resource-not-request authority
- **When to use**: a request references a resource that already carries its owning chapter or scope.
- **How**: load the resource first, authorize against the resource's scope, and reject mismatched request scope fields.
- **Why**: trusting the caller-supplied chapter id creates a spoof vector around authority checks and audit scope.
- **See**: `SLICE-022`

## Concurrency serialization before successor lookup
- **When to use**: transfer logic must ensure only one successor grant is created for a predecessor.
- **How**: lock the predecessor aggregate head first with `get_head_for_update(...)`, then look up existing successors inside the same transaction.
- **Why**: otherwise two concurrent transfers can both observe "no successor yet" and create divergent successor grants.
- **See**: `SLICE-024`

## Idempotent successor transfer replay
- **When to use**: a transfer request repeats against a predecessor that may already have been transferred.
- **How**: if the existing successor matches the requested successor, return the existing grant with `200`; if it points elsewhere, raise a conflict.
- **Why**: retries for the same operation should be safe, but retries that imply a different business decision must not silently overwrite history.
- **See**: `SLICE-024`

## Excluded (stale relative to current code)
- Handoff generalized `wu-029a` into the standard no-op downgrade pattern for seeded service grants; current `wu-029a_notifications.py` still deletes the seeded grant on downgrade.
- Handoff implied hierarchical grant scope evaluation; current authority evaluation is exact-match on `scope_kind` and `scope_id`.
- Handoff phrased Discord-originated API traffic as uniformly service-authenticated; current adapters intentionally mix service headers and direct user headers by workflow.
