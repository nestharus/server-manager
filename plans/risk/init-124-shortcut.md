READ:
- proposals/05-synthetic-member-guard.md
- research/08-synthetic-member-guard-problem-map.md
- .tmp/rca/synthetic-public-member-pollution-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- plans/risk/init-120-shortcut.md
- plans/risk/init-122-shortcut.md

# INIT-124 Phase 4 — Shortcut Risk Report

## Inputs read

- `proposals/05-synthetic-member-guard.md` (full file)
- `research/08-synthetic-member-guard-problem-map.md` (full file)
- `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md` (full file)
- Pipeline rules (Phase 4 shortcut-risk role)
- Predecessor shortcut-risk reports (`init-120-shortcut.md`, `init-122-shortcut.md`) for verdict-format and tone

## Root-cause fix vs. relocation

The RCA names the root cause as: INIT-120 deliberately writes synthetic
`members` rows whose `discord_user_id` starts with `public:`, but several
officer-facing service entry points validate inputs only by exact `members`
existence (`fetch_member_by_id()`), so any synthetic UUID can become an
application owner, a trust subject, a leadership alias, a roster holder, or
a status-mutated member. Roster is the most brittle surface because
`roster_entries.member_id` is unconstrained `TEXT`
(`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:9-15`,
`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:46-83`).

The proposal fixes that root cause at the write boundaries the RCA names,
and does not push the problem into a read-time filter that would have to
be repeated everywhere:

- The shared `is_synthetic_member()` predicate is defined exactly once at
  `services/api/app/services/members.py` and is the single discriminator
  in callers (proposal §Helper signature + location). The locked
  discriminator (`discord_user_id LIKE 'public:%'`) is implemented in one
  place; callers do not duplicate `startswith("public:")`.
- The write-time `SyntheticMemberNotAllowedError` is mapped to a typed 422
  with stable per-surface `code`/`field`/`member_id`, which makes the
  rejection observable rather than absorbed by the existing generic
  `validation_error` fallback at
  `services/api/app/api/v1/endpoints/applications/_shared.py:171`
  (proposal §Helper signature + location). That is exactly the
  observability shortcut the proposal refuses: stable codes per boundary,
  not an undifferentiated `validation_error`.
- The proposal does not relocate the failure to read-time pollution
  filtering. It anti-scopes "read-side roster hardening for compliance,
  archive counts, succession role-holder lists, or roster listing"
  (proposal §Anti-scope) and explicitly says exact member reads remain
  unfiltered because public-intake idempotency and exact admin reads need
  them. The single read-side concession is succession alias expansion,
  which uses `synthetic_policy="omit"` only so one pre-existing polluted
  roster row does not poison the whole read path (proposal §Q8, §Design
  "Leadership alias expansion"). That is not relocation; it is bounded
  defense-in-depth on a path that would otherwise alias `public:<hash>`
  into grants/applications/tickets.
- The proposal does not relocate the problem into the schema. The locked
  RCA option is "write-boundary guard only, no `members.kind` schema
  column" (proposal §Summary), and the proposal anti-scopes any
  `members.kind` / `members.linked_at` / `synthetic_members` table /
  namespace refactor. The schema follow-up is named (BL-008) rather than
  silently deferred.
- Defense in depth flows the right way: the public-intake creation path
  remains the *only* place that constructs a `public:` `discord_user_id`
  (`services/api/app/services/members.py:175`), and every guarded call
  site rejects rows that flowed back from that single source. There is
  no second place that can mint synthetic members.

Verdict on this question: the design fixes the RCA's named root cause
(missing real-Discord-member predicate at officer-facing write entry
points) and does not push the problem to a read-time stub or a
test-fixture-only filter. The "delay-to-read-time" risk the brief asks
about is explicitly refused for new writes; the only read-side handling
is the succession `omit` exception, which is justified by the
roster-text-id pre-existing-pollution risk and is named, not silent.

## Boundary completeness

Cross-referencing the RCA's "needs filter" / "needs join condition" rows
against the proposal's guarded boundaries:

| RCA "needs filter" call site | Proposal coverage | Notes |
|---|---|---|
| `services/api/app/services/applications.py:594` (auth submit applicant) | covered | `_submit_application_internal()` after `fetch_member_by_id()`, only when `submission_authority != _SubmissionAuthority.PUBLIC_INTAKE` (proposal §"Authenticated application applicant"). |
| `services/api/app/services/applications.py:847` (reassign new_owner_id) | covered | Replaces existence-only check with real-member validation (proposal §"Application reassign owner"). |
| `services/api/app/services/applications.py:854` (reactivate next_owner_id) | covered | Replaces existence-only check with real-member validation (proposal §"Application reactivate owner"). |
| Application claim owner_id (`_transition_application_locked()` claim branch, `services/api/app/services/applications.py:831`) | covered | Even though the RCA enumerated reassign/reactivate, the proposal also guards claim, which is the actor → owner write that an authenticated officer-shaped synthetic UUID could otherwise complete (proposal §"Application claim owner"). |
| `services/api/app/services/trust.py:302` (signal create) | covered | Reject after `fetch_member_by_id()` (proposal §"Trust signal creation"). |
| `services/api/app/services/trust.py:375` (compute_trust) | covered | Reject before profile read/upsert (proposal §"Trust compute"). |
| `services/api/app/services/trust.py:462` (_recompute_once) | covered | Reject before active-signal listing or audit/mutation writes (proposal §"Trust recompute"). |
| `services/api/app/services/authority.py:142` (`_resolve_member_aliases`) | covered | `synthetic_policy: Literal["reject", "omit"]` parameter, with leadership context using `reject` and succession using `omit` (proposal §"Leadership alias expansion"). |
| `services/api/app/services/authority.py:479` (succession plan roster holders) | covered | Through `_collect_member_aliases(..., synthetic_policy="omit")` at `compute_succession_plan()` (proposal §"Leadership alias expansion"). |
| `services/api/app/services/roster.py:117` (`create_roster_entry`) | covered | Parse `request.member_id` as UUID, fetch row, reject if missing or synthetic (proposal §"Roster entry creation"). |
| `services/api/app/services/members.py:216` (`patch_member_status`) | covered | Reject after `_fetch_member_by_id_for_update()` lock and before transition validation (proposal §"Member status mutation"). |

Read-side surfaces the RCA flagged as "needs join condition" — trust
profile reads (`fetch_trust_profile_by_member_id` /
`list_active_signals_for_member`), roster reads (`_ROSTER_ENTRY_SELECT`,
`list_latest_role_holders`), compliance enumeration
(`list_current_roster_members_by_chapter`,
`run_scheduled_compliance_evaluations`,
`compliance_review` consequence), archive plan
(`list_active_roster_entries_for_chapter`), and owner workload
(`list_open_applications_for_owner_ids`) — are intentionally deferred to
BL-008 (proposal §Anti-scope, §"Repository helper decision",
§"Out of scope for follow-up"). This is honest deferral, not selective
guarding: the slice claim is "prevent new pollution" rather than "repair
pre-existing pollution," and the proposal commits to that boundary
consistently.

Two boundary-completeness checks worth noting:

1. **Owner-id closure under the three transitions.** Application
   `owner_id` can only be written via claim, reassign, and reactivate
   inside `_transition_application_locked()`; submit leaves `owner_id`
   NULL. The proposal guards all three. There is no fourth path that
   would let a synthetic UUID become an `applications.owner_id` after
   the guard lands.

2. **Roster-entry write closure via one create path.** The proposal
   treats `create_roster_entry()` as the sole `roster_entries.member_id`
   write boundary, and the problem map confirms `roster_entries` write
   surface is officer-facing
   (`research/08-synthetic-member-guard-problem-map.md:84-85`). Roster
   transitions in the API mutate roster-entry state, not `member_id`
   identity, so guarding the create path closes the new-pollution
   surface. Discord roster sync resolves Discord user IDs via
   `int(user_id)` and would reject a `public:<hash>` upstream of any
   roster write, so it is not an alternate insertion path
   (`research/08-synthetic-member-guard-problem-map.md:99`,
   `services/discord/app/handlers/roster.py:206`). This is the correct
   factoring; no second write path is left unguarded.

The boundary set is the RCA's "needs filter" set in full, plus
`patch_member_status()` and application `claim`, both of which are
belt-and-suspenders rather than required by the named risk. That is
broader than the strictly-required boundary, not narrower. Risk: LOW.

## Defense-in-depth honesty (authenticated submit)

The brief asks specifically whether authenticated submit rejects
synthetic `applicant_id`. The proposal answers yes, explicitly and with
named code/status/field:

- Q4 says authenticated `POST /api/v1/applications` must reject synthetic
  `applicant_id` with HTTP 422 and `{"detail":{"code":"applicant_synthetic_not_allowed",...}}`
  (proposal §Q4).
- The exception is structurally narrow: only `_SubmissionAuthority.PUBLIC_INTAKE`
  is allowed past the guard, and `submit_public_application()` is the
  only caller that supplies that authority value
  (`services/api/app/services/applications.py:762`,
  `services/api/app/services/applications.py:767`). The bypass is keyed
  to the authority enum already used elsewhere in
  `_submit_application_internal()`, not to a new flag invented for this
  proposal — that prevents the "developer adds another bypass to keep
  green tests" failure mode.
- The component test in the test-intent track exercises this directly:
  "create a synthetic member through public-intake helper, then call
  authenticated `POST /api/v1/applications` with that UUID; assert HTTP
  422 and no application row" (proposal §"Authenticated application
  applicant guard"). That is the actual end-to-end signal, not a unit
  test that only exercises the helper.
- The endpoint mapping is named: the proposal requires a typed
  `SyntheticMemberNotAllowedError` branch *before* the existing generic
  `ValueError → {"code":"validation_error"}` fallback at
  `services/api/app/api/v1/endpoints/applications/_shared.py:171`
  (proposal §Helper signature + location). Without that ordering rule
  the rejection would still happen but the observable signal would be
  the indistinguishable `validation_error` code, defeating the
  per-boundary observability goal.

The proposal also closes the same defense-in-depth question for the
audit/actor invariant in Q8: synthetic members are never valid `actor_id`
values, the synthetic member is the applicant subject, and audit actor
fields use `service` / `public-intake` (proposal §Q8, citing
`proposals/02-public-application-intake.md:69-71`). This is consistent
with INIT-120's audit-substrate rule and is not weakened here.

Risk: LOW.

## Pre-existing-pollution honesty

The brief asks whether deferral to BL-008 is called out clearly in the
supported-surface track. It is, in four converging places:

1. **Net-value statement.** "It prevents new pollution but does not
   hide, migrate, or repair any already-polluted read rows. That keeps
   the change testable and avoids inventing roster read semantics
   before OAuth linking and identity cleanup define the long-term
   model" (proposal §Net-value statement).
2. **Anti-scope.** "No read-side roster hardening for compliance,
   archive counts, succession role-holder lists, or roster listing,"
   "No Discord OAuth linking or synthetic-to-real member conversion.
   Those belong to BL-008," and "No sweep or deletion of existing
   synthetic rows, trust profiles, roster entries, application owners,
   or audit rows" (proposal §Anti-scope).
3. **Supported-surface track blast-radius.** "Pre-existing synthetic
   owners, trust profiles, roster entries, and aliases are not
   repaired. Reads over those rows may still show polluted data until
   BL-008 or the cleanup sweep" (proposal §Supported-surface track,
   blast-radius bullets).
4. **Out-of-scope-for-follow-up.** "BL-008 / INIT-121-followup: Discord
   OAuth linking, read-side roster hardening, and a `members.kind`
   schema column," and "Pre-existing-pollution sweep: if any synthetic
   rows leaked into `roster_entries`, `trust_profiles`, `trust_signals`,
   or application owner fields before this guard landed, BL-008 or a
   dedicated cleanup slice cleans them up" (proposal §Out of scope for
   follow-up).

The Q-decisions also reinforce this honestly:

- Q6 (roster write boundary): "Do not join or rewrite roster read
  queries in INIT-124."
- Q7 (trust profile reads and repository joins): "Existing trust
  profile reads remain unchanged because hiding already-polluted
  profiles would require read-side cleanup semantics and belongs with
  BL-008 or the pre-existing-pollution sweep."
- Q8 (succession): the `omit` policy is the single deliberate
  defense-in-depth concession on the read side, justified explicitly:
  "so one pre-existing polluted roster row does not break the whole
  read path." That is a contained exception, not a hidden read-side
  hardening pass.

The assumption register names the invalidation conditions for the
deferral honestly:

- A2 names the invalidation: "any production member-write path outside
  `resolve_or_create_public_intake_member()` that assigns
  `members.discord_user_id` with the `public:` prefix." If A2 fails the
  whole guard discriminator collapses, and the proposal directs the
  reader to verify by repository search or write-path tracing.
- A3 names roster-text pre-existing pollution explicitly: "Roster
  entries written before INIT-120 do not contain synthetic UUIDs … If
  this assumption is false, the pre-existing-pollution sweep handles it
  outside INIT-124." The succession `omit` test fixture already exercises
  the "pre-existing synthetic roster holder" case, so even if A3 is
  false the slice is still defensible on the leadership/succession
  read path; everywhere else, falsification of A3 routes to BL-008
  rather than being silently absorbed.

Net: the deferral is named with a follow-up work unit (BL-008), is
called out at the surface track / anti-scope / net-value / out-of-scope
levels, and is consistent with the slice's stated purpose ("prevent new
pollution") rather than masked behind language that suggests broader
coverage than the slice delivers. Risk: LOW.

## Notable observations

1. **Single-source discriminator.** `is_synthetic_member()` and the
   `SYNTHETIC_MEMBER_DISCORD_ID_PREFIX = "public:"` constant live in one
   module (`services/api/app/services/members.py`), and the proposal
   forbids re-implementing the prefix check at call sites. That is the
   right shortcut-resistant factoring; the alternative (inline
   `startswith("public:")` at every guard site) would re-introduce the
   "magic prefix duplicated everywhere" failure mode the RCA already
   warns about.

2. **Named error type with stable codes per boundary.** The codes
   (`applicant_synthetic_not_allowed`,
   `application_owner_synthetic_not_allowed`,
   `trust_member_synthetic_not_allowed`,
   `leadership_member_synthetic_not_allowed`,
   `roster_member_synthetic_not_allowed`,
   `member_status_synthetic_not_allowed`) are observability-grade
   discriminators, not generic `validation_error`. Tests assert on
   them. Operators see them. Future read-side work (BL-008) can grep
   these codes to find guarded surfaces. This is the inverse of the
   typical observability shortcut.

3. **Public-submit positive path is part of the test-intent track,
   not assumed.** The proposal includes a positive-path test for
   `POST /api/v1/public/applications` that asserts HTTP 201 and
   `members.discord_user_id LIKE 'public:%'` (proposal §"Public
   submit positive path"), and it cites the existing INIT-120 tests as
   the floor it must not regress
   (`services/api/tests/test_public_intake_submit.py:61`,
   `services/api/tests/test_public_intake_synthetic_member.py:43`).
   That is the correct anti-shortcut: the slice that adds rejection
   logic also re-asserts that the only legitimate creation path still
   succeeds.

4. **Q8 "omit" is a deliberate scope expansion, not a leak.** Strictly,
   "succession-plan alias expansion omits synthetic roster-derived
   holders" is a read-time filter, which on a strict reading of "no
   read-side hardening" would be out of scope. The proposal calls it
   out as a deliberate exception with a specific justification ("one
   pre-existing polluted roster row does not break the whole read
   path") and ties it to assumption A3. Honest scope expansion, not
   silent hardening. Belongs in Step 6a contract definition so the
   `omit` semantics are pinned before tests are encoded.

5. **No SQL repository helper for write-time real-member validation.**
   The proposal explicitly does *not* add `repository.member_exists_real(...)`
   in this slice (proposal §"Repository helper decision"), and the
   reasoning is correct: pushing the filter into canonical repository
   methods would break public-intake idempotency
   (`services/api/app/repositories/members.py:25`,
   `services/api/app/repositories/members.py:36`), because public submit
   intentionally looks up `public:<hash>` through the same path. The
   guard belongs at service write boundaries where the caller knows
   whether it needs a real Discord member. Not a shortcut; correct
   layering.

6. **Helper signature is loose at the type level but the proposal pins
   the usage.** `is_synthetic_member(member_or_discord_user_id: object | str)`
   accepts either a string or an object with a `discord_user_id`
   attribute, and the proposal directs repository callers to pass
   `row["discord_user_id"]` rather than relying on dict handling
   (proposal §Q2). This is a contract-clarity question for Step 6a, not
   a verdict-changing shortcut: if a caller passes a dict-like row
   directly, `getattr(row, "discord_user_id")` will raise rather than
   silently return False. Failure-on-misuse is acceptable; silent
   wrong-answer would have been the shortcut, and the proposal does
   not take that path.

7. **Channel parity preserved.** The proposal applies in all channels
   because it is API service behavior, not a `local`-only branch
   (proposal §Supported-surface track, deployment-mode bullets), and
   explicitly forbids any `local`-only code path. This continues
   INIT-120/INIT-122's channel-template invariant rather than carving
   out a synthetic-guard exception.

8. **Rollback honesty.** Rollback is code-only — revert guard branches
   and error mappings, and explicitly do *not* delete synthetic
   members, applications, audit rows, trust rows, or roster rows on
   rollback (proposal §Migration / rollback). This honors the
   indefinite-retention posture for operational data and avoids the
   "rollback by data deletion" anti-pattern.

9. **Member-status guard is belt-and-suspenders, openly labeled.** The
   RCA marks `patch_member_status()` as "safe" / "no INIT-124 filter
   required unless product wants synthetic rows immutable"
   (`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:56`). The
   proposal still guards it, with an explicit reason: "Allowing status
   mutation would make placeholders look more like real Discord members
   in exact admin surfaces" (proposal §Q5). Including a not-strictly-
   required guard rather than excluding it is the opposite of a
   shortcut.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

The proposal addresses the RCA's named root cause directly (missing
real-Discord-member predicate at officer-facing write entry points), is
write-boundary complete against the RCA's "needs filter" set plus two
belt-and-suspenders sites (claim, member status), implements
authenticated-submit defense-in-depth with stable per-surface error
codes rather than generic `validation_error`, and defers pre-existing
pollution to BL-008 in four converging places (net-value statement,
anti-scope, supported-surface track, out-of-scope for follow-up) with
named invalidation conditions in the assumption register. The single
read-side concession (succession `omit` policy) is a deliberate, named
exception with assumption A3 evidence, not a hidden read-side
hardening pass. No invalidated assumptions and no non-positive value
signal on the current supported surface.
