# SLICE-024 Phase 3 Proposal: Leadership Succession + Context Transfer

## Binding sources

- `.pipeline/synthesis.md` — D1–D15 (binding).
- `.pipeline/research.md` — Phase 1 evidence.
- `product-strategy/tickets/SLICE-024.md` — AC1–AC4, WU grid, Code Boundary.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility, Test/Code Agent
  separation, migration discipline.

This proposal is bound to D1–D15. Mechanics may vary inside those boundaries;
scope and shape may not. No new Alembic file ships (D2). Migration head stays
`wu_038`.

---

## §1 — AC mapping

### AC1 — Queryable plan without successor; no automatic transfer

1. **Contracts**
   - `services/api/app/contracts/authority.py`:
     `SuccessionPlanRead`, `DepartingRoleEntry`, `PendingApplicationRef`,
     `PendingTicketRef` (shapes per §3).
2. **Repository helpers**
   (`services/api/app/repositories/authority.py`,
    `services/api/app/repositories/chapter_roles.py`,
    `services/api/app/repositories/roster.py`,
    `services/api/app/repositories/applications.py`,
    `services/api/app/repositories/tickets.py`):
   - `list_succession_triggering_roles(conn, chapter_id)` — rows from
     `chapter_roles` with `triggers_succession = TRUE`, ordered by `ordinal`.
   - `list_role_holders(conn, chapter_id, role_ids)` — roster entries for
     the triggering roles, returning `(role_id, member_id, status)`.
   - `list_active_grants_for_members(conn, member_ids, *, scope_kind,
     scope_id)` — grants with `revoked_at IS NULL` and
     `(expires_at IS NULL OR expires_at > now)` narrowed to the chapter scope.
   - `list_open_applications_for_owners_in_scope(conn, owner_ids,
     *, scope_kind, scope_id)` — open state set
     `{submitted, queued, claimed, in_review, interview, waitlisted}`
     (operational-overview set — D5).
   - `list_open_tickets_for_owners_in_scope(conn, owner_ids,
     *, scope_kind, scope_id)` — `terminal_at IS NULL`.
3. **Service**
   (`services/api/app/services/authority.py`,
    new function `compute_succession_plan`):
   - Authority: `_require_scoped_authority("succession_plan.read",
     scope_kind="chapter", scope_id=chapter_id, actor=actor, db=db)` — D4.
   - Pure read; no `mutate_entity` call; no state writes.
   - `successor_designated=False`, `successor_member_id=None` (D5).
4. **Endpoint**
   (`services/api/app/api/v1/endpoints/authority/succession_plan.py`):
   `GET /api/v1/chapters/{chapter_id}/succession-plan → SuccessionPlanRead`.
5. **Test**
   (`services/api/tests/test_succession_plan.py`): AC1 is satisfied when the
   plan returns with `successor_designated=False` and lists departing roles,
   affected grants, and pending work with no writes occurring (assert no new
   `activity_actions` rows are emitted by the request).

### AC2 — Transfer creates successor linked to predecessor; reuses grant lifecycle

1. **Contracts**:
   - `AuthorityGrantTransferRequest(successor_id: str, reason: str)` — both
     `min_length=1`.
   - Response: existing `AuthorityGrantRead` (the new grant).
   - New errors: `GrantAlreadyTransferredError(ValueError)`,
     `NonBlankReasonRequiredError(ValueError)` (Pydantic handles the blank-reason
     422 via `Field(min_length=1)`; the explicit error class is reserved for
     service-level string-only paths and test symmetry).
   - Constant: `SUCCESSION_TRANSFER_REVOCATION_REASON = "succession_transfer"`.
2. **Repository**
   (`services/api/app/repositories/authority.py`):
   - `find_successor_grant(conn, predecessor_grant_id) -> AuthorityGrantRow | None`
     — the single row where `predecessor_grant_id = :grant_id`. The lookup is
     not filtered by `revoked_at` — if a successor was created and later
     revoked, D3 still treats the predecessor as "already transferred" so the
     chain stays intact.
3. **Service**
   (`services/api/app/services/authority.py`, new function
   `transfer_authority_grant`):
   - Authority: `_require_scoped_authority("authority_grant.transfer",
     scope_kind=grant.scope_kind, scope_id=grant.scope_id, actor=actor, db=db)`.
   - Load predecessor via `_fetch_grant_row`; 404 if missing; 409 if
     `revoked_at IS NOT NULL`; check `find_successor_grant` — if present and
     `grantee_id == successor_id`: return it as an idempotent replay (HTTP 200,
     no new writes); if present with a different `grantee_id`: raise
     `GrantAlreadyTransferredError(existing_grant_id=successor.id)`.
   - Call the existing `grant_authority(...)` (with
     `predecessor_grant_id=grant_id` and predecessor's `scope_kind`,
     `scope_id`, `permissions`, `expires_at`), then `revoke_authority(...)`
     on the predecessor with
     `reason=SUCCESSION_TRANSFER_REVOCATION_REASON` and the caller-supplied
     `expected_version`.
   - Audit actions `authority.grant` + `authority.revoke` share the ambient
     `correlation_id` (D9).
4. **Endpoint**
   (`services/api/app/api/v1/endpoints/authority/transfer.py`):
   `POST /api/v1/authority-grants/{grant_id}/transfer → AuthorityGrantRead`.
   HTTP mapping: 200 (idempotent replay), 201 (new successor), 404, 409
   (already-revoked / already-transferred / duplicate-guard), 412 (stale OCC),
   403 (authority gate), 422 (blank reason, empty successor_id).
5. **Test**
   (`services/api/tests/test_authority_transfer.py`): AC2 is satisfied when the
   successor's `predecessor_grant_id` equals the predecessor id, both audit
   actions are recorded, and no bypass path (direct INSERT/UPDATE on
   `authority_grants`) is used.

### AC3 — Idempotent handoff; causal chain linking transfer and handoffs

1. **Contracts**
   (`services/api/app/contracts/applications.py`,
    `services/api/app/contracts/tickets.py`,
    `services/api/app/contracts/authority.py`):
   - `ApplicationHandoffRequest(successor_member_id: str)` — `min_length=1`.
   - `ApplicationHandoffResult(grant_id, successor_member_id,
     application_ids_transferred, application_ids_already_owned)`.
   - `TicketHandoffRequest(successor_member_id: str)` and
     `TicketHandoffResult` mirroring.
   - `APPLICATION_REASSIGN_ACTION_TYPE = "application.reassign"`,
     `APPLICATION_REASSIGN_CHANGE_TYPE = "application.reassigned"`.
   - `TICKET_REASSIGN_ACTION_TYPE = "ticket.reassign"`,
     `TICKET_REASSIGN_CHANGE_TYPE = "ticket.reassigned"`.
2. **Lifecycle extensions**
   (`services/api/app/services/applications.py`,
    `services/api/app/services/tickets.py`):
   - Applications: register a new `reassign` action in the action registry.
     Add an entry to `VALID_TRANSITIONS` for each open state (D5) where the
     source state equals the destination state. The payload allowlist is
     `{"new_owner_id"}`; the service function writes the `owner_id` column and
     emits one `application_reviews` row per item with
     `reviewer_id=actor.actor_id`, `action="reassign"`,
     `from_state == to_state`. The branch for owner-only mutations lives
     beside the existing claim/reactivate owner mutations.
   - Tickets: register a new `reassign` action that bypasses
     `category_state_machine` edge validation. It updates `owner_id`, leaves
     `state` unchanged, and writes a `ticket_transitions` row with
     `from_owner_id`/`to_owner_id` populated and `from_state == to_state`.
     The payload allowlist is `{"new_owner_id"}`.
   - Both actions emit through `mutate_entity` with the constants above.
3. **Handoff services**
   (new modules per ticket Code Boundary):
   - `services/api/app/services/leadership_handoff_applications.py`:
     `execute_handoff(db, *, grant_id, successor_member_id, actor)`.
     Authority: `_require_scoped_authority("leadership_handoff.execute",
     scope_kind=grant.scope_kind, scope_id=grant.scope_id, ...)`. Loads
     grant, derives predecessor `= grant.grantee_id`, queries open
     applications owned by predecessor in grant's scope (D5 state set;
     scope via `form_snapshot.target_scope`), partitions
     `already_owned`/`to_transfer`, and invokes
     `transition_application(action="reassign",
     payload={"new_owner_id": successor_member_id}, ...)` per item. Returns
     `ApplicationHandoffResult`.
   - `services/api/app/services/leadership_handoff_tickets.py`: same pattern
     with `transition_ticket(action="reassign", ...)`, scope via
     `category_snapshot.routing_scope`, open predicate
     `terminal_at IS NULL`.
   - Idempotency: items already owned by `successor_member_id` are skipped;
     the item is reported in `*_already_owned`. Re-invoking the same call is
     therefore a no-op on previously transferred items (AC3).
4. **Endpoints**
   (`services/api/app/api/v1/endpoints/authority/handoff_applications.py`,
    `.../handoff_tickets.py`):
   - `POST /api/v1/authority-grants/{grant_id}/handoff/applications
     → ApplicationHandoffResult`.
   - `POST /api/v1/authority-grants/{grant_id}/handoff/tickets
     → TicketHandoffResult`.
   - Error mapping: 404 grant not found, 403 missing authority, 422 blank
     `successor_member_id`, 409 on per-item OCC collision (per-item sub-op,
     see §7 error model).
5. **Tests**
   (`services/api/tests/test_leadership_handoff_applications.py`,
    `services/api/tests/test_leadership_handoff_tickets.py`):
   AC3 is satisfied when a batch transfers the expected items, re-invocation
   yields only `already_owned` ids with no further writes, terminal-state and
   out-of-scope items are excluded, and the audit trail for the batch shares
   one `correlation_id` across all per-item reassign actions (D9).

### AC4 — Leadership context view with explicit domain stale-context signal

1. **Contracts**
   (`services/api/app/contracts/read_models.py`):
   - `InheritedFromEntry(predecessor_grant_id, predecessor_member_id,
     scope_kind, scope_id, revoked_at)`.
   - `StaleHandoffEntry(predecessor_grant_id, predecessor_member_id,
     pending_application_ids, pending_ticket_ids)`.
   - `LeadershipContextRead(member_id, active_grants, inherited_from,
     current_applications, current_tickets, stale_handoff, is_stale,
     projector_is_stale, generated_at)`.
2. **Repository**
   (`services/api/app/repositories/read_models.py` or reuse/D5/D7/D8):
   - `list_active_grants_for_member(conn, member_id)` — grants where
     `grantee_id = :member_id` and active predicate.
   - `fetch_predecessor_grants(conn, grant_ids)` — single-join fetch of the
     immediate predecessor for a set of grants (one hop only — D10 non-goal).
   - Reuse `list_open_applications_for_owners_in_scope` /
     `list_open_tickets_for_owners_in_scope` (narrow `owner_ids`/`scope` per
     inherited grant).
3. **Service**
   (`services/api/app/services/read_models.py`, new function
   `read_leadership_context`):
   - Authority: `_require_scoped_authority("leadership_context.read",
     scope_kind="global", scope_id=None, ...)` — D4.
   - Aggregate active grants for `member_id`. For each active grant with
     `predecessor_grant_id` set, join to fetch predecessor info and its
     still-open work within that scope. Populate `stale_handoff`.
   - `is_stale = len(stale_handoff) > 0` (domain staleness — D11).
   - `projector_is_stale` is reported from `read_model_cursors` lag for the
     `operational_overview` projector (the existing cursor), matching the
     SLICE-017 pattern.
4. **Endpoint**
   (`services/api/app/api/v1/endpoints/authority/leadership_context.py`):
   `GET /api/v1/members/{member_id}/leadership-context →
   LeadershipContextRead`.
5. **Test**
   (`services/api/tests/test_leadership_context.py`):
   AC4 is satisfied when the response is populated (never empty) even for
   members with no inherited authority, the `is_stale` flag flips True→False
   after a clean application+ticket handoff, and `inherited_from` reflects
   the immediate predecessor grant's holder and scope.

---

## §2 — Schema (no migration)

Per D2, SLICE-024 ships **zero** Alembic migrations. Confirmed preconditions:

- `authority_grants.predecessor_grant_id` is present since WU-004.
- `authority_grants.revoked_at`, `.revoked_by`, `.revocation_reason` are
  present since WU-014.
- `chapter_roles.triggers_succession` is present since WU-007B.
- `authority_grants.grantee_id` is `TEXT` and no registry table exists for
  permission names — new permission strings (`succession_plan.read`,
  `authority_grant.transfer`, `leadership_handoff.execute`,
  `leadership_context.read`) are opaque service-layer values and require no
  seeding (D4).

**No new columns, indexes, constraints, projection tables, or service-actor
seeds are introduced.** Migration head remains `wu_038`. Any PR introducing
an Alembic file for this slice fails review. If implementation finds a
forced need (e.g., a partial unique index on `predecessor_grant_id`),
escalate to synthesis revision rather than adding one silently (D2 non-goal).

---

## §3 — Contracts (exact shapes)

### `services/api/app/contracts/authority.py` additions

```python
SUCCESSION_TRANSFER_REVOCATION_REASON = "succession_transfer"


class AuthorityGrantTransferRequest(BaseModel):
    successor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class DepartingRoleEntry(BaseModel):
    role_id: str
    holder_member_id: str | None
    triggers_succession: bool
    departure_signal: Literal["active", "roster_removed"]


class PendingApplicationRef(BaseModel):
    application_id: str
    owner_id: str
    state: str


class PendingTicketRef(BaseModel):
    ticket_id: str
    owner_id: str
    state: str


class SuccessionPlanRead(BaseModel):
    chapter_id: str
    generated_at: datetime
    departing_roles: list[DepartingRoleEntry]
    affected_grants: list[AuthorityGrantRead]
    pending_applications: list[PendingApplicationRef]
    pending_tickets: list[PendingTicketRef]
    successor_designated: bool
    successor_member_id: str | None


class ApplicationHandoffRequest(BaseModel):
    successor_member_id: str = Field(min_length=1)


HandoffFailureReason = Literal["occ_conflict", "unauthorized", "invalid_state"]


class ApplicationHandoffFailure(BaseModel):
    item_id: UUID
    reason: HandoffFailureReason
    detail: str


class ApplicationHandoffResult(BaseModel):
    grant_id: UUID
    successor_member_id: str
    application_ids_transferred: list[UUID]
    application_ids_already_owned: list[UUID]
    failed: list[ApplicationHandoffFailure]


class TicketHandoffRequest(BaseModel):
    successor_member_id: str = Field(min_length=1)


class TicketHandoffFailure(BaseModel):
    item_id: str
    reason: HandoffFailureReason
    detail: str


class TicketHandoffResult(BaseModel):
    grant_id: UUID
    successor_member_id: str
    ticket_ids_transferred: list[str]
    ticket_ids_already_owned: list[str]
    failed: list[TicketHandoffFailure]


class GrantAlreadyTransferredError(ValueError):
    """Raised when a successor grant already exists for the predecessor."""

    def __init__(self, existing_grant_id: UUID) -> None:
        super().__init__(
            f"grant already transferred to existing successor {existing_grant_id}"
        )
        self.existing_grant_id = existing_grant_id


class NonBlankReasonRequiredError(ValueError):
    """Raised when service-layer callers pass an empty transfer reason."""


class InvalidHolderIdError(ValueError):
    """Raised when a roster holder id or member id is not a canonical UUID.

    Per R5: succession-plan and leadership-context reads fail loudly on
    non-UUID holder ids rather than silently filtering them out. Applications
    join on `applications.owner_id` (UUID) and succession cannot compute
    pending applications for a holder whose identifier cannot be coerced to
    the canonical type.
    """
```

Notes:
- `ApplicationHandoffResult.*_ids` are `UUID` (applications carry UUID ids);
  `TicketHandoffResult.*_ids` are `str` (tickets use TEXT ids per research §1).
- `PendingApplicationRef.owner_id` is the stringified UUID of the application
  owner (application.owner_id is UUID FK to members.id — research §1.5);
  callers compare it against `grant.grantee_id` (TEXT). Implementation uses
  `str(uuid)` in the refs so the plan view is comparable against the grant's
  TEXT holder id.
- `AuthorityGrantRead` is unchanged and reused as both the transfer response
  and the `affected_grants` element type.

### `services/api/app/contracts/applications.py` additions

```python
APPLICATION_REASSIGN_ACTION_TYPE = "application.reassign"
APPLICATION_REASSIGN_CHANGE_TYPE = "application.reassigned"
APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({"new_owner_id"})
```

The `reassign` action is added to the existing action enum / `VALID_TRANSITIONS`
registry for every open state (D5 set), with source state equal to destination
state. No state field is mutated; only `owner_id`.

### `services/api/app/contracts/tickets.py` additions

```python
TICKET_REASSIGN_ACTION_TYPE = "ticket.reassign"
TICKET_REASSIGN_CHANGE_TYPE = "ticket.reassigned"
TICKET_REASSIGN_PAYLOAD_ALLOWLIST: frozenset[str] = frozenset({"new_owner_id"})
```

The `reassign` action is valid when `terminal_at IS NULL`, orthogonal to the
category state machine (D8). Existing per-category `allow_owner_change` edges
are not consulted.

### `services/api/app/contracts/read_models.py` additions

```python
class InheritedFromEntry(BaseModel):
    predecessor_grant_id: UUID
    predecessor_member_id: str
    scope_kind: str
    scope_id: str | None
    revoked_at: datetime | None


class StaleHandoffEntry(BaseModel):
    predecessor_grant_id: UUID
    predecessor_member_id: str
    pending_application_ids: list[UUID]
    pending_ticket_ids: list[str]


class LeadershipContextRead(BaseModel):
    member_id: str
    generated_at: datetime
    active_grants: list[AuthorityGrantRead]
    inherited_from: list[InheritedFromEntry]
    current_applications: list[PendingApplicationRef]
    current_tickets: list[PendingTicketRef]
    stale_handoff: list[StaleHandoffEntry]
    is_stale: bool
    projector_is_stale: bool
```

`PendingApplicationRef`/`PendingTicketRef` are defined once in
`contracts/authority.py` and imported by `contracts/read_models.py` so both
views share the same ref shapes. (Implementation may alternatively move them
to a neutral module such as `contracts/_refs.py`; either approach satisfies
the contract — no duplication allowed.)

---

## §4 — Repository layer

### `services/api/app/repositories/authority.py`

- `find_successor_grant(conn, predecessor_grant_id: UUID) -> AuthorityGrantRow | None`
  — single-row lookup on `authority_grants WHERE predecessor_grant_id = :id`
  (ordering: `created_at ASC`, expect 0 or 1; return the first). Used for D3
  idempotency.
- `list_active_grants_for_members(conn, member_ids: Sequence[str], *,
  scope_kind: str | None = None, scope_id: str | None = None) ->
  list[AuthorityGrantRow]` — active predicate
  (`revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now)`),
  optional scope narrowing for the succession plan.
- `list_active_grants_for_member(conn, member_id: str) ->
  list[AuthorityGrantRow]` — convenience wrapper for the leadership-context
  view (D10).
- `fetch_predecessor_grants(conn, grant_ids: Sequence[UUID]) ->
  dict[UUID, AuthorityGrantRow]` — returns a mapping `successor_grant_id →
  predecessor_row` by joining `authority_grants` to itself over
  `predecessor_grant_id`. One hop only (D10 non-goal).

### `services/api/app/repositories/chapter_roles.py`

- `list_succession_triggering_roles(conn, chapter_id: str) ->
  list[ChapterRoleRow]` — `WHERE chapter_id = :chapter_id AND
  triggers_succession = TRUE ORDER BY ordinal`.

### `services/api/app/repositories/roster.py`

- `list_holders_for_roles(conn, chapter_id: str, role_ids: Sequence[str]) ->
  list[RosterEntryRow]` — current `roster_entries` for the role set, returning
  `(role_id, member_id, status)`. Departure signal per D1 is derived in the
  service layer from `status` (`removed` → `"roster_removed"`; otherwise
  `"active"`).

### `services/api/app/repositories/applications.py`

- `list_open_applications_for_owners_in_scope(conn, owner_ids:
  Sequence[UUID], *, scope_kind: str, scope_id: str | None) ->
  list[ApplicationRow]` — filters on `state IN (submitted, queued, claimed,
  in_review, interview, waitlisted)` (D5), and on
  `form_snapshot->>'target_scope_kind' = :scope_kind` AND
  `form_snapshot->>'target_scope_id' = :scope_id` (NULL-safe). If
  `scope_kind="global"`, the scope filter is skipped (all owners' open apps).
- The existing repository surface has no list-by-owner helper today
  (research §1.4), so this is net-new.

### `services/api/app/repositories/tickets.py`

- `list_open_tickets_for_owners_in_scope(conn, owner_ids: Sequence[str], *,
  scope_kind: str, scope_id: str | None) -> list[TicketRow]` —
  `WHERE terminal_at IS NULL AND owner_id = ANY(:owner_ids)` AND
  `category_snapshot->>'routing_scope_kind' = :scope_kind` AND
  `category_snapshot->>'routing_scope_id' = :scope_id` (NULL-safe). If
  `scope_kind="global"`, the scope filter is skipped.

All repository helpers are single-query and SELECT-only. Mutations flow only
through service-layer `mutate_entity` calls.

---

## §5 — Service layer

### `services/api/app/services/authority.py` (extended)

Add two public functions alongside the existing `grant_authority`,
`revoke_authority`, `list_authority_grants`, `get_authority_grant`.

```python
def compute_succession_plan(
    db: PostgresDatabase,
    *,
    chapter_id: str,
    actor: ActorIdentity,
) -> SuccessionPlanRead:
    _require_scoped_authority(
        "succession_plan.read",
        scope_kind="chapter",
        scope_id=chapter_id,
        actor=actor,
        db=db,
    )
    with db.connection() as conn:
        roles = list_succession_triggering_roles(conn, chapter_id)
        holders = list_holders_for_roles(conn, chapter_id, [r.id for r in roles])
        holder_ids = [h.member_id for h in holders if h.member_id is not None]
        # R5: do NOT silently filter non-UUID holder ids. `applications.owner_id`
        # is a UUID FK to `members.id` (research §1.5); roster holder ids are
        # expected to be canonical member UUIDs. A non-UUID holder id is a
        # data-integrity bug, not a normal case, and must surface as an error
        # rather than producing a misleading "no pending applications" plan.
        try:
            holder_uuids = [UUID(h) for h in holder_ids]
        except ValueError as err:
            raise InvalidHolderIdError(
                f"roster holder id is not a canonical member UUID: {err}"
            ) from err
        grants = list_active_grants_for_members(
            conn,
            holder_ids,
            scope_kind="chapter",
            scope_id=chapter_id,
        )
        apps = list_open_applications_for_owners_in_scope(
            conn,
            holder_uuids,
            scope_kind="chapter",
            scope_id=chapter_id,
        )
        tickets = list_open_tickets_for_owners_in_scope(
            conn,
            holder_ids,
            scope_kind="chapter",
            scope_id=chapter_id,
        )
    return SuccessionPlanRead(
        chapter_id=chapter_id,
        generated_at=current_time(),
        departing_roles=[_to_departing_role(r, holders) for r in roles],
        affected_grants=[AuthorityGrantRead.from_row(g) for g in grants],
        pending_applications=[PendingApplicationRef(...) for a in apps],
        pending_tickets=[PendingTicketRef(...) for t in tickets],
        successor_designated=False,
        successor_member_id=None,
    )


def transfer_authority_grant(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    request: AuthorityGrantTransferRequest,
    actor: ActorIdentity,
    expected_version: int | None = None,
) -> AuthorityGrantRead:
    if not request.reason.strip():
        raise NonBlankReasonRequiredError("reason must be non-blank")

    with db.connection() as conn:
        predecessor = _fetch_grant_row(conn, grant_id)
    if predecessor is None:
        raise LookupError(f"grant not found: {grant_id}")
    if predecessor.revoked_at is not None:
        raise GrantAlreadyRevokedError(grant_id)

    _require_scoped_authority(
        "authority_grant.transfer",
        scope_kind=predecessor.scope_kind,
        scope_id=predecessor.scope_id,
        actor=actor,
        db=db,
    )

    with db.transaction() as connection:
        # R2: lock the predecessor aggregate head BEFORE the idempotency
        # lookup. This serializes concurrent transfer attempts on the same
        # predecessor (including different-successor races) on the FOR UPDATE
        # row lock that `mutate_entity` itself uses for OCC. The helper is
        # the shipped `repositories/mutations.py:get_head_for_update`.
        get_head_for_update(
            connection,
            aggregate_type="authority_grant",
            aggregate_id=str(grant_id),
        )

        # Idempotency check now runs under the predecessor lock; a
        # concurrent transfer cannot slip past it.
        existing_successor = find_successor_grant(connection, grant_id)
        if existing_successor is not None:
            if existing_successor.grantee_id == request.successor_id:
                return AuthorityGrantRead.from_row(existing_successor)
            raise GrantAlreadyTransferredError(existing_successor.id)

        # R1: grant + revoke share ONE connection/transaction. Both commit
        # atomically or neither does — no dual-active state fork on partial
        # failure. Mirrors SLICE-020 `_expire_single_intent` at
        # `services/api/app/services/permissions.py:574-639`.
        successor = grant_authority(
            db=db,
            connection=connection,
            grantee_id=request.successor_id,
            scope_kind=predecessor.scope_kind,
            scope_id=predecessor.scope_id,
            permissions=predecessor.permissions,
            expires_at=predecessor.expires_at,
            predecessor_grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
        )
        revoke_authority(
            db=db,
            connection=connection,
            grant_id=grant_id,
            actor=(actor.actor_kind, actor.actor_id),
            revoked_by=actor.actor_id,
            reason=SUCCESSION_TRANSFER_REVOCATION_REASON,
            expected_version=expected_version,
        )
        return successor
```

Transaction and concurrency notes (R1 + R2 + R3):
- `grant_authority` and `revoke_authority` are extended to accept an
  optional `connection: Connection[Any] | None = None` kwarg (no shim —
  edit signatures in place per AGENTS.md "No Backwards Compatibility";
  existing lifecycle callers continue to pass nothing and get today's
  behavior). When `connection` is provided, the function uses that
  connection directly instead of opening `with db.transaction()` /
  `with db.connection()`, and threads `connection=connection` into its
  `mutate_entity(...)` call. When `connection` is `None`, behavior is
  unchanged. This mirrors the `mutate_entity(connection=...)` pattern
  shipped in `services/api/app/services/mutations.py:58-70,192-196` and
  the SLICE-020 R1 precedent at
  `services/api/app/services/permissions.py:574-639` (`_expire_single_intent`).
- Both mutations share the transfer service's `db.transaction()` connection
  via the extended `connection=` parameter. Neither opens an inner
  transaction when a shared connection is provided, so the two
  `activity_actions` writes (and the successor insert + predecessor revoke
  projection updates) commit together or roll back together. Audit actions
  `authority.grant` + `authority.revoke` still share the ambient
  `correlation_id` (D9) — correlation is orthogonal to atomicity, and both
  now hold.
- `get_head_for_update(connection, aggregate_type="authority_grant",
  aggregate_id=str(grant_id))` runs at the top of the transaction body,
  before `find_successor_grant`. The `FOR UPDATE` row lock on the
  predecessor's `aggregate_heads` entry closes the different-successor race
  documented in earlier drafts: a second concurrent transfer call blocks
  on the lock, then on commit sees the first caller's successor and either
  returns the idempotent replay (same `successor_id`) or raises
  `GrantAlreadyTransferredError` (different `successor_id`). No DB
  constraint is required (D2 still holds).

### `services/api/app/services/leadership_handoff_applications.py` (new module)

```python
def execute_handoff(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    request: ApplicationHandoffRequest,
    actor: ActorIdentity,
) -> ApplicationHandoffResult:
    with db.connection() as conn:
        grant = _fetch_grant_row(conn, grant_id)
    if grant is None:
        raise LookupError(...)

    _require_scoped_authority(
        "leadership_handoff.execute",
        scope_kind=grant.scope_kind,
        scope_id=grant.scope_id,
        actor=actor,
        db=db,
    )

    predecessor_member_id = grant.grantee_id
    with db.connection() as conn:
        apps = list_open_applications_for_owners_in_scope(
            conn,
            [UUID(predecessor_member_id), UUID(request.successor_member_id)],
            scope_kind=grant.scope_kind,
            scope_id=grant.scope_id,
        )

    already_owned: list[UUID] = []
    to_transfer: list[ApplicationRow] = []
    for app in apps:
        if str(app.owner_id) == request.successor_member_id:
            already_owned.append(app.id)
        elif str(app.owner_id) == predecessor_member_id:
            to_transfer.append(app)

    transferred: list[UUID] = []
    failed: list[ApplicationHandoffFailure] = []
    # R4: each item runs its own tx inside `transition_application`. A
    # per-item OCC conflict (or other per-item error) does NOT abort the
    # batch — we capture it in `failed` and continue. The response is always
    # HTTP 200; partial success is represented by a non-empty `failed` list.
    # Retries pick up just the still-failed items (already-transferred items
    # fall into `already_owned`, idempotent by D7).
    for app in to_transfer:
        try:
            transition_application(
                db=db,
                application_id=app.id,
                action="reassign",
                payload={"new_owner_id": request.successor_member_id},
                actor=(actor.actor_kind, actor.actor_id),
                expected_version=None,  # per-item OCC against the current head
            )
            transferred.append(app.id)
        except StaleMutationError as err:
            failed.append(ApplicationHandoffFailure(
                item_id=app.id, reason="occ_conflict", detail=str(err),
            ))
        except InvalidTransitionError as err:
            failed.append(ApplicationHandoffFailure(
                item_id=app.id, reason="invalid_state", detail=str(err),
            ))

    return ApplicationHandoffResult(
        grant_id=grant_id,
        successor_member_id=request.successor_member_id,
        application_ids_transferred=transferred,
        application_ids_already_owned=already_owned,
        failed=failed,
    )
```

Idempotency (D7): re-invoking the same call finds all items already owned by
`successor_member_id`; `to_transfer` is empty; no writes happen; the response
reports the existing ownership as `*_already_owned` with an empty `failed`
list. Items that failed on a prior call re-enter `to_transfer` on replay and
are retried.

Audit context (per shortcut O4): the handoff service does **not** open a new
audit context. The per-item `transition_application` / `transition_ticket`
calls inherit the request's ambient `AuditContextRead` via
`get_current_audit_context()` in `mutate_entity`
(`services/api/app/services/mutations.py:74`), so every item in the batch
emits an `activity_actions` row carrying the same `correlation_id`. This is
what `test_handoff_shares_correlation_id_across_items` asserts.

### `services/api/app/services/leadership_handoff_tickets.py` (new module)

Same shape as the applications handoff above, with `transition_ticket`
replacing `transition_application` and the ticket scope predicate
(`category_snapshot.routing_scope`). Per-item failures populate
`list[TicketHandoffFailure]` with `item_id: str` (tickets use TEXT ids per
research §1), same `HandoffFailureReason` literal union as applications.

### `services/api/app/services/read_models.py` (extended)

```python
def read_leadership_context(
    db: PostgresDatabase,
    *,
    member_id: str,
    actor: ActorIdentity,
) -> LeadershipContextRead:
    _require_scoped_authority(
        "leadership_context.read",
        scope_kind="global",
        scope_id=None,
        actor=actor,
        db=db,
    )
    # R5: reject non-UUID member ids at the query boundary (same rationale
    # as compute_succession_plan). The leadership-context view joins on
    # applications.owner_id (UUID); a non-UUID member id is a 422 from the
    # caller, not a silent empty response.
    try:
        member_uuid = UUID(member_id)
    except ValueError as err:
        raise InvalidHolderIdError(
            f"member id is not a canonical UUID: {err}"
        ) from err

    with db.connection() as conn:
        grants = list_active_grants_for_member(conn, member_id)
        predecessors = fetch_predecessor_grants(
            conn,
            [g.id for g in grants if g.predecessor_grant_id is not None],
        )
        apps = list_open_applications_for_owners_in_scope(
            conn,
            [member_uuid],
            scope_kind="global",
            scope_id=None,
        )
        tickets = list_open_tickets_for_owners_in_scope(
            conn,
            [member_id],
            scope_kind="global",
            scope_id=None,
        )
        stale = _compute_stale_handoff(conn, grants, predecessors)
        projector_cursor = load_cursor(conn, OPERATIONAL_OVERVIEW_PROJECTION_NAME)
        projector_lag = _compute_projector_lag(conn, projector_cursor)

    return LeadershipContextRead(
        member_id=member_id,
        generated_at=current_time(),
        active_grants=[AuthorityGrantRead.from_row(g) for g in grants],
        inherited_from=[_to_inherited(g, predecessors) for g in grants if g.predecessor_grant_id],
        current_applications=[PendingApplicationRef(...) for a in apps],
        current_tickets=[PendingTicketRef(...) for t in tickets],
        stale_handoff=stale,
        is_stale=bool(stale),
        projector_is_stale=projector_lag > 0,
    )
```

Scope note: `current_applications` and `current_tickets` are member-wide
("work the successor currently owns"), not narrowed to any grant scope — the
leadership-context view is cross-scope by D4. The
`list_*_for_owners_in_scope` helpers accept `scope_kind="global",
scope_id=None` and skip the scope filter in that case.

`_compute_stale_handoff` iterates each active grant that has a predecessor,
loads the predecessor's open applications and tickets constrained to the
inherited grant's `(scope_kind, scope_id)`, and groups them by predecessor.

---

## §6 — Lifecycle extensions for `reassign`

### `services/api/app/services/applications.py`

1. Add `"reassign"` to the application action registry (action enum / literal
   union).
2. Register `reassign` in `VALID_TRANSITIONS`:
   - For each open state `s ∈ {submitted, queued, claimed, in_review,
     interview, waitlisted}`, add `("reassign", s) -> s` (no state change).
3. In `transition_application`, when `action == "reassign"`:
   - Validate payload keys ⊆ `APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST`.
   - Validate `new_owner_id` parses as UUID.
   - Reject if the target application state is terminal
     (`approved`, `denied`, `withdrawn`) — the `VALID_TRANSITIONS` check
     already enforces this; the test asserts the invalid-transition error
     path.
   - Emit via `mutate_entity` with
     `action_type=APPLICATION_REASSIGN_ACTION_TYPE`,
     `change_type=APPLICATION_REASSIGN_CHANGE_TYPE`,
     `payload_allowlist=APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST`.
   - The projection update sets `owner_id = new_owner_id` and leaves `state`
     unchanged; inserts one `application_reviews` row with
     `reviewer_id = actor.actor_id`, `action = "reassign"`,
     `from_state == to_state`.

### `services/api/app/services/tickets.py`

1. Add `"reassign"` to the ticket action registry.
2. Route `reassign` around the category-state-machine edge check:
   - The normal path in `transition_ticket` calls `category_state_machine`
     to validate the edge. For `reassign`, bypass that lookup entirely; the
     only precondition is `terminal_at IS NULL`.
3. Emit via `mutate_entity` with `action_type=TICKET_REASSIGN_ACTION_TYPE`,
   `change_type=TICKET_REASSIGN_CHANGE_TYPE`,
   `payload_allowlist=TICKET_REASSIGN_PAYLOAD_ALLOWLIST`.
4. Projection update sets `owner_id = new_owner_id`, leaves `state`,
   `category_id`, and `category_snapshot` unchanged, and writes a
   `ticket_transitions` row with `from_owner_id` = current, `to_owner_id` =
   new, `from_state == to_state`.

Scope of the new action (D8 non-goal): `reassign` is called only from the
leadership-handoff service modules. The action is still reachable via the
general `POST /api/v1/applications/{id}/transition` and
`POST /api/v1/tickets/{id}/transition` endpoints if a caller names the
action explicitly; gating those broader endpoints on
`leadership_handoff.execute` authority is out of scope for this slice.
The handoff endpoints gate authority, and no other shipped caller invokes
`reassign` today.

---

## §7 — Endpoints

### Package layout

The ticket Code Boundary places new endpoints under
`services/api/app/api/v1/endpoints/authority/`. The existing
`endpoints/authority.py` module exists as a single file today. Python does
not permit both a module and a subpackage with the same name.

Decision: convert the existing module into a subpackage. The existing
create/list/revoke handlers move verbatim into
`endpoints/authority/lifecycle.py`; an `__init__.py` aggregator router
includes every sub-router. This is a mechanical move, not a rewrite
(synthesis D13 forbids rewriting the handlers themselves). Final structure:

```
services/api/app/api/v1/endpoints/authority/
├── __init__.py             # APIRouter that includes all sub-routers
├── _shared.py              # _parse_if_match, _error_body, _db helpers (moved from authority.py)
├── lifecycle.py            # existing create/list/revoke (moved, unchanged bodies)
├── succession_plan.py      # GET  /chapters/{chapter_id}/succession-plan
├── transfer.py             # POST /authority-grants/{grant_id}/transfer
├── handoff_applications.py # POST /authority-grants/{grant_id}/handoff/applications
├── handoff_tickets.py      # POST /authority-grants/{grant_id}/handoff/tickets
└── leadership_context.py   # GET  /members/{member_id}/leadership-context
```

`services/api/app/api/v1/router.py` keeps its existing
`router.include_router(authority.router, tags=["authority"])` line; the
subpackage `__init__.py` exposes `router` as today, preserving the
registration.

### Endpoint bodies

Each endpoint module follows the `endpoints/permissions/*` pattern:

1. Parse path/body via Pydantic.
2. Resolve `actor = Depends(get_current_actor)`.
3. Call the service function (the service runs the authority check).
4. Map known exceptions to HTTP codes.
5. Return the response model (adding `ETag` headers where the existing
   authority lifecycle does).

Status-code mapping (non-exhaustive):

| Path                                                             | 200 | 201 | 403        | 404        | 409                                                 | 412              | 422                       |
|------------------------------------------------------------------|-----|-----|------------|------------|-----------------------------------------------------|------------------|---------------------------|
| `GET /chapters/{chapter_id}/succession-plan`                     | Y   | -   | authority  | chapter n/a| -                                                   | -                | -                         |
| `POST /authority-grants/{grant_id}/transfer`                     | idempotent replay | new grant | authority | grant n/a | revoked / already_transferred / duplicate_guard | stale predecessor | blank reason / empty id   |
| `POST /authority-grants/{grant_id}/handoff/applications`         | Y (partial ok) | -   | authority  | grant n/a  | -                                                   | -                | blank successor_member_id / non-UUID |
| `POST /authority-grants/{grant_id}/handoff/tickets`              | Y (partial ok) | -   | authority  | grant n/a  | -                                                   | -                | blank successor_member_id |
| `GET /members/{member_id}/leadership-context`                    | Y   | -   | authority  | member n/a | -                                                   | -                | non-UUID member_id                   |

Per-item error model for handoff endpoints (R4 — bound contract, single
shape, no alternatives): handoff does not take an `If-Match` on the batch.
Each per-item `transition_application` / `transition_ticket` call runs
without caller-supplied `expected_version` (the service uses the current
head) inside its own transaction — **one bad item does not abort the
batch**. The response is always HTTP 200; partial success is surfaced by
a non-empty `failed` list on `ApplicationHandoffResult` /
`TicketHandoffResult` (see §3). Each `HandoffFailure` carries
`item_id`, `reason ∈ {"occ_conflict","unauthorized","invalid_state"}`,
and a free-form `detail`. The caller retries the whole batch; already-
transferred items fall into `already_owned`, still-failing items re-enter
`failed` (D7 — idempotent rerun). A 4xx / 5xx at the endpoint level is
reserved for top-of-batch conditions (403 authority, 404 grant, 422 blank
input) — never per-item conditions.

Succession-plan and leadership-context endpoints return 422 when a
supplied `chapter_id` / `member_id` parameter or a roster holder id fails
the UUID-canonical check (R5 `InvalidHolderIdError`).

The authority gate is the only cross-cutting dependency; no endpoint here
uses a FastAPI-level `RequireAuthority(...)` dependency (research §3
confirms the existing authority endpoints do not declare one). The services
call `_require_scoped_authority` internally per D4; HTTP-level tests still
exercise the 403 path through the endpoint.

---

## §8 — Tests (per-WU, per-AC docstrings)

Each test module carries AGENTS.md-compliant per-test AC docstrings. Tests
do not mock the database; all run against the real test session fixture
(D14).

### WU-044A — `services/api/tests/test_succession_plan.py`

- `test_plan_is_queryable_without_successor` — AC1: plan returns with
  `successor_designated=False`, `successor_member_id=None` even when no
  successor is chosen.
- `test_plan_lists_succession_triggering_roles` — AC1: only roles with
  `triggers_succession=TRUE` appear in `departing_roles`.
- `test_plan_marks_removed_holders_as_roster_removed` — AC1 / D1:
  `departure_signal == "roster_removed"` for holders whose roster entry is
  in terminal `removed` state; `"active"` otherwise.
- `test_plan_lists_active_grants_for_holders_in_chapter_scope` — AC1: only
  active grants within the chapter scope appear; revoked/expired excluded.
- `test_plan_lists_open_applications_in_scope` — AC1 / D5: open state set
  includes `interview`/`waitlisted`; terminal states excluded.
- `test_plan_lists_open_tickets_in_scope` — AC1: `terminal_at IS NULL`;
  out-of-scope tickets excluded.
- `test_plan_does_not_write_activity_actions` — AC1: plan generation
  creates no new `activity_actions` rows.
- `test_plan_requires_succession_plan_read_authority` — D4: 403 when caller
  lacks `succession_plan.read` at the chapter scope.

### WU-044B — `services/api/tests/test_authority_transfer.py`

- `test_transfer_creates_successor_linked_to_predecessor` — AC2: successor's
  `predecessor_grant_id == predecessor.id`.
- `test_transfer_revokes_predecessor_with_succession_reason` — AC2 / D12:
  predecessor `revoked_at` is set; `revocation_reason ==
  "succession_transfer"`.
- `test_transfer_emits_grant_and_revoke_audit_actions` — AC2: both
  `authority.grant` and `authority.revoke` actions are recorded through
  `mutate_entity` (reuses lifecycle, no bypass).
- `test_transfer_shares_correlation_id_across_actions` — AC3 / D9:
  `correlation_id` is equal on the two emitted actions.
- `test_transfer_is_idempotent_for_same_successor` — AC3 / D3: replay with
  the same `successor_id` returns the existing successor; no new audit
  actions appear.
- `test_transfer_rejects_replay_with_different_successor` — D3: 409
  `GrantAlreadyTransferredError`.
- `test_transfer_rejects_revoked_predecessor` — D6: 409
  `GrantAlreadyRevokedError`.
- `test_transfer_rejects_blank_reason` — D6: 422 for blank reason.
- `test_transfer_rejects_blank_successor_id` — D6: 422 for blank successor.
- `test_transfer_rejects_stale_predecessor_version` — D6 / OCC: 412 on
  mismatched `If-Match`.
- `test_transfer_requires_authority_grant_transfer_permission` — D4: 403
  without `authority_grant.transfer` at the grant's scope.
- `test_transfer_rolls_back_successor_when_revoke_fails` — R1: when
  `revoke_authority` raises (simulate via a monkeypatched stale head or
  injected exception), the whole transfer rolls back — no successor row
  exists in `authority_grants`, no `authority.grant` action row exists,
  predecessor remains unrevoked. A subsequent retry succeeds cleanly.
- `test_transfer_serializes_concurrent_attempts_on_predecessor` — R2: two
  threaded transfer calls against the same predecessor with different
  successor ids are serialized by the `get_head_for_update` lock; exactly
  one successor grant is created, and the second call raises
  `GrantAlreadyTransferredError` (409) rather than inserting an orphan
  successor.

### WU-045A-applications — `services/api/tests/test_leadership_handoff_applications.py`

- `test_handoff_transfers_pending_applications` — AC3: pending applications
  owned by predecessor within the grant scope are reassigned to successor.
- `test_handoff_is_idempotent_on_replay` — AC3 / D7: replay returns
  `already_owned` for everything; no new audit actions.
- `test_handoff_skips_terminal_applications` — D7: approved/denied/
  withdrawn applications remain owned by predecessor and are absent from
  both result lists.
- `test_handoff_respects_grant_scope` — D7: applications outside the
  grant's `(scope_kind, scope_id)` are untouched.
- `test_handoff_emits_reassign_action_per_item_with_constants` — D12:
  each transferred application emits an `activity_action` with
  `action_type == APPLICATION_REASSIGN_ACTION_TYPE`,
  `change_type == APPLICATION_REASSIGN_CHANGE_TYPE`.
- `test_handoff_writes_application_review_per_item` — D7: one
  `application_reviews` row per transfer with
  `action == "reassign"`, `from_state == to_state`,
  `reviewer_id == actor.actor_id`.
- `test_handoff_shares_correlation_id_across_items` — AC3 / D9: all
  per-item reassign actions in a batch share one `correlation_id`.
- `test_handoff_requires_leadership_handoff_execute_permission` — D4: 403
  without `leadership_handoff.execute` at grant scope.
- `test_handoff_rejects_blank_successor_member_id` — 422.
- `test_handoff_partial_success_reports_failed_per_item` — R4: when one
  item raises `StaleMutationError` (simulate a concurrent owner change),
  the batch returns HTTP 200 with that item in `failed`
  (`reason="occ_conflict"`) and the other items in `transferred`; a retry
  surfaces the retry's outcome correctly (either moves to `transferred` /
  `already_owned`, or re-enters `failed`).

### WU-045A-tickets — `services/api/tests/test_leadership_handoff_tickets.py`

- `test_handoff_transfers_pending_tickets` — AC3.
- `test_handoff_bypasses_category_state_machine_edges` — D8: the ticket's
  category lacks an `allow_owner_change` edge for its current state;
  reassign still succeeds.
- `test_handoff_is_idempotent_on_replay` — AC3.
- `test_handoff_skips_terminal_tickets` — D8: `terminal_at IS NOT NULL`
  tickets are excluded.
- `test_handoff_respects_grant_scope` — D8.
- `test_handoff_emits_reassign_action_per_item_with_constants` — D12:
  `TICKET_REASSIGN_ACTION_TYPE` / `TICKET_REASSIGN_CHANGE_TYPE`.
- `test_handoff_writes_ticket_transition_per_item` — D8: one
  `ticket_transitions` row per transfer with `from_owner_id` /
  `to_owner_id` populated, `from_state == to_state`.
- `test_handoff_shares_correlation_id_across_items` — AC3 / D9.
- `test_handoff_requires_leadership_handoff_execute_permission` — D4.
- `test_handoff_rejects_blank_successor_member_id` — 422.
- `test_handoff_partial_success_reports_failed_per_item` — R4: same shape
  as the applications case above; per-item `StaleMutationError` lands in
  `TicketHandoffResult.failed` with `reason="occ_conflict"` and the batch
  still returns HTTP 200.

### WU-045B — `services/api/tests/test_leadership_context.py`

- `test_context_reads_for_member_with_no_inheritance` — AC4: populated
  response with empty lists and `is_stale=False`, not an empty output.
- `test_context_returns_active_grants_for_member` — AC4: only non-revoked,
  non-expired grants.
- `test_context_populates_inherited_from_from_predecessor_chain` — AC4 /
  D10: `InheritedFromEntry` reflects the immediate predecessor grant
  (one hop).
- `test_context_reports_is_stale_true_when_predecessor_owns_open_work` —
  AC4 / D11: domain staleness flag reflects pending predecessor apps or
  tickets within the inherited scope.
- `test_context_reports_is_stale_false_after_full_handoff` — AC4 / D11:
  completing application + ticket handoff flips `is_stale` to False.
- `test_context_reports_projector_is_stale_separately` — D11:
  `projector_is_stale` tracks `read_model_cursors` lag and is independent
  of `is_stale`.
- `test_context_includes_current_applications_and_tickets` — AC4: open
  work currently owned by the member.
- `test_context_requires_leadership_context_read_permission` — D4: 403
  without `leadership_context.read` (global).

HTTP layer coverage: each endpoint has at least one HTTP-level test that
exercises the authority gate (403), the request validation (422), and the
happy path. Per-AC behavioural assertions use the service layer directly
where the HTTP surface would only add noise.

---

## §9 — Constants (module-level, no f-strings)

| Module                                   | Constant                                    | Value                     |
|------------------------------------------|---------------------------------------------|---------------------------|
| `contracts/authority.py`                 | `SUCCESSION_TRANSFER_REVOCATION_REASON`     | `"succession_transfer"`   |
| `contracts/applications.py`              | `APPLICATION_REASSIGN_ACTION_TYPE`          | `"application.reassign"`  |
| `contracts/applications.py`              | `APPLICATION_REASSIGN_CHANGE_TYPE`          | `"application.reassigned"`|
| `contracts/applications.py`              | `APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST`    | `frozenset({"new_owner_id"})` |
| `contracts/tickets.py`                   | `TICKET_REASSIGN_ACTION_TYPE`               | `"ticket.reassign"`       |
| `contracts/tickets.py`                   | `TICKET_REASSIGN_CHANGE_TYPE`               | `"ticket.reassigned"`     |
| `contracts/tickets.py`                   | `TICKET_REASSIGN_PAYLOAD_ALLOWLIST`         | `frozenset({"new_owner_id"})` |
| (implicit, names only — D4)              | `succession_plan.read`                      | authority permission      |
| (implicit, names only — D4)              | `authority_grant.transfer`                  | authority permission      |
| (implicit, names only — D4)              | `leadership_handoff.execute`                | authority permission      |
| (implicit, names only — D4)              | `leadership_context.read`                   | authority permission      |

All `mutate_entity` emissions reference these constants; tests assert
against the constants (not hard-coded strings). Authority permission names
are strings passed to `_require_scoped_authority`; they are not bound to a
Python constant per D4 (no registry module). Tests and services may
introduce local constants for convenience, but no cross-slice permission
registry is created.

---

## §10 — Out of scope (explicit — D15)

The following are explicitly deferred; any PR adding one is out-of-bounds
for this slice and must split into a follow-up slice:

1. Automatic succession triggering on role removal (roster hook, scheduled
   worker, Discord notification).
2. Multi-role atomic succession.
3. Multi-successor reassignment per handoff call.
4. Transfer rollback endpoint.
5. Persisted successor designation (`successor_designated` is always
   `False` this slice).
6. New projection tables for leadership context (D10; live query only).
7. Alembic migrations of any kind (D2).
8. Discord messages/embeds for succession events.
9. Cross-scope sweep — handoff is bounded to the grant's scope.
10. `succession-worker` or other dedicated service actor.
11. Multi-hop predecessor lineage in `InheritedFromEntry` (immediate hop
    only; deeper history reachable via audit trail).
12. Strict per-step `causation_id` chaining across HTTP requests (D9:
    `predecessor_grant_id` + per-request `correlation_id` is sufficient).
13. Exposing `reassign` as a general-purpose endpoint outside the handoff
    flow.

---

## §11 — PR decomposition

The synthesis identifies three clean seams:

- **PR A** — WU-044A + WU-044B. Contained within authority / chapter-roles /
  roster queries and the authority lifecycle. Includes the mechanical move
  of the existing `endpoints/authority.py` into the `authority/` subpackage
  (`lifecycle.py`) as a precondition; the move is additive with no
  behavioural change. New authority permissions: `succession_plan.read`,
  `authority_grant.transfer`.
- **PR B** — WU-045A-applications + WU-045A-tickets. Highest-risk PR;
  introduces new `reassign` actions in both subsystems. Kept atomic because
  both share the `leadership_handoff.execute` permission and the batch
  handoff pattern.
- **PR C** — WU-045B. Leadership context view; depends on handoff semantics
  being settled so the `stale_handoff` / `is_stale` signals are meaningful.
  New permission: `leadership_context.read`.

Final decomposition is subject to the multi-concern review gate; this
proposal does not mandate the split beyond the synthesis recommendation.
If the reviewer at the PR stage concludes the three PRs can ship as one,
that is acceptable; they should not be merged into more than three.

---

## Guardrails (binding across all WUs)

- D1–D15 are binding. Any apparent need to violate a decision escalates to
  synthesis revision rather than silent expansion.
- All mutations flow through `mutate_entity` with narrow payload
  allowlists; no direct INSERT/UPDATE on mutable aggregates.
- All `action_type` / `change_type` values are module-level constants
  (§9). No f-strings or inline concatenation when emitting audit events.
- Authority checks run at the service layer (via
  `_require_scoped_authority`) so tests can exercise them without HTTP;
  endpoints rely on the service-layer check rather than introducing an
  `endpoints/authority/`-specific FastAPI dependency (matches SLICE-017
  pattern).
- Originating actor is spoof-proof: derived from
  `Depends(get_current_actor)` and the ambient audit context; never from
  the request body.
- No Alembic migration (D2).
- No backwards-compatibility shims: if a test pattern needs updating for
  the new `reassign` action, update the test directly (AGENTS.md).
- Follow the Test Agent / Code Agent separation at implementation time:
  the test agent sees contracts only; the code agent sees contracts + tests.

## Migration chain

- Current head: `wu_038` (SLICE-020 temporary permission lifecycle).
- SLICE-024 does not advance the head (D2).
- If implementation discovers an unavoidable migration, revisit synthesis
  before adding it; the candidate name would be
  `wu_044_leadership_succession`.

---

## Revision log

### Revision 1 — risk-gate closures

Driven by `plans/risk/slice-024-audit.md` (HIGH) and
`plans/risk/slice-024-shortcut.md` (MEDIUM). Scope risk passed at LOW in
revision 0 and is untouched.

| Revision | Closes                                  | Sections touched |
|----------|-----------------------------------------|------------------|
| R1       | audit F1 HIGH + shortcut F1 MEDIUM      | §3 (no change — parameter is on the service function, not the contract), §5 (`transfer_authority_grant` pseudocode rewritten to share one `db.transaction() as connection`; `grant_authority` / `revoke_authority` signatures extended with `connection: Connection[Any] \| None = None`; transaction-notes paragraph replaced), §8 (added `test_transfer_rolls_back_successor_when_revoke_fails`). |
| R2       | audit F2 HIGH                           | §5 (added `get_head_for_update(connection, aggregate_type="authority_grant", aggregate_id=str(grant_id))` at top of transfer's tx body, before `find_successor_grant`), §8 (added `test_transfer_serializes_concurrent_attempts_on_predecessor`). |
| R3       | audit F3 MEDIUM                         | §5 (deleted the "each run their own `db.transaction()` block" sentence; replaced with shared-connection narrative). |
| R4       | shortcut O3 LOW + audit coverage        | §3 (added `HandoffFailureReason`, `ApplicationHandoffFailure`, `TicketHandoffFailure`; `ApplicationHandoffResult.failed` / `TicketHandoffResult.failed` now required), §5 (handoff loop wraps each `transition_application` / `transition_ticket` in try/except, appends to `failed` on per-item failure; added audit-context-origin note from shortcut O4), §7 (error-model paragraph rewritten to bind a single contract — HTTP 200 with `failed` list; 409 row removed from the handoff table), §8 (added `test_handoff_partial_success_reports_failed_per_item` for both applications and tickets). |
| R5       | shortcut O2 LOW                         | §3 (added `InvalidHolderIdError(ValueError)`), §5 (`compute_succession_plan` replaces `_is_uuid(h)` filter with `UUID(h)` per holder wrapped in try/except → `InvalidHolderIdError`; `read_leadership_context` validates `member_id` at the boundary), §7 (error-model paragraph notes 422 on non-UUID `chapter_id` / `member_id` / holder id). |

No other sections changed. D1–D15 are still binding; no new decisions are
introduced. Migration head remains `wu_038`.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
