# SLICE-013 Phase 2: Synthesis

Orchestrator synthesis. D1-D12 binding.

## Problem

SLICE-013 ships chapter provisioning from templates — template-mgmt CRUD, chapter lifecycle (proposed → provisioning → active), Discord guild resource creation workflow. Prototype identified one genuine contradiction (SLICE-003 immutable templates vs AC1's PATCH) resolved via template versioning.

## Scope Decisions

### D1: Template immutability resolved via versioning (new column `version`)

SLICE-003 D9 made templates immutable (no update path). AC1 requires PATCH. Resolution:
- `chapter_templates` gains `version: BIGINT NOT NULL` + `template_family_id: UUID NOT NULL` via migration `wu-018_chapter_templates.py`.
- Each template row is still immutable in-place (per SLICE-003).
- `PATCH /chapter-templates/{id}` creates a NEW row sharing the same `template_family_id`, with `version = max(version) + 1`.
- GET by `template_id` returns a specific version; operators pass `expected_current_version` for 412 stale-write detection.
- ChapterTemplateRead gains `version`, `template_family_id` fields.

### D2: Chapter state machine — 4 states + typed transitions

```python
ChapterState = Literal["proposed", "provisioning", "active", "provisioning_failed"]

ChapterTransition = {
    ("proposed", "provisioning"),
    ("provisioning", "active"),
    ("provisioning", "provisioning_failed"),
    ("provisioning_failed", "provisioning"),   # retry
}
```

Service enforces the matrix; invalid transition raises `InvalidChapterTransitionError`. No direct state updates — always via `transition_chapter(chapter_id, to_state, reason, actor)` service call that composes with mutate_entity. Archive state and archive transitions are SLICE-023-only.

### D3: Template instantiation = copy-on-instantiate

Chapter row stores:
- `template_id: UUID` — provenance, the exact template version used
- `template_snapshot: JSONB` — deep-copied channel_structure + role_structure + default_permission_intents at provision time
- `configuration: JSONB` — operator-set overrides (empty in Phase 2)

Template edits (new version in same family) do NOT alter existing chapters. Chapters only change via explicit operator actions.

### D4: Discord provisioning workflow = sequential with partial-failure rollback plan

Order: create_category → create_roles (sequential) → create_channels with permission overwrites → record Discord resource IDs back via API → transition to active.

On any step failure:
1. Record partial resources (category_id, role_ids, channel_ids) in `discord_resources` on the Chapter row.
2. Transition chapter to `provisioning_failed`.
3. Enqueue deferred_effects row with consequence_level="consequential", precondition_state="unchecked", effect_type="chapter_provisioning_retry", payload includes chapter_id + partial resources + failure reason.

Retry (from provisioning_failed → provisioning): operator triggers retry via transition endpoint OR deferred effect handler picks up after precondition validated.

### D5: Idempotent provisioning via name-check

Before creating any Discord resource, check if a resource with the chapter's prefix/name already exists in the guild. If present, treat as already-created (record its id in discord_resources). Each role/channel name is derived deterministically from template + chapter name, so re-running provisioning on a partial state doesn't duplicate.

### D6: Deferred effect payload for failed provisioning

```python
payload = {
    "chapter_id": str(chapter.id),
    "template_id": str(chapter.template_id),
    "partial_resources": {
        "category_id": Optional[str],
        "role_ids": dict[str, str],  # {template_role_name: discord_role_id}
        "channel_ids": dict[str, str],
    },
    "failure_reason": str,
    "failed_at_step": Literal["category","role","channel","permission_overwrite","api_confirm"],
}
```

Effect handler (future slice or next PR): read payload, resume from failed step, call Discord API to finish, update chapter state via API.

### D7: Discord resources stored on Chapter row

`chapters.discord_resources: JSONB` — structure:
```python
{
    "category_id": "123456789",
    "role_ids": {"officer": "111", "member": "222", ...},
    "channel_ids": {"announcements": "333", "general": "444", ...},
}
```

Always kept in sync with Discord reality. On provisioning, populated incrementally. Archive retention semantics are SLICE-023-only.

### D8: Required permissions for API endpoints

- `chapter_template.write` for POST/PATCH template endpoints (global scope)
- `chapter_template.read` for GET (global)
- `chapter.write` for POST /chapters + POST /transitions (global scope)
- `chapter.read` for GET /chapters/{id} (global scope for Phase 2; chapter-scoped later)

All via RequireAuthority.

### D9: Discord bot permissions required

- MANAGE_CHANNELS (create_category + create_text_channel)
- MANAGE_ROLES (create_role + permission overwrites)
- VIEW_CHANNEL (observe)

Document in DiscordSettingsRead — no new env var, but add a comment documenting required bot permissions. Fail-fast at Discord runtime boot if `bot.guild.me.guild_permissions` lacks any required bit (enhance runtime_check).

### D10: Chapter aggregate identity and table schema

New migration `wu-019_chapter_lifecycle.py`:
```sql
CREATE TABLE chapters (
    id TEXT PRIMARY KEY,  -- stable chapter-id, e.g., "chapter:<slug>"
    name TEXT NOT NULL,
    template_id UUID NOT NULL REFERENCES chapter_templates(id),
    template_snapshot JSONB NOT NULL,
    configuration JSONB NOT NULL DEFAULT '{}',
    state TEXT NOT NULL CHECK (state IN ('proposed','provisioning','active','provisioning_failed')),
    discord_resources JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX uq_chapters__name ON chapters (LOWER(name));

CREATE TABLE chapter_transitions (
    id UUID PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id),
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    actor_kind TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_chapter_transitions__chapter_id ON chapter_transitions (chapter_id);
```

`aggregate_id = str(chapter.id)` for mutate_entity. Each transition writes one activity_action + one chapter_transitions row (via mutate_projection).

### D11: Discord provisioning workflow in handlers/chapters.py + commands/chapters.py

- `commands/chapters.py`: register `provision_chapter(chapter_id, actor)` as an InteractionHandler via InteractionRegistry. (Or register as a non-command background task via SchedulerLoop? Since it's triggered by an operator Discord command, InteractionHandler is correct.)
- `handlers/chapters.py`: async `provision_chapter_handler(envelope) -> InteractionResult`:
  1. Fetch chapter from API (GET /chapters/{id}) — expect state=proposed.
  2. POST /chapters/{id}/transitions with to_state="provisioning".
  3. Create Discord resources sequentially (D4).
  4. On each step success, PATCH `/chapters/{id}/discord-resources` to update discord_resources incrementally.
  5. On all success, POST transition to_state="active".
  6. On any failure, enqueue deferred effect via API (new POST /deferred-effects endpoint OR direct via the scheduler service if shared).

### D12: Anti-scope

- NO chapter editing post-provision (name changes, template swaps) — later slice.
- NO chapter archive state, archive transitions, archive workflow, archived_at column, or Discord resource teardown. Archive is SLICE-023-only.
- NO roster management (SLICE-018).
- NO template-family permission (templates and their versions all share same permission).
- NO deferred-effect handler implementation for chapter_provisioning_retry — this slice ENQUEUES the effect; the handler/worker that drains it is deferred to a follow-up slice or SLICE-023.
- NO multi-guild / multi-tenant.

## Acceptance Criteria → WU Mapping

- **AC1** (template create/update + 412): WU-018 — POST creates v1; PATCH creates new version of same family; 412 on expected_current_version mismatch.
- **AC2** (create returns proposed state + template reference): WU-019 — POST /chapters creates row at state=proposed with template_id populated.
- **AC3** (proposed→provisioning→active only after verified Discord IDs): WU-019 transitions endpoint + AC3-required `PATCH /chapters/{id}/discord-resources` endpoint + WU-020 workflow patching discord_resources before requesting final active transition.
- **AC4** (failed provisioning → deferred effect, not partial active): WU-020 catch + enqueue deferred_effect + transition to provisioning_failed (not active).

## Hand-off to Proposal

Proposer honors D1-D12 and covers:
- 2 migrations (wu-018 templates versioning, wu-019 chapters + transitions)
- Contract shapes (ChapterTemplateRead gains version/family, ChapterRead, ChapterTransitionRead, ChapterProvisionResult)
- Services (chapter_templates widened, chapters new, Discord handlers new)
- 7 API route operations + 1 Discord command handler
- Deferred effect enqueue (reuses SLICE-004 substrate)
- Authority guards
- Per-WU test plans
