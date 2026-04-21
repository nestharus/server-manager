# SLICE-016 Proposal: Advanced Trust Management

## 1. Overview

SLICE-016 implements WU-030A and WU-030B by separating trust evidence from derived trust state: AC1 is satisfied by an append-only `trust_signals` table and `POST /api/v1/trust/signals` that persists `signal_type`, structured scope, JSON value, source actor, `observed_at`, and optional `expires_at` without touching `trust_profiles`; AC2 is satisfied by `POST /api/v1/trust/recompute/{member_id}` pinning the current `policy_versions` row where `policy_type = "trust_computation"` plus denormalized `config_version`; AC3 is satisfied by a pure deterministic evaluator over canonical active signals and policy content; AC4 is satisfied by authority checks, `mutate_entity()` audit for both signal append and profile recompute, and no Discord-local or repository-level bypass. D1 defines `trust_signals`; D2 reuses policies for `TrustComputationConfig`; D3 keeps the existing `global|chapter|member` scope vocabulary; D4 extends `trust_profiles` in place; D5 and D6 add the signal and recompute APIs; D7 wires `trust.signal.create` and `trust.recompute` without seeded grants; D8 fixes action/change names; D9 fixes the migration split and chain; D10 fixes determinism; D11 excludes revocation; D12 fixes OCC retry semantics; D13 prohibits alternate trust write paths.

## 2. Migration Chain (D9)

Chain after the current Alembic head:

```python
# migrations/versions/wu-030a_trust_signals.py
revision = "wu_030a_trust_signals"
down_revision = "wu_037_ticket_sla_triggers"

# migrations/versions/wu-030b_trust_profile_recompute_metadata.py
revision = "wu_030b_trust_profile_recompute_metadata"
down_revision = "wu_030a_trust_signals"
```

`wu-030a_trust_signals.py` creates the evidence table. Use Alembic `op.execute()` for the table DDL so the JSONB check constraints are exact:

```sql
CREATE TABLE trust_signals (
    id UUID PRIMARY KEY,
    member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    signal_type TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    scope_id TEXT NULL,
    scope JSONB NOT NULL,
    value JSONB NOT NULL,
    source_actor_kind TEXT NOT NULL,
    source_actor_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT trust_signals_scope_kind_valid
        CHECK (scope_kind IN ('global', 'chapter', 'member')),
    CONSTRAINT trust_signals_scope_id_shape
        CHECK (
            (scope_kind = 'global' AND scope_id IS NULL)
            OR (scope_kind IN ('chapter', 'member') AND scope_id IS NOT NULL)
        ),
    CONSTRAINT trust_signals_source_actor_kind_valid
        CHECK (source_actor_kind IN ('user', 'service')),
    CONSTRAINT trust_signals_signal_type_not_blank
        CHECK (char_length(signal_type) > 0),
    CONSTRAINT trust_signals_source_actor_id_not_blank
        CHECK (char_length(source_actor_id) > 0),
    CONSTRAINT trust_signals_scope_is_object
        CHECK (jsonb_typeof(scope) = 'object'),
    CONSTRAINT trust_signals_scope_kind_matches_json
        CHECK (scope->>'scope_kind' = scope_kind),
    CONSTRAINT trust_signals_scope_id_matches_json
        CHECK (
            (scope_kind = 'global' AND NOT (scope ? 'scope_id'))
            OR (scope_kind IN ('chapter', 'member') AND scope->>'scope_id' = scope_id)
        ),
    CONSTRAINT trust_signals_value_is_object
        CHECK (jsonb_typeof(value) = 'object'),
    CONSTRAINT trust_signals_value_has_schema_version
        CHECK (
            value ? 'schema_version'
            AND jsonb_typeof(value->'schema_version') = 'number'
        ),
    CONSTRAINT trust_signals_expiry_after_observed
        CHECK (expires_at IS NULL OR expires_at > observed_at)
);

CREATE INDEX ix_trust_signals__member_created
    ON trust_signals (member_id, created_at DESC, id DESC);

CREATE INDEX ix_trust_signals__member_type_observed
    ON trust_signals (member_id, signal_type, observed_at DESC);

CREATE INDEX ix_trust_signals__scope
    ON trust_signals (scope_kind, scope_id);

CREATE INDEX ix_trust_signals__value_gin
    ON trust_signals USING GIN (value);

CREATE INDEX ix_trust_signals__member_expires
    ON trust_signals (member_id, expires_at);
```

Downgrade:

```sql
DROP INDEX ix_trust_signals__member_expires;
DROP INDEX ix_trust_signals__value_gin;
DROP INDEX ix_trust_signals__scope;
DROP INDEX ix_trust_signals__member_type_observed;
DROP INDEX ix_trust_signals__member_created;
DROP TABLE trust_signals;
```

`wu-030b_trust_profile_recompute_metadata.py` extends `trust_profiles` and performs the no-shim policy type rename required by D2/D9:

```sql
UPDATE policy_versions
SET policy_type = 'trust_computation'
WHERE policy_type = 'trust'
  AND id IN (
      SELECT policy_version_id
      FROM trust_profiles
  );

ALTER TABLE trust_profiles
    ADD COLUMN config_version BIGINT,
    ADD COLUMN computed_at TIMESTAMPTZ;

UPDATE trust_profiles AS tp
SET config_version = pv.version_number,
    computed_at = tp.updated_at
FROM policy_versions AS pv
WHERE pv.id = tp.policy_version_id;

ALTER TABLE trust_profiles
    ALTER COLUMN config_version SET NOT NULL,
    ALTER COLUMN computed_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN computed_at SET NOT NULL,
    ADD CONSTRAINT trust_profiles_config_version_positive
        CHECK (config_version > 0);

CREATE INDEX ix_trust_profiles__config_version
    ON trust_profiles (config_version);
```

Downgrade:

```sql
DROP INDEX ix_trust_profiles__config_version;

ALTER TABLE trust_profiles
    DROP CONSTRAINT trust_profiles_config_version_positive,
    DROP COLUMN computed_at,
    DROP COLUMN config_version;

UPDATE policy_versions
SET policy_type = 'trust'
WHERE policy_type = 'trust_computation'
  AND id IN (
      SELECT policy_version_id
      FROM trust_profiles
  );
```

Implementation note: add `trust_signals` to `GOVERNANCE_TABLES` in `services/api/tests/conftest.py` so tests isolate rows.

## 3. Contracts (D5/D6)

Extend `services/api/app/contracts/trust.py`.

Keep existing `TrustSignalsInput` for the SLICE-007 onboarding compute endpoint, but update that path to use the new `trust_computation` policy shape. Do not support both old `rules` and new content shapes.

Add:

```python
class TrustSignalScope(_TrustModel):
    scope_kind: ScopeKind
    scope_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global trust signal scope must not include scope_id")
        if self.scope_kind in {"chapter", "member"} and not self.scope_id:
            raise ValueError("chapter/member trust signal scope requires scope_id")
        return self

    def to_persisted_json(self) -> dict[str, str]:
        if self.scope_kind == "global":
            return {"scope_kind": "global"}
        return {"scope_kind": self.scope_kind, "scope_id": self.scope_id}


class TrustSignalCreate(_TrustModel):
    member_id: UUID
    signal_type: str = Field(min_length=1)
    scope: TrustSignalScope
    value: dict[str, Any]
    observed_at: datetime
    expires_at: datetime | None = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: dict[str, Any]) -> dict[str, Any]:
        schema_version = value.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, (int, float)):
            raise ValueError("trust signal value must include numeric schema_version")
        return value

    @model_validator(mode="after")
    def validate_expiry(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        return self


class TrustSignalRead(_TrustModel):
    id: UUID
    member_id: UUID
    signal_type: str
    scope: TrustSignalScope
    value: dict[str, Any]
    source_actor_kind: Literal["user", "service"]
    source_actor_id: str
    observed_at: datetime
    expires_at: datetime | None
    created_at: datetime


class TrustProfileRead(_TrustModel):
    ...
    config_version: int = Field(ge=1)


class TrustRecomputeRequest(_TrustModel):
    reason: str | None = Field(default=None, min_length=1)
    requested_by: str | None = Field(default=None, min_length=1)
```

`TrustRecomputeRequest` is not accepted by `POST /trust/recompute/{member_id}` in this slice because D6 binds the endpoint to no request body. If the class is added for generated contract completeness, it remains unused until a later slice changes the API. Do not allow client-submitted `requested_by`; the service uses `ActorIdentity`.

Add trust-specific exceptions:

- `InvalidTrustSignalScopeError`
- `InvalidTrustSignalActorError` for `actor_kind == "system"` on signal append because D1 stores only `user|service`.
- `TrustRecomputeConflictError` for retry-exhausted OCC conflict.

## 4. Repositories

Extend `services/api/app/repositories/trust.py`.

Keep `fetch_trust_profile_by_member_id()`, but include `t.config_version` in `_TRUST_PROFILE_SELECT`.

Replace `_insert_trust_profile()` with explicit profile helpers:

```python
def insert_trust_profile(connection, *, row: dict[str, Any]) -> None:
    ...

def update_trust_profile(connection, *, member_id: UUID, row: dict[str, Any]) -> None:
    ...

def upsert_trust_profile_for_recompute(connection, *, row: dict[str, Any]) -> None:
    ...
```

The recompute helper writes `score`, `tier`, `signals`, `policy_version_id`, `config_version`, `computed_at`, and `updated_at`. It must not create or advance `aggregate_heads`; that remains exclusively inside `mutate_entity()`.

Add:

```python
def insert_trust_signal(connection, *, row: dict[str, Any]) -> None:
    INSERT INTO trust_signals (
        id, member_id, signal_type, scope_kind, scope_id, scope, value,
        source_actor_kind, source_actor_id, observed_at, expires_at
    ) VALUES (...)
```

Use `Jsonb(row["scope"])` and `Jsonb(row["value"])`.

```python
def list_active_signals_for_member(
    connection,
    *,
    member_id: UUID,
    as_of: datetime,
) -> list[dict[str, Any]]:
    SELECT id, member_id, signal_type, scope_kind, scope_id, scope, value,
           source_actor_kind, source_actor_id, observed_at, expires_at, created_at
    FROM trust_signals
    WHERE member_id = %s
      AND (expires_at IS NULL OR expires_at > %s)
    ORDER BY observed_at ASC, created_at ASC, id ASC
```

No `revoked_at` predicate exists in SLICE-016 because D11 excludes revocation.

```python
def get_trust_profile_for_update(connection, member_id: UUID) -> dict[str, Any] | None:
    SELECT ... FROM trust_profiles ...
    JOIN aggregate_heads ...
    WHERE t.member_id = %s
    FOR UPDATE OF t, h
```

The current `aggregate_heads` row may be missing when recomputing a member with no prior profile. In that case the service calls `mutate_entity(expected_version=0)`, which creates the head.

## 5. Services

Extend `services/api/app/services/trust.py`.

Constants:

```python
TRUST_POLICY_TYPE = "trust_computation"
TRUST_PROFILE_AGGREGATE_TYPE = "trust_profile"
TRUST_SIGNAL_AGGREGATE_TYPE = "trust_signal"
```

`create_trust_signal(db, request, actor)`:

1. Validate the member exists with `fetch_member_by_id()`.
2. Call `validate_trust_signal_scope(request)`; this is a service-level guard in addition to Pydantic validation.
3. Reject `actor.actor_kind == "system"` because `trust_signals.source_actor_kind` is limited to `user|service`.
4. Generate `signal_id = uuid4()`.
5. Build persisted scope JSON from the structured scope; for global store `{"scope_kind": "global"}` with no `scope_id` key.
6. Call `mutate_entity()` with:
   - `aggregate_type="trust_signal"`
   - `aggregate_id=str(signal_id)`
   - `expected_version=0`
   - `action_type="trust.signal.created"`
   - `scope_kind=request.scope.scope_kind`
   - `scope_id=request.scope.scope_id`
   - `request_surface="api:/api/v1/trust/signals"`
   - `payload_allowlist={"signal_type", "scope", "value", "observed_at", "expires_at"}`
7. In `mutate_projection`, call `insert_trust_signal()` and return `StateChangeDraft(change_type="trust.signal.created", payload_json={...})`.
8. Return `TrustSignalRead` and `MutationResult`.

This resolves the append-only question: `trust_signals` is not mutable derived state, but creation still uses `mutate_entity()` as D8 binds so audit/action/state-change invariants are uniform.

`recompute_trust_profile(db, member_id, actor)`:

1. Capture `as_of = datetime.now(UTC)` once before reads. Use it only to select active signals and to persist `computed_at`; never pass it into the evaluator as a score input.
2. Open a transaction for each attempt.
3. Verify the member exists.
4. Read current profile row and aggregate version using `get_trust_profile_for_update()`. If missing, set `expected_version = 0`; otherwise use `row["version"]`.
5. Read the current policy via `fetch_latest_version(connection, "trust_computation", "global", None)`. Missing policy raises `NoTrustPolicyConfiguredError`.
6. Read active signals with `list_active_signals_for_member(connection, member_id=member_id, as_of=as_of)`.
7. Call `compute_score(signals, policy["content"]) -> ComputedTrust(score, tier, signals_summary)`.
8. Call `mutate_entity(..., connection=connection)` with:
   - `aggregate_type="trust_profile"`
   - `aggregate_id=str(member_id)`
   - `expected_version=current_profile_version`
   - `action_type="trust.recompute"`
   - `payload_allowlist={"member_id"}`
   - `scope_kind="global"`
   - `scope_id=None`
   - `request_surface=f"api:/api/v1/trust/recompute/{member_id}"`
9. In `mutate_projection`, upsert/update `trust_profiles` with `score`, `tier`, canonical `signals`, `policy_version_id=policy["id"]`, `config_version=policy["version_number"]`, `computed_at=as_of`, and `updated_at=CURRENT_TIMESTAMP`.
10. Return `StateChangeDraft(change_type="trust.recomputed", payload_json={...}, diff_json={...})`.
11. On `StaleMutationError`, re-run the whole flow once. If the retry is stale, raise `TrustRecomputeConflictError`, mapped to HTTP `409`.

Use `aggregate_type="trust_profile"`, not `"member"`, because SLICE-007 already stores trust profile OCC in `aggregate_heads` under that aggregate.

`validate_trust_signal_scope(request)`:

- Recheck D3: no `scope_id` for global; required nonblank `scope_id` for chapter/member.
- Do not add new scope kinds.
- Do not infer scope from `member_id`; signal scope is explicitly supplied and authority-addressable.

`compute_score(signals, policy_config)`:

- Validate the D2 minimum shape: `schema_version == 1`, numeric `score_floor`, `score_ceiling`, `default_score`, object `signal_weights`, object `decay_rules`, nonempty ordered `level_thresholds`.
- Canonicalize rows by `(observed_at ASC, created_at ASC, id ASC)`.
- Deduplicate exact retry duplicates by `(member_id, signal_type, scope_kind, scope_id, observed_at, source_actor_kind, source_actor_id, canonical_value)`.
- Calculate `score = default_score + sum(weight * magnitude * decay_factor)`.
- `weight` comes from `signal_weights[signal_type]`, defaulting to `0`.
- `magnitude` comes from numeric `value["magnitude"]` when present, otherwise `1`. Boolean values are invalid as magnitudes.
- `decay_factor` is `1` unless a matching deterministic decay rule exists. If decay is implemented in SLICE-016, its reference point must be derived from the included signal set, such as the max included `observed_at`; it must not use current wall-clock time.
- Clamp to `[score_floor, score_ceiling]`, round to int, and select the first threshold where `score <= max_score`.
- Return a canonical `signals` summary containing ordered signal IDs, count, included signal types, and dedupe count. This summary is persisted on `trust_profiles.signals` and used in audit diffs.

Update existing onboarding `compute_trust()`:

- Fetch `policy_type="trust_computation"` and the D2 content shape.
- Keep `POST /api/v1/trust/compute/{member_id}` as the SLICE-007 onboarding path, but it must not read or write `trust_signals`.
- Add `config_version` and `computed_at` when it creates a new `trust_profiles` row.

## 6. Endpoints

Convert `services/api/app/api/v1/endpoints/trust.py` into a package:

```text
services/api/app/api/v1/endpoints/trust/
  __init__.py
  profiles.py      # existing GET /{member_id} and POST /compute/{member_id}
  recompute.py
  signals.py
```

`signals.py`:

```python
router = APIRouter(prefix="/api/v1/trust/signals")

@router.post("", response_model=TrustSignalRead, status_code=HTTPStatus.CREATED)
def create_signal(body: TrustSignalCreate, ...):
    _require_authority(
        db=db,
        actor=actor,
        permission="trust.signal.create",
        scope_kind=body.scope.scope_kind,
        scope_id=body.scope.scope_id,
    )
    read, result = create_trust_signal(db, body, actor)
    response.headers["etag"] = result.etag
    return read
```

Use the roster manual authority pattern: construct `AuthorityRequirement` from the request body scope, call `list_grants_for_grantee()`, evaluate at `current_time()`, and return `403` with `authority_decision_denied` on denial.

`recompute.py`:

```python
router = APIRouter(prefix="/api/v1/trust/recompute")

@router.post(
    "/{member_id}",
    response_model=TrustProfileRead,
    status_code=HTTPStatus.OK,
)
def recompute(member_id: UUID, ...):
    _require_authority(
        db=db,
        actor=actor,
        permission="trust.recompute",
        scope_kind="member",
        scope_id=str(member_id),
    )
    read, result = recompute_trust_profile(db, member_id, actor)
    response.headers["etag"] = result.etag
    return read
```

Use the roster manual authority pattern after resolving `member_id` from the
path: construct
`AuthorityRequirement(permission="trust.recompute", scope_kind="member", scope_id=str(member_id))`,
call `list_grants_for_grantee()`, evaluate at `current_time()`, and return
`403` with `authority_decision_denied` on denial.

No request body, no `If-Match`, and no client-supplied expected version.

`profiles.py`:

- Move existing `POST /api/v1/trust/compute/{member_id}` and `GET /api/v1/trust/{member_id}` here.
- Preserve existing path behavior except for the required `trust_computation` policy rename and `config_version` field in responses.

`__init__.py`:

```python
from fastapi import APIRouter

from . import profiles, recompute, signals

router = APIRouter()
router.include_router(profiles.router)
router.include_router(recompute.router)
router.include_router(signals.router)
```

`services/api/app/api/v1/router.py` continues importing `trust` and should not need a route include change once the package replaces the module.

## 7. Authority Wiring (D7)

New permission names:

- `trust.signal.create` evaluated at the request body signal scope.
- `trust.recompute` evaluated at member scope for `POST /api/v1/trust/recompute/{member_id}` with `scope_id = str(member_id)`.

Do not seed any new service actor grants. Do not broaden the existing `member-onboarder` grant. Operators or services that need these permissions must receive normal authority grants outside this slice.

`POST /trust/signals` cannot use static `RequireAuthority` because the scope is body-driven. It must mirror `roster.py` manual authority evaluation.

`POST /trust/recompute/{member_id}` cannot use static `RequireAuthority` because the required member scope is derived from the resolved path parameter. It must mirror `roster.py` manual authority evaluation after resolving `member_id`, using `AuthorityRequirement(permission="trust.recompute", scope_kind="member", scope_id=str(member_id))`.

## 8. Determinism (D10)

The evaluator boundary is:

```text
compute_score(active_signals, policy_content) -> (score, tier, canonical_signals_summary)
```

Inputs:

- `active_signals`: rows already filtered by the service with a single captured `as_of`, ordered canonically by `(observed_at ASC, created_at ASC, id ASC)`.
- `policy_content`: the exact JSONB content from the pinned `policy_versions` row.

Forbidden inside `compute_score()`:

- `datetime.now()`, database timestamps, randomness, actor identity, input row iteration without explicit ordering, and external service calls.

Expiry filtering occurs outside the evaluator:

```sql
expires_at IS NULL OR expires_at > :as_of
```

This means two recomputes at different times can select different active signal sets when an expiry boundary passes. AC3 still holds because the evaluator is deterministic for the same active signal set and policy version. `computed_at` is persisted for audit/operator context, but `TrustProfileRead` does not expose it and the evaluator does not use it as a score input.

`signal_revision_at` must not be added in SLICE-016 per D4. Staleness UI and profile-listing semantics belong to a later slice.

## 9. Audit (D8)

Signal append:

- `action_type="trust.signal.created"`
- `StateChangeDraft.change_type="trust.signal.created"`
- `aggregate_type="trust_signal"`
- `aggregate_id=str(signal_id)`
- `expected_version=0`
- `scope_kind` and `scope_id` from request body scope
- payload allowlist:
  `{"signal_type", "scope", "value", "observed_at", "expires_at"}`

The state change payload should include `id`, `member_id`, `signal_type`, `scope`, `value`, `source_actor_kind`, `source_actor_id`, `observed_at`, `expires_at`, and `created_at`. It may omit `diff_json` because this creates a new append-only aggregate.

Recompute:

- `action_type="trust.recompute"`
- `StateChangeDraft.change_type="trust.recomputed"`
- `aggregate_type="trust_profile"`
- `aggregate_id=str(member_id)`
- payload allowlist: `{"member_id"}`
- scope: global

`diff_json` must carry old/new values for at least:

- `score`
- `tier`
- `policy_version_id`
- `config_version`
- canonical included signal ID list

The recompute action payload must not include raw signal values; those are already stored and audited on signal creation. The recompute payload records that the member's derived profile was recomputed, while `diff_json` records what derived state changed.

## 10. Concurrency (D12)

Recompute uses optimistic locking on `aggregate_type="trust_profile"`:

1. Read the current trust profile and its aggregate version.
2. Call `mutate_entity(expected_version=current_version)`.
3. If no profile exists, call `mutate_entity(expected_version=0)` and upsert the first profile row.
4. If `StaleMutationError` occurs, re-read member, policy, active signals, and profile version, then retry once.
5. If the retry also raises `StaleMutationError`, raise `TrustRecomputeConflictError`.
6. The endpoint maps `TrustRecomputeConflictError` to HTTP `409 Conflict` with:

```json
{
  "code": "trust_recompute_conflict",
  "message": "trust profile changed during recompute"
}
```

Signal creation uses `expected_version=0` with a new UUID aggregate ID. UUID collision is not a user-visible OCC conflict; let the database error surface as a failed audited action.

## 11. Tests (File-by-File)

Update `services/api/tests/test_trust.py`:

- Existing trust policy seeds use `policy_type="trust_computation"`.
- Existing policy content uses the D2 content shape, not the old nested `rules` shape.
- Existing profile assertions include `config_version`.
- Existing onboarding compute remains separate from `trust_signals`.

Create `services/api/tests/test_trust_signals.py`:

- `test_create_signal_persists_fields_without_mutating_profile` (AC1): create member, seed authority, post signal, assert row fields and zero change to existing profile version/score/tier.
- `test_create_signal_requires_authority_at_scope`: actor with global but not chapter permission cannot create chapter-scoped signal, or actor without `trust.signal.create` is denied.
- `test_create_signal_rejects_invalid_scope_shape`: global with `scope_id`, chapter/member without `scope_id`, and malformed value without numeric `schema_version` are rejected before insert.
- `test_create_signal_with_expires_at_persists_correctly`: `expires_at` after `observed_at` persists; `expires_at <= observed_at` returns validation error.

Create `services/api/tests/test_trust_recompute.py`:

- `test_recompute_pins_current_policy_version` (AC2): seed two `trust_computation` policy versions, recompute, assert `policy_version_id` and `config_version` match latest.
- `test_recompute_deterministic_for_same_inputs` (AC3): recompute twice without changing active signals or policy; assert same `score`, `tier`, `signals`, `policy_version_id`, and `config_version` while version may advance.
- `test_recompute_produces_new_profile_version`: existing profile version N returns ETag N+1.
- `test_recompute_returns_409_on_stale_conflict_after_retry`: monkeypatch repository or mutation hook to raise stale twice; endpoint returns `409` with `trust_recompute_conflict`.
- `test_recompute_honors_expired_signals_by_ignoring_them`: expired signal does not affect output; unexpired equivalent does.
- `test_recompute_requires_trust_recompute_at_member_scope`: user with `trust.recompute` at global scope is denied; user with `trust.recompute` at `scope_kind="member"` and `scope_id=str(member_id)` is allowed.
- `test_recompute_audit_records_correct_diff`: `activity_actions` has `trust.recompute`, `activity_state_changes` has `trust.recomputed`, and `diff_json` includes old/new derived fields and canonical signal IDs.

Audit invariant test:

- `test_no_trust_signal_bypass_remains` (D13): grep Python files outside `services/api/app/services/trust.py` and `services/api/app/repositories/trust.py`; fail if they contain direct `INSERT INTO trust_signals`, `UPDATE trust_profiles`, or `INSERT INTO trust_profiles`. Allow migration files and tests. This verifies no Discord daemon, task, or endpoint bypass writes advanced trust state directly.

Migration tests:

- Existing `alembic upgrade head` fixture must pass with the new chain.
- Add assertions for `trust_signals` constraints where cheap: invalid scope JSON and missing `schema_version` fail at the DB layer.

## 12. AC -> Implementation Trace

| Acceptance criterion | Implementation elements | Tests |
| --- | --- | --- |
| AC1: Creating a trust signal persists type, scope, value, and optional expiry without mutating current trust profile. | `wu-030a_trust_signals.py`; `TrustSignalCreate/Read`; `insert_trust_signal`; `create_trust_signal`; `POST /api/v1/trust/signals`; append-only `trust_signal` mutation audit. | `test_create_signal_persists_fields_without_mutating_profile`; `test_create_signal_with_expires_at_persists_correctly`; DB constraint tests. |
| AC2: Recompute pins the current trust policy/config version. | `wu-030b_trust_profile_recompute_metadata.py`; `policy_type="trust_computation"`; `config_version`; `recompute_trust_profile`; `upsert_trust_profile_for_recompute`; `TrustProfileRead.config_version`. | `test_recompute_pins_current_policy_version`; updated `test_trust.py` policy seed assertions. |
| AC3: Recompute is deterministic for the same signal set and policy version. | `compute_score(active_signals, policy_content)` pure boundary; canonical signal ordering; exact retry dedupe; expiry filtered outside evaluator with one `as_of`; no wall-clock inside evaluator. | `test_recompute_deterministic_for_same_inputs`; `test_recompute_honors_expired_signals_by_ignoring_them`. |
| AC4: Trust writes remain audit-safe and do not accept Discord-local ad hoc overrides. | `mutate_entity()` for signal append and recompute; `trust.signal.create` and `trust.recompute` authority; no seeded service actor grants; no Discord handlers; bypass grep invariant; existing onboarding compute remains separate and policy-renamed. | `test_create_signal_requires_authority_at_scope`; `test_recompute_audit_records_correct_diff`; `test_no_trust_signal_bypass_remains`. |

Out of scope for SLICE-016: signal revocation, scoped trust profiles, Discord handlers, service actor grant seeding, `signal_revision_at`, `trust_computation_configs` tables, backwards-compatible `policy_type="trust"` reads, and dual support for the old SLICE-007 policy content shape.
