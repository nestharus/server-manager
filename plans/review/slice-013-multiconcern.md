# SLICE-013 Phase 8 — Multi-Concern Review (PR #39)

Reviewed: 2026-04-20
PR: `feat/slice-013-chapter-provisioning` (#39), 57 files, +5534 / −1132 LOC
Inputs: `.pipeline/proposal.md` rev 3, `.pipeline/implementation.md`, `.pipeline/hookpoints.md`,
`gh pr diff 39`, `AGENTS.md` §"One Concern Per PR" (lines 178–193).

## 1. Verdict

**`MULTI_CONCERN_RECOMMEND_SPLIT`**

The PR ships three independently-reviewable work units with no circular
dependency forcing them into one merge:

- WU-018 (template family versioning) can land atomically on `main`.
  Template CRUD works without chapters referencing it.
- WU-019 (chapter lifecycle + atomic legacy substrate replacement) depends
  only on WU-018's `chapter_templates.template_family_id` / `version` columns
  being present, and runs its own migration head
  (`down_revision = "wu_018_chapter_templates"`).
- WU-020 (Discord provisioning handler) depends on WU-019's HTTP surface
  (`POST /chapters`, `POST /chapters/{id}/transitions`, `PATCH
  /chapters/{id}/discord-resources`) and the `discord-provisioner`
  authority grant seeded by the WU-019 migration. It is a pure consumer; it
  does not modify the API substrate.

Against AGENTS.md §"One Concern Per PR":
- "A PR that touches N independent concerns should be split into N PRs" — the
  three WUs touch disjoint code paths (see §4 file allocation) and disjoint
  test suites (see §6).
- "Dependency order matters — if PR B depends on PR A, A merges first" —
  WU-018 → WU-019 → WU-020 is a linear chain, not a cycle.
- The aggregate-scoping hint in the task prompt does **not** force a merge:
  templates use `aggregate_type="chapter_template"` and chapters use
  `aggregate_type="chapter"`. They do not share an aggregate namespace.
- The Discord-handler-consumes-API seam is a normal producer/consumer
  boundary that crosses services and explicitly tolerates sequential landing
  (the handler reads the API via `ApiClient`; it has no compile-time dep on
  API Python symbols).

The only piece that is atomically coupled is WU-019's legacy substrate
replacement (delete `InMemoryChapterRepository` + `ChapterStatus` + `/archive`
+ integer chapter ids simultaneously with the new persisted lifecycle). The
proposal §2 and hookpoints §9 explicitly justify this because both the legacy
and new code claim the same route paths, same `app.state.chapter_service`,
and the same `aggregate_type="chapter"` id namespace with incompatible id
types. Split *inside* WU-019 would break the service. This couples the
deletion to the addition **within** WU-019, but does not couple WU-019 to
WU-018 or WU-020.

## 2. Concerns enumerated

### Concern A — WU-018: template family versioning

Adds `template_family_id` / `version` lineage to `chapter_templates`,
`PATCH` as new-version semantics with family-locked optimistic concurrency,
and the HTTP surface (`POST/GET/PATCH /api/v1/chapter-templates`).

Touches only the template substrate. Does not reference chapters.

### Concern B — WU-019: chapter lifecycle + in-place legacy substrate replacement

Adds `chapters` and `chapter_transitions` tables, four-state lifecycle
(`proposed`/`provisioning`/`active`/`provisioning_failed`), snapshot-on-create,
mutation-backed service, incremental Discord resource persistence endpoint,
failed-provisioning deferred-effect enqueue, and seeds the
`discord-provisioner` global authority grant. Atomically deletes
`InMemoryChapterRepository`, `ChapterStatus`, `ChapterUpdate`, `ChapterRecord`,
integer `chapter_id`, `app.state.chapter_service`, `get_chapter_service`, and
the `/archive` route. Renames two unrelated authority-guard test routes away
from `/archive` and `chapter.archive` to satisfy the grep-zero invariant.

The grant seed is a data fixture consumed by WU-020 but owned by WU-019
(proposal §3 WU-019, hookpoints §1) because it is an API-side
`authority_grants` row, and keeping it in the migration that creates the
chapter lifecycle makes WU-020 deployable without a follow-up migration.

### Concern C — WU-020: Discord provisioning handler

Adds the `provision_chapter` slash command and async handler, ack-deferred
seam on the bot/registry, `headers` field on `ApiTransportRequest`,
`required_bot_permissions` on `DiscordSettingsRead`, and handler tests.
Calls WU-019's endpoints via the SLICE-006 `ApiClient`. No code inside
`services/api` or `migrations/`.

## 3. Recommended PR ordering (topological)

```
PR A (WU-018) ──▶ PR B (WU-019) ──▶ PR C (WU-020)
```

Forcing edges:

- B → A: `chapters.template_id UUID NOT NULL REFERENCES chapter_templates(id)`;
  `chapters` migration `down_revision = "wu_018_chapter_templates"`;
  `create_chapter` reads the new `version` / `template_family_id` columns
  into `template_snapshot` provenance.
- C → B: WU-020 handler calls `POST /api/v1/chapters`,
  `POST /chapters/{id}/transitions`, `PATCH /chapters/{id}/discord-resources`;
  all require the `chapter.read` / `chapter.write` grant for
  `discord-provisioner` seeded by the WU-019 migration.

No reverse edges. Each PR passes its own test suite on the main branch at
the time of merge.

## 4. File allocation (every file → exactly one PR)

### PR A — WU-018 (template versioning) [17 files]

Code:
- `migrations/versions/wu-018_chapter_templates.py`
- `services/api/app/api/v1/endpoints/chapter_templates.py`
- `services/api/app/api/v1/router.py`
- `services/api/app/contracts/chapter_templates.py`
- `services/api/app/repositories/chapter_templates.py`
- `services/api/app/services/chapter_templates.py`

Tests:
- `services/api/tests/test_chapter_templates.py`
- `services/api/tests/test_chapter_template_foundation.py`

Slice-level docs / prototype (see §5):
- `.pipeline/coderabbit-fix.md`
- `.pipeline/hookpoints.md`
- `.pipeline/implementation.md`
- `.pipeline/proposal.md`
- `.pipeline/synthesis.md`
- `plans/risk/slice-013-audit.md`
- `plans/risk/slice-013-scope.md`
- `plans/risk/slice-013-shortcut.md`
- `prototyping/slice-013-chapter-provisioning/findings.md`
- `prototyping/slice-013-chapter-provisioning/prototype-notes.md`
- `prototyping/slice-013-chapter-provisioning/prototype/discord_provisioning.py`
- `prototyping/slice-013-chapter-provisioning/prototype/failed_provision_deferred_effect.py`
- `prototyping/slice-013-chapter-provisioning/prototype/lifecycle_state_machine.py`
- `prototyping/slice-013-chapter-provisioning/prototype/template_instantiation.py`
- `prototyping/slice-013-chapter-provisioning/research.md`

### PR B — WU-019 (chapter lifecycle + legacy substrate replacement) [18 files]

Code:
- `migrations/versions/wu-019_chapter_lifecycle.py`
- `services/api/app/api/v1/endpoints/chapters.py` (replacement)
- `services/api/app/contracts/chapters.py` (replacement)
- `services/api/app/core/dependencies.py`
- `services/api/app/core/factory.py`
- `services/api/app/repositories/chapters.py` (replacement)
- `services/api/app/repositories/chapter_transitions.py` (new)
- `services/api/app/services/chapters.py` (replacement)

Tests:
- `services/api/tests/conftest.py`
- `services/api/tests/test_activity_model.py`
- `services/api/tests/test_authority_enforcement.py`
- `services/api/tests/test_authority_override_audit.py`
- `services/api/tests/test_chapter_lifecycle.py` (new)
- `services/api/tests/test_chapters.py` (DELETE)
- `services/api/tests/test_conftest.py`
- `services/api/tests/test_contracts_chapter_lifecycle.py` (new)
- `services/api/tests/test_contracts_chapters.py` (DELETE)
- `services/api/tests/test_endpoints_chapters_stubs.py`

### PR C — WU-020 (Discord provisioning handler) [16 files]

Code:
- `services/discord/app/__main__.py`
- `services/discord/app/commands/__init__.py`
- `services/discord/app/commands/chapters.py` (new)
- `services/discord/app/contracts/api_transport.py`
- `services/discord/app/contracts/chapters.py` (new)
- `services/discord/app/contracts/interactions.py`
- `services/discord/app/contracts/runtime_settings.py`
- `services/discord/app/core/bot.py`
- `services/discord/app/core/settings.py`
- `services/discord/app/handlers/__init__.py`
- `services/discord/app/handlers/chapters.py` (new)
- `services/discord/app/infrastructure/api_client.py`

Tests:
- `services/discord/tests/test_api_transport.py`
- `services/discord/tests/test_chapter_provisioning.py` (new)
- `services/discord/tests/test_main.py`
- `services/discord/tests/test_settings.py`

Total allocation: 17 + 18 + 16 = 51 files + 6 subtotal mismatch check: actual
is 17 + 18 + 16 but PR count is 57 — pipeline / plans / prototyping group is
15 files bundled into PR A, so the 57-file total checks: code/test files
split 8 (A) + 18 (B) + 16 (C) = 42, plus 15 slice docs into PR A = 57.

## 5. Straddling files — flags and justifications

### `services/api/app/api/v1/router.py` → PR A (WU-018)

Only change is adding `chapter_templates` to the imports and
`router.include_router(chapter_templates.router, ...)`. The existing
`chapters` include was already on `main`; it is not touched by this PR. So
this file belongs to WU-018. WU-019's replacement of the `chapters` endpoint
module happens *behind* the existing include without modifying `router.py`,
which is a deliberate property of the hookpoints (§5, §6).

### `services/api/tests/test_authority_enforcement.py`,
### `services/api/tests/test_authority_override_audit.py` → PR B (WU-019)

Rename a test-only route from `/archive` to `/manage` and a test-only
permission from `chapter.archive` to `chapter.write`. These changes have no
functional relationship to chapter lifecycle — but they exist *only* because
WU-019's final grep invariants require zero matches for `/archive` and
`chapter.archive` under `services/api` (proposal §3 WU-019 post-check;
hookpoints §10). Without WU-019 landing, the rename has no motivation and
would churn a test file; with WU-019 landing, the rename is mandatory. So
ownership is PR B.

### `migrations/versions/wu-019_chapter_lifecycle.py` (seed grant) → PR B (WU-019)

The migration both creates the `chapters`/`chapter_transitions` tables
(clearly WU-019) and inserts the `discord-provisioner` global authority
grant that WU-020 consumes. Splitting the grant into a separate migration
for PR C would (a) create a second migration between WU-019 and WU-020
whose only purpose is data-seeding, and (b) risk deploying WU-020 against
a database where the grant has not yet been applied. The proposal §3
WU-019 pins this fixture to the WU-019 migration. Keeping it in PR B is
correct.

### `services/api/tests/test_activity_model.py`,
### `services/api/tests/test_endpoints_chapters_stubs.py`,
### `services/api/tests/test_conftest.py`,
### `services/api/tests/conftest.py` → PR B (WU-019)

Rewrite expectations against the legacy chapter substrate (integer ids,
in-memory stores, legacy routes). These edits are consequences of WU-019's
substrate replacement, not independent work.

### `.pipeline/*`, `plans/risk/slice-013-*.md`, `prototyping/slice-013-*` → PR A

15 slice-level artifacts (proposal rev 3, synthesis, risk audits, Phase 0
prototype). They describe the whole slice, not a single WU. Cleanest
allocation is to ship them with the first PR (WU-018) since the pipeline
gate for WU-018 is the same gate as the rest of SLICE-013. Alternative
allocation (split artifacts across PRs by mentioned WU) is viable but
increases review overhead with no benefit.

## 6. Test-suite independence check

Each concern has a dedicated test surface with no cross-concern imports:

- WU-018 tests (`test_chapter_templates.py`, foundation updates) only
  touch `chapter_templates` fixtures and the chapter-template router.
- WU-019 tests (`test_chapter_lifecycle.py`, `test_contracts_chapter_lifecycle.py`,
  deletions of `test_chapters.py` / `test_contracts_chapters.py`) only touch
  `chapters` / `chapter_transitions` / `authority_grants` rows; they do not
  import Discord code.
- WU-020 tests (`test_chapter_provisioning.py`, `test_main.py`,
  `test_settings.py`, `test_api_transport.py`) are entirely under
  `services/discord/tests` and mock the API via `AsyncClient` / ApiClient
  substitutes.

No test file straddles concerns.

## 7. Size signal

PR totals (including slice docs/prototypes): 57 files, +5534 / −1132 LOC.
Excluding the 15 pipeline/plan/prototype artifacts: 42 files of code+tests,
which is still beyond typical single-concern size and consistent with the
split recommendation. The task prompt's "2758+1132" figure appears to
refer to an earlier snapshot; the current diff is larger.

## 8. Summary

Recommend splitting PR #39 into three PRs in the order
**WU-018 → WU-019 → WU-020**, with file allocation as in §4. The dependency
graph is linear and acyclic. The legacy substrate replacement is tightly
coupled to WU-019 alone and stays inside PR B. No file needs to appear in
more than one PR.
