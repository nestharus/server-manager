# SLICE-024 Shortcut Risk Assessment

**Rating: LOW.** All fifteen shortcut-focus items pass. The MEDIUM finding
from the pre-Revision-1 pass (F1 — `transfer_authority_grant` running
`grant_authority` and `revoke_authority` in two independent transactions)
is closed by `.pipeline/proposal.md` Revision 1 (R1 + R2 + R3): §5 now
opens one outer `with db.transaction() as connection:` in
`transfer_authority_grant`, threads `connection=connection` into both
`grant_authority` and `revoke_authority` (extending those two signatures
to accept `connection: Connection[Any] | None = None` per the AGENTS.md
"No Backwards Compatibility" rule), and takes a row lock on the
predecessor aggregate head via
`get_head_for_update(connection, aggregate_type="authority_grant",
aggregate_id=str(grant_id))` before the idempotency lookup. The shape
now matches the SLICE-020 R1 precedent
(`services/api/app/services/permissions.py:574-639`
`_expire_single_intent`). The three LOW observations from the prior pass
are also closed: O2 (silent `_is_uuid` filter) by R5's
`InvalidHolderIdError`, O3 (underspecified per-item error contract) by
R4's `HandoffFailureReason` / `ApplicationHandoffFailure` /
`TicketHandoffFailure` + HTTP-200-with-`failed`-list contract, and O4
(implicit ambient-audit-context use in handoff) by R4's explicit
"handoff does **not** open a new audit context" sentence in §5.

One non-blocking residual observation survives — a whitespace-only
`reason` / `successor_id` would satisfy Pydantic's `Field(min_length=1)`
but semantic non-blankness is only strip-checked for `reason` at the
service layer. LOW tidy-up; not gate-blocking.

---

## Scope

Reviewed `.pipeline/proposal.md` (1234 lines, Revision 1),
`.pipeline/synthesis.md` (D1–D15), `.pipeline/research.md` (§1–§9),
`product-strategy/tickets/SLICE-024.md` (AC1–AC4, WU-044A/044B/
045A-applications/045A-tickets/045B, Code Boundary), and `AGENTS.md`
(Live Server Principle, No Backwards Compatibility, Test/Code Agent
separation, migration discipline) against the fifteen shortcut-focus
items named by the orchestrator. Cross-verified against the shipped
`services/api/app/services/authority.py:95-221`
(`grant_authority` / `revoke_authority` transaction shape),
`services/api/app/services/mutations.py:58-196` (`mutate_entity`
`connection=` and `get_head_for_update` semantics),
`services/api/app/services/permissions.py:574-639` (SLICE-020 R1
shared-connection precedent), and
`services/api/app/repositories/mutations.py:46` (aggregate-head lock
helper).

Shortcut-specific scope: service-layer bypasses, cross-decision
"shortcut" regressions (proposal contradicting synthesis), atomicity
and replay semantics that could create unobservable state forks, and
missing explicit documentation of invariants that the contract depends
on.

---

## Findings

### F1 — Shared-connection transfer (Focus 3) — PASS (was MEDIUM, closed by R1)

**Focus item.** #3 "Shared connection for transfer create+revoke tx
(R1 precedent from SLICE-020)."

**Verdict.** PASS.

**References (post-R1).**
- `.pipeline/proposal.md:§5` lines 578-623 (`transfer_authority_grant`
  body):

  > `with db.transaction() as connection:`
  >     `get_head_for_update(connection, aggregate_type="authority_grant",`
  >         `aggregate_id=str(grant_id))`
  >     `existing_successor = find_successor_grant(connection, grant_id)`
  >     `…`
  >     `successor = grant_authority(db=db, connection=connection, …,`
  >         `predecessor_grant_id=grant_id, …)`
  >     `revoke_authority(db=db, connection=connection, grant_id=grant_id, …,`
  >         `reason=SUCCESSION_TRANSFER_REVOCATION_REASON, …)`

- `.pipeline/proposal.md:§5` lines 625-654 (transaction and concurrency
  notes, R1 + R2 + R3):

  > "`grant_authority` and `revoke_authority` are extended to accept an
  > optional `connection: Connection[Any] | None = None` kwarg (no shim
  > — edit signatures in place per AGENTS.md 'No Backwards Compatibility';
  > existing lifecycle callers continue to pass nothing and get today's
  > behavior). … Both mutations share the transfer service's
  > `db.transaction()` connection via the extended `connection=`
  > parameter. Neither opens an inner transaction when a shared
  > connection is provided, so the two `activity_actions` writes (and
  > the successor insert + predecessor revoke projection updates)
  > commit together or roll back together."

- `.pipeline/proposal.md:§11` Revision log R1 (line 1225): closes
  "audit F1 HIGH + shortcut F1 MEDIUM" by rewriting §5's transfer
  pseudocode around the shared `db.transaction() as connection` block
  and adding `test_transfer_rolls_back_successor_when_revoke_fails` to
  §8.

- `services/api/app/services/permissions.py:574-639`
  (`_expire_single_intent`, the SLICE-020 R1 precedent): single
  `with db.transaction() as connection:` block, `connection=connection`
  threaded into both `mutate_entity` calls. Proposal now mirrors this.

**Why the dual-active failure mode is closed.** The prior pass
documented a partial-failure sequence where tx 1 (`grant_authority`)
commits, tx 2 (`revoke_authority`) fails, and D3's idempotent-replay
branch returns HTTP 200 on retry without re-attempting revoke, leaving
the chapter with *both* predecessor and successor grants active
permanently. Under the Revision-1 shape, tx 1 and tx 2 are the same
transaction; either both commit (successor created AND predecessor
revoked) or both roll back (neither row changes). D3's replay branch
now only fires against a fully-applied transfer, which is the scenario
it was designed for. No path remains where replay short-circuits a
half-completed transfer.

**`grant_authority` / `revoke_authority` signature change is visible
and in scope.** Proposal §5 lines 626-637 are explicit that the two
public signatures grow `connection: Connection[Any] | None = None`.
The only other shipped callers are the existing
`create_authority_grant_endpoint` and `revoke_authority_grant_endpoint`
handlers in `endpoints/authority/lifecycle.py` (post-subpackage move);
both continue to pass no `connection`, hit the `None` branch, and get
today's behavior unchanged. This is AGENTS.md-clean: no compatibility
shim, no deprecation alias.

**Severity.** LOW (previously MEDIUM). Gate-blocking concern closed.

---

### F2 — Idempotency check order (Focus 4) — PASS

**Focus item.** #4 "Idempotency: `find_successor_grant(predecessor_grant_id)`
before create. Same successor → return existing; different → 409."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§1` lines 82-95 (AC2 block),
`.pipeline/proposal.md:§5` lines 578-623 (`transfer_authority_grant`
body), `.pipeline/proposal.md:§4` lines 429-431
(`find_successor_grant` repository helper not filtered by `revoked_at`
to keep chain intact), `.pipeline/synthesis.md:D3` lines 142-182.

The ordering under Revision 1 is:

1. `_fetch_grant_row(conn, grant_id)` — 404 if missing.
2. `predecessor.revoked_at is not None` → `GrantAlreadyRevokedError` (409).
3. `_require_scoped_authority(...)` — 403 if caller lacks
   `authority_grant.transfer`.
4. Open `with db.transaction() as connection:`.
5. `get_head_for_update(connection, aggregate_type="authority_grant",
   aggregate_id=str(grant_id))` — takes row-level `FOR UPDATE` on the
   predecessor aggregate head, serializing concurrent transfers.
6. `find_successor_grant(connection, grant_id)` — now under the lock.
7. If present and same successor: return existing (HTTP 200, no writes).
8. If present and different successor: raise
   `GrantAlreadyTransferredError` (HTTP 409).
9. Else: `grant_authority(..., connection=connection, ...)`.
10. `revoke_authority(..., connection=connection, ...)`.

Step 5's lock before step 6's lookup is the R2 closure that eliminates
the TOCTOU window for *different-successor* concurrent transfers (the
Observation O1 from the prior pass). Under R2, the second caller
blocks on the lock at step 5, then at step 6 sees the first caller's
successor and either returns the same-successor replay (step 7) or
raises `GrantAlreadyTransferredError` (step 8). Neither caller can
insert an orphan successor. `test_transfer_serializes_concurrent_attempts_on_predecessor`
(proposal §8 WU-044B line 1020-1022) covers this.

**Severity.** LOW. Idempotency contract is consistent with D3 and now
structurally race-free.

---

### F3 — Handoff idempotency via owner_id (Focus 5) — PASS

**Focus item.** #5 "Handoff idempotency via owner_id comparison
(successor == new_owner → skip)."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§5` lines 688-694:

```python
for app in apps:
    if str(app.owner_id) == request.successor_member_id:
        already_owned.append(app.id)
    elif str(app.owner_id) == predecessor_member_id:
        to_transfer.append(app)
```

Already-owned items never enter the `transition_application` call
loop. `.pipeline/synthesis.md:D7` lines 391-395 binds the partition.
`test_handoff_is_idempotent_on_replay` (proposal §8 WU-045A-applications
and WU-045A-tickets) verifies no-new-audit-rows on replay. Ticket path
mirrors identically.

**Severity.** LOW.

---

### F4 — All mutations via `mutate_entity` (Focus 1) — PASS

**Focus item.** #1 "All mutations via `mutate_entity` (no direct
INSERT/UPDATE on `authority_grants` / `applications` / `tickets`)."

**Verdict.** PASS.

**References.**
- `.pipeline/proposal.md:§4` last paragraph (line 481-483): "All
  repository helpers are single-query and SELECT-only. Mutations flow
  only through service-layer `mutate_entity` calls."
- `.pipeline/proposal.md:§Guardrails` line 1186-1187: "All mutations
  flow through `mutate_entity` with narrow payload allowlists; no
  direct INSERT/UPDATE on mutable aggregates."
- Every service-layer write in §5/§6 routes through either
  `grant_authority` / `revoke_authority` (which call `mutate_entity`),
  `transition_application(action="reassign", …)`, or
  `transition_ticket(action="reassign", …)`.
- `test_transfer_emits_grant_and_revoke_audit_actions` and
  `test_handoff_emits_reassign_action_per_item_with_constants`
  (proposal §8) assert audit-row emission through the lifecycle.

**Severity.** LOW.

---

### F5 — Transfer wraps create + revoke (Focus 2) — PASS

**Focus item.** #2 "Transfer wraps `create_authority_grant` +
`revoke_authority_grant` existing paths (AC2)."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§5` lines 602-623. Transfer
calls `grant_authority(db=db, connection=connection, grantee_id=...,
scope_kind=predecessor.scope_kind, scope_id=predecessor.scope_id,
permissions=predecessor.permissions, expires_at=predecessor.expires_at,
predecessor_grant_id=grant_id, actor=...)` and then
`revoke_authority(db=db, connection=connection, grant_id=grant_id,
actor=..., revoked_by=..., reason=SUCCESSION_TRANSFER_REVOCATION_REASON,
expected_version=expected_version)`. No shadow INSERT/UPDATE. Synthesis
D6 binds the reuse; R1 adds the shared-connection plumbing without
altering the reuse shape.

**Severity.** LOW.

---

### F6 — Constants-only action/change dispatch (Focus 6) — PASS

**Focus item.** #6 "Constants-only action/change dispatch."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§9` constants table lines
1109-1122 enumerates every action/change string as a module-level
constant: `SUCCESSION_TRANSFER_REVOCATION_REASON`,
`APPLICATION_REASSIGN_ACTION_TYPE`,
`APPLICATION_REASSIGN_CHANGE_TYPE`,
`APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST`,
`TICKET_REASSIGN_ACTION_TYPE`, `TICKET_REASSIGN_CHANGE_TYPE`,
`TICKET_REASSIGN_PAYLOAD_ALLOWLIST`. Proposal §6 lines 845-848 and
861-863 reference the constants by name for the `mutate_entity`
emissions. Tests assert against the constants, not hard-coded strings.
No f-strings or inline concatenation in emission paths.

**Severity.** LOW.

---

### F7 — Service-layer authority (Focus 7) — PASS

**Focus item.** #7 "Service-layer authority at top of each service
function."

**Verdict.** PASS.

**References.** All five new service functions call
`_require_scoped_authority(...)` as the first substantive step after
any load needed to determine scope:

- `compute_succession_plan` — line 500-506 (scope known from
  `chapter_id`; check is the literal first action).
- `transfer_authority_grant` — line 570-576 (check runs immediately
  after `_fetch_grant_row`, which is required to know the grant's
  scope; before the `db.transaction()` block and before any
  `mutate_entity` call).
- `leadership_handoff_applications.execute_handoff` — line 671-677
  (check runs immediately after `_fetch_grant_row`; before the
  per-item transition loop).
- `leadership_handoff_tickets.execute_handoff` — same pattern, §5
  tickets mirror.
- `read_leadership_context` — line 764-770 (check before any SELECT
  that returns member-scoped data; the function is global-scoped so
  no pre-load is required).

**Note (not a finding).** For `transfer_authority_grant` and the two
`execute_handoff` variants, the authority check necessarily runs *after*
`_fetch_grant_row` because the scope to gate on is the grant's own
`scope_kind` / `scope_id`. This is structurally identical to SLICE-014
`_record_drift_created` and SLICE-020 `renew_intent`: "load → authority →
mutate." The 404 (missing grant) surfaces before the 403 (no authority),
which is a minor information-disclosure shape shared by the rest of
the authority HTTP surface. Closing that is outside this slice.

**Severity.** LOW.

---

### F8 — Pydantic request validation (Focus 8) — PASS

**Focus item.** #8 "Pydantic request validation: non-blank reason,
non-blank successor_id."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§3` lines 253-256:

```python
class AuthorityGrantTransferRequest(BaseModel):
    successor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
```

Analogously `ApplicationHandoffRequest.successor_member_id: str =
Field(min_length=1)` (line 289) and `TicketHandoffRequest` (line 310).
Service-layer `NonBlankReasonRequiredError` (lines 337-339) runs
`request.reason.strip()` (§5 line 560-561) for service-to-service
callers that bypass the HTTP Pydantic layer.
`test_transfer_rejects_blank_reason` and
`test_transfer_rejects_blank_successor_id` (§8 WU-044B lines 1006-1007)
assert 422.

**Residual observation (LOW, non-blocking).** `Field(min_length=1)`
rejects `""` but accepts `"   "` (whitespace). The service-layer strip
check exists for `reason` but not for `successor_id` /
`successor_member_id`. This is a tidy-up item — under real use, the
Discord ID / member-UUID string won't be whitespace — but for uniform
semantics a `.strip()` check on the id fields in either the Pydantic
validator (preferred — `field_validator` on each field) or the service
layer would match the `reason` handling. Not a gate-blocker; noted for
implementation-time polish.

**Severity.** LOW.

---

### F9 — Reassign in `VALID_TRANSITIONS` (Focus 9) — PASS

**Focus item.** #9 "Reassign action added cleanly to
`VALID_TRANSITIONS` — no state change, owner mutation only.
`payload_allowlist` narrow."

**Verdict.** PASS.

**References.**
- Applications (§6 lines 835-837): "For each open state `s ∈ {submitted,
  queued, claimed, in_review, interview, waitlisted}`, add `('reassign',
  s) -> s` (no state change)." Payload allowlist =
  `APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST =
  frozenset({"new_owner_id"})` (§3 line 368, §9 line 1114).
- Tickets (§6 lines 856-863): "Route `reassign` around the
  category-state-machine edge check: … `from_state == to_state`."
  Payload allowlist = `TICKET_REASSIGN_PAYLOAD_ALLOWLIST =
  frozenset({"new_owner_id"})` (§3 line 380, §9 line 1117).

`.pipeline/synthesis.md:D12` binds. The reassign action's
source-equals-destination semantic ensures no edge validator is being
subverted; terminal-state rejection is handled by the `VALID_TRANSITIONS`
lookup itself on the application side, and by the `terminal_at IS NULL`
precondition on the ticket side.

**Severity.** LOW.

---

### F10 — Reassign preserves state (Focus 10) — PASS

**Focus item.** #10 "Application/ticket reassign preserves existing
state (the state machine doesn't 'move' the application just because
owner changed)."

**Verdict.** PASS.

**References.**
- Applications (§6 line 851-853): "The projection update sets
  `owner_id = new_owner_id` and leaves `state` unchanged; inserts one
  `application_reviews` row with `reviewer_id = actor.actor_id`,
  `action = 'reassign'`, `from_state == to_state`."
- Tickets (§6 lines 865-867): "Projection update sets
  `owner_id = new_owner_id`, leaves `state`, `category_id`, and
  `category_snapshot` unchanged, and writes a `ticket_transitions` row
  with `from_owner_id` = current, `to_owner_id` = new,
  `from_state == to_state`."

`test_handoff_writes_application_review_per_item` (§8
WU-045A-applications line 1041-1043) and
`test_handoff_writes_ticket_transition_per_item` (§8 WU-045A-tickets
line 1066-1069) both assert `from_state == to_state` explicitly.

**Severity.** LOW.

---

### F11 — Authorization uses grant scope (Focus 11) — PASS

**Focus item.** #11 "Authorization scope for handoff: uses the grant's
scope. Chapter-scoped grants → chapter authority check."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§5` lines 671-677:
`_require_scoped_authority("leadership_handoff.execute",
scope_kind=grant.scope_kind, scope_id=grant.scope_id, actor=actor,
db=db)`. Ticket path mirrors. Transfer uses the same pattern
(`scope_kind=predecessor.scope_kind, scope_id=predecessor.scope_id`,
line 571-572). Leadership context uses `scope_kind="global"`,
`scope_id=None` per D4 (§5 line 767-769) — correct because the view is
cross-chapter by nature. Succession plan uses `scope_kind="chapter",
scope_id=chapter_id` (§5 line 501-503). Every gate pulls the scope
from the authoritative source (grant row / path param), never from
request body.

Tests: `test_handoff_requires_leadership_handoff_execute_permission`
(apps line 1045-1046; tickets line 1071-1072),
`test_transfer_requires_authority_grant_transfer_permission` (line
1010-1011), `test_plan_requires_succession_plan_read_authority` (line
984-985), `test_context_requires_leadership_context_read_permission`
(line 1097-1098).

**Severity.** LOW.

---

### F12 — Leadership context is SELECT-only (Focus 12) — PASS

**Focus item.** #12 "Leadership context read is SELECT-only, no
writes."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§5` lines 758-815
(`read_leadership_context`) opens one `with db.connection() as conn:`
(not `db.transaction()`), executes only SELECT helpers
(`list_active_grants_for_member`, `fetch_predecessor_grants`,
`list_open_applications_for_owners_in_scope`,
`list_open_tickets_for_owners_in_scope`, `_compute_stale_handoff`,
`load_cursor`, `_compute_projector_lag`), then builds the
`LeadershipContextRead` shape. No `mutate_entity` call in the path;
no `activity_actions` row emitted. Same SELECT-only shape for
`compute_succession_plan` (§5 lines 494-549) per
`.pipeline/synthesis.md:D5` ("Pure read; no `mutate_entity` call; no
state writes").
`test_plan_does_not_write_activity_actions` (§8 WU-044A line 982-983)
asserts `activity_actions` row-count is unchanged after a plan read.
No analogous test is called out for leadership context, but the path
is structurally identical and covered by the SELECT-only helpers
(not gate-blocking — implementation can mirror the plan test if
desired).

**Severity.** LOW.

---

### F13 — Predecessor-chain traversal is bounded (Focus 13) — PASS

**Focus item.** #13 "Predecessor-chain traversal is bounded (max depth
or iterative) — no infinite loop risk."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§4` line 443-444
(`fetch_predecessor_grants`): "returns a mapping `successor_grant_id →
predecessor_row` by joining `authority_grants` to itself over
`predecessor_grant_id`. **One hop only (D10 non-goal).**"
`.pipeline/synthesis.md:D10` lines 640-642 and `.pipeline/proposal.md:§10`
item 11 (line 1149-1150) forbid multi-hop traversal. The SQL is a
single self-join, not a recursive CTE — there is no loop construct to
bound, and no termination condition to get wrong. Correct by
construction.

**Severity.** LOW.

---

### F14 — Correlation_id threading (Focus 14) — PASS

**Focus item.** #14 "Causal chain thread via middleware correlation_id
— document exactly how; no cross-request manual chaining."

**Verdict.** PASS.

**How it works (documented in the revised proposal).**

- `.pipeline/proposal.md:§5` lines 643-645 (transaction notes):
  "Audit actions `authority.grant` + `authority.revoke` still share
  the ambient `correlation_id` (D9) — correlation is orthogonal to
  atomicity, and both now hold."
- `.pipeline/proposal.md:§5` lines 739-745 (handoff audit context —
  O4 closure):

  > "Audit context (per shortcut O4): the handoff service does **not**
  > open a new audit context. The per-item `transition_application` /
  > `transition_ticket` calls inherit the request's ambient
  > `AuditContextRead` via `get_current_audit_context()` in
  > `mutate_entity` (`services/api/app/services/mutations.py:74`), so
  > every item in the batch emits an `activity_actions` row carrying
  > the same `correlation_id`."

- Mechanism confirmed in code: `services/api/app/services/mutations.py:74`
  reads `get_current_audit_context()` (a `contextvars.ContextVar` set
  by the request middleware in `services/api/app/core/context.py`).
  `mutations.py:131-132` and `mutations.py:157-158` inject the
  ambient context's `correlation_id` / `causation_id` into the
  inserted action row. Since the handoff service does not wrap its
  loop in a new `with audit_context(...)` block, every per-item
  `mutate_entity` sees the same request-level `correlation_id`.

**No cross-request manual chaining.** `.pipeline/synthesis.md:D9`
lines 537-584 and `.pipeline/proposal.md:§10` item 12 (line 1151-1152)
are explicit: operators reconstruct the cross-request chain via
`predecessor_grant_id` + per-request `correlation_id`, not via a
body-carried `succession_correlation_id`. No request/response schema
in §3 includes a chain id field. Tests:
`test_transfer_shares_correlation_id_across_actions` (§8 WU-044B line
997-998) and `test_handoff_shares_correlation_id_across_items` (§8
WU-045A-applications line 1044; WU-045A-tickets line 1070) verify the
mechanism.

**O4 closure.** The prior pass flagged that if implementation
accidentally used a per-item `with audit_context(...)` override (the
SLICE-014 reconciliation pattern), each item would get a fresh
correlation_id and the batch test would fail. Revision 1 added the
explicit "does **not** open a new audit context" sentence at §5 lines
739-745. The code agent now has an explicit directive; not an
implicit one.

**Severity.** LOW.

---

### F15 — Stale context from live projections (Focus 15) — PASS

**Focus item.** #15 "Stale context signal (AC4) —
predecessor-still-owned items computed from live projections."

**Verdict.** PASS.

**References.** `.pipeline/proposal.md:§5` lines 823-825:
`_compute_stale_handoff` "iterates each active grant that has a
predecessor, loads the predecessor's open applications and tickets
constrained to the inherited grant's `(scope_kind, scope_id)`, and
groups them by predecessor." Uses
`list_open_applications_for_owners_in_scope` and
`list_open_tickets_for_owners_in_scope` — the same repository helpers
fed by base-table SELECTs. `is_stale = bool(stale)` (line 812) and
`projector_is_stale = projector_lag > 0` (line 813) are separate
fields per D11. `.pipeline/synthesis.md:D10` / D11 bind the
"base tables are the projection state in this architecture"
interpretation; AC4's "reads from projection state" is satisfied by
the SLICE-017 operational-overview precedent, which this view
mirrors.

Tests: `test_context_reports_is_stale_true_when_predecessor_owns_open_work`
(§8 WU-045B line 1089-1091),
`test_context_reports_is_stale_false_after_full_handoff` (line
1090-1091), `test_context_reports_projector_is_stale_separately` (line
1093-1095).

**Severity.** LOW.

---

## Closed Observations (from prior pass)

### O1 (closed) — TOCTOU between `find_successor_grant` and `grant_authority`

The prior pass flagged that a concurrent different-successor transfer
could enter `find_successor_grant` between caller A's successor insert
and A's predecessor revoke. Under Revision 1, step 5
(`get_head_for_update` on the predecessor aggregate head) runs *before*
step 6 (`find_successor_grant`), so the second caller blocks on the
lock until A's transaction commits, then sees A's successor. No
concurrent-different-successor orphan can be inserted.
`test_transfer_serializes_concurrent_attempts_on_predecessor` (§8
WU-044B line 1020-1022) verifies.

### O2 (closed) — silent `_is_uuid` filter for `pending_applications`

The prior pass flagged that pre-R5 pseudocode used
`[UUID(h) for h in holder_ids if _is_uuid(h)]`, silently dropping
non-UUID holder ids. Revision 1 replaces this with an explicit
`try: [UUID(h) for h in holder_ids] except ValueError:
raise InvalidHolderIdError(...)` at §5 lines 513-521, and adds
`InvalidHolderIdError(ValueError)` to `contracts/authority.py` at §3
lines 340-349 with a comment that names the research §1.5 rationale.
`read_leadership_context` applies the same UUID-coercion guard at §5
lines 774-780 for `member_id`. §7 error-mapping table row for
`GET /chapters/{chapter_id}/succession-plan` and
`GET /members/{member_id}/leadership-context` calls out 422 on
non-UUID input (proposal §7 lines 925, 931, 948-950). No silent drop
remains.

### O3 (closed) — per-item handoff error contract

The prior pass flagged that §7 left two contract shapes on the table
for per-item failures ("whole-batch 409" vs "200 with `results`
list"). Revision 1 picks one shape and deletes the alternative. §3
now binds:

```python
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
```

§5 lines 688-730 wrap each `transition_application` /
`transition_ticket` call in try/except, capturing `StaleMutationError`
as `occ_conflict` and `InvalidTransitionError` as `invalid_state`
into the `failed` list. §7 "Per-item error model" (lines 933-946) is
rewritten: "handoff does not take an `If-Match` on the batch. Each
per-item … call runs without caller-supplied `expected_version` … —
**one bad item does not abort the batch**. The response is always
HTTP 200; partial success is surfaced by a non-empty `failed` list …
The caller retries the whole batch; already-transferred items fall
into `already_owned`, still-failing items re-enter `failed` (D7 —
idempotent rerun)." §7's status-code mapping table no longer has a
409 row for handoff endpoints. Tests
`test_handoff_partial_success_reports_failed_per_item` (apps line
1048-1053; tickets line 1073-1076) bind the single-shape contract.

### O4 (closed) — handoff audit-context origin

Closed in F14 above: §5 lines 739-745 now explicitly state "the
handoff service does **not** open a new audit context."

---

## Residual Observations (LOW, non-blocking)

### Obs R1 — whitespace-only `reason` / `successor_id` / `successor_member_id`

`Field(min_length=1)` accepts `"   "`. The service layer strip-checks
`reason` (§5 line 560-561) via `NonBlankReasonRequiredError` but does
not strip-check `successor_id` or `successor_member_id`. Under actual
use (Discord snowflake / member UUID string) the whitespace case
doesn't arise; the tidy-up is for symmetric semantics. Preferred fix:
add a `field_validator("successor_id")` on
`AuthorityGrantTransferRequest` (and symmetric on
`ApplicationHandoffRequest.successor_member_id` /
`TicketHandoffRequest.successor_member_id`) that raises on
`.strip() == ""`. Alternative: replicate the service-layer strip check.
Not a gate-blocker; implementation-phase decision.

---

## Non-findings (explicitly verified absent)

- ✅ No direct INSERT/UPDATE on `authority_grants`, `applications`,
  or `tickets` — every write routes through `mutate_entity` via the
  named service function (Focus 1; §4 repository note; §Guardrails
  line 1186-1187).
- ✅ Reassign is **not** exposed as a general-purpose endpoint outside
  the handoff flow — §6 last paragraph (lines 869-876) and §10 item 13
  (line 1153-1154). (Reassign *is* reachable through the existing
  generic transition endpoints by name; scope risk noted this and
  deferred the gating question as "out of scope for this slice.")
- ✅ No Alembic migration — `.pipeline/proposal.md:§2`,
  `.pipeline/synthesis.md:D2`, §10 item 7, "Migration chain" section.
  Migration head stays `wu_038`.
- ✅ No `succession_correlation_id` field, run-level causation UUID,
  or succession-run table — D9 binding, §10 item 12.
- ✅ Spoof-proof actor: derived from `Depends(get_current_actor)` and
  the ambient audit context; never from request body (§Guardrails
  lines 1196-1198).
- ✅ `reassign` is not called with caller-supplied `expected_version`
  — per-item OCC uses the current head (§5 line 712
  `expected_version=None`) consistent with the per-item idempotency
  model and the single-shape §7 error contract.
- ✅ `successor_designated` / `successor_member_id` on
  `SuccessionPlanRead` are always False / None this slice (§5 lines
  547-548; D5 non-goals; §10 item 5).
- ✅ No projection table for leadership context (D10, §10 item 6).
- ✅ Ticket handoff bypasses the category state-machine edge check
  intentionally (§6 lines 856-863; D8 binding implications), so
  chapters without an `allow_owner_change` edge on the current state
  are still serviceable by handoff. Test
  `test_handoff_bypasses_category_state_machine_edges` (§8
  WU-045A-tickets line 1058-1059) asserts.
- ✅ No Discord adapter call in any of the five new service functions
  (§10 item 8). No module under `services/discord/` is touched.
- ✅ No scheduled worker or succession-worker actor (§10 item 1;
  item 10; research §7).
- ✅ `is_stale` (domain) and `projector_is_stale` (cursor lag) are
  separate fields (D11; §3 lines 414-415; test line 1093-1095).
- ✅ Handoff is bounded to the grant's scope; cross-scope items
  untouched (D7/D8; §10 item 9).
- ✅ Payload allowlists are `frozenset({"new_owner_id"})` — narrow;
  any extra key trips `_redact_payload` in
  `services/api/app/services/mutations.py:37-48` (§3 lines 368, 380;
  §9 table).
- ✅ `transfer_authority_grant` write + revoke are atomic —
  `test_transfer_rolls_back_successor_when_revoke_fails` (§8 WU-044B
  line 1013-1016) verifies that `revoke_authority` failure rolls back
  the successor insert (no orphan grant, no orphan `authority.grant`
  action).
- ✅ `get_head_for_update` on the predecessor aggregate head runs
  *before* the idempotency lookup inside the shared tx — the R2
  invariant (§5 lines 583-588).

---

## Summary

| # | Focus item | Verdict |
|---|---|---|
| F1 | All mutations via `mutate_entity` | PASS |
| F2 | Transfer wraps existing create + revoke paths | PASS |
| F3 | Shared connection for transfer create + revoke (R1 precedent) | PASS (was MEDIUM; R1 closure) |
| F4 | `find_successor_grant` before create; same-successor replay / different-successor 409 | PASS |
| F5 | Handoff idempotency via `owner_id` comparison | PASS |
| F6 | Constants-only action/change dispatch | PASS |
| F7 | Service-layer authority at top of each service function | PASS |
| F8 | Pydantic request validation: non-blank `reason` / `successor_id` | PASS |
| F9 | Reassign added cleanly to `VALID_TRANSITIONS`; narrow payload allowlist | PASS |
| F10 | Reassign preserves existing state (owner-only mutation) | PASS |
| F11 | Authorization scope for handoff = grant's scope | PASS |
| F12 | Leadership-context read is SELECT-only | PASS |
| F13 | Predecessor-chain traversal is bounded (one hop) | PASS |
| F14 | Causal chain via middleware correlation_id; no cross-request manual chaining | PASS |
| F15 | Stale-context signal from live projections | PASS |
| Obs R1 | Whitespace-only `reason` / successor-id semantics (tidy-up) | LOW, non-blocking |

**Overall verdict: LOW.** All fifteen focus items pass under
`.pipeline/proposal.md` Revision 1. The pre-R1 MEDIUM finding (F1 —
two-tx transfer) is closed by the shared-connection pattern; the
three pre-R1 LOW observations (O1 different-successor race, O2
silent UUID filter, O3 underspecified per-item batch error contract)
and the one tracked note (O4 handoff audit-context origin) are all
closed in the revised §3/§5/§7/§8. One non-blocking residual
observation (whitespace-only `reason`/successor-id handling) is
recorded for implementation-time polish. The shortcut-risk gate is
clear for hookpoint research and implementation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
