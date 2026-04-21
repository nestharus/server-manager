# SLICE-018 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-018 proposal and implementation.
The proposal may choose implementation mechanics inside these boundaries, but
it must not add scope, replace these directions, or introduce compatibility
paths around them.

## Binding Decisions

- **D1 — BINDING: RosterEntry aggregate and version handling.**
  `roster_entries` is the durable `RosterEntry` aggregate table and uses
  `aggregate_type = "roster_entry"` for optimistic locking. `roster_entries`
  must not gain an independent `version` column. Read models must obtain
  `version` by joining `aggregate_heads` on
  `aggregate_type = "roster_entry"` and `aggregate_id = roster_entries.id`.
  `RosterEntryRead` must include `version`.

- **D2 — BINDING: Roster state machine.**
  The only valid roster statuses are `active`, `on_leave`, `under_review`,
  and `removed`. Allowed transitions are `active -> on_leave`,
  `active -> under_review`, `active -> removed`, `on_leave -> active`,
  `on_leave -> removed`, `under_review -> active`, and
  `under_review -> removed`. No transition is allowed out of `removed`.
  Re-admission after removal creates a new `RosterEntry` row and must not
  resurrect or mutate the removed row back to a non-removed state.

- **D3 — BINDING: RosterTransition projection.**
  `RosterTransition` must mirror the existing `chapter_transitions` projection
  pattern. The service writes the roster entry mutation and transition
  projection inside the same `mutate_entity(connection=...)` transaction, using
  `mutate_projection`. `aggregate_seq` is always `expected_version + 1`.
  `roster_transitions` must have a unique index on
  `(roster_entry_id, aggregate_seq)`.

- **D4 — BINDING: ChapterRole identity.**
  Stable `chapter_roles.id` remains the roster identity anchor stored in
  `roster_entries.role_id` and transition role fields. Discord role IDs must
  not be duplicated into `chapter_roles`. Discord role IDs are resolved from
  `chapters.discord_resources.role_ids[chapter_role.name]`.

- **D5 — BINDING: Member identity.**
  `roster_entries.member_id` remains `TEXT` without a foreign key in SLICE-018
  because the SLICE-007 member aggregate is not merged. Treat `member_id` as an
  external durable identifier. Discord sync events must carry
  `member_discord_user_id` separately and must not infer it from a local member
  table.

- **D6 — BINDING: Current roster uniqueness.**
  Add the partial unique index
  `uq_roster__chapter_member_active` on
  `roster_entries (chapter_id, member_id) WHERE status != 'removed'`. This
  prevents more than one non-removed entry for the same chapter-member pair
  while preserving removed historical rows.

- **D7 — BINDING: Operator roster authority scopes.**
  Operator-facing roster endpoints are chapter-scoped and user-actor-only.
  The only new roster permissions are `roster.read`, `roster.write`, and
  `roster.remove`; removal requires the dedicated `roster.remove` permission
  because it is destructive. `POST /api/v1/roster-entries` derives
  `scope_id` from `body.chapter_id`. `GET /api/v1/roster-entries/{id}` and
  transition endpoints first fetch the roster entry, derive the chapter
  `scope_id` from that row, then authorize `roster.read`, `roster.write`, or
  `roster.remove` as required by the operation and `to_status`. The
  `/sync-failure` endpoint is excluded from this chapter-scoped operator
  policy and follows D10.

- **D8 — BINDING: Discord sync idempotency.**
  The Discord `sync_roster` handler is idempotent. It adds missing target role
  IDs, skips roles already present, removes target-absent roles when the target
  state requires removal, and skips roles already absent. It must call
  `Member.add_roles([role], reason=...)` and
  `Member.remove_roles([role], reason=...)` with explicit reason strings. On
  Discord `Forbidden`, `NotFound`, or `HTTPException`, the handler must record
  a consequential deferred effect through the API rather than swallowing the
  failure or writing directly to the database.

- **D9 — BINDING: Deferred effect on sync failure.**
  The API exposes a service method
  `record_roster_sync_failure(roster_entry_id, reason, expected_version)`.
  It runs inside `mutate_entity` for the `roster_entry` aggregate and enqueues
  the retry in the same transaction. The idempotency key is
  `f"roster_sync_retry:{roster_entry_id}:{transition_id}"`,
  `consequence_level = "consequential"`, and
  `precondition_state = "unchecked"`. A stale `expected_version` must reject
  the failure recording and must not enqueue a retry for obsolete desired
  state.

- **D10 — BINDING: Discord handler service actor.**
  The Discord roster sync handler uses a new service actor,
  `roster-syncer`, separate from `discord-provisioner`. The migration for
  SLICE-018 seeds authority grants for `roster-syncer` with `roster.read` and
  `roster.write` at global scope. Per-chapter service grants are deferred and
  must not be introduced in this slice. `POST
  /api/v1/roster-entries/{id}/sync-failure` is service-only: it requires a
  service actor, rejects non-service actors before mutation, and authorizes
  `roster.write` at `scope_kind = "global"` to match the seeded
  `roster-syncer` grant.

- **D11 — BINDING: Originating user propagation.**
  Discord-to-API roster calls carry `originating_actor_kind` and
  `originating_actor_id` in the request body. The API records these values in
  audit payloads and transition rows using the same originating actor pattern
  established by SLICE-013.

- **D12 — BINDING: Anti-scope.**
  SLICE-018 must not implement advanced roster analytics, bulk CSV import,
  leadership succession workflow, roster archival, cross-chapter transfer, or
  automatic synchronization of per-role permission grants into
  `authority_grants`.

## Anti-Scope

- Advanced roster analytics.
- Bulk roster import from CSV or other files.
- Leadership succession workflow; this belongs to SLICE-024.
- Roster archival.
- Cross-chapter transfer.
- Automatic per-role permission grant synchronization into `authority_grants`.

## Traceability

| Decision | Supports / resolves |
|---|---|
| D1 | Supports AC3: optimistic locking with versioned reads and stale transition rejection. Resolves research finding 1 that roster version must come from `aggregate_heads`, matching chapter lifecycle. |
| D2 | Supports AC2: status transitions are explicit and auditable. Resolves research finding 4 that `removed` is terminal and re-admission creates a new entry. |
| D3 | Supports AC2 and AC3: every transition records actor/reason metadata in the same transaction as the versioned aggregate update. Resolves research finding 2 that roster transitions should mirror `chapter_transitions`. |
| D4 | Supports AC1 and Discord sync correctness: roster entries tie to durable chapter role identity while Discord IDs remain provisioning resources. Resolves research finding 3 that `chapter_roles.id` is the stable identity and Discord role IDs live in `chapters.discord_resources`. |
| D5 | Supports AC1 and WU-034 sync contract: roster state can ship before SLICE-007 member storage. Resolves research finding 7 that no merged member table exists and `member_id TEXT` must remain external. |
| D6 | Supports AC1 and D2: direct roster add cannot create competing current entries for the same chapter member while preserving removed history for re-admission. Resolves research finding 4's current-entry invariant. |
| D7 | Supports AC1, AC2, and destructive removal safety: operator roster reads/writes are authorized for the owning chapter, and removal has its own permission. Resolves research finding 8 about chapter-scoped roster authority and two-step authorization for entry-id routes while excluding the service-only sync-failure route. |
| D8 | Supports AC4: Discord role sync is recoverable and does not silently drift. Resolves research finding 5 that no existing role sync path exists and the handler must be idempotent around add/remove operations. |
| D9 | Supports AC4 and AC3: failed Discord role updates enqueue consequential deferred work only when the roster version is still current. Resolves research finding 6 and the proposed API concurrency spike. |
| D10 | Supports AC4 and least-confusion service attribution: roster sync has a distinct service actor from chapter provisioning, and sync-failure reporting uses global service authority instead of chapter scope. Resolves research finding 8's service grant question by binding global service grants for this slice. |
| D11 | Supports AC2 and audit accountability: Discord-originated roster changes preserve the human originator separately from the service actor. Resolves the SLICE-013 pattern reuse noted in the task input. |
| D12 | Resolves proposal scope risk by excluding roadmap-adjacent work that belongs to later slices or separate initiatives. Aligns with SLICE-018 ticket boundaries and the research warning against expanding into analytics, imports, succession, archival, transfer, or authority auto-sync. |
