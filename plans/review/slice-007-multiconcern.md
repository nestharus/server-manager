# SLICE-007 Phase 8 — Multi-Concern Review (PR #46)

Reviewed: 2026-04-21
PR: `feat/slice-007-member-onboarding` (#46), 25 files, +4206 / −856 LOC
Inputs: `.pipeline/proposal.md` rev 1, `.pipeline/implementation.md`,
`gh pr diff 46`, `AGENTS.md` §"PR Review Workflow" (lines 178–193).

## 1. Verdict

**`MULTI_CONCERN_RECOMMEND_SPLIT`**

PR #46 bundles three work units that are reviewable and deployable as
independent concerns with a linear producer/consumer chain:

- **WU-011** (Member aggregate + status API + migration) is self-contained
  in `services/api` and `migrations/`. It can merge atomically: the
  `members` table and `aggregate_heads` bootstrap land, the four member
  endpoints answer, and 375 API tests run green without any trust or
  Discord code.
- **WU-012** (Trust profile + initial compute API + migration) is
  self-contained in `services/api` and `migrations/` on top of WU-011.
  The `trust_profiles` table FK-references `members.id`, and the
  `wu-012_trust.py` migration seeds the single `member-onboarder` global
  grant with all four permissions (`member.read`, `member.write`,
  `trust.read`, `trust.write`).
- **WU-013** (Discord member-join onboarding handler) is self-contained
  in `services/discord`. It is a pure API consumer via the SLICE-006
  `ApiClient`: it has no compile-time dependency on API Python symbols,
  only a run-time dependency on (a) `GET/POST /api/v1/members[/…]` and
  `POST /api/v1/trust/compute/{member_id}` shapes from WU-011/WU-012 and
  (b) the seeded `member-onboarder` global grant from the WU-012
  migration.

Against AGENTS.md §"PR Review Workflow":

- "A PR that touches N independent concerns should be split into N PRs" —
  the three WUs touch disjoint code paths (`services/api` + `migrations/`
  for WU-011 and WU-012 in non-overlapping modules, vs. `services/discord`
  for WU-013) and disjoint test suites (`test_members.py`,
  `test_trust.py`, `test_onboarding.py`).
- "Dependency order matters — if PR B depends on PR A, A merges first" —
  WU-011 → WU-012 → WU-013 is a linear chain, not a cycle.
- "Additive changes go before behavioral changes" — WU-011 adds the
  member substrate; WU-012 adds trust substrate on top; WU-013 is the
  behavioral Discord consumer that depends on both.

This matches the SLICE-013 precedent (PR #39/#41/#42 split WU-018 →
WU-019 → WU-020 with the same chained producer/consumer shape) and the
SLICE-018 precedent (PR #44/#45 split WU-033 → WU-034).

## 2. Concerns enumerated

### Concern A — WU-011: Member aggregate + status API + migration

Adds `migrations/versions/wu-011_members.py` (creates `members` with
UUID `id`, `UNIQUE discord_user_id`, `status CHECK` in
`active/suspended/departed`, no `version` column — version is read via
join on `aggregate_heads` with `aggregate_type='member'`). Adds the four
member endpoints (`POST /members`, `GET /members/{id}`,
`GET /members/by-discord/{discord_user_id}`, `PATCH /members/{id}/status`)
with global-scoped `member.read` / `member.write` authority, idempotent
get-or-create on `discord_user_id` (catches `UniqueViolation` and
re-reads), and `If-Match` OCC on status patches via `mutate_entity`.
Registers the members router, adds `members` to the test truncate list,
and adds `test_members.py`.

Touches only `services/api/app/contracts/members.py`,
`services/api/app/repositories/members.py`,
`services/api/app/services/members.py`,
`services/api/app/api/v1/endpoints/members.py`, the members hunks of
`services/api/app/api/v1/router.py` and `services/api/tests/conftest.py`,
`migrations/versions/wu-011_members.py`, and
`services/api/tests/test_members.py`. Does not import trust or Discord
code.

### Concern B — WU-012: Trust profile + initial compute API + migration

Adds `migrations/versions/wu-012_trust.py` (creates `trust_profiles`
with `member_id UUID PRIMARY KEY REFERENCES members(id) ON DELETE
RESTRICT`, `policy_version_id UUID REFERENCES policy_versions(id)`,
JSONB `signals`, deterministic compute contract, plus
`ix_trust_profiles__policy_version_id` for replay). The same migration
idempotently seeds the `member-onboarder` global `authority_grants` row
with the full `["member.read", "member.write", "trust.read",
"trust.write"]` permission list (proposal D9 pins the seed to this
migration).

Adds the two trust endpoints (`POST /api/v1/trust/compute/{member_id}`,
`GET /api/v1/trust/{member_id}`) with global-scoped `trust.read` /
`trust.write` authority, deterministic policy evaluation over the fixed
`TrustSignalsInput` shape (D5), `StaleMutationError | UniqueViolation →
re-read existing profile` recovery for concurrent first-compute
redelivery (D11), typed `409 no_trust_policy_configured` and
`409 invalid_trust_policy`, and pins `policy_version_id` on the profile
for replay. Registers the trust router, adds `trust_profiles` to the
truncate list, and adds `test_trust.py`.

Touches only `services/api/app/contracts/trust.py`,
`services/api/app/repositories/trust.py`,
`services/api/app/services/trust.py`,
`services/api/app/api/v1/endpoints/trust.py`, the trust hunks of
`services/api/app/api/v1/router.py` and `services/api/tests/conftest.py`,
`migrations/versions/wu-012_trust.py`, and
`services/api/tests/test_trust.py`. Reads member state only through the
WU-011 member repository/service at runtime — no direct SQL coupling to
`members` beyond the FK.

### Concern C — WU-013: Discord member-join onboarding handler

Adds `services/discord/app/contracts/onboarding.py` (`MemberJoinEvent`,
`MemberJoinOutcomeRead`),
`services/discord/app/handlers/onboarding.py` (`handle_member_join`:
`GET /members/by-discord/{id}` → on 404 `POST /members` → `POST
/trust/compute/{member_id}` → derive `intake_required` from `tier`,
with `X-Actor-Kind: service` / `X-Actor-Id: member-onboarder` headers
and originating-user propagation in request bodies), Discord bot wiring
in `services/discord/app/core/bot.py` (converts `discord.Member` into
`MemberJoinEvent` and invokes the handler), and
`services/discord/tests/test_onboarding.py` (270 lines, fake API
client / member).

Calls WU-011 + WU-012 endpoints via the SLICE-006 `ApiTransportRequest`
contract with service-actor headers. No code inside `services/api` or
`migrations/`. No cross-service Python imports.

## 3. Recommended PR ordering (topological)

```
PR A (WU-011) ──▶ PR B (WU-012) ──▶ PR C (WU-013)
```

Forcing edges (all forward, none reverse):

### B → A forcing edges

- **Schema FK**: `trust_profiles.member_id` is declared
  `REFERENCES members(id) ON DELETE RESTRICT`
  (`migrations/versions/wu-012_trust.py:20-24`). Without WU-011's
  `members` table the migration fails to apply.
- **Migration ordering**: `wu-012_trust.py` sets
  `down_revision = "wu_011_members"` (line 11), so Alembic will not
  attempt to apply WU-012 ahead of WU-011.
- **Runtime precondition**: `compute_trust()` verifies the member
  exists through the member repository before writing a profile
  (proposal §WU-012 Service), so PR B's API surface is non-functional
  without PR A's `members` aggregate and endpoints.

### C → B forcing edges

- **Runtime endpoint consumption**: the handler POSTs
  `/api/v1/trust/compute/{member_id}` — that route is added in PR B.
  Without PR B the Discord handler's trust step hard-404s.
- **Runtime authority**: the handler sends `X-Actor-Kind: service` /
  `X-Actor-Id: member-onboarder`. The `member-onboarder` authority
  grant (with all four permissions) is seeded by PR B's migration
  (`migrations/versions/wu-012_trust.py:61-96`). Without PR B the
  grant is missing and every API call from the handler 403s.
- **Contract shape**: `TrustSignalsInput` field names
  (`discord_account_age_days`, `has_avatar`, `has_verified_badge`,
  `account_flags`, `originating_actor_*`) are defined in PR B's
  `services/api/app/contracts/trust.py`; the Discord event type mirrors
  the same wire shape in `MemberJoinEvent.signals`.

### C → A forcing edges (transitive, enforced through B)

- The handler also calls `GET /members/by-discord/{discord_user_id}`
  and `POST /members` — routes added in PR A. Because PR B depends on
  PR A, PR C merging after PR B automatically has the member surface
  available.

No reverse edges. PR A's API suite runs green without trust or Discord
code; PR B's API suite runs green without Discord code; PR C's Discord
suite mocks the API transport and runs green without a live API.

## 4. File allocation (every file → exactly one PR)

### PR A — WU-011 (member API + migration) [8 code/test hunks + 7 slice docs]

Code:
- `migrations/versions/wu-011_members.py` (new)
- `services/api/app/api/v1/endpoints/members.py` (new)
- `services/api/app/api/v1/router.py` — **members hunks only** (add
  `members` import in the endpoints import block; add
  `router.include_router(members.router, tags=["members"])`)
- `services/api/app/contracts/members.py` (new)
- `services/api/app/repositories/members.py` (new)
- `services/api/app/services/members.py` (new)

Tests:
- `services/api/tests/conftest.py` — **`members` hunk only** (add
  `"members"` to the truncate list)
- `services/api/tests/test_members.py` (new)

Slice-level docs (see §5):
- `.pipeline/implementation.md`
- `.pipeline/proposal.md`
- `.pipeline/research.md`
- `.pipeline/synthesis.md`
- `plans/risk/slice-007-audit.md`
- `plans/risk/slice-007-scope.md`
- `plans/risk/slice-007-shortcut.md`

### PR B — WU-012 (trust API + migration + service-actor grant seed) [8 code/test hunks]

Code:
- `migrations/versions/wu-012_trust.py` (new — includes the
  `member-onboarder` grant seed with all four permissions)
- `services/api/app/api/v1/endpoints/trust.py` (new)
- `services/api/app/api/v1/router.py` — **trust hunks only** (add
  `trust` import; add
  `router.include_router(trust.router, tags=["trust"])`)
- `services/api/app/contracts/trust.py` (new)
- `services/api/app/repositories/trust.py` (new)
- `services/api/app/services/trust.py` (new)

Tests:
- `services/api/tests/conftest.py` — **`trust_profiles` hunk only**
  (add `"trust_profiles"` to the truncate list)
- `services/api/tests/test_trust.py` (new)

### PR C — WU-013 (Discord member-join handler) [4 files]

Code:
- `services/discord/app/contracts/onboarding.py` (new)
- `services/discord/app/core/bot.py` (add `on_member_join` listener
  wiring)
- `services/discord/app/handlers/onboarding.py` (new)

Tests:
- `services/discord/tests/test_onboarding.py` (new)

Total allocation: 8 + 8 + 4 = 20 code/test hunks + 7 slice docs +
straddler resolution on `router.py` / `conftest.py` = every one of the
25 files in PR #46 accounted for without duplication.

## 5. Straddling files — flags and justifications

### `services/api/app/api/v1/router.py` → split across PR A and PR B

The diff has two clearly separable hunks: one adds `members` to the
import tuple and an `include_router(members.router, …)` line; the other
adds `trust` to the import tuple and `include_router(trust.router, …)`.
Splitting each hunk into its own PR cleanly mirrors the WU boundary and
avoids introducing an import for a module that does not yet exist in
the respective PR branch.

### `services/api/tests/conftest.py` → split across PR A and PR B

Same pattern: the truncate-list addition adds `"trust_profiles"` and
`"members"` in a single diff. Each table is created by its own
migration, so each fixture line travels with its creating migration.

### `migrations/versions/wu-012_trust.py` (seed grant covers `member.*`) → PR B

The `member-onboarder` grant seeded by `wu-012_trust.py:61-96`
includes `member.read` and `member.write` alongside `trust.read` and
`trust.write`. Two options were considered:

1. Keep the full four-permission grant inside `wu-012_trust.py` (as
   implemented and as pinned by proposal D9).
2. Split the grant — seed `member.*` in `wu-011_members.py` and
   `trust.*` in `wu-012_trust.py`.

Option 1 is preferred and kept as-is. Rationale: (a) the grant exists
solely to unblock the WU-013 Discord service actor; if WU-013 never
ships, the grant is harmless unused authority state, so there is no
value in landing it earlier. (b) A single seed statement is
idempotent via `WHERE NOT EXISTS … permissions @> […]` containment on
the full permission list; splitting into two seeds across two
migrations would require two independent `NOT EXISTS` guards and a
different revocation strategy in the two downgrade paths. (c) The
proposal D9 decision table explicitly pins the grant seed to the
`wu-012_trust.py` migration. Keep the grant in PR B.

The parallel to SLICE-018 PR A's `roster-syncer` grant (seeded in
`wu-033_roster.py` and consumed by PR B) is exact: the migration that
creates the final aggregate seeds the service-actor grant its
downstream consumer will use.

### `.pipeline/*`, `plans/risk/slice-007-*.md` → PR A

7 slice-level artifacts (proposal rev 1, synthesis, research,
implementation notes, three risk reports). They describe the whole
slice, not a single WU. Cleanest allocation is to ship them with PR A
since PR A lands the foundational member substrate that the artifacts
primarily describe. An alternative split by WU is viable but adds
review overhead across three PRs. This matches the SLICE-018 review
conclusion.

### `services/discord/app/core/bot.py` → PR C

The `on_member_join` listener wiring is additive (22 new lines, no
edits to existing behavior) and is the entry point that drives
`handle_member_join`. It cannot be separated from the handler it
invokes.

## 6. Test-suite independence check

Each concern has a dedicated test surface with no cross-concern
imports:

- **WU-011 tests** (`test_members.py`, `conftest.py` `members`
  truncate hunk) live under `services/api/tests/`. They import only
  `services/api/app/*` symbols. They do not reference trust or
  Discord code.
- **WU-012 tests** (`test_trust.py`, `conftest.py` `trust_profiles`
  truncate hunk) live under `services/api/tests/`. They import only
  `services/api/app/*` symbols (including the WU-011 member
  repository/service, which PR B's branch base includes once PR A is
  merged). They do not reference Discord code.
- **WU-013 tests** (`test_onboarding.py`) live entirely under
  `services/discord/tests/`. They import only `services/discord/app/*`
  and a fake `api_client`; they do not import API code or hit a live
  API. The member-create and trust-compute API call shapes are
  asserted against captured `ApiTransportRequest` records, not against
  a running server.

No test file straddles concerns.

## 7. Size signal

PR totals: 25 files, +4206 / −856 LOC. Excluding the 7 pipeline /
risk artifacts (~2.2k LOC of the additions and essentially all of the
−856 deletions, since `.pipeline/*` files carry SLICE-018 → SLICE-007
rewrites), code+tests split is roughly:

- PR A (WU-011): ~1.07k added across 8 hunks
  (migration 47, endpoints 173, contracts 72, repository 105, service
  232, tests 436, router +2, conftest +1)
- PR B (WU-012): ~1.20k added across 8 hunks
  (migration 110 including grant seed, endpoints 107, contracts 58,
  repository 65, service 264, tests 595, router +2, conftest +1)
- PR C (WU-013): ~0.44k added across 4 files
  (handler 111, contracts 38, bot wiring 22, tests 270)

All three PRs are within typical single-concern size. PR C is small
but irreducible — the handler, its contracts, its bot-listener entry
point, and its tests form one atomic behavioral unit.

## 8. Summary

Recommend splitting PR #46 into three PRs in the order **WU-011 →
WU-012 → WU-013**, with file allocation as in §4. The dependency
graph is a linear chain (A → B → C) and acyclic. Both straddling files
(`router.py`, `conftest.py`) split cleanly along WU boundaries into
distinct hunks. The `member-onboarder` service-actor grant stays
inside PR B's migration per proposal D9, matching the SLICE-018
`roster-syncer` precedent. No file needs to appear in more than one
PR.
