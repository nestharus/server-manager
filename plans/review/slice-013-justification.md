# SLICE-013 Phase 8 — Opus Justification Review (PR #39)

Reviewed: 2026-04-20
PR: `feat/slice-013-chapter-provisioning` (#39)
Branch: `feat/slice-013-chapter-provisioning` @ aeecd5e
Inputs: `.pipeline/synthesis.md` (D1–D12), `product-strategy/tickets/SLICE-013.md`
(AC1–AC4), `.pipeline/proposal.md` rev 3, `plans/risk/slice-013-audit.md`,
`plans/risk/slice-013-scope.md`, `plans/risk/slice-013-shortcut.md`,
`git diff 96497c6..HEAD`.

## 1. Verdict

**`LOW_CONCERN`** — no HIGH findings. Every non-trivial file traces to an
AC / D-decision / prior-slice decision / explicit Revision-3 rationale. The
three LOW findings below are minor hygiene items that do not block merge.

No scope creep: no endpoint, column, or contract field exists outside the
AC/D trace. No deferred stubs (`TODO`, `NotImplementedError`, placeholder
`pass`). No backwards-compatibility shims (legacy `InMemoryChapterRepository`,
`ChapterStatus`, integer chapter id, `/archive` route all deleted atomically
per Revision-3 §2). No magic values outside D-decisioned constants
(`chapter_provision_retry:` prefix is explicitly in synthesis D6; service
actor id `discord-provisioner` is explicitly in synthesis D2 and seeded by
migration).

## 2. Findings

| # | Severity | File:Line | Description | Proposed fix / justification |
|---|---|---|---|---|
| F1 | LOW | `services/api/app/repositories/chapter_transitions.py:45-60` | `list_chapter_transitions` is defined but has zero production callers; no test currently exercises it. Proposal line 248 permits helper-style repo functions "allowed only if tests need direct verification" — that condition is not met at merge time. | Either delete, or add the direct-verification test the proposal gates it on. Leave-as-is is acceptable under SLICE-013 scope only if a follow-up test is committed before SLICE-014 opens, since audit/ledger features in later slices will likely need it. **Not merge-blocking.** |
| F2 | LOW | `services/discord/app/contracts/chapters.py:8-34` | `ProvisioningStep` literal and `ChapterProvisionResult` model are defined and re-exported but never imported outside this file. `provision_chapter_handler` returns `InteractionResult`, not `ChapterProvisionResult`. `ChapterProvisioningError` is the only live consumer of `ProvisioningStep`. The `"ack"` and `"transition_failed"` step values in the literal are unreferenced. | SLICE-013 ticket Deliverables §Discord lists a `ChapterProvisionResult` with step/failed_step as the intended handler return type. The current handler deviates — it swallows errors into `InteractionResult.success=False` with free-text `response_text`. Either (a) make the handler return `ChapterProvisionResult` to match the ticket, or (b) delete the unused contract. Keeping both the unused contract *and* the ticket-divergent handler signature is the worst option. **Recommended: (b) delete** — the `InteractionResult` shape is adequate for AC2 ("failures logged via state change"). **Not merge-blocking** because AC2 is still satisfied by the ledgered `provisioning_failed` transition. |
| F3 | LOW | `services/api/app/repositories/chapter_templates.py` `insert_template_version` | Thin alias around `insert_chapter_template` with exactly one caller (`patch_chapter_template`). Marginal abstraction. | Justifiable under Revision-3 §3 (distinct semantic intent: "insert_chapter_template" = create root of family, "insert_template_version" = add version to existing family) and the one-level-of-indirection keeps the PATCH service call site readable. **Keep.** No action required. |

No MEDIUM or HIGH findings.

## 3. Trace matrix

Every non-trivial file → AC / D-decision / prior-slice / Revision-3 rationale.

### Migrations

| File | Justification |
|---|---|
| `migrations/versions/wu-018_chapter_templates.py` | **D9** (copy-on-instantiate via versioning) + **Rev-3 §1** (template family columns resolve SLICE-003 D9 immutability vs AC1 PATCH). Adds `template_family_id` + `version`, `uq_chapter_templates__family_version` backstop for race (synthesis D9 §"atomicity"). Backfill `template_family_id = id, version = 1` is the only semantically correct identity for pre-existing rows (any new UUID would orphan them from themselves). |
| `migrations/versions/wu-019_chapter_lifecycle.py` | **AC2** (chapters table + state machine), **D10** (`state CHECK IN (...)`, `uq_chapters__name LOWER(name)`, `chapter_transitions` ledger), **D11** (template_snapshot JSONB copy-on-instantiate), **D12** (discord_resources JSONB). Seeds `discord-provisioner` authority grants — **D2**. Idempotent `NOT EXISTS` guard addresses audit F6c; downgrade deletes the seeded grant addresses audit F6c. |

### API contracts

| File | Justification |
|---|---|
| `services/api/app/contracts/chapter_templates.py` — `template_family_id`, `version` fields on `ChapterTemplateRead` | **D9** + **Rev-3 §1**. `expected_current_version` on `ChapterTemplatePatch` — **AC1** optimistic concurrency. `StaleTemplateVersionError`, `TemplateSchemaVersionMismatchError` — typed errors required by **D8** (typed-error discipline from SLICE-010/011). `ChapterTemplatePatchEmptyError` — **AC1** "PATCH must mutate ≥1 field" (validated via `validate_patch`). |
| `services/api/app/contracts/chapters.py` — `ChapterState` literal, `ChapterCreate`, `ChapterRead`, `ChapterResourcesPatchRequest`, `ChapterTransitionRequest` | **AC2** (4-state machine), **AC3** (transitions), **AC4** (resource PATCH). `ChapterId = str` — **D5** (chapter aggregate keyed by uuid4 string, replacing legacy integer). `IncompleteProvisioningError(missing)` — **D7** (strict provisioning gate). `ChapterDuplicateNameError` — implicit from **D10** `uq_chapters__name` constraint; typed-error pattern from **D8**. `InvalidChapterTransitionError` — **D10** enforced set of allowed transitions. |

### API services

| File | Justification |
|---|---|
| `services/api/app/services/chapter_templates.py` `create_chapter_template` | **AC1** (POST), uses **SLICE-011** `mutate_entity(...)`. `template_family_id = template_id, version = 1` seeding — **D9**. |
| `services/api/app/services/chapter_templates.py` `patch_chapter_template` | **AC1** (PATCH), **D9** immutable-by-family-version (inserts new row with new `id` but same `template_family_id`, `version = current+1`). `fetch_current_template_family_version_for_update` + `IntegrityError→412` catch — **D9** race backstop (Rev-3 §1 concurrency rationale). |
| `services/api/app/services/chapters.py` `create_chapter` | **AC2** (POST creates `proposed`). `payload_allowlist = set(request.model_dump(mode="json").keys())` — **SLICE-011** mutate_entity contract. Snapshot clone of template into `template_snapshot` — **D11**. |
| `services/api/app/services/chapters.py` `transition_chapter` + `VALID_TRANSITIONS` | **AC3** (4 valid transitions, reject others with 409). `_verify_provisioning_complete` gate on `→ active` — **D7** (category + all roles + all channels). Deferred effect enqueued on `→ provisioning_failed` inside the projection callback with idempotency key `chapter_provision_retry:{chapter_id}:{chapter_transition_id}` — **D6** (deterministic retry key) + **SLICE-007** atomic enqueue. |
| `services/api/app/services/chapters.py` `patch_chapter_discord_resources` | **AC4** (PATCH `/discord-resources`). Shallow-merge of `role_ids`/`channel_ids`, `category_id` only replaced when non-null — **D12** (append-as-you-go persistence). |

### API endpoints

| File | Justification |
|---|---|
| `services/api/app/api/v1/endpoints/chapter_templates.py` POST/GET/PATCH | **AC1**. Authority scopes `chapter_template.read`/`chapter_template.write` — **D1**. Error mapping (`404`/`412`/`409`) — **D8**. |
| `services/api/app/api/v1/endpoints/chapters.py` POST/GET/POST-transitions/PATCH-discord-resources | **AC2/AC3/AC4**. `If-Match` required on mutating routes (`428`/`400`/`412`) — **SLICE-010/011** optimistic concurrency contract. Authority scope `chapter.write` — **D1**. `chapter.read` on GET — **D1**. Error mapping — **D8**. |
| `services/api/app/api/v1/router.py` mount | Routes required by **AC1–AC4**. |

### API repositories

| File | Justification |
|---|---|
| `services/api/app/repositories/chapter_templates.py` adds `fetch_chapter_template_for_update`, `fetch_current_template_family_version_for_update`, `fetch_latest_template_family_version_for_update`, `insert_template_version` | **D9** (FOR UPDATE locking on family rows before computing next version number; race-free version bump). |
| `services/api/app/repositories/chapters.py` `insert_chapter`, `fetch_chapter`, `fetch_chapter_for_update`, `update_chapter_state`, `merge_chapter_discord_resources` | **AC2/AC3/AC4**. Legacy in-memory repo replaced atomically — **Rev-3 §2** (coupled delete required because both old and new claim `aggregate_type="chapter"` and the same route paths). `_CHAPTER_SELECT` joins `aggregate_heads` — **SLICE-011** projection/version pairing. |
| `services/api/app/repositories/chapter_transitions.py` `insert_chapter_transition` | **AC3** (transition ledger row). `list_chapter_transitions` — flagged **F1**. |

### Discord

| File | Justification |
|---|---|
| `services/discord/app/handlers/chapters.py` `provision_chapter_handler` | **AC2/AC3/AC4** end-to-end flow. `SERVICE_ACTOR_HEADERS = {"X-Actor-Kind":"service","X-Actor-Id":"discord-provisioner"}` — **D2**. `ack_deferred()` invoked before first API call — **D3** (3s window). Short-circuit when state ∈ {`provisioning`,`active`} — **D4** (no double-provision). `derive_resource_names` deterministic slug — **D5** (rediscovery keying). Category→roles→channels sequence with PATCH-after-each — **D12**. Category-scoped channel rediscovery — CodeRabbit fix aeecd5e / audit F15. `check_required_bot_permissions` — **D9b** (bot capability preflight). On failure, POST `provisioning_failed` transition — **AC2** (failures must ledger). |
| `services/discord/app/commands/chapters.py` `register_chapter_commands` | Glue for the command registration; only ticket-listed command name `provision_chapter`. |
| `services/discord/app/contracts/chapters.py` `ChapterProvisioningError` | Used by handler error paths (**D8** typed-error style). `ProvisioningStep`/`ChapterProvisionResult` — flagged **F2**. |
| `services/discord/app/contracts/interactions.py` `ack_deferred` field on `InteractionEnvelope` | **D3** (deferred-ack closure carried from bot into handler). `exclude=True` keeps it out of payload serialization. |
| `services/discord/app/contracts/api_transport.py` `headers` field on `ApiTransportRequest` | **D2** (handler must be able to send service-actor headers). |
| `services/discord/app/contracts/runtime_settings.py` `required_bot_permissions` | **D9b** (preflight permission set configurable per environment). |
| `services/discord/app/core/bot.py` `deferred`/`ack_deferred`/followup-webhook branch | **D3** (deferred-ack plumbing). `_interaction_correlation_id` uuid4 fallback is pre-existing from **SLICE-006**, unchanged. |
| `services/discord/app/infrastructure/api_client.py` headers-merge change | **Rev-3 §5** (correlation headers must still override per-call headers). |
| `services/discord/app/__main__.py` `register_chapter_commands(bot)` call | Glue — registers the AC2 command on bot startup. |

### Tests

| File | Justification |
|---|---|
| `services/api/tests/test_chapter_templates.py` | AC1 coverage: `test_create_chapter_template_creates_new_family_version_1`, `test_patch_chapter_template_creates_new_version_same_family`, `test_patch_chapter_template_stale_expected_version_returns_412`, `test_patch_race_one_accepted_one_412_no_integrityerror`, `test_discord_provisioner_service_actor_has_chapter_grants_after_migration`. All trace to **AC1 + D9 + D2**. |
| `services/api/tests/test_chapter_lifecycle.py` | AC2/AC3/AC4 coverage including `test_transition_to_active_rejects_when_incomplete` (parametrized, **D7**), `test_patch_discord_resources_merges_not_replaces` (**D12**), `test_transition_provisioning_to_failed_enqueues_deferred_effect_atomically` (**D6 + SLICE-007**), `test_retry_transition_from_provisioning_failed_to_provisioning` (**AC3**), `test_deferred_effect_idempotency_key_per_transition` (**D6**), `test_api_records_originating_user_discord_id_in_audit_payload` (**D2**). Grep-invariant tests `test_no_legacy_inmemorychapterrepository_remains`, `test_no_chapterstatus_remains`, `test_no_archive_route_under_api_v1_chapters` enforce **Rev-3 §2** legacy removal. |
| `services/discord/tests/test_chapter_provisioning.py` | `test_discord_handler_acks_deferred_before_api_calls` (**D3**), `test_provision_rejects_when_chapter_already_provisioning` (**D4**, CodeRabbit fix aeecd5e), `test_discord_handler_rediscovers_role_by_name_after_patch_failure` (**D5**), `test_rediscovers_channel_only_within_category` (audit F15 / CodeRabbit fix). |
| `services/api/tests/test_authority_enforcement.py`, `test_authority_override_audit.py` — `chapter.archive → chapter.write` rename | **Rev-3 §2** (legacy `/archive` route removed; `chapter.write` scope is the correct post-SLICE-013 authority per **D1**). |
| Deleted: `services/api/tests/test_chapters.py`, `test_contracts_chapters.py`, Section 4 of `test_activity_model.py` | **Rev-3 §2** — these tested legacy slug/integer-id/status semantics that no longer exist. |

### Core / factory cleanup

| File | Justification |
|---|---|
| `services/api/app/core/dependencies.py` — removed `get_chapter_service` + `ChapterService` import | **Rev-3 §2** / **AGENTS.md** "no compat shims" — legacy `ChapterService` was deleted; stale import/factory-dep removed in the same PR. |
| `services/api/app/core/factory.py` — removed `chapter_repository`, `action_store`, `state_change_store` params + `app.state.chapter_service` wiring | Same — dead wiring after legacy substrate removed. |

## 4. Notes on what was explicitly NOT found (negative-scope checklist)

- ❌ No `TODO` / `FIXME` / `NotImplementedError` / empty `pass` handler in SLICE-013-added code (verified via grep during review).
- ❌ No re-exports, `if legacy:` branches, deprecated aliases, or `# removed` comment stubs.
- ❌ No endpoint outside AC1–AC4 surface: 3 template routes (POST/GET/PATCH) + 4 chapter routes (POST/GET/POST-transitions/PATCH-discord-resources). Zero "archive", "deactivate", "list-all", or other non-ticketed verbs.
- ❌ No DB column outside D10/D11/D12 spec. `originating_actor_kind`/`originating_actor_id` on `chapter_transitions` are nullable and justified by **D2** (Discord handler must record originating user in the audit ledger).
- ❌ No magic constants unjustified. `chapter_provision_retry:` prefix is D6. `service`/`discord-provisioner` actor is D2. `MANAGE_ROLES`/`MANAGE_CHANNELS`/`VIEW_CHANNEL` defaults are D9b.
- ❌ No test without AC/D trace (every test in the three new test files maps above).

## 5. Recommendation

**Merge-ready from a justification standpoint.** Address F1 and F2 as
follow-up cleanup (either in this PR via a post-review commit, or tracked
for SLICE-014). F3 is a judgment call the author already made correctly.

See `plans/review/slice-013-multiconcern.md` for the separate
one-concern-per-PR concern (`MULTI_CONCERN_RECOMMEND_SPLIT`). The two
reviews are orthogonal: nothing in this justification review would change
if the PR is or is not split, and nothing in the multiconcern review
affects the AC/D traceability evaluated here.
