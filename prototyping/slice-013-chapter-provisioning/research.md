# Prototype Research: slice-013-chapter-provisioning

## Slice under investigation

**Roadmap reference:** `SLICE-013`, `VS-005`, `WU-018` through `WU-020`
**Capability being prototyped:** Provision a chapter from a template through an API-backed lifecycle that creates Discord roles/channels safely and degrades cleanly on failure.

## Questions the prototype will answer

1. **Discord provisioning workflow:** Can one Discord handler, using the existing `InteractionRegistry` + `ApiClient` seams, read chapter/template state from the API, call the minimum discord.py creation primitives, and surface typed failures without network access in tests?
   Success criteria: the prototype can exercise category creation, role creation, and text/voice channel creation against a mock guild, pass per-role overwrites at creation time or through a follow-up overwrite call, and map injected downstream errors into a stable failure result.

2. **Lifecycle + optimistic locking:** Can the chapter lifecycle be expressed as versioned aggregate transitions under `mutate_entity()` without introducing a second concurrency mechanism?
   Success criteria: `proposed -> provisioning -> active` succeeds with exactly one version increment per accepted transition, stale `expected_version` is rejected, and invalid transitions raise a typed lifecycle error.

3. **Failed provisioning deferred effect:** When Discord provisioning fails after some resources already exist, can one accepted write atomically persist both chapter degraded state and one consequential deferred effect with enough data for retry or cleanup?
   Success criteria: the prototype shows a single logical mutation ending with a non-active chapter state plus one deferred-effect payload that includes the chapter identity and the partial Discord resources already created.

4. **Template instantiation model:** Does chapter provisioning need a copy-on-instantiate snapshot of template structure, or is a live `template_id` reference sufficient once template edits exist?
   Success criteria: the prototype can simulate a later template edit and verify whether a provisioned chapter still has a stable, replayable configuration for reconciliation and retry.

5. **Snapshot storage location:** If copy-on-instantiate is required, can the snapshot live on the chapter aggregate without violating the proposal’s governance boundary for `Chapter.configuration`?
   Success criteria: the prototype makes clear whether the slice can reuse `configuration` or whether it needs a separate operational snapshot field or child records.

6. **Idempotent retry anchor:** On a re-run after partial provisioning, what durable state is available to prevent duplicate Discord resources?
   Success criteria: the prototype identifies a persisted source of truth for already-created resource IDs; name-only duplicate detection is not enough.

## External dependencies

- `discord.py`:
  Repo pins `discord.py>=2.3,<3` in both root and Discord-service `pyproject.toml`; `NOTES.md` records prior local research resolving `discord.py 2.7.1` on `2026-04-13`.
  Relevant documented behaviors:
  role creation uses `Guild.create_role(..., reason=None)` and requires `manage_roles`; role ordering, if needed, is a separate `Guild.edit_role_positions(...)` call.
  channel creation uses guild channel-creation methods with `overwrites={Role|Member: PermissionOverwrite}` and `reason=...`; if a category is supplied and no explicit overwrites are passed, permissions sync from the category.
  channel overwrite edits can be applied later with `abc.GuildChannel.set_permissions(...)`.
  Sources: `https://discordpy.readthedocs.io/en/v2.3.2/api.html`, `https://discordpy.readthedocs.io/en/latest/migrating.html`

- Discord exception surface:
  The documented creation/update calls raise `Forbidden`, `HTTPException`, and `TypeError`; these are the minimum error classes the prototype should inject and map.
  Source: `https://discordpy.readthedocs.io/en/v2.3.2/api.html`

- Existing test transport:
  Discord-side tests already use `httpx.MockTransport` as `api_client_stub`, so API integration can remain offline.
  Code reference: `services/discord/tests/conftest.py`

## Codebase touchpoints

- `services/discord/app/commands/registry.py`:
  Existing command registration and dispatch seam for the provisioning command handler.

- `services/discord/app/core/bot.py`:
  Builds `InteractionEnvelope`, dispatches to the registry, and sends the handler’s response text back to Discord.

- `services/discord/app/core/request_context.py`:
  Single owner of `InteractionEnvelope -> AuditContextRead` mapping.

- `services/discord/app/infrastructure/api_client.py`:
  Existing Discord-to-API transport that propagates correlation and causation headers automatically.

- `services/discord/tests/conftest.py`:
  Already provides `bot`, `interaction_factory`, and `api_client_stub` fixtures that fit the requested no-network prototype shape.

- `services/discord/tests/test_interaction_framework.py`, `services/discord/tests/test_api_transport.py`, `services/discord/tests/test_api_context.py`:
  Define the existing dispatch, transport, and correlation contracts the prototype should stay inside.

- `services/api/app/services/mutations.py`:
  Shared OCC write primitive; every accepted mutation increments `aggregate_heads.current_seq` once and can run inside a caller-supplied DB connection.

- `services/api/app/contracts/scheduler.py`, `services/api/app/services/deferred_effects.py`, `services/api/app/repositories/deferred_effects.py`, `services/api/tests/test_deferred_effect_foundation.py`:
  Existing deferred-effect model, including `consequence_level`, `precondition_state`, `idempotency_key`, retries, and degraded-state visibility.

- `services/api/app/contracts/chapter_templates.py`, `services/api/app/services/chapter_templates.py`, `services/api/tests/test_chapter_template_foundation.py`:
  Current merged template foundation. Important current fact: it is create/read only and explicitly immutable.

- `services/api/app/contracts/chapter_roles.py`, `services/api/tests/test_chapter_role_foundation.py`:
  Existing `template_id` linkage on concrete chapter-role rows. This is the main current evidence for template-origin tracking.

- `services/api/app/contracts/chapters.py`, `services/api/app/services/chapters.py`, `services/api/app/repositories/chapters.py`:
  Existing chapter surface is only a stub and does not match `WU-019`. It currently defaults a new chapter to `provisioning`, lacks `proposed`, and has no transition endpoint.

- `product-strategy/tickets/SLICE-013.md`, `product-strategy/ai roadmap.md`, `product-strategy/proposal.md`:
  Define the target slice semantics and expose the mismatches the prototype must clarify.

## Constraints (must respect)

- No prototype code should hit the live Discord server. Tier-3 visible writes require explicit per-action user approval, so the prototype must stay mock-only.

- No new third-party dependencies beyond `discord.py`.

- Tests must boot without network, using the existing `api_client_stub` and mocked guild/channel/role methods.

- `SLICE-003` currently locks chapter templates as immutable.
  Evidence: `services/api/tests/test_chapter_template_foundation.py` asserts there is no `update_chapter_template` surface.

- `SLICE-013` requires mutable template management.
  Evidence: both `product-strategy/tickets/SLICE-013.md` and `product-strategy/ai roadmap.md` require `PATCH /api/v1/chapter-templates/{template_id}` with stale-write rejection.

- The proposal reserves `Chapter.configuration` for non-operational chapter metadata only.
  Operational settings are explicitly governed elsewhere, so storing a channel/role template snapshot in `configuration` would cross that boundary unless the proposal is revised.

- Deferred effects are not `mutate_entity()` aggregates.
  They are infrastructure rows with independent idempotency (`idempotency_key`) and worker lifecycle (`queued`, `claimed`, `completed`, `failed`, `skipped`).

- Consequential deferred effects do not execute while `precondition_state` is `unchecked`.
  They must be marked `valid` before the worker claims them; `invalid` is terminal non-execution but still operator-visible.

- Failed deferred effects retry until `max_attempts`, then terminate at `status='failed'` and require operator intervention.

- `mutate_entity()` already accepts an optional live DB connection.
  The prototype should test atomic composition through that existing seam before assuming the mutation surface must grow again.

- The current local bare `python3` environment does not import `discord`, even though the repo pins it.
  Prototype work should therefore rely on documented signatures and repo test doubles unless the prototype agent runs inside the managed project environment.

## Minimum viable prototype scope

The smallest useful prototype is four offline scripts under `prototyping/slice-013-chapter-provisioning/prototype/`: one mock Discord provisioning flow, one typed lifecycle state machine, one atomic failure-plus-deferred-effect experiment, and one template-instantiation snapshot experiment. It should reuse existing fixture patterns (`httpx.MockTransport`, mocked guild methods, typed Pydantic contracts) and explicitly exclude real Discord I/O, real FastAPI endpoints, migrations, and operator UI.

The prototype should answer whether the slice can stay within the existing registry, API transport, mutation, and deferred-effect seams. It should not attempt full production design or schema finalization beyond what is needed to make the contradictions measurable.

## Early-exit conditions

- **Template mutability contradiction remains unresolved.**
  If the prototype cannot reconcile `SLICE-003` immutability with `SLICE-013`’s required PATCH/update path, implementation should stop and escalate before writing production code.

- **Copy-on-instantiate requires violating the proposal’s `Chapter.configuration` boundary.**
  If the only workable snapshot location is the existing `configuration` field, that is a proposal-level conflict and should be escalated rather than silently repurposed.

- **Idempotent retry has no durable anchor for partial resources.**
  If partial Discord resource IDs cannot be persisted somewhere durable on failure, retry will devolve into name-based duplicate detection and should be treated as unsafe.

- **Atomic state-change plus deferred-effect enqueue cannot be demonstrated through current transaction seams.**
  If the prototype can only achieve atomicity by widening `mutate_entity()` again or duplicating transaction logic, that surface expansion should be flagged explicitly.

- **Discord creation flow requires materially more than the expected role/channel management surface.**
  If the minimal flow needs additional Discord capabilities or manual operator cleanup to remain safe, the slice scope needs to be reconsidered.

- **The installed runtime API surface differs from the documented discord.py calls in a way that affects the prototype contract.**
  If the managed environment exposes different method names or signatures than the documented version range implies, the prototype should stop and record the actual runtime before going further.

## Time budget

`1-2 hours` of agent time.
