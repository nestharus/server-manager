# SLICE-014 Proposal: Permission Intent and Drift Detection

This proposal is binding for the SLICE-014 implementation and is derived
directly from `.pipeline/synthesis.md` D1–D15. Nothing here widens
lifecycle scope, introduces compatibility shims, or rewrites the shipped
WU-006a / WU-006b foundations. When the proposal refers to a decision as
"per D5" (etc.) it is binding — the synthesis is the authoritative source
of truth and this document only describes the mechanics inside those
boundaries.

The ticket (`product-strategy/tickets/SLICE-014.md`) decomposes the work
into four work units:

| WU | Scope |
|---|---|
| WU-027 | Permission intent management API (D1 narrowing + GET list + create/update). |
| WU-028A | Permission drift read + resolution API (D2 widening + state machine from D5 + spoof-proof resolver from D6). |
| WU-028B-api | Permission reconciliation run API (D3 idempotency + D4 lifecycle + D8 algorithm). |
| WU-028B-discord | Discord permission snapshot adapter (D12 + D13). |

Acceptance criteria are referenced inline per §1. Migration chain is
`wu_035_application_interview → wu_027 → wu_028a → wu_028b` per D14.

---

## §1 — AC Mapping

### AC1 — Create/update intent persists full target and rejects stale updates with 412

1. **Schema narrowing.** Apply migration `wu_027_permission_intents_refinements`
   (§2.1) to replace the shipped `permission_intents_scope_kind_valid`
   CHECK constraint so `scope_kind ∈ {'global','chapter'}`. This rejects
   `member` at the DB layer per D1.
   - File: `migrations/versions/wu-027_permission_intents_refinements.py`
2. **Contract narrowing.** Replace the `ScopeKind`-sourced validator on
   `_PermissionIntentBase` and `_PermissionIntentCreateBase` with a local
   `PermissionIntentScopeKind: TypeAlias = Literal["global", "chapter"]`.
   Keep `scope_id` optional but validate the shape: `global ⇒ scope_id is
   None`; `chapter ⇒ scope_id is not None`. Do not re-export the wider
   `ScopeKind` from this module; do not add any alias.
   - File: `services/api/app/contracts/permissions.py` (edit existing
     `_PermissionIntentBase`, `_PermissionIntentCreateBase`).
3. **Repository list.** Add
   `list_permission_intents(connection, *, scope_kind, scope_id)` returning
   normalized intent rows. Ordering `(role_id, channel_id NULLS FIRST, id)`.
   - File: `services/api/app/repositories/permissions.py`.
4. **Service create/update via `mutate_entity`.** Extend the shipped
   `create_permission_intent` / `update_permission_intent` functions to
   accept `actor: ActorIdentity` and to use that actor’s identity on the
   `MutationRequest` instead of the hardcoded
   `actor_kind='system'/actor_id='permissions-service'` shim in
   `services/api/app/services/permissions.py:44-55`. No compat shim for
   the prior system actor — it was foundation-only.
   - File: `services/api/app/services/permissions.py`.
5. **Service list helper.** `list_permission_intents(db, *, actor,
   scope_kind, scope_id)` resolves authority via
   `RequireAuthority('permission_intent.read', scope_kind,
   scope_id)` at the endpoint and calls the repository list.
   - File: `services/api/app/services/permissions.py`.
6. **Endpoints.** Three endpoints in
   `services/api/app/api/v1/endpoints/permissions/intents.py`:
   - `POST /api/v1/permission-intents` — 201 + strong ETag `"1"`.
   - `PATCH /api/v1/permission-intents/{intent_id}` — requires `If-Match`
     strong ETag; 412 on mismatch; 200 + fresh ETag otherwise.
   - `GET /api/v1/permission-intents?scope_kind=…&scope_id=…` — list with
     filter coverage per D10.
7. **OCC**. The shipped compound aggregate id
   (`build_permission_intent_aggregate_id` at
   `services/api/app/services/permissions.py:29-41`) is retained. Patches
   flow through `mutate_entity(expected_version=<If-Match>)`; stale head
   → `StaleMutationError` → `HTTPException 412` via
   `raise_known_application_error`-style helper in §6.
8. **Tests (AC1).** See §8 WU-027.

### AC2 — Drift reads include orphaned state; resolve rejects stale version with 412

1. **Drift widening.** Apply migration
   `wu_028a_permission_drift_widening` (§2.2) to add scope/target locator,
   resolution metadata, and the run anchor column (FK added later in
   wu_028b). Installs variant/scope/resolution CHECK constraints from D2.
   - File: `migrations/versions/wu-028a_permission_drift_widening.py`.
2. **Drift read contract widening.** Add `scope_kind`, `scope_id`,
   `role_id`, `channel_id`, `kind`, `reconciliation_run_id`,
   `resolved_by_kind`, `resolved_by_id`, `resolved_at`, `resolution_reason`
   to `PermissionDriftRead`. Keep the anchor-shape validator. Add a
   resolution-shape validator mirroring D2’s CHECK (defense in depth).
   - File: `services/api/app/contracts/permissions.py`.
3. **Drift resolution request contract.** `PermissionDriftResolutionRequest`
   per D6 (§3). Action → target status constant map.
4. **Repository list + resolve.** Add
   `list_permission_drift(connection, *, status=None, scope_kind=None,
   scope_id=None, role_id=None, reconciliation_run_id=None,
   has_intent=None)` and
   `update_permission_drift_resolution(connection, *, drift_id, status,
   resolved_by_kind, resolved_by_id, resolved_at, resolution_reason)`.
   - File: `services/api/app/repositories/permissions.py`.
5. **Service resolve via state machine.** Introduce
   `VALID_DRIFT_TRANSITIONS` per D5 and a spoof-proof `_originating_actor`
   helper mirroring `services/api/app/services/applications.py:189-195`.
   Replace the existing `update_permission_drift_status` (which currently
   tolerates missing `expected_version`) with `resolve_permission_drift`
   that requires `expected_version: int`, refuses terminals with 409, and
   populates resolution metadata for `reconciled|accepted` transitions.
   - File: `services/api/app/services/permissions.py`.
6. **Endpoints.** Two endpoints in
   `services/api/app/api/v1/endpoints/permissions/drift.py`:
   - `GET /api/v1/permission-drift` — filters per D10.
   - `POST /api/v1/permission-drift/{drift_id}/resolve` — requires
     `If-Match`; 412 on stale; 409 on invalid state transition or
     terminal; 200 + fresh ETag otherwise.
7. **Tests (AC2).** See §8 WU-028A.

### AC3 — Reconciliation runs create drift for both mismatched and orphaned state

1. **Run table + service actor.** Apply migration
   `wu_028b_permission_reconciliation_runs` (§2.3): creates
   `permission_reconciliation_runs`, adds FK
   `permission_drift.reconciliation_run_id →
   permission_reconciliation_runs.id ON DELETE RESTRICT`, installs partial
   unique indexes from D3, and seeds the `permission-reconciler` service
   actor (§9).
   - File: `migrations/versions/wu-028b_permission_reconciliation_runs.py`.
2. **Contracts.** `PermissionReconciliationRunCreate`,
   `PermissionReconciliationRunRead`, `PermissionSnapshotEntry` (variant
   discriminated), `ReconciliationSnapshotRequest` (duplicate-key rejection
   at contract boundary). §3.
3. **Repository.**
   - `insert_reconciliation_run(connection, *, run_row)`.
   - `fetch_reconciliation_run(connection, run_id)`.
   - `update_reconciliation_run_status(connection, *, run_id, status,
     snapshot_submitted_at, reconciled_at, failed_at, failure_reason)`.
   - `insert_drift_batch(connection, *, rows)` using `INSERT … ON CONFLICT
     DO NOTHING` against the D3 partial unique indexes and returning
     persisted row ids.
   - `list_drift_by_run(connection, run_id)`.
   - File: `services/api/app/repositories/permissions.py`.
4. **Reconciliation service.**
   - `create_reconciliation_run(db, *, request, actor)` — advances from
     seed through `mutate_entity(expected_version=0,
     action_type='permission_reconciliation_run.create')`.
   - `submit_reconciliation_snapshot(db, *, run_id, entries, actor)` —
     D8 algorithm, single transaction + terminal replay idempotency.
   - File (new): `services/api/app/services/permission_reconciliation.py`.
5. **Endpoints.** Two endpoints in
   `services/api/app/api/v1/endpoints/permissions/reconciliation.py`:
   - `POST /api/v1/permission-reconciliation/runs` — 201 + strong ETag
     `"1"`; response includes `status='requested'` and empty `drift_ids`.
   - `POST /api/v1/permission-reconciliation/runs/{run_id}/snapshots` —
     200 + fresh ETag; populates `drift_ids`.
6. **Tests (AC3).** See §8 WU-028B-api.

### AC4 — Discord adapter never mutates drift locally; retries reuse run_id

1. **API idempotency.** The snapshot POST is idempotent by path
   `run_id`: if the run is already terminal, return the cached drift list
   without reprocessing (D8 step 2). The Discord adapter therefore does
   not need to pre-check status before retrying.
2. **Discord adapter.** The handler creates a run on the API, walks
   in-memory guild cache per D13, POSTs the snapshot, and surfaces the
   drift count in an ephemeral message. No local drift store is written
   under any error path; retries re-POST the snapshot with the same
   `run_id` (§7).
3. **Tests (AC4).** See §8 WU-028B-discord.

---

## §2 — Migration Plan

All three migrations’ `downgrade()` is an explicit no-op with a comment
citing the AGENTS.md Live Server Principle (precedent: wu-037 /
wu-042). No destructive revert of seeded grants.

### §2.1 — `wu-027_permission_intents_refinements`

```python
# migrations/versions/wu-027_permission_intents_refinements.py
"""WU-027 narrow permission_intent scope kinds to global|chapter."""

from __future__ import annotations

from alembic import op


revision = "wu_027_permission_intents_refinements"
down_revision = "wu_035_application_interview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # D1 pre-narrow guard: refuse if any member-scoped intent exists.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM permission_intents WHERE scope_kind = 'member'
            ) THEN
                RAISE EXCEPTION
                    'SLICE-014 D1: permission_intents contains scope_kind=member '
                    'rows; forward migration refuses to narrow scope.';
            END IF;
        END
        $$;
        """
    )
    # Replace the scope_kind CHECK constraint shipped in wu-006a.
    op.drop_constraint(
        "permission_intents_scope_kind_valid",
        "permission_intents",
        type_="check",
    )
    op.create_check_constraint(
        "permission_intents_scope_kind_valid",
        "permission_intents",
        "scope_kind IN ('global', 'chapter')",
    )
    # Defense-in-depth: scope-id shape matches scope_kind.
    op.create_check_constraint(
        "permission_intents_scope_shape_valid",
        "permission_intents",
        "(scope_kind = 'global' AND scope_id IS NULL) "
        "OR (scope_kind = 'chapter' AND scope_id IS NOT NULL)",
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: widening the scope
    # constraint after narrowing would silently re-admit member rows a
    # running server cannot reconstruct. Reverts are explicit operator
    # actions, not migration responsibilities.
    pass
```

### §2.2 — `wu-028a_permission_drift_widening`

```python
# migrations/versions/wu-028a_permission_drift_widening.py
"""WU-028A widen permission_drift for scope, target, and resolution."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_028a_permission_drift_widening"
down_revision = "wu_027_permission_intents_refinements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # D2 pre-widening guard: refuse if orphaned drift already exists that
    # we cannot backfill a target for.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM permission_drift
                WHERE permission_intent_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'SLICE-014 D2: pre-existing orphaned permission_drift row; '
                    'widening refuses to synthesize a target locator.';
            END IF;
        END
        $$;
        """
    )

    op.add_column(
        "permission_drift",
        sa.Column("scope_kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("scope_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("role_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("channel_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("reconciliation_run_id", sa.dialects.postgresql.UUID(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolved_by_kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolved_by_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "permission_drift",
        sa.Column("resolution_reason", sa.Text(), nullable=True),
    )

    # Backfill legacy intent-linked rows (guard above guarantees no orphans).
    op.execute(
        """
        UPDATE permission_drift d
           SET scope_kind  = i.scope_kind,
               scope_id    = i.scope_id,
               role_id     = i.role_id,
               channel_id  = i.channel_id,
               kind        = i.kind
          FROM permission_intents i
         WHERE d.permission_intent_id = i.id
           AND d.role_id IS NULL;
        """
    )

    # Enforce NOT NULL after backfill.
    op.alter_column("permission_drift", "scope_kind", nullable=False)
    op.alter_column("permission_drift", "role_id", nullable=False)
    op.alter_column("permission_drift", "kind", nullable=False)

    op.create_check_constraint(
        "permission_drift_scope_kind_valid",
        "permission_drift",
        "scope_kind IN ('global', 'chapter')",
    )
    op.create_check_constraint(
        "permission_drift_kind_valid",
        "permission_drift",
        "kind IN ('guild_role', 'channel_role')",
    )
    op.create_check_constraint(
        "permission_drift_scope_shape_valid",
        "permission_drift",
        "(scope_kind = 'global' AND scope_id IS NULL) "
        "OR (scope_kind = 'chapter' AND scope_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "permission_drift_variant_shape_valid",
        "permission_drift",
        "(kind = 'guild_role' AND channel_id IS NULL) "
        "OR (kind = 'channel_role' AND channel_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "permission_drift_resolution_shape_valid",
        "permission_drift",
        "("
        "status IN ('reconciled','accepted') "
        "AND resolved_by_kind IS NOT NULL "
        "AND resolved_by_id IS NOT NULL "
        "AND resolved_at IS NOT NULL "
        "AND resolution_reason IS NOT NULL"
        ") OR ("
        "status IN ('detected','acknowledged') "
        "AND resolved_by_kind IS NULL "
        "AND resolved_by_id IS NULL "
        "AND resolved_at IS NULL "
        "AND resolution_reason IS NULL"
        ")",
    )

    op.create_index(
        "ix_permission_drift__scope",
        "permission_drift",
        ["scope_kind", "scope_id"],
    )
    op.create_index(
        "ix_permission_drift__reconciliation_run_id",
        "permission_drift",
        ["reconciliation_run_id"],
    )
    op.create_index(
        "ix_permission_drift__role_channel_kind",
        "permission_drift",
        ["role_id", "channel_id", "kind"],
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: the widened columns hold
    # orphaned drift targets that a downgrade cannot preserve safely.
    pass
```

### §2.3 — `wu-028b_permission_reconciliation_runs`

```python
# migrations/versions/wu-028b_permission_reconciliation_runs.py
"""WU-028B create permission_reconciliation_runs; link drift; seed reconciler."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_028b_permission_reconciliation_runs"
down_revision = "wu_028a_permission_drift_widening"
branch_labels = None
depends_on = None


_RECONCILER_PERMISSIONS = (
    '["permission_intent.read",'
    '"permission_drift.read",'
    '"permission_drift.write",'
    '"permission_reconciliation_run.write"]'
)


def upgrade() -> None:
    op.create_table(
        "permission_reconciliation_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(), primary_key=True),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column("requested_by_kind", sa.Text(), nullable=False),
        sa.Column("requested_by_id", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("snapshot_submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "scope_kind IN ('global', 'chapter')",
            name="permission_reconciliation_runs_scope_kind_valid",
        ),
        sa.CheckConstraint(
            "(scope_kind = 'global' AND scope_id IS NULL) "
            "OR (scope_kind = 'chapter' AND scope_id IS NOT NULL)",
            name="permission_reconciliation_runs_scope_shape_valid",
        ),
        sa.CheckConstraint(
            "status IN ('requested','snapshot_submitted','reconciled','failed')",
            name="permission_reconciliation_runs_status_valid",
        ),
        sa.CheckConstraint(
            "("
            "status = 'requested' "
            "AND snapshot_submitted_at IS NULL "
            "AND reconciled_at IS NULL "
            "AND failed_at IS NULL"
            ") OR ("
            "status = 'snapshot_submitted' "
            "AND snapshot_submitted_at IS NOT NULL "
            "AND reconciled_at IS NULL "
            "AND failed_at IS NULL"
            ") OR ("
            "status = 'reconciled' "
            "AND snapshot_submitted_at IS NOT NULL "
            "AND reconciled_at IS NOT NULL "
            "AND failed_at IS NULL"
            ") OR ("
            "status = 'failed' "
            "AND failed_at IS NOT NULL "
            "AND failure_reason IS NOT NULL "
            "AND reconciled_at IS NULL"
            ")",
            name="permission_reconciliation_runs_terminal_shape_valid",
        ),
    )

    op.create_index(
        "ix_permission_reconciliation_runs__scope",
        "permission_reconciliation_runs",
        ["scope_kind", "scope_id"],
    )
    op.create_index(
        "ix_permission_reconciliation_runs__status_requested_at",
        "permission_reconciliation_runs",
        ["status", "requested_at"],
    )

    op.create_foreign_key(
        "fk_permission_drift__reconciliation_run_id__permission_reconciliation_runs",
        source_table="permission_drift",
        referent_table="permission_reconciliation_runs",
        local_cols=["reconciliation_run_id"],
        remote_cols=["id"],
        ondelete="RESTRICT",
    )

    # D3 — partial unique indexes. Two indexes because Postgres treats
    # NULL channel_id as distinct; the second index catches guild-role rows.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_permission_drift__run_target
            ON permission_drift (reconciliation_run_id, role_id, kind, channel_id)
            WHERE reconciliation_run_id IS NOT NULL
              AND channel_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_permission_drift__run_target_guild
            ON permission_drift (reconciliation_run_id, role_id, kind)
            WHERE reconciliation_run_id IS NOT NULL
              AND channel_id IS NULL;
        """
    )

    # D9 — service-actor grant. Idempotent via @>/<@ containment + active
    # grant guard (wu-037 precedent).
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
            'permission-reconciler',
            'global',
            NULL,
            '{_RECONCILER_PERMISSIONS}'::jsonb,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM authority_grants
             WHERE grantee_id = 'permission-reconciler'
               AND scope_kind = 'global'
               AND scope_id IS NULL
               AND permissions @> '{_RECONCILER_PERMISSIONS}'::jsonb
               AND permissions <@ '{_RECONCILER_PERMISSIONS}'::jsonb
               AND revoked_at IS NULL
               AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        );
        """
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: drift rows reference the
    # run table and seeded actor grants may already be relied on by
    # operator workflows. Revocation is an explicit operator action.
    pass
```

**Note on chapter-scope reconciliation**: the service actor holds a
single `scope_kind='global', scope_id=NULL` grant. Per the existing
hierarchical authority evaluator (`services/api/app/services/authority.py`,
precedent from SLICE-008), a global-scoped grant satisfies a chapter-scope
requirement for the same permission. This is confirmed by the resolver
pattern used in `_RequireAuthority` at
`services/api/app/core/dependencies.py:56-138`. A chapter-scope seed is
therefore **not** required.

---

## §3 — Contracts

All additions are in `services/api/app/contracts/permissions.py` unless
stated otherwise. Pydantic v2 with `model_config = ConfigDict(extra="forbid")`
and `frozen=False` unless existing sibling contracts use `frozen=True`;
in this file the shipped models use only `extra="forbid"`, so new models
follow suit.

### §3.1 — Narrowed intent scope

```python
PermissionIntentScopeKind: TypeAlias = Literal["global", "chapter"]


class _PermissionIntentBase(_PermissionModel):
    id: UUID
    scope_kind: PermissionIntentScopeKind   # narrowed per D1
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    reason: str | None = None
    temporary: bool
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "_PermissionIntentBase":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self

    @model_validator(mode="after")
    def validate_temporal_shape(self) -> "_PermissionIntentBase":
        if self.temporary and self.expires_at is None:
            raise ValueError("temporary permission intents require expires_at")
        if not self.temporary and self.expires_at is not None:
            raise ValueError("non-temporary permission intents forbid expires_at")
        return self
```

Apply the same `scope_kind` narrowing + scope-shape validator to
`_PermissionIntentCreateBase`. `PermissionIntentUpdate` already excludes
scope fields — it remains unchanged.

### §3.2 — `PermissionDriftRead` widening

```python
class PermissionDriftRead(_PermissionModel):
    id: UUID
    permission_intent_id: UUID | None = None
    intent_version: int | None = Field(default=None, ge=1)

    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    role_id: str = Field(min_length=1)
    channel_id: str | None = None
    kind: PermissionIntentKind
    reconciliation_run_id: UUID | None = None

    actual_bits: DecimalBitString | None = None
    actual_allow_bits: DecimalBitString | None = None
    actual_deny_bits: DecimalBitString | None = None
    intended_bits: DecimalBitString | None = None
    intended_allow_bits: DecimalBitString | None = None
    intended_deny_bits: DecimalBitString | None = None

    status: PermissionDriftStatus
    detected_at: datetime

    resolved_by_kind: str | None = None
    resolved_by_id: str | None = None
    resolved_at: datetime | None = None
    resolution_reason: str | None = None

    @model_validator(mode="after")
    def validate_intent_anchor(self) -> "PermissionDriftRead":
        if (self.permission_intent_id is None) != (self.intent_version is None):
            raise ValueError(
                "permission_intent_id and intent_version must be both set or both null"
            )
        return self

    @model_validator(mode="after")
    def validate_variant_shape(self) -> "PermissionDriftRead":
        if self.kind == "guild_role" and self.channel_id is not None:
            raise ValueError("guild_role drift forbids channel_id")
        if self.kind == "channel_role" and self.channel_id is None:
            raise ValueError("channel_role drift requires channel_id")
        return self

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "PermissionDriftRead":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self

    @model_validator(mode="after")
    def validate_resolution_shape(self) -> "PermissionDriftRead":
        resolution_present = (
            self.resolved_by_kind is not None
            or self.resolved_by_id is not None
            or self.resolved_at is not None
            or self.resolution_reason is not None
        )
        if self.status in ("reconciled", "accepted"):
            if not all(
                (
                    self.resolved_by_kind,
                    self.resolved_by_id,
                    self.resolved_at,
                    self.resolution_reason,
                )
            ):
                raise ValueError("terminal drift requires full resolution metadata")
        elif resolution_present:
            raise ValueError("non-terminal drift forbids resolution metadata")
        return self
```

### §3.3 — Drift resolution request (D6)

```python
DriftResolutionAction: TypeAlias = Literal["acknowledge", "reconcile", "accept"]


class PermissionDriftResolutionRequest(_PermissionModel):
    action: DriftResolutionAction
    reason: str = Field(min_length=1)
    resolved_by_kind: str | None = None
    resolved_by_id: str | None = None

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be non-blank")
        return value

    @model_validator(mode="after")
    def validate_resolved_by_pair(self) -> "PermissionDriftResolutionRequest":
        # R8 / shortcut F6: `resolved_by_kind` and `resolved_by_id` must be
        # supplied together or omitted together. Mirrors the both-or-neither
        # discipline `services/api/app/contracts/applications.py:223-227` uses
        # for `originating_actor_*`. Prevents a service caller from submitting
        # only one half and silently mixing service identity into the other.
        if (self.resolved_by_kind is None) != (self.resolved_by_id is None):
            raise ValueError(
                "resolved_by_kind and resolved_by_id must be supplied together "
                "or omitted together"
            )
        return self
```

### §3.4 — Reconciliation contracts (D7)

```python
class PermissionReconciliationRunCreate(_PermissionModel):
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    originating_actor_kind: str | None = None
    originating_actor_id: str | None = None

    @model_validator(mode="after")
    def validate_scope_shape(self) -> "PermissionReconciliationRunCreate":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("global scope forbids scope_id")
        if self.scope_kind == "chapter" and self.scope_id is None:
            raise ValueError("chapter scope requires scope_id")
        return self


PermissionReconciliationRunStatus: TypeAlias = Literal[
    "requested", "snapshot_submitted", "reconciled", "failed",
]


class PermissionReconciliationRunRead(_PermissionModel):
    id: UUID
    scope_kind: PermissionIntentScopeKind
    scope_id: str | None = None
    requested_by_kind: str
    requested_by_id: str
    requested_at: datetime
    snapshot_submitted_at: datetime | None = None
    reconciled_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    status: PermissionReconciliationRunStatus
    drift_ids: list[UUID] = Field(default_factory=list)


class _PermissionSnapshotBase(_PermissionModel):
    role_id: str = Field(min_length=1)


class GuildRolePermissionSnapshotEntry(_PermissionSnapshotBase):
    kind: Literal["guild_role"]
    permission_bits: DecimalBitString


class ChannelRolePermissionSnapshotEntry(_PermissionSnapshotBase):
    kind: Literal["channel_role"]
    channel_id: str = Field(min_length=1)
    allow_bits: DecimalBitString
    deny_bits: DecimalBitString


PermissionSnapshotEntry = Annotated[
    GuildRolePermissionSnapshotEntry | ChannelRolePermissionSnapshotEntry,
    Field(discriminator="kind"),
]


class ReconciliationSnapshotRequest(_PermissionModel):
    entries: list[PermissionSnapshotEntry] = Field(default_factory=list)

    @field_validator("entries")
    @classmethod
    def reject_duplicate_keys(cls, value: list[Any]) -> list[Any]:
        seen: set[tuple[str, str, str | None]] = set()
        for entry in value:
            key = (
                entry.kind,
                entry.role_id,
                getattr(entry, "channel_id", None),
            )
            if key in seen:
                raise ValueError(f"duplicate snapshot entry for {key}")
            seen.add(key)
        return value
```

Export the new names from `__all__`.

### §3.5 — Discord mirrors

Add a parallel set of the request/response models (the ones the adapter
sends/receives) in `services/discord/app/contracts/permissions.py`. These
mirror the API contracts exactly; they do not import from
`services/api/…` (the Discord service has no dependency on the API
service package per existing precedent in
`services/discord/app/contracts/interactions.py`).

---

## §4 — Repository Layer

All additions in `services/api/app/repositories/permissions.py`.

### §4.1 — Intent list

```python
def list_permission_intents(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
    role_id: str | None = None,
    channel_id: str | None = None,
    kind: str | None = None,
    temporary: bool | None = None,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    clauses = ["scope_kind = %s"]
    params: list[Any] = [scope_kind]
    if scope_id is None:
        clauses.append("scope_id IS NULL")
    else:
        clauses.append("scope_id = %s")
        params.append(scope_id)
    if role_id is not None:
        clauses.append("role_id = %s")
        params.append(role_id)
    if channel_id is not None:
        clauses.append("channel_id = %s")
        params.append(channel_id)
    if kind is not None:
        clauses.append("kind = %s")
        params.append(kind)
    if temporary is not None:
        clauses.append("temporary = %s")
        params.append(temporary)
    if not include_expired:
        clauses.append("(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)")
    where = " AND ".join(clauses)
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            f"""
            SELECT id, kind, scope_kind, scope_id, role_id, channel_id,
                   permission_bits, allow_bits, deny_bits, reason,
                   temporary, expires_at
            FROM permission_intents
            WHERE {where}
            ORDER BY role_id, channel_id NULLS FIRST, id
            """,
            params,
        ).fetchall()
    return [_normalize_permission_intent_row(row) for row in rows]
```

### §4.2 — Drift list + resolve + batch insert

```python
def list_permission_drift(
    connection: Connection[Any],
    *,
    status: list[str] | None = None,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    role_id: str | None = None,
    reconciliation_run_id: UUID | None = None,
    has_intent: bool | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        placeholders = ", ".join(["%s"] * len(status))
        clauses.append(f"status IN ({placeholders})")
        params.extend(status)
    if scope_kind is not None:
        clauses.append("scope_kind = %s")
        params.append(scope_kind)
    if scope_id is not None:
        clauses.append("scope_id = %s")
        params.append(scope_id)
    if role_id is not None:
        clauses.append("role_id = %s")
        params.append(role_id)
    if reconciliation_run_id is not None:
        clauses.append("reconciliation_run_id = %s")
        params.append(reconciliation_run_id)
    if has_intent is True:
        clauses.append("permission_intent_id IS NOT NULL")
    elif has_intent is False:
        clauses.append("permission_intent_id IS NULL")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            f"""
            SELECT id, permission_intent_id, intent_version,
                   scope_kind, scope_id, role_id, channel_id, kind,
                   reconciliation_run_id,
                   actual_bits, actual_allow_bits, actual_deny_bits,
                   intended_bits, intended_allow_bits, intended_deny_bits,
                   status, detected_at,
                   resolved_by_kind, resolved_by_id, resolved_at,
                   resolution_reason
            FROM permission_drift
            {where}
            ORDER BY detected_at DESC, id
            """,
            params,
        ).fetchall()
    return [_normalize_permission_drift_row(row) for row in rows]


def insert_permission_drift_batch(
    connection: Connection[Any],
    *,
    rows: Sequence[dict[str, Any]],
) -> list[UUID]:
    """Insert drift rows ON CONFLICT DO NOTHING against the D3 partial unique
    indexes. Returns **only** the ids of rows newly persisted by this
    invocation (i.e., rows for which ``INSERT … RETURNING id`` yielded a row).
    Conflict rows are silently skipped — the caller reads the run's full drift
    set via ``list_drift_by_run(run_id)`` (which enumerates every drift row
    anchored to the run, new or pre-existing). This split cleanly separates
    "ids I just wrote" (for which ``mutate_entity(expected_version=0)`` is
    legal) from "ids already at version ≥ 1" (for which it would raise
    ``StaleMutationError``). Caller must pre-assign UUIDs. See R4 / shortcut
    finding F4.
    """
    inserted: list[UUID] = []
    for row in rows:
        result = connection.execute(
            """
            INSERT INTO permission_drift (
                id, permission_intent_id, intent_version,
                scope_kind, scope_id, role_id, channel_id, kind,
                reconciliation_run_id,
                actual_bits, actual_allow_bits, actual_deny_bits,
                intended_bits, intended_allow_bits, intended_deny_bits,
                status, detected_at
            ) VALUES (
                %(id)s, %(permission_intent_id)s, %(intent_version)s,
                %(scope_kind)s, %(scope_id)s, %(role_id)s, %(channel_id)s,
                %(kind)s, %(reconciliation_run_id)s,
                %(actual_bits)s, %(actual_allow_bits)s, %(actual_deny_bits)s,
                %(intended_bits)s, %(intended_allow_bits)s, %(intended_deny_bits)s,
                %(status)s, CURRENT_TIMESTAMP
            )
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            row,
        ).fetchone()
        if result is not None:
            inserted.append(result[0])
        # Conflict rows are intentionally dropped — the caller queries
        # list_drift_by_run(run_id) for the run's final drift set.
    return inserted


def update_permission_drift_resolution(
    connection: Connection[Any],
    *,
    drift_id: UUID,
    status: str,
    resolved_by_kind: str | None,
    resolved_by_id: str | None,
    resolved_at: datetime | None,
    resolution_reason: str | None,
) -> int:
    cursor = connection.execute(
        """
        UPDATE permission_drift
           SET status = %s,
               resolved_by_kind = %s,
               resolved_by_id = %s,
               resolved_at = %s,
               resolution_reason = %s
         WHERE id = %s
        """,
        (
            status,
            resolved_by_kind,
            resolved_by_id,
            resolved_at,
            resolution_reason,
            drift_id,
        ),
    )
    return cursor.rowcount
```

### §4.3 — Reconciliation run CRUD

```python
def insert_reconciliation_run(
    connection: Connection[Any],
    *,
    row: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO permission_reconciliation_runs (
            id, scope_kind, scope_id,
            requested_by_kind, requested_by_id,
            requested_at, status
        )
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'requested')
        """,
        (
            row["id"],
            row["scope_kind"],
            row["scope_id"],
            row["requested_by_kind"],
            row["requested_by_id"],
        ),
    )


def fetch_reconciliation_run(
    connection: Connection[Any],
    run_id: UUID,
) -> dict[str, Any] | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, scope_kind, scope_id,
                   requested_by_kind, requested_by_id, requested_at,
                   snapshot_submitted_at, reconciled_at,
                   failed_at, failure_reason, status
            FROM permission_reconciliation_runs
            WHERE id = %s
            """,
            (run_id,),
        ).fetchone()


def update_reconciliation_run_status(
    connection: Connection[Any],
    *,
    run_id: UUID,
    status: str,
    snapshot_submitted_at: datetime | None = None,
    reconciled_at: datetime | None = None,
    failed_at: datetime | None = None,
    failure_reason: str | None = None,
) -> int:
    cursor = connection.execute(
        """
        UPDATE permission_reconciliation_runs
           SET status = %s,
               snapshot_submitted_at = COALESCE(%s, snapshot_submitted_at),
               reconciled_at = COALESCE(%s, reconciled_at),
               failed_at = COALESCE(%s, failed_at),
               failure_reason = COALESCE(%s, failure_reason)
         WHERE id = %s
        """,
        (status, snapshot_submitted_at, reconciled_at, failed_at,
         failure_reason, run_id),
    )
    return cursor.rowcount


def list_drift_ids_by_run(
    connection: Connection[Any],
    run_id: UUID,
) -> list[UUID]:
    rows = connection.execute(
        """
        SELECT id FROM permission_drift
         WHERE reconciliation_run_id = %s
         ORDER BY detected_at, id
        """,
        (run_id,),
    ).fetchall()
    return [row[0] for row in rows]
```

---

## §5 — Service Layer

### §5.1 — Intent service (extend existing)

Extend `services/api/app/services/permissions.py`:

- Add module-level constants (full declaration in §10.1):
  `INTENT_CREATE_PAYLOAD_ALLOWLIST`, `INTENT_UPDATE_PAYLOAD_ALLOWLIST`.
- Add the service-layer authority helper (R5 / shortcut F5 — mirrors
  `services/api/app/services/applications.py::_require_authority`):
  ```python
  def _require_scoped_authority(
      permission: str,
      *,
      scope_kind: str,
      scope_id: str | None,
      actor: ActorIdentity,
      db: PostgresDatabase,
  ) -> None:
      """Service-layer authority gate. Builds an ``AuthorityRequirement`` from
      the concrete scope and evaluates it via the shipped hierarchical
      authority evaluator. Raises ``PermissionError('authority denied')`` on
      denial, which maps to 403 at the endpoint. Called before ``mutate_entity``
      in every mutating service function so the mutation is never reachable
      from a non-HTTP caller (background jobs, CLIs, future deferred-effects
      callbacks) without authority enforcement. Endpoints retain
      ``_require_scoped`` as an early-403 short-circuit but are no longer
      the sole gate.
      """
      requirement = AuthorityRequirement(
          permission=permission,
          scope_kind=scope_kind,
          scope_id=scope_id,
      )
      authority.evaluate(db, actor=actor, requirement=requirement)
  ```
- Replace the `_make_request(...)` helper (currently hardcodes
  `actor_kind='system'`, `actor_id='permissions-service'`) with
  ```python
  def _make_request(
      *, expected_version: int, actor: ActorIdentity, request_surface: str,
      reason_text: str | None = None,
  ) -> MutationRequest:
      return MutationRequest(
          expected_version=expected_version,
          actor_kind=actor.actor_kind,
          actor_id=actor.actor_id,
          reason_text=reason_text,
          request_surface=request_surface,
      )
  ```
- `create_permission_intent(db, request, *, actor)` — BEFORE calling
  `mutate_entity`, invokes
  `_require_scoped_authority('permission_intent.write',
  scope_kind=request.scope_kind, scope_id=request.scope_id, actor=actor,
  db=db)` (R5). Then uses the actor-scoped `_make_request` and the
  `INTENT_CREATE_PAYLOAD_ALLOWLIST`.
- `update_permission_intent(db, intent_id, *, expected_version, patch,
  actor)` — loads the current intent via `read_permission_intent(db,
  intent_id)`, then invokes
  `_require_scoped_authority('permission_intent.write',
  scope_kind=current.scope_kind, scope_id=current.scope_id, actor=actor,
  db=db)` (R5) BEFORE calling `mutate_entity`. Uses the actor-scoped
  `_make_request` and the `INTENT_UPDATE_PAYLOAD_ALLOWLIST`.
- Add `list_permission_intents(db, *, scope_kind, scope_id, actor, ...)`
  which invokes
  `_require_scoped_authority('permission_intent.read',
  scope_kind=scope_kind, scope_id=scope_id, actor=actor, db=db)` (R5)
  BEFORE calling the repository list, then returns a list of
  `PermissionIntentRead`.

### §5.2 — Drift service (extend / replace `update_permission_drift_status`)

Replace the shipped permissive `update_permission_drift_status` with a
strict `resolve_permission_drift`:

```python
DRIFT_RESOLUTION_TARGET_STATUS: dict[str, str] = {
    "acknowledge": "acknowledged",
    "reconcile":   "reconciled",
    "accept":      "accepted",
}

VALID_DRIFT_TRANSITIONS: dict[tuple[str, str], str] = {
    ("detected", "acknowledge"): "acknowledged",
    ("detected", "reconcile"):   "reconciled",
    ("detected", "accept"):      "accepted",
    ("acknowledged", "reconcile"): "reconciled",
    ("acknowledged", "accept"):    "accepted",
}

DRIFT_TERMINAL_STATUSES = frozenset({"reconciled", "accepted"})

DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    "acknowledge": {"action", "reason",
                    "resolved_by_kind", "resolved_by_id"},
    "reconcile":   {"action", "reason",
                    "resolved_by_kind", "resolved_by_id"},
    "accept":      {"action", "reason",
                    "resolved_by_kind", "resolved_by_id"},
}


class InvalidDriftTransitionError(Exception):
    def __init__(self, *, drift_id: UUID, from_state: str, action: str):
        super().__init__(
            f"drift {drift_id} cannot {action} from state {from_state}"
        )
        self.drift_id = drift_id
        self.from_state = from_state
        self.action = action


def _drift_originating_actor(
    request: PermissionDriftResolutionRequest,
    actor: ActorIdentity,
) -> tuple[str, str]:
    if actor.actor_kind == "service":
        kind = request.resolved_by_kind or actor.actor_kind
        ident = request.resolved_by_id or actor.actor_id
        return kind, ident
    return actor.actor_kind, actor.actor_id


def resolve_permission_drift(
    db: PostgresDatabase,
    *,
    drift_id: UUID,
    request: PermissionDriftResolutionRequest,
    expected_version: int,
    actor: ActorIdentity,
) -> tuple[PermissionDriftRead, MutationResult]:
    current = read_permission_drift(db, drift_id)

    # R5 — service-layer authority gate BEFORE the mutation. Endpoint-level
    # `_require_scoped` remains as an early-403 short-circuit but is no
    # longer the sole gate; background / CLI / deferred-effects callers
    # hit the same enforcement.
    _require_scoped_authority(
        "permission_drift.write",
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
        actor=actor,
        db=db,
    )

    if current.status in DRIFT_TERMINAL_STATUSES:
        raise InvalidDriftTransitionError(
            drift_id=drift_id, from_state=current.status, action=request.action,
        )
    next_status = VALID_DRIFT_TRANSITIONS.get((current.status, request.action))
    if next_status is None:
        raise InvalidDriftTransitionError(
            drift_id=drift_id, from_state=current.status, action=request.action,
        )

    is_terminal = next_status in DRIFT_TERMINAL_STATUSES
    if is_terminal:
        resolved_kind, resolved_id = _drift_originating_actor(request, actor)
        resolved_at = datetime.now(UTC)
    else:
        resolved_kind, resolved_id, resolved_at = None, None, None
    resolution_reason = request.reason if is_terminal else None

    aggregate_id = str(drift_id)
    action_payload = {
        "action": request.action,
        "reason": request.reason,
        "resolved_by_kind": resolved_kind,
        "resolved_by_id": resolved_id,
    }

    # R1 / shortcut F1 — action_type and change_type are read from the
    # constant dispatch dicts in §10.1, never built via f-string. The
    # prior `f"permission_drift.{request.action}d"` produced
    # `permission_drift.acceptd` for `action="accept"`; the constant
    # table forbids that class of bug.
    action_type = DRIFT_RESOLUTION_ACTION_TYPE[request.action]
    change_type = DRIFT_RESOLUTION_CHANGE_TYPE[request.action]
    from_state = current.status

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        updated = update_permission_drift_resolution(
            connection,
            drift_id=drift_id,
            status=next_status,
            resolved_by_kind=resolved_kind,
            resolved_by_id=resolved_id,
            resolved_at=resolved_at,
            resolution_reason=resolution_reason,
        )
        if updated != 1:
            raise LookupError(f"permission drift {drift_id} was not found")
        return StateChangeDraft(
            change_type=change_type,
            payload_json={
                "status": next_status,
                "resolved_by_kind": resolved_kind,
                "resolved_by_id": resolved_id,
                "resolved_at": None if resolved_at is None else resolved_at.isoformat(),
                "resolution_reason": resolution_reason,
            },
            # R8 / audit F3 — BEFORE/AFTER diff mirrors the shipped
            # applications precedent at
            # `services/api/app/services/applications.py:715-721`.
            diff_json={"from": from_state, "to": next_status},
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_drift",
        aggregate_id=aggregate_id,
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/permission-drift/{drift_id}/resolve",
        ),
        action_type=action_type,
        action_payload=action_payload,
        payload_allowlist=DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST[request.action],
        mutate_projection=mutate_projection,
        scope_kind=current.scope_kind,
        scope_id=current.scope_id,
    )
    return read_permission_drift(db, drift_id), result
```

Notes:
- `InvalidDriftTransitionError` maps to 409 in §6.
- `StaleMutationError` from `mutate_entity` maps to 412.
- `LookupError` / `MissingAggregateError` → 404.
- The shipped lenient `update_permission_drift_status` is removed; no
  caller outside the removed test seam exists in the tree (per AGENTS.md
  No Backwards Compatibility).

Add a service-layer read gate on `list_permission_drift` (R5):

```python
def list_permission_drift(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    scope_kind: str | None,
    scope_id: str | None,
    status: list[str] | None = None,
    role_id: str | None = None,
    reconciliation_run_id: UUID | None = None,
    has_intent: bool | None = None,
) -> list[PermissionDriftRead]:
    # R5 — service-layer authority gate. When the caller omits
    # `scope_kind`, the service demands `permission_drift.read` at the
    # global scope (broad read), matching the endpoint's fallback.
    _require_scoped_authority(
        "permission_drift.read",
        scope_kind=scope_kind or "global",
        scope_id=scope_id,
        actor=actor,
        db=db,
    )
    with db.connection() as connection:
        rows = permission_repo.list_permission_drift(
            connection,
            status=status,
            scope_kind=scope_kind,
            scope_id=scope_id,
            role_id=role_id,
            reconciliation_run_id=reconciliation_run_id,
            has_intent=has_intent,
        )
    return [PermissionDriftRead.model_validate(row) for row in rows]
```

### §5.3 — Reconciliation service (new module)

New file `services/api/app/services/permission_reconciliation.py`.

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.permissions import (
    PermissionReconciliationRunCreate,
    PermissionReconciliationRunRead,
    PermissionSnapshotEntry,
)
from app.repositories.db import PostgresDatabase
from app.repositories import permissions as permission_repo
from app.services.mutations import mutate_entity


RUN_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "scope_kind", "scope_id",
    "originating_actor_kind", "originating_actor_id",
}
RUN_SUBMIT_SNAPSHOT_PAYLOAD_ALLOWLIST: set[str] = {"entry_count"}
# RUN_TERMINAL_STATUSES / VALID_RUN_TRANSITIONS / RUN_ACTION_TYPE /
# RUN_CHANGE_TYPE / DRIFT_CREATE_PAYLOAD_ALLOWLIST are declared in §10.2
# and imported here; re-declared below for local reference.
RUN_TERMINAL_STATUSES = frozenset({"reconciled", "failed"})
VALID_RUN_TRANSITIONS: dict[tuple[str, str], str] = {
    ("requested", "submit_snapshot"):      "snapshot_submitted",
    ("snapshot_submitted", "reconcile"):   "reconciled",
    ("snapshot_submitted", "fail"):        "failed",
    ("requested", "fail"):                 "failed",
}


class ReconciliationRunNotFoundError(LookupError):
    pass


class ReconciliationRunConflictError(Exception):
    def __init__(self, *, run_id: UUID, status: str):
        super().__init__(f"run {run_id} in status {status}")
        self.run_id = run_id
        self.status = status


def _requested_by(actor: ActorIdentity,
                  request: PermissionReconciliationRunCreate) -> tuple[str, str]:
    if actor.actor_kind == "service" and request.originating_actor_kind and request.originating_actor_id:
        return request.originating_actor_kind, request.originating_actor_id
    return actor.actor_kind, actor.actor_id


def create_reconciliation_run(
    db: PostgresDatabase,
    *,
    request: PermissionReconciliationRunCreate,
    actor: ActorIdentity,
) -> tuple[PermissionReconciliationRunRead, MutationResult]:
    # R5 — service-layer authority gate (mirrors applications precedent).
    _require_scoped_authority(
        "permission_reconciliation_run.write",
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
        actor=actor,
        db=db,
    )

    run_id = uuid4()
    requested_by_kind, requested_by_id = _requested_by(actor, request)
    aggregate_id = str(run_id)

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        permission_repo.insert_reconciliation_run(
            connection,
            row={
                "id": run_id,
                "scope_kind": request.scope_kind,
                "scope_id": request.scope_id,
                "requested_by_kind": requested_by_kind,
                "requested_by_id": requested_by_id,
            },
        )
        return StateChangeDraft(
            # R3 / shortcut F3 — change_type comes from the RUN_CHANGE_TYPE
            # dispatch dict declared in §10.2, never an inline literal.
            change_type=RUN_CHANGE_TYPE["create"],
            payload_json={
                "status": "requested",
                "scope_kind": request.scope_kind,
                "scope_id": request.scope_id,
                "requested_by_kind": requested_by_kind,
                "requested_by_id": requested_by_id,
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="permission_reconciliation_run",
        aggregate_id=aggregate_id,
        request=MutationRequest(
            expected_version=0,
            actor_kind=actor.actor_kind,
            actor_id=actor.actor_id,
            reason_text=None,
            request_surface="api:/api/v1/permission-reconciliation/runs",
        ),
        # R3 / shortcut F3 — action_type via RUN_ACTION_TYPE, not inline.
        action_type=RUN_ACTION_TYPE["create"],
        action_payload={
            "scope_kind": request.scope_kind,
            "scope_id": request.scope_id,
            "originating_actor_kind": request.originating_actor_kind,
            "originating_actor_id": request.originating_actor_id,
        },
        payload_allowlist=RUN_CREATE_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
    )
    return read_reconciliation_run(db, run_id), result


def read_reconciliation_run(
    db: PostgresDatabase, run_id: UUID,
) -> PermissionReconciliationRunRead:
    with db.connection() as connection:
        row = permission_repo.fetch_reconciliation_run(connection, run_id)
        if row is None:
            raise ReconciliationRunNotFoundError(str(run_id))
        drift_ids = permission_repo.list_drift_ids_by_run(connection, run_id)
    payload = dict(row)
    payload["drift_ids"] = drift_ids
    return PermissionReconciliationRunRead.model_validate(payload)


def submit_reconciliation_snapshot(
    db: PostgresDatabase,
    *,
    run_id: UUID,
    entries: list[PermissionSnapshotEntry],
    actor: ActorIdentity,
) -> tuple[PermissionReconciliationRunRead, MutationResult]:
    # Step 1: load run (no tx yet).
    existing = read_reconciliation_run(db, run_id)

    # R5 — service-layer authority gate. Scope is loaded from the run row
    # so the mutation is gated regardless of how the caller arrived here.
    _require_scoped_authority(
        "permission_reconciliation_run.write",
        scope_kind=existing.scope_kind,
        scope_id=existing.scope_id,
        actor=actor,
        db=db,
    )

    # Step 2: terminal replay idempotency (AC4). R2 / shortcut F2 —
    # terminal-kind is discriminated via `RUN_TERMINAL_STATUSES` membership,
    # never inline string literals. The two terminal kinds are split on
    # outcome: `reconciled` returns cached, `failed` raises 409.
    if existing.status in RUN_TERMINAL_STATUSES:
        if existing.status == "reconciled":
            # R8 / shortcut F7 — compute head version once.
            head_version = _read_head_version(db, run_id)
            return existing, MutationResult(
                version=head_version,
                etag=f'"{head_version}"',
            )
        # existing.status == "failed"
        raise ReconciliationRunConflictError(
            run_id=run_id, status=existing.status,
        )
    if existing.status != "requested":
        # snapshot_submitted but not terminal: treat as conflict.
        raise ReconciliationRunConflictError(
            run_id=run_id, status=existing.status,
        )

    # Step 3–9: advance head + diff + insert drift + advance head in one tx.
    try:
        with db.transaction() as connection:
            _advance_run_submit(connection, run_id=run_id, actor=actor,
                                entry_count=len(entries))
            drift_rows = _build_drift_rows(connection, run=existing,
                                           entries=entries)
            # R4 / shortcut F4 — repository returns ONLY newly-inserted ids
            # (conflict rows are silently skipped). Every id in this list is
            # therefore safe to mutate_entity with expected_version=0. The
            # run's final drift set (new + any pre-existing) is read back
            # via list_drift_ids_by_run below.
            new_drift_ids = permission_repo.insert_permission_drift_batch(
                connection, rows=drift_rows,
            )
            for drift_id in new_drift_ids:
                _record_drift_created(
                    connection,
                    drift_id=drift_id,
                    drift_row=_drift_row_by_id(drift_rows, drift_id),
                    actor=actor,
                )
            run_drift_ids = permission_repo.list_drift_ids_by_run(
                connection, run_id,
            )
            _advance_run_reconciled(
                connection, run_id=run_id, actor=actor,
                drift_ids=run_drift_ids,
            )
    except Exception as error:
        # D8 step 10 — advance run to failed in a new tx.
        _advance_run_failed(db, run_id=run_id, actor=actor,
                            failure_reason=repr(error)[:500])
        raise

    # R8 / shortcut F7 — compute head version once here too.
    head_version = _read_head_version(db, run_id)
    return read_reconciliation_run(db, run_id), MutationResult(
        version=head_version,
        etag=f'"{head_version}"',
    )
```

Helpers:

- `_advance_run_submit(connection, *, run_id, actor, entry_count)` — calls
  `mutate_entity` against aggregate
  `("permission_reconciliation_run", str(run_id))` with:
  - `action_type=RUN_ACTION_TYPE["submit_snapshot"]` (R3),
  - `action_payload={"entry_count": entry_count}` (R7 / audit F2),
  - `payload_allowlist=RUN_ADVANCE_PAYLOAD_ALLOWLIST["submit_snapshot"]`,
  - `mutate_projection` that calls
    `permission_repo.update_reconciliation_run_status(...,
    status="snapshot_submitted", snapshot_submitted_at=now)` and returns
    `StateChangeDraft(change_type=RUN_CHANGE_TYPE["submit_snapshot"],
    payload_json={"status": "snapshot_submitted",
    "snapshot_submitted_at": now.isoformat(),
    "entry_count": entry_count},
    diff_json={"from": "requested", "to": "snapshot_submitted"})`
    (R7 + R8).
- `_advance_run_reconciled(connection, *, run_id, actor, drift_ids)` —
  `mutate_entity` with:
  - `action_type=RUN_ACTION_TYPE["reconcile"]` (R3),
  - `action_payload={"drift_count": len(drift_ids)}` (R7),
  - `payload_allowlist=RUN_ADVANCE_PAYLOAD_ALLOWLIST["reconcile"]`,
  - `mutate_projection` that calls
    `permission_repo.update_reconciliation_run_status(...,
    status="reconciled", reconciled_at=now)` and returns
    `StateChangeDraft(change_type=RUN_CHANGE_TYPE["reconcile"],
    payload_json={"status": "reconciled",
    "reconciled_at": now.isoformat(),
    "drift_count": len(drift_ids),
    "drift_ids": [str(d) for d in drift_ids]},
    diff_json={"from": "snapshot_submitted", "to": "reconciled"})`
    (R7 + R8).
- `_advance_run_failed(db, *, run_id, actor, failure_reason)` — runs in
  its own transaction (not the caller's) per D8 step 10. Calls
  `mutate_entity` with:
  - `action_type=RUN_ACTION_TYPE["fail"]` (R3),
  - `action_payload={"failure_reason": failure_reason}` (R7 / audit F2),
  - `payload_allowlist=RUN_ADVANCE_PAYLOAD_ALLOWLIST["fail"]`,
  - `mutate_projection` that calls
    `permission_repo.update_reconciliation_run_status(...,
    status="failed", failed_at=now, failure_reason=failure_reason)` and
    returns
    `StateChangeDraft(change_type=RUN_CHANGE_TYPE["fail"],
    payload_json={"status": "failed",
    "failed_at": now.isoformat(),
    "failure_reason": failure_reason},
    diff_json={"from": <prior_status>, "to": "failed"})`
    (R7 + R8). `prior_status` is read from the run row inside the
    projection's own transaction so the diff is accurate whether the
    failure path entered from `requested` or `snapshot_submitted`.
- `_build_drift_rows(connection, run, entries)` applies the D8 diff
  algorithm:
  1. `intents = permission_repo.list_permission_intents(connection,
     scope_kind=run.scope_kind, scope_id=run.scope_id,
     include_expired=False)` — only live intents.
  2. Build `intent_by_key = {(i.kind, i.role_id, i.channel_id or None): i}`.
  3. Build `snapshot_by_key = {(e.kind, e.role_id, getattr(e, 'channel_id',
     None)): e}`.
  4. For each key in the sorted union:
     - masks equal → skip;
     - mismatch → emit drift with `permission_intent_id=intent.id`,
       `intent_version=<aggregate head>`, both mask sides filled;
     - intent only → drift with cleared-state actuals
       (`'0'` for guild_role; `'0'/'0'` for channel_role);
     - snapshot only → drift with
       `permission_intent_id=NULL, intent_version=NULL`, scope/target
       from the run + snapshot entry, `status='detected'`.
  5. Each returned drift row carries `reconciliation_run_id=run.id`,
     pre-assigned `id=uuid4()`, `status='detected'`, scope/target
     normalized to the run’s scope.
- `_drift_row_by_id(drift_rows, drift_id)` — linear lookup of the
  pre-built drift row dict by id so `_record_drift_created` can populate
  `action_payload` and `payload_json` from the same fields the batch
  insert used.
- `_record_drift_created(connection, *, drift_id, drift_row, actor)` —
  issues a `mutate_entity(...)` call on
  `("permission_drift", str(drift_id))` with:
  - `expected_version=0`,
  - `action_type="permission_drift.create"`,
  - `action_payload={k: drift_row[k] for k in
    DRIFT_CREATE_PAYLOAD_ALLOWLIST if k in drift_row}` (R6 / audit F1),
  - `payload_allowlist=DRIFT_CREATE_PAYLOAD_ALLOWLIST` (R6 / audit F1),
  - `mutate_projection` that runs a no-op projection and returns
    `StateChangeDraft(change_type="permission_drift.created",
    payload_json={"drift_id": str(drift_id),
    "reconciliation_run_id": str(drift_row["reconciliation_run_id"]),
    "permission_intent_id":
      None if drift_row["permission_intent_id"] is None
      else str(drift_row["permission_intent_id"]),
    "intent_version": drift_row["intent_version"],
    "scope_kind": drift_row["scope_kind"],
    "scope_id": drift_row["scope_id"],
    "role_id": drift_row["role_id"],
    "channel_id": drift_row["channel_id"],
    "kind": drift_row["kind"],
    "status": drift_row["status"],
    "actual_bits": drift_row.get("actual_bits"),
    "actual_allow_bits": drift_row.get("actual_allow_bits"),
    "actual_deny_bits": drift_row.get("actual_deny_bits"),
    "intended_bits": drift_row.get("intended_bits"),
    "intended_allow_bits": drift_row.get("intended_allow_bits"),
    "intended_deny_bits": drift_row.get("intended_deny_bits")})`
    (R6 / audit F1).
  The row is already inserted by the batch insert; the `mutate_projection`
  does no additional repository work. This guarantees an aggregate head
  exists for every drift id, satisfying OCC for the subsequent resolve
  endpoint.
  R4 / shortcut F4 — `_record_drift_created` is only invoked for ids in
  `new_drift_ids`, which is the filtered `insert_permission_drift_batch`
  return (newly-inserted rows only). Conflict rows are never passed to
  `_record_drift_created`; `expected_version=0` can therefore never fire
  against an existing aggregate head.
- `_read_head_version(db, run_id)` reads `aggregate_heads.current_seq`
  keyed by `('permission_reconciliation_run', str(run_id))`. Called once
  per terminal-replay return path (R8 / shortcut F7).

The single-transaction wrapper is provided by `db.transaction()` which
is the same substrate `mutate_entity` uses when `connection` is None;
passing the explicit `connection` keeps all mutations inside one
transaction. On exception, the outer `with` block rolls back and the
fallback `_advance_run_failed` runs in its own connection.

---

## §6 — Endpoints

Subpackage mirroring `services/api/app/api/v1/endpoints/applications/`.
Add `services/api/app/api/v1/endpoints/permissions/` with four files.
Import-time side effects minimal; aggregator returns a single `router`.

### §6.1 — `__init__.py`

```python
from fastapi import APIRouter

from .drift import router as drift_router
from .intents import router as intents_router
from .reconciliation import router as reconciliation_router


router = APIRouter()
router.include_router(intents_router, tags=["permission-intents"])
router.include_router(drift_router, tags=["permission-drift"])
router.include_router(reconciliation_router, tags=["permission-reconciliation"])
```

Mount in `services/api/app/api/v1/router.py`:

```python
from app.api.v1.endpoints import (
    ...,
    permissions,
    ...,
)
...
router.include_router(permissions.router)
```

### §6.2 — `intents.py`

```python
router = APIRouter(prefix="/api/v1/permission-intents")


@router.post("", response_model=PermissionIntentRead, status_code=HTTPStatus.CREATED)
def create_intent_endpoint(
    body: PermissionIntentCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionIntentRead:
    _require_scoped(actor, db, body.scope_kind, body.scope_id,
                    "permission_intent.write")
    try:
        read, result = create_permission_intent(db, body, actor=actor)
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.patch("/{intent_id}", response_model=PermissionIntentRead)
def patch_intent_endpoint(
    intent_id: UUID,
    body: PermissionIntentUpdate,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionIntentRead:
    expected_version = parse_if_match_strong(request)
    try:
        current = read_permission_intent(db, intent_id)
        _require_scoped(actor, db, current.scope_kind, current.scope_id,
                        "permission_intent.write")
        read, result = update_permission_intent(
            db, intent_id,
            expected_version=expected_version,
            patch=body.model_dump(mode="python", exclude_unset=True),
            actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.get("", response_model=list[PermissionIntentRead])
def list_intents_endpoint(
    scope_kind: PermissionIntentScopeKind,
    scope_id: str | None = None,
    role_id: str | None = None,
    channel_id: str | None = None,
    kind: PermissionIntentKind | None = None,
    temporary: bool | None = None,
    include_expired: bool = False,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[PermissionIntentRead]:
    _require_scoped(actor, db, scope_kind, scope_id,
                    "permission_intent.read")
    return list_permission_intents(
        db, scope_kind=scope_kind, scope_id=scope_id, role_id=role_id,
        channel_id=channel_id, kind=kind, temporary=temporary,
        include_expired=include_expired,
    )
```

`_require_scoped(actor, db, scope_kind, scope_id, permission)` manually
builds an `AuthorityRequirement` and calls `evaluate(...)` (mirroring the
SLICE-012 precedent from `services/api/app/api/v1/endpoints/applications/lifecycle.py`
where body-derived scope cannot use the static-param `RequireAuthority`
helper). It raises `PermissionError("authority denied")` on denial,
which maps to 403 via `raise_known_permission_error`.

### §6.3 — `drift.py`

```python
router = APIRouter(prefix="/api/v1/permission-drift")


@router.get("", response_model=list[PermissionDriftRead])
def list_drift_endpoint(
    status: list[str] | None = Query(default=None),
    scope_kind: PermissionIntentScopeKind | None = None,
    scope_id: str | None = None,
    role_id: str | None = None,
    reconciliation_run_id: UUID | None = None,
    has_intent: bool | None = None,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[PermissionDriftRead]:
    _require_scoped(
        actor, db,
        scope_kind or "global",
        scope_id,
        "permission_drift.read",
    )
    return list_permission_drift(
        db, status=status, scope_kind=scope_kind, scope_id=scope_id,
        role_id=role_id, reconciliation_run_id=reconciliation_run_id,
        has_intent=has_intent,
    )


@router.post("/{drift_id}/resolve", response_model=PermissionDriftRead)
def resolve_drift_endpoint(
    drift_id: UUID,
    body: PermissionDriftResolutionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionDriftRead:
    expected_version = parse_if_match_strong(request)
    try:
        current = read_permission_drift(db, drift_id)
        _require_scoped(actor, db, current.scope_kind, current.scope_id,
                        "permission_drift.write")
        read, result = resolve_permission_drift(
            db, drift_id=drift_id, request=body,
            expected_version=expected_version, actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read
```

For the list endpoint: when no `scope_kind` is provided, the authority
check falls back to requiring `permission_drift.read` at global scope.
This matches the shipped read-filter pattern where an operator with
broad reads sees everything, while chapter officers only see their
chapter by passing `scope_kind=chapter&scope_id=<id>`.

### §6.4 — `reconciliation.py`

```python
router = APIRouter(prefix="/api/v1/permission-reconciliation")


@router.post("/runs", response_model=PermissionReconciliationRunRead,
             status_code=HTTPStatus.CREATED)
def create_run_endpoint(
    body: PermissionReconciliationRunCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionReconciliationRunRead:
    _require_scoped(actor, db, body.scope_kind, body.scope_id,
                    "permission_reconciliation_run.write")
    try:
        read, result = create_reconciliation_run(db, request=body, actor=actor)
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read


@router.post("/runs/{run_id}/snapshots",
             response_model=PermissionReconciliationRunRead)
def submit_snapshot_endpoint(
    run_id: UUID,
    body: ReconciliationSnapshotRequest,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PermissionReconciliationRunRead:
    try:
        existing = read_reconciliation_run(db, run_id)
        _require_scoped(actor, db, existing.scope_kind, existing.scope_id,
                        "permission_reconciliation_run.write")
        read, result = submit_reconciliation_snapshot(
            db, run_id=run_id, entries=list(body.entries), actor=actor,
        )
    except Exception as error:
        raise_known_permission_error(error)
    set_etag(response, result.etag)
    return read
```

### §6.5 — Shared helper module `_shared.py`

Mirror `services/api/app/api/v1/endpoints/applications/_shared.py`
with:
- `get_db(request)`
- `parse_if_match_strong(request)`
- `set_etag(response, etag)`
- `raise_known_permission_error(error)` — maps
  `PermissionIntentNotFoundError`, `PermissionDriftNotFoundError`,
  `ReconciliationRunNotFoundError`, `MissingAggregateError`, `LookupError`
  → 404; `StaleMutationError` → 412;
  `InvalidDriftTransitionError`, `ReconciliationRunConflictError` → 409;
  `PermissionError` → 403; `ValueError` → 422.

---

## §7 — Discord Adapter

Three new files under `services/discord/` plus the handler registration.

### §7.1 — Contracts (`services/discord/app/contracts/permissions.py`)

Mirror the API contracts needed by the adapter:
- `DiscordReconciliationRunCreate` — body sent to POST /runs
- `DiscordReconciliationRunRead` — parsed response
- `DiscordPermissionSnapshotEntry` — per-entry payload
- `DiscordReconciliationSnapshotRequest` — aggregated payload

Same field shapes as the API (`scope_kind`, `scope_id`, decimal bit
strings, discriminated kind union). Independent package to preserve
service isolation.

### §7.2 — API client (`services/discord/app/infrastructure/permission_client.py`)

```python
class PermissionApiClient:
    def __init__(self, api_client: ApiClient, service_actor_id: str = "permission-reconciler"):
        self._api = api_client
        self._actor_id = service_actor_id

    async def create_reconciliation_run(
        self, *, scope_kind: str, scope_id: str | None,
        originating_actor_kind: str, originating_actor_id: str,
    ) -> DiscordReconciliationRunRead:
        response = await self._api.call(ApiTransportRequest(
            method="POST",
            path="/api/v1/permission-reconciliation/runs",
            headers={"X-Actor-Kind": "service", "X-Actor-Id": self._actor_id},
            json={
                "scope_kind": scope_kind,
                "scope_id": scope_id,
                "originating_actor_kind": originating_actor_kind,
                "originating_actor_id": originating_actor_id,
            },
        ))
        response.raise_for_status()
        return DiscordReconciliationRunRead.model_validate_json(response.body)

    async def submit_snapshot(
        self, *, run_id: UUID, entries: list[DiscordPermissionSnapshotEntry],
    ) -> DiscordReconciliationRunRead:
        response = await self._api.call(ApiTransportRequest(
            method="POST",
            path=f"/api/v1/permission-reconciliation/runs/{run_id}/snapshots",
            headers={"X-Actor-Kind": "service", "X-Actor-Id": self._actor_id},
            json={"entries": [e.model_dump(mode="json") for e in entries]},
        ))
        response.raise_for_status()
        return DiscordReconciliationRunRead.model_validate_json(response.body)
```

Header names and `ApiClient.call` signature follow
`services/discord/app/infrastructure/api_client.py:25-65`. Correlation
ID propagation is handled inside `ApiClient.call` automatically.

### §7.3 — Handler (`services/discord/app/handlers/permissions.py`)

```python
async def handle_reconcile_permissions(
    envelope: InteractionEnvelope,
    *,
    permission_client: PermissionApiClient,
    guild: Any,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    scope_kind, scope_id = _resolve_scope(envelope, guild)

    try:
        run = await permission_client.create_reconciliation_run(
            scope_kind=scope_kind, scope_id=scope_id,
            originating_actor_kind=envelope.actor_kind,
            originating_actor_id=envelope.actor_id,
        )
    except ApiHttpError as error:
        return _ephemeral_error(f"could not start reconciliation: {error.reason}")

    entries = _build_snapshot(guild, scope_kind, scope_id)

    try:
        result = await permission_client.submit_snapshot(
            run_id=run.id, entries=entries,
        )
    except ApiConflictError:
        # 409 on snapshot POST → terminal replay; fetch current state
        # of the run to surface drift summary.
        result = await permission_client.read_run(run.id)
    except ApiPreconditionFailedError:
        # 412 must not retry locally — surface the error. The API owns
        # the run lifecycle and we don't hold a stale version ourselves.
        return _ephemeral_error(
            "reconciliation conflicted with a concurrent run; retry."
        )
    except ApiHttpError as error:
        return _ephemeral_error(
            f"snapshot submission failed: {error.reason}"
        )

    drift_count = len(result.drift_ids)
    return InteractionResult(
        success=True,
        response_text=f"Reconciliation run {run.id} complete "
                      f"({drift_count} drift row(s)).",
    )


def _resolve_scope(envelope, guild) -> tuple[str, str | None]:
    chapter_id = envelope.arguments.get("chapter")
    if chapter_id:
        return "chapter", str(chapter_id)
    return "global", None


def _build_snapshot(guild, scope_kind: str, scope_id: str | None):
    entries: list[DiscordPermissionSnapshotEntry] = []
    for role in guild.roles:
        if role == guild.default_role:
            continue
        entries.append(GuildRolePermissionSnapshotEntry(
            kind="guild_role",
            role_id=str(role.id),
            permission_bits=_decimal_bits(role.permissions.value),
        ))
    if scope_kind == "chapter":
        for channel in _channels_for_chapter(guild, scope_id):
            for target, overwrite in (channel.overwrites or {}).items():
                if not _is_role(target):
                    continue
                allow, deny = overwrite.pair()
                entries.append(ChannelRolePermissionSnapshotEntry(
                    kind="channel_role",
                    role_id=str(target.id),
                    channel_id=str(channel.id),
                    allow_bits=_decimal_bits(allow.value),
                    deny_bits=_decimal_bits(deny.value),
                ))
    # D13: `global` scope does NOT walk channels.
    return entries
```

- `_channels_for_chapter(guild, scope_id)` — resolves chapter channels
  via the same chapter repository helpers that
  `services/discord/app/handlers/chapters.py:200-247` uses. Zero
  `fetch_*` calls per D13.
- `_decimal_bits(value: int) -> str` — `str(int(value))`.
- `_ephemeral_error(msg)` returns `InteractionResult(success=False,
  response_text=msg)` (ephemeral is the contract default).

### §7.4 — Command registration
(`services/discord/app/commands/permissions.py`)

```python
RECONCILE_PERMISSIONS_COMMAND = "reconcile-permissions"


def register_permission_commands(bot):
    async def _handler(envelope: InteractionEnvelope) -> InteractionResult:
        guild = None
        if envelope.guild_id is not None and hasattr(bot, "get_guild"):
            guild = bot.get_guild(int(envelope.guild_id))
        return await handle_reconcile_permissions(
            envelope,
            permission_client=bot.permission_client,
            guild=guild,
        )

    bot.register_interaction_handler(RECONCILE_PERMISSIONS_COMMAND, _handler)
```

Slash command surface: `/reconcile-permissions [chapter:Chapter?]`.
When invoked with a chapter argument the run is chapter-scoped; absent
the argument it is global-scoped per D13.

---

## §8 — Tests

Every test carries an AC-referenced docstring (`"""AC1: …"""` /
`"""AC2: …"""` / etc.) per SLICE-021 precedent. Per AGENTS.md, the test
agent sees only contracts and endpoint signatures — service internals
are not imported.

### §8.1 — WU-027 `services/api/tests/test_permission_intents.py`

- `test_create_intent_persists_full_target_and_returns_etag` — AC1
- `test_patch_intent_with_matching_if_match_advances_version` — AC1
- `test_patch_intent_with_stale_if_match_returns_412` — AC1
- `test_create_intent_rejects_scope_kind_member` — AC1 (contract + DB)
- `test_create_guild_role_intent_rejects_allow_deny_fields` — AC1
- `test_create_channel_role_intent_requires_channel_allow_deny` — AC1
- `test_list_intents_filters_by_scope_kind_scope_id` — AC1
- `test_list_intents_excludes_expired_by_default` — AC1
- `test_list_intents_requires_permission_intent_read` — AC1
- `test_patch_intent_requires_permission_intent_write` — AC1

### §8.2 — WU-028A `services/api/tests/test_permission_drift.py`

- `test_list_drift_returns_intent_linked_and_orphaned_rows` — AC2
- `test_list_drift_has_intent_filter` — AC2
- `test_resolve_drift_detected_to_acknowledged_with_if_match` — AC2
- `test_resolve_drift_acknowledged_to_reconciled_populates_resolved_fields` — AC2
- `test_resolve_drift_detected_to_accepted_skips_acknowledged` — AC2
- `test_resolve_drift_stale_if_match_returns_412` — AC2
- `test_resolve_drift_user_actor_cannot_spoof_resolved_by_fields` — AC2
- `test_resolve_drift_service_actor_sets_resolved_by_from_body` — AC2
- `test_resolve_drift_terminal_status_returns_409` — AC2
- `test_resolve_drift_invalid_transition_returns_409` — AC2
- `test_resolve_drift_accept_emits_correct_change_type` — AC2 (R1 /
  shortcut F1 regression guard — asserts that resolving with
  `action="accept"` writes an `activity_state_changes` row whose
  `change_type` is exactly `permission_drift.accepted`, not
  `permission_drift.acceptd`; parametrised across all three actions to
  pin each dispatch-table entry against the `DRIFT_RESOLUTION_CHANGE_TYPE`
  constants declared in §10.1).

### §8.3 — WU-028B-api `services/api/tests/test_permission_reconciliation_api.py`

- `test_create_run_returns_requested_status_and_etag` — AC3
- `test_submit_snapshot_materializes_drift_for_mismatches` — AC3
- `test_submit_snapshot_materializes_drift_for_orphaned_actual` — AC3
- `test_submit_snapshot_emits_cleared_state_drift_for_missing_actual` — AC3
- `test_submit_snapshot_skips_matching_intent_actual` — AC3
- `test_submit_snapshot_global_scope_skips_channel_entries` — AC3
- `test_submit_snapshot_idempotent_replay_returns_same_drift_set` — AC4
- `test_submit_snapshot_terminal_run_returns_cached_result` — AC4
- `test_submit_snapshot_without_permission_returns_403` — AC3
- `test_submit_snapshot_duplicate_entry_rejected_at_contract` — AC3
- `test_submit_snapshot_failure_advances_run_to_failed` — AC3
- `test_create_run_scope_shape_validated` — AC3

### §8.4 — WU-028B-discord `services/discord/tests/test_permission_reconciliation_adapter.py`

- `test_handler_creates_run_walks_guild_roles_and_posts_snapshot` — AC4
- `test_handler_chapter_scope_walks_chapter_channels_only` — AC4 (D13)
- `test_handler_global_scope_does_not_walk_channels` — AC4 (D13)
- `test_handler_retry_reuses_run_id_no_second_run_created` — AC4
- `test_handler_snapshot_409_fetches_cached_result` — AC4
- `test_handler_snapshot_412_surfaces_ephemeral_error_no_retry_loop` — AC4
- `test_handler_never_calls_drift_mutation_endpoints` — AC4
- `test_handler_never_calls_fetch_channel_or_fetch_member` — AC4 (D13)
- `test_handler_serializes_permission_bits_as_decimal_strings` — AC4

Test scaffolding:
- API tests use `httpx.AsyncClient` against the FastAPI app fixture and
  seed service-actor auth via the shipped test helpers
  (matches SLICE-012 pattern in existing `test_applications.py`).
- Reconciliation tests seed intents via the intent API, then mint a run
  via the run API, then submit a snapshot via the snapshot endpoint.
- Discord tests mock `guild.roles`, `guild.channels`, and
  `PermissionApiClient`; they assert on `permission_client.method_calls`.

---

## §9 — Service Actor Grants

The `permission-reconciler` service actor is seeded inside
`wu-028b_permission_reconciliation_runs` (see §2.3). Permissions granted:

- `permission_intent.read`
- `permission_drift.read`
- `permission_drift.write`
- `permission_reconciliation_run.write`

Scope: `global`, `scope_id NULL`. The seed uses the exact-containment
idempotency pattern from wu-037 (`@>` and `<@` against the JSONB
permission array, active-grant guard on `revoked_at` and `expires_at`).

**Chapter-scope coverage**: per SLICE-008 precedent, a global-scoped
grant satisfies a chapter-scope authority check for the same permission
name (`services/api/app/services/authority.py` `evaluate(...)` — the
requirement `scope_kind='chapter', scope_id=X` is satisfied by an
active grant at `scope_kind='global'` for the same permission). A
separate chapter-scope seed is therefore not required, and would add
attack surface without new capability.

Operators who are **not** the seeded service actor must be granted the
relevant permission(s) through the existing authority API. SLICE-014
does not ship a new `policy_type` or seeded operator role.

---

## §10 — Constants and Registries

Per §4 of the research and existing per-module convention (chapters,
applications, tickets all define local constant dicts), these constants
live in the service module that uses them. No central registry change.

### §10.1 — `services/api/app/services/permissions.py`

```python
INTENT_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "kind", "scope_kind", "scope_id", "role_id", "channel_id",
    "permission_bits", "allow_bits", "deny_bits",
    "reason", "temporary", "expires_at",
}
INTENT_UPDATE_PAYLOAD_ALLOWLIST: set[str] = {
    "reason", "temporary", "expires_at",
    "permission_bits", "allow_bits", "deny_bits",
}

DRIFT_RESOLUTION_TARGET_STATUS: dict[str, str] = {
    "acknowledge": "acknowledged",
    "reconcile":   "reconciled",
    "accept":      "accepted",
}
VALID_DRIFT_TRANSITIONS: dict[tuple[str, str], str] = {
    ("detected", "acknowledge"): "acknowledged",
    ("detected", "reconcile"):   "reconciled",
    ("detected", "accept"):      "accepted",
    ("acknowledged", "reconcile"): "reconciled",
    ("acknowledged", "accept"):    "accepted",
}
DRIFT_TERMINAL_STATUSES = frozenset({"reconciled", "accepted"})
DRIFT_RESOLUTION_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    "acknowledge": {"action", "reason", "resolved_by_kind", "resolved_by_id"},
    "reconcile":   {"action", "reason", "resolved_by_kind", "resolved_by_id"},
    "accept":      {"action", "reason", "resolved_by_kind", "resolved_by_id"},
}

# R1 / shortcut F1 — constant-lookup dispatch dicts replacing the prior
# f-string construction of `permission_drift.{action}` /
# `permission_drift.{action}d`. The f-string form silently produced
# `permission_drift.acceptd` for `action="accept"`; constant dispatch
# forbids that class of bug and matches
# `services/api/app/services/applications.py:68-78` precedent.
DRIFT_RESOLUTION_ACTION_TYPE: dict[str, str] = {
    "acknowledge": "permission_drift.acknowledge",
    "reconcile":   "permission_drift.reconcile",
    "accept":      "permission_drift.accept",
}
DRIFT_RESOLUTION_CHANGE_TYPE: dict[str, str] = {
    "acknowledge": "permission_drift.acknowledged",
    "reconcile":   "permission_drift.reconciled",
    "accept":      "permission_drift.accepted",
}
```

### §10.2 — `services/api/app/services/permission_reconciliation.py`

```python
VALID_RUN_TRANSITIONS: dict[tuple[str, str], str] = {
    ("requested", "submit_snapshot"):    "snapshot_submitted",
    ("snapshot_submitted", "reconcile"): "reconciled",
    ("snapshot_submitted", "fail"):      "failed",
    ("requested", "fail"):               "failed",
}
RUN_TERMINAL_STATUSES = frozenset({"reconciled", "failed"})
RUN_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "scope_kind", "scope_id",
    "originating_actor_kind", "originating_actor_id",
}
RUN_ADVANCE_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    "submit_snapshot": {"entry_count"},
    "reconcile":       {"drift_count"},
    "fail":            {"failure_reason"},
}

# R3 / shortcut F3 — action_type / change_type dispatch dicts for the run
# lifecycle. The `create` / `submit_snapshot` / `reconcile` / `fail` keys
# match `RUN_ADVANCE_PAYLOAD_ALLOWLIST` plus the create key so the service
# never constructs an audit event name inline.
RUN_ACTION_TYPE: dict[str, str] = {
    "create":          "permission_reconciliation_run.create",
    "submit_snapshot": "permission_reconciliation_run.submit_snapshot",
    "reconcile":       "permission_reconciliation_run.reconcile",
    "fail":            "permission_reconciliation_run.fail",
}
RUN_CHANGE_TYPE: dict[str, str] = {
    "create":          "permission_reconciliation_run.created",
    "submit_snapshot": "permission_reconciliation_run.snapshot_submitted",
    "reconcile":       "permission_reconciliation_run.reconciled",
    "fail":            "permission_reconciliation_run.failed",
}

# R6 / audit F1 — allowlist for `_record_drift_created`. Pins the keys
# the drift-create audit row exposes on both `action_payload` (mutation
# request) and `StateChangeDraft.payload_json` (projection). Without this
# the helper's action_payload would be filtered to `{}` by `_redact_payload`
# at `services/api/app/services/mutations.py:37-48` and the BEFORE/AFTER
# projection could not reconstruct the drift target.
DRIFT_CREATE_PAYLOAD_ALLOWLIST: set[str] = {
    "drift_id", "reconciliation_run_id", "permission_intent_id",
    "intent_version", "scope_kind", "scope_id", "role_id",
    "channel_id", "kind", "status",
}
```

### §10.3 — `change_type` names (state-change projections)

- `permission_intent.created`, `permission_intent.updated` (already shipped)
- `permission_drift.created`, `permission_drift.acknowledged`,
  `permission_drift.reconciled`, `permission_drift.accepted`
  (drift-side entries served by `DRIFT_RESOLUTION_CHANGE_TYPE` in §10.1
  and the `permission_drift.created` literal in `_record_drift_created`).
- `permission_reconciliation_run.created`,
  `permission_reconciliation_run.snapshot_submitted`,
  `permission_reconciliation_run.reconciled`,
  `permission_reconciliation_run.failed`
  (all four served by `RUN_CHANGE_TYPE` in §10.2 — R3 renamed the
  create-transition change_type from `.requested` to `.created` for
  symmetry with the verb-past pattern the other three follow and with
  `permission_intent.created`).

No magic strings elsewhere. `VALID_DRIFT_TRANSITIONS` / etc. are
extended by future slices with `.update({...})`, never inline compare
(matches `services/api/app/services/applications.py:48-66` precedent).

---

## §11 — Explicitly Out of Scope

Per synthesis D8/D9/D15 and research §9 open questions:

- Automatic / scheduled reconciliation — deferred; the seeded service
  actor is only used for manual Discord-adapter-triggered runs.
- `requested → failed` transition on TTL — lifecycle is wired but no
  scheduler is introduced in this slice.
- "Accept orphaned drift creates a new intent" convenience flow —
  deferred; in this slice, `accept` marks drift resolved only; a
  follow-up intent create is a separate operator action.
- Drift notifications / alerting — deferred to SLICE-015 consumer.
- `GET /api/v1/permission-reconciliation/runs/{run_id}` read endpoint —
  deferred; adapters observe runs via the snapshot POST idempotent
  replay behavior.
- Per-action permission splits (separate `acknowledge` vs `reconcile`
  vs `accept` permission names) — deferred.
- Read-only drift operator role scheme — deferred.
- Cross-run drift dedup; per-scope uniqueness when
  `reconciliation_run_id IS NULL` — deferred.
- JSONB snapshot archive on the run row — not stored; the diff consumes
  and discards the snapshot payload.
- Cross-service E2E tests — deferred to a future integration slice.
- Property-based / fuzz tests for the diff engine — deferred.
- Member-level channel overwrite serialization — deferred; only role
  targets are in scope.
- New `policy_type` / seeded operator policy changes — deferred; new
  permission strings are introduced only through authority grants.
- Backwards-compatibility shims for the removed
  `update_permission_drift_status` function — none; per AGENTS.md
  No Backwards Compatibility.
- **Denial-audit rows.** Denied authority checks emit 403 but do not
  write audit rows. This matches shipped `RequireAuthority` behavior
  (`services/api/app/core/dependencies.py:86-95` — overrides log via
  `record_authority_override`, denials don't). Both the endpoint-level
  `_require_scoped` early short-circuit and the new service-layer
  `_require_scoped_authority` gate (R5 / §5.1) inherit this behavior —
  neither writes a denial row. This resolves audit Finding 6 (R9): the
  Focus 10 prompt asked about denial audit rows under the "SLICE-008
  precedent" framing, but the shipped SLICE-008 precedent
  (`RequireAuthority` + `record_authority_override`) only logs
  *overrides*, not plain denials. SLICE-014 therefore matches the
  shipped precedent. A future slice that wants symmetric denial
  logging can add a `record_authority_denial(db, *, actor, requirement,
  surface)` helper mirroring `record_authority_override` and call it
  from both gates; that work is explicitly out of scope here.

---

## Summary

- **Three linear migrations** (`wu-027 → wu-028a → wu-028b`) chained
  from the shipped head `wu_035_application_interview`; guards refuse
  unsafe legacy rows; downgrades are no-ops with Live-Server-Principle
  comments.
- **Permission drift widened in place** with scope/target locator,
  run anchor FK, and resolution metadata enforced by a split-shape
  CHECK constraint so terminal and non-terminal rows cannot drift.
- **New `permission_reconciliation_runs` table + algorithm** in
  `services/api/app/services/permission_reconciliation.py`, with
  single-transaction diff + drift materialization and terminal-replay
  idempotency keyed by path `run_id` to satisfy AC4.
- **Router subpackage `permissions/` (intents, drift, reconciliation)**
  with strong-ETag If-Match discipline, `PermissionDriftResolutionRequest`
  spoof-proof for user vs service actors, and a seeded
  `permission-reconciler` service actor (global scope) whose grant also
  satisfies chapter-scope authority checks via the shipped hierarchical
  evaluator.
- **Discord adapter** walks in-memory `guild.roles` and (chapter-scope
  only) `guild.channels[*].overwrites`, creates a run, POSTs the
  snapshot, and never writes drift state locally — conflicts and
  preconditions surface as ephemeral operator messages with the
  API-assigned `run_id` remaining the idempotency anchor.

---

## Revision log

Proposal Revision 1 addresses blocking findings from the risk gate
(`plans/risk/slice-014-audit.md` MEDIUM,
`plans/risk/slice-014-shortcut.md` MEDIUM). Scope risk
(`plans/risk/slice-014-scope.md`) is LOW and requires no change.

- **R1 (shortcut F1 HIGH — `permission_drift.acceptd` typo).** Added
  `DRIFT_RESOLUTION_ACTION_TYPE` and `DRIFT_RESOLUTION_CHANGE_TYPE`
  dispatch dicts in §10.1. Updated §5.2 `resolve_permission_drift` call
  site to read `action_type` / `change_type` from those dicts instead of
  building them via f-string. Added
  `test_resolve_drift_accept_emits_correct_change_type` to §8.2 WU-028A.
- **R2 (shortcut F2 MEDIUM — inline run-status literals).** Replaced
  the inline `existing.status == "reconciled"` / `"failed"` comparisons
  in §5.3 `submit_reconciliation_snapshot` with a single
  `if existing.status in RUN_TERMINAL_STATUSES:` membership check and
  an inner switch on the terminal kind.
- **R3 (shortcut F3 MEDIUM — inline run action/change strings).** Added
  `RUN_ACTION_TYPE` and `RUN_CHANGE_TYPE` dispatch dicts in §10.2.
  Routed §5.3 `create_reconciliation_run` and the three `_advance_run_*`
  helpers through those dicts. Updated §10.3 name inventory to match
  (`permission_reconciliation_run.created` replaces `.requested` as the
  create-transition change_type for verb-past symmetry with the other
  three).
- **R4 (shortcut F4 MEDIUM — drift-batch return shape).** Changed
  §4.2 `insert_permission_drift_batch` to return only the newly-inserted
  drift ids; conflict rows are silently dropped. Updated §5.3
  `submit_reconciliation_snapshot` to iterate only the filtered
  `new_drift_ids` through `_record_drift_created` (so
  `expected_version=0` can never fire against an existing aggregate
  head) and to read the run's final drift set via
  `list_drift_ids_by_run(run_id)` before the reconcile advance.
- **R5 (shortcut F5 MEDIUM — service-layer authority).** Added
  `_require_scoped_authority(permission, *, scope_kind, scope_id, actor,
  db)` helper in §5.1 (declared in `services/api/app/services/permissions.py`).
  Added authority-check calls BEFORE `mutate_entity` in each mutating or
  reading service function: `create_permission_intent`,
  `update_permission_intent`, `list_permission_intents` (§5.1);
  `list_permission_drift`, `resolve_permission_drift` (§5.2);
  `create_reconciliation_run`, `submit_reconciliation_snapshot` (§5.3).
  Endpoint-level `_require_scoped` (§6.2–§6.4) retained as an early-403
  short-circuit but is no longer the sole gate.
- **R6 (audit F1 MEDIUM — drift-create audit payload).** Added
  `DRIFT_CREATE_PAYLOAD_ALLOWLIST` in §10.2. Updated §5.3
  `_record_drift_created` helper so both `action_payload` and
  `StateChangeDraft.payload_json` populate explicitly from the drift
  row's scope/target/intent-anchor/mask fields. Added `drift_row` parameter
  threaded through `submit_reconciliation_snapshot` via the new
  `_drift_row_by_id` lookup.
- **R7 (audit F2 MEDIUM — run-advance audit payload).** Specified
  `action_payload`, `change_type` (via `RUN_CHANGE_TYPE`), and
  `payload_json` for each of `_advance_run_submit`,
  `_advance_run_reconciled`, `_advance_run_failed` in §5.3. Each
  projection now carries the full AFTER-state on `payload_json`
  (`status`, the transition's timestamp column, and the transition's
  distinctive field — `entry_count` / `drift_count` + `drift_ids` /
  `failure_reason`).
- **R8 (shortcut F6 + audit F3 LOW — quality-of-life).**
  (a) Added `model_validator(mode="after")` on
  `PermissionDriftResolutionRequest` in §3.3 enforcing
  `resolved_by_kind` / `resolved_by_id` both-or-neither.
  (b) Added `diff_json={"from": current.status, "to": next_status}` to
  the drift-resolve projection in §5.2 and
  `diff_json={"from": <prior>, "to": <next>}` to each run-advance
  projection in §5.3 for parity with the shipped applications
  precedent.
  (c) Refactored the terminal-replay return paths in §5.3
  `submit_reconciliation_snapshot` to compute `_read_head_version` once
  per path (shortcut F7).
- **R9 (audit F4 LOW — denial-audit clarification).** Added a
  "Denial-audit rows" non-goal bullet in §11 documenting that denied
  authority checks emit 403 without writing audit rows (matching shipped
  `RequireAuthority` — overrides log, denials don't). Both the endpoint
  `_require_scoped` gate and the new service-layer
  `_require_scoped_authority` gate inherit this behavior. Marked as the
  resolution of audit Finding 6.

Sections touched by revision id:

| Revision | Sections edited |
|----------|-----------------|
| R1       | §5.2, §8.2, §10.1 |
| R2       | §5.3 |
| R3       | §5.3, §10.2, §10.3 |
| R4       | §4.2, §5.3 |
| R5       | §5.1, §5.2, §5.3 |
| R6       | §5.3, §10.2 |
| R7       | §5.3 |
| R8       | §3.3, §5.2, §5.3 |
| R9       | §11 |

D1–D15 bindings are preserved. No migrations added, removed, or
reordered. §1 AC mapping is unchanged: R4/R5 refactor the service-layer
mechanics that back AC3 without altering the AC itself. The five
authority permission names declared in D11 and §9 are unchanged.
