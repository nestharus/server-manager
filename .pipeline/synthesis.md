# SLICE-024 Phase 2 Synthesis: Binding Decisions (Leadership Succession)

These decisions are binding for the SLICE-024 proposal, hookpoint research,
risk, test, and implementation phases. The proposal may choose mechanics
inside these boundaries, but it must not expand scope beyond the five
work units (WU-044A, WU-044B, WU-045A-applications, WU-045A-tickets,
WU-045B), reshape the existing `authority_grants`, `roster_entries`,
`applications`, or `tickets` aggregates, or introduce a parallel audit
namespace for succession/handoff.

## Inputs

- `.pipeline/research.md` — Phase 1 research report.
- `product-strategy/tickets/SLICE-024.md` — Acceptance Criteria (AC1–AC4),
  Work Units, Code Boundary.
- `AGENTS.md` — Live Server Principle, No Backwards Compatibility,
  migration discipline, Test/Code Agent separation.
- `product-strategy/proposal.md` — Governance → AuthorityGrant predecessor
  linkage; Sub-community Lifecycle → ChapterRole succession metadata.
- Existing code in worktree:
  - `services/api/app/contracts/authority.py`,
    `services/api/app/services/authority.py`,
    `services/api/app/repositories/authority.py` — grant/revoke lifecycle,
    `predecessor_grant_id` linkage, duplicate guard.
  - `services/api/app/contracts/applications.py`,
    `services/api/app/services/applications.py` — application ownership,
    `transition_application`, `claim`/`reactivate` owner changes.
  - `services/api/app/contracts/tickets.py`,
    `services/api/app/services/tickets.py` — ticket ownership,
    `transition_ticket`, category state-machine edge `allow_owner_change`.
  - `services/api/app/contracts/roster.py`,
    `services/api/app/services/roster.py`,
    `services/api/app/repositories/roster.py` — roster_entries as live
    holder state, roster_transitions as history, no explicit
    `departed_at` column.
  - `services/api/app/contracts/chapter_roles.py`,
    `services/api/app/services/chapter_roles.py` — `triggers_succession`
    flag already present on `chapter_roles`.
  - `services/api/app/services/mutations.py`,
    `services/api/app/contracts/mutations.py` — `mutate_entity` OCC +
    ambient audit context + `correlation_id` / `causation_id`
    propagation.
  - `services/api/app/services/read_models.py`,
    `services/api/app/repositories/read_models.py` — operational overview
    pattern (live base-table queries + cursor-based freshness).
  - `services/api/app/repositories/archive_queries.py` — precedent for
    cross-subsystem queries over authority + applications + tickets.
  - Migration head: `wu_038` (SLICE-020 temporary permission lifecycle).

## Acceptance Criteria Reference

- **AC1**: A succession-triggering departure produces a queryable plan even
  when no successor is designated, and no automatic authority transfer
  occurs without that designation.
  (`product-strategy/tickets/SLICE-024.md:59`.)
- **AC2**: Authority transfer creates a new grant linked to the predecessor
  and reuses the existing grant lifecycle path instead of bypassing audit.
  (`…:60`.)
- **AC3**: Application and ticket handoff executions are idempotent and
  write one causal chain linking departure, grant transfer, and each
  handoff action. (`…:61`.)
- **AC4**: The leadership-context view reads from projection state and
  surfaces missing handoff state as an explicit stale-context signal
  rather than empty output. (`…:62`.)

---

## D1 — Role holder departure model

**Decision.** SLICE-024 reads "departure" from the existing roster
substrate. Departure = `roster_entries.status` is a removed/terminal
state, OR the roster entry has been marked removed via
`roster_transitions` (to_status = `removed`). No new `departed_at`
column is added to `chapter_roles`, `roster_entries`, or
`authority_grants`. The succession plan does not require explicit
"departing" persisted state to be queryable.

**Rationale.** Research §1 (role holder tracking) and §6 (migration
needs) establish that live holder state lives on `roster_entries.role_id`
and history lives on `roster_transitions`; there is no `departed_at` or
departure-reason enum anywhere in the schema, and roster tests treat
`removed` as terminal (`services/api/tests/test_roster.py:484`). Adding
a departure column to `chapter_roles` would misplace it, since role
occupancy is on roster entries, not on the role definition table
(research §6). AC1 requires a plan that is queryable *before* any
successor/transfer, so the plan must compute over current signals, not
wait on new state.

**Binding implications.**
- Succession plan queries `roster_entries` for the current holder of
  each `triggers_succession` role; holders in terminal state are tagged
  `departure_signal = "roster_removed"`, holders with an active status
  are tagged `departure_signal = "active"` (the plan still lists them so
  operators can see what would be at risk).
- The plan surfaces the holder set regardless of departure status; AC1's
  "even when no successor is designated" is satisfied because the plan
  never requires a designation to be computed.
- No migration adds departure columns. The schema stays as-is.

**Non-goals.**
- Introducing `departed_at`, `departing`, or `removal_reason_enum`
  anywhere.
- Changing `roster_entries.status` values or adding new transitions.
- Automatic plan generation on roster removal (out of scope — see D15).

---

## D2 — No new schema migration

**Decision.** SLICE-024 ships no Alembic migration. The existing schema
already carries `authority_grants.predecessor_grant_id`,
`authority_grants.revoked_at`, `authority_grants.revoked_by`,
`authority_grants.revocation_reason`, and
`chapter_roles.triggers_succession`. No new columns, tables, indexes, or
service-actor rows are required for the five work units.

**Rationale.** Research §1 confirms `predecessor_grant_id` exists since
WU-004 (`migrations/versions/wu-004_authority_foundation.py:30`) and
`triggers_succession` exists since WU-007B
(`migrations/versions/wu-007b_chapter_roles_foundation.py:24`). Research
§6 explicitly flags that a `wu-044_chapter_roles_succession` migration
that only adds `triggers_succession` would be redundant. Authority
permission strings are opaque service-layer values with no registry
table, so new permission names (D4) do not require a migration.

**Binding implications.**
- Migration head remains `wu_038` after this slice lands.
- If implementation discovers a forced need for a constraint
  (e.g., unique successor-per-predecessor — see D3), escalate to
  synthesis before adding a migration; do not add one silently.
- Any PR that proposes a new Alembic file fails review.

**Non-goals.**
- Unique index on `authority_grants(predecessor_grant_id) WHERE predecessor_grant_id IS NOT NULL`.
- New successor-designation table.
- New projection tables for leadership context (see D10).
- New service-actor seed (transfer/handoff are operator-triggered;
  research §7).

---

## D3 — Authority transfer idempotency (service-layer)

**Decision.** Transfer idempotency is enforced at the service layer, not
the schema. Before creating a successor grant, the transfer service
queries `authority_grants WHERE predecessor_grant_id = :grant_id`.

- If a successor grant already exists and its `grantee_id` matches the
  request's `successor_id`: return that existing successor grant with
  HTTP 200 (idempotent replay), no new audit actions.
- If a successor grant already exists and its `grantee_id` differs from
  the request's `successor_id`: raise `GrantAlreadyTransferredError`,
  mapped to HTTP 409 Conflict.
- If no successor grant exists: proceed with the transfer flow (D6).

**Rationale.** Research §3 documents that the schema does not prevent
multiple successor rows for the same predecessor and that the current
revoke path is explicitly non-idempotent (second revoke → 409
`GrantAlreadyRevokedError`). AC3 requires handoff executions to be
idempotent and the transfer to write one causal chain; allowing the
successor chain to fork would violate that chain invariant. A
service-layer check keeps the guarantee without a new migration (D2).

**Binding implications.**
- New repository helper:
  `get_successor_grant(session, predecessor_id) -> AuthorityGrant | None`.
- New error type in `services/authority.py`:
  `GrantAlreadyTransferredError` (carries existing `successor_grant_id`
  for operator debuggability).
- HTTP mapping: `GrantAlreadyTransferredError -> 409`; same-successor
  replay returns 200 with the existing grant body (no new write, no
  new audit action).
- The check runs inside the same transaction as create+revoke (D6).

**Non-goals.**
- Enforcing the uniqueness at the schema level (the cleaner long-term
  answer is a partial unique index, but it is not required for this
  slice; see D2).
- Idempotency based on client-supplied idempotency keys.
- Preventing manual same-grantee re-grants through the existing
  `grant_authority` path (separate concern).

---

## D4 — Authority permissions (names only, no seeding)

**Decision.** SLICE-024 introduces four new authority permission strings,
used as service-layer and endpoint gates. They are not pre-seeded in any
migration; operators grant them at runtime via the existing
`grant_authority` flow.

- `authority_grant.transfer` — gates `POST /authority-grants/{id}/transfer`.
  Scope check matches the predecessor grant's own `(scope_kind, scope_id)`.
- `leadership_handoff.execute` — gates
  `POST /authority-grants/{id}/handoff/applications` and
  `POST /authority-grants/{id}/handoff/tickets`. Scope matches the grant.
- `leadership_context.read` — gates
  `GET /members/{member_id}/leadership-context`. Scope: `global` (the
  view is cross-chapter by nature).
- `succession_plan.read` — gates
  `GET /chapters/{chapter_id}/succession-plan`. Scope matches the
  chapter.

**Rationale.** Research §3 notes that existing authority HTTP endpoints
do not use `RequireAuthority(...)`; SLICE-024 endpoints are new and
operator-sensitive, so they must be gated from day one (AC2's "reuses
the existing grant lifecycle path instead of bypassing audit" implies
the same rigor for authority checks). Research §6/§7 confirm that
authority permission names are opaque strings — no registry table, no
migration needed. Operator-granted-at-runtime matches the existing
`roster.remove`, `chapters.write` pattern.

**Binding implications.**
- Each new endpoint wires `RequireAuthority("<permission>", scope=...)`
  via the existing dependency pattern; scope derivation comes from the
  path parameter (grant's scope for grant-scoped endpoints, chapter_id
  for the plan endpoint, global for leadership-context).
- Service-layer functions take an explicit `actor` and re-check the
  permission inside the service call so the test suite can exercise
  service-level authority without HTTP.
- No documentation-only "permission registry" module is created.

**Non-goals.**
- Pre-seeding default grants for these permissions in a migration.
- Inventing a permission hierarchy or wildcard semantics.
- Adding authority gates to *existing* authority endpoints (separate
  concern, explicitly flagged in research §3).

---

## D5 — Succession plan shape (computed on demand)

**Decision.** `GET /chapters/{chapter_id}/succession-plan` returns a
`SuccessionPlanRead` that is computed live from base tables on every
request. It is not stored. The contract:

```python
class DepartingRoleEntry(BaseModel):
    role_id: str
    holder_member_id: str | None      # None if role is currently vacant
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
    successor_designated: bool              # always False in this slice
    successor_member_id: str | None         # always None in this slice
```

Open application states for `pending_applications`:
`{submitted, queued, claimed, in_review, interview, waitlisted}` —
matches operational overview (`services/api/app/services/read_models.py:31`).
Open ticket predicate: `terminal_at IS NULL`.

**Rationale.** Research §2 enumerates every input needed and confirms
all of them are derivable from existing tables except successor
designation, which is explicitly deferred (research §2 "Not computable
from existing state alone" and the open question in §9). AC1
("queryable plan even when no successor is designated") is satisfied
because `successor_designated` / `successor_member_id` are present on
the contract but always false/null in this slice; the field exists so
the contract does not need to change when designation persistence
lands in a future slice. Research §5 and archive-plan precedent
(`services/api/app/repositories/archive_queries.py`) support live-query
computation without dedicated projection tables. The application-state
set matches operational overview rather than archive plan because
leadership handoff must move interview/waitlisted work too — those are
still operational commitments.

**Binding implications.**
- Repository gains `list_departing_role_holders(chapter_id)`,
  `list_active_grants_for_members(member_ids)`,
  `list_open_applications_for_owners(owner_ids, scope)`,
  `list_open_tickets_for_owners(owner_ids, scope)`. Each is single-query.
- Plan computation is read-only; no `mutate_entity` calls, no audit
  events, no state writes.
- `generated_at` is the request timestamp; the plan does not carry
  `is_stale` (staleness belongs to leadership-context — D11).
- Scope filter: `pending_applications` and `pending_tickets` are scoped
  to the chapter (via `form_snapshot.target_scope` /
  `category_snapshot.routing_scope`), not to every item ever owned by
  the holder across subsystems.

**Non-goals.**
- Persisting the plan or caching it.
- Designating a successor through this endpoint (it is a read).
- Including roles without `triggers_succession=TRUE`.
- Including applications/tickets outside the chapter's scope.

---

## D6 — Authority transfer semantics

**Decision.** `POST /authority-grants/{grant_id}/transfer` body:

```python
class AuthorityGrantTransferRequest(BaseModel):
    successor_id: str                # new grantee
    reason: str = Field(min_length=1)
```

Service flow (`transfer_authority_grant`):

1. Authority check: `authority_grant.transfer` at the predecessor grant's
   `(scope_kind, scope_id)` — D4.
2. Load predecessor grant via `fetch_grant(grant_id)` (existing helper).
   Reject with 404 if missing, 409 if already revoked (predecessor
   cannot be revoked before transfer), 409 per D3 if already transferred
   to a different successor.
3. Within one transaction (shared DB connection, shared audit context):
   a. Create successor via `grant_authority(...)` with
      `grantee_id=successor_id`, `scope_kind` / `scope_id` /
      `permissions` / `expires_at` copied from predecessor,
      `predecessor_grant_id=grant_id`.
   b. Revoke predecessor via `revoke_authority(...)` with
      `revocation_reason="succession_transfer"` (constant — see D12).
4. Return `AuthorityGrantRead` for the new successor grant (HTTP 201).
5. Replay with same `successor_id`: return existing successor grant
   (HTTP 200), no new writes (D3).

Both writes share the ambient `correlation_id` so the two audit actions
(`authority.grant` + `authority.revoke`) link together (D9).

**Rationale.** AC2 requires reuse of the existing grant lifecycle
("instead of bypassing audit"). Research §3 confirms `grant_authority`
and `revoke_authority` already route through `mutate_entity`, already
record their own audit actions, and already validate OCC. Wrapping them
satisfies AC2 without touching their internals. The duplicate guard in
`_require_no_active_duplicate`
(`services/api/app/repositories/authority.py:118`) remains active — if
the successor already has an identical active grant, the transfer fails
with `DuplicateGrantError` (409), which is correct: the operator must
revoke the duplicate first rather than fork authority. Research §3
specifies exactly this sequence.

**Binding implications.**
- New constant in `contracts/authority.py`:
  `SUCCESSION_TRANSFER_REVOCATION_REASON = "succession_transfer"`.
- No modification to `grant_authority` / `revoke_authority` internals.
- Endpoint returns `AuthorityGrantRead` (existing contract), not a new
  transfer-specific shape — the response *is* the new grant.
- Errors: 404 for missing predecessor, 409 for already-revoked, 409 for
  already-transferred-to-different-successor (per D3), 409 for
  duplicate-guard, 412 for stale version on predecessor.
- Version (`If-Match`) on predecessor is enforced via existing OCC on
  the revoke step; request header `If-Match` optional but, if provided,
  must match predecessor's current version.

**Non-goals.**
- Creating successor grants with *different* permissions/scope than the
  predecessor (that is a re-grant, not a transfer).
- Supporting partial permission transfer (subset of permissions to a
  successor).
- Reverting a completed transfer via this endpoint (see D15).
- Exposing an HTTP endpoint that lists all transfers (separate concern).

---

## D7 — Application handoff

**Decision.** `POST /authority-grants/{grant_id}/handoff/applications`
body:

```python
class ApplicationHandoffRequest(BaseModel):
    successor_member_id: str
```

Service flow (`leadership_handoff_applications.execute_handoff`):

1. Authority check: `leadership_handoff.execute` at the grant's scope.
2. Load grant; derive `predecessor_member_id = grant.grantee_id` and
   grant scope.
3. Query open applications owned by `predecessor_member_id` within the
   grant's scope (scope filter via `form_snapshot.target_scope`). Open
   state set per D5.
4. Partition: `already_owned = [app where owner_id == successor_member_id]`
   (no-op), `to_transfer = [app where owner_id == predecessor_member_id]`.
5. For each app in `to_transfer`, invoke
   `transition_application(action="reassign", new_owner_id=successor_member_id)`.
   The `reassign` action updates `owner_id` with no state change. Each
   write goes through `mutate_entity` with
   `action_type="application.reassign"` and
   `change_type="application.reassigned"`; one `application_reviews` row
   per item records the reassignment with `reviewer_id=actor`,
   `action="reassign"`, `from_state == to_state`.
6. Return:

```python
class ApplicationHandoffResult(BaseModel):
    grant_id: str
    successor_member_id: str
    application_ids_transferred: list[str]
    application_ids_already_owned: list[str]
```

The `reassign` action is added to `VALID_TRANSITIONS` with the open
state set (D5) as both source and destination; no state change. Payload
allowlist: `new_owner_id` only. Authority for the action is the
endpoint-level `leadership_handoff.execute`; the service does not
re-check per-item claim authority.

**Rationale.** Research §4 confirms no generic reassignment action
exists today; `reactivate` is limited to `waitlisted → claimed`, which
is too narrow for handoff. Adding a first-class `reassign` action keeps
the write inside the lifecycle (AC2's audit-not-bypassed discipline
applies by analogy here) and lets the audit trail record the ownership
change uniformly. AC3's idempotency requirement is satisfied by skipping
already-owned items — re-invoking the handoff is a no-op on
already-transferred items and replays the same outcome.

**Binding implications.**
- `services/api/app/services/applications.py`: add `"reassign"` to the
  action registry, register it in `VALID_TRANSITIONS` for every open
  state (both source and destination = same state), add a narrow payload
  allowlist, branch owner-update logic. `application.reassign` /
  `application.reassigned` added to the action-type / change-type
  constants (D12).
- New service module:
  `services/api/app/services/leadership_handoff_applications.py`,
  implementing
  `execute_handoff(grant_id, successor_member_id, actor, *, conn)`. It
  does not invent its own mutation primitive — it calls
  `transition_application` per item.
- Repository helper:
  `list_open_applications_for_owner_in_scope(owner_id, scope)` (shared
  with D5).
- Scope filter: only applications whose `form_snapshot.target_scope`
  matches the grant's scope are handed off. Applications outside scope
  are not touched (operator must handle them separately).
- Per-item errors are not fatal for the batch: each item runs in its own
  OCC sub-transaction; the batch never rolls back items already
  transferred. Per-item failures are surfaced in the response (exact
  contract field deferred to implementation but must include item id and
  reason).

**Non-goals.**
- Bulk reassignment to multiple successors.
- Changing application state during handoff (handoff preserves state).
- Handoff of terminal applications (`approved`, `denied`, `withdrawn`).
- A cross-scope sweep that hands off applications outside the grant's
  scope.

---

## D8 — Ticket handoff

**Decision.** `POST /authority-grants/{grant_id}/handoff/tickets` body:

```python
class TicketHandoffRequest(BaseModel):
    successor_member_id: str
```

Service flow (`leadership_handoff_tickets.execute_handoff`): same shape
as D7, substituting tickets for applications.

1. Authority check: `leadership_handoff.execute` at the grant's scope.
2. Derive predecessor = `grant.grantee_id`.
3. Query open tickets (`terminal_at IS NULL`) owned by predecessor
   within grant scope (scope via `category_snapshot.routing_scope`).
4. Partition already-owned vs to-transfer.
5. For each to-transfer ticket, issue a `reassign` action via
   `transition_ticket(action="reassign", new_owner_id=successor_member_id)`.
   The `reassign` action bypasses the normal category state-machine edge
   check for owner changes — it is a dedicated ownership action, not a
   state transition. It emits a `ticket_transitions` row with
   `from_owner_id` → `to_owner_id`, `from_state == to_state`.
   `action_type="ticket.reassign"`,
   `change_type="ticket.reassigned"` (D12).

Return:

```python
class TicketHandoffResult(BaseModel):
    grant_id: str
    successor_member_id: str
    ticket_ids_transferred: list[str]
    ticket_ids_already_owned: list[str]
```

**Rationale.** Research §4 documents that existing ticket owner changes
require a category state-machine edge with `allow_owner_change=True`,
which is not universally available. Leadership handoff cannot depend on
per-category configuration — the predecessor's work exists regardless
of whether an edge was configured. Introducing a dedicated `reassign`
action that is orthogonal to the state machine matches the
applications-side decision (D7) and keeps audit uniform
(`ticket_transitions` still records the change). AC3's idempotency is
handled the same way as D7.

**Binding implications.**
- `services/api/app/services/tickets.py`: add `reassign` as a
  first-class action that bypasses `category_state_machine` edge
  validation, updates `owner_id`, leaves `state` unchanged, and writes a
  `ticket_transitions` row. Constants `TICKET_REASSIGN_ACTION_TYPE` /
  `TICKET_REASSIGN_CHANGE_TYPE` (D12).
- New service module:
  `services/api/app/services/leadership_handoff_tickets.py` with
  `execute_handoff(...)`.
- Repository helper:
  `list_open_tickets_for_owner_in_scope(owner_id, scope)` (shared with
  D5).
- Scope filter via `category_snapshot.routing_scope`; tickets outside
  the grant scope are skipped.
- Error handling: same per-item semantics as D7.

**Non-goals.**
- Making the ticket `reassign` action available outside the handoff
  endpoint (it is service-layer only; no general-purpose reassign
  endpoint ships).
- Re-routing to a different category during handoff (category
  unchanged).
- Honoring `allow_owner_change` on category edges for handoff — handoff
  bypasses that guard deliberately.

---

## D9 — Causal chain (AC3)

**Decision.** The causal chain is expressed through (a) the shared
`correlation_id` propagated by the existing audit middleware within
each HTTP request, and (b) the durable `predecessor_grant_id` linkage
on `authority_grants`. SLICE-024 does not introduce a new
`succession_correlation_id` field, new audit columns, or a
succession-run table.

- Within a single HTTP request (e.g., transfer): the create-successor
  and revoke-predecessor `activity_actions` share `correlation_id` via
  the ambient audit context, forming the direct causal link between
  those two writes.
- Across the multi-endpoint flow (plan → transfer → handoff apps →
  handoff tickets): each HTTP request has its own correlation_id.
  Reconstruction of the full chain is done by following
  `predecessor_grant_id` through `authority_grants` and matching
  `grant_id` through the handoff audit actions.
- Per-handoff-item: each item's reassign mutation carries the request's
  correlation_id; all items in a single handoff batch share it.

**Rationale.** Research §4 "Causal chain reality check" explains that
`mutate_entity` does not return the inserted action ID and therefore
does not support strict per-step `causation_id` chaining ergonomically.
Research cites chapter archive
(`services/api/app/services/chapters.py:875`) as the closest precedent:
one run-level correlation/causation across many effects rather than
direct per-step parentage. AC3's causal-chain requirement is satisfied
by (a) the `predecessor_grant_id` FK linkage, which is the durable
spine of the chain, and (b) the shared correlation_id per request,
which links co-occurring writes. Introducing a new cross-request
chaining primitive would be net-new infrastructure beyond the slice's
scope.

**Binding implications.**
- No new contract fields for `succession_correlation_id` or similar
  tokens on any handoff/transfer request or response body.
- Tests for AC3 assert: (a) the transfer produces two audit actions with
  equal `correlation_id`; (b) the successor grant's
  `predecessor_grant_id` matches the predecessor; (c) each handoff
  batch's per-item audit actions share one `correlation_id`; (d)
  re-invoking handoff with the same successor yields the same audit
  action set for the items already transferred (idempotency).
- Operators reconstruct the cross-request chain via the audit trail
  query surface (existing capability).

**Non-goals.**
- A succession-run aggregate or run table.
- Extending `mutate_entity` to return action_id for fine-grained
  `causation_id` chaining.
- Cross-request correlation stitching through request bodies.

---

## D10 — Leadership context view (live query, not new projection)

**Decision.** `GET /members/{member_id}/leadership-context` is
implemented the same way as `read_operational_overview` (SLICE-017
pattern): live queries against base tables, plus a cursor-based
freshness layer for the read-model lag signal. No new projection tables
are introduced; AC4's "reads from projection state" is interpreted per
the existing SLICE-017 semantic — the base tables *are* the projection
state in this architecture, and freshness is reported via
`read_model_cursors` lag.

Data sources:

- `active_grants`:
  `authority_grants WHERE grantee_id = :member_id AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now)`.
- `inherited_from`: for each active grant whose
  `predecessor_grant_id IS NOT NULL`, join back to `authority_grants` to
  fetch the predecessor (its `grantee_id`, scope, revoked_at,
  revocation_reason).
- `current_applications`: applications owned by `:member_id` in the open
  state set (D5).
- `current_tickets`: tickets owned by `:member_id` with
  `terminal_at IS NULL`.
- `stale_handoff`: for each predecessor derived from `inherited_from`,
  list the predecessor's still-open applications and tickets within the
  inherited grant's scope (i.e., items the successor inherited authority
  for but where the predecessor still owns the work).
- `is_stale`: `len(stale_handoff) > 0`.

**Rationale.** Research §5 states that the current read-model substrate
is minimal and that there are no dedicated projection tables today.
`read_operational_overview`
(`services/api/app/services/read_models.py:128`) is the shipped
precedent. Research §5 explicitly offers this interpretation of AC4 and
recommends it as the tractable path. Creating projection tables would
be net-new infrastructure beyond the slice's scope (D2).

**Binding implications.**
- New service function `read_leadership_context(member_id)` in
  `services/api/app/services/read_models.py` (matches the ticket's Code
  Boundary).
- Repository helpers added to
  `services/api/app/repositories/read_models.py` or reused from
  D5/D7/D8 (`list_open_applications_for_owner`,
  `list_open_tickets_for_owner`, `list_active_grants_for_member`,
  `traverse_predecessor_grants`).
- Read-model cursor lag is reported alongside domain staleness but is
  *separate* from `is_stale` — see D11.
- Endpoint authority: `leadership_context.read` at global scope.

**Non-goals.**
- Creating projection tables for leadership context.
- Recomputing inheritance transitively across >1 predecessor hop (the
  view shows the immediate predecessor only; deeper history comes from
  the audit trail).
- A list endpoint returning leadership context for every member in a
  chapter.

---

## D11 — Stale context signal (domain staleness)

**Decision.** `LeadershipContextRead.is_stale` is a *domain* staleness
signal, not the same as SLICE-017's projector lag. Contract:

```python
class InheritedFromEntry(BaseModel):
    predecessor_grant_id: str
    predecessor_member_id: str
    scope_kind: str
    scope_id: str | None
    revoked_at: datetime | None

class StaleHandoffEntry(BaseModel):
    predecessor_grant_id: str
    predecessor_member_id: str
    pending_application_ids: list[str]
    pending_ticket_ids: list[str]

class LeadershipContextRead(BaseModel):
    member_id: str
    active_grants: list[AuthorityGrantRead]
    inherited_from: list[InheritedFromEntry]
    current_applications: list[ApplicationRef]
    current_tickets: list[TicketRef]
    stale_handoff: list[StaleHandoffEntry]
    is_stale: bool                         # len(stale_handoff) > 0
    projector_is_stale: bool               # SLICE-017 cursor lag, separate
    generated_at: datetime
```

`is_stale = True` ⇔ the successor inherited authority (via
`predecessor_grant_id`) for a scope where the predecessor still owns
open applications or open tickets. This is the explicit AC4 signal.

**Rationale.** Research §5 is explicit: SLICE-017's `is_stale` means
"the projector is behind"; SLICE-024's `is_stale` means "the successor
context is incomplete because predecessor-owned work still exists."
Conflating them would misrepresent what AC4 asks for ("explicit
stale-context signal rather than empty output"). Keeping both as
separate fields makes operator semantics unambiguous.

**Binding implications.**
- Two boolean fields on the contract: `is_stale` (domain) and
  `projector_is_stale` (cursor-lag). Both are emitted on every response.
- Empty context (no inherited grants, no current work) yields a
  populated response with empty lists and `is_stale = False` — AC4's
  "rather than empty output" is satisfied by always returning the
  structured view.
- A test asserts that cleared predecessor work flips `is_stale` from
  True to False after a full handoff.

**Non-goals.**
- Unifying `is_stale` with cursor lag.
- Persisting the stale-handoff list (it is derived).
- Alarming/paging on `is_stale = True` (out of scope).

---

## D12 — Constants, action/change types, transition registry

**Decision.** New module-level constants (no f-strings, no inline string
concatenation when emitting audit events):

In `contracts/authority.py`:
- `SUCCESSION_TRANSFER_REVOCATION_REASON = "succession_transfer"`

In `contracts/applications.py` / action-type table:
- Action: `"reassign"` (new entry in the open-state allowlist)
- `APPLICATION_REASSIGN_ACTION_TYPE = "application.reassign"`
- `APPLICATION_REASSIGN_CHANGE_TYPE = "application.reassigned"`
- Payload allowlist: `{"new_owner_id"}` only

In `contracts/tickets.py` / action-type table:
- Action: `"reassign"` (orthogonal to category state-machine edges)
- `TICKET_REASSIGN_ACTION_TYPE = "ticket.reassign"`
- `TICKET_REASSIGN_CHANGE_TYPE = "ticket.reassigned"`
- Payload allowlist: `{"new_owner_id"}` only

`VALID_TRANSITIONS` extensions:
- Applications: `reassign` is valid when source state ∈ open-state set
  (D5); destination state equals source state.
- Tickets: `reassign` is valid from any non-terminal state (terminal_at
  IS NULL); destination state equals source state.

**Rationale.** AGENTS.md forbids f-string action/change types. Reusing
the existing constants pattern keeps audit emission typesafe and
grep-stable. Research §4 establishes that both subsystems need new
transition actions.

**Binding implications.**
- All new audit emissions in SLICE-024 reference these constants; no
  ad-hoc strings.
- Tests assert exact action_type / change_type values against the
  constants (not hard-coded strings in tests either).
- `mutate_entity` payload allowlists are narrow; any additional fields
  trip the allowlist check and fail the test.

**Non-goals.**
- Adding generic "reassign" surface to other aggregates (e.g., roster,
  authority grants).
- Normalizing past actions that pre-date this slice.

---

## D13 — Endpoint layout

**Decision.** New endpoint modules under
`services/api/app/api/v1/endpoints/authority/`:

- `succession_plan.py` — GET `/chapters/{chapter_id}/succession-plan`
- `transfer.py` — POST `/authority-grants/{grant_id}/transfer`
- `handoff_applications.py` — POST `/authority-grants/{grant_id}/handoff/applications`
- `handoff_tickets.py` — POST `/authority-grants/{grant_id}/handoff/tickets`
- `leadership_context.py` — GET `/members/{member_id}/leadership-context`
- `__init__.py` — aggregator router that includes the above sub-routers

New service modules:

- `services/api/app/services/leadership_handoff_applications.py`
- `services/api/app/services/leadership_handoff_tickets.py`

Existing `services/api/app/services/authority.py` gains
`transfer_authority_grant(...)` and `compute_succession_plan(...)`
(the latter may live in a new helper module if `authority.py` becomes
too broad — implementation discretion within this slice).

`services/api/app/services/read_models.py` gains
`read_leadership_context(...)`.

Contract files updated per the ticket's Code Boundary:
- `contracts/authority.py` — `AuthorityGrantTransferRequest`,
  `SuccessionPlanRead`, `DepartingRoleEntry`, `PendingApplicationRef`,
  `PendingTicketRef`, `ApplicationHandoffRequest`,
  `ApplicationHandoffResult`, `TicketHandoffRequest`,
  `TicketHandoffResult`, plus constants (D12).
- `contracts/applications.py` — reassign action wiring + constants.
- `contracts/tickets.py` — reassign action wiring + constants.
- `contracts/read_models.py` — `LeadershipContextRead`,
  `InheritedFromEntry`, `StaleHandoffEntry`.

**Rationale.** Matches SLICE-014's split endpoint layout (per-concern
modules under a subdirectory with an aggregator router). Keeps each
WU's HTTP surface in a dedicated file for clean review and rollback.
Aligns with the ticket's Code Boundary paths.

**Binding implications.**
- Top-level `api/v1/endpoints/__init__.py` includes the `authority`
  aggregator router.
- Each endpoint module is short (≤ ~120 lines): request body parsing,
  authority guard, service call, response model.
- Service modules are the only place that invoke `mutate_entity` or
  touch repositories.

**Non-goals.**
- Rewriting the existing `endpoints/authority.py` module
  (create/list/revoke).
- Adding GraphQL, webhooks, or non-REST surfaces for succession.

---

## D14 — Test boundaries

**Decision.** Test boundaries follow the ticket's Code Boundary columns.
Each WU has exactly one test module:

- WU-044A → `services/api/tests/test_succession_plan.py`
- WU-044B → `services/api/tests/test_authority_transfer.py`
- WU-045A-applications → `services/api/tests/test_leadership_handoff_applications.py`
- WU-045A-tickets → `services/api/tests/test_leadership_handoff_tickets.py`
- WU-045B → `services/api/tests/test_leadership_context.py`

Each test carries a per-test AC docstring (per AGENTS.md Test Agent
requirements). The AC docstring cites AC1–AC4 or a specific D-decision
whenever the test is not a pure happy-path assertion.

Required coverage (not exhaustive):

- AC1: WU-044A test asserts plan is returned with
  `successor_designated=False` / `successor_member_id=None` when no
  designation exists; plan surfaces `triggers_succession` holders,
  affected grants, pending applications, pending tickets.
- AC2: WU-044B test asserts `grant_authority` + `revoke_authority` are
  both invoked (audit actions emitted, `predecessor_grant_id` linked,
  revocation_reason set).
- AC3 — transfer idempotency: replay with same successor returns
  existing grant and no new audit actions.
- AC3 — transfer 409: replay with different successor raises 409.
- AC3 — handoff idempotency (apps & tickets): re-invoking yields
  `already_owned` partition only.
- AC3 — causal chain: shared `correlation_id` across create-successor
  + revoke-predecessor within one transfer request.
- AC4: WU-045B test asserts `is_stale=True` when predecessor owns open
  work, `is_stale=False` once handoff clears it, populated empty
  response when member has no inherited authority.
- Authority gates (D4): each endpoint returns 403 when the caller
  lacks the required permission.
- Reassign action constraints (D7/D8): terminal applications/tickets
  are not reassigned; scope filter excludes out-of-scope items.

**Rationale.** Matches AGENTS.md Test Agent separation. Per-test AC
docstrings make review/regression triage trivial. Keeping one module
per WU respects the Code Boundary and simplifies the PR decomposition
question.

**Binding implications.**
- Tests use `mutate_entity`-level assertions (correlation_id,
  action_type constants from D12) where AC3 compliance is being
  verified.
- No mocking of the database; every test uses the real test session
  per repo convention.
- Tests exercise service-level authority and HTTP-level authority
  separately per endpoint.

**Non-goals.**
- Multi-WU omnibus test files.
- UI/E2E tests (no UI in this slice).

---

## D15 — Out of scope / deferred

**Decision.** The following are explicitly out of scope for SLICE-024
and will not be implemented in this slice, regardless of apparent
convenience during implementation:

1. **Automatic succession triggering.** The plan endpoint is pull-only;
   no scheduled worker, no event hook on roster removal, no Discord
   notification triggers a transfer or handoff automatically.
2. **Multi-role atomic succession.** Transfer and handoff operate on
   one grant / one successor per invocation. Chapters undergoing full
   leadership turnover make multiple calls.
3. **Bulk multi-successor reassignment.** Each handoff call has exactly
   one `successor_member_id`. Splitting pending work across multiple
   successors requires multiple calls (and thus multiple grants).
4. **Transfer rollback.** Once a transfer is recorded, reversing it
   requires separate operator action (re-grant + re-revoke); this slice
   ships no rollback endpoint.
5. **Successor designation persistence.** `successor_member_id` is never
   persisted in this slice — the plan always returns
   `successor_designated=False`. A future slice may add a designation
   table/field.
6. **New projection tables.** Leadership context is computed live
   (D10).
7. **Schema migrations.** No Alembic file ships (D2).
8. **Discord interactions.** No Discord message, embed, or interaction
   is emitted for succession events in this slice.
9. **Cross-scope handoff.** Handoff is bounded to the grant's scope;
   items outside scope are ignored, not escalated or reassigned.
10. **Succession-specific service actor.** Transfer/handoff are
    operator-triggered; no `succession-worker` actor is seeded
    (research §7).
11. **Deeper predecessor chain traversal in leadership-context.** The
    view shows the immediate predecessor only; multi-hop lineage is
    derivable from the audit trail on demand.
12. **Strict per-step `causation_id` chaining across HTTP requests.**
    Causal linkage relies on `predecessor_grant_id` + per-request
    correlation_id (D9).

**Rationale.** Each item was surfaced in research (§3, §4, §5, §6, §7)
or anticipated by AC1–AC4 without being required. Deferring them keeps
the slice shippable in one review cycle and avoids scope creep into
separate slices (notification, scheduling, multi-successor planning).

**Binding implications.**
- Any PR that adds one of the above is out-of-bounds for SLICE-024 and
  must be split into a follow-up slice.
- Implementation-phase discoveries that appear to require one of these
  items escalate to synthesis revision rather than silent expansion.

**Non-goals.** (Meta: this decision *is* the non-goal list.)

---

## PR decomposition

The five WUs naturally split into three PRs along subsystem seams:

- **PR A** — WU-044A + WU-044B (succession plan + authority transfer):
  contained within authority / chapter-roles / roster queries and the
  authority lifecycle.
- **PR B** — WU-045A-applications + WU-045A-tickets (handoff
  execution): the highest-risk PR; introduces new `reassign` actions
  to both subsystems. Kept together because they share the handoff
  service pattern and the `leadership_handoff.execute` permission.
- **PR C** — WU-045B (leadership context view): read-model extension
  that depends on the handoff semantics landing first for the stale
  signal to be meaningful.

Final decomposition is subject to multi-concern review at the PR stage;
synthesis does not mandate the split, only identifies the clean seams.

## Guardrails (binding for all WUs)

- Follow SLICE-014 + SLICE-017 endpoint and service patterns
  (per-concern endpoint modules, live-query read models).
- All mutations flow through `mutate_entity` with narrow payload
  allowlists; no direct INSERT/UPDATE on mutable aggregates.
- All `action_type` / `change_type` values are module-level constants;
  no f-strings, no inline concatenation.
- All new endpoints gate on the D4 authority permissions at both the
  HTTP layer and the service layer.
- Originating actor is spoof-proof: services derive originating actor
  from the ambient audit context, never from the request body.
- No Alembic migration (D2). Migration head stays `wu_038`.
- No backwards-compatibility shims: if a test pattern needs updating
  for the new `reassign` action, update the test directly.

## Migration chain

- Current head: `wu_038` (SLICE-020 temporary permission lifecycle).
- SLICE-024 does not advance the head.
- If implementation discovers an unavoidable migration (e.g., a
  constraint forced by D3), revisit synthesis before adding it; the
  candidate name would be `wu_044_leadership_succession`.
