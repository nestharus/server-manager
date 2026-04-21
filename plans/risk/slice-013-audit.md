# SLICE-013 Phase 4 Audit Risk Assessment

**Rating: LOW**

## Scope note

The focus-area prompt references `slice-013-scheduler/findings.md` and concerns like `SELECT FOR UPDATE SKIP LOCKED`, claim queries, 5-minute lease semantics, `asyncio.to_thread()`, handler heartbeats, and FastAPI lifespan scheduler wiring. **None of those apply to this proposal.** SLICE-013 is chapter provisioning (WU-018 template mgmt, WU-019 chapter lifecycle, WU-020 Discord handler). It only *enqueues* consequential deferred effects — the worker/scheduler is explicitly deferred (D12, synthesis.md:155-156; proposal.md:40 anti-scope). The scheduler/worker rubric items are therefore either satisfied by SLICE-004 substrate already on `main` or out-of-scope here. I reframed around what SLICE-013 actually does: template versioning races, chapter lifecycle atomicity, Discord-to-API actor threading, deferred-effect enqueue correctness, legacy-substrate replacement, and migration safety.

`.pipeline/research.md` does not exist in this worktree; the prototype research is at `prototyping/slice-013-chapter-provisioning/research.md` (proposal.md:13 Source note). The prototype findings path is `prototyping/slice-013-chapter-provisioning/findings.md`, not `slice-013-scheduler/findings.md`.

**Revision tracking.** This audit evaluates `proposal.md` at Revision 3 (proposal.md:508). Revision 3 explicitly claims to fix the three MEDIUM findings from the prior audit pass (F5 name-based rediscovery invariant, F6 service-actor grant seeding, F7 Discord deferred-ack). Each is verified below.

## Findings

### F1 — Template PATCH race: correctly pinned, unique-index backstop present (LOW)
Proposal.md:104-113 locks the source row, runs `SELECT ... FOR UPDATE` across the family to compute `max(version)`, then inserts at `current+1`. `uq_chapter_templates__family_version` (proposal.md:76) is the DB backstop; `IntegrityError` is translated to `StaleTemplateVersionError → 412 Precondition Failed` (proposal.md:111). Test `Two PATCHes racing on the same expected_current_version produce one accepted version and one 412, never a leaked IntegrityError/500` (proposal.md:135) covers the race. Design is sound.

### F2 — `mutate_entity` + `enqueue_effect` atomicity on `provisioning_failed` (LOW)
Proposal mandates `enqueue_effect(connection=...)` on the active connection inside the `mutate_projection` callback (proposal.md:300), matching the prototype atomicity proof (findings.md:27-35) and the `mutate_entity(connection=...)` seam (`services/api/app/services/mutations.py:58-71, 191-197`). State degradation + deferred-effect row are one transaction. Rollback is coherent. Correct.

### F3 — Idempotency key includes `chapter_transition_id`, not `chapter_id` or version (LOW)
`chapter_provision_retry:{chapter_id}:{chapter_transition_id}` (proposal.md:301, 477). `enqueue_effect` uses `ON CONFLICT (idempotency_key) DO NOTHING` (verified in `services/api/app/repositories/deferred_effects.py:66`), so re-enqueue for the same transition is silently no-op; `IntegrityError` does not leak to the caller. Each retry (`provisioning_failed → provisioning → provisioning_failed`) mints a new transition id, so a fresh effect row is created per attempt. Correct.

### F4 — Precondition gate honored by design (LOW)
Enqueued effects are `consequence_level="consequential"`, `precondition_state="unchecked"` (repositories/deferred_effects.py:45-51 writes the literal `'unchecked'` at insert time; proposal.md:347, 503). The existing SLICE-004 claim predicate requires `(consequence_level = 'safe' OR precondition_state = 'valid')` (deferred_effects.py:165-167 on main). Unchecked consequential rows cannot be claimed — so nothing dispatches until a future slice validates preconditions. No worker-side bypass risk in SLICE-013, and no admin SQL path is introduced by this slice.

### F5 — Lost-PATCH → orphan Discord resource: name-based rediscovery invariant now explicit (LOW; was MEDIUM in Rev 2)
**Rev 3 fix verified.** Proposal.md:443 (Tradeoffs §4): "If `PATCH /discord-resources` fails after a Discord resource is successfully created, the resource id is lost from the API's side. On retry, the handler rediscovers it via deterministic slug-name matching against the guild (D5). Slug derivation MUST be stable and collision-resistant within a guild; name drift breaks rediscovery. No secondary anchor, such as a Discord ID stored in Discord metadata, is available in Phase 0." Proposal.md:399 pins the runtime behavior: "If a `PATCH /discord-resources` call fails after the Discord resource exists, stop the current run. On retry, rediscover the resource by deterministic slug-name matching against the guild before creating another resource with the same logical key." Test coverage is explicit: `test_discord_handler_rediscovers_role_by_name_after_patch_failure` where role creation succeeds, `PATCH /discord-resources` fails, and retry rediscovers by name (proposal.md:424). Residual risk: slug collisions and name drift remain the load-bearing invariant, but this is explicitly scoped as Phase 0.

### F6 — `discord-provisioner` service actor grants seeded in migration (LOW; was MEDIUM in Rev 2)
**Rev 3 fix verified.** WU-019 migration inserts a global non-expiring grant with `grantee_id='discord-provisioner'` and permissions `["chapter.read","chapter.write","chapter_template.read"]` (proposal.md:170-188). The authority guard evaluates on `actor.actor_id` only (`services/api/app/core/dependencies.py:85` uses `list_grants_for_grantee(grantee_id=actor.actor_id)`), so the seeded row matches the `X-Actor-Id: discord-provisioner` header regardless of `actor_kind`. Migration test `test_discord_provisioner_service_actor_has_chapter_grants_after_migration` asserts the seeded row exists with the right scope and permissions (proposal.md:190). Permission set is correctly minimized — write on chapters (create + transition + resource merge), read on templates (snapshots happen server-side so no template.write is needed).

Sub-findings worth a single-line proposal pin but not elevating severity:

- **F6a — Service-actor id namespace collision (LOW).** A user actor with `actor_id='discord-provisioner'` would inherit the seeded grants because the guard keys on `actor_id` alone. Discord user ids are numeric snowflakes in practice, but nothing schema-level prevents the collision. Acceptable for Phase 0; recommend a non-blocking note that grantee_ids for service actors must remain distinct from any plausible user actor_id.
- **F6b — Grant audit trail is the migration file (LOW).** The seed INSERT has `revoked_at=NULL`, `expires_at=NULL`, no `predecessor_grant_id`, and is written as raw DML, not through `mutate_entity()`. There is no `activity_actions` row recording *when* or *by whom* this grant was authorized beyond the migration commit itself. That is acceptable — the migration file is a versioned, reviewed artifact — but operators should be aware that `SELECT * FROM activity_actions WHERE aggregate_type='authority_grant' AND aggregate_id=<seed_grant_id>` will be empty.
- **F6c — Downgrade path not specified (LOW).** The proposal spec for wu-019 does not describe `downgrade()`. If a future environment downgrades past wu-019 and re-upgrades, a second grant row will be inserted because `gen_random_uuid()` yields a fresh id each time and there is no `ON CONFLICT` clause. Duplicate active grants for the same `(grantee_id, scope_kind, permissions)` tuple are not syntactically rejected (no DB uniqueness on that tuple), but `evaluate()` treats them as OR-merged, so correctness is preserved; operator UX in grant listings merely shows duplicates. Recommend proposing a `downgrade()` that deletes rows with `grantee_id='discord-provisioner' AND scope_kind='global'`, or using a deterministic id so replays are idempotent.

None of F6a/F6b/F6c are blocking. F6 is resolved from MEDIUM to LOW.

### F7 — Discord interaction 3-second budget: deferred ack requirement now explicit (LOW; was MEDIUM in Rev 2)
**Rev 3 fix verified.** Proposal.md:372: "The Discord handler MUST `ack_deferred()` inside the 3-second interaction window and return the final `InteractionResult` via follow-up webhook. The current registry only calls the handler and returns its result (`services/discord/app/commands/registry.py:28-33`), and `HumilityBot.dispatch_interaction(...)` only sends a Discord response after registry dispatch completes (`services/discord/app/core/bot.py:51-56`), so SLICE-013 must add the explicit deferred-ack seam before any API call or visible Discord mutation." Proposal.md:420: test `test_provision_chapter_handler_acks_deferred_before_api_calls` asserts deferred ack fires before the first API call. Proposal.md:475 records it as a §6 pin. Residual design note: the exact seam (whether `ack_deferred` lives in the handler, the registry, or the `HumilityBot.dispatch_interaction` wrapper) is implementation-deferred, but the contract and test are pinned.

### F8 — `payload_allowlist` for chapter mutations not pinned (LOW)
`mutate_entity` redacts `action_payload` via caller-supplied `payload_allowlist` (`services/api/app/services/mutations.py:37-48`). Existing callers mix styles: `chapter_templates.py:72` uses `set(request.model_dump().keys())`; `policies.py:169` uses `None` (drops payload); `audit_overrides.py:52` uses a specific narrow set. The proposal does not specify which the chapter service should use for `create_chapter` / `transition_chapter` / `patch_chapter_discord_resources`. `ChapterTransitionRequest` carries `to_state`, `reason`, `originating_actor_kind`, `originating_actor_id` — none are secrets. `ChapterCreate` adds `template_id`, `name`, `configuration`; `configuration` is operator-supplied free-form JSONB and is the one field that *could* in principle carry secrets in a future slice (today Phase 2 leaves it empty). `ChapterResourcesPatchRequest.resources` contains Discord IDs only. No current exposure, but the proposal should pin the choice so the audit payload shape is predictable across callers. Not blocking.

### F9 — `category_id=None` in merge PATCH cannot clear existing id (LOW, documented)
Proposal.md:268: "`category_id=None` means 'no category update' and cannot clear an existing category in this slice." Documented. Operational corollary: if a Discord category is deleted mid-provisioning and re-created, the operator cannot overwrite the stale id via the merge endpoint. Acceptable for Phase 0 because the retry path starts from `provisioning_failed → provisioning` which only transitions state and does not clear `discord_resources`. The handler's name-based rediscovery on retry (F5) would match the newly-created category and the PATCH would preserve the stale id unless the rediscovery writes replace it — which `role_ids`/`channel_ids` do at key granularity but `category_id=None` does not. Minor: consider allowing an explicit `"category_id": ""` sentinel in a future slice. Confirmed safe as specified.

### F10 — `chapter_transitions` projection consistency with `activity_state_changes` (LOW)
`activity_actions`/`activity_state_changes` remain the authoritative mutation/audit ledger (proposal.md:302, 459). `chapter_transitions` is a denormalized projection written inside the same `mutate_projection` callback (proposal.md:298). Both live or both roll back. Proposal.md:302 explicitly declares `activity_actions` as the tie-breaker when they disagree: "If an inconsistency is ever discovered, `activity_actions` wins." Correct.

### F11 — Migration chain ordering (LOW)
Current head is `wu_014_authority_api` (`migrations/versions/wu-014_authority_api.py:10`). wu-018 correctly sets `down_revision="wu_014_authority_api"` (proposal.md:60). wu-019 chains on wu-018 (proposal.md:144). `pgcrypto` is enabled before the UUID backfill (proposal.md:61) — verified no existing `CREATE EXTENSION` in the tree. Nullable → backfill → NOT NULL is the correct three-step pattern for a live table (proposal.md:62-78). FK `chapters.template_id REFERENCES chapter_templates(id)` is valid because wu-019 runs after wu-018. The seeded authority grant in wu-019 runs after `authority_grants` exists (wu-004), so no ordering hazard. `chapters.id TEXT PRIMARY KEY` is compatible with the `activity_actions.aggregate_id TEXT` shape used by `mutate_entity`.

### F12 — Correlation/causation + actor propagation across handler → API (LOW)
`mutate_entity` reads `get_current_audit_context()` if the request doesn't carry explicit ids (mutations.py:74-92 on main). SLICE-006 `ApiClient` already propagates correlation/causation headers (`services/discord/app/infrastructure/api_client.py:25-62`), and SLICE-008 `ActorMiddleware` materializes the audit context from headers (`services/api/app/core/actor.py:63-81`). The Discord handler executes inside the interaction task's context, and `InteractionRegistry` dispatch preserves audit context (proposal.md:33 cites `services/discord/tests/test_api_context.py:110-146`). Proposal.md:462 flags that the current `ApiClient` does *not yet* propagate actor headers, so WU-020 extends this seam to emit `X-Actor-Kind: service, X-Actor-Id: discord-provisioner`. Design is consistent; context is request-scoped on the API side and is not cached across jobs (no scheduler). No stale-context risk flagged.

### F13 — Originating user recorded on projection, preserves accountability (LOW)
`chapter_transitions.originating_actor_kind/id` are nullable columns (proposal.md:163-164). This preserves accountability — the Discord operator who ran `/provision_chapter` is recorded on every transition row even though the API caller is `service/discord-provisioner`. Not indexed; no query-path requires it yet. Fine.

### F14 — `payload_json` secret-leak surface (LOW)
SLICE-002 added `payload_allowlist` on notifications because caller-supplied JSON could carry secrets. For `deferred_effects.payload_json`, the SLICE-013 payload is service-assembled: `chapter_id`, `template_id`, `partial_resources` (Discord IDs), `failure_reason`, `failed_at_step` (synthesis.md:62-72). No caller-supplied free-form fields enter `payload_json`. No secret-leak surface from this slice. (`ChapterCreate.configuration` flows into `chapters.configuration`, not into any deferred_effect payload.)

### F15 — Unchecked consequential effects accumulate until worker slice lands (LOW, operational)
Because `precondition_state="unchecked"` never gets claimed, `chapter_provisioning_retry` effect rows will accumulate in `deferred_effects` indefinitely until a future precondition validator + worker land. Not a correctness bug — just growing row count and operator-visible "stuck effects" in any list view. Worth a one-line acknowledgement in proposal anti-scope that operators will see a non-empty queue of unchecked consequential effects until the retry worker slice ships.

### F16 — Legacy in-memory chapter substrate ripped out atomically (LOW; new in Rev 3)
**New in Rev 3.** Proposal.md:30 and §5 declare that SLICE-013 deletes `InMemoryChapterRepository`, `ChapterRecord`, integer-id contracts, the legacy `/archive` route, and the in-memory `ChapterService` in place, with no parallel parked code and no compatibility aliases (proposal.md:255, 324, 455-457). Grep invariants are explicit (proposal.md:354-358). I cross-checked for external consumers via `grep -r "ChapterService\|InMemoryChapterRepository\|ChapterRecord"`; all hits live in the six files the proposal already enumerates for rewrite (`services/api/app/{services,repositories,contracts,core/factory,api/v1/endpoints}/chapters*`, plus tests). No module outside this set consumes the legacy types. The rip-out is safe blast-radius-wise.

Residual concern: the rip-out includes changing `chapters.id` from `int` to `TEXT (UUID)`, `aggregate_type="chapter"` aggregate ids from integer-stringified to UUID-stringified, and dropping the legacy `/archive` route. If any `aggregate_type="chapter"` rows already exist in `activity_actions` (from the legacy code path), their `aggregate_id` will be integer-stringified text, which will not match UUID-stringified new ids. The proposal does not describe a backfill or soft-delete for legacy activity rows. Given the legacy substrate was in-memory only (`InMemoryActionStore` / `InMemoryStateChangeStore`, proposal.md:457), no persistent rows exist in `activity_actions` from the legacy path, so there is nothing to migrate. Confirmed safe.

### F17 — `_verify_provisioning_complete` gate for `to_state="active"` (LOW; new in Rev 3)
**New in Rev 3.** Proposal.md:277-295 adds strict completeness checks: active transition requires `category_id`, every role in the template snapshot's `role_structure`, and every channel in the template snapshot's `channel_structure`. Three specific tests pin this (proposal.md:342-344). This closes the gap where a handler could have partial resources but post a successful active transition. Check runs inside the same `mutate_projection`, so it composes with the OCC lock. Returns `409 incomplete_provisioning` with structured `missing` payload. Correct design; audit story holds — a chapter cannot be marked `active` unless the API can see evidence of every template-required Discord resource being persisted.

## Summary table

| # | Finding | Severity |
|---|---|---|
| F1 | Template PATCH race locked; unique-index backstop maps `IntegrityError → 412` | LOW |
| F2 | `mutate_entity(connection=...)` + `enqueue_effect(connection=...)` atomicity sound | LOW |
| F3 | Idempotency key scoped to `chapter_transition_id`; `ON CONFLICT DO NOTHING` verified | LOW |
| F4 | Precondition gate honored — `unchecked` consequential rows cannot be claimed | LOW |
| F5 | Rev 3 pins name-based rediscovery invariant + dedicated test | LOW (was MEDIUM) |
| F6 | Rev 3 seeds `discord-provisioner` grants in migration + migration test | LOW (was MEDIUM) |
| F6a | Service-actor id namespace collision with user actor_id | LOW |
| F6b | Grant audit trail is the migration file, not an `activity_actions` row | LOW |
| F6c | Migration `downgrade()` path for grant seed not specified | LOW |
| F7 | Rev 3 requires `ack_deferred` before API work + dedicated test | LOW (was MEDIUM) |
| F8 | `payload_allowlist` choice for chapter mutations not pinned | LOW |
| F9 | `category_id=None` cannot clear — documented, safe for Phase 0 | LOW |
| F10 | `chapter_transitions` projection written in same `mutate_projection`; ledger tiebreaker pinned | LOW |
| F11 | Migration chain wu-014 → wu-018 → wu-019 + pgcrypto + nullable/backfill/NOT NULL correct | LOW |
| F12 | Correlation/causation/actor propagation across handler → API is request-scoped, no stale context | LOW |
| F13 | Originating-user fields nullable on projection — preserves operator accountability | LOW |
| F14 | `payload_json` is service-assembled, not caller-supplied — no secret-leak | LOW |
| F15 | Unchecked consequential effects accumulate until retry worker slice (operational, not correctness) | LOW |
| F16 | Legacy in-memory chapter substrate ripped out atomically; no persistent residue | LOW |
| F17 | Strict `_verify_provisioning_complete` gate for active transition | LOW |

## Verdict

**LOW.** Revision 3 directly and verifiably addresses the three MEDIUM findings from the prior audit (F5, F6, F7). No HIGH or MEDIUM items remain. The core data-integrity story — atomic transition + deferred-effect enqueue, OCC via `mutate_entity`, idempotent PATCH, copy-on-instantiate, precondition gate honored, name-based idempotent rediscovery, strict active-transition completeness, atomic legacy-substrate replacement — is sound.

The LOW-severity sub-findings (F6a/F6b/F6c, F8, F9, F15) are non-blocking polish items. The proposer may optionally absorb them as §6 pins before implementation:

- **F6a:** Add a §6 pin that service-actor `grantee_id` values must remain distinct from user actor_ids. Since Discord user ids are numeric snowflakes, a non-numeric token like `discord-provisioner` is already collision-safe in practice; a one-liner codifies the invariant.
- **F6b / F6c:** Document in §6 that wu-019's `downgrade()` should delete the seed grant, or switch to a deterministic grant id (`uuid5(namespace, 'discord-provisioner:global:chapter.read+chapter.write+chapter_template.read')`) with `ON CONFLICT (id) DO NOTHING` so downgrade/upgrade cycles are idempotent.
- **F8:** Pin the `payload_allowlist` choice for `create_chapter`, `transition_chapter`, and `patch_chapter_discord_resources` so audit payloads are predictable. `set(request.model_dump().keys())` matches the `chapter_templates.py:72` convention.
- **F15:** Add one line to §2 anti-scope noting that operators will observe an accumulating queue of `precondition_state="unchecked"` effects until the retry worker slice lands.

None of these are required to downgrade to LOW — the slice is already LOW. They are deferred polish.
