# SLICE-018 Phase 8 — Opus Justification Review (PR #43)

Reviewed: 2026-04-20
PR: `feat/slice-018-roster-management` (#43)
Branch head: `ce2fe59` (against `origin/main` = `560b305`)
Inputs: `.pipeline/proposal.md` (Revision 1), `.pipeline/synthesis.md` (D1–D12),
`product-strategy/tickets/SLICE-018.md` (AC1–AC4), `plans/risk/slice-018-audit.md`,
`plans/risk/slice-018-scope.md`, `plans/risk/slice-018-shortcut.md`,
`git diff origin/main..HEAD`.

## 1. Verdict

**`LOW_CONCERN`** — no HIGH findings. Every non-trivial file traces to an
AC / D-decision / prior-slice / revision rationale. The six LOW findings
below are minor hygiene items that do not block merge.

No scope creep blocks merge: the only endpoint beyond the ticket's enumerated
set (`POST /sync-failure`) is explicitly in proposal §2 and §3 and is
required by D8/D9 (Discord-to-API, not Discord-to-DB). No deferred stubs
(`TODO`, `NotImplementedError`, placeholder `pass`). No backwards-compatibility
shims — legacy `insert_roster_entry`, `fetch_roster_entry`, `update_roster_status`,
`read_roster_entry`, `transition_roster_status`, the hardcoded `"roster-service"`
actor id, and the public `RosterEntryCreate.status` input are deleted atomically
per proposal §WU-033 Repository/Service and Service §"Remove or rename" line,
with the `test_no_legacy_insert_roster_entry_remains` file-grep invariant pinning
the removal (`services/api/tests/test_roster.py:682-694`).

## 2. Findings

| # | Severity | File:Line | Description | Proposed fix / justification |
|---|---|---|---|---|
| F1 | LOW-MEDIUM | `services/discord/app/contracts/roster.py:30`; `services/discord/app/handlers/roster.py:187-188`; `services/discord/tests/test_roster_sync.py:132-152` | `RosterSyncEvent.ack_deferred: Any \| None = None` field, the handler's `if event.ack_deferred is not None: await event.ack_deferred()` call, and the `test_discord_handler_acks_deferred_before_api_calls` test are all net-new in implementation. Audit F9 (`plans/risk/slice-018-audit.md:70-74`) explicitly concluded "3-second budget does not apply" because `sync_roster` has no `InteractionEnvelope` parameter and is not wired to a slash command this slice. `.pipeline/implementation.md:53` discloses this as a deviation ("Added optional `ack_deferred` to `RosterSyncEvent` so `sync_roster` can satisfy the explicit phase constraint…"), but no AC, D-decision, or proposal line requires the field, no in-repo caller passes it, and the `Any \| None` typing defeats Pydantic contract discipline. This is designing for a hypothetical future caller, which the repo guidance explicitly forbids ("Don't design for hypothetical future requirements."). | Delete the field, the handler branch, and the test. The audit's F9 polish recommendation is a one-line anti-scope pin, not a field addition. If a future slice wires `sync_roster` to an interaction, it should add the `InteractionEnvelope` + `ack_deferred` shim at that slice with proper typing (`Callable[[], Awaitable[None]]`) rather than carrying an untyped optional here. **Not merge-blocking** (field is optional, defaults to `None`, no behavior change when unused), but should be removed before a downstream slice accidentally adopts the `Any`-typed shape. |
| F2 | LOW | `services/api/app/repositories/roster.py:160-168` `_touch_roster_entry` | Helper bumps `updated_at` on the roster row inside `record_roster_sync_failure`. Not named in proposal §WU-033 Repository (lines 170-189 list `_fetch_roster_entry`, `_fetch_roster_entry_for_update`, `_insert_roster_entry`, `_insert_roster_transition`, `_update_roster_entry`, `_fetch_chapter_role_for_update_or_validate`; no `_touch_*`). D9 says the sync-failure path "does not change `roster_entries.status` or `role_id`" but says nothing about `updated_at`. The `aggregate_heads` advance from `mutate_entity` is already the authoritative version bump for AC3; bumping `updated_at` without a status/role change is a plausible audit-ergonomics choice but is unjustified by the proposal, synthesis, or AC trace. | Either (a) drop the `_touch_roster_entry` call and let `updated_at` reflect only real status/role changes — the aggregate version still advances — or (b) pin in proposal §6 that sync-failure rows bump `updated_at` for observability. **Keep is acceptable** because the behavior is internally consistent and has no downstream contract impact, but it is a justification-chain gap. **Not merge-blocking.** |
| F3 | LOW | `services/api/app/repositories/roster.py:77-92` `_fetch_chapter_role_for_update_or_validate` | Helper name suggests conditional `FOR UPDATE`, but the SQL always uses `FOR UPDATE`. It is called both from the create path (`services/api/app/services/roster.py:116` via `_validate_role`) where a chapter-role row-lock is not semantically needed (we are not mutating `chapter_roles`), and from the transition path where it is. Proposal §Repository line 185-186 names this helper and says it "verifies the role belongs to the same chapter before insert or transition," which is validation, not locking. Taking a `FOR UPDATE` lock on `chapter_roles` during every roster create creates unnecessary contention with concurrent chapter-role writes (SLICE-013 territory). | Rename to `_fetch_chapter_role` and drop `FOR UPDATE`, OR split into `_fetch_chapter_role_for_validate` (no lock) used by create and `_fetch_chapter_role_for_update` (FOR UPDATE) used by transition. **Not merge-blocking** — the lock is brief and chapter-role writes are rare — but the name/behavior mismatch is an invitation for future drift. |
| F4 | LOW | `services/api/tests/test_roster.py:287-306` `test_create_roster_entry_duplicate_active_returns_409` | Audit F3 sub-risk (`plans/risk/slice-018-audit.md:35`) asked for `test_create_roster_duplicate_current_entry_returns_409_not_500` to pin the except-clause ordering so `UniqueViolation` is translated to 409 rather than leaking as 500. The committed test `test_create_roster_entry_duplicate_active_returns_409` covers the behavior but does not probe the 500-vs-409 boundary (e.g., does not assert the response body has `"code": "duplicate_current_roster_entry"` *and* no stack trace). | Tighten the assertion or add an explicit negative test that any non-`uq_roster__chapter_member_active` UniqueViolation would re-raise (currently handled by `_is_current_entry_unique_violation` at `services/api/app/services/roster.py:103-105`). **Not merge-blocking** — the test does assert the 409 code on line 306. |
| F5 | LOW | `services/api/app/services/roster.py:197-203` role-only transition semantics | Audit F12 flagged this: the D2 state matrix has no self-loops, so a `to_status == current_status` request with a different `to_role_id` is rejected with `InvalidRosterStatusTransitionError`. The implementation picks the reject-role-only-transitions branch without an explicit test. AC2 ("Status **and** role transitions create a RosterTransition record") is ambiguous on whether role-only transitions must be accepted. | Add a parametrized test making the rejection explicit (e.g., `test_role_only_transition_without_status_change_rejected_with_409`) or, if role-only is meant to be supported, allow `(s, s)` self-loops for roles while keeping `removed` terminal. **Not merge-blocking** — behavior is defensible and bounded by D2. |
| F6 | LOW | `services/discord/app/handlers/roster.py:38-40, 84-102` `_slug` + suffix matching | The role-name rediscovery uses a slug helper that lowercases, strips non-alphanumerics, and additionally accepts any role whose slugged name ends with `-{role_slug}`. Proposal §WU-034 Handler line 344-346 says "rediscover by deterministic role name using the same chapter resource naming substrate as SLICE-013 where available." SLICE-013 provisions roles as `{chapter-prefix}-{role_name}`, so the suffix match is consistent with that substrate, but neither the proposal nor any test fixes `_slug` as the substrate's actual function. The `_role_name_matches` short-circuit on `endswith(f"-{role_slug}")` could match unintended roles if two chapters' prefixes overlap in a single guild (unlikely today; possible in multi-chapter-per-guild setups). | Pin `_slug` to a named substrate helper (or reuse SLICE-013's if one exists and is exported) and document the intentional suffix-match scope. **Not merge-blocking** — single-guild-per-chapter is the current deployment assumption and AC4 tests assert the expected rediscovery. |

No MEDIUM or HIGH findings.

## 3. Trace matrix

Every non-trivial file → AC / D-decision / prior-slice / Revision-1 rationale.

### Migration

| File | Justification |
|---|---|
| `migrations/versions/wu-033_roster.py` | `down_revision = "wu_019_chapter_lifecycle"` — proposal §WU-033 Migration line 95-96. `updated_at`, `removal_metadata` columns — proposal §Migration lines 99-100. Chapter FK + composite `(chapter_id, role_id)` FK — **D6** cross-chapter transfer prevention + proposal lines 101-106. `uq_chapter_roles__chapter_id_id` — supports composite FK (proposal line 104); infra-only, no CRUD. `uq_roster__chapter_member_active` partial unique index — **D6** (synthesis.md:48-53) + **AC1**. `roster_transitions` table with `aggregate_seq` unique + FK to `chapters/chapter_roles` — **D3** (synthesis.md:27-34). `roster-syncer` global grant seed with `NOT EXISTS` guard — **D10** (synthesis.md:88-97) + audit F15 polish. `downgrade` deletes by match — audit F15 (`plans/risk/slice-018-audit.md:108-110`). |

### API contracts

| File | Justification |
|---|---|
| `services/api/app/contracts/roster.py` `RosterStatus` | **D2** (synthesis.md:18-26) 4-valued state. |
| `RosterEntryRead` + `version`, `updated_at`, `removal_metadata` fields | **D1** (synthesis.md:10-16) version via `aggregate_heads`; proposal §Contracts line 138-141. |
| `RosterEntryCreate` (drops public `status`) | **D2** + **D6** + proposal §Contracts line 142-145 ("Creation always writes `status='active'` server-side"). Scope risk §9 flags this as *necessary* (D2 + D6). |
| `RosterEntryTransitionRequest` | **D2/D3** transitions + **D7** removal permission + **D11** originating actor; proposal §Contracts lines 146-152. |
| `RosterSyncFailureRequest` | **D9** deferred-effect enqueue + **D10** service actor + **D11** originating actor; proposal §Contracts lines 153-162. |
| Typed errors `RosterEntryNotFoundError`, `RosterRoleChapterMismatchError`, `RosterDuplicateCurrentEntryError` | **D8** typed-error discipline from SLICE-010/011 + proposal §Contracts lines 163-168. `RosterRoleNotFoundError`, `InvalidRosterStatusTransitionError` — preserved from foundation (proposal §Preserved line 408). |

### API repositories

| File | Justification |
|---|---|
| `services/api/app/repositories/roster.py` `_ROSTER_ENTRY_SELECT` joining `aggregate_heads` | **D1** version resolution pattern from `services/api/app/repositories/chapters.py` (SLICE-013); proposal §Repository line 174-175. |
| `_fetch_roster_entry`, `_fetch_roster_entry_for_update` | **D1/D3** read and lock patterns; proposal §Repository lines 176-179. |
| `_insert_roster_entry` (status hard-coded `'active'`) | **D2** terminal states + **D6** uniqueness; proposal §Service line 193. |
| `_insert_roster_transition` | **D3** projection row shape mirroring `chapter_transitions`; proposal §Repository line 180-181. |
| `_update_roster_entry` | **D3** transition projection updates aggregate row in same tx; proposal §Repository line 182-184. |
| `_fetch_chapter_role_for_update_or_validate` | **D4** `chapter_roles.id` as roster identity anchor + cross-chapter transfer prevention; proposal §Repository lines 185-186. *See F3 for naming concern.* |
| `_touch_roster_entry` | *Unjustified — see F2.* Used to bump `updated_at` in sync-failure. No AC/D-decision or proposal line. |

### API services

| File | Justification |
|---|---|
| `services/api/app/services/roster.py` `VALID_TRANSITIONS` | **D2** state matrix; foundation `_validate_roster_transition` is replaced by the inline set+helper pattern paralleling `chapters.py` VALID_TRANSITIONS (preserved semantics per proposal §Preserved line 410-412). Shortcut §3 flags no parallel validator. |
| `_make_request(..., actor, ...)` | Replaces hardcoded `actor_kind="system", actor_id="roster-service"` from foundation — shortcut §2 (`plans/risk/slice-018-shortcut.md:40-54`) + proposal §Service rename line 238-240. |
| `create_roster_entry(db, request, actor)` | **AC1** + **D1** `mutate_entity(expected_version=0)` + **D7** chapter scope + **D6** duplicate → `RosterDuplicateCurrentEntryError`; proposal §Service lines 192-200. `_validate_role` inside the projection — **D4**. |
| `get_roster_entry` | **AC3** ETag from version + **D1** version join; proposal §Service lines 201-203. |
| `transition_roster_entry(..., expected_version)` | **AC2/AC3** + **D2/D3/D4/D11**: fetch FOR UPDATE, validate matrix, composite role validation, aggregate_seq = expected_version+1, transition row with originating actor, same-tx update. Proposal §Service lines 204-219. |
| `_enqueue_roster_sync_retry` | **D9** atomic enqueue on same connection + idempotency key `roster_sync_retry:{roster_entry_id}:{transition_id}` + `consequence_level="consequential"`. `get_current_audit_context()` raise-if-missing — audit F17 polish (`plans/risk/slice-018-audit.md:116-118`) + parallel to `services/api/app/services/chapters.py::_enqueue_failed_provisioning_effect`. Proposal §Service lines 220-237. |
| `record_roster_sync_failure` | **AC4** + **D9/D10/D11**: runs through `mutate_entity` for `roster_entry` aggregate at `scope_kind="global", scope_id=None`, enqueues effect inside projection, does not change status/role. Proposal §Service lines 220-236. |

### API endpoints

| File | Justification |
|---|---|
| `services/api/app/api/v1/endpoints/roster.py` router mount | Ticket §Technical Specification (§19-30); proposal §Endpoints line 242. |
| `_parse_if_match`/`_set_etag` | Mirrors `services/api/app/api/v1/endpoints/chapters.py:39-51` — SLICE-010/011 OCC pattern; proposal §Endpoints line 253-254. |
| `_user_actor_only` / `_service_actor_only` | **D7** operator endpoints user-only + **D10** sync-failure service-only (revision 1 resolution of audit F1); proposal §Endpoints lines 243-250, 277-286. |
| `POST /api/v1/roster-entries` | **AC1** + **D7** body-derived chapter scope; proposal §Endpoints lines 255-261. |
| `GET /api/v1/roster-entries/{id}` | **D7** fetch-first-then-authorize (since `RequireAuthority` is path-only); proposal §Endpoints lines 262-268. |
| `POST /{id}/transitions` | **AC2/AC3** + **D7** fetch-then-authorize with `roster.remove` gating on `to_status == "removed"`; proposal §Endpoints lines 269-276. |
| `POST /{id}/sync-failure` | **AC4** + **D8/D9/D10** Revision-1 authority split; proposal §Endpoints lines 277-286. `RequireAuthority("roster.write", "global")` matches D10 global grant. |
| `_raise_for_roster_error` | **D8** typed error → HTTP status mapping + proposal §Endpoints + SLICE-010/011 pattern. |

### API router + conftest

| File | Justification |
|---|---|
| `services/api/app/api/v1/router.py` (+2 lines `roster` import/mount) | Required by ticket Technical Specification endpoints. |
| `services/api/tests/conftest.py` (+1 line `roster_transitions` in `GOVERNANCE_TABLES`) | Required by wu-033 migration; clean-up between test cases. |

### Discord contracts

| File | Justification |
|---|---|
| `services/discord/app/contracts/roster.py` `RosterSyncEvent` fields | Each extra field traces to a D-decision (scope §3 inventory): `roster_entry_version` (**D1/AC3**), `transition_id` (**D9** idempotency key), `chapter_id` (audit/handler context), `member_id`+`member_discord_user_id` (**D5** — no member FK), `chapter_role_name`+`chapter_discord_role_id`+`chapter_discord_resources` (**D4** resolution chain), `status` (**D8** add/remove decision), `originating_actor_kind`+`originating_actor_id` (**D11**), `reason` (**D11** audit), `correlation_id` (audit/tracing). |
| `RosterSyncEvent.ack_deferred` | *Unjustified — see F1.* No AC/D-decision/proposal line. |
| `RosterSyncResult` | **D8** idempotency observability (`skipped_role_ids`) + **D9** 412-case (`failure_recorded=False`). Proposal §Contracts (WU-034) lines 322-328. |

### Discord handler

| File | Justification |
|---|---|
| `services/discord/app/handlers/roster.py` `SERVICE_ACTOR_HEADERS = {"X-Actor-Kind": "service", "X-Actor-Id": "roster-syncer"}` | **D10** (synthesis.md:88-97) + proposal §Handler lines 332-334. |
| `_resolve_member` (cached → get_member → fetch_member fallback) | Proposal §Handler lines 337-339; D8 failure taxonomy on `NotFound`/`HTTPException`. |
| `_resolve_role` (chapter_discord_role_id → resources role_ids → name rediscovery) | **D4** resource chain + proposal §Handler lines 340-348 + audit F7 stale-ID test. |
| `_slug` / `_role_name_matches` | **D4** rediscovery by deterministic name — proposal §Handler line 344-346. *See F6 for substrate-pinning gap.* |
| `_has_role` idempotency branches | **D8** (synthesis.md:67-75); proposal §Handler lines 349-352. |
| `_reason` format | **D11** includes roster_entry_id, transition_id, originating_actor. Proposal §Handler line 353. |
| `_record_sync_failure` → `POST /sync-failure` with SERVICE_ACTOR_HEADERS + `If-Match` | **D9** API-owned enqueue + **D10** service actor + **D11** originating actor; proposal §Handler lines 354-358. |
| `except (Forbidden, NotFound, HTTPException)` + `RosterSyncFailure` | **D8** (synthesis.md:67-75); proposal §Handler lines 354-356. |
| `ack_deferred` call | *Unjustified — see F1.* |

### Tests

| File | Justification |
|---|---|
| `services/api/tests/test_roster.py` `test_create_roster_entry_in_active_state`, `test_create_roster_entry_requires_roster_write_permission_chapter_scope` | AC1 trace (proposal §AC Trace lines 437-441). |
| `test_create_roster_entry_duplicate_active_returns_409` | D6 + audit F3 sub-risk (proposal §F3 mapping). *See F4 for assertion tightness.* |
| `test_transition_creates_roster_transition_row_with_actor`, `test_transition_records_reason_and_originating_user`, `test_transition_allowed_state_pairs`, `test_transition_disallowed_state_pairs_return_409`, `test_removed_is_terminal` | AC2 trace (proposal §AC Trace lines 443-448). |
| `test_transition_with_current_version_succeeds`, `test_transition_with_stale_version_returns_412`, `test_get_roster_entry_returns_version_and_etag` | AC3 trace (proposal §AC Trace lines 452-454). |
| `test_sync_failure_enqueues_deferred_effect_atomically`, `test_sync_failure_idempotency_key_per_transition`, `test_sync_failure_preserves_roster_entry_state`, `test_sync_failure_rejects_non_service_actors_with_403`, `test_sync_failure_accepts_roster_syncer_service_actor_with_global_grant` | AC4 trace + Revision-1 authority split (proposal §AC Trace lines 457-463). |
| `test_partial_unique_index_allows_one_active_per_chapter_member` | D6 invariant (proposal §Invariants line 469). |
| `test_roster_syncer_service_actor_grants_seeded` | D10 migration invariant (proposal §Invariants line 470). |
| `test_no_legacy_insert_roster_entry_remains` | File-grep invariant matching proposal §Service "Remove or rename" line 238-240; shortcut §1 (`plans/risk/slice-018-shortcut.md:19-38`). Implementation deviation from proposal's `test_no_legacy_roster_in_memory_remains` name — per scope §9 minor observation, no in-memory roster substrate ever existed; the grep-probe form is the correct concrete test. |
| `services/discord/tests/test_roster_sync.py` `test_discord_handler_calls_sync_failure_on_forbidden`, `test_discord_handler_rediscovers_role_id_by_name` | AC4 trace (proposal §AC Trace lines 464-465). |
| `test_discord_handler_acks_deferred_before_api_calls` | *Unjustified — see F1.* No AC or D-decision. Tests a capability that is not used by any in-repo caller. |

### Anti-scope confirmation (D12)

Spot-checked against scope §2 and §10:

- No `triggers_succession` consumer wired — `chapter_roles.triggers_succession` is read-only in the seed fixture (`services/api/tests/test_roster.py:112,153`), never read by roster services. **SLICE-024 boundary preserved.**
- No archival state / `RosterStatus` remains 4-valued (`services/api/app/contracts/roster.py:10`). **Roster archival not added.**
- No cross-chapter transfer — `_update_roster_entry` has no `chapter_id` parameter (`services/api/app/repositories/roster.py:139-157`), and the composite FK forbids role swaps across chapters. **Cross-chapter transfer blocked.**
- No bulk-import endpoint / no CSV parser / no succession service module. **Bulk import, succession absent.**
- No per-role authority auto-sync — the only `authority_grants` write in wu-033 is the `roster-syncer` seed. **Auto-sync absent.**
- No member FK on `roster_entries.member_id` — migration does not add one; **D5** preserved.
- No deferred-effect worker for roster — only `enqueue_effect`; no worker registration; no `precondition_validator`. **Worker deferral preserved.**

## 4. Sanity probes for "deferred stubs"

Grepped the PR for `TODO`, `NotImplementedError`, `...`-only function bodies, `pass  #`, `raise NotImplementedError`. None found in production code. `.pipeline/implementation.md` is the only doc that references deferrals, and those are scope boundaries (retry worker, reconciliation slice) disclosed in proposal §2.

## 5. "Non-trivial file" coverage checklist

| File in diff | Traced? |
|---|---|
| `migrations/versions/wu-033_roster.py` | ✅ |
| `services/api/app/api/v1/endpoints/roster.py` | ✅ |
| `services/api/app/api/v1/router.py` | ✅ |
| `services/api/app/contracts/roster.py` | ✅ |
| `services/api/app/repositories/roster.py` | ✅ (F2 for `_touch_roster_entry`; F3 for `_fetch_chapter_role_for_update_or_validate` naming) |
| `services/api/app/services/roster.py` | ✅ (F5 for role-only transition semantics) |
| `services/api/tests/conftest.py` | ✅ |
| `services/api/tests/test_roster.py` | ✅ (F4 for duplicate-vs-500 test tightness) |
| `services/api/tests/test_roster_foundation.py` (deleted) | ✅ (F16 audit + shortcut §1) |
| `services/discord/app/contracts/roster.py` | ✅ (F1 for `ack_deferred`) |
| `services/discord/app/handlers/roster.py` | ✅ (F1 for `ack_deferred`; F6 for `_slug`) |
| `services/discord/tests/test_roster_sync.py` | ✅ (F1 for `ack_deferred` test) |
| `.pipeline/implementation.md`, `.pipeline/proposal.md`, `.pipeline/synthesis.md`, `.pipeline/research.md`, `plans/risk/slice-018-*.md` | Planspace — informational, not production code. |

## 6. Merge recommendation

**Merge allowed under `LOW_CONCERN`.**

Non-blocking polish to absorb before SLICE-019/020/021 open:

1. **F1** — Delete `ack_deferred`-related additions in the Discord contract, handler, and test; replace with a one-line anti-scope pin per audit F9 polish recommendation. If a reviewer prefers to keep the hook, replace `Any | None` with `Callable[[], Awaitable[None]] | None` and add a comment that the field is a reserved seam for SLICE-019+.
2. **F2** — Decide `_touch_roster_entry`: either drop it or pin in proposal §6 that sync-failure bumps `updated_at` for audit ergonomics.
3. **F3** — Split `_fetch_chapter_role_for_update_or_validate` into validate/for-update variants, or rename + drop `FOR UPDATE` on the create path.
4. **F4** — Tighten `test_create_roster_entry_duplicate_active_returns_409` assertion per audit F3 sub-risk (`"code": "duplicate_current_roster_entry"` on the 409 body).
5. **F5** — Add an explicit `test_role_only_transition_rejected_with_409` (or whichever branch is intended) to pin audit F12.
6. **F6** — Name the `_slug` substrate and pin its intended scope (single chapter per guild) in WU-034 tradeoffs §4.

No HIGH findings. No merge block.
