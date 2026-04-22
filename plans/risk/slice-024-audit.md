# SLICE-024 Risk: Audit

## Summary

**Overall severity: LOW.** This is a re-audit of Revision 1 of the
proposal, which introduces R1–R5 to close the prior audit's HIGH/MEDIUM
findings. Every audit-trail concern (atomic transfer, serialized
predecessor lock, per-item correlation, payload allowlist, constants
dispatch, idempotent replay, 409-before-mutation ordering, read-only
plan, per-item partial-success auditing) now matches shipped precedent
(`services/api/app/services/permissions.py:574-639`, SLICE-020
`_expire_single_intent`). Three minor observations carry LOW severity
and are implementer-hygiene items, not gate blockers.

## Scope

Audit-trail integrity, correlation/causation linkage, `mutate_entity`
discipline (constants + `payload_allowlist`), atomic transaction
composition for linked mutations, and idempotent replay semantics.
Scope creep (→ scope risk) and shortcut introduction (→ shortcut risk)
are out of scope for this report.

Inputs:
- `.pipeline/proposal.md` (Revision 1, incorporating R1–R5).
- `.pipeline/synthesis.md` (D1–D15).
- `product-strategy/tickets/SLICE-024.md`.
- `AGENTS.md`.
- Shipped code in worktree (`services/api/app/services/authority.py`,
  `services/api/app/services/mutations.py`,
  `services/api/app/services/permissions.py`,
  `services/api/app/services/applications.py`,
  `services/api/app/services/tickets.py`,
  `services/api/app/repositories/mutations.py`).

## Status of prior findings

| Prior | Severity | Status | Revision that closes it |
|-------|----------|--------|--------------------------|
| F1 — transfer atomicity | HIGH → **LOW** | Resolved | R1 |
| F2 — concurrent-transfer race | HIGH → **LOW** | Resolved | R2 |
| F3 — proposal §5 contradicts synthesis D6 | MEDIUM → **LOW** | Resolved | R3 |
| F4 — `payload_allowlist` discipline | LOW | Unchanged | — |
| F5 — constants dispatch, no f-strings | LOW | Unchanged | — |
| F6 — service-layer authority gate | LOW | Unchanged | — |
| F7 — correlation-ID propagation | LOW | Unchanged | — |
| F8 — plan is read-only, no audit | LOW | Unchanged | — |
| F9 — revoked-predecessor 409 ordering | LOW | Unchanged | — |
| F10 — idempotent replay emits no audit | LOW | Unchanged | — |
| F11 — handoff already-owned emits no audit | LOW | Unchanged | — |
| F12 — `predecessor_grant_id` persisted | LOW | Unchanged | — |

Three new observations (A1–A3) from Revision 1 follow; all LOW.

## Findings

### F1 — LOW — Authority transfer atomicity (closed by R1)

**Claim.** Synthesis §D6 step 3 binds: "Within one transaction (shared
DB connection, shared audit context)." Revision 1 §5
(`transfer_authority_grant`) opens one `with db.transaction() as
connection:` block and threads `connection=connection` into both
`grant_authority(...)` and `revoke_authority(...)`.

**Evidence.**
- Proposal §5 pseudocode: `with db.transaction() as connection: …
  grant_authority(db=db, connection=connection, …) …
  revoke_authority(db=db, connection=connection, …)`.
- Transaction-notes paragraph: "Both mutations share the transfer
  service's `db.transaction()` connection via the extended `connection=`
  parameter. Neither opens an inner transaction when a shared connection
  is provided."
- Precedent: `services/api/app/services/permissions.py:589-629`
  (`_expire_single_intent`) opens `with db.transaction() as connection:`
  and passes `connection=connection` into `mutate_entity(...)` and
  `_create_expiry_drift(db, connection=connection, …)`. The Revision 1
  shape matches line-for-line.
- `services/api/app/services/mutations.py:70,192-196`: `mutate_entity`
  accepts `connection: Connection[Any] | None = None`; when provided,
  `_run_mutation(connection)` runs on the caller's connection without
  opening a fresh tx.
- Test coverage added: §8
  `test_transfer_rolls_back_successor_when_revoke_fails` asserts that a
  `revoke_authority` failure rolls back the successor insert and the
  `authority.grant` action row — the precise invariant R1 restores.

**Consequence.** Grant-successor and revoke-predecessor now commit
together or roll back together; the "successor exists, predecessor
un-revoked" fork is structurally impossible. AC3's "one causal chain"
is satisfied across the failure path, not only the happy path.

**Severity: LOW.** No implementation action required beyond following
the revised pseudocode.

### F2 — LOW — Concurrent-transfer race (closed by R2)

**Claim.** Revision 1 §5 adds an explicit lock on the predecessor head
before the idempotency check:

```
get_head_for_update(
    connection,
    aggregate_type="authority_grant",
    aggregate_id=str(grant_id),
)
existing_successor = find_successor_grant(connection, grant_id)
```

**Evidence.**
- `services/api/app/repositories/mutations.py:19-33`: `get_head_for_update`
  issues `SELECT … FROM aggregate_heads WHERE … FOR UPDATE`, taking an
  exclusive row-level lock on the predecessor's head entry.
- With the lock acquired before `find_successor_grant`, a concurrent
  transfer attempt against the same predecessor blocks on the lock,
  then (after commit of the first caller's revoke/successor) reads
  the now-present successor and either returns the idempotent replay
  (same `successor_id`) or raises `GrantAlreadyTransferredError`
  (different `successor_id`) — no orphan successor is created.
- Lock is re-acquired (no-op) inside `revoke_authority`'s
  `mutate_entity(...)` at `mutations.py:112-116`; re-entrancy inside
  the same transaction is safe.
- `grant_authority` locks a *different* aggregate (the new successor
  id), so it does not deadlock against the predecessor lock.
- Test coverage added: §8
  `test_transfer_serializes_concurrent_attempts_on_predecessor` asserts
  exactly one successor and a `GrantAlreadyTransferredError` on the
  losing caller.

**Consequence.** The different-successor race documented in the prior
audit (two callers inserting both `successor_A` and `successor_B` linked
to the same predecessor) is closed without a new DB constraint (D2
holds).

**Severity: LOW.** Matches the service-layer-lock strategy shipped
elsewhere in the codebase; no migration required.

### F3 — LOW — Proposal/synthesis coherence (closed by R3)

**Claim.** Revision 1 deletes the offending "each run their own
`db.transaction()` block internally" sentence and replaces it with a
paragraph describing the shared-connection pattern and the R1
signature extension.

**Evidence.** Proposal §5 transaction-notes paragraph now reads:
"`grant_authority` and `revoke_authority` are extended to accept an
optional `connection: Connection[Any] | None = None` kwarg (no shim —
edit signatures in place per AGENTS.md 'No Backwards Compatibility';
existing lifecycle callers continue to pass nothing and get today's
behavior). When `connection` is provided, the function uses that
connection directly instead of opening `with db.transaction()` /
`with db.connection()`…".

**Consequence.** Proposal no longer silently relaxes D6. Any apparent
need to violate a decision would now properly escalate to synthesis
revision (per AGENTS.md guardrail) rather than living as a contradiction
between phases.

**Severity: LOW.**

### F4 — LOW — `payload_allowlist` discipline

**Claim.** Focus item 1: every mutation via `mutate_entity` with
explicit `payload_allowlist`.

**Evidence.**
- Proposal §9 defines frozenset constants
  `APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST = frozenset({"new_owner_id"})`
  and `TICKET_REASSIGN_PAYLOAD_ALLOWLIST = frozenset({"new_owner_id"})`
  at module level.
- Proposal §6 wires them in: "Emit via `mutate_entity` with
  `action_type=APPLICATION_REASSIGN_ACTION_TYPE`,
  `change_type=APPLICATION_REASSIGN_CHANGE_TYPE`,
  `payload_allowlist=APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST`"
  (and tickets-side symmetric).
- `services/api/app/services/mutations.py:37-48` (`_redact_payload`)
  enforces the allowlist — any key outside the set is dropped from the
  persisted `request_json`. Empty or `None` allowlists redact to `{}`.

**Observation (unchanged from prior audit).** The existing
`authority.grant` / `authority.revoke` lifecycle passes
`payload_allowlist=None` (`authority.py:161,215`); the durable fields
(`predecessor_grant_id`, `revocation_reason`) live in
`StateChangeDraft.payload_json`, not the action `request_json`. Tests
must assert against state-change payloads, not action payloads, when
verifying these fields. Transfer inherits this pattern unchanged.

**Severity: LOW.**

### F5 — LOW — Constants dispatch for `action_type` / `change_type`

**Claim.** Focus item 2: no f-strings for action/change types.

**Evidence.**
- Proposal §9 defines all four new constants at module level with
  literal string values; tests also assert against the constants.
- `SUCCESSION_TRANSFER_REVOCATION_REASON = "succession_transfer"` is a
  module-level constant on `contracts/authority.py`; no f-string
  formation in the revoke call at proposal §5.
- Matches the dict-constant pattern in
  `services/api/app/services/permissions.py:43-62`
  (`INTENT_ACTION_TYPE["expire"]`) and the plain literal at
  `services/api/app/services/authority.py:159,213`.

**Severity: LOW.**

### F6 — LOW — Service-layer authority gate (SLICE-014 R5 precedent)

**Claim.** Focus item 7: every service function calls
`_require_scoped_authority` before mutations.

**Evidence.** Proposal §5 calls `_require_scoped_authority(...)` at the
top of `compute_succession_plan` (scope `chapter`),
`transfer_authority_grant` (scope of predecessor grant),
`leadership_handoff_applications.execute_handoff` and
`leadership_handoff_tickets.execute_handoff` (scope of grant), and
`read_leadership_context` (scope `global`). Each of these calls runs
*before* any `mutate_entity` emission.

Synthesis D4 binds the same shape. No endpoint-level
`RequireAuthority(...)` is introduced (matches the existing authority
surface per research §3 and the SLICE-014 R5 pattern of
service-layer-only gates).

**Severity: LOW.**

### F7 — LOW — Correlation-ID propagation for handoff batches

**Claim.** Focus item 5: AC3's causal chain — each handoff item
inherits `correlation_id` from the HTTP request via middleware.

**Evidence.**
- `services/api/app/services/mutations.py:74`,
  `mutations.py:131-132,157-158`: `mutate_entity` reads the ambient
  `AuditContextRead` via `get_current_audit_context()` (a contextvar
  set by `CorrelationMiddleware`) and attaches the resulting
  `correlation_id` / `causation_id` to every accepted / rejected
  action row.
- Proposal §5 (shortcut-O4 inheritance note): "the handoff service
  does **not** open a new audit context. The per-item
  `transition_application` / `transition_ticket` calls inherit the
  request's ambient `AuditContextRead`". This is the correct
  application of the shipped contextvar mechanism — no new
  infrastructure.
- Tests `test_handoff_shares_correlation_id_across_items` (both apps
  and tickets), `test_transfer_shares_correlation_id_across_actions`
  are listed in §8.

**Severity: LOW.**

### F8 — LOW — Succession plan is read-only

**Claim.** Focus item 4: audit context for the plan read.

**Evidence.** `compute_succession_plan` (proposal §5) issues only
SELECTs against `chapter_roles`, `roster_entries`, `authority_grants`,
`applications`, `tickets`. No `mutate_entity` call. No
`activity_actions` rows. The explicit
`test_plan_does_not_write_activity_actions` (§8) asserts this.

HTTP middleware still sets correlation context for logging / tracing
purposes, but no root audit shim is required on the read path.

**Severity: LOW.**

### F9 — LOW — Revoked-predecessor 409 before mutation

**Claim.** Focus item 9: revoked-grant transfer returns 409 **before**
creating a successor.

**Evidence.** Proposal §5 pseudocode orders the guards explicitly:

```
predecessor = _fetch_grant_row(conn, grant_id)          # 404 if None
if predecessor.revoked_at is not None: raise GrantAlreadyRevokedError  # 409
_require_scoped_authority(...)                          # 403
with db.transaction() as connection:
    get_head_for_update(...)                            # R2 serialization
    existing_successor = find_successor_grant(...)      # D3 idempotency
    # only now: grant_authority(...), revoke_authority(...)
```

No `mutate_entity` emission runs before the revoked / 404 / authority
checks. The check-then-act window between `_fetch_grant_row` and the
lock is closed by R2's `get_head_for_update` plus
`find_successor_grant` under lock (F2).

**Severity: LOW.**

### F10 — LOW — Idempotent replay emits no new audit rows

**Claim.** Focus item 10: transfer replay with the same successor
returns HTTP 200 with the existing grant and **no** new audit rows.

**Evidence.** Proposal §5:

```
existing_successor = find_successor_grant(connection, grant_id)
if existing_successor is not None:
    if existing_successor.grantee_id == request.successor_id:
        return AuthorityGrantRead.from_row(existing_successor)
    raise GrantAlreadyTransferredError(existing_successor.id)
```

The short-circuit is at the service layer, *before* any call to
`grant_authority` / `revoke_authority`. Because both mutation
primitives unconditionally audit through `mutate_entity`, the
short-circuit is how "no new audit on replay" is achieved — matching
SLICE-014's terminal-replay pattern.

Test `test_transfer_is_idempotent_for_same_successor` (§8) asserts
"no new audit actions appear" on replay.

**Severity: LOW.**

### F11 — LOW — Handoff already-owned emits no audit rows

**Claim.** Focus item 11: only actually-reassigned items emit audit
rows.

**Evidence.** Proposal §5 partitions items into `already_owned`
(`owner_id == successor_member_id`) and `to_transfer`
(`owner_id == predecessor_member_id`) before iterating. Only
`to_transfer` items reach `transition_application` /
`transition_ticket`. Already-owned items never invoke
`mutate_entity`; replay after a complete handoff produces a result
whose lists contain only `already_owned` entries and zero audit rows.

The R4 partial-success path correctly does *not* widen this: items
that raised `StaleMutationError` last time re-enter `to_transfer` on
replay (not `already_owned`), so their retry audit is emitted as a
normal per-item action — this is the intended behavior.

Tests `test_handoff_is_idempotent_on_replay` (apps and tickets) in §8
cover this.

**Severity: LOW.**

### F12 — LOW — `predecessor_grant_id` linkage persisted and audited

**Claim.** Focus item 8: `predecessor_grant_id` is written on transfer
and recorded in the state-change payload.

**Evidence.**
- `services/api/app/services/authority.py:103` — `grant_authority`
  accepts `predecessor_grant_id: UUID | None`.
- `services/api/app/services/authority.py:131` — row inserted into
  `authority_grants` includes `predecessor_grant_id`.
- `services/api/app/services/authority.py:143-145` — emitted
  `StateChangeDraft.payload_json` includes a stringified
  `predecessor_grant_id`.
- Proposal §5 passes `predecessor_grant_id=grant_id` through the
  `grant_authority(db=db, connection=connection, …)` call.

Test `test_transfer_creates_successor_linked_to_predecessor` (§8)
asserts `successor.predecessor_grant_id == predecessor.id`.

**Severity: LOW.** Durable spine of AC3 intact.

### A1 — LOW — `revoke_authority` inner read-back is under-specified

**Claim.** `services/api/app/services/authority.py:220` ends
`revoke_authority` with `read, _etag = get_authority_grant(db,
grant_id=grant_id)`. `get_authority_grant` opens its own
`with db.connection()` (authority.py:309). When revoke_authority runs
inside a shared transfer transaction, this read-back executes on a
*separate* connection and will see pre-revoke data (the transfer tx
has not committed yet). Revision 1 states that with `connection`
provided the function "uses that connection directly instead of
opening `with db.transaction()` / `with db.connection()`" but does not
spell out how the line-220 re-read is reshaped.

**Evidence.** No audit row is affected — the re-read is a SELECT and
does not call `mutate_entity`. In the transfer flow the returned
`AuthorityGrantRead` from `revoke_authority` is **discarded**
(`return successor`, not the revoke's return value), so stale data
never reaches a caller. But an implementer following the proposal
literally could either keep line 220 as-is (an extra connection and a
stale — but unused — read) or silently extend `get_authority_grant`'s
signature.

**Action.** Not a gate finding. Implementer-hygiene guidance: either
inline the read-back using the already-known `row` + `revoked_at`
values (no extra connection), or extend `get_authority_grant(...,
connection: Connection[Any] | None = None)` and thread the shared
connection through. Preferred: inline, since the return value is
discarded by the transfer caller anyway.

**Severity: LOW.**

### A2 — LOW — Pseudocode error names do not match shipped types

**Claim.** Proposal §5 handoff loop catches
`except InvalidTransitionError as err`. No symbol by that exact name
exists in the codebase.

**Evidence.**
- `services/api/app/services/applications.py:399` raises
  `InvalidApplicationTransitionError`.
- `services/api/app/services/tickets.py:143` raises
  `InvalidTicketTransitionError` (and related
  `TicketTransition*ForbiddenError` variants).

**Action.** Implementer must substitute the correct types in each
handoff module:
`InvalidApplicationTransitionError` in
`leadership_handoff_applications.py`, and
`InvalidTicketTransitionError` (plus the
`TicketTransitionOwnerChangeForbiddenError` variant, since reassign
bypasses `category_state_machine` per D8 but other per-item guards
may still fire) in `leadership_handoff_tickets.py`.

No audit-correctness impact — the `mutate_entity` reject/fail paths
are unchanged regardless of which exception type the outer loop
catches; this is a naming correction only.

**Severity: LOW.**

### A3 — LOW — `get_head_for_update` return value discarded defensively

**Claim.** Proposal §5 calls
`get_head_for_update(connection, aggregate_type="authority_grant",
aggregate_id=str(grant_id))` and discards the return. The function's
shipped signature returns `AggregateHeadRow | None`
(`services/api/app/repositories/mutations.py:19-24`).

**Evidence.** If the predecessor's `aggregate_heads` row is somehow
absent at lock time, `get_head_for_update` returns `None` and the
transfer proceeds into `find_successor_grant` / `grant_authority` /
`revoke_authority`. In practice this cannot happen — the predecessor
row is populated by `mutate_entity` at the original `grant_authority`
call (`mutations.py:98-110` inserts the head with `ON CONFLICT DO
NOTHING`), and `_fetch_grant_row` has already succeeded. But an
explicit assertion makes the invariant unambiguous and surfaces
head-row corruption as a clear failure rather than a silent race.

**Action.** Not a gate finding. Implementer-hygiene: assert the return
is non-None, or rely on `revoke_authority`'s own
`MissingAggregateError` (`mutations.py:117-121`) to catch the same
condition later in the same tx. Either satisfies the audit concern.

**Severity: LOW.**

## Required Revisions Before Proceeding

**None.** All audit-gate blockers are closed by R1–R3. The three new
A-observations (A1–A3) are implementer-hygiene items and do not block
the risk gate.

## Not Audited (Out of Scope for This Report)

- Scope creep / D15 violations (→ `slice-024-scope.md`).
- Shortcut introductions: skipped authority checks, hard-coded action
  types, manual INSERT bypasses, etc. (→ `slice-024-shortcut.md`).
- Test coverage adequacy beyond the audit-specific assertions called
  out in the findings (covered by the test phase).
- Security / authorization boundary review beyond the D4 gate check
  (covered by the security-review workflow at PR stage).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
