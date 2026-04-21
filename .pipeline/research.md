# SLICE-007 Phase 1 Research: Member Onboarding With Initial Trust Assessment

## 1. Prototyping Assessment

**NO - production implementation can proceed without a disposable prototype.**

This slice stays inside already-proven surfaces:

- API writes use the existing `mutate_entity()` / `aggregate_heads` optimistic-locking substrate. The primitive bootstraps a new head at expected version `0`, locks the head row, rejects stale versions, records accepted/rejected/failed audit actions, and returns a strong ETag (`services/api/app/services/mutations.py:58`, `services/api/app/services/mutations.py:97`, `services/api/app/services/mutations.py:112`, `services/api/app/services/mutations.py:123`, `services/api/app/contracts/mutations.py:7`).
- Policy lookup and version pinning can use the existing `policy_versions` table and repository helpers. `policy_versions` already stores `policy_type`, `scope_kind`, `scope_id`, `version_number`, `content`, and `effective_at`; `fetch_latest_version()` returns latest content and metadata for a policy scope (`migrations/versions/wu-005_policy_foundation.py:17`, `services/api/app/repositories/policies.py:10`).
- Discord-to-API transport is already present. `ApiClient.call()` adds correlation headers and accepts caller-supplied request headers/body/path (`services/discord/app/infrastructure/api_client.py:25`, `services/discord/app/contracts/api_transport.py:8`). The Discord bot already enables the members intent needed for member events (`services/discord/app/core/bot.py:21`).
- The handler has no visible Discord write in this slice. It only calls the API and returns a local outcome, so it does not require a Mutation Safety prototype.

The only external-platform nuance is event delivery: Discord gateway events may be delivered more than once, so the join handler must be idempotent. Discord's own API reference says events can be sent "exactly one time" or "up to N times" and clients should operate idempotently (https://docs.discord.com/developers/reference#consistency).

## 2. Per-Question Answers

### 1. Member aggregate shape

There is no existing production `members` API/table/substrate in `services/api`; the ticket explicitly says no durable onboarding flow exists yet (`product-strategy/tickets/SLICE-007.md:68`). The member aggregate should therefore be new and should follow the current projection-plus-head pattern, not add a local `version` column.

Recommended shape:

- `members.id UUID PRIMARY KEY`
- `discord_user_id TEXT NOT NULL UNIQUE`
- `joined_at TIMESTAMPTZ NOT NULL`
- `status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'departed'))`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

`MemberRead.version` should come from `aggregate_heads.current_seq` joined on `aggregate_type = 'member'` and `aggregate_id = members.id::text`, mirroring the current roster read query that joins `aggregate_heads` for `version` (`services/api/app/repositories/roster.py:11`). This is safe for UUID aggregate IDs because `aggregate_id` was widened to `TEXT` after WU-002 (`migrations/versions/wu-003a_widen_aggregate_id.py:19`).

Creation should call `mutate_entity()` with `aggregate_type="member"`, the generated UUID as `aggregate_id`, and `expected_version=0`. The primitive creates the aggregate head on expected version zero (`services/api/app/services/mutations.py:97`) and returns version `1`/ETag on success (`services/api/app/services/mutations.py:167`).

### 2. Member state machine

The valid statuses are `active`, `suspended`, and `departed` (`product-strategy/tickets/SLICE-007.md:22`). No status is terminal.

Recommended transition matrix:

- `active -> suspended`: admin action.
- `suspended -> active`: admin lift.
- `active -> departed`: member leaves guild.
- `departed -> active`: member rejoins.

Do **not** allow same-status no-op patches. Treat them as `409 Conflict`, consistent with roster rejecting invalid/no-op transitions (`services/api/app/services/roster.py:97`).

Open edge: the input does not explicitly allow `suspended -> departed`. Operationally, a suspended member can leave Discord. Research recommendation: keep the phase-1 matrix exactly as stated above and record `suspended -> departed` as a synthesis/proposal question rather than expanding state behavior in research.

### 3. TrustProfile shape

The ticket requires `member_id`, computed `score`/`tier`, `signals`, policy/config linkage, and `version` (`product-strategy/tickets/SLICE-007.md:21`). INIT-002 requires results to be deterministic for the same inputs and pinned to the governing policy/config version (`product-strategy/tickets/INIT-002.md:43`).

Recommended phase-1 shape:

- `trust_profiles.id UUID PRIMARY KEY`
- `member_id UUID NOT NULL UNIQUE REFERENCES members(id) ON DELETE RESTRICT`
- `score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100)`
- `tier TEXT NOT NULL`
- `intake_required BOOLEAN NOT NULL`
- `signals JSONB NOT NULL`
- `policy_version_id UUID NOT NULL REFERENCES policy_versions(id) ON DELETE RESTRICT`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

`TrustProfileRead` should include `id`, `member_id`, `score`, `tier`, `signals`, `policy_version_id`, `policy_version_number`, `intake_required`, and `version`. The AI roadmap only lists `TrustProfileRead(member_id, score, tier, signals, intake_required, version)` (`product-strategy/ai roadmap.md:491`), but the ticket also requires policy/config linkage (`product-strategy/tickets/SLICE-007.md:23`), and INIT-002 makes policy pinning an acceptance criterion (`product-strategy/tickets/INIT-002.md:47`).

Versioning: use aggregate type `trust_profile` and aggregate ID `member_id` or `trust_profile.id`. Prefer `member_id` as aggregate ID because the public route is member-keyed (`GET /api/v1/trust/{member_id}`), and phase-1 has exactly one initial profile per member.

### 4. Trust computation semantics

Initial compute should be deterministic and one-profile-per-member for this slice. The ticket calls this "initial trust assessment" (`product-strategy/tickets/SLICE-007.md:1`), while SLICE-016 separately owns later trust signals and recomputation (`product-strategy/tickets/SLICE-016.md:10`, `product-strategy/tickets/SLICE-016.md:26`). Therefore:

- `POST /api/v1/trust/compute/{member_id}` computes the initial profile if none exists.
- If a profile already exists for that member, return the existing profile rather than recomputing under a newer policy. This makes duplicate Discord join events idempotent and preserves the policy latch.
- Later recomputation under the current policy belongs to SLICE-016, which has separate `POST /api/v1/trust/recompute/{member_id}` scope (`product-strategy/tickets/SLICE-016.md:27`).

This is a POST because the first call creates durable state and audit entries. It is idempotent by member ID, not a pure read.

### 5. TrustSignal / initial platform-metadata signal

The API cannot introspect live Discord user metadata. The Discord adapter must supply the initial platform metadata as request data.

Recommended `TrustSignal` representation inside SLICE-007:

```text
TrustSignalInput(
  signal_type="discord_platform_metadata",
  source="discord_member_join",
  observed_at,
  value={
    "discord_user_id": str,
    "account_created_at": datetime,
    "account_age_days": int,
    "joined_at": datetime,
    "has_avatar": bool,
    "is_bot": bool,
    "public_flags": int | null,
    "member_flags": int | null,
    "pending": bool | null
  }
)
```

Evidence for these fields:

- Discord user objects expose `id`, `avatar`, optional `bot`, `flags`, and `public_flags` (https://docs.discord.com/developers/resources/user#user-object-user-structure).
- Discord member objects expose `joined_at`, guild `avatar`, `flags`, and `pending` (https://docs.discord.com/developers/resources/guild#guild-member-object-guild-member-structure).
- Discord snowflake IDs encode a timestamp, so the adapter can compute account creation/account age from `discord_user_id` even when the library does not directly provide `created_at` (https://docs.discord.com/developers/reference#snowflakes).

Do **not** include verified email, phone verification, mutual servers, or OAuth connection data in phase 1 unless the adapter can legitimately observe them. The official user object marks `verified`/`email` behind the `email` OAuth scope, not ordinary bot gateway membership (`https://docs.discord.com/developers/resources/user#user-object-user-structure`). "Verified phone" is not exposed in the cited bot/member objects.

Store the signal snapshot in `trust_profiles.signals` for phase 1. Do not create a general `trust_signals` append-only table yet; SLICE-016 explicitly owns all signal types beyond platform metadata and signal management endpoints (`product-strategy/tickets/SLICE-016.md:21`).

### 6. Trust policy version

Use `policy_versions` with `policy_type = "trust"` and `scope_kind = "global"`, `scope_id = NULL`.

Why:

- The policy table is already generic by `policy_type`, scope, version, and content (`migrations/versions/wu-005_policy_foundation.py:17`).
- Policy reads can fetch latest version and content through `fetch_latest_version()` (`services/api/app/repositories/policies.py:10`).
- The proposal says onboarding uses the active global trust configuration and the profile should be explainable from documented signals and active weights/thresholds (`product-strategy/proposal.md:647`).

If no current trust policy exists, return a typed API error (`409 Conflict` is the cleanest fit: computation cannot proceed because required configuration is missing). Do not silently create a default policy in trust compute; policy creation is already a governed policy endpoint requiring `policy.write` (`services/api/app/api/v1/endpoints/policies.py:46`).

Minimum expected trust policy content for phase 1:

```json
{
  "score_floor": 0,
  "score_ceiling": 100,
  "default_score": 50,
  "tiers": [
    {"tier": "low", "min_score": 0, "intake_required": true},
    {"tier": "standard", "min_score": 50, "intake_required": false},
    {"tier": "high", "min_score": 80, "intake_required": false}
  ],
  "weights": {
    "account_age_days": {"min": 0, "max": 365, "points": 30},
    "has_avatar": 5,
    "is_bot": -100
  }
}
```

The exact policy schema should be finalized in proposal, but the computation must canonicalize enough to be deterministic. Use sorted tier thresholds and no randomness/time reads except the explicit `observed_at`/`joined_at` inputs.

### 7. Member vs roster `member_id`

Do not add an FK from `roster_entries.member_id` to `members.id` in SLICE-007.

Evidence:

- `roster_entries.member_id` is currently `TEXT NOT NULL`, created before members exist (`migrations/versions/wu-007c_roster_foundation.py:17`).
- SLICE-018 intentionally kept that field unconstrained because SLICE-007 was not merged yet; the review artifacts record "No member FK on `roster_entries.member_id`" as preserved behavior (`plans/review/slice-018-justification.md:151`).
- Adding an FK now would be a cross-slice migration against existing rows. Even if dev rows are empty, production-shaped migrations should not assume that.

Recommended binding for SLICE-007: `members.id` is a UUID. New roster code after SLICE-007 can mirror `members.id` into `roster_entries.member_id` by convention, but the FK cleanup should be a later explicit migration with backfill/validation.

### 8. Discord member-join event handler

The handler should be thin and API-first, matching the ticket's acceptance criterion that onboarding requests member creation/lookup and trust computation through the API rather than Discord-local logic (`product-strategy/tickets/SLICE-007.md:60`).

Suggested shape:

```text
handle_member_join(event: MemberJoinEvent, api_client) -> MemberJoinOutcomeRead

1. GET /api/v1/members/by-discord/{discord_user_id}
2. If 404, POST /api/v1/members with discord_user_id and joined_at
3. POST /api/v1/trust/compute/{member_id} with initial platform-metadata signal
4. Return member_id, trust_profile_id, intake_required
```

Headers should identify the service actor, likely:

```text
X-Actor-Kind: service
X-Actor-Id: discord-onboarding
```

The API client will add correlation headers from ambient context (`services/discord/app/infrastructure/api_client.py:25`). Because non-interaction gateway events do not use `InteractionEnvelope`, WU-013 should create an audit context around each join event before calling `ApiClient.call()`.

Discord bot wiring should add `async def on_member_join(self, member)` or register a listener that converts `discord.Member` to `MemberJoinEvent`. The bot already sets `intents.members = True` (`services/discord/app/core/bot.py:21`).

### 9. Unique constraint and idempotency

Add `UNIQUE(discord_user_id)` on `members`.

The handler must lookup first, create second. The service should still catch unique violations and return/read the existing member or map to `409 Conflict`, because two duplicate join events can race. Discord explicitly documents that events can be sent up to N times and recommends idempotent event handling (https://docs.discord.com/developers/reference#consistency).

Trust compute should also be idempotent. Add `UNIQUE(member_id)` on `trust_profiles`; if another request created the profile first, return the existing profile.

### 10. Status transitions and audit projection

For member status changes, `activity_actions` / `activity_state_changes` are sufficient for phase 1. A separate `member_transitions` projection is optional and not required by the ticket.

Why no `member_transitions` table now:

- The ticket asks for member status patching and OCC, not transition history queries (`product-strategy/tickets/SLICE-007.md:30`, `product-strategy/tickets/SLICE-007.md:61`).
- The audit substrate already records action type, aggregate type/id, actor, request surface, scope, status, reason, and state-change payload (`migrations/versions/wu-002_activity_substrate.py:17`, `migrations/versions/wu-003b_audit_context_columns.py:16`, `services/api/app/repositories/mutations.py:46`).
- Roster needed a transition table because downstream Discord role sync required transition IDs and retry idempotency. Member status has no downstream Discord visible write in this slice.

If proposal chooses a projection anyway, keep it clearly query-driven and write it in the same `mutate_projection` transaction. Do not make it the source of truth.

### 11. Authority scopes

Members and initial trust are guild-level, not chapter-level. Use global authority requirements:

- `member.read`: `GET /members/{id}`, `GET /members/by-discord/{discord_user_id}`
- `member.write`: `POST /members`, non-suspension status patches such as departed/rejoin
- `member.suspend`: `PATCH /members/{id}/status` when `to_status == "suspended"` or lifting suspension if proposal wants a dedicated permission for both sides
- `trust.read`: `GET /trust/{member_id}`
- `trust.compute`: `POST /trust/compute/{member_id}`

The current authority substrate supports `global`, `chapter`, and `member` scopes (`migrations/versions/wu-004_authority_foundation.py:17`, `services/api/app/contracts/scope.py:4`), and endpoint dependencies already enforce permission/scope combinations through `RequireAuthority()` (`services/api/app/core/dependencies.py:56`).

Seed a service actor grant for Discord onboarding:

```text
grantee_id = "discord-onboarding"
scope_kind = "global"
permissions = ["member.read", "member.write", "trust.compute", "trust.read"]
```

This mirrors prior service grants such as `roster-syncer`, which is seeded globally for service-to-API sync reporting (`migrations/versions/wu-033_roster.py:134`).

### 12. Existing member code in repo

No production member aggregate, member API, trust API, or onboarding handler exists in `services/api` or `services/discord`. The only `member_id` substrate currently relevant is roster, where `member_id` is a text identifier (`migrations/versions/wu-007c_roster_foundation.py:17`, `services/api/app/contracts/roster.py:17`). Legacy `daemon/` member references are pre-research draft Discord inspection/application code and should not be extended for this API-first slice; DECISIONS says those drafts are preserved historical artifacts until hookpoint research proves reuse (`DECISIONS.md:45`, `DECISIONS.md:63`).

## 3. Proposed Data Model

### `members`

```sql
CREATE TABLE members (
  id UUID PRIMARY KEY,
  discord_user_id TEXT NOT NULL,
  joined_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_members__discord_user_id UNIQUE (discord_user_id),
  CONSTRAINT members_status_valid CHECK (status IN ('active', 'suspended', 'departed'))
);
```

Read version from `aggregate_heads`, not from `members`.

### `trust_profiles`

```sql
CREATE TABLE trust_profiles (
  id UUID PRIMARY KEY,
  member_id UUID NOT NULL,
  score INTEGER NOT NULL,
  tier TEXT NOT NULL,
  intake_required BOOLEAN NOT NULL,
  signals JSONB NOT NULL,
  policy_version_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_trust_profiles__member_id UNIQUE (member_id),
  CONSTRAINT fk_trust_profiles__member_id__members
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT,
  CONSTRAINT fk_trust_profiles__policy_version_id__policy_versions
    FOREIGN KEY (policy_version_id) REFERENCES policy_versions(id) ON DELETE RESTRICT,
  CONSTRAINT trust_profiles_score_range CHECK (score >= 0 AND score <= 100)
);
```

Read version from `aggregate_heads` using `aggregate_type = 'trust_profile'`.

### Policy row

Use existing `policy_versions` rows:

```text
policy_type = "trust"
scope_kind = "global"
scope_id = NULL
content = deterministic trust scoring config
```

## 4. Proposed API Surface + Contracts

### Member contracts

```text
MemberStatus = Literal["active", "suspended", "departed"]

MemberCreate(
  discord_user_id: str,
  joined_at: datetime
)

MemberRead(
  id: UUID,
  discord_user_id: str,
  joined_at: datetime,
  status: MemberStatus,
  created_at: datetime,
  updated_at: datetime,
  version: int
)

MemberStatusPatch(
  to_status: MemberStatus,
  reason: str,
  originating_actor_kind: Literal["user", "service"] = "user",
  originating_actor_id: str
)
```

Endpoints:

- `POST /api/v1/members` -> `201 MemberRead`, `ETag: "1"`, requires global `member.write`
- `GET /api/v1/members/{member_id}` -> `MemberRead`, requires global `member.read`
- `GET /api/v1/members/by-discord/{discord_user_id}` -> `MemberRead`, requires global `member.read`
- `PATCH /api/v1/members/{member_id}/status` -> `MemberRead`, requires `If-Match`, returns `412` on stale version, requires global `member.write` or `member.suspend` depending transition

### Trust contracts

```text
TrustTier = str

TrustSignalInput(
  signal_type: Literal["discord_platform_metadata"],
  source: Literal["discord_member_join"],
  observed_at: datetime,
  value: dict[str, Any]
)

TrustComputeRequest(
  signals: list[TrustSignalInput]
)

TrustProfileRead(
  id: UUID,
  member_id: UUID,
  score: int,
  tier: TrustTier,
  intake_required: bool,
  signals: list[TrustSignalInput],
  policy_version_id: UUID,
  policy_version_number: int,
  created_at: datetime,
  updated_at: datetime,
  version: int
)
```

Endpoints:

- `POST /api/v1/trust/compute/{member_id}` -> `TrustProfileRead`, idempotent create-or-read, requires global `trust.compute`
- `GET /api/v1/trust/{member_id}` -> `TrustProfileRead`, requires global `trust.read`

### Error mapping

- Missing member: `404`
- Duplicate member create: preferably return existing member if the duplicate is the same `discord_user_id`; otherwise `409`
- Invalid status transition: `409`
- Missing `If-Match` on status patch: `428`, matching roster (`services/api/app/api/v1/endpoints/roster.py:41`)
- Stale version: `412`, matching mutation contract and roster endpoint mapping (`services/api/app/contracts/mutations.py:70`, `services/api/app/api/v1/endpoints/roster.py:108`)
- Missing trust policy: `409`

## 5. Discord Handler Shape

```text
MemberJoinEvent(
  discord_user_id: str,
  joined_at: datetime,
  account_created_at: datetime,
  has_avatar: bool,
  is_bot: bool,
  public_flags: int | None = None,
  member_flags: int | None = None,
  pending: bool | None = None
)

MemberJoinOutcomeRead(
  member_id: UUID,
  trust_profile_id: UUID,
  intake_required: bool
)
```

Algorithm:

```text
1. Build a root audit context for the gateway event.
2. Call GET /api/v1/members/by-discord/{discord_user_id}
   with X-Actor-Kind=service, X-Actor-Id=discord-onboarding.
3. If 404, call POST /api/v1/members with discord_user_id and joined_at.
4. Build TrustSignalInput from the Discord member object.
5. Call POST /api/v1/trust/compute/{member_id}.
6. Return MemberJoinOutcomeRead from API result.
```

The handler should not score trust locally and should not decide intake locally. It should return `intake_required` from the trust API, satisfying the WU-013 acceptance criterion (`product-strategy/ai roadmap.md:517`).

## 6. State Machine

```text
active --admin suspend--> suspended
suspended --admin lift--> active
active --guild leave--> departed
departed --guild rejoin--> active
```

Properties:

- No terminal state.
- No same-status no-op transition.
- All transitions require OCC via `If-Match`.
- All transitions are audit actions under aggregate type `member`.
- `joined_at` remains the Discord join-event timestamp for the current/most recent join. Rejoin from `departed -> active` should update `joined_at` to the new event timestamp if the status patch/handler includes it. If historical join/leave timeline is required later, add a projection in a later slice.

## 7. Open Questions

1. Should `suspended -> departed` be allowed when a suspended member leaves the guild? The provided transition list does not include it, but the real Discord event can happen.
2. Should `suspended -> active` require `member.suspend` or `member.write`? Security posture suggests `member.suspend` for both suspend and lift, but the permission split should be decided in synthesis/proposal.
3. Should initial trust compute require a supplied `signals` body, or can it compute from a `members.initial_signals` snapshot captured during member creation? Recommendation: require signals on compute to keep member records small and preserve handler/API separation.
4. Should `POST /members` return existing member on duplicate `discord_user_id` for handler idempotency, or should only the handler perform lookup-first? Recommendation: service-level duplicate handling is safer under race.
5. What exact default trust policy seed, if any, exists before first compute? Research recommends no implicit default inside compute; proposal must decide whether a migration seeds a starter `policy_versions(policy_type="trust")` row.

## 8. Recommended Magnitude

**M-L, leaning M - confirmed.**

Reasons:

- Migrations and API layering are straightforward because they reuse existing patterns (`mutate_entity`, `aggregate_heads`, `policy_versions`, `RequireAuthority`, `ApiClient`).
- The slice touches both services and introduces a new deterministic trust computation surface, so it is larger than a narrow CRUD slice.
- The riskiest parts are policy schema design, idempotent create/compute behavior, and keeping Discord metadata capture explicit without inventing unavailable signals.
- No prototype is needed, and no visible Discord write is in scope, so it does not rise to full L.
