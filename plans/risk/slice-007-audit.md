# SLICE-007 Audit Risk Assessment

## Overall: LOW

The proposal is sound across all eight audit focus areas. Concurrency, OCC,
audit attribution, and migration safety are handled with patterns already proven
in `chapters`, `roster`, and the `mutate_entity()` substrate. No data-loss,
corruption, or security exposure risks were identified that warrant revision.

## Focus Area Findings

### 1. `UNIQUE(discord_user_id)` + idempotent `POST /members` — LOW

Two concurrent `POST /members` for the same `discord_user_id` generate
**different** server-side UUIDs, so each request bootstraps a distinct
`aggregate_heads` row and they do **not** serialize on the head lock. The loser
fails on the projection-side `UNIQUE(discord_user_id)` constraint with
`UniqueViolation`. The service catches that and re-reads by `discord_user_id`
(`.pipeline/proposal.md:150-151`, D11 at `.pipeline/proposal.md:391`).

The recovery is via retry-read, not `ON CONFLICT DO UPDATE`. That is the right
choice here: the proposal does not want to overwrite or merge data on duplicate
delivery; it wants get-or-create semantics, and retry-read returns the existing
row exactly as committed. Because the head bootstrap, accepted-action insert,
and member row insert all run inside the `mutate_entity()` transaction
(`services/api/app/services/mutations.py:94-185`), the `UniqueViolation` rolls
back the orphan head row as well — no leaked `aggregate_heads(member, <new
UUID>)` rows. The failure-audit path runs in a separate transaction
(`services/api/app/services/mutations.py:206-224`) and writes one `failed`
action attributing the rejected attempt to the actor. Symmetric to the existing
`chapters.create` pattern (`services/api/app/services/chapters.py:163-164`).

AC coverage: `test_create_member_idempotent_on_duplicate_discord_user_id`,
`test_unique_discord_user_id_enforced`.

### 2. Trust compute idempotency under concurrency — LOW

`POST /trust/compute/{member_id}` uses `aggregate_id=str(member_id)` so two
concurrent first-compute requests serialize on the **same** `aggregate_heads`
row. The `INSERT ... ON CONFLICT DO NOTHING` plus `SELECT ... FOR UPDATE` in
`mutate_entity()` (`services/api/app/services/mutations.py:97-116`) guarantees
exactly one writer commits at `expected_version=0`; the loser observes
`current_seq=1`, fails the version check
(`services/api/app/services/mutations.py:123-148`), and gets a
`StaleMutationError` rather than ever reaching `mutate_projection`. The proposal
catches that and re-reads the now-committed profile
(`.pipeline/proposal.md:252-261`, D11 at `.pipeline/proposal.md:391`).

The additional `UniqueViolation` catch on the same path is belt-and-suspenders
for the unlikely case where the head check passes for two writers (e.g. due to
isolation-level surprises) — the `trust_profiles.member_id PRIMARY KEY` then
prevents a duplicate row. Either exception resolves to the same re-read-and-
return outcome. The pinned recovery list (`StaleMutationError | UniqueViolation
-> re-read existing profile and return`) and the re-raise on unexpectedly absent
re-read (`.pipeline/proposal.md:255-258`) are correct. AC coverage:
`test_compute_trust_concurrent_same_member_returns_same_profile_to_both`.

### 3. Trust policy version resolution race — LOW

`compute_trust()` fetches the latest global `policy_type='trust'` row and uses
its `policy_version_id` and `rules` content as scoring input
(`.pipeline/proposal.md:241-263`). The proposal does not require the policy
fetch to run inside the `mutate_entity()` transaction. That is acceptable
because:

- The same fetched policy row provides **both** the `rules` used for scoring
  **and** the `policy_version_id` persisted on `trust_profiles`. The stored row
  is internally consistent: the score reflects the policy version it cites.
- If a `policy_versions` row is rotated between fetch and projection write, the
  FK `policy_version_id REFERENCES policy_versions(id) ON DELETE RESTRICT`
  (`.pipeline/proposal.md:194`) prevents the cited version from being deleted
  out from under the write. New versions are additive (a new row with a higher
  `version_number`); the captured `policy_version_id` continues to resolve.
- D3 idempotency means each member's profile is pinned to one
  `policy_version_id` for the life of SLICE-007. Recompute against a newer
  policy is explicitly out of scope (D12, owned by SLICE-016).

Missing policy raises `NoTrustPolicyConfiguredError -> 409
{"code":"no_trust_policy_configured"}` and invalid policy shape raises
`InvalidTrustPolicyError -> 409 {"code":"invalid_trust_policy"}` rather than
silent defaulting (`.pipeline/proposal.md:243-244`,
`.pipeline/proposal.md:278-280`, `.pipeline/proposal.md:290-291`). Both are
covered by AC tests.

### 4. Determinism of trust compute — LOW

D6 forbids reading ambient time, random values, or mutable external state
during scoring (`.pipeline/synthesis.md:50-54`,
`.pipeline/proposal.md:248-251`). The compute function is pure over
`(TrustSignalsInput, policy.rules) -> (score, tier)`. `created_at`/`updated_at`
on `trust_profiles` come from `CURRENT_TIMESTAMP` defaults applied at insert
time and are not part of the deterministic output surface — they document when
the profile was committed, not the score. AC coverage:
`test_compute_trust_is_deterministic_given_same_signals_and_policy`,
`test_compute_trust_creates_profile_with_current_policy_version`.

### 5. Member status PATCH OCC — LOW

`PATCH /api/v1/members/{id}/status` requires `If-Match`
(`.pipeline/proposal.md:181`), routes through `mutate_entity()` against
`aggregate_type='member'`, and maps stale version to `412`, invalid/no-op
transition to `409`, and missing member to `404`
(`.pipeline/proposal.md:155-163`, `.pipeline/proposal.md:178-182`). The D2
transition matrix — including `suspended -> departed` — is enforced server-side
in `patch_member_status()`. The state-machine validation runs **inside**
`mutate_projection`, which means the head lock is held when the transition
check runs, so two concurrent transitions for the same member are serialized
and the loser observes the post-commit state. AC coverage:
`test_patch_member_status_with_current_version_succeeds_and_advances_version`,
`test_patch_member_status_returns_412_on_stale_version`.

### 6. `member-onboarder` grant seeded in `wu-012` (not `wu-011`) — LOW

The proposal seeds the `member-onboarder` global grants in `wu-012_trust.py`
(`.pipeline/proposal.md:199-203`, D9 at `.pipeline/proposal.md:389`), even
though the `members` table itself is created in `wu-011_members.py`. A
deploy that applies only `wu-011` would expose `POST /members` and friends, but
`member-onboarder` would not yet hold any grants and the Discord onboarding
handler would receive `403 authority_decision_denied` from
`RequireAuthority("member.write", "global")`
(`services/api/app/core/dependencies.py:86-95`).

This is acceptable because:

- Alembic applies migrations sequentially as a single deploy step; partial
  application is an operational anomaly, not a steady state.
- A 403 response is a fail-closed authorization denial — no member is created,
  no trust profile is computed, no audit row is written with the wrong actor.
  There is no data loss or corruption path. The handler propagates the API
  failure as the documented onboarding failure
  (`.pipeline/proposal.md:341-342`).
- Other service grants in this codebase follow the same convention (e.g.
  `roster-syncer` is seeded in `wu-033_roster.py:134-159` alongside the
  feature it enables, not in the foundation migration).

The invariant test `test_member_onboarder_service_actor_has_read_and_write_
grants_after_migration` (`.pipeline/proposal.md:428`) guards the post-migration
grant surface, which is the meaningful checkpoint.

### 7. Audit `payload_allowlist` for member create, status patch, trust compute — LOW

The proposal uses `payload_allowlist=set(request.model_dump(mode="json").keys())`
for all three mutations (`.pipeline/proposal.md:344-347`), matching the pattern
in `services/api/app/services/chapters.py:160` and
`services/api/app/services/roster.py:159`. Concretely:

- `MemberCreate.model_dump().keys()` = `{discord_user_id, joined_at,
  originating_actor_kind, originating_actor_id}`. All four are allowlisted
  and survive `_redact_payload()` (`services/api/app/services/mutations.py:37-48`).
- `MemberStatusPatch.model_dump().keys()` = `{status, reason,
  originating_actor_kind, originating_actor_id}`. All allowlisted.
- `TrustSignalsInput.model_dump().keys()` = `{discord_account_age_days,
  has_avatar, has_verified_badge, account_flags, originating_actor_kind,
  originating_actor_id}`. All allowlisted; the JSONB `signals` column on
  `trust_profiles` stores the same shape per `.pipeline/proposal.md:262-263`.

Audit reviewers can therefore reconstruct who triggered each mutation, what
they sent, and what state-change payload was committed.

### 8. Originating actor propagation — LOW

The Discord handler sends `X-Actor-Kind: service` / `X-Actor-Id:
member-onboarder` headers (`.pipeline/proposal.md:317-318`, D8 at
`.pipeline/proposal.md:388`) and additionally puts the originating Discord
user ID in the request body via `originating_actor_kind="user"` /
`originating_actor_id=<discord_user_id>` for member create, status patch, and
trust compute (`.pipeline/proposal.md:341-347`). Because those fields are part
of the request schema, they flow through both `action_payload` (after allowlist
filtering) and `StateChangeDraft.payload_json` (in services that include them
in the state-change body). This mirrors the originating-actor convention
established in `services/discord/app/handlers/chapters.py:88` and
`services/api/app/services/chapters.py:138-142`. AC coverage:
`test_handle_member_join_records_originating_user_in_audit`.

### 9. Migration safety — LOW

- `members` and `trust_profiles` are both new; no rows exist anywhere in the
  fleet, so there is no backfill, no NOT NULL retrofit on populated columns,
  and no implicit default-value risk.
- `trust_profiles.member_id REFERENCES members(id) ON DELETE RESTRICT` and
  `trust_profiles.policy_version_id REFERENCES policy_versions(id) ON DELETE
  RESTRICT` (`.pipeline/proposal.md:190-194`) preserve referential integrity
  on downgrade and on operator-initiated deletes.
- D10 deliberately leaves `roster_entries.member_id` as `TEXT` and defers FK
  cleanup (`.pipeline/proposal.md:84-85`); attempting it in this slice would
  mix durable onboarding with cross-slice migration risk on already-shipped
  data. The deferral is the safer posture.
- Downgrade of `wu-012_trust.py` removes only the `member-onboarder` global
  grant (`.pipeline/proposal.md:204`), which is the narrow correct cleanup
  for the row this migration introduced.

## Non-Blocking Observation

`TrustSignalsInput` declares `originating_actor_kind` and
`originating_actor_id` alongside the four D5 scoring fields, and the proposal
states "Stores the exact input signals and selected `policy_version_id` on
`trust_profiles`" (`.pipeline/proposal.md:262-263`). Read literally, that
persists originating-actor fields inside `trust_profiles.signals` JSONB along
with the scoring fields. Determinism is preserved because the evaluator only
reads the four D5 fields per D6, but the storage layer mixes audit context
with scoring input. The originating-actor attribution is already recorded
through the mutation `payload_allowlist` path
(`activity_actions.request_json` and `activity_state_changes.payload_json`),
so the JSONB copy is redundant rather than missing. Consider scoping the
persisted `signals` blob to just the D5 fields in a follow-up; not required
for this slice.

## Recommendation

**Accept.** All eight focus areas resolve to LOW. The Revision 1 changes pin
the concurrent-redelivery recovery for trust compute, add AC4 stale-PATCH
coverage, add AC2 concurrent-redelivery coverage, add typed `invalid_trust_
policy` 409 mapping, and seed the `member-onboarder` grants with both read and
write on member and trust. Member-create idempotency uses the correct
exception class (`UniqueViolation` on `discord_user_id`, not
`StaleMutationError`) for the different-UUID-per-request path. Migration
cleanup is correctly narrow. No revision required from an audit-risk
standpoint.
