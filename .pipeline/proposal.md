# SLICE-020 Phase 3 Proposal: Temporary Permission Management

## Binding sources

- `.pipeline/synthesis.md` — D1–D15 (binding).
- `.pipeline/research.md` — evidence base (informational).
- `product-strategy/tickets/SLICE-020.md` — AC1–AC4, Work Units WU-038A / WU-038B, Code Boundary.
- `AGENTS.md` — Live Server Principle (no rollback), Test/Code Agent Separation, migration discipline, No Backwards Compatibility.

All mechanics below stay inside the boundaries set by D1–D15. Anything not listed here is explicitly out of scope per §10.

---

## §1 — AC mapping

Each AC is listed with the numbered implementation steps and file paths that realize it. Every step cites the binding decision from synthesis.

### AC1 — Renewing a temporary intent with the current version updates `expires_at`; stale renewal → 412 (`SLICE-020.md:52`)

1. **[D10]** Add `PermissionIntentRenewalRequest` to `services/api/app/contracts/permissions.py` (see §3).
2. **[D10]** Add `expired_at: datetime | None = None` to `_PermissionIntentBase` + companion cross-field validator (see §3).
3. **[D1]** Migration `migrations/versions/wu-038_permission_intent_expiry.py` adds `expired_at TIMESTAMPTZ NULL` + `permission_intents_expired_at_valid` CHECK (see §2).
4. **[D10]** Repository `services/api/app/repositories/permissions.py::fetch_permission_intent` / `insert_permission_intent` / `list_permission_intents` / `update_permission_intent_row` round-trip `expired_at` (see §4).
5. **[D2][D3][D12]** Add `renew_permission_intent()` to `services/api/app/services/permissions.py` with: authority check on `permission_intent.write` at the intent's scope, temporary + active guards, service-layer future-check on `request.expires_at` raising `RenewalExpiresAtInPastError` (R5), and `mutate_entity` with `action_type=INTENT_ACTION_TYPE["renew"]` / `change_type=INTENT_CHANGE_TYPE["renewed"]` and `INTENT_RENEW_PAYLOAD_ALLOWLIST` (see §5).
6. **[D2]** Add `POST /api/v1/permission-intents/{intent_id}/renew` in a new file `services/api/app/api/v1/endpoints/permissions/temporary.py` (see §7). Reuse `parse_if_match_strong()` for 412 mapping; reuse `set_etag()` to emit new version on 200.
7. **[D2]** Register `temporary_router` in `services/api/app/api/v1/endpoints/permissions/__init__.py`.
8. **[D14]** `services/api/tests/test_permission_temporary_api.py` covers success, 412 on stale If-Match, 428 on missing If-Match (mapped by `parse_if_match_strong`), and `expired_at=None` in the renewed response (see §8).

### AC2 — Renewal rejected for non-temporary intents (`SLICE-020.md:53`)

1. **[D2][D10]** Add `NonTemporaryIntentRenewalError(Exception)`, `ExpiredIntentRenewalError(Exception)`, and `RenewalExpiresAtInPastError(Exception)` to `services/api/app/contracts/permissions.py` (see §3).
2. **[D2]** `renew_permission_intent()` raises `NonTemporaryIntentRenewalError` when `current.temporary is False`.
3. **[D2]** `renew_permission_intent()` raises `ExpiredIntentRenewalError` when `current.expired_at is not None` **or** `current.expires_at <= now`.
4. **[D2][R5]** `renew_permission_intent()` raises `RenewalExpiresAtInPastError` when `request.expires_at <= now` — evaluated against the same service-layer `now` used for the active-expired guard, so the two checks are time-consistent.
5. **[D2]** Extend `raise_known_permission_error()` in `services/api/app/api/v1/endpoints/permissions/_shared.py` to map all three errors → `422` with codes `non_temporary_intent`, `expired_intent`, and `renewal_expires_at_in_past` (see §5).
6. **[D14]** `test_permission_temporary_api.py` asserts each 422 code path (see §8).

### AC3 — Expiry worker creates drift entries and remains idempotent (`SLICE-020.md:54`)

1. **[D1]** Migration adds `expired_at`; it is the idempotency key (partial filter `expired_at IS NULL` in the candidate SELECT).
2. **[D4]** `services/api/app/services/permissions.py::expire_temporary_permission_intents(db, *, actor, now, batch_size)` loads candidates via `FOR UPDATE SKIP LOCKED`, processes each inside a per-intent transaction: stamps `expired_at` then writes the drift row.
3. **[D4][D6]** `services/api/app/tasks/permission_expiry.py` exposes `configure_permission_expiry()`, `get_permission_expiry_db()`, and `permission_expiry_worker_tick(*, now=None, batch_size=None)`; the tick delegates to the service function with `actor=ActorIdentity("service", PERMISSION_EXPIRER_ACTOR_ID)` (see §6).
4. **[D7]** Migration seeds `permission-expirer` service actor grant with `permission_intent.write` + `permission_drift.write` at `global` scope.
5. **[D8]** `services/api/app/services/scheduler.py` gains `PERMISSION_EXPIRY_INTERVAL_SECONDS = 60`, `_last_permission_expiry_tick_at: datetime | None = None`, and `_run_permission_expiry_if_due(now)` invoked from `_tick()` (see §6).
6. **[D6]** `services/api/app/tasks/permission_expiry.py::PERMISSION_EXPIRY_BATCH_SIZE = 50`.
7. **[D14]** `services/api/tests/test_permission_temporary_worker.py` asserts: one expiry stamp + one drift row per expired intent, idempotent rerun (counts unchanged), non-temporary skipped, future-expiry skipped, already-expired skipped, batching across multiple ticks (see §8).

### AC4 — Expired intents flow through stable reconciliation path, not inline Discord mutation (`SLICE-020.md:55`)

1. **[D4][D9]** Worker never calls any Discord adapter; only writes `permission_intents.expired_at` and inserts a `permission_drift` row.
2. **[D9]** Drift row carries `permission_intent_id` + `intent_version` from the expired intent, `reconciliation_run_id = NULL`, `status = 'detected'`, `intended_bits`/`intended_allow_bits`/`intended_deny_bits` mirror intent, `actual_bits`/`actual_allow_bits`/`actual_deny_bits` are **NULL** (semantic: "Discord state unknown; operator must reconcile").
3. **[D9]** Drift creation routes through a new service helper `services/api/app/services/permissions.py::_create_expiry_drift()` which emits `mutate_entity(aggregate_type="permission_drift", action_type=DRIFT_ACTION_TYPE["detect_expired"], change_type=DRIFT_CHANGE_TYPE["detected_expired"], …)` with `EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST`. It does **not** perform a per-intent `_require_scoped_authority` check (R3) — the sweep's top-level `permission_intent.write` gate at global scope is the authority boundary, matching SLICE-014's `_record_drift_created` precedent. It runs inside the caller's transaction via `connection=connection` (R1) so the expire-stamp and drift-insert are atomic.
4. **[D9]** The drift is resolvable via the existing `POST /api/v1/permission-drift/{id}/resolve` flows (acknowledge / reconcile / accept) — no new resolution surface is introduced.
5. **[D14]** `test_permission_temporary_worker.py` asserts the drift row is returned by `GET /api/v1/permission-drift?scope_kind=…` alongside reconciliation drift, and that `resolve` transitions continue to work on the expiry drift (see §8).

---

## §2 — Migration plan (`wu_038_permission_intent_expiry`)

File: `migrations/versions/wu-038_permission_intent_expiry.py`.

```python
"""WU-038 add permission_intents.expired_at; seed permission-expirer actor."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wu_038_permission_intent_expiry"
down_revision = "wu_031_read_models"
branch_labels = None
depends_on = None


_EXPIRER_PERMISSIONS = (
    '["permission_intent.write",'
    '"permission_drift.write"]'
)


def upgrade() -> None:
    op.add_column(
        "permission_intents",
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "permission_intents_expired_at_valid",
        "permission_intents",
        "expired_at IS NULL OR expired_at >= expires_at",
    )

    op.execute(
        f"""
        INSERT INTO authority_grants (
            id,
            grantee_id,
            scope_kind,
            scope_id,
            permissions,
            expires_at,
            revoked_at,
            revoked_by,
            revocation_reason,
            predecessor_grant_id
        )
        SELECT
            gen_random_uuid(),
            'permission-expirer',
            'global',
            NULL,
            '{_EXPIRER_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM authority_grants
             WHERE grantee_id = 'permission-expirer'
               AND scope_kind = 'global'
               AND scope_id IS NULL
               AND permissions @> '{_EXPIRER_PERMISSIONS}'::jsonb
               AND permissions <@ '{_EXPIRER_PERMISSIONS}'::jsonb
               AND revoked_at IS NULL
               AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        );
        """
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle.
    pass
```

**Chain.** `wu_031_read_models → wu_038_permission_intent_expiry`. Current head confirmed at `migrations/versions/wu-031_read_models.py:11` ([D13]).

**Seed rationale.** Mirrors `wu-028b_permission_reconciliation_runs.py:127-163` `@>` AND `<@` containment + `expires_at IS NULL` + `revoked_at IS NULL` guard, idempotent via `WHERE NOT EXISTS` ([D7]).

**Index.** No new index is created. The existing `ix_permission_intents__temporary_expires` partial index (`WHERE temporary IS TRUE` — `wu-006a:80`) already narrows candidate rows efficiently; the `expired_at IS NULL` filter sits inside the same partition ([D1] binding implications).

**Constraint rationale.** `expired_at IS NULL OR expired_at >= expires_at` prevents a row from claiming an expiration stamp that predates its own scheduled expiration — keeps the contract-layer `validate_expired_shape` validator and the DB constraint in lockstep ([D1], [D10]).

**Downgrade.** No-op per the Live Server Principle (every recent migration uses a no-op downgrade). The inline comment ties the discipline to AGENTS.md.

---

## §3 — Contracts (`services/api/app/contracts/permissions.py`)

All additions strictly extend the module; nothing existing is renamed, widened, or deleted ([D10], [D15]).

### 3.1 `expired_at` on `_PermissionIntentBase`

```python
class _PermissionIntentBase(_PermissionModel):
    id: UUID
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    reason: str | None = None
    temporary: bool
    expires_at: datetime | None = None
    expired_at: datetime | None = None   # NEW

    # ...existing validators unchanged...

    @model_validator(mode="after")
    def validate_expired_shape(self) -> "_PermissionIntentBase":
        if self.expired_at is not None and self.expires_at is None:
            raise ValueError("expired_at requires expires_at")
        if (
            self.expired_at is not None
            and self.expires_at is not None
            and self.expired_at < self.expires_at
        ):
            raise ValueError("expired_at cannot precede expires_at")
        return self
```

Propagates to `GuildRolePermissionIntent` / `ChannelRolePermissionIntent` (both inherit). `PermissionIntentCreate` and `PermissionIntentUpdate` are **not** widened: only the expiry service path writes `expired_at` ([D10] non-goals).

### 3.2 `PermissionIntentRenewalRequest`

```python
from pydantic import AwareDatetime  # already the pattern in contracts/trust.py

class PermissionIntentRenewalRequest(_PermissionModel):
    expires_at: AwareDatetime
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be non-blank")
        return value
```

Mirrors `PermissionDriftResolutionRequest.reject_blank_reason` ([D2] rationale). `AwareDatetime` is the repo pattern for timezone-aware datetimes (`services/api/app/contracts/trust.py:7`).

**Future-check is NOT at contract layer.** "Future" is defined against the service's `now` (see §5.1). A Pydantic validator using `datetime.now()` uses wall-clock time at parse time, which drifts from the service's `now` and cannot be exercised by tests that inject `now` at service entry. The check is raised as `RenewalExpiresAtInPastError` inside `renew_permission_intent` (see §3.4, §5.1).

### 3.3 `PermissionExpirySweepResult`

```python
class PermissionExpirySweepResult(_PermissionModel):
    expired_intent_ids: list[UUID] = Field(default_factory=list)
    drift_ids: list[UUID] = Field(default_factory=list)
    inspected_count: int = Field(ge=0)
    expired_count: int = Field(ge=0)
    errored_count: int = Field(ge=0)
```

No `originating_actor_*` fields on the request. The manual trigger endpoint takes **no body**; the actor is always the session caller ([D5] spoof-proof).

### 3.4 Renewal error classes

```python
class NonTemporaryIntentRenewalError(Exception):
    def __init__(self, intent_id: UUID) -> None:
        self.intent_id = intent_id
        super().__init__(
            f"permission intent {intent_id} is not temporary and cannot be renewed"
        )


class ExpiredIntentRenewalError(Exception):
    def __init__(self, intent_id: UUID) -> None:
        self.intent_id = intent_id
        super().__init__(
            f"permission intent {intent_id} is already expired and cannot be renewed"
        )


class RenewalExpiresAtInPastError(Exception):
    def __init__(self, intent_id: UUID) -> None:
        self.intent_id = intent_id
        super().__init__(
            f"permission intent {intent_id} renewal requires expires_at in the future"
        )
```

All three map to HTTP 422 via `raise_known_permission_error` with codes `non_temporary_intent`, `expired_intent`, and `renewal_expires_at_in_past` respectively ([D2]).

### 3.5 `__all__` additions

Append to `__all__`: `"PermissionIntentRenewalRequest"`, `"PermissionExpirySweepResult"`, `"NonTemporaryIntentRenewalError"`, `"ExpiredIntentRenewalError"`, `"RenewalExpiresAtInPastError"`.

---

## §4 — Repository (`services/api/app/repositories/permissions.py`)

All changes stay in this file; no schema surface other than `expired_at` is touched ([D1], [D10]).

### 4.1 Round-trip `expired_at`

- `insert_permission_intent()` — append `expired_at` to the `INSERT` column list and `VALUES` tuple (always `NULL` on create — `PermissionIntentCreate` does not expose the field).
- `fetch_permission_intent()` — add `expired_at` to the SELECT list.
- `list_permission_intents()` — add `expired_at` to the SELECT list. Current active-only filter (`expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP`) is unchanged; `expired_at` is orthogonal to active/expired filtering as seen by operators ([D11]).
- `update_permission_intent_row()` — does **not** write `expired_at`. That column is written only through `mark_intent_expired_row` below.
- `_normalize_permission_intent_row()` — include `expired_at` in the normalized dict.

### 4.2 New repository helpers (for expiry worker)

```python
def select_expirable_intents(
    connection: Connection[Any],
    *,
    now: datetime,
    batch_size: int,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """
            SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                   permission_bits, allow_bits, deny_bits, reason,
                   temporary, expires_at, expired_at
            FROM permission_intents
            WHERE temporary = TRUE
              AND expires_at <= %s
              AND expired_at IS NULL
            ORDER BY expires_at ASC, id ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (now, batch_size),
        ).fetchall()
    return [_normalize_permission_intent_row(row) for row in rows]


def mark_intent_expired_row(
    connection: Connection[Any],
    *,
    intent_id: UUID,
    expired_at: datetime,
) -> int:
    cursor = connection.execute(
        """
        UPDATE permission_intents
           SET expired_at = %s
         WHERE id = %s
           AND expired_at IS NULL
        """,
        (expired_at, intent_id),
    )
    return cursor.rowcount
```

`FOR UPDATE SKIP LOCKED` provides non-blocking job-queue claim semantics ([D4], [D6]). The `expired_at IS NULL` predicate inside `mark_intent_expired_row` is a defense-in-depth guard against duplicate marking if two sweeps race past the SELECT.

---

## §5 — Service layer (`services/api/app/services/permissions.py`)

### 5.1 Renewal — `renew_permission_intent()`

```python
def renew_permission_intent(
    db: PostgresDatabase,
    intent_id: UUID,
    *,
    expected_version: int,
    request: PermissionIntentRenewalRequest,
    actor: ActorIdentity,
) -> tuple[Any, MutationResult]:
    with db.connection() as connection:
        current_row = permission_repo.fetch_permission_intent(connection, intent_id)
    if current_row is None:
        raise PermissionIntentNotFoundError(intent_id)
    current = PermissionIntentRead.model_validate(current_row)

    _require_scoped_authority(
        "permission_intent.write",
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
        actor=actor,
        db=db,
    )

    if not current.temporary:
        raise NonTemporaryIntentRenewalError(intent_id)
    now = datetime.now(tz=UTC)
    if current.expired_at is not None or (
        current.expires_at is not None and current.expires_at <= now
    ):
        raise ExpiredIntentRenewalError(intent_id)
    if request.expires_at <= now:
        raise RenewalExpiresAtInPastError(intent_id)

    validated_patch = {"expires_at": request.expires_at}
    updated = validated_update(current, validated_patch)
    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
        role_id=current.role_id,
        channel_id=getattr(current, "channel_id", None),
    )

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = _to_permission_intent_row(updated)
        updated_count = permission_repo.update_permission_intent_row(
            connection, intent_id=intent_id, row=row,
        )
        if updated_count != 1:
            raise PermissionIntentNotFoundError(intent_id)
        return StateChangeDraft(
            change_type=INTENT_CHANGE_TYPE["renewed"],
            payload_json=updated.model_dump(mode="json"),
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_intent",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/permission-intents/{intent_id}/renew",
            reason_text=request.reason,
        ),
        action_type=INTENT_ACTION_TYPE["renew"],
        action_payload={
            "new_expires_at": request.expires_at.isoformat(),
            "reason": request.reason,
        },
        payload_allowlist=INTENT_RENEW_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
    )
    return read_permission_intent(db, intent_id), result
```

Checks in order: (1) authority at the intent's scope, (2) temporary-only, (3) not already expired (either `expired_at` stamped or `expires_at` in the past relative to service `now`), (4) the new `request.expires_at` must itself be in the future relative to the same `now` — raising `RenewalExpiresAtInPastError` keeps the check time-consistent with the existing-expiry guard and does not depend on wall-clock at contract-parse time (R5). OCC is enforced by `mutate_entity`'s `expected_version` → `StaleMutationError` (already mapped to 412 by `raise_known_permission_error`). No new mapping code needed for AC1's 412 path.

### 5.2 Expiry — `expire_temporary_permission_intents()` + `_create_expiry_drift()`

```python
def expire_temporary_permission_intents(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    now: datetime,
    batch_size: int,
    source: str = "worker_sweep",
) -> PermissionExpirySweepResult:
    _require_scoped_authority(
        "permission_intent.write",
        scope_kind="global",
        scope_id=None,
        actor=actor,
        db=db,
    )

    with db.connection() as connection:
        candidates = permission_repo.select_expirable_intents(
            connection, now=now, batch_size=batch_size,
        )

    inspected = len(candidates)
    expired_ids: list[UUID] = []
    drift_ids: list[UUID] = []
    errored = 0

    for row in candidates:
        intent = PermissionIntentRead.model_validate(row)
        try:
            expired_intent, drift = _expire_single_intent(
                db, intent=intent, actor=actor, now=now, source=source,
            )
        except StaleMutationError:
            # R6: expected control-flow race — another mutation advanced the
            # head between candidate SELECT and our `mutate_entity`. Next
            # tick re-selects because `expired_at` is still NULL.
            logger.debug(
                "permission expiry: OCC conflict on intent %s; retry next tick",
                intent.id,
            )
            continue
        except Exception:
            logger.exception(
                "permission-expiry failed for intent %s", intent.id,
            )
            errored += 1
            continue
        expired_ids.append(expired_intent.id)
        drift_ids.append(drift.id)

    return PermissionExpirySweepResult(
        expired_intent_ids=expired_ids,
        drift_ids=drift_ids,
        inspected_count=inspected,
        expired_count=len(expired_ids),
        errored_count=errored,
    )


def _expire_single_intent(
    db: PostgresDatabase,
    *,
    intent: Any,
    actor: ActorIdentity,
    now: datetime,
    source: str,
) -> tuple[Any, PermissionDriftRead]:
    aggregate_id = build_permission_intent_aggregate_id(
        scope_kind=intent.scope_kind,
        scope_id=intent.scope_id,
        role_id=intent.role_id,
        channel_id=getattr(intent, "channel_id", None),
    )

    # R1: single transaction spanning BOTH mutate_entity calls. If the drift
    # mutation fails for any reason, the expired_at stamp rolls back with it
    # and the candidate is re-selected on the next tick. Pattern mirrors
    # `submit_reconciliation_snapshot` in permission_reconciliation.py:674-694.
    with db.transaction() as connection:
        expected_version = _read_intent_head_version(
            connection, aggregate_id=aggregate_id, intent_id=intent.id,
        )

        def mutate_projection_expire(active: Connection[Any]) -> StateChangeDraft:
            updated_count = permission_repo.mark_intent_expired_row(
                active, intent_id=intent.id, expired_at=now,
            )
            if updated_count != 1:
                raise PermissionIntentNotFoundError(intent.id)
            updated = intent.model_copy(update={"expired_at": now})
            return StateChangeDraft(
                change_type=INTENT_CHANGE_TYPE["expired"],
                payload_json=updated.model_dump(mode="json"),
            )

        expire_result = mutate_entity(
            db=db,
            aggregate_type="permission_intent",
            aggregate_id=aggregate_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface="worker:permission_expiry",
            ),
            action_type=INTENT_ACTION_TYPE["expire"],
            action_payload={
                "expired_at": now.isoformat(),
                "source": source,
            },
            payload_allowlist=INTENT_EXPIRE_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection_expire,
            scope_kind=intent.scope_kind,
            scope_id=intent.scope_id,
            connection=connection,
        )

        drift = _create_expiry_drift(
            db,
            connection=connection,
            intent=intent,
            intent_version_after_expire=expire_result.version,
            actor=actor,
            now=now,
        )
    # Commit happens on `with` exit. Reading back the intent + drift is a
    # read-only op outside the tx.
    expired_intent = read_permission_intent(db, intent.id)
    return expired_intent, drift


def _create_expiry_drift(
    db: PostgresDatabase,
    *,
    connection: Connection[Any],
    intent: Any,
    intent_version_after_expire: int,
    actor: ActorIdentity,
    now: datetime,
) -> PermissionDriftRead:
    # R3: NO per-intent `_require_scoped_authority` here. The sweep's
    # top-level authority check already gates the operation at global scope,
    # matching SLICE-014's `_record_drift_created` precedent
    # (permission_reconciliation.py:581-639) which performs no per-scope
    # authority check either. A chapter-scoped check here would fail because
    # the `permission-expirer` service actor only holds a global grant; the
    # authority model is flat (authority.py:238 requires exact scope_kind
    # match).
    drift = PermissionDriftRead.model_validate({
        "id": uuid4(),
        "permission_intent_id": intent.id,
        "intent_version": intent_version_after_expire,
        "scope_kind": intent.scope_kind,
        "scope_id": intent.scope_id,
        "role_id": intent.role_id,
        "channel_id": getattr(intent, "channel_id", None),
        "kind": intent.kind,
        "reconciliation_run_id": None,
        "intended_bits": getattr(intent, "permission_bits", None),
        "intended_allow_bits": getattr(intent, "allow_bits", None),
        "intended_deny_bits": getattr(intent, "deny_bits", None),
        "actual_bits": None,
        "actual_allow_bits": None,
        "actual_deny_bits": None,
        "status": "detected",
        "detected_at": now,
    })

    # R8 lean action_payload: only the identifying + scope keys, no bit masks.
    # Mirrors `_record_drift_created`'s split between action_payload (lean)
    # and payload_json (full).
    action_payload = {
        "drift_id": str(drift.id),
        "permission_intent_id": str(intent.id),
        "intent_version": intent_version_after_expire,
        "scope_kind": intent.scope_kind,
        "scope_id": intent.scope_id,
        "role_id": intent.role_id,
        "channel_id": getattr(intent, "channel_id", None),
        "kind": intent.kind,
        "status": "detected",
    }

    def mutate_projection_drift(active: Connection[Any]) -> StateChangeDraft:
        permission_repo.insert_permission_drift(
            active, row=_to_permission_drift_row(drift),
        )
        return StateChangeDraft(
            change_type=DRIFT_CHANGE_TYPE["detected_expired"],
            payload_json=drift.model_dump(mode="json"),
        )

    mutate_entity(
        db=db,
        aggregate_type="permission_drift",
        aggregate_id=str(drift.id),
        request=_make_request(
            expected_version=0,
            actor=actor,
            request_surface="worker:permission_expiry",
        ),
        action_type=DRIFT_ACTION_TYPE["detect_expired"],
        action_payload=action_payload,
        payload_allowlist=EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection_drift,
        scope_kind=intent.scope_kind,
        scope_id=intent.scope_id,
        connection=connection,
    )
    return drift


def _read_intent_head_version(
    connection: Connection[Any],
    *,
    aggregate_id: str,
    intent_id: UUID,
) -> int:
    """R4: Load the head version for a `permission_intent` aggregate from
    `aggregate_heads`. Uses the composite `aggregate_id` built by
    `build_permission_intent_aggregate_id` — NOT the raw intent UUID (which
    is the row id, not the aggregate id). Runs inside the caller's
    transaction so the read is consistent with the subsequent
    `mutate_entity` call."""
    row = connection.execute(
        """
        SELECT current_seq
          FROM aggregate_heads
         WHERE aggregate_type = 'permission_intent'
           AND aggregate_id = %s
        """,
        (aggregate_id,),
    ).fetchone()
    if row is None:
        raise PermissionIntentNotFoundError(intent_id)
    return int(row[0])
```

**Per-intent transaction boundary (R1).** `_expire_single_intent` opens a **single** `db.transaction()` and threads that connection into both `mutate_entity` calls via `connection=connection`. Both audit rows (`permission_intent.expire` action + `permission_drift.detect_expired` action), both state-change rows (`permission_intent.expired`, `permission_drift.detected_expired`), and both projection writes (`mark_intent_expired_row`, `insert_permission_drift`) either commit together or roll back together. Partial failure is impossible — the previous two-transaction design left an intent stamped expired with no drift row, which the `expired_at IS NULL` candidate filter then permanently skipped.

This is a deliberate departure from `evaluate_ticket_sla`'s single-batch-tx shape (`services/api/app/services/ticket_sla.py:516-558` wraps the entire for-loop in one tx). Per-intent tx here is justified by (a) R1 atomicity between expire-stamp and drift-insert for a single intent, and (b) preventing one poison-pill intent from rolling back the whole batch. Precedent for the shared-connection threading: `permission_reconciliation.py::submit_reconciliation_snapshot` at lines 674-694 and `_record_drift_created` at line 638.

**Concurrency guarantees after R1.** Single-expiry is guaranteed by **OCC on `aggregate_heads`** (first worker's `mutate_entity` bumps `current_seq`; second worker's expected_version read plus `get_head_for_update` inside `mutate_entity` detects the mismatch and raises `StaleMutationError`, caught at debug per R6) **plus** the `expired_at IS NULL` predicate in `mark_intent_expired_row` (defense-in-depth if anything bypasses OCC). `FOR UPDATE SKIP LOCKED` in `select_expirable_intents` is a minor latency-contention optimization — the row locks release when the candidate-SELECT connection returns to the pool — not a primary idempotency layer.

### 5.3 Error mapping (`services/api/app/api/v1/endpoints/permissions/_shared.py`)

Extend `raise_known_permission_error`:

```python
from app.contracts.permissions import (
    ExpiredIntentRenewalError,
    NonTemporaryIntentRenewalError,
    RenewalExpiresAtInPastError,
    # ...existing imports...
)

if isinstance(error, NonTemporaryIntentRenewalError):
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={
            "code": "non_temporary_intent",
            "message": str(error),
            "intent_id": str(error.intent_id),
        },
    ) from error
if isinstance(error, ExpiredIntentRenewalError):
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={
            "code": "expired_intent",
            "message": str(error),
            "intent_id": str(error.intent_id),
        },
    ) from error
if isinstance(error, RenewalExpiresAtInPastError):
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={
            "code": "renewal_expires_at_in_past",
            "message": str(error),
            "intent_id": str(error.intent_id),
        },
    ) from error
```

Placed **before** the generic `PermissionError` / `InvalidPermissionIntentError` fallbacks so the specific codes win.

### 5.4 Logger

Add `logger = logging.getLogger(__name__)` to `services/api/app/services/permissions.py` if not already present (used by the per-intent `logger.exception` in §5.2).

---

## §6 — Worker + scheduler integration

### 6.1 `services/api/app/tasks/permission_expiry.py` (new file)

```python
from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.permissions import PermissionExpirySweepResult
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.mutations import StaleMutationError
from app.services.permissions import (
    PERMISSION_EXPIRER_ACTOR_ID,
    expire_temporary_permission_intents,
)


logger = logging.getLogger(__name__)

PERMISSION_EXPIRY_BATCH_SIZE: int = 50

_DB: PostgresDatabase | None = None


def configure_permission_expiry(*, db: PostgresDatabase) -> None:
    global _DB
    _DB = db


def get_permission_expiry_db() -> PostgresDatabase:
    global _DB
    if _DB is None:
        _DB = PostgresDatabase()
    return _DB


def _expirer_service_actor() -> ActorIdentity:
    return ActorIdentity(actor_kind="service", actor_id=PERMISSION_EXPIRER_ACTOR_ID)


def _root_audit_context() -> AuditContextRead:
    """R2: Scheduler-thread root audit context. Mirrors
    `services/api/app/services/ticket_sla.py::_root_audit_context` verbatim.
    Without this, `mutate_entity` raises `MissingCorrelationContextError`
    because `contextvars` do not propagate into the `asyncio.to_thread`
    worker that invokes this tick."""
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def permission_expiry_worker_tick(
    *,
    now: datetime | None = None,
    batch_size: int | None = None,
) -> PermissionExpirySweepResult | None:
    """R2 + R6. Install root audit context when none exists (scheduler
    thread path); reuse the ambient one if present (test / manual-trigger
    paths). Surface `StaleMutationError` at debug — it is expected control
    flow (SLICE-017 MAJOR 4 precedent). Log everything else via
    `logger.exception`."""
    existing_ctx = get_current_audit_context()
    ambient = (
        use_audit_context(_root_audit_context())
        if existing_ctx is None
        else nullcontext()
    )
    with ambient:
        try:
            return expire_temporary_permission_intents(
                get_permission_expiry_db(),
                actor=_expirer_service_actor(),
                now=now or datetime.now(tz=UTC),
                batch_size=batch_size or PERMISSION_EXPIRY_BATCH_SIZE,
                source="worker_sweep",
            )
        except StaleMutationError:
            logger.debug("permission expiry: OCC conflict, retry next tick")
            return None
        except Exception:
            logger.exception("permission expiry worker tick failed")
            return None
```

Shape matches `services/api/app/tasks/ticket_sla.py` ([D4] binding implications), with the audit-context install moved here from the service layer because the scheduler's `asyncio.to_thread` hand-off (§6.3 line 706) breaks `contextvars` propagation; the manual endpoint path (§7.1) is unaffected because FastAPI's `CorrelationMiddleware` already installed a context per request.

### 6.2 `services/api/app/tasks/__init__.py`

Wire into `configure_task_runtime`:

```python
from app.tasks.permission_expiry import configure_permission_expiry
# ...
def configure_task_runtime(...):
    # ...existing wiring...
    configure_ticket_sla(db=db)
    configure_permission_expiry(db=db)   # NEW
```

### 6.3 `services/api/app/services/scheduler.py`

Module-level constant:

```python
PERMISSION_EXPIRY_INTERVAL_SECONDS = 60
```

`SchedulerLoop.__init__` gains `self._last_permission_expiry_tick_at: datetime | None = None`.

New method, mirroring `_run_ticket_sla_if_due`:

```python
async def _run_permission_expiry_if_due(self, now: datetime) -> None:
    if (
        self._last_permission_expiry_tick_at is not None
        and (now - self._last_permission_expiry_tick_at).total_seconds()
        < PERMISSION_EXPIRY_INTERVAL_SECONDS
    ):
        return

    from app.tasks.permission_expiry import permission_expiry_worker_tick

    self._last_permission_expiry_tick_at = now
    try:
        await asyncio.to_thread(permission_expiry_worker_tick, now=now)
    except Exception:
        logger.exception(
            "permission-expiry worker tick failed for worker %s",
            self._worker_id,
        )
```

Invoked from `_tick()` after `_run_read_model_tick_if_due(now)`:

```python
await self._run_permission_expiry_if_due(now)
```

Add `"PERMISSION_EXPIRY_INTERVAL_SECONDS"` to the module `__all__` ([D8]).

---

## §7 — Endpoints

### 7.1 New file: `services/api/app/api/v1/endpoints/permissions/temporary.py`

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field

from app.contracts.actor import ActorIdentity
from app.contracts.permissions import (
    ChannelRolePermissionIntent,
    GuildRolePermissionIntent,
    PermissionExpirySweepResult,
    PermissionIntentRenewalRequest,
)
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.permissions import (
    PERMISSION_EXPIRY_MANUAL_DEFAULT_BATCH_SIZE,
    expire_temporary_permission_intents,
    renew_permission_intent,
)

from ._shared import (
    get_db,
    parse_if_match_strong,
    raise_known_permission_error,
    require_scoped,
    set_etag,
)


PermissionIntentReadResponse = Annotated[
    GuildRolePermissionIntent | ChannelRolePermissionIntent,
    Field(discriminator="kind"),
]


router = APIRouter(prefix="/api/v1/permission-intents")


@router.post("/{intent_id}/renew", response_model=PermissionIntentReadResponse)
def renew_intent_endpoint(
    intent_id: UUID,
    body: PermissionIntentRenewalRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> Any:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = renew_permission_intent(
            db,
            intent_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.post("/expire/run", response_model=PermissionExpirySweepResult)
def run_permission_expiry_endpoint(
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionExpirySweepResult:
    try:
        require_scoped(
            actor, db, "global", None, "permission_intent.write",
        )
        return expire_temporary_permission_intents(
            db,
            actor=actor,
            now=datetime.now(tz=UTC),
            batch_size=PERMISSION_EXPIRY_MANUAL_DEFAULT_BATCH_SIZE,
            source="manual_trigger",
        )
    except Exception as error:
        raise_known_permission_error(error)
```

Notes:
- Endpoint-level `require_scoped(...)` on the manual trigger matches the belt-and-braces shape used by `intents.py` for write endpoints ([D5]).
- Renewal endpoint does **not** call `require_scoped` at the endpoint — authority requires knowing the intent's scope, which is discovered inside `renew_permission_intent`. This mirrors the service-side check the `patch_intent_endpoint` already relies on after the scope read ([D3]).
- No body on `POST /expire/run` — spoof-proof ([D5] binding implications).

### 7.2 Router registration: `services/api/app/api/v1/endpoints/permissions/__init__.py`

```python
from .temporary import router as temporary_router
# ...
permissions_router = APIRouter()
permissions_router.include_router(intents.router)
permissions_router.include_router(drift.router)
permissions_router.include_router(reconciliation.router)
permissions_router.include_router(temporary_router)   # NEW
```

### 7.3 Error mapping coverage

All error paths are handled by `raise_known_permission_error`:

| Failure | HTTP | Source |
|---|---|---|
| Intent not found | 404 | `PermissionIntentNotFoundError` |
| Stale `If-Match` | 412 | `StaleMutationError` |
| Missing/weak `If-Match` | 428 / 412 | `parse_if_match_strong` |
| Renewal of non-temporary | 422 `non_temporary_intent` | `NonTemporaryIntentRenewalError` |
| Renewal of expired | 422 `expired_intent` | `ExpiredIntentRenewalError` |
| Renewal `expires_at` not in future | 422 `renewal_expires_at_in_past` | `RenewalExpiresAtInPastError` |
| Blank reason | 422 (Pydantic) | FastAPI body validation |
| Authority denied | 403 | `PermissionError` |

---

## §8 — Tests

Per-test docstring format: first line is the AC tag (`AC1`, `AC2`, `AC3`, `AC4`) followed by a one-sentence description. The test agent writes from contracts + synthesis decisions only; the code agent implements ([AGENTS.md §Implementation Workflow]).

### 8.1 `services/api/tests/test_permission_temporary_api.py` — WU-038A (AC1, AC2)

```python
def test_renew_temporary_intent_with_current_version_advances_expires_at(...):
    """AC1: renew temporary intent with current version updates expires_at
    and advances aggregate version."""

def test_renew_with_stale_if_match_returns_412(...):
    """AC1: renew with stale If-Match returns 412 Precondition Failed."""

def test_renew_with_missing_if_match_returns_428(...):
    """AC1: renew without If-Match returns 428 Precondition Required."""

def test_renew_non_temporary_intent_returns_422_non_temporary(...):
    """AC2: renewal rejected for non-temporary intent with code
    'non_temporary_intent'."""

def test_renew_already_expired_by_expires_at_returns_422_expired(...):
    """AC1: renew intent whose expires_at has passed returns 422 with
    code 'expired_intent'."""

def test_renew_already_expired_by_expired_at_returns_422_expired(...):
    """AC1: renew intent whose expired_at is set returns 422 with code
    'expired_intent'."""

def test_renew_with_past_expires_at_body_returns_422_renewal_expires_at_in_past(...):
    """AC1: renew request with past expires_at is rejected at the service
    layer with code 'renewal_expires_at_in_past' (R5: future-check uses the
    service's `now`, not wall-clock at Pydantic parse time)."""

def test_renew_with_blank_reason_returns_422_validation(...):
    """AC1: renew request with blank reason rejected at Pydantic layer."""

def test_renew_without_permission_intent_write_returns_403(...):
    """AC1: actor lacking permission_intent.write at intent scope gets 403."""

def test_renew_response_exposes_expired_at_null(...):
    """AC1: renewed intent read response includes expired_at: null."""

def test_renew_emits_renew_audit_verbs_with_allowlisted_payload(...):
    """AC1: renewal emits permission_intent.renew action and
    permission_intent.renewed change with payload limited to
    INTENT_RENEW_PAYLOAD_ALLOWLIST."""
```

### 8.2 `services/api/tests/test_permission_temporary_worker.py` — WU-038B (AC3, AC4)

```python
def test_worker_marks_expired_intents_and_creates_drift_rows(...):
    """AC3: worker stamps expired_at on temporary intents past expires_at
    and creates one drift row per expired intent."""

def test_worker_is_idempotent_on_rerun(...):
    """AC3: running worker a second time against the same candidates does
    not write a second expired_at or create a second drift row."""

def test_worker_skips_non_temporary_intents(...):
    """AC3: non-temporary intents are never selected regardless of timing."""

def test_worker_skips_future_expires_at_intents(...):
    """AC3: temporary intents with expires_at > now are not selected."""

def test_worker_skips_already_expired_intents(...):
    """AC3: intents with expired_at IS NOT NULL are not re-selected."""

def test_expiry_drift_row_shape_matches_d9(...):
    """AC4: drift row has permission_intent_id set, intent_version set,
    reconciliation_run_id NULL, actual_* NULL, intended_* mirrors intent,
    status='detected'."""

def test_expiry_drift_is_listable_via_get_permission_drift(...):
    """AC4: GET /api/v1/permission-drift?scope_kind=... returns expiry drift
    alongside reconciliation drift."""

def test_expiry_drift_resolvable_via_existing_resolve_endpoint(...):
    """AC4: POST /api/v1/permission-drift/{id}/resolve works on expiry drift
    for acknowledge / reconcile / accept actions."""

def test_worker_batch_size_bounds_per_tick_work(...):
    """AC3: a candidate set larger than PERMISSION_EXPIRY_BATCH_SIZE drains
    across multiple ticks with no candidate processed twice."""

def test_concurrent_sweeps_do_not_duplicate_via_for_update_skip_locked(...):
    """AC3: two concurrent expiry sweeps processing overlapping candidates
    result in each intent expired exactly once."""

def test_per_intent_failure_does_not_abort_batch(...):
    """AC3: a synthetic failure on one intent does not abort the batch;
    remaining intents still expire; failed intent retried on next tick."""

def test_manual_trigger_returns_sweep_result_with_counts(...):
    """AC3: POST /api/v1/permission-intents/expire/run returns
    PermissionExpirySweepResult with accurate expired_count + drift_ids."""

def test_manual_trigger_requires_global_permission_intent_write(...):
    """AC3: caller without permission_intent.write at global scope gets 403."""

def test_manual_trigger_accepts_no_body_so_actor_cannot_be_spoofed(...):
    """AC3: manual trigger endpoint defines no body params; any posted
    originating-actor override is ignored — audit rows show the session
    caller."""

def test_worker_emits_expire_and_detect_expired_audit_verbs(...):
    """AC3: each expired intent emits one permission_intent.expire action
    with INTENT_EXPIRE_PAYLOAD_ALLOWLIST payload ({expired_at, source}),
    one permission_intent.expired state change, one
    permission_drift.detect_expired action with
    EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST payload, and one
    permission_drift.detected_expired state change — all four rows
    committed under the same correlation_id in a single transaction (R1,
    R2, R7, R9)."""

def test_worker_installs_root_audit_context_when_invoked_from_scheduler_thread(...):
    """AC3 (R2): invoking permission_expiry_worker_tick with no ambient
    audit context does not raise MissingCorrelationContextError; produced
    activity_actions rows all share one correlation_id per tick."""

def test_worker_expire_and_drift_are_atomic_on_failure(...):
    """AC3 (R1): if the drift insert raises, the expired_at stamp rolls
    back and the intent is re-selected on the next tick. No orphaned
    expired_at rows."""

def test_worker_stale_mutation_collision_is_logged_at_debug_not_errored(...):
    """AC3 (R6): a concurrent PATCH that advances the intent version
    between candidate SELECT and mutate_entity produces a
    StaleMutationError that is logged at debug, not exception, and does
    NOT increment errored_count on the sweep result."""

def test_worker_expires_chapter_scoped_intent_without_authority_failure(...):
    """AC3 (R3): a chapter-scoped temporary intent is expired by a
    permission-expirer service actor holding only a global grant. No
    per-drift scope authority check obstructs the sweep."""
```

**Test harness patterns**: `httpx.AsyncClient` + DB fixtures as in existing `test_permission_intents.py`; `now` injected at service entry points (no `time.sleep`); `PERMISSION_EXPIRY_BATCH_SIZE` monkey-patched via `monkeypatch.setattr(tasks.permission_expiry, ...)` to exercise multi-batch drains ([D14] binding implications).

**Fixtures not required**: no Discord adapter fixtures — AC4 specifies the stable reconciliation path is the Discord surface, not this slice ([D14] non-goals).

---

## §9 — Constants

All literals that span service / repository / test / endpoint code are hoisted to named constants. No magic strings anywhere in the slice.

### 9.1 `services/api/app/services/permissions.py`

```python
PERMISSION_EXPIRER_ACTOR_ID: str = "permission-expirer"
PERMISSION_EXPIRY_MANUAL_DEFAULT_BATCH_SIZE: int = 50

# R7: audit verbs hoisted to constants-dict dispatch, matching the pattern of
# SLICE-014's DRIFT_RESOLUTION_ACTION_TYPE / DRIFT_RESOLUTION_CHANGE_TYPE at
# permissions.py:72-81. Every mutate_entity call site routes through these
# dicts — no inline action_type / change_type strings in the slice.
INTENT_ACTION_TYPE: dict[str, str] = {
    "renew": "permission_intent.renew",
    "expire": "permission_intent.expire",
}
INTENT_CHANGE_TYPE: dict[str, str] = {
    "renewed": "permission_intent.renewed",
    "expired": "permission_intent.expired",
}
# R9: distinct change_type for expiry-originated drift so operators can
# filter audit rows by origin (reconciliation-driven drift still emits
# `permission_drift.created`). Synthesis D12's "reused permission_drift.detected"
# was factually incorrect — reconciliation's shipped change_type is
# `permission_drift.created`, not `.detected`.
DRIFT_ACTION_TYPE: dict[str, str] = {
    "detect_expired": "permission_drift.detect_expired",
}
DRIFT_CHANGE_TYPE: dict[str, str] = {
    "detected_expired": "permission_drift.detected_expired",
}

# R8: allowlists narrowed to field-specific keys. No wildcards; no mirroring
# of the whole request. For `permission_intent` aggregates the aggregate_id
# is the composite built by `build_permission_intent_aggregate_id`, so
# `intent_id` / row UUID is not in the action_payload (and therefore not in
# the allowlist). For `permission_drift`, the aggregate_id IS `drift_id`,
# which is included in the action_payload for cross-reference.
INTENT_RENEW_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "new_expires_at", "reason",
})
INTENT_EXPIRE_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "expired_at", "source",  # source ∈ {"worker_sweep", "manual_trigger"}
})
EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({
    "drift_id",
    "permission_intent_id",
    "intent_version",
    "scope_kind",
    "scope_id",
    "role_id",
    "channel_id",
    "kind",
    "status",
})
```

### 9.2 `services/api/app/tasks/permission_expiry.py`

```python
PERMISSION_EXPIRY_BATCH_SIZE: int = 50
```

### 9.3 `services/api/app/services/scheduler.py`

```python
PERMISSION_EXPIRY_INTERVAL_SECONDS: int = 60
```

### 9.4 Audit verbs (dispatched via the constants dicts in §9.1)

| Dict lookup | Resolved string | Call site |
|---|---|---|
| `INTENT_ACTION_TYPE["renew"]` | `permission_intent.renew` | `renew_permission_intent` |
| `INTENT_CHANGE_TYPE["renewed"]` | `permission_intent.renewed` | `renew_permission_intent` |
| `INTENT_ACTION_TYPE["expire"]` | `permission_intent.expire` | `_expire_single_intent` |
| `INTENT_CHANGE_TYPE["expired"]` | `permission_intent.expired` | `_expire_single_intent` |
| `DRIFT_ACTION_TYPE["detect_expired"]` | `permission_drift.detect_expired` | `_create_expiry_drift` |
| `DRIFT_CHANGE_TYPE["detected_expired"]` | `permission_drift.detected_expired` | `_create_expiry_drift` |

R7: every `mutate_entity` call site dereferences one of these dicts — no inline strings, no f-string generation. R9: the expiry-drift `change_type` is distinct from reconciliation's `permission_drift.created`, so audit readers can filter expiry-origin drift without joining to `permission_intent_id` IS NOT NULL. The **payload allowlists** (§9.1) ensure these verbs emit stable, audit-legible payloads ([D12]).

---

## §10 — Out of scope (explicit)

Per synthesis **D15**, the following MUST NOT be added in this slice. Any risk / hookpoint / implementation phase flagging these is treated as scope creep:

1. Auto-reconciliation of expired intents against Discord (operators continue to trigger reconciliation via existing flow).
2. Expiry notifications / alerts via SLICE-015 consumer hooks.
3. Time-travel or historical "was-expired-when" views.
4. Bulk renewal endpoint.
5. Scope-filtered expiry (worker remains global).
6. Chapter-scoped authority on `POST /expire/run` (stays global).
7. Backpressure / circuit-breaker around the worker beyond per-intent `try/except logger.exception`.
8. `permission_intent.status` column or FSM.
9. Widening `PermissionIntentUpdate` with `expired_at`.
10. Reconciliation-run-scoped dedupe for expiry drift (expiry drift carries `reconciliation_run_id = NULL` by contract).
11. UI / frontend consumers — contract-only surface.
12. New permission namespace (`permission_intent.renew` / `permission_intent.expire` as **permissions**; authority remains `permission_intent.write` + `permission_drift.write`).
13. Any new index on `permission_intents.expired_at`.
14. Any changes to reconciliation drift shapes or `_build_drift_rows` in `permission_reconciliation.py`.

---

## Guardrails

- **SLICE-014 patterns.** Service-layer authority (`_require_scoped_authority`), constants dispatch (allowlists), `@>` AND `<@` containment in seed, spoof-proof originating actor (`POST /expire/run` takes no body).
- **Migration.** Single migration `wu_038_permission_intent_expiry`; downgrade is no-op per Live Server Principle; seed is idempotent via `WHERE NOT EXISTS` + containment.
- **No magic strings.** Every audit verb, allowlist, actor id, batch size, interval is a named constant at module level.
- **Per-test AC docstring.** Each test begins with `"""ACn: ...` — binding for the test agent.
- **Concurrent worker safety.** Primary guard is **OCC on `aggregate_heads`** (any concurrent mutation that bumps the intent's `current_seq` causes the second worker's `mutate_entity` to raise `StaleMutationError`, caught at `debug` per R6 and retried next tick) plus the **`expired_at IS NULL` predicate in `mark_intent_expired_row`** (defense-in-depth). `FOR UPDATE SKIP LOCKED` in `select_expirable_intents` is a contention-latency optimization; the row locks release when the candidate-SELECT connection returns to the pool, so it is not an idempotency layer on its own.
- **Per-intent atomicity (R1).** Expire stamp + drift insert + both audit rows + both state-change rows commit inside a single `db.transaction()` per intent. Partial failure rolls back the expire stamp, and the candidate is re-selected on the next tick. No "expired_at with no drift row" failure mode.
- **Worker audit context (R2).** `permission_expiry_worker_tick` installs `use_audit_context(_root_audit_context())` when no ambient context exists, so the scheduler's `asyncio.to_thread` hand-off does not break `mutate_entity`'s `MissingCorrelationContextError` guard. Every audit row emitted in one tick shares one `correlation_id`.
- **No new abstractions.** No registries, no generic "lifecycle engine", no refactor of `update_permission_intent`. Only what AC1–AC4 demand.
- **Test/Code agent separation.** Test files are written from contracts + this proposal; code files from contracts + tests (AGENTS.md §Implementation Workflow).
- **No backwards-compatibility shims.** New columns, new endpoints, new audit verbs. Existing callers unchanged.

---

## 5-bullet summary

- **Migration `wu_038_permission_intent_expiry`** adds `permission_intents.expired_at TIMESTAMPTZ NULL` + `permission_intents_expired_at_valid` CHECK + idempotent seed of `permission-expirer` service actor with `permission_intent.write` + `permission_drift.write` at global scope; downgrade is no-op.
- **Renewal (WU-038A)** ships as `POST /api/v1/permission-intents/{intent_id}/renew` via a new `temporary.py` endpoint + `renew_permission_intent()` service function that enforces authority, temporary-only, active-only, service-layer future-check on `request.expires_at` (R5), non-blank `reason`, and `If-Match` OCC; emits audit verbs routed through `INTENT_ACTION_TYPE["renew"]` / `INTENT_CHANGE_TYPE["renewed"]` (R7) with the narrow `INTENT_RENEW_PAYLOAD_ALLOWLIST = {"new_expires_at", "reason"}` (R8).
- **Expiry worker (WU-038B)** ships as `services/api/app/tasks/permission_expiry.py` + `expire_temporary_permission_intents()` service, wired into `SchedulerLoop` at 60-second intervals with 50-row batches. `permission_expiry_worker_tick` installs a root audit context when none exists (R2) and catches `StaleMutationError` at `debug` (R6). `_expire_single_intent` opens **one** `db.transaction()` per candidate and threads its `connection` into both `mutate_entity` calls (R1) so the expire-stamp and drift-insert are atomic. The drift helper does **not** perform a per-intent authority check (R3); the sweep's top-level `permission_intent.write` at global scope is the sole authority gate. The head-version read uses `_read_intent_head_version(aggregate_id, …)` against `aggregate_heads` with the composite aggregate id built by `build_permission_intent_aggregate_id` (R4). Discord is never called.
- **Expiry drift shape (D9)** carries `permission_intent_id`, `intent_version`, intended_* mirroring intent, `actual_* = NULL`, `reconciliation_run_id = NULL`, `status = 'detected'`, emitted via new verbs `DRIFT_ACTION_TYPE["detect_expired"]` → `DRIFT_CHANGE_TYPE["detected_expired"]` (R9 distinguishes expiry-origin drift from reconciliation's `permission_drift.created`). Action-payload uses the lean `EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST` (R8: 9 keys, no bit masks); bit masks live only in `StateChangeDraft.payload_json`, matching `_record_drift_created`'s split. Resolves through the existing `POST /permission-drift/{id}/resolve` flows, satisfying AC4's "stable reconciliation path" requirement.
- **Tests split along WU boundaries**: `test_permission_temporary_api.py` covers AC1/AC2 (success, 412, 428, 422 non_temporary/expired/renewal_expires_at_in_past/validation, 403, audit payload); `test_permission_temporary_worker.py` covers AC3/AC4 (expire + drift create atomicity (R1), root audit context install (R2), chapter-scoped intent without per-drift authority obstruction (R3), OCC collision at debug (R6), idempotency, filters, batching, concurrency, per-intent resilience, manual trigger authority + spoof-proofing, audit emission with narrow allowlists). All `now` injected at service entry; no sleeps; `PERMISSION_EXPIRY_BATCH_SIZE` monkey-patched for drain tests.

---

## Revision log — Revision 1

Revisions applied to close blocking findings in `plans/risk/slice-020-shortcut.md`
(HIGH: F1, F2; MEDIUM: F3, F4, F5) and `plans/risk/slice-020-audit.md`
(MEDIUM 1, MEDIUM 2; LOW 3, LOW 4, LOW 7). `plans/risk/slice-020-scope.md`
verdict was LOW with no required action.

| Revision | Binding risk | Sections touched |
|---|---|---|
| **R1** — Expire + drift commit in ONE transaction via shared `connection=` kwarg threaded into both `mutate_entity` calls; rollback on drift failure reverts the expire stamp and re-qualifies the candidate on the next tick. | shortcut F1 (HIGH), audit MEDIUM 2 | §1 AC4 step 3; §5.2 (`_expire_single_intent` rewritten, `_create_expiry_drift` accepts `connection=`); Guardrails (atomicity bullet); 5-bullet summary (worker bullet) |
| **R2** — `permission_expiry_worker_tick` installs `use_audit_context(_root_audit_context())` when no ambient context exists (mirrors `evaluate_ticket_sla` at `services/api/app/services/ticket_sla.py:508-513`), fixing `MissingCorrelationContextError` on the scheduler's `asyncio.to_thread` path. | audit MEDIUM 1 | §6.1 (tick rewritten + new `_root_audit_context` helper); Guardrails (worker-audit-context bullet); 5-bullet summary (worker bullet); new test `test_worker_installs_root_audit_context_when_invoked_from_scheduler_thread` in §8.2 |
| **R3** — Dropped per-intent `_require_scoped_authority("permission_drift.write", intent.scope_kind, …)` inside `_create_expiry_drift`. Chapter-scoped intents no longer fail on the flat authority model (`authority.py:238` requires exact `scope_kind` match). Precedent: SLICE-014's `_record_drift_created` also has no per-scope check. Top-level `permission_intent.write` at global scope remains the authority gate. | shortcut F2 (HIGH) | §1 AC4 step 3; §5.2 (`_create_expiry_drift` body + explanatory comment); new test `test_worker_expires_chapter_scoped_intent_without_authority_failure` in §8.2 |
| **R4** — Deleted the stubbed `_current_intent_version(db, intent.id)` which passed the raw row UUID. Replaced with `_read_intent_head_version(connection, *, aggregate_id, intent_id)` that queries `aggregate_heads` with the **composite** aggregate id built by `build_permission_intent_aggregate_id`. The read runs inside the same transaction as the `mutate_entity` call, so it is consistent with the head-for-update check. | shortcut F3 (MEDIUM) | §5.2 (`_read_intent_head_version` added; `_expire_single_intent` uses it inside the tx) |
| **R5** — Removed the `@field_validator("expires_at")` future-check from `PermissionIntentRenewalRequest` and added a service-layer `if request.expires_at <= now: raise RenewalExpiresAtInPastError(...)` in `renew_permission_intent` using the same `now` as the active-expired guard. Added `RenewalExpiresAtInPastError` to contracts and a 422 code `renewal_expires_at_in_past` in `_shared.raise_known_permission_error`. | shortcut F4 (MEDIUM) | §1 AC1 step 5; §1 AC2 step 4 + renumbered; §3.2 (validator removed + rationale); §3.4 (new error class); §3.5 (`__all__`); §5.1 (service check + constant dispatch); §5.3 (mapping); §7.3 (error table); §8.1 (test renamed) |
| **R6** — `StaleMutationError` classified as expected control flow. Per-intent loop in `expire_temporary_permission_intents` catches it at `debug` and does NOT increment `errored_count`; task tick also catches it at `debug` returning `None`. Only unexpected exceptions go to `logger.exception`. | shortcut F5 (MEDIUM), audit LOW 3 | §5.2 (loop exception split); §6.1 (tick exception split); Guardrails concurrency bullet; new test `test_worker_stale_mutation_collision_is_logged_at_debug_not_errored` in §8.2 |
| **R7** — Hoisted action/change-type strings into module-level dicts `INTENT_ACTION_TYPE`, `INTENT_CHANGE_TYPE`, `DRIFT_ACTION_TYPE`, `DRIFT_CHANGE_TYPE` matching SLICE-014's `DRIFT_RESOLUTION_ACTION_TYPE` / `DRIFT_RESOLUTION_CHANGE_TYPE` pattern. Every `mutate_entity` call site dereferences these dicts — no inline strings. | shortcut F9 (LOW, policy-bound) | §1 AC1 step 5; §1 AC4 step 3; §5.1 (`action_type=INTENT_ACTION_TYPE["renew"]`, `change_type=INTENT_CHANGE_TYPE["renewed"]`); §5.2 (expire + drift call sites use dict dispatch); §9.1 (dicts added); §9.4 (table rewritten in dict-lookup form) |
| **R8** — Payload allowlists tightened: `INTENT_RENEW_PAYLOAD_ALLOWLIST = {"new_expires_at", "reason"}`; `INTENT_EXPIRE_PAYLOAD_ALLOWLIST = {"expired_at", "source"}` with `source ∈ {"worker_sweep", "manual_trigger"}` threaded via a new `source` parameter on `expire_temporary_permission_intents`; `EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST` narrowed from 17 keys to 9 (drift_id + permission_intent_id + intent_version + scope + target + status — no bit masks, no `actual_*` NULLs, no `reconciliation_run_id` NULL). `_create_expiry_drift` now builds a lean `action_payload` dict mirroring `_record_drift_created`'s split between action_payload and payload_json. | audit LOW 4, audit LOW 5 | §5.2 (`_create_expiry_drift` constructs lean action_payload; `expire_temporary_permission_intents` + `_expire_single_intent` accept and thread `source`); §7.1 (manual endpoint passes `source="manual_trigger"`); §9.1 (allowlists replaced; `EXPIRY_DRIFT_DETECT_PAYLOAD_ALLOWLIST` renamed to `EXPIRY_DRIFT_CREATE_PAYLOAD_ALLOWLIST`); 5-bullet summary |
| **R9** — Expiry drift `change_type` distinguished from reconciliation's. Reconciliation emits `permission_drift.created`; expiry emits the new `permission_drift.detected_expired`. Synthesis D12's claim of reuse (originally `permission_drift.detected`) was factually incorrect and is superseded. Operators can now filter audit rows by origin without joining to `permission_intent_id IS NOT NULL`. | audit LOW 7 | §1 AC4 step 3; §5.2 (`_create_expiry_drift` uses `DRIFT_CHANGE_TYPE["detected_expired"]`); §9.1 + §9.4; 5-bullet summary |

**Not-blocking findings acknowledged but not revised** (rationale-only, already consistent with revised text):

- **shortcut F6 (MEDIUM)** — SKIP LOCKED framed as optimization, not idempotency layer. Addressed by rewriting Guardrails' "Concurrent worker safety" bullet to name OCC on `aggregate_heads` + `mark_intent_expired_row`'s predicate as the primary guards.
- **shortcut F7 (LOW)** — Claim that per-intent tx "matches ticket_sla" removed; §5.2 now frames per-intent tx as a deliberate departure from `ticket_sla`'s single-batch-tx shape, citing `submit_reconciliation_snapshot` as the shared-connection precedent.
- **shortcut F8 (LOW)** — `mark_intent_expired_row` rowcount=0 still raises `PermissionIntentNotFoundError`. Under R1's shared-tx, rowcount=0 only happens under a genuine data inconsistency (the row truly vanished) because OCC races surface as `StaleMutationError` before the projection runs. The F8 concern (benign concurrency dedupe misreported as error) is subsumed by R6's StaleMutationError split.
- **shortcut F10 (LOW)** — Drift `uuid4()` generated outside the tx is safe because the whole `with db.transaction()` block is atomic under R1; on rollback, neither the audit row, the state-change row, nor the projection exist, and the `drift_ids` list is only appended after `with` exits. Noted in §5.2 narrative.
- **audit LOW 6** — `request_surface` hardcoded. Not revised in this iteration; the actor disambiguates worker vs. operator and scope R7's "no inline strings" intent does not yet cover `request_surface`. Deferred to future hygiene pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
