# SLICE-018 Shortcut Risk Assessment

**Rating: LOW**

## Scope

Reviewed `worktrees/slice-018/.pipeline/proposal.md` against
`research.md`, `synthesis.md`, `AGENTS.md`
("No Backwards Compatibility" lines 564-576, "No Deferred Stubs"
lines 580-585, "Scope Hygiene"), and the merged SLICE-001..013
substrate (`services/api/app/services/mutations.py`,
`services/api/app/services/chapters.py`,
`services/api/app/services/roster.py`,
`services/api/app/repositories/roster.py`,
`services/api/app/repositories/deferred_effects.py`).

## Findings

### 1. Compatibility shims — clean
Proposal explicitly removes, not aliases, the WU-007C foundation's
public helpers:

- `services/api/app/services/roster.py`: rename/remove
  `read_roster_entry` and `transition_roster_status` "with no
  compatibility shim" (proposal §WU-033 Service, final paragraph).
- `services/api/app/repositories/roster.py`: underscore-prefixed
  helpers "replace the current public-only foundation helpers
  `insert_roster_entry`, `fetch_roster_entry`, and
  `update_roster_status` without leaving compatibility aliases"
  (proposal §Repository).
- `services/api/app/contracts/roster.py`: `RosterEntryCreate` is
  updated to drop the public `status` input, "delete the public
  create-status input and update foundation tests rather than
  preserving a compatibility path".
- Invariant test `test_no_legacy_roster_in_memory_remains`
  (AC trace §Invariants) pins the removal.

Complies with AGENTS.md §"No Backwards Compatibility".

### 2. Hardcoded actors — fixed
Current substrate at `services/api/app/services/roster.py:31-38`
hardcodes `actor_kind="system"` and `actor_id="roster-service"`.
The proposal replaces all three entry points with `actor` threaded
from the endpoint layer:

- `create_roster_entry(db, request, actor)`
- `transition_roster_entry(db, entry_id, request, actor, expected_version)`
- `record_roster_sync_failure(db, roster_entry_id, request, actor, expected_version)`

The service-actor identity for Discord (`roster-syncer`) is
enforced at the endpoint layer (proposal §Endpoints, sync-failure
route) and still passed to `mutate_entity` as the audit actor —
consistent with the SLICE-013 `discord-provisioner` pattern at
`services/api/app/services/chapters.py:339-342`.

### 3. Duplicated logic — reused, not duplicated
`_validate_roster_transition` (existing
`services/api/app/services/roster.py:41`) is the D2 matrix.
Proposal §WU-033 Service step `transition_roster_entry` says
"Applies D2 state matrix exactly" and the invariant test
`test_transition_state_machine_allowed_and_rejected_transitions`
pins it against the live matrix — no parallel validator is added.

### 4. Fake transactions — none
`enqueue_effect` is called inside the same `mutate_entity`
transaction for `record_roster_sync_failure` (proposal §Service,
D9). This mirrors `_enqueue_failed_provisioning_effect` at
`services/api/app/services/chapters.py:273-305`, which receives the
open `connection` from the `mutate_projection` callback. No
convenience path that opens its own connection.

### 5. Idempotency key — per transition, not per chapter
Proposal sets
`idempotency_key = f"roster_sync_retry:{roster_entry_id}:{request.transition_id}"`
(proposal §Service, `record_roster_sync_failure`), matching D9.
Roster-scoped + transition-scoped deduplication. Allows later
transitions on the same entry to enqueue their own retries;
prevents repeat failure reports for the same desired state from
duplicating effects. No chapter-wide shortcut.

### 6. Deferred stubs — none in-scope, deferrals disclosed
- `POST /api/v1/roster-entries/{id}/sync-failure` is a real
  endpoint with actor auth, OCC, authority, and `mutate_entity`
  enqueue (proposal §Endpoints). Not a TODO.
- Discord role-sync worker for executing retries is explicitly
  out-of-scope (proposal §Out of Scope bullet: "No deferred-effect
  worker for executing roster sync retries. This slice enqueues
  the effect only."). This is scope deferral, not a stub — no
  placeholder code.
- Stale-role-ID rediscovery by name in the Discord handler does
  not persist the corrected role ID; the proposal documents this
  in §Tradeoffs ("persisting the corrected role ID is deferred to
  a later resource-reconciliation slice"). This is a disclosed
  scope boundary, not a TODO in code.

Complies with AGENTS.md §"No Deferred Stubs".

### 7. Chapter role ID resolution — substrate-consistent
Proposal resolves Discord role IDs through the SLICE-013 substrate
`chapters.discord_resources.role_ids[chapter_role.name]`
(proposal §Handler, D4). No hardcoded mapping, no parallel table.
Ordered fallback is:

1. `event.chapter_discord_role_id` if present (API can
   pre-resolve).
2. `event.chapter_discord_resources["role_ids"][event.chapter_role_name]`.
3. Rediscovery via `guild.roles` by deterministic role name if
   the stored ID is stale.

This is a resolver chain over the same stored value, not a
duplicated mapping.

### 8. Foundation replacement — in-place, not parked
Migration `wu-033_roster.py` extends `roster_entries` (adds
`updated_at`, `removal_metadata`, chapter FK, composite role FK,
partial unique index) and adds `roster_transitions` + seeded
`roster-syncer` grant. The foundation table is not parked or
duplicated; it is the durable aggregate table (D1). Existing
contracts/repositories/service are rewritten, not wrapped.

### 9. Authority grants — global is binding, not a shortcut
D10 binds global scope for `roster-syncer`'s `roster.read` /
`roster.write`. Proposal seeds exactly these and notes
"Per-chapter service grants would be tighter, but D10 explicitly
defers them" (§Tradeoffs). This is an explicit synthesis decision,
not a shortcut — the tradeoff is documented. The endpoint still
pins `actor_id == "roster-syncer"` at the handler boundary.

### 10. Originating actor — propagated, not defaulted away
`RosterEntryTransitionRequest.originating_actor_id` and
`RosterSyncFailureRequest.originating_actor_id` are required
(`Field(min_length=1)`), mirroring the SLICE-013 originating-actor
pattern in `services/api/app/contracts/chapters.py`. Payloads
flow into `roster_transitions` and state-change projections
(D11).

## Summary Table

| Focus area                              | Finding | Severity |
|-----------------------------------------|---------|----------|
| Compatibility shims for legacy roster   | Replace-in-place, invariant test pins removal | None |
| Hardcoded system actor                  | Threaded from caller; endpoint enforces service identity | None |
| Duplicated state-machine logic          | `_validate_roster_transition` reused | None |
| Fake transactions / convenience connection | `enqueue_effect` uses `mutate_entity` connection | None |
| Idempotency key scope                   | Per-transition (roster_entry_id + transition_id) | None |
| `sync-failure` endpoint as stub         | Real endpoint, full OCC + authority + enqueue | None |
| Chapter role ID hardcoded mapping       | Resolved via `chapters.discord_resources.role_ids[name]` | None |
| Foundation parked vs. replaced          | Extended in-place; no alias layer | None |
| Stale-role-ID persistence               | Disclosed deferral (resource-reconciliation slice) | Observation |
| `check_required_bot_permissions` reuse  | Not referenced in proposal; D8 covers failure via `Forbidden` path | Observation |
| Global `roster-syncer` grant            | D10-bound, documented tradeoff | Not a shortcut |

## What LOW Requires

LOW holds as long as implementation enforces the proposal's
explicit boundaries:

1. `enqueue_effect` in `record_roster_sync_failure` is called
   with the same `connection` passed into `mutate_projection`
   (mirror `services/api/app/services/chapters.py:273-305`). No
   `db.connection()` inside the callback.
2. `read_roster_entry`, `transition_roster_status`,
   `insert_roster_entry`, `fetch_roster_entry`,
   `update_roster_status`, and the public `status` field on
   `RosterEntryCreate` are fully removed — not aliased, not
   re-exported. The `test_no_legacy_roster_in_memory_remains`
   test must assert this by import or symbol probe.
3. All three service functions require `actor` as an argument and
   thread it into `MutationRequest`. No module-level
   `actor_id="roster-service"` constant survives.
4. `_validate_roster_transition` (or its replacement) is the only
   matrix checker — no inline `if/elif` matrix in
   `transition_roster_entry`.
5. Sync-failure endpoint checks `actor_kind=="service"` and
   `actor_id=="roster-syncer"` before invoking the service;
   failure to match returns 403 before any mutation.
6. Stale `If-Match` on sync-failure returns 412 and does not
   insert a deferred effect (test
   `test_sync_failure_idempotency_key_per_transition` must cover
   both branches).
7. Discord handler's role-ID rediscovery by name must not write
   the corrected ID back to `chapters.discord_resources` in this
   slice — that persistence belongs to the later reconciliation
   slice as disclosed.

If any of these slip in implementation, the risk rises to MEDIUM
(one substrate-violating shortcut) or HIGH (multiple).
