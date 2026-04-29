READ:
- proposals/06-members-kind.md
- research/10-members-kind-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md
- services/api/app/services/members.py
- services/api/app/repositories/members.py
- services/api/app/contracts/members.py
- services/api/app/services/applications.py
- services/api/app/services/trust.py
- services/api/app/services/roster.py
- services/api/app/services/authority.py
- services/api/app/services/read_models.py
- services/api/app/repositories/db.py
- migrations/env.py
- migrations/versions/wu-003b_audit_context_columns.py
- migrations/versions/wu-028a_permission_drift_widening.py
- migrations/versions/wu-041a_compliance_evaluations.py
- migrations/versions/wu-042_chapter_governance.py
- services/api/tests/conftest.py

# INIT-125A Phase 4 — Supported-Surface Risk

## Inputs read

- `proposals/06-members-kind.md` — full proposal, including supported-surface track (lines 206-245), net-value statement (lines 31-33), assumption register A1–A3 (lines 247-251), test-intent track (lines 253-260), migration/rollback (lines 266-282), and the eight INIT-124 boundary call-site updates (lines 176-200).
- `research/10-members-kind-problem-map.md` — approved Phase 2.5 problem map covering touched surface, current supported paths, brittle behavior, blast-radius adjacents, and deployment cohort.
- `.tmp/rca/discord-oauth-linking-FINDINGS.md` — RCA enumerating identity-linking decomposition; INIT-125A is the first slice for the discriminator only.
- `~/ai/workflows/implementation-pipeline.md` — phase ordering, supported-surface termination rule (line 106), and Phase 4 orthogonality between termination and the LOW/MEDIUM/HIGH verdict.
- Cited sources for assumption verification and adjacent-path checks: `services/api/app/services/members.py:46-56`, `services/api/app/services/members.py:116-206`, `services/api/app/services/members.py:229-295`, `services/api/app/repositories/members.py:10-79`, `services/api/app/contracts/members.py:18-32`, `services/api/app/services/applications.py:324-336`, `services/api/app/services/applications.py:618-632`, `services/api/app/services/applications.py:773-805`, `services/api/app/services/applications.py:867-906`, `services/api/app/services/trust.py:291-486`, `services/api/app/services/roster.py:120-158`, `services/api/app/services/authority.py:145-553`, `services/api/app/services/read_models.py:247-252`, `services/api/app/repositories/db.py:14-22`, `migrations/env.py:16-23`, `migrations/versions/wu-003b_audit_context_columns.py:45-57`, `migrations/versions/wu-028a_permission_drift_widening.py:34-110`, `migrations/versions/wu-041a_compliance_evaluations.py:10-11`, `migrations/versions/wu-042_chapter_governance.py:10-11`.

## Termination evaluation

Per `~/ai/workflows/implementation-pipeline.md:106`, evaluate orthogonal termination signals first, in this order: invalidated assumption that breaks the current problem framing -> return to research; otherwise non-positive value on the current supported surface -> terminate; otherwise NONE.

### Invalidated assumption check

I cross-checked each proposal assumption against current source.

- A1 (existing rows are either `public:%` synthetic or numeric Discord ID). The current synthetic creation point is `services/api/app/services/members.py:180-192`, which derives `discord_user_id = "public:<digest>"` from `public_submission_id` and `channel_salt`. The helper rule defining synthetic identity is `services/api/app/services/members.py:46-56`. The RCA's read-only check on the running `humility-local` cluster on `2026-04-28` reports 14 `public:%` synthetic rows and zero rows in roster/trust/owner pointing at synthetic members (`.tmp/rca/discord-oauth-linking-FINDINGS.md:73-85`). The backfill `CASE WHEN discord_user_id LIKE 'public:%' THEN 'public_intake' ELSE 'discord' END` (`proposals/06-members-kind.md:113-122`) classifies any non-`public:` value as `discord`, so an unanticipated third prefix would be silently absorbed into `discord`. The proposal's verification SQL (`proposals/06-members-kind.md:243-244`) catches a mismatch post-migration. No source today contradicts A1.
- A2 (production `INSERT INTO members` flows through `_insert_member()`). Verified at `services/api/app/repositories/members.py:58-79` (single production INSERT helper), `services/api/app/services/members.py:116-177` (`create_or_get_member()` calls `_insert_member()`), and `services/api/app/services/members.py:180-206` (`resolve_or_create_public_intake_member()` reaches the same path). No production INSERT bypass found. Test fixtures bypass and must be updated; the proposal acknowledges this and the problem map enumerates the test files (`research/10-members-kind-problem-map.md:47`).
- A3 (`MemberRead` is the only public member read contract; adding `kind` does not break existing clients). Verified at `services/api/app/contracts/members.py:25-32` and the read mapper at `services/api/app/services/members.py:87-96`. `MemberCreate` stays unchanged so callers cannot drive `kind`. Adding a non-optional `kind` field to a JSON response is an additive change in standard tolerant-reader practice; the invalidator is a strict client. None observed.

No INVALIDATED_ASSUMPTION signal.

### Non-positive value check

Existing-state risk is concrete and named in the problem map. The current discriminator is a magic string in `discord_user_id` (`services/api/app/services/members.py:46-56`), the predicate unit test asserts the prefix as the identity boundary (`services/api/tests/test_synthetic_member_helper.py:10-54`), and INIT-124's own assumption register flagged that the prefix is stable only as long as no Discord-origin row starts with literal `public:` (`proposals/05-synthetic-member-guard.md:53-58`, `proposals/05-synthetic-member-guard.md:250-254`). Replacing the prefix with an enforced `kind` column closes the deferred debt that INIT-124 explicitly assumed away.

Added blast radius is bounded:

- One Alembic migration that adds one column, backfills, drops default, sets NOT NULL, and adds one CHECK constraint.
- One typed enum `MemberKind = Literal["discord", "public_intake"]` and one new field on `MemberRead`.
- One internal `_kind` keyword on `_insert_member()` plus one branch in `resolve_or_create_public_intake_member()`.
- Eight INIT-124 guard call-site updates that pass already-fetched member rows to `is_synthetic_member()`.
- Zero new error codes, zero error-code renames, zero schema changes outside `members`, zero changes to Authentik/Pomerium/Cedar/Discord-handler/web-UI/GitOps/channel-template surfaces, and zero Discord-visible mutation.

Migration cost is one additive column with backfill; rollback drops the column and constraint without touching `applications.applicant_id`, audit rows, or roster/trust state. The reduction in concrete current-state risk (typed schema discriminator replacing a magic-string prefix at eight officer-reachable boundaries plus the public intake creator) clearly outweighs the additive blast radius (one column, one enum, one helper signature change) plus the migration/rollback burden (one Alembic head with a no-op rollback for the discriminator alone).

No NON_POSITIVE_VALUE signal.

## Existing-state risk reduction

The proposal closes the named brittleness flagged by both the problem map and the RCA.

- The discriminator moves from a magic string (`SYNTHETIC_MEMBER_PREFIX = "public:"`) into an enforced column (`members.kind` with `CHECK (kind IN ('discord', 'public_intake'))`). This converts a runtime invariant into a schema-level constraint, which is the right level for an identity discriminator.
- `is_synthetic_member()` narrows from `object | str` to member-like objects only; raw strings fail loudly. This eliminates the compatibility shim path INIT-124 left open, and means a forgotten call site that still passes `discord_user_id` will raise at test time rather than silently miscompare.
- Every guard call site in `services/api/app/services/applications.py:324-336`, `services/api/app/services/applications.py:618-632`, `services/api/app/services/applications.py:867-906`, `services/api/app/services/trust.py:291-486`, `services/api/app/services/roster.py:120-158`, `services/api/app/services/authority.py:145-201`, and `services/api/app/services/members.py:229-295` already fetches the member row before deciding, so the predicate-source change does not introduce new fetches and does not move the locking boundary.
- `MemberRead.kind` makes the contract explicit to authorized callers and discourages future client logic from re-parsing `discord_user_id` to infer synthetic identity.
- Public-intake idempotency is preserved verbatim because `discord_user_id = "public:<digest>"` is still derived from `public_submission_id` and `channel_salt` (`services/api/app/services/members.py:180-192`); only the row's `kind` column changes.
- The proposal explicitly defers OAuth, conversion/link records, and historical roster/trust cleanup to BL-016/BL-017/BL-018 (`proposals/06-members-kind.md:284-288`), matching the RCA's decomposition (`.tmp/rca/discord-oauth-linking-FINDINGS.md:229-259`). Pre-existing pollution remains observable but unaddressed in this slice; the RCA's local check found zero such rows, and the slice does not promise to address historical pollution.

The fragility shifts from "synthetic identity is inferred from a string prefix" to "synthetic identity is a typed schema column", with the residual pre-existing-pollution surface explicitly assigned to a later slice.

## Adjacent-path blast-radius bounding

Adjacent paths I checked:

- INIT-120 public submit (`POST /api/v1/public/applications`, `POST /api/public/applications`). `submit_public_application()` resolves/creates a public-intake member through `resolve_or_create_public_intake_member()` and submits with `_SubmissionAuthority.PUBLIC_INTAKE` (`services/api/app/services/applications.py:773-805`). The proposal preserves both the receipt shape and the authority exception (`proposals/06-members-kind.md:218-220`, `proposals/06-members-kind.md:225`). Existing INIT-120 e2e fixtures assert `public:[0-9a-f]{32}` (`services/api/tests/test_public_intake_submit.py:54-62`). The proposal explicitly retains the `public:` token format in `discord_user_id` for idempotency (`proposals/06-members-kind.md:81`, `proposals/06-members-kind.md:156-160`). Adjacent path stays intact.
- INIT-124 boundary guards. Each of the eight guarded write paths still rejects synthetic/public-intake members and accepts real members; only the predicate source changes (prefix -> kind). The proposal preserves all six shipped error codes (`applicant_synthetic_not_allowed`, `owner_synthetic_not_allowed`, `trust_subject_synthetic_not_allowed`, `roster_member_synthetic_not_allowed`, `leadership_alias_synthetic_not_allowed`, `member_status_synthetic_not_allowed`) verbatim (`proposals/06-members-kind.md:84-85`, `proposals/06-members-kind.md:53-54`). Tests-intent track explicitly covers each guard at `particular-integration` level (`proposals/06-members-kind.md:259`).
- Discord submission service (`services/discord/app/handlers/application_submission.py`). Resolves the actor through `/api/v1/members/by-discord/{numeric}` and submits authenticated. The proposal does not change `create_or_get_member()`'s external signature; default `_kind="discord"` is applied internally (`proposals/06-members-kind.md:69`, `proposals/06-members-kind.md:202-204`). Adjacent path stays green.
- Authenticated submit `POST /api/v1/applications`. The submit guard now reads `kind` from the fetched applicant row instead of the prefix; the public-intake authority exception remains the only allowed synthetic-applicant submission path (`services/api/app/services/applications.py:618-632`, preserved in proposal `proposals/06-members-kind.md:178-180`). Existing real-member tests pass unchanged.
- Member exact reads (`/api/v1/members/{member_id}`, `/api/v1/members/by-discord/{discord_user_id}`). Intentionally unfiltered (`services/api/app/api/v1/endpoints/members.py:112-145`). The new `kind` field surfaces to authorized callers; this was an expected, documented choice (`proposals/06-members-kind.md:71-73`).
- Audit substrate (`activity_actions`, `activity_state_changes`). Anti-scoped: `kind` is not an audit-tracked field in this slice; the projection-only treatment matches the INIT-124 audit posture (`proposals/06-members-kind.md:228`).
- Trust profile reads, active-signal lists, owner workload aggregates, roster reads, compliance, archive counts. Out of scope; deferred to BL-018 read-side hardening (`proposals/06-members-kind.md:288`). Pre-existing pollution may still surface in those reads after the slice lands; the proposal does not promise to clean it.
- Cedar policy, Pomerium, Authentik, Discord OAuth, web UI, GitOps manifests, channel-template renderers. Not touched. Anti-scope respected.

Adjacent-path coverage gap (notable observation, non-blocking): the test-intent track has one item per guard call site (`proposals/06-members-kind.md:259`), but the migration unit test seeds only one `public:%` row and one numeric row (`proposals/06-members-kind.md:255`). Step 6a/6b should add a positive-control case where a numeric Discord ID that happens to contain the substring `public` (e.g., `123public456` is impossible because Discord snowflakes are decimal-numeric, but a degenerate test vector is cheap) is classified as `discord`. The Discord snowflake spec rules out the collision, but a regression test against the backfill SQL is essentially free.

## Migration and rollback realism

The migration follows the populated-table widening pattern from `migrations/versions/wu-028a_permission_drift_widening.py:34-110`: add nullable column, backfill via `UPDATE`, drop temporary default, alter to `NOT NULL`, add CHECK. This pattern is established convention in this repo. `migrations/versions/wu-003b_audit_context_columns.py:17-57` shows the same drop-default-after-add discipline.

Migration head verification:

- `migrations/versions/wu-041a_compliance_evaluations.py:10-11` declares `revision = "wu_041a_compliance_evaluations"` with `down_revision = "wu_037_compliance_evidence_invalidation"`.
- `migrations/versions/wu-042_chapter_governance.py:10-11` declares `revision = "wu_042_chapter_governance"` with `down_revision = "wu_022_applications"`. The chapter-governance migration is on a parallel chain below `wu_035_application_interview` rather than on the current head's chain.
- The proposal's selected `down_revision = "wu_041a_compliance_evaluations"` (`proposals/06-members-kind.md:65`) matches the most-recently-added head on the main chain. Step 6a should re-verify with `alembic heads` immediately before implementation; if a newer migration lands between proposal and Step 6, `down_revision` must move forward.

Constraint naming convention:

- `services/api/app/repositories/db.py:14-22` defines a SQLAlchemy MetaData naming convention with `"ck": "ck_%(table_name)s__%(constraint_name)s"`. `migrations/env.py:23` binds it as `target_metadata`, so Alembic's `op.create_check_constraint("members_kind_valid", "members", ...)` materializes the constraint as `ck_members__members_kind_valid` in PostgreSQL. This matches the wu-003b precedent (`migrations/versions/wu-003b_audit_context_columns.py:45-57` creates `activity_actions_scope_kind_valid` with the bare name, then drops `ck_activity_actions__activity_actions_scope_kind_valid`).
- The proposal's downgrade `op.drop_constraint("ck_members__members_kind_valid", "members", type_="check")` (`proposals/06-members-kind.md:133`) is consistent with this convention. Step 6c should run the migration up + down at least once locally to confirm; the audit gate also flagged this as a watch signal (`plans/risk/init-125a-audit.md:31`).

Rollback realism:

- The downgrade drops the CHECK constraint and the column. It does not delete `members` rows, rewrite `applications.applicant_id`, or touch audit/roster/trust state.
- The proposal's source-of-truth for synthetic identity in the rolled-back state is the residual `public:` prefix on the original rows. Because the migration does not mutate `discord_user_id`, the previous prefix-based helper would still classify the same rows correctly after a downgrade. This makes the rollback recoverable rather than data-lossy for the discriminator alone.
- Sequencing: API code that selects `kind` and uses kind-based guards must be reverted before the column is dropped, or the API will 500 on member reads. The proposal documents this ordering (`proposals/06-members-kind.md:276-282`). Step 6 must enforce: deploy migration before API code on upgrade; revert API code before downgrade migration on rollback.

Notable observation (non-blocking): the migration's `op.execute(...)` UPDATE backfill is idempotent only in the strict sense that a re-run before the `NOT NULL` alteration will only fill `kind IS NULL` rows. If the migration partially completes (column added, backfill not run, alteration aborted), a manual re-run is safe. After `NOT NULL` and the CHECK constraint are in place, no further `UPDATE` is required because new INSERTs flow through `_insert_member()`. This matches the wu-028a pattern.

## Observability

The proposal preserves observability through stable error codes plus existing logs and adds one new operator-visible signal.

- All six INIT-124 guard error codes remain unchanged (`proposals/06-members-kind.md:84-85`). API consumers continue to discriminate by code without contract churn.
- `MemberRead.kind` becomes a direct introspection signal for operators inspecting members: a `GET /api/v1/members/{id}` response now distinguishes `discord` from `public_intake` without parsing `discord_user_id`.
- The proposal includes verification SQL (`proposals/06-members-kind.md:241-245`) that an operator can run after migration:
  - `SELECT kind, count(*) FROM members GROUP BY kind ORDER BY kind;` — sanity-check the partition.
  - `SELECT count(*) FROM members WHERE discord_user_id LIKE 'public:%' AND kind <> 'public_intake';` — must be 0.
  - `SELECT count(*) FROM members WHERE discord_user_id NOT LIKE 'public:%' AND kind <> 'discord';` — must be 0.
- No metrics or alerts subsystem is added; this is consistent with the INIT-124 posture.

Residual observability concerns (non-blocking):

- `MemberKind` exposed as a closed `Literal["discord", "public_intake"]` in `MemberRead` means future kind additions (e.g., a hypothetical `linked_pending` from BL-017) become a contract bump. The proposal anti-scopes `linked_pending` (`proposals/06-members-kind.md:52`) and the RCA's open issue on `linked_pending` was deliberately closed in this slice (`.tmp/rca/discord-oauth-linking-FINDINGS.md:256-259`). When BL-017 lands, it will need to widen the type. Acceptable for the current slice.
- The CHECK constraint `kind IN ('discord', 'public_intake')` will reject any future `INSERT` that sends an unrecognized kind. This is correct for the current slice but will require a CHECK widening at the same time as the type widening above. Acceptable.
- The migration verification SQL is documented as operator-runnable but is not wired into a post-migration assertion. Step 6 may consider adding the check to a one-shot post-migration verification script if it exists in the repo. Optional.

## Channel-template parity

The proposal stays channel-agnostic by design. All channels run the same Alembic migration and the same API code (`proposals/06-members-kind.md:208-210`).

Parity-relevant checks:

- The change is a SQL migration plus service-layer logic. No GitOps manifest, channel-conditional renderer, or `gitops/channels/<channel>/` resource is touched.
- Local-IS-a-deployment-target framing holds (auto-memory `environment-agnostic-stack.md`): the migration runs in local exactly the way it runs in any other channel.
- Deployment cohort is "all channels" with no channel-specific code path (`proposals/06-members-kind.md:208-210`). No `local`-only or `dev`-only conditional branch is introduced into shared API code.
- The slice has no environment-specific secrets, no Discord OAuth endpoints, and no Authentik blueprint changes (those are decomposed to BL-016).

Local-first deployment with the same logical contract for remote channels is the correct posture for a schema-and-guard slice.

## Assumption register cross-check

For each assumption: I check (a) the cited evidence exists and supports the claim, and (b) the invalidation condition is observable.

A1. "Existing rows have either `discord_user_id LIKE 'public:%'` or a numeric Discord ID; no third case."
- Cited at `proposals/02-public-application-intake.md:65-72`, `services/api/app/services/members.py:46-56`, and `.tmp/rca/discord-oauth-linking-FINDINGS.md:73-85`. Verified `services/api/app/services/members.py:46-50` defines `SYNTHETIC_MEMBER_PREFIX = "public:"`. Verified `services/api/app/services/members.py:180-192` derives `discord_user_id = "public:<digest>"` for public intake. RCA's read-only check on the running cluster on `2026-04-28` returned 14 `public:%` rows and zero indicators of a third case.
- Invalidation condition: any existing member row with a non-numeric, non-`public:` `discord_user_id`. Observable through `SELECT id, discord_user_id FROM members WHERE discord_user_id NOT LIKE 'public:%' AND discord_user_id !~ '^[0-9]+$';`. Detection is built into the proposal's own verification SQL (`proposals/06-members-kind.md:243-244`). ✓

A2. "All active production code paths for `INSERT INTO members` go through `_insert_member()`."
- Cited at `services/api/app/repositories/members.py:58-79`, `services/api/app/services/members.py:116-177`, and `services/api/app/services/members.py:180-206`. Verified that `_insert_member()` is the only production helper; verified that `create_or_get_member()` and `resolve_or_create_public_intake_member()` both reach it.
- Invalidation condition: any production code path or test fixture writing directly to `members` without an explicit `kind` value. Observable through repository grep (`INSERT INTO members` outside `app/repositories/members.py`). The problem map enumerates the test files that bypass: `services/api/tests/conftest.py`, `services/api/tests/public_intake_fixtures.py`, `services/api/tests/test_members.py`, `services/api/tests/test_roster.py`, `services/api/tests/chapter_governance_helpers.py` (`research/10-members-kind-problem-map.md:47`). Step 6 must update each. ✓

A3. "`MemberRead` is the only public member read contract; adding `kind` does not break existing clients."
- Cited at `services/api/app/contracts/members.py:25-32`, `services/api/app/services/members.py:87-96`, and `services/api/app/contracts/members.py:18-22`. Verified that `MemberRead` is defined as the read DTO; verified that `MemberCreate` is separate and does not accept caller-supplied `kind`.
- Invalidation condition: a public API consumer that fails on unknown `MemberRead.kind`, or evidence that exposing `kind` is sensitive (e.g., an external integration that infers identity from member shape and would behave differently). No such consumer is in this repo. The web shell, Discord daemon, and admin tooling all parse JSON tolerantly. ✓

All three assumptions resolve at their cited locations. Each has an observable invalidation condition. None is contradicted by current source.

## Notable observations

These are observations and watch signals, not verdict-blockers.

1. **Test fixture coverage scope.** The proposal's scope (line 45) names `services/api/tests/conftest.py` for fixture updates, but the problem map identifies four additional test files with direct `INSERT INTO members`: `services/api/tests/public_intake_fixtures.py`, `services/api/tests/test_members.py`, `services/api/tests/test_roster.py`, and `services/api/tests/chapter_governance_helpers.py` (`research/10-members-kind-problem-map.md:47`). Step 6c must update every direct INSERT to include `kind`, otherwise the `NOT NULL` constraint will fail at fixture setup time. The contract in Step 6a should enumerate the full file list.

2. **`is_synthetic_member()` row-shape contract.** The proposal's helper (`proposals/06-members-kind.md:144-150`) reads `member["kind"]` for `dict` input and `getattr(member, "kind")` otherwise. Repository rows are `psycopg` row objects whose mapping shape depends on cursor configuration; if a guard call site passes a tuple-like row instead of a dict-like row, `member["kind"]` may raise. Step 6a should lock the row shape contract: every call site fetches the member through `_member_from_row()` -> `MemberRead`, or via `fetch_member_by_id()` which already returns the dict-like row. A unit test with a `dict`, a `MemberRead`, and a tuple-like row (asserting the tuple raises) closes this.

3. **Migration head verification at Step 6a.** The proposal selects `wu_041a_compliance_evaluations` as `down_revision` (`proposals/06-members-kind.md:65`). Step 6a should re-run `alembic heads` immediately before implementation. If another migration lands between proposal acceptance and Step 6, the `down_revision` and filename `wu-043_members_kind.py` must be advanced. Audit gate noted the same watch signal (`plans/risk/init-125a-audit.md:31`).

4. **Constraint name materialization.** Alembic's `op.create_check_constraint("members_kind_valid", ...)` materializes as `ck_members__members_kind_valid` because `migrations/env.py:23` binds the SQLAlchemy MetaData naming convention from `services/api/app/repositories/db.py:14-22`. The proposal's downgrade name matches. Step 6c should run the upgrade-then-downgrade cycle locally to confirm.

5. **`MemberRead.kind` non-optional default.** The proposal adds `kind` as a required field on `MemberRead`. Any test fixture that constructs a `MemberRead` directly (e.g., by calling the model with kwargs) will need to supply `kind`. Step 6c should grep for `MemberRead(` constructions in tests.

6. **No caller-supplied `kind` on `MemberCreate`.** The proposal correctly keeps `MemberCreate` unchanged (`proposals/06-members-kind.md:174`). This is the right write-boundary: external callers cannot mint synthetic rows. The internal `_kind` keyword on `_insert_member()` is the only kind-control path, and it is invoked only by `resolve_or_create_public_intake_member()`. Step 6c should confirm that no third caller of `_insert_member()` sneaks in during implementation.

7. **Discord submission flow expects `kind="discord"` for real members.** `services/discord/app/handlers/application_submission.py` resolves the actor through `/api/v1/members/by-discord/{numeric}` and submits authenticated. After this slice, that path will receive `kind="discord"` rows from `create_or_get_member()` defaults, and authenticated submit guards will accept them. Step 6c should verify the round-trip with at least one Discord-side integration smoke if one exists in the repo.

8. **Pre-existing pollution remains observable.** The RCA's local check found 14 `public:%` synthetic rows and zero downstream pollution (`.tmp/rca/discord-oauth-linking-FINDINGS.md:73-85`). After this slice, any pre-existing synthetic owner_id on `applications.owner_id`, synthetic `roster_entries.member_id`, synthetic `trust_profiles.member_id`, or synthetic `trust_signals.member_id` rows continue to read normally. Cleanup is BL-018; the proposal anti-scopes read-side hardening (`proposals/06-members-kind.md:51`, `proposals/06-members-kind.md:288`). Officer-facing reads must not regress in unexpected ways for a chapter that already has pollution; this is INIT-124's already-shipped residual and INIT-125A does not change it.

## Verdict

The proposal targets a well-bounded schema slice that introduces a typed `members.kind` discriminator, preserves all six shipped INIT-124 guard error codes, preserves INIT-120 public submit's receipt shape and idempotency contract, and uses a single Alembic migration on the current head with a non-destructive rollback. The assumption register is verifiable against current source (A1 backfill case-coverage, A2 single production INSERT path, A3 `MemberRead`-only read contract). The supported-surface track is honest about deferred read-side hardening, OAuth, and conversion/link records, all of which are explicitly assigned to BL-016/BL-017/BL-018. Blast radius is bounded to one column, one Pydantic field, one helper signature change, eight guard call-site updates, and the public-intake creator branch. Migration and rollback are realistic and follow established repo patterns (`wu-028a`, `wu-003b`). Channel-template parity is preserved because the change is shared API behavior with no channel-conditional code. The main residuals (test fixture file coverage beyond conftest, `is_synthetic_member()` row shape contract, migration-head re-verification at Step 6a, constraint-name materialization sanity, `MemberRead` constructor sites in tests, write-boundary preservation on `_insert_member()`, Discord submission round-trip, and pre-existing pollution staying out of scope) are Step 6a/6b/6c obligations rather than proposal-design defects. INIT-120 e2e and INIT-124 guards remain green by design.

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
