READ:
- `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md`
- `research/08-synthetic-member-guard-problem-map.md`
- `plans/BACKLOG.md`
- `proposals/02-public-application-intake.md`
- `services/api/app/repositories/members.py`
- `services/api/app/services/members.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/trust.py`
- `services/api/app/services/authority.py`
- `services/api/app/services/read_models.py`
- `services/api/app/services/roster.py`
- `services/api/app/api/v1/endpoints/applications/lifecycle.py`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/api/v1/endpoints/applications/_shared.py`
- `services/api/app/api/v1/endpoints/members.py`
- `services/api/app/api/v1/endpoints/trust/_shared.py`
- `services/api/app/api/v1/endpoints/roster.py`
- `services/api/app/api/v1/endpoints/authority/_shared.py`
- `migrations/versions/wu-011_members.py`
- `migrations/versions/wu-022_applications.py`
- `migrations/versions/wu-007c_roster_foundation.py`
- `services/api/tests/test_public_intake_submit.py`
- `services/api/tests/test_public_intake_synthetic_member.py`
- `services/discord/app/handlers/application_submission.py`
- `services/discord/app/handlers/onboarding.py`
- `services/discord/app/handlers/roster.py`

# INIT-124 / BL-005 Phase 3 - Proposal: Synthetic member write-boundary guard

## Summary

Add a shared synthetic-member predicate and service-layer guards so public-intake placeholder members cannot be written into real-member-only surfaces. INIT-120 deliberately creates `members` rows whose `discord_user_id` starts with `public:` for unauthenticated public applicants, and BL-005 tracks that those rows can pollute roster, trust, officer, and member-facing surfaces unless explicitly filtered (`plans/BACKLOG.md:144`, `plans/BACKLOG.md:148`, `plans/BACKLOG.md:150`). This proposal takes the locked RCA option: write-boundary guard only, no `members.kind` schema column.

The one supported exception remains INIT-120 public submit. `POST /api/v1/public/applications` calls `submit_public_application()` (`services/api/app/api/v1/endpoints/applications/public.py:18`, `services/api/app/api/v1/endpoints/applications/public.py:31`), and that service must keep creating or reusing a synthetic applicant through `resolve_or_create_public_intake_member()` (`services/api/app/services/applications.py:751`, `services/api/app/services/members.py:167`, `services/api/app/services/members.py:175`).

## Net-value statement

This has positive net value because it blocks new synthetic-member contamination at the write boundaries that create officer workload, roster state, trust state, leadership aliases, and member status changes, while preserving public application intake exactly where synthetic applicants are intentional. The RCA found no production global `member_count` query, and the main risk is indirect: exact UUID validation and `roster_entries.member_id` as unconstrained `TEXT` allow synthetic member IDs to become owner, trust, roster, or alias inputs (`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:9`, `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:12`, `migrations/versions/wu-007c_roster_foundation.py:21`).

The slice is intentionally smaller than BL-008. It prevents new pollution but does not hide, migrate, or repair any already-polluted read rows. That keeps the change testable and avoids inventing roster read semantics before OAuth linking and identity cleanup define the long-term model.

## Scope

- Add `is_synthetic_member()` in `services/api/app/services/members.py`.
- Add service-layer guards for authenticated application submit, application owner assignment, application claim, trust signal creation, trust compute, trust recompute, leadership alias expansion, roster entry creation, and member status mutation.
- Add typed error handling so guarded API surfaces return stable 422 response codes instead of generic `validation_error`.
- Keep exact member reads and raw repository lookups unfiltered.
- Keep `submit_public_application()` and `resolve_or_create_public_intake_member()` creating synthetic members.
- Add test intent for every guarded boundary, with a unit and component pair per boundary plus a positive public-submit test.
- Record residual read-side and pre-existing-data risk in `plans/risk/init-124-test-residuals.md`.

## Anti-scope

- No schema migration.
- No `members.kind`, `members.linked_at`, separate synthetic-member table, or namespace refactor.
- No read-side roster hardening for compliance, archive counts, succession role-holder lists, or roster listing.
- No SQL repository helper such as `member_exists_real(...)` for write-side queries in this slice.
- No Discord OAuth linking or synthetic-to-real member conversion. Those belong to BL-008.
- No sweep or deletion of existing synthetic rows, trust profiles, roster entries, application owners, or audit rows.
- No Discord-visible action.

## Implementation decisions taken in proposal

### Q1. Helper location

Put the helper in `services/api/app/services/members.py`. That module already owns member service semantics, exact member reads, status mutation, and the public synthetic creation point (`services/api/app/services/members.py:103`, `services/api/app/services/members.py:167`, `services/api/app/services/members.py:216`).

### Q2. Helper signature

Use:

```python
def is_synthetic_member(member_or_discord_user_id: object | str) -> bool:
    ...
```

If the input is `str`, treat it as `discord_user_id`. Otherwise read `member_or_discord_user_id.discord_user_id`. Repository rows should call the helper with `row["discord_user_id"]`, not rely on dict handling. The helper returns `True` when the Discord identifier starts with `"public:"`.

### Q3. Helper polarity

Use the negative name `is_synthetic_member()`. The locked discriminator is synthetic identity, and the guard sites need to reject synthetic rows. A positive `is_real_discord_member()` would invite call sites to duplicate the negation or conflate "not synthetic" with a fully validated Discord snowflake.

### Q4. Authenticated application submit

Authenticated `POST /api/v1/applications` must reject a synthetic `applicant_id` with HTTP 422 and body `{"detail":{"code":"applicant_synthetic_not_allowed",...}}`. The public submit path remains allowed because `_submit_application_internal()` already receives `submission_authority`, and public submit passes `_SubmissionAuthority.PUBLIC_INTAKE` (`services/api/app/services/applications.py:572`, `services/api/app/services/applications.py:577`, `services/api/app/services/applications.py:762`, `services/api/app/services/applications.py:767`).

### Q5. Member status mutation

`PATCH /api/v1/members/{member_id}/status` must reject synthetic members. The current path locks the member row by UUID before changing status (`services/api/app/services/members.py:216`, `services/api/app/services/members.py:227`, `services/api/app/services/members.py:235`), and synthetic rows share the same status enum as real members because the schema only permits `active`, `suspended`, or `departed` (`migrations/versions/wu-011_members.py:39`). Allowing status mutation would make placeholders look more like real Discord members in exact admin surfaces.

### Q6. Roster write boundary

Roster entry creation is write-side only in this slice. `RosterEntryCreate.member_id` is currently just non-empty text (`services/api/app/contracts/roster.py:29`, `services/api/app/contracts/roster.py:31`), and `roster_entries.member_id` is unconstrained `TEXT` (`migrations/versions/wu-007c_roster_foundation.py:17`, `migrations/versions/wu-007c_roster_foundation.py:21`). For new writes through `create_roster_entry()`, require a UUID string that resolves to a non-synthetic member before insert. Do not join or rewrite roster read queries in INIT-124.

### Q7. Trust profile reads and repository joins

Service-boundary prevention is enough for INIT-124. Trust signal creation, trust compute, and trust recompute must reject synthetic members before they create or update trust rows (`services/api/app/services/trust.py:302`, `services/api/app/services/trust.py:375`, `services/api/app/services/trust.py:462`). Existing trust profile reads remain unchanged because hiding already-polluted profiles would require read-side cleanup semantics and belongs with BL-008 or the pre-existing-pollution sweep.

### Q8. Leadership, owner query, and actor policy

Leadership alias expansion must never add a `public:<hash>` alias. Direct leadership context requests for a synthetic UUID should reject with 422. Succession-plan alias expansion should omit synthetic roster-derived holders from alias sets so one pre-existing polluted roster row does not break the whole read path; it also must not include that synthetic UUID in application owner lookup aliases.

Application owner workload queries do not get repository joins in this slice. Guard owner assignment instead: claim, reassign, and reactivate must validate the owner as a real member before writing `applications.owner_id`. Synthetic members are never valid `actor_id` values for public intake; INIT-120 stores the synthetic member as the applicant subject while audit actor fields use `service` / `public-intake` (`proposals/02-public-application-intake.md:69`, `proposals/02-public-application-intake.md:71`).

## Design

### Helper signature + location

Add to `services/api/app/services/members.py`:

```python
SYNTHETIC_MEMBER_DISCORD_ID_PREFIX = "public:"

def is_synthetic_member(member_or_discord_user_id: object | str) -> bool:
    if isinstance(member_or_discord_user_id, str):
        discord_user_id = member_or_discord_user_id
    else:
        discord_user_id = getattr(member_or_discord_user_id, "discord_user_id")
    return discord_user_id.startswith(SYNTHETIC_MEMBER_DISCORD_ID_PREFIX)
```

Add a small typed exception, preferably in `services/api/app/contracts/members.py`, for guarded write-boundary failures:

```python
class SyntheticMemberNotAllowedError(ValueError):
    def __init__(self, *, code: str, member_id: UUID | str, field: str) -> None:
        self.code = code
        self.member_id = member_id
        self.field = field
        super().__init__(f"synthetic member is not allowed for {field}")
```

The endpoint shared handlers should map this exception to HTTP 422 and preserve `error.code`, `error.member_id`, and `error.field` in `detail`. The authenticated application endpoint currently maps generic `ValueError` to `{"code":"validation_error"}` (`services/api/app/api/v1/endpoints/applications/_shared.py:171`); this proposal requires a specific synthetic-member branch before that fallback.

Outside direct helper unit tests and the public-intake submit path, every production call site that observes `is_synthetic_member(...) is True` must raise immediately through this typed error.

### Boundary checks

Authenticated application applicant:

- Call site: `_submit_application_internal()` immediately after `fetch_member_by_id(connection, validated.applicant_id)` at `services/api/app/services/applications.py:594`.
- Guard: if the row exists and `submission_authority != _SubmissionAuthority.PUBLIC_INTAKE`, call `is_synthetic_member(row["discord_user_id"])`; if true, raise `SyntheticMemberNotAllowedError(code="applicant_synthetic_not_allowed", field="applicant_id", member_id=validated.applicant_id)`.
- Expected API result: HTTP 422, `{"detail":{"code":"applicant_synthetic_not_allowed","field":"applicant_id","member_id":"..."}}`.
- Exception: public submit passes `_SubmissionAuthority.PUBLIC_INTAKE` and must continue to accept the synthetic applicant created at `services/api/app/services/applications.py:751`.

Application claim owner:

- Call site: `_transition_application_locked()` in the `action == "claim"` branch before `updated["owner_id"] = reviewer_id` (`services/api/app/services/applications.py:831`, `services/api/app/services/applications.py:832`).
- Guard: fetch `reviewer_id` with `fetch_member_by_id(active_connection, reviewer_id)` and reject when `is_synthetic_member(row["discord_user_id"])`.
- Expected API result: HTTP 422, `{"detail":{"code":"application_owner_synthetic_not_allowed","field":"actor_id","member_id":"..."}}`.

Application reassign owner:

- Call site: `_transition_application_locked()` in the `action == "reassign"` branch where `new_owner_id` is currently checked only for existence (`services/api/app/services/applications.py:844`, `services/api/app/services/applications.py:847`).
- Guard: replace the existence-only check with real-member validation for `request.new_owner_id`.
- Expected API result: HTTP 422, `{"detail":{"code":"application_owner_synthetic_not_allowed","field":"new_owner_id","member_id":"..."}}`.

Application reactivate owner:

- Call site: `_transition_application_locked()` in the `action == "reactivate"` branch where `next_owner_id` is currently checked only for existence (`services/api/app/services/applications.py:850`, `services/api/app/services/applications.py:854`).
- Guard: replace the existence-only check with real-member validation for `next_owner_id`.
- Expected API result: HTTP 422, `{"detail":{"code":"application_owner_synthetic_not_allowed","field":"new_owner_id","member_id":"..."}}`.

Trust signal creation:

- Call site: `create_trust_signal()` after `fetch_member_by_id(connection, request.member_id)` (`services/api/app/services/trust.py:302`, `services/api/app/services/trust.py:303`).
- Guard: reject when the fetched row is synthetic.
- Expected API result: HTTP 422, `{"detail":{"code":"trust_member_synthetic_not_allowed","field":"member_id","member_id":"..."}}`.

Trust compute:

- Call site: `compute_trust()` after `fetch_member_by_id(connection, member_id)` (`services/api/app/services/trust.py:375`, `services/api/app/services/trust.py:376`).
- Guard: reject when the fetched row is synthetic before reading or writing the trust profile.
- Expected API result: HTTP 422, `{"detail":{"code":"trust_member_synthetic_not_allowed","field":"member_id","member_id":"..."}}`.

Trust recompute:

- Call site: `_recompute_once()` after `fetch_member_by_id(connection, member_id)` and before `list_active_signals_for_member()` (`services/api/app/services/trust.py:462`, `services/api/app/services/trust.py:472`).
- Guard: reject when the fetched row is synthetic.
- Expected API result: HTTP 422, `{"detail":{"code":"trust_member_synthetic_not_allowed","field":"member_id","member_id":"..."}}`.

Leadership alias expansion:

- Call site: `_resolve_member_aliases()` where UUID inputs fetch `member_row` and add `member_row["discord_user_id"]` to text aliases (`services/api/app/services/authority.py:142`, `services/api/app/services/authority.py:159`, `services/api/app/services/authority.py:161`).
- Guard: add a policy argument to alias collection, such as `synthetic_policy: Literal["reject", "omit"]`.
- Direct leadership context: `read_leadership_context()` calls `_collect_member_aliases(..., synthetic_policy="reject")` (`services/api/app/services/read_models.py:232`, `services/api/app/services/read_models.py:247`). Expected API result: HTTP 422, `{"detail":{"code":"leadership_member_synthetic_not_allowed","field":"member_id","member_id":"..."}}`.
- Succession plan: `compute_succession_plan()` calls `_collect_member_aliases(..., synthetic_policy="omit")` when expanding roster-derived holders (`services/api/app/services/authority.py:493`, `services/api/app/services/authority.py:527`). Expected API result: no error; the synthetic row contributes no `public:` text alias and no UUID owner alias to grant, application, or ticket lookups.

Roster entry creation:

- Call site: `create_roster_entry()` before `_insert_roster_entry()` stores `request.member_id` (`services/api/app/services/roster.py:117`, `services/api/app/services/roster.py:124`, `services/api/app/services/roster.py:131`).
- Guard: parse `request.member_id` as a UUID string, fetch the member row with `fetch_member_by_id()`, and reject if missing or synthetic. Missing/non-UUID can use existing validation handling; synthetic uses the specific code.
- Expected API result for synthetic: HTTP 422, `{"detail":{"code":"roster_member_synthetic_not_allowed","field":"member_id","member_id":"..."}}`.
- Expected API result for non-UUID or missing member: HTTP 422 or 404 per implementation convention, but not the synthetic code.

Member status mutation:

- Call site: `patch_member_status()` inside `mutate_projection()` after `_fetch_member_by_id_for_update(connection, member_id)` and before transition validation (`services/api/app/services/members.py:216`, `services/api/app/services/members.py:227`, `services/api/app/services/members.py:230`).
- Guard: reject if the locked row is synthetic.
- Expected API result: HTTP 422, `{"detail":{"code":"member_status_synthetic_not_allowed","field":"member_id","member_id":"..."}}`.

### Repository helper decision

Do not add a SQL repository helper such as `repository.member_exists_real(...)` in this slice. The canonical repository methods stay exact and unfiltered because public intake idempotency and exact member reads need them (`services/api/app/repositories/members.py:25`, `services/api/app/repositories/members.py:36`; `research/08-synthetic-member-guard-problem-map.md:110`). The guard belongs at service write boundaries where the caller knows whether it needs a real Discord member.

Read-side hardening for `roster_entries`, compliance, archive counts, trust profile reads, and owner workload queries is deferred to BL-008 because those paths need a durable identity contract for existing `TEXT` roster member IDs and any already-polluted rows.

## Supported-surface track

Deployment mode:

- Apply in all channels because this is API service behavior, not a local-only route condition.
- Validate first in the local channel because INIT-120 public intake local proof covers browser, API, Cedar, database, and audit composition (`research/08-synthetic-member-guard-problem-map.md:267`, `research/08-synthetic-member-guard-problem-map.md:270`).
- No code path may branch on channel; INIT-120 already requires local concrete manifests and the same logical contract for remote materialization (`proposals/02-public-application-intake.md:141`, `proposals/02-public-application-intake.md:143`, `proposals/02-public-application-intake.md:145`).

Cohort:

- Cluster API consumers using `POST /api/v1/applications`, application transitions, trust endpoints, roster entry creation, leadership context, succession plan, and member status mutation.
- Officer-facing API and UI consumers that rely on owner workload, trust, roster, leadership, and status semantics.
- Public web applicants are not in the rejection cohort because `POST /api/v1/public/applications` must keep succeeding.

Adjacent paths:

- Discord submission service is adjacent but should continue to pass because it resolves a real Discord actor ID through `/api/v1/members/by-discord/{discord_user_id}` and then submits authenticated applications as that member (`services/discord/app/handlers/application_submission.py:29`, `services/discord/app/handlers/application_submission.py:60`, `services/discord/app/handlers/application_submission.py:65`, `services/discord/app/handlers/application_submission.py:75`).
- Discord onboarding should continue to pass because it gets `discord_user_id` from the Discord join event, creates or resolves that real member, then computes trust (`services/discord/app/handlers/onboarding.py:54`, `services/discord/app/handlers/onboarding.py:62`, `services/discord/app/handlers/onboarding.py:99`).
- Discord roster sync expects Discord user IDs and calls `int(user_id)` during guild resolution, so synthetic roster events should be stopped at roster write time rather than handled in Discord mutation code (`services/discord/app/handlers/roster.py:53`, `services/discord/app/handlers/roster.py:59`, `services/discord/app/handlers/roster.py:206`).
- Audit substrate remains unchanged. Public intake uses service actor `public-intake`; synthetic members are application subjects, not actors (`proposals/02-public-application-intake.md:69`, `proposals/02-public-application-intake.md:71`).
- INIT-120 public submit must keep creating synthetic members via `resolve_or_create_public_intake_member()` and submitting through `_SubmissionAuthority.PUBLIC_INTAKE` (`services/api/app/services/members.py:167`, `services/api/app/services/members.py:175`, `services/api/app/services/applications.py:762`, `services/api/app/services/applications.py:767`).

Blast-radius:

- New 422 rejections can affect any caller that currently passes a synthetic UUID into authenticated/officer routes.
- Exact member reads still expose synthetic rows to authorized callers; this is intentional and not a roster/list aggregate.
- Pre-existing synthetic owners, trust profiles, roster entries, and aliases are not repaired. Reads over those rows may still show polluted data until BL-008 or the cleanup sweep.
- No Discord-visible mutation occurs.

Migration / rollback:

- No data migration.
- Deploy code and tests together.
- Rollback is code-only: remove or revert the guard branches and error mappings. Do not delete synthetic members or dependent applications/trust/roster rows during rollback.

Observability:

- Stable error codes are the primary observable signal: `applicant_synthetic_not_allowed`, `application_owner_synthetic_not_allowed`, `trust_member_synthetic_not_allowed`, `leadership_member_synthetic_not_allowed`, `roster_member_synthetic_not_allowed`, and `member_status_synthetic_not_allowed`.
- Existing access logs and API error responses are enough for this slice. A metric can be added later if these rejections are frequent, but do not add a telemetry subsystem in INIT-124.
- The residual-risk artifact records untested or intentionally deferred read-side pollution risks.

## Assumption register

- A1: `public:` prefix is a stable identifier for synthetic members. Verified: Discord IDs are numeric snowflakes returned as strings, not prefixed text (`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:111`, `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:113`, `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:115`). Local synthetic creation uses `discord_user_id=f"public:{digest[:32]}"` (`services/api/app/services/members.py:173`, `services/api/app/services/members.py:175`). Invalidated by: a Discord-origin member row whose `discord_user_id` starts with literal `public:`, verified by SQL such as `SELECT id, discord_user_id FROM members WHERE discord_user_id LIKE 'public:%';` plus source tracing that shows the row came from Discord join/import rather than public application intake.
- A2: No production code creates members with `public:` prefix other than the INIT-120 public-intake helper. Repository search found only the helper's member identifier creation at `services/api/app/services/members.py:175`; the other production `public:` occurrence is public submit's client application ID, not a member ID (`services/api/app/services/applications.py:744`). Invalidated by: any production member-write path outside `resolve_or_create_public_intake_member()` that assigns `members.discord_user_id` with the `public:` prefix, verified by repository search or write-path tracing.
- A3: Roster entries written before INIT-120 do not contain synthetic UUIDs. Roster foundation predates synthetic public member creation and stores `member_id` as text (`migrations/versions/wu-007c_roster_foundation.py:17`, `migrations/versions/wu-007c_roster_foundation.py:21`), while INIT-120 introduced synthetic applicant members later as the public submit persistence model (`proposals/02-public-application-intake.md:65`, `proposals/02-public-application-intake.md:69`, `proposals/02-public-application-intake.md:70`). If this assumption is false, the pre-existing-pollution sweep handles it outside INIT-124.

## Test-intent track

Authenticated application applicant guard:

- Unit: call the internal applicant-validation helper with a synthetic `discord_user_id` row and `_SubmissionAuthority.USER`; assert `SyntheticMemberNotAllowedError.code == "applicant_synthetic_not_allowed"`.
- Component: create a synthetic member through public-intake helper, then call authenticated `POST /api/v1/applications` with that UUID; assert HTTP 422 and no application row.
- Metadata: named risk: authenticated applicant contamination; intended behavior: non-public application submit rejects synthetic applicants; selected levels: unit + component; fixture source/application point: synthetic row from public-intake helper applied as `applicant_id`; assumption links: A1, A2; observable signal: `applicant_synthetic_not_allowed`, HTTP 422, no application insert; residual risk: pre-existing applications with synthetic applicants remain unchanged.

Public submit positive path:

- Unit: `is_synthetic_member("public:<hash>")` returns `True`, and public authority bypass logic allows `_SubmissionAuthority.PUBLIC_INTAKE`.
- Component: call `POST /api/v1/public/applications`; assert HTTP 201, queued application row exists, and applicant `members.discord_user_id` starts with `public:`. This preserves existing public-intake expectations (`services/api/tests/test_public_intake_submit.py:61`, `services/api/tests/test_public_intake_synthetic_member.py:43`).
- Metadata: named risk: public-intake regression; intended behavior: the sole approved synthetic creation path still succeeds; selected levels: unit + component; fixture source/application point: public intake request fixture applied to `POST /api/v1/public/applications`; assumption links: A1, A2; observable signal: HTTP 201 plus `members.discord_user_id LIKE 'public:%'`; residual risk: duplicate/idempotency edge cases stay covered by INIT-120 tests, not expanded here.

Application owner assignment and claim guard:

- Unit: validate real-owner helper rejects synthetic rows for fields `actor_id` and `new_owner_id` with `application_owner_synthetic_not_allowed`.
- Component: create an application, then attempt `claim` as a synthetic user actor, `reassign` to a synthetic `new_owner_id`, and `reactivate` to a synthetic `new_owner_id`; each returns HTTP 422 and leaves `owner_id` unchanged.
- Metadata: named risk: synthetic officer workload ownership; intended behavior: owner writes reject synthetic actors/owners; selected levels: unit + component; fixture source/application point: synthetic public-intake member applied as transition actor or `new_owner_id`; assumption links: A1, A2; observable signal: `application_owner_synthetic_not_allowed`, HTTP 422, unchanged `owner_id`; residual risk: already-owned synthetic applications are not repaired.

Trust signal guard:

- Unit: call trust member validation with a synthetic row; assert `trust_member_synthetic_not_allowed`.
- Component: `POST /api/v1/trust/signals` with synthetic `member_id`; assert HTTP 422 and no `trust_signals` row.
- Metadata: named risk: synthetic trust evidence; intended behavior: trust signal creation rejects synthetic subjects; selected levels: unit + component; fixture source/application point: synthetic public-intake member applied as trust `member_id`; assumption links: A1, A2; observable signal: `trust_member_synthetic_not_allowed`, HTTP 422, no `trust_signals` insert; residual risk: pre-existing synthetic trust signals remain visible.

Trust compute guard:

- Unit: compute path validation rejects synthetic rows before profile lookup/upsert.
- Component: `POST /api/v1/trust/compute/{synthetic_member_id}`; assert HTTP 422 and no `trust_profiles` row.
- Metadata: named risk: synthetic trust profile creation; intended behavior: compute rejects synthetic members before profile mutation; selected levels: unit + component; fixture source/application point: synthetic public-intake member applied as compute path member ID; assumption links: A1, A2; observable signal: `trust_member_synthetic_not_allowed`, HTTP 422, no `trust_profiles` insert/upsert; residual risk: existing synthetic profiles are not hidden.

Trust recompute guard:

- Unit: recompute path validation rejects synthetic rows before active-signal listing.
- Component: `POST /api/v1/trust/recompute/{synthetic_member_id}`; assert HTTP 422 and no mutation result/audit state change.
- Metadata: named risk: synthetic trust recomputation; intended behavior: recompute rejects synthetic members before signal reads or audit/mutation writes; selected levels: unit + component; fixture source/application point: synthetic public-intake member applied as recompute path member ID; assumption links: A1, A2; observable signal: `trust_member_synthetic_not_allowed`, HTTP 422, no mutation/audit result; residual risk: batch recompute behavior outside this endpoint is not expanded.

Leadership alias expansion guard:

- Unit: `_collect_member_aliases(..., synthetic_policy="reject")` raises for a synthetic UUID; `_collect_member_aliases(..., synthetic_policy="omit")` returns no `public:` alias and no synthetic UUID owner alias.
- Component: `GET /api/v1/members/{synthetic_member_id}/leadership-context` returns HTTP 422. A succession-plan fixture with a pre-existing synthetic roster holder returns HTTP 200 and excludes pending-work rows that would only be reachable through `public:<hash>`.
- Metadata: named risk: synthetic leadership alias leakage; intended behavior: direct leadership rejects synthetic UUIDs and succession alias expansion omits synthetic roster holders; selected levels: unit + component; fixture source/application point: synthetic public-intake member applied to leadership context and seeded as a roster holder for succession; assumption links: A1, A2, A3; observable signal: `leadership_member_synthetic_not_allowed` for direct reads, HTTP 200 with no `public:` or synthetic UUID owner alias for succession; residual risk: other read-side roster aggregates remain deferred.

Roster entry creation guard:

- Unit: roster member validation rejects a synthetic UUID string with `roster_member_synthetic_not_allowed`.
- Component: `POST /api/v1/roster-entries` with synthetic `member_id`; assert HTTP 422 and no roster row.
- Metadata: named risk: synthetic roster membership; intended behavior: roster entry creation rejects synthetic member IDs before insert; selected levels: unit + component; fixture source/application point: synthetic public-intake member UUID applied as `RosterEntryCreate.member_id`; assumption links: A1, A2; observable signal: `roster_member_synthetic_not_allowed`, HTTP 422, no roster row; residual risk: historical roster rows are not swept.

Member status guard:

- Unit: status mutation validation rejects a locked synthetic member row with `member_status_synthetic_not_allowed`.
- Component: `PATCH /api/v1/members/{synthetic_member_id}/status` with a correct ETag; assert HTTP 422 and unchanged status/version.
- Metadata: named risk: synthetic member lifecycle mutation; intended behavior: status updates reject synthetic rows after lock and before version/status mutation; selected levels: unit + component; fixture source/application point: synthetic public-intake member applied as path `member_id` with valid ETag; assumption links: A1, A2; observable signal: `member_status_synthetic_not_allowed`, HTTP 422, unchanged status/version; residual risk: exact reads can still show synthetic rows.

### Residual-risk artifact

Write residual test and data risks to `plans/risk/init-124-test-residuals.md`.

## Migration / rollback

Migration is code-only:

1. Add tests that encode the guard contract and the public-submit positive path.
2. Add helper and typed synthetic-member error.
3. Add service guard call sites.
4. Add endpoint error mappings.
5. Run the focused API test suite.

Rollback is code-only:

1. Revert the guard call sites and error mappings.
2. Keep synthetic member rows, applications, audit rows, trust rows, and roster rows intact.
3. If rollback is triggered because a real caller depended on synthetic writes, record that caller and decide whether it belongs in BL-008 linking or in a separate product correction.

No schema downgrade, data deletion, or Discord-visible recovery action is part of rollback.

## Out of scope for follow-up

- BL-008 / INIT-121-followup: Discord OAuth linking, read-side roster hardening, and a `members.kind` schema column.
- Pre-existing-pollution sweep: if any synthetic rows leaked into `roster_entries`, `trust_profiles`, `trust_signals`, or application owner fields before this guard landed, BL-008 or a dedicated cleanup slice cleans them up.
