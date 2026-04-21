# SLICE-018 Scope Risk: **LOW**

Rating: **LOW** — the proposal delivers the 4 ACs with named tests, observes D12 anti-scope verbatim, and the single route beyond the ticket's enumerated endpoint list (`POST /sync-failure`) is required by AC4 and the D8/D9 "Discord calls the API, not the DB" pattern already established in SLICE-013.

## SLICE-018 ACs (ticket)

1. Direct roster add creates an active roster entry tied to a chapter role.
2. Status and role transitions create a `RosterTransition` record with actor attribution and reason.
3. Read with version `N`, transition with `expected_version = N`, then retry with stale `N` returns `412 Precondition Failed`.
4. A failed Discord role update queues a consequential deferred effect instead of silently drifting.

## Findings

### 1. AC trace is complete and testable

| AC | Named tests | Source |
|---|---|---|
| AC1 | `test_create_roster_entry_in_active_state`; `test_create_roster_entry_requires_roster_write_permission_chapter_scope`; supporting invariant `test_partial_unique_index_allows_one_active_per_chapter_member`. | proposal §3 WU-033 tests, §7 AC1. |
| AC2 | `test_transition_creates_roster_transition_row_with_actor`; `test_transition_records_reason`; `test_transition_state_machine_allowed_and_rejected_transitions`; `test_removed_is_terminal_no_further_transitions`. | proposal §3 WU-033 tests, §7 AC2. |
| AC3 | `test_transition_with_current_version_succeeds`; `test_transition_with_stale_version_returns_412`; `test_get_roster_entry_returns_version_and_etag`. | proposal §3 WU-033 tests, §7 AC3. |
| AC4 | `test_sync_failure_enqueues_deferred_effect_atomically`; `test_sync_failure_idempotency_key_per_transition`; `test_sync_failure_preserves_roster_entry_state`; `test_discord_handler_calls_sync_failure_on_forbidden`; `test_discord_handler_rediscovers_role_id_by_name_for_chapter`; plus `test_discord_handler_calls_sync_failure_on_{not_found,stale_role_id,departed_member}`. | proposal §3 WU-033+WU-034 tests, §7 AC4. |

No AC is missing a direct test path. AC4 gets the heaviest coverage because it spans both the API enqueue path and the Discord failure→API call shape; that is correct for the AC, not over-scope.

### 2. Anti-scope items from synthesis D12 are absent

| D12 item | Proposal coverage |
|---|---|
| Advanced roster analytics | Not present. Not mentioned anywhere in §3. |
| Bulk CSV/file import | Explicit in §2 ("No bulk CSV or file import"). No import contract, no import endpoint, no import service. |
| Leadership succession workflow | Explicit in §2 ("No leadership succession workflow; SLICE-024 owns it"). `chapter_roles.triggers_succession` is untouched — no succession trigger code is wired from a `removed` transition. |
| Roster archival | Explicit in §2 ("No roster archival workflow"). No archive state is added; `RosterStatus` literal stays 4-valued (active/on_leave/under_review/removed). |
| Cross-chapter transfer | Explicit in §2 ("No cross-chapter transfer"). The composite FK `(chapter_id, role_id) -> chapter_roles(chapter_id, id)` and D6 partial-unique index actively forbid a transition from carrying a roster entry into another chapter. |
| Automatic per-role permission grant sync into `authority_grants` | Explicit in §2. The only `authority_grants` write in the slice is the D10-required `roster-syncer` service-actor seed. No per-`chapter_roles.id`-to-permission mapping, no reconciliation job. |

### 3. Deviations from the AI roadmap / ticket are explicitly noted

The ticket enumerates 3 API routes + 1 Discord handler. The proposal ships **4 + 1**. The +1 route is `POST /api/v1/roster-entries/{id}/sync-failure`.

- §2 "In scope" lists this as the fourth roster endpoint alongside the three ticket endpoints.
- §3 WU-033 endpoints section includes it and documents the service-actor enforcement, `If-Match` behavior, and 412-on-stale semantics.
- Rationale is AC4 and D8/D9: the Discord handler "must record a consequential deferred effect through the API rather than swallowing the failure or writing directly to the database" (synthesis D8). `record_roster_sync_failure` has to be callable by the Discord service actor, which means it needs an HTTP surface — otherwise WU-034 either (a) writes to the DB directly from Discord (violates D8), or (b) piggybacks on the `/transitions` endpoint with a special reason (conflates failure recording with actual state change and breaks the D9 "does not change status or role_id" invariant).
- The research section 4 also proposed this route explicitly (`POST /api/v1/roster-entries/{roster_entry_id}/sync-failures`). The proposal's singular `sync-failure` is a minor naming variance from the research plural; cosmetic.

**Contract drift from AI roadmap** — the roadmap's inline contracts for WU-033/WU-034 are minimal sketches. The proposal extends both:

- WU-033 `RosterTransitionRequest` → proposal renames to `RosterEntryTransitionRequest`, drops `expected_version` from the body (moved to `If-Match` header, matching the chapter lifecycle pattern and the ticket's AC3 wording which says "Read with version N, transition with expected_version N"), and adds `originating_actor_kind`, `originating_actor_id`, `removal_metadata`. All three additions are required by D11 (originating actor propagation) and by audit-chain parity with SLICE-013. Not new scope.
- WU-034 `RosterSyncEvent` — the roadmap lists 4 fields; the proposal lists 13. The additions (`roster_entry_version`, `transition_id`, `chapter_id`, `member_id`, `chapter_role_name`, `chapter_discord_role_id`, `chapter_discord_resources`, `originating_actor_kind`, `originating_actor_id`, `reason`, `correlation_id`) are driven by D1 (If-Match needs version), D9 (idempotency key needs transition_id), D4 (Discord role resolution through chapter resources by name), D11 (originating actor), and D8 (stale-role rediscovery by name for AC4). Each extra field has a D-decision backing it.
- WU-034 `RosterSyncResult` adds `skipped_role_ids` (idempotency observability) and `failure_recorded` (412 case where failure was not enqueued). Reasonable contract extension, not new behavior.

Both deviations extend rather than contradict the roadmap, and every new field ties back to a binding D-decision.

### 4. In-place refactor of the WU-007C roster foundation

The proposal deletes the public helpers `insert_roster_entry`, `fetch_roster_entry`, `update_roster_status`, renames `read_roster_entry` and `transition_roster_status`, and updates all call sites and tests "with no compatibility shim" (§3 WU-033 repository and service sections). This is scope expansion beyond "add new endpoints".

The justification parallels SLICE-013's legacy-substrate replacement — leaving the public helpers would fork the roster service into two mutation surfaces (foundation public helpers vs. the new lifecycle service), producing inconsistent aggregate-version handling (WU-007C writes version 1 on create but never advances; WU-033 advances via `aggregate_heads`). The in-place refactor prevents that forked state.

The `RosterEntryCreate` contract change (removing the status input, always writing `active` server-side) is similarly forced: D2 pins `removed` as terminal, and allowing a client-created `removed` entry would let callers inject terminal rows that bypass the transition projection and the D6 partial-unique check. Making creation server-side-status-only is a correctness requirement for AC1 and AC2, not aesthetics.

§2 ("Extend, not replace") and §5 ("Preserve the WU-007C `roster_entries` foundation as the durable roster aggregate table. It is extended with lifecycle columns and constraints, not replaced.") spell the boundary out: the TABLE is preserved, the in-code helpers are rewritten. Correct framing.

Flagged here for visibility; not a severity escalation.

### 5. Migration touches `chapter_roles` — infra glue, not CRUD expansion

§3 WU-033 migration adds `UNIQUE (chapter_id, id)` on `chapter_roles` to support the composite FK `roster_entries (chapter_id, role_id) -> chapter_roles (chapter_id, id)`. This touches a WU-007B foundation table but adds no CRUD endpoint, no contract, no service method. It is the minimum DDL needed for the cross-chapter-transfer prevention invariant (D6 + anti-scope cross-chapter transfer). Infra glue, not roster-role CRUD expansion.

No chapter-role create/update/delete endpoints are added. Chapter role lifecycle remains the chapter-provisioning slice's territory (SLICE-013).

### 6. Deferred-effect scope is enqueue-only

- §2 Out of scope: "No deferred-effect worker for executing roster sync retries. This slice enqueues the effect only."
- §3 WU-033 `record_roster_sync_failure` uses `enqueue_effect` via the same `mutate_entity` transaction. No worker, no retry scheduler, no `precondition_validator` registration beyond the repository default `precondition_state="unchecked"`.
- Idempotency key `roster_sync_retry:{roster_entry_id}:{transition_id}` is deterministic and dedups repeat failures for the same desired transition while allowing a later transition to enqueue its own retry. Matches the SLICE-013 pattern for `chapter_provisioning_retry:{chapter_id}:{chapter_transition_id}`.
- AC4 tests confirm atomicity (`test_sync_failure_enqueues_deferred_effect_atomically`) and idempotency key shape (`test_sync_failure_idempotency_key_per_transition`).

### 7. Discord handler scope stays inside WU-034 boundaries

The WU-034 handler does role add/remove on existing Discord members and records failures through the API. It does **not**:

- Create, rename, or persist Discord roles — §3 WU-034: "Do not create, rename, or persist Discord roles in WU-034. Role creation and resource persistence remain the chapter provisioning substrate's job."
- Write to the database directly — §3 WU-034: "Do not write to the database directly from Discord." D8 binding.
- Persist a rediscovered-by-name role ID — the handler uses name-based rediscovery for the AC4 stale-role test but explicitly defers persisting the corrected ID: §4 tradeoff 4 says "persisting the corrected role ID is deferred to a later resource-reconciliation slice". This is the right boundary — persisting through the API would require another API endpoint and re-enter WU-020's chapter-resources PATCH territory.

### 8. New permissions scope is exactly the three D7 names

Only `roster.read`, `roster.write`, `roster.remove` are introduced. Removal requires its own dedicated permission (D7, ticket philosophy principle 7). The service-actor seed `roster-syncer` gets `roster.read` + `roster.write` only — not `roster.remove` — because the Discord handler never initiates a removal; human operators drive removals through the API. Correctly narrow.

### 9. Minor observations (not severity escalations)

| Observation | Verdict |
|---|---|
| `test_no_legacy_roster_in_memory_remains` (invariant test, §7) | **Vestigial.** No in-memory roster substrate exists per research §9 (contracts/repository/service only; no `InMemoryRosterRepository`). Test asserts absence of something that doesn't exist. Low-cost to keep as a grep invariant against future regression, but flag for implementation: confirm the assertion targets a real substrate rather than boilerplate copy of SLICE-013's `test_no_legacy_in_memory_chapter_remains`. |
| `RosterSyncEvent.chapter_discord_resources: dict[str, Any]` passing the full resources dict to Discord | **Acceptable but wide.** Only `role_ids` is consumed for name rediscovery. Could be narrowed to `chapter_discord_role_ids: dict[str, str]`. Not a scope concern; a contract-minimality nit. |
| `/sync-failure` (singular) vs research's `/sync-failures` (plural) | **Cosmetic.** Singular reads as "record-the-sync-failure" verb shape; plural would read as a collection resource. Either works. |
| `RosterEntryCreate` drops the `status` input | **Necessary.** D2 + D6 require `active` on creation. |

### 10. No scope leakage into downstream slices

| Downstream | Would depend on | Present in proposal? |
|---|---|---|
| SLICE-024 leadership succession | `chapter_roles.triggers_succession` + `removed` transition trigger | **No.** §2 anti-scope: "No leadership succession workflow; SLICE-024 owns it." `triggers_succession` is read-only from existing foundation. |
| SLICE-022 compliance | roster state as compliance input | **No.** No compliance hook registered; roster transitions only write to `activity_actions`/`activity_state_changes`/`roster_transitions`. |
| Roster archival (future) | archive state / archived_at column | **No.** `RosterStatus` literal is 4-valued; no archival column. |
| Cross-chapter transfer | endpoint allowing chapter_id change | **No.** Actively prevented by composite FK. |
| Per-role authority auto-sync | background reconciler or write into `authority_grants` | **No.** Only the `roster-syncer` service-actor seed is written. |
| Member aggregate (SLICE-007) | `roster_entries.member_id` FK | **No.** `member_id` stays `TEXT` per D5. |
| Deferred-effect retry worker | handler code for `roster_sync_retry` | **No.** Enqueue only. |

## Summary table

| Risk category | Severity | Notes |
|---|---|---|
| Bundles downstream work (SLICE-024 / archival / cross-chapter / member FK / retry worker) | None | All explicitly excluded per D12 and §2 anti-scope. |
| Missing AC test path | None | All 4 ACs have direct tests per §7. |
| Silent deviation from AI roadmap | None | +1 endpoint (`/sync-failure`), contract extensions to `RosterSyncEvent`/`RosterEntryTransitionRequest`, and use of `If-Match` instead of body-based `expected_version` are all explicit in §2–§3 and backed by D-decisions. |
| Over-scoped Discord handler (role creation, DB writes, ID persistence) | None | §3 WU-034 explicitly forbids role creation/rename, direct DB writes, and persisting rediscovered role IDs. |
| Over-scoped permission model (per-role authority sync) | None | §2 anti-scope; only the three D7-named permissions + the D10 `roster-syncer` service seed. |
| Over-scoped `chapter_roles` changes | None | Only an additional `UNIQUE (chapter_id, id)` to support the composite FK. No CRUD. |
| Foundation helper deletion (in-place refactor) | Low | Scope expansion beyond net-new code but required by D1 aggregate-version consistency and D2 terminal-state correctness. Parallels SLICE-013's legacy substrate replacement. |
| Vestigial invariant test (`test_no_legacy_roster_in_memory_remains`) | Low | Asserts absence of something that already doesn't exist. Minor cost; implementation should confirm the target is real. |

## What LOW requires (already met)

1. Each AC has at least one direct test — **yes** (§7).
2. Anti-scope items (D12) absent from proposal body — **yes** (§2 + table above).
3. Any deviation from the AI roadmap / ticket endpoint list is explicitly noted with rationale — **yes** (`/sync-failure` justified by AC4/D8/D9; contract extensions justified by D11/D4/D9).
4. No deferred-effect worker or precondition validator shipped in this slice — **yes** (§2 explicit; §3 is enqueue-only).
5. No leadership succession, archival, cross-chapter transfer, bulk import, analytics, or per-role authority auto-sync — **yes** (§2 + §10 table).
6. Chapter-role CRUD stays in SLICE-013's territory; the only `chapter_roles` touch is the composite-FK supporting unique index — **yes** (§5).
7. Foundation helper replacement is scoped with grep-style invariants and justified by correctness — **yes** (§4 of this assessment; §2 + §3 of the proposal).

No scope reductions or additions are required. The proposal is right-sized for the 4 ACs, and every expansion beyond the ticket's minimal shape has an explicit D-decision rationale.
