# SLICE-018 Phase 4 Audit Risk Assessment

**Rating: LOW**

## Scope note

This audit evaluates `worktrees/slice-018/.pipeline/proposal.md` (Revision 1) against binding synthesis decisions D1–D12 (`.pipeline/synthesis.md`), the SLICE-018 ticket's four ACs, Phase 1 research, and merged substrate (SLICE-001..013). Focus areas from the prompt: atomic deferred-effect enqueue, D6 partial-unique race handling, OCC enforcement on transitions, terminal-state invariant for `removed`, authority fetch-then-enforce races, `roster-syncer` grant-scope correctness, Discord handler idempotency under concurrent events, originating-user audit propagation, Discord 3-second ack, member-departure non-blocking semantics, and wu-033 migration safety against the existing wu-007c foundation.

The prior audit (pre-Revision 1) rated this MEDIUM on F1 — a contradiction between the sync-failure endpoint's chapter-scoped authority requirement and the D10 global-only grant for `roster-syncer`. Revision 1 of the proposal explicitly resolves this by splitting the authority model: operator endpoints are chapter-scoped and user-actor only, while `/sync-failure` is global-scoped, service-actor only, with explicit pre-mutation actor identity checks and a matching positive/negative AC4 trace. That resolution is load-bearing and correctly reasoned against `services/api/app/services/authority.py:236–244`. With F1 retired, no remaining finding rises above LOW.

## Findings

### F1 — `roster-syncer` authority scope (RESOLVED in Revision 1)

Pre-revision, the proposal required `roster.write` at `scope_kind="chapter"` on the sync-failure endpoint while D10 constrained `roster-syncer` to a global-only grant. The merged `evaluate()` rejects kind mismatches (`services/api/app/services/authority.py:238–241`), so the Discord handler's sync-failure POST would have received 403 and AC4 would have silently degraded.

Revision 1 resolves this cleanly. Proposal §3 (proposal.md:277–286) now specifies:

- `POST /api/v1/roster-entries/{id}/sync-failure` requires `roster.write` at `scope_kind="global"` with no chapter `scope_id`, matching the D10-seeded grant exactly.
- The endpoint rejects `actor_kind != "service"` and `actor_id != "roster-syncer"` **before** the authority check, with `403 {"code": "service_actor_required"}`. This is implemented as a local FastAPI dependency (`_service_actor_only`) rather than a service-layer assert, so a user-actor X-Actor-Id spoof cannot reach the authority evaluator.
- Operator endpoints (`POST /roster-entries`, `GET /roster-entries/{id}`, `POST /roster-entries/{id}/transitions`) retain chapter-scoped authority per D7 and require `actor_kind="user"`.

AC4 trace now includes both `test_sync_failure_rejects_non_service_actors_with_403` and `test_sync_failure_accepts_roster_syncer_service_actor_with_global_grant` (proposal.md:298–300, 462–463), pinning both the authority-kind match and the identity gate.

Residual observation (not a defect): the endpoint-layer actor-identity dependency is the only thing keeping the global grant from being reachable by an operator spoof. The proposal pins it correctly. LOW.

### F2 — Atomic `mutate_entity` + `enqueue_effect` on the roster aggregate (LOW)

`record_roster_sync_failure` runs `enqueue_effect` inside the `mutate_projection` callback on the active connection (proposal.md:227–236, D9 synthesis.md:74–86). `services/api/app/repositories/deferred_effects.py:31–102` accepts a caller connection, and `services/api/app/services/mutations.py:94–202` runs `mutate_projection(active_connection)` inside the same `db.transaction()` block. This mirrors `_enqueue_failed_provisioning_effect` in `services/api/app/services/chapters.py:273–305`, which SLICE-013's audit rated sound. Stale `If-Match` is rejected before the projection runs (mutations.py:123–148), so the enqueue cannot fire for an obsolete desired state. The idempotency key `roster_sync_retry:{roster_entry_id}:{transition_id}` rides `ON CONFLICT (idempotency_key) DO NOTHING` (deferred_effects.py:66), so duplicate failure reports for the same transition are silently merged. Sound.

### F3 — D6 partial unique index + typed `RosterDuplicateCurrentEntryError` (LOW)

D6 binds `uq_roster__chapter_member_active` on `(chapter_id, member_id) WHERE status != 'removed'`. Proposal.md:199–200 maps the index violation to `RosterDuplicateCurrentEntryError` → 409. Concurrent CREATE on the same `(chapter_id, member_id)` is arbitrated by Postgres partial-unique-index enforcement on insert; one INSERT wins, the other raises `UniqueViolation`, and the service translates to 409. The create-vs-resurrect race is also safe: the transition-to-removed path holds `SELECT … FOR UPDATE` on `aggregate_heads` plus the roster row, so a concurrent CREATE either (a) commits after removal and succeeds because the now-`removed` row is excluded by the partial predicate, or (b) commits before and blocks the CREATE on the index. D2 prohibits mutating a removed row back to non-removed, so no resurrection path exists.

Sub-risk — the service must catch `psycopg.errors.UniqueViolation` specifically and distinguish it from the existing FK-violation path for `role_id` → `RosterRoleNotFoundError` at `services/api/app/services/roster.py:105–106`. The except-clause ordering must prefer the more specific error. Pin a test `test_create_roster_duplicate_current_entry_returns_409_not_500`.

### F4 — OCC on transitions (LOW)

All mutation endpoints require `If-Match`:

- `POST /api/v1/roster-entries/{id}/transitions` — proposal.md:269–276,
- `POST /api/v1/roster-entries/{id}/sync-failure` — proposal.md:277–286.

Parser semantics mirror `services/api/app/api/v1/endpoints/chapters.py:39–51`: missing → 428, malformed → 400, stale → 412 from `StaleMutationError`. Create uses `expected_version=0` server-side and returns ETag `"1"`, consistent with chapter create. No transition path bypasses `mutate_entity`; both `transition_roster_entry` and `record_roster_sync_failure` route through the mutation helper, and the projection callback only runs on version match. Sound.

### F5 — Terminal `removed` state invariant (LOW)

D2 makes `removed` terminal; re-admission creates a new `RosterEntry` row. The existing `_validate_roster_transition` in `services/api/app/services/roster.py:41–49` already encodes `"removed": set()`. Proposal.md:210–214 re-states "no transition out of `removed`" and AC2 trace includes `test_removed_is_terminal_no_further_transitions`. No code path in the proposal bypasses the validator — `transition_roster_entry` calls it inside `mutate_projection` after fetching `FOR UPDATE`. The D6 partial unique index is a second line of defense if a resurrection path were ever added later.

### F6 — Authority fetch-then-enforce race on transitions (LOW)

D7 requires entry-id endpoints to fetch the row, derive `chapter_id`, then enforce authority. Roster entries never change `chapter_id` anywhere in the proposal: the proposed `_update_roster_entry(connection, entry_id, status, role_id, removal_metadata)` has no `chapter_id` parameter, D12 excludes cross-chapter transfer, and the composite FK `(chapter_id, role_id) -> chapter_roles(chapter_id, id)` prevents a role swap that would implicitly require a chapter change. Roster rows are never deleted — removal is a status transition — so the aggregate cannot vanish between enforcement and service execution. Sound.

### F7 — Discord handler idempotency under concurrent sync events (LOW)

D8 binds skip-present / skip-absent idempotency. Two concurrent sync events on the same entry:

- **Both succeed.** Each reads `Member.roles`, decides add/remove, and issues the Discord API call. Discord's `add_roles`/`remove_roles` are server-side idempotent. No deferred effect enqueued. Eventually consistent — last-write-wins is accepted per D8 and research finding 6.
- **Both fail.** Each calls `/sync-failure` with the same `transition_id` → same `idempotency_key` → `ON CONFLICT DO NOTHING` dedupes the effect row. `mutate_entity` + `SELECT FOR UPDATE` on `aggregate_heads` serializes the two API calls: the first advances the head by one, the second sees a stale `expected_version` and returns 412. The handler's `failure_recorded=False` short-circuit (proposal.md:359–360) is correct — no obsolete retry is created.
- **Different transitions (T1 then T2).** Distinct `transition_id` values yield distinct idempotency keys; both effect rows are enqueued. Correct.

Sound.

### F8 — Originating actor propagation into audit payloads (LOW)

`RosterEntryTransitionRequest` and `RosterSyncFailureRequest` both carry `originating_actor_kind` and `originating_actor_id` (proposal.md:152–153, 161–162). The `payload_allowlist=set(request.model_dump(mode="json").keys())` pattern from `services/api/app/services/chapters.py:160` preserves these fields in `action_payload` after `_redact_payload`. D11 also requires them on transition rows, and the proposal writes them explicitly in the `roster_transitions` INSERT (proposal.md:121–122, 218–219).

Sub-risk — `RosterSyncFailureRequest` defaults `originating_actor_kind` to `"service"`. Correct for the Discord-to-API retry context (the "originating" actor on sync-failure is the Discord handler re-invoking itself), but this means the human operator who triggered the earlier transition is not surfaced in the sync-failure audit row's `originating_actor_*` fields. Operators tracing a deferred retry to a human will need to join `deferred_effects.payload_json` or the earlier `activity_actions` row by `transition_id`. Acceptable given audit schema; a one-line pin that the deferred effect's `payload_json` carries through the prior transition's human originator would be clearer polish.

### F9 — Discord handler 3-second ack (LOW / N/A this slice)

SLICE-013 established that `ack_deferred()` must fire before any API or Discord call for interactions that enter via a slash command. SLICE-018's `sync_roster(event: RosterSyncEvent, *, api_client=None, guild=None) -> RosterSyncResult` (proposal.md:335–336) has no `InteractionEnvelope` parameter and no `ack_deferred` call site. The handler is not wired to a slash command in this slice; the invocation surface is deferred along with the retry worker. 3-second budget does not apply.

Forward risk: if a later slice wires `sync_roster` to a Discord interaction (e.g., operator "sync now"), that slice must own the ack-before-API seam. A one-line anti-scope note pinning this is worthwhile but not blocking.

### F10 — Member departure and stale role ID non-blocking on roster state (LOW)

D8 requires the handler to classify `NotFound` (departed member, deleted role), `Forbidden`, `HTTPException`, stale role, or resolution failures as sync failures and record them through the API. `record_roster_sync_failure` explicitly does not change `roster_entries.status` or `role_id` (proposal.md:225). The roster aggregate remains authoritative; Discord drift continues until a future retry slice lands. AC4 is satisfied — the failure is captured as a consequential deferred effect rather than silently dropped.

Sub-risk — if the sync-failure API call itself fails (network, 412 stale, 500), the handler returns `failure_recorded=False` (proposal.md:359–360). The original Discord error is lost to the upstream dispatcher; only in-process logs record it. Acceptable given the upstream dispatcher can retry the whole event on any non-successful return. A one-line pin on this contract to the dispatcher would be clearer.

### F11 — wu-033 migration safety against existing wu-007c `roster_entries` rows (LOW)

Changes to `roster_entries`:

- Add `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP` — safe on non-empty tables.
- Add `removal_metadata JSONB NOT NULL DEFAULT '{}'::jsonb` — safe.
- Add `FK chapter_id -> chapters(id)` — will fail if any existing row carries a `chapter_id` absent from `chapters`. Production has zero rows (no endpoint on `main`). Test fixtures that inserted roster_entries with arbitrary `chapter_id` strings must be updated.
- Add composite FK `(chapter_id, role_id) -> chapter_roles(chapter_id, id)` — requires the new `uq_chapter_roles__chapter_id_id` unique constraint first (proposal.md:104). Adding the explicit unique constraint on `(chapter_id, id)` is safe because `chapter_roles.id` is already PK-unique; every `(chapter_id, id)` pair is distinct by the underlying id uniqueness.
- Add partial unique index `uq_roster__chapter_member_active` — will fail if existing rows violate the constraint. Foundation-only data is compliant by its single-insert test pattern.

Proposal.md:102–103 acknowledges the fixture update: "update roster tests to seed a chapter before creating chapter roles or roster entries". Operational pin: any non-main environment with seeded `roster_entries` rows lacking matching `chapters` rows must be cleaned up before running wu-033.

### F12 — Role-only transition ambiguity (LOW)

AC2 says "Status **and** role transitions create a RosterTransition row". The D2 matrix does not include self-loops (`active -> active`), so a request with `to_status == current_status` and a different `to_role_id` would be rejected by `_validate_roster_transition` as written. Two reads of AC2 are possible: role-only transitions accepted, or role-only transitions require a paired status change.

The proposal does not explicitly address this. Neither branch causes data corruption; this only determines whether a certain request shape is accepted. Pin the chosen semantic (and a matching positive or negative test) before implementation.

### F13 — `payload_allowlist` scope for roster mutations (LOW)

Implementation must specify `payload_allowlist` for `create`, `transition`, and `sync_failure` mutations. Following the chapter pattern, `set(request.model_dump(mode="json").keys())` includes all request fields; none carry secrets. `RosterSyncFailureRequest.desired_discord_role_ids` and `member_discord_user_id` are operational identifiers, not secrets. Pin this choice in §6.

### F14 — `roster-syncer` actor_id namespace collision with user actor_id (LOW)

`services/api/app/core/dependencies.py:80` looks up grants by `actor.actor_id` only. A user actor whose `actor_id` is literally `"roster-syncer"` would inherit the seeded global grants. Discord user ids are numeric snowflakes in practice, so collision with a non-numeric service actor name is implausible. The `/sync-failure` actor-identity gate requires `actor_kind="service"`, which is an independent discriminator — a user actor spoofing `actor_id="roster-syncer"` would still be rejected at the dependency layer. A reserved naming convention (e.g., `service:` prefix) would be ideal but is out of scope here.

### F15 — wu-033 migration `downgrade()` path for the `roster-syncer` seed grant (LOW)

SLICE-013's wu-019 migration seeds the `discord-provisioner` grant with a `NOT EXISTS` guard and its `downgrade()` deletes by permissions match. Proposal.md:130–132 specifies the `roster-syncer` seed but does not name the `downgrade()`. Pin a downgrade that deletes by `grantee_id='roster-syncer' AND scope_kind='global' AND permissions JSONB match AND revoked_at IS NULL`, mirroring wu-019.

### F16 — Legacy roster substrate replacement without compatibility shim (LOW)

Proposal.md:188–190, 238–240 declares `insert_roster_entry`, `fetch_roster_entry`, `update_roster_status`, `read_roster_entry`, and `transition_roster_status` are renamed/removed with no compatibility aliases. The legacy names are consumed only in `services/api/app/services/roster.py`, `services/api/app/repositories/roster.py`, and their tests. Atomic rip-out is safe. AC trace test `test_no_legacy_roster_in_memory_remains` pins this (proposal.md:471).

### F17 — `enqueue_effect` depends on request-scoped audit context (LOW)

`_enqueue_failed_provisioning_effect` at `services/api/app/services/chapters.py:281–283` reads `get_current_audit_context()` and raises if missing. `record_roster_sync_failure` must do the same. Because the endpoint goes through `ActorMiddleware` → `use_audit_context` → `mutate_entity`, the context is guaranteed under request-scoped invocation. The proposal does not name this dependency explicitly; pin in §6 that the sync-failure projection inherits the request's correlation id.

### F18 — Unchecked consequential effects accumulate until retry-worker slice (LOW, operational)

SLICE-004's worker cannot claim `precondition_state="unchecked"` consequential rows. Every failed Discord sync therefore leaves a `roster_role_sync / roster_sync_retry` row in the queue until a future precondition-validator slice lands. Operators will see non-empty queues. Not a correctness bug — a one-line anti-scope pin acknowledging the accumulation profile is the right mitigation.

## Summary table

| # | Finding | Severity |
| --- | --- | --- |
| F1 | `roster-syncer` authority scope split — sync-failure global, operator endpoints chapter-scoped | RESOLVED (Revision 1) |
| F2 | `mutate_entity` + `enqueue_effect` atomicity on roster aggregate | LOW |
| F3 | D6 partial unique index + typed `RosterDuplicateCurrentEntryError` | LOW |
| F4 | OCC via `If-Match` enforced on all transition and sync-failure endpoints | LOW |
| F5 | `removed` terminal state preserved; re-admission creates new row | LOW |
| F6 | Fetch-then-enforce chapter resolution; roster entries never change `chapter_id` | LOW |
| F7 | Concurrent Discord sync events idempotent end-to-end | LOW |
| F8 | Originating actor propagated into action payloads and `roster_transitions` | LOW |
| F9 | 3-second Discord ack not applicable — `sync_roster` is not a slash-command handler | LOW |
| F10 | `record_roster_sync_failure` does not mutate roster state; departure non-blocking | LOW |
| F11 | wu-033 FK + partial-unique additions safe given empty production roster_entries | LOW |
| F12 | Role-only transition (no status change) semantics not pinned | LOW |
| F13 | `payload_allowlist` choice for roster mutations not explicitly pinned | LOW |
| F14 | `roster-syncer` actor_id namespace vs user actor_ids | LOW |
| F15 | wu-033 `downgrade()` not specified for `roster-syncer` seed grant | LOW |
| F16 | Legacy roster substrate replaced atomically with no compatibility residue | LOW |
| F17 | Deferred-effect enqueue depends on request-scoped audit context — not explicitly pinned | LOW |
| F18 | Unchecked consequential effects accumulate until retry-validator slice ships | LOW |

## Verdict

**LOW.** Revision 1 retires the only pre-revision defect (F1) by splitting operator and service authority exactly as `evaluate()` requires and as D10 permits. All remaining findings are implementation polish — payload allowlist pins, downgrade path specification, role-only transition semantics, operational runbook notes — none of which cause data loss, corruption, or security exposure. The core safety properties (atomic enqueue on same connection, OCC on every mutation, terminal `removed` state, fetch-then-enforce for chapter-scoped authority, idempotent Discord mutations, non-blocking sync-failure) are load-bearing and correct against the merged substrate.

## What LOW requires

Not applicable — rating is already LOW.

Non-blocking polish worth absorbing in §6 before implementation (none of these block downgrade to LOW):

- **F8 sub-risk** — pin the deferred effect's `payload_json.originating_actor_*` to carry the original human operator from the prior transition, so retry audit rows can be joined to a human without walking `activity_actions`.
- **F9 forward-risk pin** — one-line anti-scope note that `sync_roster` is not an interaction handler this slice and any future interaction-triggered call path must wrap it in an `ack_deferred` shim.
- **F10 sub-risk** — pin that the upstream dispatcher invoking `sync_roster` owns retry on `failure_recorded=False`.
- **F11 operational pin** — runbook note that non-main environments with non-empty `roster_entries` rows lacking matching `chapters` rows must be cleaned up before running wu-033.
- **F12** — pin whether role-only transitions (no status change) are accepted; add a positive or negative AC2 test.
- **F13** — pin `payload_allowlist=set(request.model_dump(mode="json").keys())` for all three roster mutations.
- **F14** — pin that service-actor `grantee_id` values are non-numeric and reserved from the user `actor_id` namespace.
- **F15** — specify wu-033 `downgrade()` deletes the `roster-syncer` seed grant, or use a deterministic UUIDv5 id with `ON CONFLICT (id) DO NOTHING` for idempotent cycle safety.
- **F17** — explicitly state that the sync-failure projection inherits `get_current_audit_context()` and raises if missing, mirroring `_enqueue_failed_provisioning_effect`.
- **F18** — one line to §2 anti-scope acknowledging that unchecked consequential `roster_role_sync` effects will accumulate until the retry-validator slice lands.
