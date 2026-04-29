READ:
- `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- `research/10-members-kind-problem-map.md`
- `plans/BACKLOG.md`
- `proposals/05-synthetic-member-guard.md`
- `proposals/02-public-application-intake.md`
- `migrations/versions/wu-028a_permission_drift_widening.py`
- `migrations/versions/wu-003b_audit_context_columns.py`
- `migrations/versions/wu-011_members.py`
- `migrations/versions/wu-041a_compliance_evaluations.py`
- `migrations/versions/wu-042_chapter_governance.py`
- `services/api/app/repositories/members.py`
- `services/api/app/services/members.py`
- `services/api/app/contracts/members.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/trust.py`
- `services/api/app/services/roster.py`
- `services/api/app/services/authority.py`
- `services/api/app/services/read_models.py`
- `services/api/tests/conftest.py`
- `services/api/tests/test_synthetic_member_helper.py`
- `services/api/tests/test_public_intake_synthetic_member.py`
- `services/api/tests/test_public_intake_submit.py`

# INIT-125A / BL-008 Phase 3 - Proposal: `members.kind` discriminator

## Summary

Add `members.kind` as the durable discriminator between real Discord members and public-intake placeholder members, then migrate INIT-124 synthetic-member guards from `discord_user_id LIKE 'public:%'` to `kind == 'public_intake'`. This keeps INIT-120 public submit working, preserves all shipped guard error codes, and deliberately stops short of Discord OAuth, member conversion, read-side cleanup, or a `linked_pending` state; the RCA identifies `members.kind` as the right first schema slice but not the full linking fix (`.tmp/rca/discord-oauth-linking-FINDINGS.md:149`, `.tmp/rca/discord-oauth-linking-FINDINGS.md:152-165`, `.tmp/rca/discord-oauth-linking-FINDINGS.md:229-259`).

## Net-value statement

This has positive net value because it replaces a brittle magic-prefix identity rule with an explicit schema contract while preserving the narrow write-boundary protection already shipped in INIT-124. INIT-124 intentionally deferred `members.kind` and relied on the `public:` prefix as an assumption (`proposals/05-synthetic-member-guard.md:53-58`, `proposals/05-synthetic-member-guard.md:250-254`); BL-008 now decomposes that debt into INIT-125A for the discriminator, BL-016 for OAuth, BL-017 for conversion, and BL-018 for cleanup (`plans/BACKLOG.md:223-245`).

## Scope

- Add Alembic migration `migrations/versions/wu-043_members_kind.py` with `revision = "wu_043_members_kind"` and `down_revision = "wu_041a_compliance_evaluations"`.
- Add `members.kind TEXT NOT NULL` with allowed values `discord` and `public_intake`.
- Backfill existing `public:%` rows to `public_intake` and all other rows to `discord`.
- Update member repository reads/inserts so fetched rows include `kind` and new rows persist it.
- Update `MemberRead` and the service mapper (`_member_from_row()`, equivalent to the prompt's `_member_to_read`) to expose `kind`.
- Change `is_synthetic_member()` to accept only member-like objects with a `kind` attribute/key and to return true only for `kind == "public_intake"`.
- Update INIT-124 BL-005 guard call sites to pass fetched member rows, not raw Discord id strings.
- Update public-intake creation to set `kind="public_intake"` and normal member creation to set `kind="discord"` without changing the external `create_or_get_member()` signature.
- Update fixtures and tests so real members default to `discord`, synthetic/public-intake members default to `public_intake`, and prefix-specific assertions become kind-specific assertions.

## Anti-scope

- No Discord OAuth provider, Authentik source, OIDC callback, or applicant login/link route.
- No conversion service, `member_links` table, synthetic-to-real promotion, or application re-pointing.
- No read-side roster/trust cleanup, historical data sweep, or query-level roster hardening.
- No `linked_pending` value in `members.kind`.
- No caller-supplied `kind` in `MemberCreate`.
- No rename of INIT-124 shipped error codes such as `trust_subject_synthetic_not_allowed`.
- No Discord-visible mutation.

## Implementation decisions taken in proposal

### Q1. Migration mechanics

Use nullable add, SQL backfill, explicit `server_default=None`, alter to `NOT NULL`, then add a check constraint. Do not leave a server default. This follows the populated-table widening pattern used by `permission_drift.kind`, which adds nullable columns, backfills them, then makes required columns non-null and adds check constraints (`migrations/versions/wu-028a_permission_drift_widening.py:34-53`, `migrations/versions/wu-028a_permission_drift_widening.py:83-110`). The `activity_actions.correlation_id` migration shows the local convention for dropping a temporary/default bridge after add (`migrations/versions/wu-003b_audit_context_columns.py:17-38`).

### Q2. Migration head and filename

The current graph-derived Alembic head is `wu_041a_compliance_evaluations`; `wu-042_chapter_governance.py` already exists in `migrations/versions/` and is part of the graph below `wu_035_application_interview` (`migrations/versions/wu-041a_compliance_evaluations.py:10-11`, `migrations/versions/wu-042_chapter_governance.py:10-11`). Name the new file `migrations/versions/wu-043_members_kind.py`, set `revision = "wu_043_members_kind"`, and set `down_revision = "wu_041a_compliance_evaluations"`.

### Q3. Normal creation path

Keep `create_or_get_member(db, request, actor)` unchanged for external callers. Add an internal `_kind: MemberKind = "discord"` keyword to the private repository `_insert_member()` helper, defaulting to `discord`; branch inside `resolve_or_create_public_intake_member()` so only that public-intake path passes `_kind="public_intake"`. Today normal creation and public intake both converge through `create_or_get_member()` and `_insert_member()` (`services/api/app/services/members.py:116-177`, `services/api/app/services/members.py:180-206`, `services/api/app/repositories/members.py:58-79`).

### Q4. Read contract

Expose `kind` on `MemberRead`. Exact member reads already return `MemberRead` through `_member_from_row()` and are intentionally unfiltered (`services/api/app/services/members.py:87-96`, `services/api/app/services/members.py:209-226`); adding `kind` makes the supported contract explicit and reduces client pressure to parse `discord_user_id`.

### Q5. Helper signature

Narrow `is_synthetic_member()` to member-like objects only. The current helper accepts raw strings and checks `discord_user_id.startswith("public:")` (`services/api/app/services/members.py:46-56`); keeping raw-string support would be a compatibility shim for the deprecated discriminator. The new helper accepts rows, Pydantic models, or simple objects that expose `kind`, and fails loudly for raw strings or missing `kind` during tests.

### Q6. Test fixtures

Shared fixtures and direct SQL test inserts must include `kind`. Existing test factories insert `members (id, discord_user_id, joined_at, status)` directly and synthesize public rows from a `public:` prefix (`services/api/tests/conftest.py:208-233`); helper and public-intake tests currently assert prefix behavior (`services/api/tests/test_synthetic_member_helper.py:10-54`, `services/api/tests/test_public_intake_synthetic_member.py:37-45`, `services/api/tests/test_public_intake_submit.py:54-62`). Rewrite those tests to assert kind behavior, while leaving the `public:` token format only where it remains part of public-intake idempotency.

### Q7. Error codes

Preserve all shipped INIT-124 error codes. The implementation currently emits `applicant_synthetic_not_allowed`, `owner_synthetic_not_allowed`, `trust_subject_synthetic_not_allowed`, `roster_member_synthetic_not_allowed`, `leadership_alias_synthetic_not_allowed`, and `member_status_synthetic_not_allowed` at the guarded boundaries (`services/api/app/services/applications.py:622-632`, `services/api/app/services/applications.py:867-906`, `services/api/app/services/trust.py:112-119`, `services/api/app/services/roster.py:129-136`, `services/api/app/services/authority.py:166-179`, `services/api/app/services/members.py:243-250`). INIT-125A changes the discriminator only.

## Design

### Migration

Add a new migration file:

```python
"""WU-043 members kind discriminator."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "wu_043_members_kind"
down_revision = "wu_041a_compliance_evaluations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("kind", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE members
           SET kind = CASE
               WHEN discord_user_id LIKE 'public:%' THEN 'public_intake'
               ELSE 'discord'
           END
         WHERE kind IS NULL;
        """
    )
    op.alter_column("members", "kind", server_default=None)
    op.alter_column("members", "kind", nullable=False)
    op.create_check_constraint(
        "members_kind_valid",
        "members",
        "kind IN ('discord', 'public_intake')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_members__members_kind_valid", "members", type_="check")
    op.drop_column("members", "kind")
```

The migration deliberately has no lingering `server_default`. The backfill is idempotent in the only way an Alembic migration needs here: if the update is re-run before the non-null alteration, it only fills rows where `kind IS NULL`. Downgrade drops the check constraint and the column; it does not mutate `discord_user_id` or application references.

### Helper change in `services/api/app/services/members.py`

Replace the prefix helper with a kind helper:

```python
def is_synthetic_member(member: object) -> bool:
    if isinstance(member, dict):
        kind = member["kind"]
    else:
        kind = getattr(member, "kind")
    return kind == "public_intake"
```

Do not retain string-input support. Every production guard already fetches a member row before making the decision, so the call sites can pass the row directly (`services/api/app/services/applications.py:331-336`, `services/api/app/services/trust.py:315-320`, `services/api/app/services/roster.py:126-136`, `services/api/app/services/authority.py:164-180`, `services/api/app/services/members.py:240-250`).

### Public-intake creator update

Keep the public-intake identifier generation as-is for idempotency, but ensure its row is typed:

- `resolve_or_create_public_intake_member()` still derives `discord_user_id = "public:<digest>"` from `public_submission_id` and `channel_salt` (`services/api/app/services/members.py:180-192`).
- It creates the row through the same member aggregate path, but passes the private insertion kind as `public_intake`.
- The public route remains the one approved synthetic write path: `submit_public_application()` resolves/creates a public-intake member, builds an internal `ApplicationSubmission`, and submits with `_SubmissionAuthority.PUBLIC_INTAKE` (`services/api/app/services/applications.py:773-805`; `proposals/05-synthetic-member-guard.md:33-50`).

### `MemberRead` + `_member_to_read` update

Add:

```python
MemberKind = Literal["discord", "public_intake"]

class MemberRead(_MemberModel):
    ...
    kind: MemberKind
```

Update `_MEMBER_SELECT` to select `m.kind`, and update `_member_from_row()` to include `kind=row["kind"]` (`services/api/app/repositories/members.py:10-22`, `services/api/app/services/members.py:87-96`). `MemberCreate` remains unchanged and must not accept caller-supplied `kind` (`services/api/app/contracts/members.py:18-22`).

### BL-005 guard call-site updates

Authenticated submit:

- Change `_submit_application_internal()` to call `is_synthetic_member(applicant)` after `fetch_member_by_id()`, preserving `applicant_synthetic_not_allowed` and the public-intake authority exception (`services/api/app/services/applications.py:618-632`).

Owner claim/reassign/reactivate:

- Change `_require_non_synthetic_application_member()` to call `is_synthetic_member(member)` and preserve `owner_synthetic_not_allowed` (`services/api/app/services/applications.py:324-336`, `services/api/app/services/applications.py:867-906`).

Trust:

- Change `create_trust_signal()`, `compute_trust()`, and `_recompute_once()` to pass fetched member rows to the helper and preserve `trust_subject_synthetic_not_allowed` (`services/api/app/services/trust.py:291-321`, `services/api/app/services/trust.py:384-397`, `services/api/app/services/trust.py:474-486`).

Leadership:

- Change `_resolve_member_aliases()` to pass `member_row` to the helper. Preserve `synthetic_policy="reject"` for leadership context and `synthetic_policy="omit"` for succession-plan holder aggregation (`services/api/app/services/authority.py:145-182`, `services/api/app/services/read_models.py:247-252`, `services/api/app/services/authority.py:549-553`).

Roster:

- Change `_validate_roster_member()` to pass fetched member rows to the helper and preserve `roster_member_synthetic_not_allowed` (`services/api/app/services/roster.py:120-158`).

PATCH status:

- Change `patch_member_status()` to pass the locked row to the helper and preserve `member_status_synthetic_not_allowed` (`services/api/app/services/members.py:229-295`).

### Call-boundary preservation

`_insert_member()` gets an internal `_kind` parameter, but `create_or_get_member()` keeps its external signature unchanged. Existing normal callers get `discord` by default; the public-intake creator is the only override. This is a caller contract preservation, not a dual-behavior shim: all call sites are updated to the single `kind` discriminator, and string-prefix synthetic checks are deleted.

## Supported-surface track

Deployment mode:

- All channels. The Alembic migration runs in every deployment because `members.kind` becomes part of the API contract and write-boundary behavior; BL-008 already names INIT-125A as a schema/guard migration slice (`plans/BACKLOG.md:236-245`).

Cohort:

- Cluster operators who inspect members, application ownership, roster, trust, and leadership behavior.
- API consumers of member read endpoints, public submit, authenticated submit, application lifecycle transitions, trust, roster, leadership, and member status PATCH.

Adjacent paths:

- INIT-120 public submit remains adjacent and must continue to create/reuse public-intake members (`services/api/app/services/applications.py:773-805`; `proposals/02-public-application-intake.md:65-72`).
- INIT-124 guards remain adjacent and must continue to reject public-intake members at real-member-only write boundaries (`proposals/05-synthetic-member-guard.md:43-50`, `proposals/05-synthetic-member-guard.md:260-310`).
- Discord submission flow remains adjacent because it creates/resolves real Discord members and submits through the authenticated route, which now accepts only `kind="discord"` applicants outside the public-intake exception.

Blast-radius notes:

- INIT-120 public-intake submit stays behaviorally unchanged: submit still queues the application and returns the same receipt; only the inserted member row's `kind` value differs. Regressions inside this slice include failure to stamp/reuse `public_intake`, changed receipt shape, or broken public-submit idempotency.
- INIT-124 boundary guards stay behaviorally unchanged: real members are still accepted, synthetic/public-intake members are still rejected, and error codes stay stable; the internal mechanism switches from `public:` prefix to `kind`. Regressions inside this slice include accepting `public_intake`, rejecting `discord`, or renaming shipped guard codes.
- Discord submission service stays behaviorally unchanged because it uses `create_or_get_member()`, whose external signature remains unchanged and whose default insert kind is `discord`. Regressions inside this slice include Discord-created members missing `kind="discord"` or authenticated submissions being blocked for real Discord members.
- Audit substrate stays unchanged: `kind` is not audit-tracked in this slice. Regressions inside this slice include altering audit context, adding audit writes for `kind`, or changing existing audit row shape.

Migration / rollback:

- Upgrade adds and backfills `members.kind`, then enforces non-null plus `members_kind_valid`.
- Rollback drops the check constraint and column. It does not delete members, rewrite `applications.applicant_id`, or modify audit rows.

Observability:

- Existing API error responses remain the primary signal because the error codes do not change.
- Member read responses now expose `kind`, giving operators a direct way to distinguish `discord` from `public_intake`.
- Migration success can be verified with counts by `kind` and by cross-checking `public:%` rows:

```sql
SELECT kind, count(*) FROM members GROUP BY kind ORDER BY kind;
SELECT count(*) FROM members WHERE discord_user_id LIKE 'public:%' AND kind <> 'public_intake';
SELECT count(*) FROM members WHERE discord_user_id NOT LIKE 'public:%' AND kind <> 'discord';
```

## Assumption register

- A1: Existing rows have either `discord_user_id LIKE 'public:%'` for synthetic public-intake members or a numeric Discord ID for real members; there is no third case. Evidence: INIT-120 created public applicants as `public:<sha>` rows (`proposals/02-public-application-intake.md:65-72`), the current helper defines synthetic identity by the `public:` prefix (`services/api/app/services/members.py:46-56`), and the RCA local database check found synthetic rows only through `discord_user_id LIKE 'public:%'` (`.tmp/rca/discord-oauth-linking-FINDINGS.md:73-85`). Invalidated by any existing member row with a non-numeric, non-`public:` `discord_user_id`.
- A2: All active production code paths for `INSERT INTO members` go through `_insert_member()`. Evidence: the repository owns the single production `INSERT INTO members` helper (`services/api/app/repositories/members.py:58-79`), normal creation calls it from `create_or_get_member()` (`services/api/app/services/members.py:116-177`), and public intake reaches member creation through `resolve_or_create_public_intake_member()` (`services/api/app/services/members.py:180-206`). Test helpers contain direct inserts and must be updated separately (`services/api/tests/conftest.py:208-233`). Invalidated by a production code path or test fixture that bypasses `_insert_member()` and writes directly to `members` without an explicit `kind` value.
- A3: `MemberRead` is the only public member read contract, and adding `kind` does not break existing clients. Evidence: `MemberRead` currently defines the returned member shape (`services/api/app/contracts/members.py:25-32`), exact member reads map repository rows through `_member_from_row()` (`services/api/app/services/members.py:87-96`, `services/api/app/services/members.py:209-226`), and `MemberCreate` is separate from read output so callers do not get write authority over `kind` (`services/api/app/contracts/members.py:18-22`). Invalidated by a public API consumer that fails on unknown `MemberRead.kind`, or by evidence that exposing `kind` is sensitive because an external integration can infer identity from member properties.

## Test-intent track

- Migration unit: Risk: backfill or constraint drift misclassifies existing rows. Acceptance: seeded one `public:<hash>` id and one numeric Discord id upgrade to `public_intake`/`discord`, `kind` is `NOT NULL`, invalid values fail, and no persistent default remains; re-running the backfill SQL before constraints is harmless. Level: `unit`. Fixture: Alembic migration test seeds raw `members` rows. Assumption: A1. Signal: SQL assertions on row values, column metadata, and check/default behavior. Residual: does not verify every production database value beyond the sampled prefix cases.
- Helper unit: Risk: guards keep relying on `discord_user_id` prefix or silently accept raw strings. Acceptance: `is_synthetic_member()` returns true for member-like rows/models with `kind="public_intake"`, false for `kind="discord"` even if `discord_user_id` starts with `public:`, and rejects raw string input. Level: `unit`. Fixture: plain dict/object/Pydantic-like member fixtures. Assumption: A3. Signal: boolean assertions plus expected exception for raw strings. Residual: does not prove every call site passes a fetched member row.
- Public-intake creator: Risk: public-intake rows lose idempotency or get stamped as real Discord members. Acceptance: `resolve_or_create_public_intake_member()` creates/reuses the same `public:<digest>` row with `kind="public_intake"`. Level: `component`. Fixture: service-level DB fixture applying public submission id and channel salt. Assumption: A2. Signal: one member row, stable id across repeat calls, and stored `kind="public_intake"`. Residual: does not cover full public application submission routing.
- Normal creation: Risk: real Discord creation is forced to expose or omit the new discriminator incorrectly. Acceptance: `create_or_get_member()` keeps its external signature and creates/reuses rows with `kind="discord"`. Level: `component`. Fixture: service-level DB fixture using `MemberCreate` and actor context. Assumption: A2. Signal: created row/read DTO has `kind="discord"` and caller supplies no kind. Residual: does not cover Discord daemon transport behavior.
- INIT-124 boundary guards: Risk: kind migration weakens existing real-member-only write boundaries or changes shipped error codes. Acceptance: authenticated submit, owner claim/reassign/reactivate, trust signal/compute/recompute, leadership alias reject/omit, roster create, and member status PATCH reject `public_intake`, accept `discord`, and preserve error codes. Level: `particular-integration`. Fixture: existing API/service fixtures with inserted `discord` and `public_intake` members at each guard application point. Assumption: A3. Signal: success for real members, expected HTTP/service errors for public-intake members, unchanged code strings. Residual: does not exhaustively test unrelated read-model filtering.
- INIT-120 e2e public submit: Risk: supported public intake changes user-visible behavior while adding `kind`. Acceptance: public submit still resolves a public-intake member, creates a queued application, routes it with the public-intake service actor, and returns the same receipt shape. Level: `end-to-end`. Fixture: public submit API test fixture using the existing public route and database. Assumption: A1, A2. Signal: HTTP success, queued application row, member row with `kind="public_intake"`, unchanged receipt fields. Residual: does not verify Discord-visible follow-up because this slice has no Discord-visible mutation.

### Residual-risk artifact

`plans/risk/init-125a-test-residuals.md`

## Migration / rollback

Upgrade path:

1. Deploy the Alembic migration in all channels before code requiring `members.kind` starts.
2. Add nullable `members.kind`.
3. Backfill `public_intake` for `discord_user_id LIKE 'public:%'`, otherwise `discord`.
4. Clear any server default, alter `kind` to `NOT NULL`, and add `members_kind_valid`.
5. Deploy API code that selects/inserts/maps `kind` and uses kind-based guards.

Rollback path:

1. Roll back API code to the previous prefix-based guard version if necessary.
2. Downgrade the migration by dropping `members_kind_valid` and `members.kind`.
3. Do not delete public-intake member rows or rewrite application ownership/applicant references as part of rollback.

The downgrade is intentionally lossy only for the derived discriminator. The source prefix remains present on public-intake rows, so rollback can recover previous behavior without data repair.

## Out of scope for follow-up

- BL-016: Authentik Discord OAuth provider and applicant OIDC plumbing (`plans/BACKLOG.md:342-352`).
- BL-017: conversion service, supersession/link records, and application re-pointing (`plans/BACKLOG.md:355-365`).
- BL-018: historical roster/trust cleanup and read hardening (`plans/BACKLOG.md:367-380`).
