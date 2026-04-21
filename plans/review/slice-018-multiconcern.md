# SLICE-018 Phase 8 — Multi-Concern Review (PR #43)

Reviewed: 2026-04-20
PR: `feat/slice-018-roster-management` (#43), 19 files, +3447 / −1160 LOC
Inputs: `.pipeline/proposal.md` rev 1, `.pipeline/implementation.md`,
`gh pr diff 43`, `AGENTS.md` §"One Concern Per PR" (lines 178–193).

## 1. Verdict

**`MULTI_CONCERN_RECOMMEND_SPLIT`**

PR #43 bundles two work units that are reviewable and deployable as
independent concerns with a linear producer/consumer edge:

- **WU-033** (roster lifecycle API + migration + legacy foundation
  replacement) is self-contained in `services/api` and `migrations/`. It
  can merge atomically on `main`: migration head advances, new endpoints
  answer, legacy `test_roster_foundation.py` is replaced by
  `test_roster.py`, and the `roster-syncer` global grant is seeded.
- **WU-034** (Discord roster role sync handler) is self-contained in
  `services/discord`. It is a pure API consumer via the SLICE-006
  `ApiClient`: it has no compile-time dependency on API Python symbols,
  only a run-time dependency on (a) the `POST /api/v1/roster-entries/{id}/sync-failure`
  endpoint shape from WU-033 and (b) the seeded `roster-syncer` global
  `roster.write` grant from the WU-033 migration.

Against AGENTS.md §"One Concern Per PR":
- "A PR that touches N independent concerns should be split into N PRs" —
  the two WUs touch disjoint code paths (`services/api` + `migrations/`
  vs. `services/discord`) and disjoint test suites (`services/api/tests/`
  vs. `services/discord/tests/`).
- "Dependency order matters — if PR B depends on PR A, A merges first" —
  WU-033 → WU-034 is a linear edge, not a cycle.
- "Additive changes go before behavioral changes" — the Discord handler
  is a new behavioral consumer; the API surface + grant it consumes is
  additive and lands first.

The legacy foundation replacement called out in Focus Area 3 (delete
`test_roster_foundation.py`, rename public repository helpers to
underscore-prefixed internals, remove `read_roster_entry` /
`transition_roster_status`, replace `RosterEntryCreate.status` path) is
scoped **entirely** to WU-033. It is tightly coupled to the new service
module and migration within WU-033, but uncoupled from WU-034. Keep the
deletion inside PR A with the addition that replaces it.

This matches the SLICE-013 precedent (PR #39 split WU-018 → WU-019 →
WU-020 with the same producer/consumer shape).

## 2. Concerns enumerated

### Concern A — WU-033: roster lifecycle API + migration + legacy replacement

Adds `migrations/versions/wu-033_roster.py` (extends `roster_entries`,
creates `roster_transitions`, adds partial unique index
`uq_roster__chapter_member_active`, adds composite role FK, seeds
`roster-syncer` global `roster.read` + `roster.write` grant), the four
roster lifecycle endpoints (`POST /roster-entries`, `GET /{id}`,
`POST /{id}/transitions`, `POST /{id}/sync-failure`) with two-tier
authority split (chapter-scoped user-actor operator surface vs.
global-scoped service-actor `/sync-failure`), `mutate_entity`-backed
transitions with `If-Match` OCC, `roster_transitions` projection in the
same transaction, and atomic `enqueue_effect` for sync-failure with
idempotency key `roster_sync_retry:{entry}:{transition_id}`. In the same
diff it replaces the WU-007C foundation contracts / repository / service
in place, removes the public `insert_roster_entry` / `fetch_roster_entry`
/ `update_roster_status` / `read_roster_entry` /
`transition_roster_status` symbols, drops the public
`RosterEntryCreate.status` path, and deletes
`services/api/tests/test_roster_foundation.py` (314 lines) in favor of
the new `services/api/tests/test_roster.py` (694 lines).

Touches only `services/api`, `migrations/`, and the slice-wide pipeline
artifacts. Does not import Discord code.

### Concern B — WU-034: Discord roster role sync handler

Adds `services/discord/app/contracts/roster.py` (`RosterSyncEvent`,
`RosterSyncResult`), `services/discord/app/handlers/roster.py`
(`sync_roster`, idempotent add/remove, `SERVICE_ACTOR_HEADERS`,
name-based role rediscovery, `RosterSyncFailure` categorization, API
callback on failure), and `services/discord/tests/test_roster_sync.py`
(152 lines, fake guild / member / API client).

Calls WU-033's `/sync-failure` endpoint via the SLICE-006
`ApiTransportRequest` contract with `If-Match`, `X-Actor-Kind: service`,
`X-Actor-Id: roster-syncer` headers. No code inside `services/api` or
`migrations/`. No cross-service Python imports.

## 3. Recommended PR ordering (topological)

```
PR A (WU-033) ──▶ PR B (WU-034)
```

Forcing edges (all A→B, none B→A):

- B → A runtime: the handler POSTs `/api/v1/roster-entries/{id}/sync-failure`;
  the route is added in PR A.
- B → A authority: the handler sends `X-Actor-Id: roster-syncer`; the
  endpoint requires `actor_kind="service"`, `actor_id="roster-syncer"`,
  and global-scoped `roster.write`. The matching `authority_grants` row
  is seeded by the WU-033 migration's `INSERT INTO authority_grants ...
  WHERE NOT EXISTS` block (migrations/versions/wu-033_roster.py:134-169).
  Without PR A the grant is missing and the handler's failure path 403s.
- B → A contract: `RosterSyncFailureRequest` field names
  (`transition_id`, `member_discord_user_id`, `operation`,
  `failed_at_step`, `desired_discord_role_ids`, `error_type`,
  `originating_actor_*`) are defined in PR A's
  `services/api/app/contracts/roster.py`; the handler serializes the
  same wire shape.

No reverse edges. PR A's `354 passed` API suite runs green without any
Discord code; PR B's `59 passed` Discord suite mocks the API transport
and runs green without a live API.

## 4. File allocation (every file → exactly one PR)

### PR A — WU-033 (roster API + migration + legacy replacement) [9 code/test files + 7 slice docs]

Code:
- `migrations/versions/wu-033_roster.py` (new)
- `services/api/app/api/v1/endpoints/roster.py` (new)
- `services/api/app/api/v1/router.py` (add `roster` include)
- `services/api/app/contracts/roster.py` (extend + add transition /
  sync-failure contracts + typed errors)
- `services/api/app/repositories/roster.py` (rewrite helpers as
  underscore-prefixed internals, add transition insert + lock-for-update)
- `services/api/app/services/roster.py` (rewrite into
  create/get/transition/record-sync-failure using `mutate_entity` and
  `enqueue_effect`)

Tests:
- `services/api/tests/conftest.py` (add `roster_transitions` to truncate list)
- `services/api/tests/test_roster.py` (new, 694 lines)
- `services/api/tests/test_roster_foundation.py` (DELETE, 314 lines)

Slice-level docs (see §5):
- `.pipeline/implementation.md`
- `.pipeline/proposal.md`
- `.pipeline/research.md`
- `.pipeline/synthesis.md`
- `plans/risk/slice-018-audit.md`
- `plans/risk/slice-018-scope.md`
- `plans/risk/slice-018-shortcut.md`

### PR B — WU-034 (Discord roster sync handler) [3 files]

Code:
- `services/discord/app/contracts/roster.py` (new)
- `services/discord/app/handlers/roster.py` (new)

Tests:
- `services/discord/tests/test_roster_sync.py` (new)

Total allocation: 9 + 3 = 12 code/test files + 7 slice docs = 19 files,
matches PR #43's file count.

## 5. Straddling files — flags and justifications

### `migrations/versions/wu-033_roster.py` (seed grant) → PR A (WU-033)

The migration both creates the roster lifecycle schema (clearly WU-033)
and seeds the `roster-syncer` global `authority_grants` row that WU-034
consumes. Splitting the grant into a separate migration for PR B would
(a) create an additional migration head between PR A and PR B whose only
job is data seeding, and (b) risk deploying the Discord handler against
a database where the grant is missing, which would hard-403 every
failure report. Proposal §3 WU-033 and D10 pin this seed to the WU-033
migration. Keep it in PR A.

### `services/api/tests/conftest.py` → PR A (WU-033)

Single-line change adding `roster_transitions` to the truncate list.
That table is created by the WU-033 migration, so the fixture update is
a consequence of PR A.

### `services/api/tests/test_roster_foundation.py` (DELETE) → PR A (WU-033)

Under AGENTS.md "A large deletion is its own PR, separate from the
addition that replaces it" the question is whether this deletion should
be a third PR. It should not: the 314-line foundation file exists
*because* the WU-007C foundation shipped public helpers that WU-033
replaces with underscore-prefixed internals in the same module
(`services/api/app/repositories/roster.py`,
`services/api/app/services/roster.py`). The same module cannot export
both APIs; splitting the delete away from the rewrite would leave one PR
with imports pointing at symbols that no longer exist. This is the same
coupling precedent that SLICE-013 PR B established for the
`InMemoryChapterRepository` delete, and the multi-concern review there
accepted bundling the delete with its replacement inside a single PR.

### `.pipeline/*`, `plans/risk/slice-018-*.md` → PR A

7 slice-level artifacts (proposal rev 1, synthesis, research, risk
audits, implementation notes). They describe the whole slice, not a
single WU. Cleanest allocation is to ship them with PR A since PR A
lands the substrate that the artifacts primarily describe; an
alternative split by WU is viable but adds review overhead.

## 6. Test-suite independence check

Each concern has a dedicated test surface with no cross-concern imports:

- WU-033 tests (`test_roster.py`, deletion of `test_roster_foundation.py`,
  `conftest.py` truncate update) live entirely under `services/api/tests/`.
  They import only `services/api/app/*` symbols. They do not import
  Discord code or reference `services/discord`.
- WU-034 tests (`test_roster_sync.py`) live entirely under
  `services/discord/tests/`. They import only `services/discord/app/*`
  and a fake `api_client`; they do not import API code or hit a live
  API. The sync-failure API call shape is asserted against captured
  `ApiTransportRequest` records, not against a running server.

No test file straddles concerns.

## 7. Size signal

PR totals: 19 files, +3447 / −1160 LOC. Excluding the 7 pipeline /
risk artifacts (~1.2k LOC), code+tests split is roughly:

- PR A (WU-033): ~2.1k added / 1.1k removed across 9 files
  (migration 201, endpoints 247, services 389, repository 130,
  contracts 54, tests 694, conftest 1, router 2, − foundation test 314)
- PR B (WU-034): ~460 added across 3 files
  (handler 263, contracts 46, tests 152)

PR A is within typical single-concern size; PR B is small. The split is
natural and does not require splitting WU-033 further.

## 8. Summary

Recommend splitting PR #43 into two PRs in the order **WU-033 →
WU-034**, with file allocation as in §4. The dependency graph is a
single A→B edge and acyclic. The legacy roster-foundation replacement
stays inside PR A alongside the addition that replaces it. No file
needs to appear in more than one PR.
