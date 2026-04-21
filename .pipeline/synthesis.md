# SLICE-016 Phase 2 Synthesis: Binding Decisions

Revision 1 note: D7 now evaluates `trust.recompute` at member scope using
the `{member_id}` path parameter, while preserving body-scope evaluation for
`trust.signal.create`.

These decisions are binding for the SLICE-016 proposal and implementation.
The proposal may choose implementation mechanics inside these boundaries, but
it must not add scope, replace these directions, or introduce compatibility
paths around them.

## Acceptance Criteria Reference

- **AC1**: Creating a trust signal persists type, scope, value, and optional
  expiry without mutating the current trust profile immediately.
- **AC2**: Recompute pins the current trust policy/config version when
  producing the new profile.
- **AC3**: Recompute is deterministic for the same signal set and policy
  version.
- **AC4**: Trust writes remain audit-safe and do not accept Discord-local ad
  hoc overrides.

## Resolved Existing State

- Current `trust_profiles` columns from `migrations/versions/wu-012_trust.py`
  are: `member_id`, `score`, `tier`, `signals`, `policy_version_id`,
  `created_at`, and `updated_at`. The aggregate version is in
  `aggregate_heads` for `aggregate_type = "trust_profile"`.
- Current SLICE-007 trust code uses `policy_type = "trust"`. SLICE-016
  replaces that with `policy_type = "trust_computation"` everywhere trust
  computation policy is read, seeded, or tested. Do not keep aliases.
- Current SLICE-010 policy identity is
  `(policy_type, scope_kind, scope_id, version_number)`. "Current active"
  means the row returned by `fetch_latest_version()`: highest
  `version_number`, then latest `effective_at`, then latest `id`, for the
  same `(policy_type, scope_kind, scope_id)`.
- Current trust output contract is stable around `member_id`, `score`, `tier`,
  `signals`, `policy_version_id`, and aggregate `version`. SLICE-016 may add
  `config_version`; it must not expose recompute timestamps in
  `TrustProfileRead`.

## Binding Decisions

- **D1 - BINDING: TrustSignal table shape.**
  SLICE-016 creates `trust_signals` as an append-only evidence table:
  `id UUID PRIMARY KEY`, `member_id UUID NOT NULL REFERENCES members(id) ON
  DELETE RESTRICT`, `signal_type TEXT NOT NULL`, `scope_kind TEXT NOT NULL`,
  `scope_id TEXT NULL`, `scope JSONB NOT NULL`, `value JSONB NOT NULL`,
  `source_actor_kind TEXT NOT NULL`, `source_actor_id TEXT NOT NULL`,
  `observed_at TIMESTAMPTZ NOT NULL`, `expires_at TIMESTAMPTZ NULL`, and
  `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.

  Required CHECK constraints:
  `scope_kind IN ('global','chapter','member')`;
  global scope requires `scope_id IS NULL`; chapter/member scope require
  `scope_id IS NOT NULL`;
  `source_actor_kind IN ('user','service')`;
  `char_length(signal_type) > 0`;
  `jsonb_typeof(scope) = 'object'`;
  `scope->>'scope_kind' = scope_kind`;
  global scope has no JSON scope id, while chapter/member scope has
  `scope->>'scope_id' = scope_id`;
  `jsonb_typeof(value) = 'object'`;
  `value ? 'schema_version'`;
  `jsonb_typeof(value->'schema_version') = 'number'`;
  and `expires_at IS NULL OR expires_at > observed_at`.

  Required indexes:
  `(member_id, created_at DESC, id DESC)`;
  `(member_id, signal_type, observed_at DESC)`;
  `(scope_kind, scope_id)`;
  a GIN index on `value`;
  and `(member_id, expires_at)`. Do not create a partial "active signal" index
  with `CURRENT_TIMESTAMP`; PostgreSQL partial indexes cannot depend on moving
  time. Filter active rows in the query.

  Do not add a uniqueness or dedupe constraint. Duplicate semantics belong in
  the deterministic combiner, not in the table.

  AC traceability: supports AC1 by defining the persisted evidence fields and
  preventing arbitrary malformed scope/value JSON from entering the evidence
  table.

- **D2 - BINDING: TrustComputationConfig uses policies.**
  `TrustComputationConfig` is stored as `policy_versions.content` with
  `policy_type = "trust_computation"`. Do not create a
  `trust_computation_configs` table.

  Minimum content shape for SLICE-016:

  ```json
  {
    "schema_version": 1,
    "score_floor": 0,
    "score_ceiling": 100,
    "default_score": 50,
    "signal_weights": {},
    "decay_rules": {},
    "level_thresholds": [
      {"tier": "low", "max_score": 39},
      {"tier": "medium", "max_score": 79},
      {"tier": "high", "max_score": 100}
    ]
  }
  ```

  SLICE-016 must update SLICE-007 trust tests and seeds from
  `policy_type = "trust"` to `policy_type = "trust_computation"` and to the
  new content shape. Supporting both the old `rules` shape and the new shape
  is forbidden.

  AC traceability: supports AC2 by using the existing versioned policy
  substrate as the config pin instead of creating a parallel config system.

- **D3 - BINDING: Signal scope vocabulary.**
  Trust signals use the existing `ScopeKind =
  Literal["global","chapter","member"]`. The API accepts a structured scope:

  ```text
  TrustSignalScope
    scope_kind: ScopeKind
    scope_id: str | None
  ```

  The service constructs the persisted `scope` JSON from `scope_kind` and
  `scope_id`; clients do not submit arbitrary scope JSON. Scope rules are:
  `global` means server-wide evidence and must have `scope_id = None`;
  `chapter` means chapter-specific evidence and must have `scope_id`;
  `member` means member-scoped evidence and must have `scope_id`.

  AC traceability: supports AC1 by making signal scope inspectable and
  authority-addressable.

- **D4 - BINDING: TrustProfile extension and aggregate versioning.**
  Extend `trust_profiles` in place. Do not create a parallel
  `trust_profile_versions` table.

  Required added columns:
  `config_version BIGINT NOT NULL` and
  `computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.

  Backfill `config_version` from the referenced `policy_versions.version_number`
  and backfill `computed_at` from `updated_at`. Keep `policy_version_id` as the
  durable config pin and treat `config_version` as denormalized operator-facing
  metadata. Do not add `signal_revision_at` in SLICE-016; no profile-listing or
  staleness UI requires it.

  Aggregate version remains in `aggregate_heads` for
  `aggregate_type = "trust_profile"` and `aggregate_id = str(member_id)`.
  `TrustProfileRead` adds `config_version` but does not add `computed_at`.

  AC traceability: supports AC2 by recording both the policy row id and numeric
  policy version used for the profile, while preserving existing optimistic
  locking.

- **D5 - BINDING: Signal append API.**
  Add `POST /api/v1/trust/signals -> TrustSignalRead` with status `201`.

  Request shape:

  ```text
  TrustSignalCreate
    member_id: UUID
    signal_type: str
    scope: TrustSignalScope
    value: dict[str, Any]  # object, must include schema_version
    observed_at: datetime
    expires_at: datetime | None = None
  ```

  Response shape:

  ```text
  TrustSignalRead
    id: UUID
    member_id: UUID
    signal_type: str
    scope: TrustSignalScope
    value: dict[str, Any]
    source_actor_kind: Literal["user","service"]
    source_actor_id: str
    observed_at: datetime
    expires_at: datetime | None
    created_at: datetime
  ```

  Clients must not submit source actor fields. The service derives
  `source_actor_kind` and `source_actor_id` from the authenticated actor.
  Signal append verifies the member exists, writes only `trust_signals`, and
  does not read, update, or recompute `trust_profiles`.

  Authority is body-scope driven: evaluate
  `AuthorityRequirement(permission="trust.signal.create", scope_kind=body.scope.scope_kind,
  scope_id=body.scope.scope_id)` manually in the endpoint before calling the
  service.

  AC traceability: directly satisfies AC1 and supports AC4 by separating
  evidence append from derived profile mutation.

- **D6 - BINDING: Recompute API.**
  Add `POST /api/v1/trust/recompute/{member_id} -> TrustProfileRead`.
  The request has no body and no client-supplied expected version. The response
  status is `200` whether the profile already existed or had to be created,
  and the response `ETag` is the new trust-profile aggregate version.

  Recompute flow:
  verify the member exists; read current
  `policy_type = "trust_computation"` at `scope_kind = "global"` and
  `scope_id = None`; read active signals for the member; run the pure
  evaluator; upsert/update `trust_profiles`; pin `policy_version_id` and
  `config_version`; and return the profile.

  Profile scope remains global for SLICE-016 because `trust_profiles` is keyed
  only by `member_id` and the endpoint path carries no profile scope. Scoped
  computation configs may be stored in policies, but this endpoint consumes
  only the global `trust_computation` config until a later slice introduces
  scoped trust profiles.

  AC traceability: directly satisfies AC2 and AC3 by making recompute the only
  operation that converts persisted evidence plus current config into derived
  score/tier state.

- **D7 - BINDING: Authority grants.**
  New trust operations use these permissions:
  `trust.signal.create` at the request body signal scope, with
  `scope_kind = body.scope.scope_kind` and `scope_id = body.scope.scope_id`;
  and `trust.recompute` at member scope for
  `POST /trust/recompute/{member_id}`, with `scope_kind = "member"` and
  `scope_id = str(member_id)`.

  Do not seed a new trust service actor. Existing user and service actors must
  receive normal authority grants if they need these permissions. Existing
  `member-onboarder` grants may remain for SLICE-007 onboarding behavior but
  must not be broadened to include advanced trust signal or recompute
  permissions unless a later migration explicitly grants them.

  AC traceability: supports AC4 by keeping writes inside the established
  authority model without adding an unreviewed service bypass.

- **D8 - BINDING: Audit action and state-change names.**
  Signal creation uses `mutate_entity()` with
  `aggregate_type = "trust_signal"`, `aggregate_id = str(signal_id)`,
  `expected_version = 0`, `action_type = "trust.signal.created"`, and
  `StateChangeDraft.change_type = "trust.signal.created"`.

  Recompute uses `mutate_entity()` with
  `aggregate_type = "trust_profile"`, `aggregate_id = str(member_id)`,
  `action_type = "trust.recompute"`, and
  `StateChangeDraft.change_type = "trust.recomputed"`.

  Recompute state changes must include `diff_json` with old/new values for at
  least `score`, `tier`, `policy_version_id`, `config_version`, and the
  canonical included signal id list. Signal creation may omit `diff_json`
  because it creates a new aggregate.

  AC traceability: directly supports AC4 and gives operators an inspectable
  derived-state change record.

- **D9 - BINDING: Migration split.**
  Use two migrations:
  `migrations/versions/wu-030a_trust_signals.py` creates `trust_signals`, its
  constraints, and its indexes; `migrations/versions/wu-030b_trust_profile_recompute_metadata.py`
  extends and backfills `trust_profiles`.

  `wu-030b` also performs the no-shim data rename for existing trust
  computation policy rows from `policy_type = "trust"` to
  `policy_type = "trust_computation"` where those rows are referenced by
  `trust_profiles`. Runtime code and tests must not support both names.

  Chain these migrations after the current Alembic head in the implementation
  worktree, with `wu-030b` depending on `wu-030a`.

  AC traceability: supports AC1 and AC2 by separating evidence-table creation
  from profile metadata and data backfill.

- **D10 - BINDING: Determinism boundary.**
  Trust computation is a pure function of `(active_signals, policy_content)`.
  It returns only deterministic score output: `score`, `tier`, and a canonical
  `signals` summary. It must not use randomness, actor identity, database row
  read order, or wall-clock time inside the evaluator.

  Signal ordering is canonical:
  `(observed_at ASC, created_at ASC, id ASC)`. The evaluator may dedupe exact
  retry duplicates by canonical key
  `(member_id, signal_type, scope_kind, scope_id, observed_at,
  source_actor_kind, source_actor_id, canonical_value)`.

  Expiry filtering happens outside the evaluator by capturing one `as_of` time
  at the start of recompute and selecting rows where
  `expires_at IS NULL OR expires_at > as_of`. That `as_of` value is not part
  of `TrustProfileRead` and is not a score input.

  AC traceability: directly satisfies AC3.

- **D11 - BINDING: Signal revocation is out of scope.**
  SLICE-016 has no signal revocation endpoint, no `trust_signal.revoke` action,
  and no `revoked_at` column. If revocation is needed later, it must be a
  separate audited mutation and migration rather than a hidden update path
  added to this slice.

  AC traceability: supports AC1 and AC4 by keeping this slice to signal append
  and deterministic recompute.

- **D12 - BINDING: Recompute concurrency.**
  Recompute reads the current trust-profile aggregate version internally and
  calls `mutate_entity(expected_version=current_version)`. If
  `StaleMutationError` occurs, the service must re-read member, policy,
  active signals, and profile version, then retry once. If the retry also
  sees a stale version, return HTTP `409 Conflict` with a trust-specific error
  code such as `trust_recompute_conflict`.

  Do not require `If-Match` on recompute. Recompute is server-derived, so
  operator clients should not provide an expected profile version.

  AC traceability: supports AC3 and AC4 by preserving optimistic locking while
  avoiding client-supplied OCC for a deterministic server-side operation.

- **D13 - BINDING: No Discord bypass or alternate write path.**
  SLICE-016 adds no Discord interaction and no Discord-side direct database
  writes. Any future Discord UI for trust evidence must call the HTTP API.

  New operator-managed trust evidence can only be written through
  `POST /api/v1/trust/signals`. Derived trust profile updates can only be
  written through the API service path that calls `mutate_entity()` for
  `trust_profile`. No daemon, task, repository helper, or Discord adapter may
  write `trust_signals` or `trust_profiles` directly outside these service
  functions.

  The existing SLICE-007 `/api/v1/trust/compute/{member_id}` onboarding path is
  not an advanced trust-signal path. During SLICE-016 it must be updated to
  use `policy_type = "trust_computation"` if it remains public, and it must
  not accept operator-managed TrustSignal evidence or bypass the new
  signal/recompute flow.

  AC traceability: directly satisfies AC4.

## Synthesis Notes

- The central boundary is evidence versus derived state. `trust_signals` is
  append-only evidence; `trust_profiles` is recomputed derived state.
- `policy_versions` is already the right substrate for
  `TrustComputationConfig`; adding a second config table would duplicate
  versioning, preview/confirm, scope, and audit behavior.
- Timestamps are allowed as persistence/audit metadata, but deterministic
  trust output must remain score/tier/signals/config pin only.
