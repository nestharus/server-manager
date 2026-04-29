READ:
- proposals/06-members-kind.md
- research/10-members-kind-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- services/api/app/services/members.py
- services/api/app/repositories/members.py
- services/api/app/services/applications.py
- migrations/versions/wu-028a_permission_drift_widening.py
- migrations/versions/wu-035_application_interview.py
- migrations/versions/wu-042_chapter_governance.py
- services/api/app/repositories/db.py
- plans/risk/init-124-shortcut.md

# INIT-125A Phase 4 — Shortcut Risk Report

## Inputs read

- `proposals/06-members-kind.md` (full file)
- `research/10-members-kind-problem-map.md` (full file)
- `.tmp/rca/discord-oauth-linking-FINDINGS.md` (full file)
- Pipeline rules (Phase 4 shortcut-risk role)
- Predecessor `plans/risk/init-124-shortcut.md` for verdict-format and tone
- Spot-checks: `services/api/app/services/members.py:46-56,116-206,229-260`,
  `services/api/app/repositories/members.py:10-79`,
  `services/api/app/services/applications.py:324-336,615-632`,
  `migrations/versions/wu-028a_permission_drift_widening.py:34-110`,
  `migrations/versions/wu-035_application_interview.py:36-43`,
  `migrations/versions/wu-042_chapter_governance.py:24,275`,
  `services/api/app/repositories/db.py:14-22`

## Root-cause fix vs. relocation

The RCA names the root cause as: synthetic-vs-real identity is encoded
only as a magic prefix on `members.discord_user_id` (`public:<sha>`),
and INIT-124 guards inspect that prefix at every boundary — there is
no durable schema discriminator, so the prefix is the contract
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:140-165,229-259`,
`research/10-members-kind-problem-map.md:42-46`). The RCA explicitly
flags `members.kind` as the right *first* schema slice, distinct from
the OAuth, conversion, and cleanup slices that follow.

The proposal moves the discriminator off the prefix in three coupled
moves:

- Schema: `members.kind TEXT NOT NULL` with
  `CHECK (kind IN ('discord', 'public_intake'))`
  (`proposals/06-members-kind.md:108-129`). Future inserts must declare
  kind; the database itself enforces the closed enum.
- Helper: `is_synthetic_member()` is rewritten to read only `member.kind`
  from a row/object/Pydantic model and to fail loudly on raw strings
  or missing attribute (`proposals/06-members-kind.md:142-152`). The
  prefix predicate is deleted, not shadowed.
- Call sites: every existing INIT-124 call site is updated to pass the
  fetched row (or row-shaped object) rather than `row["discord_user_id"]`.
  The proposal lists them by name and line — applications submit (auth +
  owner transitions), trust signal/compute/recompute, leadership alias
  (reject and omit), roster create, member status PATCH
  (`proposals/06-members-kind.md:178-200`).

This is real relocation, not shadowing. After upgrade, no production
read path inspects the `public:` prefix as the source of truth for
synthetic identity. The single residual coupling is the migration's
own backfill expression
(`CASE WHEN discord_user_id LIKE 'public:%' THEN 'public_intake' ELSE 'discord' END`
at `proposals/06-members-kind.md:115-122`), which is a one-time
transitional read of the old discriminator to seed the new one — the
correct way to do this kind of cutover under A1
(`proposals/06-members-kind.md:249`).

The public-intake creator deliberately keeps minting
`discord_user_id="public:<digest>"` as part of public-submit
*idempotency* (`proposals/06-members-kind.md:156-160`), not as the
identity discriminator. That preserves INIT-120's idempotency contract
while letting INIT-125A change what `is_synthetic_member()` actually
asks. The two concerns are correctly factored apart: idempotency key
shape vs. identity classification.

Verdict on this question: the proposal fixes the named root cause
(magic-prefix discriminator) by moving the runtime decision to a
typed schema column and by deleting the prefix predicate from the
helper, with no production caller left reading the prefix to classify.
This is the stated INIT-125A scope from the RCA and the proposal does
not under-deliver against it.

## Migration mechanics

The proposal selects the populated-table widening pattern: add nullable,
backfill via SQL, alter to NOT NULL, add CHECK constraint, no lasting
`server_default` (`proposals/06-members-kind.md:108-129`). This matches
the in-repo precedent at
`migrations/versions/wu-028a_permission_drift_widening.py:34-110`,
which adds `permission_drift.kind` nullable, backfills from a join,
alters to NOT NULL, then adds a `kind IN (...)` check constraint. The
proposal cites that file by line range
(`proposals/06-members-kind.md:61`).

Ordering is correct:

1. `add_column("kind", Text, nullable=True)` — populated rows get NULL.
2. `UPDATE members SET kind = CASE ... END WHERE kind IS NULL` —
   backfill before any constraint exists. The `WHERE kind IS NULL`
   guard is the explicit re-run safety: re-running the SQL after
   backfill but before the NOT NULL alter is a no-op.
3. `alter_column("kind", server_default=None)` — defensive, given the
   add_column never set one. Harmless idempotent clear.
4. `alter_column("kind", nullable=False)` — succeeds because every
   row was filled in step 2.
5. `create_check_constraint("members_kind_valid", "members", "kind IN ('discord','public_intake')")`
   — applied after backfill, so no row violates it at constraint
   creation time and all future inserts are validated.

Idempotency on re-run:

- Alembic itself prevents re-run of the same migration revision against
  the same DB; the relevant idempotency surface is partial failure or
  manual `alembic stamp`/replay scenarios. The backfill's `WHERE kind
  IS NULL` clause makes the only re-runnable step a no-op against
  already-populated rows, which is the right invariant.
- The proposal's verification queries
  (`proposals/06-members-kind.md:241-244`) make backfill correctness
  externally observable: zero rows with `public:%` prefix and
  `kind <> 'public_intake'`, and zero rows without the prefix and
  `kind <> 'discord'`. That gives operators a post-deploy check, which
  is the correct shortcut-resistant posture.

Net: ordering is the same nullable→backfill→NOT NULL→CHECK pattern
already shipped at wu-028a; idempotency is achieved through the
`WHERE kind IS NULL` guard rather than by relying on alembic's
single-run semantics; no lasting `server_default` means the slice is
not silently dependent on a temporary default that a follow-up
forgets to drop. Risk on this dimension: LOW. (One downgrade naming
nit appears under §Notable observations — it does not change the
upgrade-path verdict.)

## Helper signature: dropping string input (no compat shim)

Current helper accepts `object | str` and inspects the prefix
(`services/api/app/services/members.py:46-56`). Production call sites
that currently pass a string today are:

- `services/api/app/services/applications.py:334`:
  `is_synthetic_member(member["discord_user_id"])` — `member` already
  fetched on line 331.
- `services/api/app/services/applications.py:624`:
  `is_synthetic_member(applicant["discord_user_id"])` — `applicant`
  already fetched on line 619.
- `services/api/app/services/members.py:243`:
  `is_synthetic_member(row["discord_user_id"])` — `row` already
  fetched on line 240.

(Trust, roster, and authority paths follow the same shape per the
problem map; they fetch the row, then pass the column to the helper —
`research/10-members-kind-problem-map.md:52-58`.)

In every case the row is already in scope at the call site. Passing
the row instead of the column is a one-line change at each site and
preserves the lock semantics that already exist. No production path
holds only a `discord_user_id` string at the moment it needs to
classify, so dropping string support drops nothing real.

The proposal explicitly forbids a raw-string overload as a "compatibility
shim for the deprecated discriminator"
(`proposals/06-members-kind.md:75-77`), which is the pipeline's
no-backwards-compat rule applied correctly. The helper now fails
loudly (raises) when given a raw string or an object without `kind`
(`proposals/06-members-kind.md:142-150`), which is the right
shortcut-resistant posture: a future caller that tries to revive the
prefix shorthand sees a test-time failure rather than a silent False.

Test impact is bounded. The unit test
`test_is_synthetic_member_identifies_only_public_prefix` and the
parametrized raw-string cases are explicitly listed for rewrite to
kind-based assertions (`proposals/06-members-kind.md:80-82`,
`research/10-members-kind-problem-map.md:32`); the proposal's
test-intent track names the unit test re-signal explicitly
(`proposals/06-members-kind.md:256`). That is honest test rework,
not a contract weakening.

Risk on this dimension: LOW.

## Backfill correctness for both classes

For `kind = 'public_intake'` rows:

- Source contract: `resolve_or_create_public_intake_member()` is the
  only production path that mints `public:<digest>` ids
  (`services/api/app/services/members.py:180-206`). RCA local DB check
  on 2026-04-28 found 14 such rows and zero rows with non-prefix
  synthetic identity (`research/10-members-kind-problem-map.md:73-85`).
- Backfill: every row matched by `discord_user_id LIKE 'public:%'`
  becomes `kind = 'public_intake'`. This is a literal read of the
  same predicate the deprecated helper used.
- Verification: `SELECT count(*) FROM members WHERE discord_user_id
  LIKE 'public:%' AND kind <> 'public_intake'` should return 0
  (`proposals/06-members-kind.md:243`).

For `kind = 'discord'` rows:

- Source contract: every other production member-creation path goes
  through `create_or_get_member()` and ultimately `_insert_member()`
  with a numeric Discord snowflake as `discord_user_id`
  (`services/api/app/services/members.py:116-177`,
  `services/api/app/repositories/members.py:58-79`).
- Backfill: the `ELSE 'discord'` branch covers everything that does
  not match the `public:%` prefix.
- Verification: `SELECT count(*) FROM members WHERE discord_user_id
  NOT LIKE 'public:%' AND kind <> 'discord'` should return 0
  (`proposals/06-members-kind.md:244`).

Both classes are bounded by A1: "existing rows have either
`discord_user_id LIKE 'public:%'` for synthetic public-intake
members or a numeric Discord ID for real members; there is no third
case" (`proposals/06-members-kind.md:249`). The assumption names its
evidence (the local DB check, INIT-120 source path, current helper
predicate) and the explicit invalidation: "any existing member row
with a non-numeric, non-`public:` `discord_user_id`" — which would
also have been a pre-existing INIT-124 guard violation. If A1 is
wrong, both INIT-124's prefix predicate and INIT-125A's backfill
fail in the same direction, and the verification queries make that
visible immediately.

A2 names the invalidation surface for write-time backfill skew: any
production INSERT path that bypasses `_insert_member()` and writes
without an explicit `kind` value (`proposals/06-members-kind.md:250`).
The proposal calls out `services/api/tests/conftest.py:208-233` and
several other test-fixture direct inserts as needing the same
update, which is honest rather than implicit.

Risk on this dimension: LOW. The backfill is the deprecated helper's
own predicate, executed once, with both directions of correctness
externally checkable.

## Anti-scope deferrals honest (BL-016/017/018)

The RCA's recommended decomposition
(`.tmp/rca/discord-oauth-linking-FINDINGS.md:337-383`) maps to four
slices:

1. Identity discriminator — INIT-125A — this proposal.
2. Authentik/Discord applicant auth.
3. Conversion service + member_links + application re-pointing.
4. Historical cleanup + read hardening.

The proposal anti-scopes the latter three explicitly and ties each
to a backlog id
(`proposals/06-members-kind.md:49-55,285-288`):

- BL-016: Authentik Discord OAuth provider, OIDC callback, applicant
  login/link route. Anti-scope bullet "No Discord OAuth provider,
  Authentik source, OIDC callback, or applicant login/link route"
  matches RCA §"Authentik OIDC for applicants" missing-pieces list
  (`.tmp/rca/discord-oauth-linking-FINDINGS.md:108-115`).
- BL-017: conversion service, supersession/link records, application
  re-pointing. Anti-scope bullet "No conversion service, `member_links`
  table, synthetic-to-real promotion, or application re-pointing"
  matches RCA §"Conversion service shape" / §"Application re-pointing
  semantics" (`.tmp/rca/discord-oauth-linking-FINDINGS.md:168-198,
  296-334`).
- BL-018: historical roster/trust cleanup, query-level hardening.
  Anti-scope bullet "No read-side roster/trust cleanup, historical
  data sweep, or query-level roster hardening" matches RCA
  §"Read-side cleanup approach" (`.tmp/rca/discord-oauth-linking-FINDINGS.md:201-227`).

Two further deferrals are structurally honest:

- `linked_pending` is excluded from the enum
  (`proposals/06-members-kind.md:52`). The RCA flagged this as an
  open design question that depends on whether INIT-125C uses
  in-place promotion, a `member_links` table, or both
  (`.tmp/rca/discord-oauth-linking-FINDINGS.md:256-259`). Choosing
  the two-value enum now means the CHECK constraint must be widened
  by INIT-125C if `linked_pending` is needed; that is a contained
  follow-up cost (one ALTER) rather than a speculative widening
  today. The choice is consistent with the pipeline's
  no-deferred-stubs rule — adding `linked_pending` now without a
  consumer would be a stub.
- Caller-supplied `kind` in `MemberCreate` is excluded
  (`proposals/06-members-kind.md:53,174`). The discriminator is
  enforced by the creation path, not by the request shape; external
  callers cannot mint `public_intake` rows. That preserves INIT-124's
  invariant that public intake is the only synthetic write path
  (`proposals/05-synthetic-member-guard.md:33-50`) and is the right
  shortcut-resistant choice.

Two named no-changes preserve in-flight contracts:

- INIT-124 shipped error codes are explicitly preserved by name
  (`proposals/06-members-kind.md:54,83-85`). The proposal lists
  every shipped code and its current emit site. This is correct: a
  rename now would mean every operator runbook, dashboard, and test
  must change for a slice that is supposed to swap the predicate
  source, not the surface contract.
- No Discord-visible mutation (`proposals/06-members-kind.md:56`).
  That keeps the slice testable against the local stack without
  needing Authentik/Discord plumbing.

The supported-surface track is consistent with these deferrals. The
blast-radius bullets at `proposals/06-members-kind.md:225-228`
explicitly enumerate which adjacent surfaces stay behaviorally
unchanged (INIT-120 receipt shape, INIT-124 boundary semantics,
Discord submission flow, audit substrate) and what counts as a
regression inside each. The migration/rollback section
(`proposals/06-members-kind.md:268-282`) commits to not deleting
public-intake rows or rewriting application FKs on rollback, which
is the same indefinite-retention posture INIT-124 took
(`plans/risk/init-124-shortcut.md` §"Rollback honesty").

Risk on this dimension: LOW. Each deferral names the follow-up work
unit, the surface it does not touch, and (for `linked_pending` and
caller-supplied `kind`) the principled reason for the no-now choice.

## Notable observations

1. **Single source of synthetic identity, durably typed.** Today
   `is_synthetic_member()` and the `SYNTHETIC_MEMBER_PREFIX` constant
   are the single-place discriminator
   (`services/api/app/services/members.py:46-56`); INIT-124's
   shortcut review already credited that factoring. INIT-125A
   carries that single-source posture forward but moves the source
   of truth from a runtime constant to a typed schema column with a
   CHECK constraint. That makes the discriminator visible to
   operators (`SELECT kind, count(*) FROM members ...`,
   `proposals/06-members-kind.md:242`) and enforced by the database
   rather than by helper convention. This is the inverse of the
   typical observability/safety shortcut.

2. **Public-intake idempotency stays in the right place.** The
   `public:<digest>` `discord_user_id` is *only* an idempotency key
   for INIT-120 public submit
   (`proposals/06-members-kind.md:156-160`,
   `services/api/app/services/members.py:180-206`). The proposal
   does not rename it, hash it differently, or move it into the new
   `kind` column. Conflating "how do we re-find the same public
   submission?" with "how do we tell synthetic from real?" is
   exactly the conflation that produced the magic-prefix
   discriminator in the first place; the proposal explicitly keeps
   them separate.

3. **Helper signature failure-on-misuse is loud, not silent.** The
   new helper raises on raw-string input or on objects without a
   `kind` attribute (`proposals/06-members-kind.md:142-150`). That
   means a future caller that imports a deprecated pattern (e.g. a
   merge from a stale branch that still passes `discord_user_id`)
   sees an exception in tests rather than a silent False. The
   alternative — accepting strings and returning False — would have
   been the shortcut. The proposal does not take that path.

4. **MemberRead exposing `kind` is a deliberate scope expansion,
   not a leak.** Adding `kind` to the public read contract
   (`proposals/06-members-kind.md:163-174`) goes slightly beyond the
   minimum needed to swap the predicate, but the proposal justifies
   it explicitly: it discourages clients from parsing the
   `discord_user_id` prefix to recover the same information
   (`research/10-members-kind-problem-map.md:80`). Pushing a typed
   field into the read contract now prevents a future where two
   places (server helper + client parsing) re-implement the same
   classification — the same anti-pattern this slice is removing
   server-side. This is honest scope expansion, named in A3 and in
   the supported-surface track. Belongs in Step 6a contract
   definition so the read-shape is pinned before tests are encoded.

5. **Internal `_kind` keyword on `_insert_member()` is the right
   layering.** The proposal threads `_kind` through the private
   repository helper rather than through `MemberCreate` or the
   external `create_or_get_member()` signature
   (`proposals/06-members-kind.md:67-69,202-204`). That means the
   service-layer caller (public-intake creator) opts in by passing
   `_kind="public_intake"` explicitly, and every other caller
   defaults to `discord` without seeing the parameter. External API
   callers cannot mint synthetic rows because `MemberCreate` does
   not carry `kind`. This is the same layering pattern INIT-124
   used to keep the synthetic-write boundary single-sourced.

6. **Migration check-constraint downgrade name asymmetry.** The
   upgrade calls
   `op.create_check_constraint("members_kind_valid", "members", ...)`
   but the downgrade calls
   `op.drop_constraint("ck_members__members_kind_valid", "members", type_="check")`
   (`proposals/06-members-kind.md:125-129,133`). Existing repo
   migrations consistently use bare names on both ends —
   `applications_state_valid` (`migrations/versions/wu-035_application_interview.py:36,99-106`),
   `chapters_state_valid` (`migrations/versions/wu-042_chapter_governance.py:24,275`),
   `permission_drift_kind_valid` (wu-028a). The SQLAlchemy
   `MetaData` naming convention at
   `services/api/app/repositories/db.py:14-22` does prepend
   `ck_<table>__`, but that convention only applies to constraints
   declared on `MetaData`-bound tables; raw `op.create_check_constraint`
   calls in alembic use the literal name as written. The
   downgrade as written will fail with `constraint
   "ck_members__members_kind_valid" of relation "members" does not
   exist`. This is not a shortcut-risk verdict mover (the upgrade
   path is correct and the slice's blast-radius is bounded), but
   Step 6a or Step 6c must reconcile the pair to one bare name
   (`members_kind_valid`) before the migration is shipped.
   Otherwise the proposal's own honest rollback claim
   (`proposals/06-members-kind.md:276-282`) becomes false at
   downgrade time. Worth surfacing to audit risk for capture as a
   contract defect.

7. **Test fixture fan-out is named, not implicit.** The proposal
   calls out direct-insert sites in the test suite
   (`proposals/06-members-kind.md:79-82`, problem map at
   `research/10-members-kind-problem-map.md:32,47`) — `conftest.py`,
   `public_intake_fixtures.py`, `test_members.py`, `test_roster.py`,
   `chapter_governance_helpers.py`. After NOT NULL lands, any
   un-updated fixture will fail loudly at INSERT time, not at
   assert time. That is the right failure mode. Listing them
   up-front means Step 6c is not surprised by a long-tail of
   fixture breakage.

8. **Error-code stability is a non-negotiable contract.** The
   proposal preserves `applicant_synthetic_not_allowed`,
   `owner_synthetic_not_allowed`,
   `trust_subject_synthetic_not_allowed`,
   `roster_member_synthetic_not_allowed`,
   `leadership_alias_synthetic_not_allowed`, and
   `member_status_synthetic_not_allowed` by name
   (`proposals/06-members-kind.md:54,83-85`). The problem map flags
   one INIT-124-prose vs. shipped-code drift around
   `trust_subject_synthetic_not_allowed` vs.
   `trust_member_synthetic_not_allowed`
   (`research/10-members-kind-problem-map.md:54,83`); the proposal
   explicitly chooses the shipped code, which is correct — renaming
   here would be a hidden API break and a shortcut from operator
   stability for a slice whose stated job is swapping the
   discriminator source.

9. **Channel parity preserved.** The migration is declared as
   running in every channel because `members.kind` is part of the
   API contract and write-boundary behavior
   (`proposals/06-members-kind.md:208-210`). No `local`-only branch,
   no per-channel skew. This continues the
   INIT-120/INIT-122/INIT-124 channel-template invariant rather
   than carving out a synthetic-discriminator exception.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

The proposal moves the synthetic-vs-real discriminator off the
`discord_user_id` prefix and into a typed schema column with CHECK
enforcement, deletes the prefix predicate from the runtime helper,
updates every named INIT-124 call site to pass rows rather than
prefix strings, and preserves shipped INIT-124 error codes. Migration
mechanics follow the in-repo `wu-028a` populated-table widening
pattern with `WHERE kind IS NULL` re-run safety and no lasting
`server_default`. Backfill correctness is bounded by A1 and is
externally checkable in both directions through the proposal's
verification queries. Helper-signature narrowing drops nothing real
because every production caller already has the row in scope, and
the loud-failure semantics on raw-string input prevent a silent
revival of the deprecated predicate. The three large adjacent slices
(BL-016 OAuth, BL-017 conversion + re-pointing, BL-018 historical
cleanup + read hardening) are explicitly anti-scoped by name with
RCA-aligned justification, and `linked_pending` and caller-supplied
`kind` are honestly excluded with principled reasons rather than
deferred as silent stubs. The downgrade check-constraint name
asymmetry (Observation 6) is a contract defect to fix in Step 6a/6c
and route to audit risk; it does not change the shortcut-risk
verdict because the upgrade path is correct, the slice does not
silently rely on a temporary default, and the slice's purpose is
fully delivered on the upgrade side. No invalidated assumptions and
no non-positive value signal on the current supported surface.
