# SLICE-007 Shortcut Risk Assessment

Proposal under review: `worktrees/slice-007/.pipeline/proposal.md` (Revision 1).
Cross-references: `AGENTS.md` §"No Backwards Compatibility", "No Deferred Stubs",
and the already-merged SLICE-001..018 substrate under `services/api/app/` and
`services/discord/app/`.

## Overall: LOW

No shortcuts introduced. The proposal reuses the substrate rather than building
parallel paths, and every idempotency and error path is pinned to a named
exception plus an AC test.

## Focus-Area Findings

### 1. Hardcoded actors — LOW

- Member and trust service signatures accept an `actor` parameter resolved by
  `RequireAuthority` at the endpoint layer (`proposal.md:143`,
  `proposal.md:155`, `proposal.md:237`). There is no hardcoded `"system"` /
  `"member-service"` / `"trust-service"` literal injected into
  `mutate_entity()` from the SLICE-007 services.
- Existing hardcoded system actors live only in pre-existing substrate
  (`services/api/app/services/chapter_templates.py:32`,
  `services/api/app/services/chapter_roles.py:18`,
  `services/api/app/services/permissions.py:51`). SLICE-007 does not extend
  that pattern.
- `member-onboarder` is a seeded service actor in `authority_grants`, not a
  literal burned into service code. D9 binds the grant set
  (`member.read`, `member.write`, `trust.read`, `trust.write`) and the migration
  downgrade removes the seed (`proposal.md:200-204`), keeping it durable and
  reversible.
- Originating user attribution flows through body fields
  `originating_actor_kind` / `originating_actor_id` (`proposal.md:113-125`,
  `proposal.md:214-215`, `proposal.md:341-343`) rather than header spoofing,
  matching the SLICE-013 precedent in
  `services/discord/app/handlers/chapters.py:88`.
- Invariant test `test_no_hardcoded_system_actor_in_members_service`
  (`proposal.md:429`) locks this against regression.

### 2. Compatibility shims — LOW

- The repo contains no pre-existing `members` module in
  `services/api/app/services`, `repositories`, `contracts`, or `endpoints/`;
  there is no legacy code to shim. Verified by directory listing (no
  `members.py` in any of those layers) and by grep for `member` returning
  only roster/chapter/authority files plus test fixtures.
- The proposal adds one new table per aggregate (`members`, `trust_profiles`)
  with no parallel or transitional tables. No deprecated aliases, dual-write
  paths, or feature flags appear.
- `roster_entries.member_id` stays `TEXT` per D10 (`proposal.md:84-85`,
  `proposal.md:390`). The existing contract in
  `services/api/app/contracts/roster.py:20` already types it as
  `str = Field(min_length=1)`, so the proposal is not introducing a shim — it
  is leaving an existing loosely-typed column alone until a later slice does
  the explicit backfill + FK migration.

### 3. Deferred FK (D10) — LOW

- The deferral is legitimate cross-slice staging, not a shortcut covering a
  design break:
  - SLICE-018 already shipped `roster_entries.member_id` as `TEXT` holding
    `discord_user_id` strings, not `members.id` UUIDs
    (`services/api/app/contracts/roster.py:20` confirms the contract).
  - Introducing an FK to `members.id` now would require a backfill from
    Discord-user-id strings to UUID primary keys, which is a cross-slice data
    migration unrelated to onboarding.
  - D10 pins this out of scope and the Tradeoffs section explains the reason
    (`proposal.md:357-359`).
- No placeholder stub, TODO, or "will wire later" comment is prescribed. The
  later cleanup is a future slice with its own ticket, satisfying AGENTS.md
  §"No Deferred Stubs".
- **Observation (not a gate):** The deferred FK means there is no database-
  level integrity guarantee between `members.id` and `roster_entries.member_id`
  until the cleanup slice lands. Safe for SLICE-007 because roster entries
  keyed by `discord_user_id` strings don't reference `members.id` at all yet;
  worth tracking as an outstanding invariant gap on the roadmap, not as a
  SLICE-007 risk.

### 4. Fake transactions / mutate_entity + connection= bypass — LOW

- All member and trust mutations route through `mutate_entity()` with explicit
  `aggregate_type`, `aggregate_id`, `expected_version`, `scope_kind`, and
  `payload_allowlist` (`proposal.md:147-151`, `proposal.md:160-163`,
  `proposal.md:250-252`). That matches the chapter/roster/policy precedent at
  `services/api/app/services/mutations.py:58`.
- Repository write helpers are underscore-prefixed (`_insert_member`,
  `_update_member_status`, `_insert_trust_profile` —
  `proposal.md:137-139`, `proposal.md:230-231`), so services own the mutation
  boundary and no endpoint can sneak a direct write in.
- The `mutate_entity()` signature already supports an external `connection=`
  for composed transactions (`services/api/app/services/mutations.py:70`),
  but the proposal does not invoke that escape hatch. There is no custom
  transaction manager, no parallel `aggregate_heads` seed, and no manual
  `advance_head` call.

### 5. Deterministic compute without real tests — LOW

- D6 binds scoring determinism and the evaluator input (`TrustSignalsInput`
  plus the policy row's `rules` JSON) — no ambient clock, random source, or
  external state (`proposal.md:247-249`, synthesis D6).
- The policy content contract pins explicit fields the evaluator must consume
  (`rules.score_floor`, `score_ceiling`, `default_score`, typed `weights`,
  `flags`, `tiers` — `proposal.md:270-278`).
- Invalid shape is an explicit error path: `InvalidTrustPolicyError -> 409
  invalid_trust_policy` (`proposal.md:278-280`, `proposal.md:290-291`). This
  closes the "silent default / hidden mock" route because any missing or
  malformed rule field raises rather than falling back to a constant.
- AC2 includes the tests that would catch a hidden mock:
  `test_compute_trust_is_deterministic_given_same_signals_and_policy`,
  `test_compute_trust_returns_409_when_policy_shape_invalid`, and
  `test_trust_profile_stores_policy_version_id_for_replay`
  (`proposal.md:407-412`). Determinism is tested against real policy input,
  not an injected stub score.

### 6. Duplicated logic — LOW

Every cross-cutting concern reuses the SLICE-001..010 substrate:

- **Authority enforcement**: `RequireAuthority("member.read|write", "global")`
  and `RequireAuthority("trust.read|write", "global")` from
  `services/api/app/core/dependencies.py:129` (`proposal.md:168-181`,
  `proposal.md:283-293`). No new authority helper is added.
- **Actor propagation**: Reuses the `originating_actor_kind` /
  `originating_actor_id` body-field convention from SLICE-013 chapters
  (`services/discord/app/handlers/chapters.py:88`) and the
  `SERVICE_ACTOR_HEADERS` pattern at `services/discord/app/handlers/chapters.py:12`.
  Confirmed in repo: `SERVICE_ACTOR_HEADERS = {"X-Actor-Kind": "service",
  "X-Actor-Id": "discord-provisioner"}`; SLICE-007 only changes the
  `X-Actor-Id` to `member-onboarder`.
- **Payload allowlist**: Uses
  `payload_allowlist=set(request.model_dump(mode="json").keys())`
  (`proposal.md:345-346`), matching the identical pattern at
  `services/api/app/services/roster.py:159,277,371` and
  `services/api/app/services/chapters.py:160,265,394`.
- **Policy lookup**: Reuses `services/api/app/repositories/policies.py:10`
  rather than defining a parallel trust-only query (`proposal.md:232-233`,
  D4). Storing `policy_version_id` on the profile follows the versioned-policy
  replay pattern from SLICE-010.
- **Aggregate-head projection read**: The `_MEMBER_SELECT` and
  `_TRUST_PROFILE_SELECT` joins are structural copies of
  `_ROSTER_ENTRY_SELECT` at `services/api/app/repositories/roster.py:11-25`,
  which is the documented pattern, not duplication.

No parallel substrate, no forked authority check, no private actor-propagation
helper.

### 7. `POST /members` idempotency — LOW (real ON CONFLICT, no retry loop)

- Idempotency is a bounded two-step recovery, not a retry spin:
  1. Service reads by `discord_user_id`. If present, return with `200 OK`
     (`proposal.md:144-147`).
  2. Otherwise, `mutate_entity(... expected_version=0)`, which bootstraps the
     `aggregate_heads` row via `INSERT ... ON CONFLICT DO NOTHING`
     (confirmed at `services/api/app/services/mutations.py:97-110`).
  3. If a concurrent insert wins, `UniqueViolation` on `members.discord_user_id`
     is caught and the service re-reads (`proposal.md:150-151`). One re-read,
     deterministic return — no loop, no backoff.
- Trust compute uses the same shape but pins a larger exception set:
  `StaleMutationError | UniqueViolation -> re-read existing profile and
  return` (`proposal.md:259-261`), with an explicit re-raise clause if the
  re-read is unexpectedly absent (`proposal.md:253-255`) so failures are not
  silently swallowed.
- AC tests verify both cases:
  `test_create_member_idempotent_on_duplicate_discord_user_id`
  (`proposal.md:401`),
  `test_compute_trust_returns_existing_profile_on_retry`, and
  `test_compute_trust_concurrent_same_member_returns_same_profile_to_both`
  (`proposal.md:408-409`).

## Recommendation

**Accept.** The proposal ships cleanly on the SLICE-001..010 substrate with
no hardcoded actors, no compatibility shims, no parallel mutation paths, no
hidden policy defaults, and no retry-loop idempotency. The deferred roster FK
(D10) is a legitimate cross-slice staging decision, explicitly owned by a
later cleanup slice, and does not read as a shortcut. No proposal changes
required for shortcut-risk clearance.
