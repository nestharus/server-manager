## Inputs read

READ:
- `proposals/05-synthetic-member-guard.md`
- `research/08-synthetic-member-guard-problem-map.md`
- `plans/risk/init-124-audit.md`
- `plans/risk/init-124-scope.md`
- `plans/risk/init-124-shortcut.md`
- `plans/risk/init-124-supported-surface.md`
- `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md`
- `plans/audit-history/init-124-audit-history.md`
- `services/api/app/services/members.py`
- `services/api/app/contracts/members.py`
- `services/api/app/repositories/members.py`
- `services/api/app/services/applications.py`
- `services/api/app/api/v1/endpoints/applications/lifecycle.py`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/api/v1/endpoints/applications/_shared.py`
- `services/api/app/services/trust.py`
- `services/api/app/repositories/trust.py`
- `services/api/app/api/v1/endpoints/trust/_shared.py`
- `services/api/app/api/v1/endpoints/trust/signals.py`
- `services/api/app/api/v1/endpoints/trust/profiles.py`
- `services/api/app/api/v1/endpoints/trust/recompute.py`
- `services/api/app/services/authority.py`
- `services/api/app/services/read_models.py`
- `services/api/app/services/leadership_handoff_applications.py`
- `services/api/app/services/leadership_handoff_tickets.py`
- `services/api/app/services/compliance.py`
- `services/api/app/api/v1/endpoints/authority/_shared.py`
- `services/api/app/api/v1/endpoints/authority/leadership_context.py`
- `services/api/app/api/v1/endpoints/authority/succession_plan.py`
- `services/api/app/services/roster.py`
- `services/api/app/repositories/roster.py`
- `services/api/app/contracts/roster.py`
- `services/api/app/api/v1/endpoints/roster.py`
- `services/api/app/api/v1/endpoints/members.py`
- `services/api/tests/test_public_intake_submit.py`
- `services/api/tests/test_public_intake_synthetic_member.py`
- `services/api/tests/test_applications.py`
- `services/api/tests/test_members.py`
- `services/api/tests/test_trust.py`
- `services/api/tests/test_trust_signals.py`
- `services/api/tests/test_trust_recompute.py`
- `services/api/tests/trust_helpers.py`
- `services/api/tests/test_roster.py`
- `services/api/tests/test_leadership_context.py`
- `services/api/tests/test_succession_plan.py`
- `services/api/tests/authority_slice_helpers.py`

No contradiction was found for approved assumptions A1..A3. A1 and A2 are supported by current source search: the only production `public:` member identifier creation is `services/api/app/services/members.py:173-175`; `services/api/app/services/applications.py:744` creates a public client application id, not a member id. A3 is not contradicted by source, but remains a data-state assumption that can only be falsified by a database check against `roster_entries`.

## Predicate helper location hookpoints

Reusable hookpoints:

- `services/api/app/services/members.py:32-43` contains current member service constants and the `PUBLIC_INTAKE_MEMBER_ACTOR`.
- `services/api/app/services/members.py:167-193` is the only current synthetic member creation path. It generates `discord_user_id=f"public:{digest[:32]}"` at `services/api/app/services/members.py:173-175`.
- `services/api/app/services/members.py:74-83` maps canonical repository rows to `MemberRead`; helper callers can pass `row["discord_user_id"]` or a `MemberRead`.
- `services/api/app/services/members.py:277-282` exports the module public surface through `__all__`.

Confirmed location and insertion point:

- The proposed location, `services/api/app/services/members.py`, matches the current source structure. There is no separate identity module, and this file already owns exact member reads, status mutation, and the public synthetic creation point.
- Exact insertion point: add `SYNTHETIC_MEMBER_DISCORD_ID_PREFIX = "public:"` and `is_synthetic_member(...)` after `PUBLIC_INTAKE_MEMBER_ACTOR` at `services/api/app/services/members.py:40-43` and before `_generated_audit_context()` at `services/api/app/services/members.py:46`.
- Add `is_synthetic_member` to `__all__` at `services/api/app/services/members.py:277-282`.

New files needed:

- No new production file is needed for the helper.
- A new focused pytest file is useful for the unit-level predicate tests, e.g. `services/api/tests/test_synthetic_member_guard.py`, unless implementation prefers colocating a small unit test in `services/api/tests/test_public_intake_synthetic_member.py`.

Conflicting systems:

- Repository rows are dictionaries from `psycopg.rows.dict_row`; dicts do not expose `.discord_user_id`. The proposal already says repository rows should call `is_synthetic_member(row["discord_user_id"])`, not pass the row directly.
- `fetch_member_by_id()` and `fetch_member_by_discord_id()` in `services/api/app/repositories/members.py:25-44` must remain exact and unfiltered because public intake idempotency needs exact lookup of `public:` rows.

Deletion candidates:

- None. Do not delete or filter canonical repository lookup functions.

## Authenticated submit guard hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/applications/lifecycle.py:45-56` is authenticated `POST /api/v1/applications`; it delegates to `submit_application()`.
- `services/api/app/services/applications.py:723-734` wraps authenticated submit with `submission_authority=_SubmissionAuthority.USER`.
- `services/api/app/services/applications.py:572-579` is the shared `_submit_application_internal(...)` signature with `submission_authority`.
- `services/api/app/services/applications.py:594-596` is the current applicant existence check. This is the insertion point for the synthetic guard: keep the fetched row, reject synthetic when authority is not `_SubmissionAuthority.PUBLIC_INTAKE`, and preserve the existing missing-member behavior.
- `services/api/app/api/v1/endpoints/applications/_shared.py:171-175` currently maps generic `ValueError` to `{"code": "validation_error"}`. The typed synthetic exception branch must be added before this fallback.

New files needed:

- No new production file. `SyntheticMemberNotAllowedError` can live in `services/api/app/contracts/members.py`, which currently contains member DTOs and member exceptions at `services/api/app/contracts/members.py:42-61`.
- New or expanded component tests can reuse `services/api/tests/test_public_intake_submit.py` or `services/api/tests/test_applications.py`.

Conflicting systems:

- Public and authenticated submit share `_submit_application_internal()`. A guard placed only on `fetch_member_by_id()` or the repository would break public submit; the guard must branch on `submission_authority`.
- `services/api/tests/test_public_intake_submit.py:98-139` already asserts authenticated submit keeps the user surface and authority gate for a real member. This is the positive real-member case to preserve.

Deletion candidates:

- Delete no path. Replace no dispatch. The authority split already exists and should be reused.

## Owner claim/reassign/reactivate hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/applications/lifecycle.py:76-97` is `POST /api/v1/applications/{application_id}/transitions`.
- `services/api/app/services/applications.py:929-1000` is the outer `transition_application()` flow; it computes `reviewer_id` and delegates to `_transition_application_locked()`.
- `services/api/app/services/applications.py:797-833` is the locked transition mutation path. The claim insertion point is immediately before `updated["owner_id"] = reviewer_id` at `services/api/app/services/applications.py:831-832`.
- `services/api/app/services/applications.py:844-849` is the reassign owner existence check. Replace this existence-only check with a real-member validation.
- `services/api/app/services/applications.py:850-856` is the reactivate owner existence check. Replace this existence-only check with the same real-member validation.
- `services/api/app/api/v1/endpoints/applications/_shared.py:171-175` is the application error fallback; add the typed synthetic branch before generic `ValueError`.

New files needed:

- No new production file.
- Component tests can extend `services/api/tests/test_applications.py`, which already has helpers for members, grants, submit, claim, and transition ETags at `services/api/tests/test_applications.py:63-157` and existing claim/review tests at `services/api/tests/test_applications.py:270-418`.

Conflicting systems:

- `_reviewer_id()` is actor-derived. Claim should only raise `application_owner_synthetic_not_allowed` when `reviewer_id` resolves to a synthetic member. Missing or non-UUID actor shapes should keep their existing error behavior.
- Existing positive claim behavior for real member reviewers is covered by `services/api/tests/test_applications.py:270-299` and `services/api/tests/test_applications.py:302-418`.

Deletion candidates:

- The duplicated existence-only checks at `services/api/app/services/applications.py:847-848` and `services/api/app/services/applications.py:854-855` are replacement candidates for a local real-member validation helper inside `applications.py`; do not add compatibility fallback checks after the synthetic guard.

## Trust signal/compute/recompute hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/trust/signals.py:19-37` is `POST /api/v1/trust/signals`; it delegates to `create_trust_signal()`.
- `services/api/app/services/trust.py:302-304` is the trust signal member existence check. Use the fetched row to reject synthetic before `insert_trust_signal()` at `services/api/app/services/trust.py:310-325`.
- `services/api/app/api/v1/endpoints/trust/profiles.py:25-46` is `POST /api/v1/trust/compute/{member_id}`; it delegates to `compute_trust()`.
- `services/api/app/services/trust.py:375-380` is the compute path existence/profile-read block. Use the fetched row to reject synthetic before reading or writing a trust profile.
- `services/api/app/api/v1/endpoints/trust/recompute.py:20-43` is `POST /api/v1/trust/recompute/{member_id}`; it delegates to `recompute_trust_profile()`.
- `services/api/app/services/trust.py:462-472` is `_recompute_once()`; reject synthetic after `fetch_member_by_id()` and before `get_trust_profile_for_update()` / `list_active_signals_for_member()`.
- `services/api/app/api/v1/endpoints/trust/_shared.py:57-97` maps trust errors. It currently handles member-not-found and trust-specific errors only; add `SyntheticMemberNotAllowedError` mapping to 422 there.
- `services/api/app/repositories/trust.py:27-35`, `services/api/app/repositories/trust.py:151-171`, and `services/api/app/repositories/trust.py:174-186` are exact trust reads/locks and are not the right place for this slice's guard.

New files needed:

- No new production file.
- Tests can extend existing trust component files:
  - signal create: `services/api/tests/test_trust_signals.py`, using `_signal_payload()` at `services/api/tests/test_trust_signals.py:25-46`;
  - compute: `services/api/tests/test_trust.py`, using `_trust_signals()` and profile count helpers at `services/api/tests/test_trust.py:82-166`;
  - recompute: `services/api/tests/test_trust_recompute.py`, using `_setup_recompute_member()` and `_create_signal()` at `services/api/tests/test_trust_recompute.py:48-77`.

Conflicting systems:

- Trust profile reads intentionally remain unchanged. `GET /api/v1/trust/{member_id}` at `services/api/app/api/v1/endpoints/trust/profiles.py:49-64` can still read a pre-existing synthetic trust profile if one already exists.
- `services/api/tests/trust_helpers.py:79-86` creates real members through the API and should continue to pass as the positive real-member helper.

Deletion candidates:

- None in repositories. Do not add or delete trust repository joins for INIT-124.

## Leadership alias expansion hookpoints

Reusable hookpoints:

- `services/api/app/services/leadership.py` is absent. Alias resolution lives in `services/api/app/services/authority.py`.
- `services/api/app/services/authority.py:131-139` normalizes holder IDs as UUID strings or numeric Discord IDs.
- `services/api/app/services/authority.py:142-163` is `_resolve_member_aliases()`. It currently adds `member_row["discord_user_id"]` for any UUID-backed member at `services/api/app/services/authority.py:159-161`; this is where a synthetic UUID expands to `public:<hash>`.
- `services/api/app/services/authority.py:166-179` is `_collect_member_aliases()`. This is the natural location for a keyword-only `synthetic_policy` and the policy loop.
- Direct leadership context enters through `services/api/app/api/v1/endpoints/authority/leadership_context.py:19-33`, then `services/api/app/services/read_models.py:232-251`. This call should pass `synthetic_policy="reject"`.
- Succession plan enters through `services/api/app/api/v1/endpoints/authority/succession_plan.py:17-26`, then `services/api/app/services/authority.py:479-570`. The roster-holder alias call at `services/api/app/services/authority.py:527-530` should pass `synthetic_policy="omit"`.
- `services/api/app/api/v1/endpoints/authority/_shared.py:68-122` maps authority/read-model errors. It currently maps `InvalidHolderIdError` and generic `ValueError`; add the typed synthetic branch before generic `ValueError`.

New files needed:

- No new production file.
- Tests can extend `services/api/tests/test_leadership_context.py` for direct reject/real accept and `services/api/tests/test_succession_plan.py` for succession omit/real accept.

Conflicting systems:

- `_collect_member_aliases()` has more current consumers than the proposal's direct leadership/succession pair:
  - permission aliasing in `_collect_actor_grant_aliases()` at `services/api/app/services/authority.py:387-404`;
  - application handoff at `services/api/app/services/leadership_handoff_applications.py:65-73`;
  - ticket handoff at `services/api/app/services/leadership_handoff_tickets.py:50-58`;
  - compliance evidence submitter matching at `services/api/app/services/compliance.py:496-501`;
  - stale handoff predecessor expansion in `services/api/app/services/read_models.py:292`.
- Because of those extra consumers, implementation should either make `synthetic_policy` keyword-only with a default that preserves existing non-target call sites, or update every call site explicitly. Default-to-reject is safest for real-member-only semantics, but may change authority/compliance/handoff behavior beyond the proposal. Default-to-current behavior would preserve non-target call sites but risks future synthetic leakage. This needs a deliberate Step 6 contract choice.
- Direct leadership context currently allows numeric IDs without a member row and returns an empty shape, as tested at `services/api/tests/test_leadership_context.py:50-77`. The synthetic reject should only trigger when an input resolves to a synthetic member row, not for a non-member numeric string.

Deletion candidates:

- No deletion. Do not create `services/api/app/services/leadership.py`; use the existing authority/read-model split.

## Roster entry creation hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/roster.py:143-162` is `POST /api/v1/roster-entries`.
- `services/api/app/services/roster.py:117-174` is `create_roster_entry()`.
- `services/api/app/services/roster.py:124-135` is the mutation insertion point: validate the chapter role, parse `request.member_id` as UUID, fetch member row, reject missing/synthetic, then call `_insert_roster_entry()`.
- `services/api/app/contracts/roster.py:29-32` currently defines `RosterEntryCreate.member_id` as any non-empty `str`.
- `services/api/app/repositories/roster.py:28-52` is the raw insert. It should remain a raw repository function.
- `services/api/app/api/v1/endpoints/roster.py:105-140` maps roster errors. It currently has no generic `ValueError` mapping and no synthetic branch; add explicit typed handling for the new error and decide the non-UUID/missing-member convention separately.

New files needed:

- No new production file.
- Tests can extend `services/api/tests/test_roster.py`.

Conflicting systems:

- Existing roster tests create entries with literal `"member-1"` by default via `_create_entry()` at `services/api/tests/test_roster.py:164-181`, and assert duplicate behavior using `"member-1"` at `services/api/tests/test_roster.py:291-310`. The approved proposal requires roster creation to accept only UUID strings that resolve to non-synthetic members. These tests and fixtures must be updated to seed real members and pass their UUIDs.
- `roster_entries.member_id` is still unconstrained `TEXT`, and `services/api/app/repositories/roster.py:170-193` reads latest holders without joining `members`. This is intentional anti-scope for INIT-124; only new create writes are guarded.

Deletion candidates:

- The test fixture default `member_id="member-1"` at `services/api/tests/test_roster.py:168` is a replacement candidate. It should not survive if create now requires real member UUIDs.
- No repository deletion.

## PATCH member status hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/members.py:148-173` is `PATCH /api/v1/members/{member_id}/status`.
- `services/api/app/services/members.py:216-274` is `patch_member_status()`.
- `services/api/app/services/members.py:227-230` is the locked row fetch. The synthetic guard insertion point is after `_fetch_member_by_id_for_update()` returns a row and before `from_status = row["status"]` / transition validation at `services/api/app/services/members.py:230-233`.
- `services/api/app/api/v1/endpoints/members.py:61-86` maps member errors. Add the typed synthetic branch before falling through to `raise error`.

New files needed:

- No new production file.
- Tests can extend `services/api/tests/test_members.py`, which already has a positive status mutation test at `services/api/tests/test_members.py:266-307` and stale-version coverage at `services/api/tests/test_members.py:309-340`.

Conflicting systems:

- Exact member reads remain unfiltered at `services/api/app/services/members.py:196-213`; status mutation is the only member endpoint guarded in this slice.
- The guard should run inside the locked mutation closure so the status transition and optimistic-locking flow stay coherent.

Deletion candidates:

- None.

## Public submit positive-case hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/applications/public.py:18-35` is public `POST /api/v1/public/applications`.
- `services/api/app/services/applications.py:737-769` is `submit_public_application()`.
- `services/api/app/services/applications.py:751-755` resolves or creates the synthetic public-intake member.
- `services/api/app/services/applications.py:756-768` submits the synthetic member through `_submit_application_internal()` with `submission_authority=_SubmissionAuthority.PUBLIC_INTAKE`.
- `services/api/app/services/members.py:167-193` creates/reuses the synthetic member; this path must continue to call `create_or_get_member()`.
- Existing positive tests:
  - `services/api/tests/test_public_intake_submit.py:36-70` asserts public submit creates a queued application and the applicant Discord ID starts with `public:`.
  - `services/api/tests/test_public_intake_submit.py:73-95` asserts public idempotency namespace behavior.
  - `services/api/tests/test_public_intake_synthetic_member.py:23-45` asserts synthetic member format and active status.
  - `services/api/tests/test_public_intake_synthetic_member.py:48-76` asserts synthetic member idempotency.

Required positive-case behavior:

- `is_synthetic_member(member.discord_user_id)` should return `True` for the public-intake member, but `_submit_application_internal()` must not reject it when `submission_authority == _SubmissionAuthority.PUBLIC_INTAKE`.
- Do not add a helper exception or endpoint mapping branch that catches the public submit path by accident.

New files needed:

- No new production file.
- New regression can extend `services/api/tests/test_public_intake_submit.py` or remain covered by existing INIT-120 tests plus one explicit guard-regression test.

Conflicting systems:

- Any repository-level "real member" helper or `fetch_member_by_id()` filter would break this path. Keep the guard at service write boundaries.

Deletion candidates:

- None. Existing INIT-120 public-intake tests are not deletion candidates; they are regression gates.

## Test surface hookpoints

Predicate helper unit:

- Add unit coverage for `is_synthetic_member()`:
  - `"public:abc"` returns `True`;
  - numeric Discord-like strings and arbitrary non-prefixed strings return `False`;
  - `MemberRead` or a simple object with `.discord_user_id` returns the corresponding value;
  - passing a dict directly is either explicitly unsupported or handled deliberately. The proposal says callers should pass `row["discord_user_id"]`, so a test should lock that discipline if the helper keeps the current object-or-string signature.

Authenticated submit:

- Rejection: create a synthetic member through `resolve_or_create_public_intake_member()` or public submit, then call authenticated `POST /api/v1/applications` with that UUID. Expect 422 `applicant_synthetic_not_allowed` and no application row. Reuse form/grant helpers from `services/api/tests/test_public_intake_submit.py:16-30` or `services/api/tests/test_applications.py:136-157`.
- Acceptance: existing real-member authenticated submit at `services/api/tests/test_public_intake_submit.py:98-139` and `services/api/tests/test_applications.py:169-190` should keep passing.

Owner claim/reassign/reactivate:

- Rejection: seed queued applications with real applicants, then use synthetic owner actors/targets for claim, reassign, and reactivate. Expect 422 `application_owner_synthetic_not_allowed`, with field `actor_id` for claim and `new_owner_id` for reassign/reactivate.
- Acceptance: existing real claim/review tests at `services/api/tests/test_applications.py:270-418` should keep passing. Add explicit reassign/reactivate positive real-owner cases if not already present in later sections of the file.

Trust signal/compute/recompute:

- Rejection:
  - `POST /api/v1/trust/signals` with synthetic `member_id` should return 422 `trust_member_synthetic_not_allowed` and insert no `trust_signals` row.
  - `POST /api/v1/trust/compute/{synthetic_id}` should return 422 and insert no `trust_profiles` row.
  - `POST /api/v1/trust/recompute/{synthetic_id}` should return 422 and not upsert a profile.
- Acceptance:
  - signal positive path at `services/api/tests/test_trust_signals.py:49-177`;
  - compute positive path at `services/api/tests/test_trust.py:210-268`;
  - recompute positive paths at `services/api/tests/test_trust_recompute.py:80-173`.

Leadership alias expansion:

- Direct leadership rejection: create synthetic member, request `/api/v1/members/{synthetic_uuid}/leadership-context`, expect 422 `leadership_member_synthetic_not_allowed`.
- Direct real acceptance: existing leadership empty-shape test at `services/api/tests/test_leadership_context.py:50-77` covers numeric non-member input; add or keep a real member UUID positive case if the new policy distinguishes UUID-backed members.
- Succession omit: seed a roster holder with a synthetic member UUID using test-only direct insert (`services/api/tests/authority_slice_helpers.py:185-221`), grant succession read, and assert no `public:` alias leaks into grants/applications/tickets and no synthetic UUID appears in owner alias lookups. Also keep the existing real-holder positive test at `services/api/tests/test_succession_plan.py:15-60`.

Roster entry creation:

- Rejection: `POST /api/v1/roster-entries` with a synthetic member UUID returns 422 `roster_member_synthetic_not_allowed` and inserts no `roster_entries` row.
- Acceptance: update `services/api/tests/test_roster.py` helpers to seed a real member UUID and keep `test_create_roster_entry_in_active_state()` (`services/api/tests/test_roster.py:252-264`) and duplicate active behavior (`services/api/tests/test_roster.py:291-310`) passing under the new UUID contract.
- Non-UUID/missing-member cases should be locked separately so they do not return the synthetic code.

PATCH member status:

- Rejection: create synthetic member, call `PATCH /api/v1/members/{member_id}/status` with current ETag, expect 422 `member_status_synthetic_not_allowed` and unchanged row/version.
- Acceptance: existing positive/stale tests at `services/api/tests/test_members.py:266-340` should keep passing for real members.

INIT-120 regression:

- Keep running `services/api/tests/test_public_intake_submit.py` and `services/api/tests/test_public_intake_synthetic_member.py`. These are the positive proof that public submit still creates synthetic members and that the helper returning `True` does not imply rejection on public submit.

## Conflicting systems / deletion candidates

Conflicting or watch systems:

- `_collect_member_aliases()` has additional consumers beyond direct leadership context and succession. Current source calls it from authority permission aliasing, leadership handoff applications/tickets, compliance evidence matching, direct leadership read models, and succession. The implementation must make an explicit compatibility-free policy choice for each call site or a safe default.
- Roster create currently accepts arbitrary text member IDs in tests and contract (`services/api/app/contracts/roster.py:29-32`; `services/api/tests/test_roster.py:164-181`). The approved proposal intentionally tightens create to UUIDs resolving to non-synthetic members. Test fixtures using `"member-1"` must be replaced, not shimmed.
- Trust and roster repositories are exact raw data access. Adding repository joins or filters would exceed the approved write-boundary slice and could break public-intake or existing read behavior.
- Pre-existing polluted rows remain readable in trust profiles, roster-derived aggregates, owner workload queries, and exact member reads. This is residual risk, not a hookpoint defect.

Deletion/replacement candidates:

- Replace the application owner existence-only checks at `services/api/app/services/applications.py:847-848` and `services/api/app/services/applications.py:854-855` with real-member validation.
- Replace `services/api/tests/test_roster.py:168` default `member_id="member-1"` and direct call sites that assume roster create accepts arbitrary non-empty text.
- Do not delete public-intake tests, exact member repository lookups, trust repository reads, roster repository reads, or `resolve_or_create_public_intake_member()`.

## New files required

Required new artifact:

- `research/09-synthetic-member-guard-hookpoints.md`

Likely new test file:

- `services/api/tests/test_synthetic_member_guard.py` for predicate helper unit tests and possibly service-level validation helper tests.

No new production source file is required. Production changes should be edits to existing files:

- `services/api/app/services/members.py`
- `services/api/app/contracts/members.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/trust.py`
- `services/api/app/services/authority.py`
- `services/api/app/services/read_models.py`
- `services/api/app/services/roster.py`
- endpoint shared/error handlers:
  - `services/api/app/api/v1/endpoints/applications/_shared.py`
  - `services/api/app/api/v1/endpoints/trust/_shared.py`
  - `services/api/app/api/v1/endpoints/authority/_shared.py`
  - `services/api/app/api/v1/endpoints/roster.py`
  - `services/api/app/api/v1/endpoints/members.py`

Likely existing test files to extend:

- `services/api/tests/test_public_intake_submit.py`
- `services/api/tests/test_public_intake_synthetic_member.py`
- `services/api/tests/test_applications.py`
- `services/api/tests/test_trust.py`
- `services/api/tests/test_trust_signals.py`
- `services/api/tests/test_trust_recompute.py`
- `services/api/tests/test_roster.py`
- `services/api/tests/test_members.py`
- `services/api/tests/test_leadership_context.py`
- `services/api/tests/test_succession_plan.py`

## Notable observations

- `services/api/app/services/leadership.py` does not exist. Leadership aliasing is in `services/api/app/services/authority.py`, with direct leadership read-model assembly in `services/api/app/services/read_models.py`.
- The proposal's helper location is confirmed. Best insertion point is immediately after `PUBLIC_INTAKE_MEMBER_ACTOR` and before `_generated_audit_context()` in `services/api/app/services/members.py`.
- The public-submit exception is structurally clean because `_submit_application_internal()` already receives `submission_authority`, and public submit is the only current path passing `_SubmissionAuthority.PUBLIC_INTAKE`.
- Endpoint error mapping is a cross-cutting implementation requirement. Applications, trust, authority, roster, and members each have their own error handler shape; adding only the application `_shared.py` mapping would leave other surfaces without the promised stable 422 codes.
- Existing roster tests reveal the largest implementation/test adjustment: current create tests use non-UUID text `member_id`, while the approved proposal requires UUID-backed real members for new roster entries.
- A3 remains a data-state assumption. Source does not contradict it, but a database query should be used before or during implementation verification if the implementation claims anything about pre-existing roster pollution.
