# SLICE-007 Phase 3 Proposal: Member Onboarding With Initial Trust Assessment

## Source

This proposal implements WU-011, WU-012, and WU-013 from
`product-strategy/tickets/SLICE-007.md`, using the Phase 1 research in
`.pipeline/research.md` and the Phase 2 binding synthesis in
`.pipeline/synthesis.md`.

Primary source citations:

- `.pipeline/research.md` section 1: no prototype is required because the slice stays
  on existing `mutate_entity()`/`aggregate_heads`, policy-version, and
  Discord-to-API transport surfaces.
- `.pipeline/research.md` sections 2.1, 2.9, and 2.10: member creation should be a new
  projection-plus-head aggregate, `discord_user_id` must be unique, and member
  lifecycle history should use `activity_actions` rather than a dedicated
  transition projection.
- `.pipeline/research.md` sections 2.4 and 2.6: trust compute is initial-only,
  idempotent by member, uses the latest global `policy_versions` trust row,
  and returns a typed `409` when no trust policy exists.
- `.pipeline/research.md` sections 2.8 and 2.11: the Discord join handler must be
  API-first and use global member/trust authority.
- `.pipeline/synthesis.md` D1-D12: these decisions are binding. Where research
  and synthesis differ, D1-D12 control this proposal.

Existing code references:

- `services/api/app/services/mutations.py:58` defines `mutate_entity()`;
  `services/api/app/services/mutations.py:97` bootstraps `aggregate_heads` for
  `expected_version=0`; `services/api/app/services/mutations.py:123` rejects
  stale versions; `services/api/app/services/mutations.py:150` writes accepted
  audit actions; `services/api/app/services/mutations.py:167` advances the
  version.
- `services/api/app/repositories/roster.py:11` shows the current projection
  read pattern that joins `aggregate_heads` for `version`.
- `services/api/app/repositories/policies.py:10` provides latest policy-version
  lookup.
- `services/api/app/core/dependencies.py:56` and
  `services/api/app/core/dependencies.py:129` provide global authority
  enforcement through `RequireAuthority`.
- `services/discord/app/infrastructure/api_client.py:25` adds correlation
  headers to API calls while preserving caller-supplied headers.
- `services/discord/app/core/bot.py:21` already enables the Discord members
  intent needed for join events.
- `services/discord/app/handlers/chapters.py:12` and
  `services/discord/app/handlers/chapters.py:88` are the precedent for service
  actor headers plus originating-user payload fields.

## In Scope

- Add a durable `member` aggregate backed by `members` plus
  `aggregate_heads`.
- Add member create/get/status APIs with global `member.read` and
  `member.write` authority.
- Add a durable one-profile-per-member `trust_profile` aggregate backed by
  `trust_profiles` plus `aggregate_heads`.
- Add initial trust compute and read APIs with global `trust.read` and
  `trust.write` authority.
- Compute trust deterministically from the fixed onboarding signal JSON and the
  currently selected trust policy version.
- Return `409 {"code": "no_trust_policy_configured"}` when no global trust
  policy exists.
- Seed the `member-onboarder` service actor with global `member.read`,
  `member.write`, `trust.read`, and `trust.write` grants.
- Add a Discord member-join handler that creates or finds the member, requests
  trust compute through the API, and returns an onboarding outcome.
- Carry the originating Discord user ID in request bodies so API audit payloads
  preserve the user behind the service actor.

## Out of Scope

D12 anti-scope is explicit and remains binding. SLICE-007 does not implement:

- Trust recomputation.
- Trust signal extensibility beyond the initial onboarding JSONB shape.
- Member merge or split workflows.
- Member data export.
- Compliance-driven member status changes.
- Per-chapter member visibility.
- Age verification.
- Phone verification.

The slice also does not add a foreign key from `roster_entries.member_id` to
`members.id`; D10 defers that backfill and constraint to a later cleanup slice.

## Work Units

### WU-011 Member Aggregate + Status API

**Migration: `migrations/versions/wu-011_members.py`**

- Create `members`:
  - `id UUID PRIMARY KEY`
  - `discord_user_id TEXT NOT NULL UNIQUE`
  - `joined_at TIMESTAMPTZ NOT NULL`
  - `status TEXT NOT NULL CHECK (status IN ('active','suspended','departed'))`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- Do not add a `version` column.
- The service bootstraps the matching `aggregate_heads` row through
  `mutate_entity(... expected_version=0, aggregate_type="member")`, matching
  the established aggregate-head bootstrap pattern.

**Contracts: `services/api/app/contracts/members.py`**

- `MemberStatus = Literal["active", "suspended", "departed"]`
- `MemberCreate`
  - `discord_user_id: str`
  - `joined_at: datetime`
  - `originating_actor_kind: Literal["user", "service"] = "user"`
  - `originating_actor_id: str`
- `MemberRead`
  - `id: UUID`
  - `discord_user_id: str`
  - `joined_at: datetime`
  - `status: MemberStatus`
  - `created_at: datetime`
  - `updated_at: datetime`
  - `version: int`
- `MemberStatusPatch`
  - `status: MemberStatus`
  - `reason: str`
  - `originating_actor_kind: Literal["user", "service"] = "user"`
  - `originating_actor_id: str`
- Errors: `MemberNotFoundError`, `InvalidMemberStatusTransitionError`.

**Repository: `services/api/app/repositories/members.py`**

- `_MEMBER_SELECT` joins `members` to `aggregate_heads` with
  `aggregate_type = 'member'` and `aggregate_id = members.id::text`.
- Public reads:
  - `fetch_member_by_id(connection, member_id)`
  - `fetch_member_by_discord_id(connection, discord_user_id)`
- Internal writes:
  - `_insert_member(connection, row)`
  - `_update_member_status(connection, member_id, status)`
- Keep write helpers underscore-prefixed so services own mutation semantics and
  audit, matching the roster repository boundary.

**Service: `services/api/app/services/members.py`**

- `create_or_get_member(db, request, actor) -> tuple[MemberRead, MutationResult | None, bool]`
  - Checks by `discord_user_id` first.
  - If found, returns the current member and no mutation result; endpoint emits
    `200 OK`.
  - If absent, generates a UUID and calls `mutate_entity()` with
    `aggregate_type="member"`, `expected_version=0`, action type
    `member.create`, and global scope.
  - Catches `UniqueViolation` on `discord_user_id` and re-reads the existing
    row to make duplicate Discord join delivery race-safe.
  - New members always start `status="active"`.
- `get_member_by_id(db, member_id) -> tuple[MemberRead, str]`
- `get_member_by_discord_id(db, discord_user_id) -> tuple[MemberRead, str]`
- `patch_member_status(db, member_id, request, actor, expected_version) -> tuple[MemberRead, MutationResult]`
  - Allows D2 transitions:
    `active -> suspended`, `suspended -> active`, `active -> departed`,
    `suspended -> departed`, `departed -> active`.
  - Rejects same-status and unsupported transitions with `409`.
  - Uses `mutate_entity()` against aggregate type `member`; stale `If-Match`
    becomes `412 Precondition Failed`.
  - Stores originating actor fields in `action_payload` and
    `StateChangeDraft.payload_json`.

**Endpoints: `services/api/app/api/v1/endpoints/members.py`**

- `POST /api/v1/members`
  - Requires `RequireAuthority("member.write", "global")`.
  - Returns `201 Created` for new members and `200 OK` for existing
    `discord_user_id`.
  - Sets `ETag` when a new mutation creates the row; for existing rows, derives
    `ETag` from `MemberRead.version`.
- `GET /api/v1/members/{id}`
  - Requires `RequireAuthority("member.read", "global")`.
- `GET /api/v1/members/by-discord/{discord_user_id}`
  - Requires `RequireAuthority("member.read", "global")`.
  - Returns `404 {"code": "member_not_found"}` when absent.
- `PATCH /api/v1/members/{id}/status`
  - Requires `RequireAuthority("member.write", "global")`.
  - Requires `If-Match`.
  - Maps stale mutation to `412`, invalid transition to `409`, missing member to
    `404`.
- Register the router in `services/api/app/api/v1/router.py`.

### WU-012 Trust Profile + Initial Computation API

**Migration: `migrations/versions/wu-012_trust.py`**

- Create `trust_profiles`:
  - `member_id UUID PRIMARY KEY REFERENCES members(id) ON DELETE RESTRICT`
  - `score INT NOT NULL CHECK (score >= 0 AND score <= 100)`
  - `tier TEXT NOT NULL`
  - `signals JSONB NOT NULL`
  - `policy_version_id UUID NOT NULL REFERENCES policy_versions(id) ON DELETE RESTRICT`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- Do not add a `version` column; read version through `aggregate_heads` with
  `aggregate_type = 'trust_profile'` and `aggregate_id = member_id::text`.
- Idempotently seed one active global `authority_grants` row for
  `grantee_id='member-onboarder'`, `scope_kind='global'`, `scope_id IS NULL`,
  and permissions containing
  `["member.read", "member.write", "trust.read", "trust.write"]`.
- Downgrade removes only that global `member-onboarder` grant.
- The migration may also create indexes for policy replay reads, such as
  `ix_trust_profiles__policy_version_id`.

**Contracts: `services/api/app/contracts/trust.py`**

- `TrustSignalsInput`
  - `discord_account_age_days: int = Field(ge=0)`
  - `has_avatar: bool`
  - `has_verified_badge: bool`
  - `account_flags: list[str] = Field(default_factory=list)`
  - `originating_actor_kind: Literal["user", "service"] = "user"`
  - `originating_actor_id: str`
- `TrustProfileRead`
  - `member_id: UUID`
  - `score: int`
  - `tier: str`
  - `signals: dict[str, Any]`
  - `policy_version_id: UUID`
  - `version: int`
- Errors: `TrustProfileNotFoundError`, `NoTrustPolicyConfiguredError`,
  `InvalidTrustPolicyError`, `MemberNotFoundError` reuse or import boundary.

**Repository: `services/api/app/repositories/trust.py`**

- `_TRUST_PROFILE_SELECT` joins `trust_profiles` to `aggregate_heads` with
  `aggregate_type = 'trust_profile'`.
- `fetch_trust_profile_by_member_id(connection, member_id)`.
- `_insert_trust_profile(connection, row)`.
- Reuse `services/api/app/repositories/policies.py:10` for latest global trust
  policy lookup rather than creating a parallel policy query.

**Service: `services/api/app/services/trust.py`**

- `compute_trust(db, member_id, signals, actor) -> tuple[TrustProfileRead, MutationResult | None, bool]`
  - Verifies the member exists through the member repository/service.
  - If a trust profile already exists for `member_id`, returns it without
    recomputing. This is idempotency, not recomputation.
  - Fetches the latest policy where `policy_type="trust"`,
    `scope_kind="global"`, `scope_id=None`.
  - If absent, raises `NoTrustPolicyConfiguredError` and the endpoint maps it
    to `409 {"code": "no_trust_policy_configured"}`.
  - Computes `score` and `tier` deterministically from `signals` and the
    selected policy row's `rules` JSON.
  - Does not read ambient time, random values, Discord, or other mutable
    external state during scoring.
  - Calls `mutate_entity()` with `aggregate_type="trust_profile"`,
    `aggregate_id=str(member_id)`, `expected_version=0`, action type
    `trust_profile.compute`, and global scope.
  - Catches `StaleMutationError` from concurrent first-compute redelivery,
    re-reads the profile by `member_id`, and returns the committed profile
    without recomputing. If the re-read is unexpectedly absent, re-raises the
    original stale error.
  - Also catches `UniqueViolation` from the profile insert path and uses the
    same re-read-and-return recovery. This is belt-and-suspenders protection
    for a create-after-head-check window.
  - The pinned idempotency exception list is:
    `StaleMutationError | UniqueViolation -> re-read existing profile and
    return`.
  - Stores the exact input signals and selected `policy_version_id` on
    `trust_profiles`.
- `get_trust_profile(db, member_id) -> tuple[TrustProfileRead, str]`

Policy content contract for SLICE-007:

- The current policy row content must contain a deterministic `rules` object.
- The evaluator should accept a minimal shape such as:
  - `rules.score_floor`
  - `rules.score_ceiling`
  - `rules.default_score`
  - `rules.weights.discord_account_age_days`
  - `rules.weights.has_avatar`
  - `rules.weights.has_verified_badge`
  - `rules.flags`
  - `rules.tiers`
- Invalid policy shape raises `InvalidTrustPolicyError`; the endpoint maps it
  to typed `409 {"code": "invalid_trust_policy"}` rather than silently
  defaulting.

**Endpoints: `services/api/app/api/v1/endpoints/trust.py`**

- `POST /api/v1/trust/compute/{member_id}`
  - Requires `RequireAuthority("trust.write", "global")`.
  - Returns `201 Created` on first compute and `200 OK` when the profile already
    exists, including concurrent redelivery recovered through
    `StaleMutationError` or `UniqueViolation`.
  - Sets `ETag` from mutation result or current read version.
  - Maps `InvalidTrustPolicyError` to
    `409 {"code": "invalid_trust_policy"}`.
- `GET /api/v1/trust/{member_id}`
  - Requires `RequireAuthority("trust.read", "global")`.
  - Returns `404 {"code": "trust_profile_not_found"}` when absent.
- Register the router in `services/api/app/api/v1/router.py`.

### WU-013 Discord Member-Join Onboarding Flow

**Contracts: `services/discord/app/contracts/onboarding.py`**

- `MemberJoinEvent`
  - `discord_user_id: str`
  - `joined_at: datetime`
  - `signals: TrustSignalsInput`-compatible payload with the fixed D5 fields
  - `originating_actor_kind: Literal["user"] = "user"`
  - `originating_actor_id: str`
- `MemberJoinOutcomeRead`
  - `member: dict[str, Any]`
  - `trust: dict[str, Any]`
  - `intake_required: bool`

**Handler: `services/discord/app/handlers/onboarding.py`**

- `handle_member_join(event: MemberJoinEvent) -> MemberJoinOutcomeRead`
- The handler uses API calls only; it must not compute trust locally.
- Service actor headers:
  - `X-Actor-Kind: service`
  - `X-Actor-Id: member-onboarder`
- Flow:
  1. `GET /api/v1/members/by-discord/{discord_user_id}`.
  2. If status is `404`, call `POST /api/v1/members` with
     `discord_user_id`, `joined_at`, and originating actor fields derived from
     the event.
  3. Call `POST /api/v1/trust/compute/{member_id}` with the D5 signal JSON and
     originating actor fields.
  4. Derive `intake_required` from `trust.tier`.
  5. Return `MemberJoinOutcomeRead(member=member, trust=trust,
     intake_required=intake_required)`.
- The tier mapping is local policy interpretation for the returned outcome:
  `low` requires intake; all other tiers do not. This is deliberately derived
  from the persisted profile's tier rather than recomputing score.
- API errors propagate as onboarding failures; duplicate delivery is handled by
  member create idempotency and trust compute idempotency.
- Bot wiring should add an `on_member_join` listener on `HumilityBot` or a
  registered listener that converts `discord.Member` into `MemberJoinEvent`
  and calls `handle_member_join`.

**Audit payload**

- API calls are attributed to `service/member-onboarder` through headers.
- The originating Discord user is carried in the request body through
  `originating_actor_kind="user"` and `originating_actor_id=<discord_user_id>`.
- Member create, status patch, and trust compute services include those fields
  in their mutation action payload allowlist and state-change payload.
- Those mutation calls use
  `payload_allowlist=set(request.model_dump(mode="json").keys())`, matching
  the existing member/chapter/roster mutation allowlist pattern.

## Tradeoffs

- **Member status audit uses `activity_actions` only.** D2 forbids a dedicated
  `member_transitions` table. This is acceptable because the member lifecycle
  is simple in this slice and no downstream Discord effect needs a transition
  ID for retry idempotency.
- **Roster FK is deferred.** D10 keeps `roster_entries.member_id` as
  unconstrained `TEXT`. Adding an FK now would mix durable member onboarding
  with a cross-slice roster migration and backfill.
- **Trust recompute is not supported.** D3 makes compute idempotent and
  initial-only. A second compute returns the existing profile even if the trust
  policy has changed; SLICE-016 owns recomputation and additional signals.
- **No default trust policy is seeded here.** Missing trust policy returns
  `409 no_trust_policy_configured`. Policy creation already belongs to the
  policy-versioning surface and should stay explicit.

## Preserved

- **SLICE-002 audit.** Mutations go through `mutate_entity()`, preserving
  accepted/rejected/failed audit actions, correlation headers, causation, and
  `activity_state_changes`.
- **SLICE-008 authority.** Member and trust APIs use explicit global
  `RequireAuthority` checks. The Discord handler uses a narrowly seeded service
  actor rather than bypassing authority.
- **SLICE-010 policy versioning substrate.** Trust computation uses
  `policy_versions` and stores `policy_version_id` for replay. No parallel
  configuration table is introduced.

## Resolved Decisions

| Decision | Proposal resolution |
|---|---|
| D1 | `members` is introduced in `migrations/versions/wu-011_members.py` with the exact UUID/Discord/joined/status shape. It has no `version` column. `MemberRead.version` comes from a repository join on `aggregate_heads`, following `services/api/app/repositories/roster.py:11`. Creation uses `mutate_entity()` bootstrap from `services/api/app/services/mutations.py:97`. |
| D2 | `patch_member_status()` enforces the allowed status matrix and records changes only through `activity_actions`/`activity_state_changes` via `mutate_entity()`. No `member_transitions` table is created. |
| D3 | `trust_profiles.member_id` is the primary key and aggregate id. `compute_trust()` returns an existing profile without recomputing and only creates a profile when none exists. Version reads use `aggregate_heads` with `aggregate_type='trust_profile'`. |
| D4 | `compute_trust()` calls the existing policy repository pattern from `services/api/app/repositories/policies.py:10` for `policy_type='trust'`, global scope. Missing policy maps to `409 no_trust_policy_configured`. The selected `policy_version_id` is persisted. |
| D5 | `TrustSignalsInput` is the fixed JSON shape: `discord_account_age_days`, `has_avatar`, `has_verified_badge`, and `account_flags`. Signals are stored in `trust_profiles.signals` JSONB. No standalone signal table is added. |
| D6 | Trust scoring is a pure evaluator over `TrustSignalsInput` plus the selected policy row's `rules` JSON. It reads no clock, random source, Discord state, or mutable external dependency during scoring. |
| D7 | `handle_member_join(event: MemberJoinEvent)` implements GET by Discord ID, POST member on 404, then POST trust compute, and returns `MemberJoinOutcomeRead`. The handler uses `ApiTransportRequest` through the existing API client, matching `services/discord/app/infrastructure/api_client.py:25`. |
| D8 | The handler sends `X-Actor-Kind: service` and `X-Actor-Id: member-onboarder`, following the service-header precedent in `services/discord/app/handlers/chapters.py:12`. Request bodies carry `originating_actor_id=<discord_user_id>`, following the originating-body precedent in `services/discord/app/handlers/chapters.py:88`. |
| D9 | Member endpoints require global `member.read`/`member.write`; trust endpoints require global `trust.read`/`trust.write` through `RequireAuthority` from `services/api/app/core/dependencies.py:129`. `wu-012_trust.py` idempotently seeds global `member.read`, `member.write`, `trust.read`, and `trust.write` for `member-onboarder`. |
| D10 | `wu-011_members.py` does not alter `roster_entries`. Existing roster code keeps `member_id` as string-shaped data, as seen in `services/api/app/contracts/roster.py`. FK cleanup is deferred. |
| D11 | `POST /members` is get-or-create by `discord_user_id`: existing row returns `200`, new row returns `201`. Member create catches `UniqueViolation` on `discord_user_id` and re-reads. `POST /trust/compute/{member_id}` returns an existing profile on sequential retry and concurrent first-compute redelivery; trust compute catches `StaleMutationError | UniqueViolation`, re-reads by `member_id`, and returns the committed profile. |
| D12 | The out-of-scope list is restated above and no proposed contract, migration, endpoint, or handler adds recompute, extensible signals, merge/split, export, compliance statuses, per-chapter visibility, age verification, or phone verification. |

## AC Trace

### AC1: Creating a member returns an active record with server-assigned id

- `test_create_member_returns_active_with_uuid_id`
- `test_create_member_idempotent_on_duplicate_discord_user_id`
- `test_create_member_requires_member_write_permission`
- `test_get_member_by_id_returns_current_state`
- `test_get_member_by_discord_id_404_when_absent`

### AC2: Initial trust compute persists deterministic profile using current policy version

- `test_compute_trust_creates_profile_with_current_policy_version`
- `test_compute_trust_is_deterministic_given_same_signals_and_policy`
- `test_compute_trust_returns_existing_profile_on_retry`
- `test_compute_trust_concurrent_same_member_returns_same_profile_to_both`
- `test_compute_trust_returns_409_when_no_trust_policy`
- `test_compute_trust_returns_409_when_policy_shape_invalid`
- `test_trust_profile_stores_policy_version_id_for_replay`

### AC3: Discord join flow uses API, not local logic

- `test_handle_member_join_creates_member_when_absent`
- `test_handle_member_join_reuses_member_when_present`
- `test_handle_member_join_computes_trust_and_derives_intake_required`
- `test_handle_member_join_records_originating_user_in_audit`

### AC4: Stale status patch is rejected through optimistic locking

- `test_patch_member_status_with_current_version_succeeds_and_advances_version`
- `test_patch_member_status_returns_412_on_stale_version`

### Invariants

- `test_member_onboarder_service_actor_has_read_and_write_grants_after_migration`
- `test_no_hardcoded_system_actor_in_members_service`
- `test_unique_discord_user_id_enforced`

## Revision History

- **Revision 0** — Initial proposal for WU-011, WU-012, and WU-013.
- **Revision 1** — Closes round-1 risk findings: pins
  `StaleMutationError | UniqueViolation` recovery for concurrent trust compute
  redelivery, adds AC4 stale-version PATCH tests, seeds `member-onboarder` with
  read/write member and trust grants, and requires typed
  `InvalidTrustPolicyError -> 409` coverage for malformed policy rules.
