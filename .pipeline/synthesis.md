# SLICE-007 Phase 2 Synthesis: Binding Decisions

These decisions are binding for the SLICE-007 proposal and implementation.
The proposal may choose implementation mechanics inside these boundaries, but
it must not add scope, replace these directions, or introduce compatibility
paths around them.

## Binding Decisions

- **D1 — BINDING: Member aggregate shape and version handling.**
  The member aggregate type is `member`. `members` must use
  `aggregate_heads` for optimistic-locking version reads and must not gain an
  independent `version` column. The table shape is:
  `id UUID PRIMARY KEY`, `discord_user_id TEXT NOT NULL UNIQUE`,
  `joined_at TIMESTAMPTZ NOT NULL`, and
  `status TEXT NOT NULL CHECK (status IN ('active','suspended','departed'))`.
  Read models obtain `version` by joining `aggregate_heads` on
  `aggregate_type = 'member'` and `aggregate_id = members.id::text`.

- **D2 — BINDING: Member status state machine.**
  Valid statuses are `active`, `suspended`, and `departed`. Allowed
  transitions are `active -> suspended`, `suspended -> active`,
  `active -> departed`, `suspended -> departed`, and `departed -> active`.
  There is no terminal member status. Status changes are audited through
  `activity_actions` only; SLICE-007 must not add a dedicated
  `member_transitions` projection.

- **D3 — BINDING: TrustProfile cardinality and compute idempotency.**
  `TrustProfile` is one row per member and uses `aggregate_heads` with
  `aggregate_type = 'trust_profile'` for version reads. Initial compute creates
  the row. Subsequent computes are forbidden as recomputation, because future
  SLICE-016 owns recompute. `POST /trust/compute/{member_id}` is idempotent:
  if a profile already exists, it returns the existing profile instead of
  recomputing.

- **D4 — BINDING: Trust policy version source and missing-policy error.**
  Trust computation references a `policy_versions` row where
  `policy_type = 'trust'`. Compute uses the current trust policy, defined as
  the trust policy row with the highest `version_number`. If no trust policy
  exists, compute returns `409 no_trust_policy_configured`. The selected
  `policy_version_id` is stored on `trust_profiles` for replay and audit.

- **D5 — BINDING: TrustSignal storage and initial shape.**
  Initial trust signals are stored inside `TrustProfile.signals` as JSONB, not
  in a standalone trust signal table. The initial schema is
  `{discord_account_age_days: int, has_avatar: bool, has_verified_badge: bool,
  account_flags: list[str]}`. The compute function consumes these signals plus
  the selected trust policy to produce score and tier.

- **D6 — BINDING: Deterministic trust computation.**
  Trust compute is deterministic: the same `signals` and `policy_version`
  produce the same `score` and `tier`. The evaluator uses the selected
  policy row's `rules` JSON as evaluation input. It must not read ambient time,
  random values, or mutable external state during scoring.

- **D7 — BINDING: Discord member-join handler flow.**
  The Discord handler signature is
  `handle_member_join(event: MemberJoinEvent)`. It performs:
  `GET /members/by-discord/{discord_user_id}`; if that returns 404,
  `POST /members` with `{discord_user_id, joined_at, initial_signals}`; then
  `POST /trust/compute/{member_id}` with signals. It returns
  `MemberJoinOutcome { member: MemberRead, trust: TrustProfileRead,
  intake_required: bool }`, where `intake_required` is derived from
  `trust.tier`.

- **D8 — BINDING: Discord service actor and originating user audit.**
  The Discord handler calls the API with
  `X-Actor-Kind: service` and `X-Actor-Id: member-onboarder`. The originating
  Discord user ID is carried in the request body and recorded in audit payloads.

- **D9 — BINDING: Authority scopes and service grant.**
  Add `member.read` and `member.write` at `scope_kind = 'global'`. Add
  `trust.read` and `trust.write` at `scope_kind = 'global'`. Seed the
  `member-onboarder` service actor with global `member.read`, `member.write`,
  `trust.read`, and `trust.write` grants.

- **D10 — BINDING: Roster member foreign key is deferred.**
  SLICE-007 ships the `members` table with its own UUID primary key. It must
  not add a foreign key from `roster_entries.member_id` to `members.id`.
  `roster_entries.member_id` remains unconstrained `TEXT` in this slice. A
  follow-up cleanup slice owns the backfill and FK addition.

- **D11 — BINDING: API idempotency for create and compute.**
  `POST /members` with an existing `discord_user_id` returns the existing
  member with `200 OK`, not `201 Created`; the endpoint is get-or-create by
  Discord user ID. `POST /trust/compute/{member_id}` returns the existing
  profile if already computed.

- **D12 — BINDING: Anti-scope.**
  SLICE-007 must not implement trust recomputation, trust signal extensibility,
  member merge/split, member data export, compliance-driven status changes,
  per-chapter member visibility, age verification, or phone verification.

## Anti-Scope

- Trust recomputation; this belongs to SLICE-016.
- Trust signal extensibility beyond the initial onboarding JSONB shape.
- Member merge or split workflows.
- Member data export.
- Compliance-driven member status changes.
- Per-chapter member visibility.
- Age verification.
- Phone verification.

## Traceability

| Decision | Supports / resolves |
|---|---|
| D1 | Supports AC1 and AC4: member creation returns a durable active member with server-assigned UUID and version reads use the established `aggregate_heads` optimistic-locking substrate. Resolves research finding 1 that no member aggregate exists and the member table should follow the projection-plus-head pattern. |
| D2 | Supports AC4: status patching has an explicit state machine and stale updates are rejected through the aggregate version. Resolves research findings 2 and 10 by allowing real Discord leave/rejoin paths, including suspended members leaving, while avoiding a dedicated transition projection. |
| D3 | Supports AC2: initial trust computation persists one durable profile for an existing member. Resolves research finding 4 that SLICE-007 is initial compute only and duplicate join events must return the pinned profile rather than recompute under a newer policy. |
| D4 | Supports AC2: trust computation uses the current trust policy version and stores the policy version id for replay/audit. Resolves research finding 6 that `policy_versions` already provides the generic policy version substrate and missing policy should fail explicitly instead of silently defaulting. |
| D5 | Supports AC2 and the ticket's TrustSignal requirement: onboarding captures platform metadata in the profile without building the future signal-management subsystem. Resolves research finding 5 that SLICE-016 owns general trust signals and that unavailable Discord/OAuth data must not be invented. |
| D6 | Supports AC2 and INIT-002: trust output is deterministic for the same inputs and pinned policy. Resolves research finding 6's requirement that scoring use policy content as explicit input and avoid hidden mutable state. |
| D7 | Supports AC3: Discord member-join onboarding creates or finds the member and requests trust computation through the API rather than Discord-local logic. Resolves research finding 8 that the handler should stay thin and API-first. |
| D8 | Supports AC3 and audit accountability: API calls are attributed to the service actor while preserving the originating Discord user ID in payload/audit. Resolves research finding 8's need for gateway-event audit context and follows the originating-actor pattern established by SLICE-013. |
| D9 | Supports AC1, AC2, and AC3: member and trust endpoints have explicit global authority requirements, and the onboarding service has the global read/write grants needed to look up or create members, compute trust, and use the trust read endpoint if implementation performs read-after-compute. Resolves research finding 11 that members and initial trust are guild-level surfaces, not chapter-scoped surfaces. |
| D10 | Resolves cross-slice integration with SLICE-018: member UUIDs are introduced without mutating the already-shipped `roster_entries.member_id TEXT` contract. Resolves research finding 7 and SLICE-018 D5 that the roster FK cleanup must be a later explicit migration. |
| D11 | Supports AC1 and AC3: duplicate join/create and duplicate compute events are idempotent under Discord gateway redelivery. Resolves research finding 9 that both `members.discord_user_id` and `trust_profiles.member_id` need service-level race-safe idempotency. |
| D12 | Resolves scope risk by excluding roadmap-adjacent trust, identity, compliance, and visibility work. Aligns with SLICE-016 ownership of recomputation/signal extensibility and keeps SLICE-007 limited to durable member onboarding plus initial trust assessment. |
