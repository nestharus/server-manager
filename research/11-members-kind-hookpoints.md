READ:
- `proposals/06-members-kind.md`
- `research/10-members-kind-problem-map.md`
- `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- `plans/audit-history/init-125a-audit-history.md`
- `plans/risk/init-125a-audit.md`
- `plans/risk/init-125a-scope.md`
- `plans/risk/init-125a-shortcut.md`
- `plans/risk/init-125a-supported-surface.md`
- `migrations/versions/wu-011_members.py`
- `migrations/versions/wu-028a_permission_drift_widening.py`
- `migrations/versions/wu-035_application_interview.py`
- `migrations/versions/wu-041a_compliance_evaluations.py`
- `migrations/versions/wu-042_chapter_governance.py`
- `migrations/env.py`
- `services/api/app/repositories/db.py`
- `services/api/app/repositories/members.py`
- `services/api/app/services/members.py`
- `services/api/app/contracts/members.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/trust.py`
- `services/api/app/services/authority.py`
- `services/api/app/services/read_models.py`
- `services/api/app/services/roster.py`
- `services/api/app/api/v1/endpoints/members.py`
- `services/api/tests/conftest.py`
- `services/api/tests/public_intake_fixtures.py`
- `services/api/tests/test_members.py`
- `services/api/tests/test_roster.py`
- `services/api/tests/chapter_governance_helpers.py`
- `services/api/tests/test_operational_views.py`
- `services/api/tests/test_chapter_archive_plan.py`
- `services/api/tests/test_synthetic_member_helper.py`
- `services/api/tests/test_public_intake_synthetic_member.py`
- `services/api/tests/test_public_intake_submit.py`

## Inputs read

- Approved proposal rev 1: `proposals/06-members-kind.md`.
- Approved problem map: `research/10-members-kind-problem-map.md`.
- RCA: `.tmp/rca/discord-oauth-linking-FINDINGS.md`.
- Audit history: `plans/audit-history/init-125a-audit-history.md`.
- Round-2 risk artifacts present in this worktree: `plans/risk/init-125a-audit.md`, `plans/risk/init-125a-scope.md`, `plans/risk/init-125a-shortcut.md`, and `plans/risk/init-125a-supported-surface.md`.
- Current implementation hookpoints named by the proposal and risk reports.

No approved A1..A3 invalidation was found. Direct test inserts without `kind` are present, but they are the expected fixture hookpoints already named by the proposal/problem map rather than a new production insert path.

## Migration file placement hookpoints

- Current `members` table definition is in `migrations/versions/wu-011_members.py:16`. The table has `id`, `discord_user_id`, `joined_at`, `status`, timestamps, a unique constraint on `discord_user_id`, and a `status` check, but no `kind` column (`migrations/versions/wu-011_members.py:17`, `migrations/versions/wu-011_members.py:20`, `migrations/versions/wu-011_members.py:35`, `migrations/versions/wu-011_members.py:39`).
- Graph-derived Alembic head from the current files is `wu_041a_compliance_evaluations` in `migrations/versions/wu-041a_compliance_evaluations.py:10`; its `down_revision` is `wu_040a_compliance_evidence` at `migrations/versions/wu-041a_compliance_evaluations.py:11`.
- `migrations/versions/wu-042_chapter_governance.py` already exists, with `revision = "wu_042_chapter_governance"` at `migrations/versions/wu-042_chapter_governance.py:10` and `down_revision = "wu_022_applications"` at `migrations/versions/wu-042_chapter_governance.py:11`. `migrations/versions/wu-035_application_interview.py:10` chains later from `wu_042_chapter_governance`, so `wu-042` is occupied and is not the graph head.
- New migration file should be `migrations/versions/wu-043_members_kind.py`, with `revision = "wu_043_members_kind"` and `down_revision = "wu_041a_compliance_evaluations"`.
- Use the populated-table widening pattern from `migrations/versions/wu-028a_permission_drift_widening.py:34`: add nullable columns first, backfill by SQL at `migrations/versions/wu-028a_permission_drift_widening.py:83`, then alter required columns to non-null at `migrations/versions/wu-028a_permission_drift_widening.py:97`, and finally add check constraints at `migrations/versions/wu-028a_permission_drift_widening.py:101`.
- Constraint name should be created as bare `members_kind_valid`. The naming convention in `services/api/app/repositories/db.py:14` materializes check constraints as `ck_<table>__<constraint_name>` (`services/api/app/repositories/db.py:20`), and Alembic binds that metadata at `migrations/env.py:23`. Downgrade should therefore drop `ck_members__members_kind_valid`.

Implementation shape:

- Add `members.kind` as nullable `sa.Text()`.
- Backfill:
  `public:%` -> `public_intake`; all other rows -> `discord`.
- Alter `kind` to `nullable=False`.
- Add check constraint allowing only `discord` and `public_intake`.
- Do not leave a server default.

## Members repository hookpoints

- `_MEMBER_SELECT` starts at `services/api/app/repositories/members.py:10` and currently selects `m.id`, `m.discord_user_id`, `m.joined_at`, `m.status`, timestamps, and version (`services/api/app/repositories/members.py:11`, `services/api/app/repositories/members.py:17`). Add `m.kind`.
- `fetch_member_by_id()` uses `_MEMBER_SELECT` at `services/api/app/repositories/members.py:31`; adding `m.kind` there feeds all id-based guard callers.
- `fetch_member_by_discord_id()` uses `_MEMBER_SELECT` at `services/api/app/repositories/members.py:42`; adding `m.kind` there feeds exact member reads and authority alias lookup by Discord id.
- `_fetch_member_by_id_for_update()` uses `_MEMBER_SELECT` at `services/api/app/repositories/members.py:53`; adding `m.kind` there feeds the PATCH-status guard while preserving the current lock boundary.
- `_insert_member()` is the only production `INSERT INTO members` helper found in `services/api/app` (`services/api/app/repositories/members.py:58`). It currently inserts `id`, `discord_user_id`, `joined_at`, and `status` only (`services/api/app/repositories/members.py:65`). Add an internal `_kind: MemberKind = "discord"` keyword parameter and insert `kind`.
- All production and test `INSERT INTO members` SQL must include `kind`. Production hookpoint: `services/api/app/repositories/members.py:65`. Test hookpoints are listed in `## Test fixture hookpoints`.

## Members service hookpoints

- `SYNTHETIC_MEMBER_PREFIX = "public:"` is at `services/api/app/services/members.py:46`. After the helper switches to `kind`, the constant is a deletion candidate unless tests still need a local expected-prefix literal for public-intake idempotency.
- `is_synthetic_member()` is at `services/api/app/services/members.py:49`. It currently accepts `object | str`, branches on raw strings at `services/api/app/services/members.py:50`, falls back to `discord_user_id` at `services/api/app/services/members.py:53`, and classifies by prefix at `services/api/app/services/members.py:54`. Replace with a row/object-only helper keyed to `kind == "public_intake"`. Do not keep raw-string support.
- `_member_from_row()` is at `services/api/app/services/members.py:87`. It currently builds `MemberRead` without `kind` through `services/api/app/services/members.py:95`. Add `kind=row["kind"]`.
- `create_or_get_member()` starts at `services/api/app/services/members.py:116`; its external signature should stay unchanged. It calls `_insert_member()` at `services/api/app/services/members.py:129` with row fields but no kind. Normal calls should rely on `_insert_member(..., _kind="discord")` by default.
- `resolve_or_create_public_intake_member()` starts at `services/api/app/services/members.py:180`. It derives the stable public id at `services/api/app/services/members.py:186` and sets `discord_user_id=f"public:{digest[:32]}"` at `services/api/app/services/members.py:188`. This public-id format should remain for idempotency, but classification must come from `kind`.
- Current public-intake creation reaches `_insert_member()` only through `create_or_get_member()` at `services/api/app/services/members.py:195` and again at `services/api/app/services/members.py:201`. Phase 6 needs an internal service hookpoint to pass `_kind="public_intake"` without adding `kind` to `MemberCreate` or the public `create_or_get_member(db, request, actor)` signature.
- `patch_member_status()` starts at `services/api/app/services/members.py:229`. It locks the row at `services/api/app/services/members.py:240` and currently passes `row["discord_user_id"]` to the helper at `services/api/app/services/members.py:243`. Change that call to pass the locked row.

## MemberRead contract hookpoints

- `MemberStatus` is defined at `services/api/app/contracts/members.py:10`. Add adjacent `MemberKind = Literal["discord", "public_intake"]`.
- `MemberCreate` is at `services/api/app/contracts/members.py:18` and must remain unchanged; no caller-supplied `kind`.
- `MemberRead` starts at `services/api/app/contracts/members.py:25` and currently includes `id`, `discord_user_id`, `joined_at`, `status`, timestamps, and `version` (`services/api/app/contracts/members.py:26`, `services/api/app/contracts/members.py:32`). Add required `kind: MemberKind`.
- `_member_from_row()` in `services/api/app/services/members.py:87` is the only in-repo `MemberRead(` construction found. Update it with the new required field.
- Member endpoints return `MemberRead` at `services/api/app/api/v1/endpoints/members.py:91`, `services/api/app/api/v1/endpoints/members.py:114`, `services/api/app/api/v1/endpoints/members.py:132`, and `services/api/app/api/v1/endpoints/members.py:150`. They should need no route-signature change once the contract and mapper are updated.

## BL-005 guard call sites

- Authenticated application submit: `services/api/app/services/applications.py:618` fetches `applicant = fetch_member_by_id(...)`; `services/api/app/services/applications.py:624` currently passes `applicant["discord_user_id"]`. Caller already has the fetched member object. Change to `is_synthetic_member(applicant)` and preserve `applicant_synthetic_not_allowed`.
- Application owner guard: `_require_non_synthetic_application_member()` fetches `member` at `services/api/app/services/applications.py:331`; `services/api/app/services/applications.py:334` currently passes `member["discord_user_id"]`. Caller already has the fetched member object. Change to `is_synthetic_member(member)` and preserve `owner_synthetic_not_allowed`.
- Owner guard consumers are claim at `services/api/app/services/applications.py:869`, reassign at `services/api/app/services/applications.py:890`, and reactivate at `services/api/app/services/applications.py:901`.
- Trust signal creation: `services/api/app/services/trust.py:316` fetches `member`; `services/api/app/services/trust.py:319` currently passes `member["discord_user_id"]`. Caller already has the fetched member object. Change to `is_synthetic_member(member)` and preserve `trust_subject_synthetic_not_allowed`.
- Trust compute: `services/api/app/services/trust.py:392` fetches `member`; `services/api/app/services/trust.py:395` currently passes `member["discord_user_id"]`. Caller already has the fetched member object.
- Trust recompute: `services/api/app/services/trust.py:482` fetches `member`; `services/api/app/services/trust.py:485` currently passes `member["discord_user_id"]`. Caller already has the fetched member object.
- Leadership analog is `services/api/app/services/authority.py`, not a separate `leadership.py`. `_resolve_member_aliases()` starts at `services/api/app/services/authority.py:145`. UUID input path fetches `member_row` at `services/api/app/services/authority.py:164`; `services/api/app/services/authority.py:166` currently passes `member_row["discord_user_id"]`. Caller already has the fetched member row. Change to `is_synthetic_member(member_row)` and preserve `leadership_alias_synthetic_not_allowed`.
- Leadership direct read reaches the alias guard through `services/api/app/services/read_models.py:248` with `synthetic_policy="reject"` at `services/api/app/services/read_models.py:251`.
- Succession-plan aggregation reaches the alias guard through `services/api/app/services/authority.py:549` with `synthetic_policy="omit"` at `services/api/app/services/authority.py:552`.
- Roster: `_validate_roster_member()` starts at `services/api/app/services/roster.py:120`. It parses UUID-like member ids, fetches `member` at `services/api/app/services/roster.py:126`, and currently passes `member["discord_user_id"]` at `services/api/app/services/roster.py:129`. Caller already has the fetched member object. Change to `is_synthetic_member(member)` and preserve `roster_member_synthetic_not_allowed`.
- Member PATCH status endpoint: `services/api/app/api/v1/endpoints/members.py:153` delegates to service `patch_member_status_service()` at `services/api/app/api/v1/endpoints/members.py:163`. The actual guard is in `services/api/app/services/members.py:240`, where the service fetches a locked row, and `services/api/app/services/members.py:243`, where it currently passes the string. Change to `is_synthetic_member(row)` and preserve `member_status_synthetic_not_allowed`.

## Test fixture hookpoints

- Shared synthetic guard fixture: `SyntheticMemberGuardMember` at `services/api/tests/conftest.py:198` currently has `id` and `discord_user_id` only. Add `kind` or use a row/model shape that includes `kind`.
- Shared synthetic guard insert: `services/api/tests/conftest.py:213` inserts `members (id, discord_user_id, joined_at, status)`. Add `kind` and parameterize `SyntheticMemberGuardMemberFactory.create(..., kind=...)`.
- `SyntheticMemberGuardMemberFactory.real()` at `services/api/tests/conftest.py:229` should create `kind="discord"`.
- `SyntheticMemberGuardMemberFactory.synthetic()` at `services/api/tests/conftest.py:232` should create `kind="public_intake"`.
- Public-intake helper `create_real_member()` inserts directly at `services/api/tests/public_intake_fixtures.py:107`. Add `kind="discord"`.
- Public-intake fixture `fetch_application_row()` joins `members` at `services/api/tests/public_intake_fixtures.py:157` and selects only `m.discord_user_id` at `services/api/tests/public_intake_fixtures.py:155`. Add `m.kind AS applicant_kind` so public-submit tests can assert `public_intake` without parsing the prefix.
- Unique-constraint test direct insert at `services/api/tests/test_members.py:467` must include `kind` so the intended unique violation remains on `discord_user_id`, not `NOT NULL`.
- Roster helper `_seed_real_roster_member()` inserts directly at `services/api/tests/test_roster.py:170`. Add `kind="discord"`.
- Chapter governance helper inserts directly at `services/api/tests/chapter_governance_helpers.py:215`. Add `kind="discord"`.
- Operational views helper `_seed_member()` inserts directly at `services/api/tests/test_operational_views.py:78`. Add `kind="discord"` or a parameter with default `discord`.
- Chapter archive plan setup inserts directly at `services/api/tests/test_chapter_archive_plan.py:87`. Add `kind="discord"`.
- Predicate unit test `services/api/tests/test_synthetic_member_helper.py:10` is prefix-based today and includes raw-string cases at `services/api/tests/test_synthetic_member_helper.py:14` and object cases with `discord_user_id` at `services/api/tests/test_synthetic_member_helper.py:24`. Rewrite to assert kind-based behavior for dict/object/`MemberRead`-like shapes, including raw-string rejection.
- Public-intake synthetic-member tests currently assert the prefix at `services/api/tests/test_public_intake_synthetic_member.py:43` and public prefix separation at `services/api/tests/test_public_intake_synthetic_member.py:107`. Keep only idempotency assertions that truly depend on `public:<digest>`; move classification assertions to `kind`.
- Public submit e2e currently asserts `application["applicant_discord_user_id"].startswith("public:")` at `services/api/tests/test_public_intake_submit.py:61`. Add/read `applicant_kind` and assert `public_intake`; keep receipt and queued-state behavior unchanged.
- Existing migration test helpers are in `services/api/tests/conftest.py:237` and run `alembic` with the repo config at `services/api/tests/conftest.py:252`. Migration-specific assertions can be added to an existing test file or a new focused test file; no existing dedicated members-kind test file exists.

## Conflicting systems / deletion candidates

- Delete or stop using prefix classification in `services/api/app/services/members.py:46` and `services/api/app/services/members.py:49`. The `public:` token can remain as a public-intake idempotency namespace, but it must not remain the synthetic discriminator.
- Delete raw-string support from `is_synthetic_member()`. Keeping it would be a compatibility shim for the deprecated discriminator and would contradict Q5.
- Prefix-based helper tests in `services/api/tests/test_synthetic_member_helper.py:10` conflict with the new helper contract and should be rewritten, not extended.
- Prefix-based guard call arguments conflict with the narrowed helper. Every production guard already has a fetched member row, so no new repository fetch layer is needed.
- Direct test SQL inserts conflict with the new non-null column until they include explicit `kind`.
- No production `INSERT INTO members` bypassing `_insert_member()` was found. This supports A2.
- Do not introduce `linked_pending`; the approved proposal anti-scopes it and the migration check should allow only `discord` and `public_intake`.
- Do not add `kind` to `MemberCreate`; external caller selection of kind is anti-scoped.
- Do not add read-side roster/trust cleanup or conversion/linking files in this slice; those belong to later backlog items.

## New files required

- Required implementation file: `migrations/versions/wu-043_members_kind.py`.
- Required research artifact already created by this phase: `research/11-members-kind-hookpoints.md`.
- No new production service, repository, endpoint, or contract module is required.
- Test implementation may either update existing files or add a focused migration test file, for example `services/api/tests/test_members_kind_migration.py`, but a new test file is not structurally required by the hookpoints.

## Notable observations

- The audit-history file in this worktree still says Round 2 is pending, while the prompt and `plans/risk/init-125a-*.md` artifacts report LOW verdicts. This is documentation drift, not a code hookpoint.
- `wu-042_chapter_governance.py` is already present even though the current graph head is `wu_041a_compliance_evaluations`. Use `wu-043_members_kind.py` to avoid filename/revision collision, and chain it to the graph head `wu_041a_compliance_evaluations`.
- The helper implementation should define its accepted row shapes explicitly. Current repository fetches use `dict_row`, so `member["kind"]` works for production rows; a Pydantic/object path should use `getattr(member, "kind")`. Raw strings and missing `kind` should fail loudly.
- Public-intake rows should still have `discord_user_id = "public:<digest>"` for idempotency and existing receipt traceability. The required change is that runtime synthetic classification reads `kind`, not that the public id format disappears.
- Exact member reads are intentionally unfiltered today. Adding `MemberRead.kind` makes the discriminator visible to authorized readers and should reduce client pressure to parse `discord_user_id`.
