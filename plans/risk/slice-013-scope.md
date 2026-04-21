# SLICE-013 Scope Risk: **LOW**

Rating: **LOW** — the proposal delivers the 4 ACs, keeps anti-scope items out, and the two scope expansions beyond the minimal ticket shape (an extra PATCH endpoint, and in-place deletion of the legacy in-memory chapter substrate) are both explicitly called out and justified against concrete correctness problems, not opportunistic refactors.

## Prompt calibration note

The task template mentions scheduler-era concerns — WU-008A/B, `services/api/app/tasks/__init__.py`, `DegradedStateSummaryRead(subsystem, pending_effect_count)`, handler-registry DB tables, Phase 0 scheduler, and the anti-scope line "API endpoints: none; Discord: none". None of that applies to SLICE-013. SLICE-013 is chapter provisioning; the ticket explicitly enumerates 6 API routes + 1 Discord handler, and the AI roadmap's WU-018/019/020 contracts match. This assessment is framed against SLICE-013's real 4 ACs, not the scheduler slice.

## SLICE-013 ACs (ticket)

1. Template create/update persists channel and role structure and rejects stale updates with `412 Precondition Failed`.
2. Creating a chapter returns `proposed` state and the selected template reference.
3. Provisioning moves `proposed -> provisioning -> active` only after verified Discord resource IDs are persisted through the API.
4. A failed Discord provisioning step queues a consequential deferred effect instead of partially marking the chapter active.

## Findings

### 1. AC trace is complete and testable

| AC | Named tests | Source |
|---|---|---|
| AC1 | POST v1; PATCH inserts new family version; stale `expected_current_version` → 412; two concurrent PATCHes → one accept + one 412 (no 500); PATCH without actor/authority headers → 403; `schema_version` still enforced. | `test_chapter_templates.py` (proposal §3 WU-018 tests, §7 AC1). |
| AC2 | POST returns `state="proposed"`, selected `template_id`, `template_snapshot` deep-copied, empty structured `discord_resources`, `version=1`, ETag; later template edits do not alter existing snapshots. | `test_chapter_lifecycle.py` (proposal §3 WU-019 tests, §7 AC2). |
| AC3 | Full transition matrix covered; `test_transition_to_active_rejects_when_discord_resources_missing_{category|role|channel}`; incremental PATCH merges across calls; `If-Match` 412/428; handler asserts API call order and service-actor headers; `test_discord_handler_rediscovers_role_by_name_after_patch_failure`; `test_provision_chapter_handler_acks_deferred_before_api_calls`. | `test_chapter_lifecycle.py`, `test_chapter_provisioning.py` (proposal §3 WU-019+WU-020 tests, §7 AC3). |
| AC4 | Failed transition inserts one consequential deferred effect with `precondition_state="unchecked"` and idempotency key `chapter_provision_retry:{chapter_id}:{chapter_transition_id}`; chapter stays non-active; `test_retry_transition_from_provisioning_failed_to_provisioning`; partial-failure path persists ids via `PATCH /discord-resources` before posting failure. | `test_chapter_lifecycle.py`, `test_chapter_provisioning.py` (proposal §3, §7 AC4). |

No AC is missing a direct test path.

### 2. Anti-scope items from synthesis D12 are absent

| D12 item | Proposal coverage |
|---|---|
| No post-provision editing / template swaps / name changes | Explicit in §2 anti-scope; no PATCH route for chapter names or template swaps. |
| No archive state / `archived_at` / teardown | `ChapterState` literal is 4-valued; migration omits `archived_at`; proposal revision 2 explicitly removed archive scope (§6); SLICE-023 ownership called out. |
| No roster management | Not touched. |
| No template-family permission model | All uses `chapter_template.{read,write}` global; no per-version grant. |
| No retry worker / deferred-effect handler | §2 "Deferred effect enqueue only … defers the handler/worker implementation"; WU-019 only enqueues via repository-level `enqueue_effect(connection=...)` inside the same mutation transaction; no worker code anywhere. |
| No multi-guild / multi-tenant | Not referenced; single `DiscordSettingsRead.guild_id` reused. |
| No new third-party deps | Uses existing SLICE-006 `ApiClient` and existing `discord.py`. |

### 3. Deviations from the AI roadmap / ticket are explicitly noted

The ticket enumerates 6 API routes + 1 Discord handler. The proposal ships 7 + 1. The +1 route is `PATCH /api/v1/chapters/{chapter_id}/discord-resources`.

- §1 endpoint-count note explicitly flags this: "Phase 4 risk review adds one AC3-required incremental persistence route, so this proposal now defines seven route operations".
- Rationale is AC3 — "verified Discord resource IDs are persisted through the API" has to mean "before the final active transition", otherwise a mid-sequence Discord failure would lose partial IDs (prototype findings lines 5–14: capture must be append-as-you-go, not on-success).
- The alternative is worse: either (a) overload the `POST /transitions` request body with a resource patch (forces spurious `provisioning → provisioning` self-transitions to avoid losing IDs mid-run), or (b) flush all IDs only at the final active transition (loses partial IDs on any intermediate failure — violates D5 idempotency and AC4 partial-resource persistence).

The ticket's schema list also includes `Chapter.archived_at?`. The proposal drops it entirely. This is called out in §6 resolved pins and §2 anti-scope with explicit SLICE-023 hand-off.

Both deviations are scoped and justified in the proposal body, not silent.

### 4. Legacy substrate replacement — expanded scope, but justified

Revision 3 adds explicit deletion of the legacy in-memory chapter substrate: `InMemoryChapterRepository`, `ChapterService` action/state-change store wiring, integer-id contracts, `ChapterStatus` enum, and `/archive` route — all replaced in place inside WU-019.

This IS scope expansion beyond "add new provisioning code", but the proposal §2 and §5 document the correctness reason rather than treating it as a style cleanup: leaving the legacy code in place would produce two `GET /api/v1/chapters/{chapter_id}` routes with incompatible id types (integer vs UUID string), duplicate `app.state.chapter_service`, and mixed `aggregate_type="chapter"` id forms in `activity_actions` — actual correctness bugs, not aesthetics. The proposal encodes this as post-implementation grep invariants (§3 WU-019 tests: `InMemoryChapterRepository` → 0, `ChapterStatus` → 0, `class ChapterRecord` → 0, `/archive` under `/api/v1/chapters` → 0, integer `chapter_id` paths → 0).

This is the right call — deleting in-place is less scope risk than parking parallel code. Flagged here for visibility; not a severity escalation.

### 5. Deferred-effect scope is enqueue-only

- §2: "Deferred effect enqueue only. D6 ... defers the handler/worker implementation".
- §5: "no worker implementation belongs in this slice".
- §6 pins `effect_type="chapter_provisioning_retry"` and the deterministic idempotency key.
- Only touch point is repository-level `enqueue_effect(connection=...)` inside the same `mutate_entity()` transaction — reuses SLICE-004 substrate, adds no new primitives.
- Prototype findings (lines 27–35) confirm the atomicity is shape-proven; proposal uses the right connection-threading seam.

### 6. Handler-registry scope is existing substrate

WU-020 reuses `InteractionRegistry` + `HumilityBot.register_interaction_handler` from SLICE-006. No new dispatch framework, no handler-registration DB table, no scheduler loop. The only widening is extending the SLICE-006 `ApiClient` seam to propagate actor headers (`X-Actor-Kind: service`, `X-Actor-Id: discord-provisioner`), which is necessary plumbing, not a new abstraction.

The Discord deferred-ack seam is added because the current `HumilityBot.dispatch_interaction(...)` responds only after the handler returns (proposal §3 WU-020, lines 372). A chapter provisioning run routinely exceeds Discord's 3-second interaction window, so deferred-ack is a correctness prerequisite for WU-020, not a cross-cutting refactor. Scoped narrowly to `handlers/chapters.py`.

### 7. Template versioning resolution is narrowly scoped

D1's template-family versioning stays minimally invasive:

- Additive columns only (`template_family_id UUID`, `version BIGINT`) on an existing table; nullable → backfill → NOT NULL migration split.
- `schema_version INT` is untouched; SLICE-003's content-shape contract remains intact.
- In-place mutation surface stays forbidden; PATCH inserts a new row in the same family.
- Existing `test_chapter_template_foundation.py` is additive-only per §5 — the old immutability assertion is revised to "no in-place update surface" while accepting PATCH-as-new-version.
- `pgcrypto` extension creation (Step 0 of the migration) is a minor new dep on Postgres but does not introduce a Python third-party dep.

Minor note: the proposal introduces `fetch_chapter_template_for_update` and `fetch_current_template_family_version_for_update` as separate helpers. A simpler design would fold them. Code-quality nit, not scope.

### 8. Ambiguous/minor expansions reviewed

| Proposal element | Verdict |
|---|---|
| `_verify_provisioning_complete` strict completeness (category + every template role + every template channel) | **In-scope.** AC3's "verified Discord resource IDs" reasonably means "complete against the template snapshot"; a partial map would let active fire with missing channels. Hardening added in revision 2. |
| `DiscordSettingsRead.required_bot_permissions` field | **In-scope per D9.** Documented metadata; boot-time validation is optional; handler-level preflight is required before visible Discord writes. No new env var. |
| `originating_actor_kind` / `originating_actor_id` on request bodies | **In-scope per D8 + D11.** Service actor calls the API; original Discord user preserved for audit. Deliberately NOT user federation — that is a later slice. |
| Denormalized `chapter_transitions` projection table | **In-scope per D10.** Written in the same `mutate_entity()` transaction; `activity_actions` remains authoritative. §4 tradeoffs and §5 "activity_actions wins" make the canonical-source ordering explicit. |
| Discord provisioner service-actor grant seeded in `wu-019_chapters` migration | **In-scope and necessary.** Without the grant, every WU-020 API call 403s. Migration uses the actual `authority_grants` JSONB schema (grep-verified). Scope is narrow: one global non-expiring grant for `grantee_id='discord-provisioner'`. |
| Name-based rediscovery after lost `PATCH /discord-resources` | **In-scope per D5.** Resilience for AC3 when partial-resource persistence fails mid-run; proposal flags that slug derivation must be stable and collision-resistant within a guild. |
| Role hierarchy / voice channels / role ordering / `edit_role_positions` | **Correctly deferred.** Prototype-flagged; not shipped in SLICE-013. |

### 9. No scope leakage into downstream slices

| Downstream | Would depend on | Present in proposal? |
|---|---|---|
| SLICE-018 roster management | chapter lifecycle | No roster code. |
| SLICE-020 temporary permissions | chapter resources | No temporary-permission code. |
| SLICE-022 compliance | chapter state | No compliance eval code. |
| SLICE-023 chapter archival | archive state/teardown | Explicitly excluded. |
| SLICE-024 leadership succession | chapter context | Not touched. |

## Summary table

| Risk category | Severity | Notes |
|---|---|---|
| Bundles downstream work (SLICE-018 / SLICE-020 / SLICE-022 / SLICE-023 / retry worker) | None | All explicitly excluded per D12 and anti-scope §2. |
| Missing AC test path | None | All 4 ACs have named tests per §3 and §7. |
| Silent deviation from AI roadmap | None | +1 endpoint and `archived_at` drop both flagged in §1, §2, §6. |
| Premature abstraction / speculative scaffolding | None meaningful | Minor: two template-family lookup helpers could fold to one. |
| Over-scoped handler (executing deferred effect) | None | Only enqueues; no worker code anywhere. |
| Over-scoped template permissions | None | Family shares one permission; no per-version authority. |
| Over-scoped Discord identity federation | None | Service actor mapping is deliberately narrow; operator carried in audit only. |
| Scope leakage into operator UI | None | No UI work proposed. |
| Legacy substrate deletion (in-place rewrite) | Low | Scope expansion beyond net-new code, but justified by real correctness problems (duplicate routes, incompatible id types). Post-impl grep invariants lock it down. |

## What LOW requires (already met)

1. Each AC has at least one direct test — **yes**.
2. Anti-scope items (D12) absent from proposal body — **yes**.
3. Any deviation from AI roadmap / ticket endpoint list is explicitly noted with rationale — **yes** (§1 endpoint-count note, §6 resolved pins, §2 anti-scope for archive).
4. No deferred-effect handler or worker shipped in this slice — **yes**.
5. No archive state, archival column, or teardown — **yes**.
6. No roster, multi-guild, or per-version permission expansion — **yes**.
7. Legacy substrate deletion is scoped with grep invariants and justified by correctness, not aesthetics — **yes** (§2, §5, §3 WU-019 grep invariants).

No scope reductions or additions are required. The proposal is right-sized for the 4 ACs and every expansion beyond the minimal ticket shape has explicit rationale.
