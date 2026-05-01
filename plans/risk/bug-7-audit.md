# Risk audit — BUG-7 officer member aggregate head in e2e authority seed

Inputs:
- Proposal: `proposals/22-bug-7-officer-aggregate-head.md`
- RCA: `research/35-bug-7-officer-queue-chapter-rca.md`
- Substrate: `infra/tests/e2e/lib/seed-authority-grants.mjs` (extend
  with member aggregate-head insertion + chapter-fixture guard).

## Verdict

**Risk level: LOW.** APPROVED — proceed to implementation.

The proposal directly attacks the RCA's named root cause: the e2e
authority seed inserts a raw `members` row but no `aggregate_heads`
row, while the production member read path (`fetch_member_by_discord_id`
at `services/api/app/repositories/members.py:10-23,37-45`) joins
`members` to `aggregate_heads`, so the seeded officer is invisible to
`_build_officer_actor` →
`resolve_or_create_real_discord_member` and the bridge 500s before
list filtering ever runs. The fix lives in the test fixture (the wrong
side of the contract was the test, not production), uses the same
direct-projection minimum-row shape that is already established by
`services/api/tests/chapter_selector_fixtures.py`,
`services/api/tests/public_intake_fixtures.py`, and BUG-5's
`seed-chapter-fixture.mjs` (`current_seq=1`, `latest_change_id=NULL`),
and is fail-closed and idempotent in the same shape as the BUG-5
helper. Anti-scope correctly forbids weakening
`fetch_member_by_discord_id`, compensating in `_build_officer_actor`,
backfilling in `resolve_or_create_real_discord_member`, or sneaking
`chapter-alpha` creation into this helper. TG-1/2/3 are testable as
written.

## Findings

### F-1 Fix targets the RCA's actual root cause — PASS

RCA §"Root Cause" (lines 132-139) names the failure precisely: the
seeded officer member has no `aggregate_heads` row, so the
`members ⨝ aggregate_heads` join in `fetch_member_by_discord_id`
returns no row, the resolver tries to insert and is rejected by the
`members.discord_user_id` unique index via `ON CONFLICT DO NOTHING`,
which raises `DiscordMemberRaceLost`, and the race-lost recovery path
(`services/api/app/services/members.py:264-267`) calls
`_fetch_member_row_by_discord_id`, which delegates to the same
aggregate-head-joined `fetch_member_by_discord_id`
(`services/api/app/services/members.py:114-121`,
`services/api/app/repositories/members.py:37-45`). That second join
also returns nothing, `MemberNotFoundError` is raised, FastAPI surfaces
500, and `list_applications` is never reached.

Proposal §1 (lines 3-12) reproduces this chain verbatim and §2 Q1
(lines 17-25) chooses the only fix surface that does not weaken a
production contract: insert the missing `aggregate_heads` row in the
fixture helper. The two rejected options — relaxing the bridge or
having the resolver backfill direct-seeded projection rows — would
both teach production code to tolerate impossible state and erase the
load-bearing invariant that a `members` row without an
`aggregate_heads` row is incomplete. PASS.

### F-2 SQL targets the right schema — PASS

§Q2 (lines 27-48) prescribes:

```sql
INSERT INTO aggregate_heads (
  aggregate_type, aggregate_id, current_seq, latest_change_id
) VALUES ('member', <member.id::text>, 1, NULL)
```

This matches the join condition the production query relies on at
`services/api/app/repositories/members.py:20-22`
(`h.aggregate_type = 'member' AND h.aggregate_id = m.id::text`) and
the column the production query reads
(`h.current_seq AS version`, line 18). The fixture-shape constants
`current_seq = 1` / `latest_change_id = NULL` are the same shape used
by every other minimum-row materialized fixture in the repo, including
`services/api/tests/chapter_selector_fixtures.py`,
`services/api/tests/public_intake_fixtures.py`, and BUG-5's
`infra/tests/e2e/lib/seed-chapter-fixture.mjs:235-256`. The reasoning
in §Q2 (lines 42-47) for excluding `current_seq = 0` is correct:
`current_seq = 0` is the pre-create head row that `mutate_entity`
writes inside its transaction before the accepted state change; a
direct-seeded *existing* member projection should be visible at
version 1, not as a half-created mutation. PASS.

### F-3 Idempotency rules are complete — PASS

§Q3 (lines 50-62) lays out the idempotency contract: insert the head
when missing, no-op when an existing head matches the fixture shape
exactly (`aggregate_type='member'`, `aggregate_id=member.id::text`,
`current_seq=1`, `latest_change_id IS NULL`), abort on incompatible
shape, and explicitly forbids the helper from updating an existing
head to coerce it into fixture shape (which would rewrite aggregate
history and silently mask drift).

§3 substrate (lines 95-114) maps that contract to concrete CTEs:
`fixture_guard` for the abort check, `inserted_member_head` for the
WHERE-NOT-EXISTS insert, plus a final SELECT that reports
no-op/inserted/aborted distinctly enough to diagnose. The shape mirrors
`infra/tests/e2e/lib/seed-chapter-fixture.mjs:93-178` (`existing` →
`conflicts` → `guard` → `inserted_*` → `counts`), which is already
established in this repo for the analogous chapter fixture and was
endorsed by `plans/risk/bug-5-audit.md` (F-2). PASS.

### F-4 No poisoning of other tests — PASS

The helper writes are confined to:

- one `members` row keyed by `discord_user_id` (existing behavior,
  unchanged);
- one `aggregate_heads` row keyed by
  `('member', <officer member id>::text)` (new);
- one `authority_grants` row for the requested
  `(grantee_id, scope_kind, scope_id, permissions)` (existing
  behavior, unchanged).

§Q4 (lines 64-83) adds a *guard-only* chapter-alpha precondition for
the chapter-scoped invocation: it asserts that BUG-5's chapter fixture
already exists and aborts otherwise; it explicitly does not create or
repair the chapter, that ownership remains with
`seed-chapter-fixture.mjs`. §5 anti-scope (lines 162-174) forbids
synthesizing activity actions / state changes, adding authority-grant
aggregate heads, or repairing the chapter inside this helper. The
member id is derived from the existing `resolved_member` /
`checked_member` flow which is keyed on the officer's `discord_user_id`
constant, so the new `aggregate_heads` insert touches exactly that
officer's row and nothing else. No leakage into other test surfaces.
PASS.

### F-5 Bridge actor construction succeeds on the next call — PASS

After the helper runs, `fetch_member_by_discord_id` for
`210987654321098765` returns a row with
`version = aggregate_heads.current_seq = 1`. That non-None return short-
circuits `resolve_or_create_real_discord_member` at
`services/api/app/services/members.py:210-212` (`if existing is not
None: return _require_real_discord_member(existing)`), so the resolver
never reaches the `_insert_member_on_discord_conflict_do_nothing` path
that previously raised `DiscordMemberRaceLost`. The seeded officer's
`members.kind = 'discord'`
(`infra/tests/e2e/lib/seed-authority-grants.mjs:71-72`) so
`_require_real_discord_member` (`services/api/app/services/members.py:
188-193`) returns a `MemberRead` instead of raising
`NonDiscordMemberError`. `_build_officer_actor`
(`services/api/app/api/v1/endpoints/web.py:122-141`) receives the
member and returns
`ActorIdentity(actor_kind="user", actor_id=str(member.id))`, after
which the queue endpoint can call `list_applications`. The
`MemberNotFoundError → 500` chain documented in the RCA
(`research/35-bug-7-officer-queue-chapter-rca.md:39-46,131-139`) is
broken at its first link. PASS.

### F-6 TG-1/2/3 are testable — PASS

- **TG-1** (proposal lines 125-142): direct DB query against
  `members ⨝ aggregate_heads` for `discord_user_id = '210987654321098765'`
  expecting one row with `current_seq = 1`. Executable through the
  same `kubectl exec ... psql` path the helper itself uses; the assert
  is exact (one row, exact version) so a regression that wrote the
  member but not the head, or wrote the head with the wrong sequence,
  fails loudly. Mirrors BUG-5 TG-1's three-way assertion shape and is
  the right shape for this fix.

- **TG-2** (proposal lines 144-154): officer queue endpoint with
  spoofed Pomerium officer headers should return 200, not 500. The
  proposal correctly notes that `GET /api/v1/me`
  (`research/35-bug-7-officer-queue-chapter-rca.md:34-36,118-120`)
  *already* returned 200 in the broken state because that endpoint
  does not call `_build_officer_actor`, so it would have been a
  misleading green check. Targeting `GET /api/v1/web/officer/applications?
  state=submitted,queued&scope_kind=chapter&scope_id=chapter-alpha`
  is precisely the call the RCA observed at 500 and is the smallest
  scope that exercises both the bridge actor build *and* the
  chapter-scoped read. The TG is therefore both falsifiable and
  failure-isolating.

- **TG-3** (proposal lines 156-161): full re-run of
  `infra/tests/e2e/tests/19-web-ui.sh` with the expectation that
  Playwright finds the queue row at `[data-application-id="<id>"]`.
  This is the regression scenario the bug originally caught.
  `services/web/src/features/officer/ApplicationQueueRoute.tsx:185-191`
  renders that exact selector
  (`research/35-bug-7-officer-queue-chapter-rca.md:80-89`), so the TG
  is an end-to-end pass criterion.

PASS.

## Observations (non-blocking)

1. **Two scope invocations, only one head.** Per
   `infra/tests/e2e/tests/19-web-ui.sh:280-287`,
   `seed-authority-grants.mjs` is invoked twice (once with default
   global scope, once with `E2E_APPLICATION_SCOPE_KIND=chapter` /
   `E2E_APPLICATION_SCOPE_ID=chapter-alpha`). The new
   `inserted_member_head` CTE is keyed by the officer's
   `discord_user_id` constant, so the first invocation inserts the
   head and the second finds the row already present and no-ops.
   That is exactly the intended idempotent behavior; flagging it only
   so the implementer wires the WHERE-NOT-EXISTS guard against the
   correct
   `(aggregate_type='member', aggregate_id=<member.id::text>)` key
   and not against the head's `latest_change_id` or anything else
   that would change between runs.

2. **CTE write visibility.** Implementer should use the
   `seed-chapter-fixture.mjs:179-262` pattern (explicit
   `WHERE NOT EXISTS` / guard subquery in the modifying CTE) rather
   than chained `RETURNING` reads, because PostgreSQL data-modifying
   CTEs share a single snapshot and cannot see each other's row writes
   through SELECT. Same observation `plans/risk/bug-5-audit.md`
   recorded for the chapter helper. The proposal's §3 substrate (lines
   95-114) is already structured this way; flagging only as
   implementation guidance.

3. **Chapter guard scope.** §Q4 (lines 81-83) correctly limits the
   chapter-fixture precondition to the chapter-scoped invocation
   (`E2E_APPLICATION_SCOPE_KIND=chapter` and
   `E2E_APPLICATION_SCOPE_ID=chapter-alpha`). For the default global
   invocation the helper must not assert chapter presence — otherwise
   it would couple the global officer seeding to BUG-5 and break
   tests that don't need a chapter fixture. Implementer should branch
   the guard on the `scopeKind`/`scopeId` env values
   (`infra/tests/e2e/lib/seed-authority-grants.mjs:13-14`), not run it
   unconditionally.

4. **Authority-grant aggregate heads remain intentionally absent.**
   §Q5 (lines 86-91) and §5 anti-scope (lines 170) explicitly hold the
   line: `list_grants` /`list_grants_for_grantee` read raw
   `authority_grants` rows without joining `aggregate_heads`, so the
   missing grant heads are not load-bearing for the BUG-7 surface.
   This is the right scope-discipline call — adding them would expand
   the diff and risk adding synthetic activity rows without a
   corresponding production contract requiring them. If a future bug
   surfaces a code path that *does* require grant aggregate heads,
   that work belongs to a separate proposal, not this one.

5. **`checked_member` UNION + LIMIT 1 ordering.** The existing
   `seed-authority-grants.mjs:77-82` `checked_member` CTE relies on
   `UNION ALL ... LIMIT 1` to surface either the just-inserted row or
   the prior row. PostgreSQL does not guarantee `UNION ALL` ordering
   without an explicit `ORDER BY`, but in practice the
   `resolved_member` branch is empty on a no-op insert (the `ON
   CONFLICT DO UPDATE SET discord_user_id = EXCLUDED.discord_user_id`
   trick still RETURNS the row, so this is fine for the existing
   helper). The new `inserted_member_head` CTE should derive
   `member.id` from `checked_member`, not re-resolve it, to inherit the
   same ordering robustness. Implementation guidance only.

## Acceptance check (proposed)

When implementation lands, all of the following must hold:

- `infra/tests/e2e/lib/seed-authority-grants.mjs` is the only
  modified file (no production code, no migrations, no helper-file
  splits, no GitOps changes). Diff sits in the §6 budget of roughly
  50-90 changed lines.
- The helper inserts (when missing) one
  `aggregate_heads` row with `aggregate_type='member'`,
  `aggregate_id = <officer member id>::text`,
  `current_seq=1`, `latest_change_id=NULL`, keyed off the
  `checked_member` CTE.
- The helper aborts (does not silently update) when an existing
  member head row exists with `current_seq <> 1` or
  `latest_change_id IS NOT NULL`.
- The helper aborts when `kind <> 'discord'` for the seeded member
  (already enforced for the grant insert at lines 108-109; should be
  enforced consistently in the new guard).
- When `E2E_APPLICATION_SCOPE_KIND=chapter` and
  `E2E_APPLICATION_SCOPE_ID=chapter-alpha`, the helper performs the
  §Q4 chapter-fixture precondition check and aborts if BUG-5's
  chapter fixture is missing or has a non-fixture shape.
- The helper does not create, update, or repair the `chapter-alpha`
  row, the chapter `aggregate_heads` row, the chapter template, the
  `authority_grants` aggregate head, or any `activity_actions` /
  `activity_state_changes` rows.
- Final SELECT returns a JSON summary that distinguishes
  member-row inserted/already-present, member-head
  inserted/already-present/aborted, and grant inserted/already-present
  outcomes, so the test runner can diagnose partial state.
- TG-1: direct DB query for the officer Discord user joined to
  `aggregate_heads` returns exactly one row,
  `(210987654321098765, 1)`.
- TG-2: with spoofed Pomerium officer headers,
  `GET /api/v1/web/officer/applications?state=submitted,queued&scope_kind=chapter&scope_id=chapter-alpha`
  returns `200`, not `500`.
- TG-3: re-running `infra/tests/e2e/tests/19-web-ui.sh` succeeds and
  Playwright finds the queue row at `[data-application-id="<id>"]`.
- No edits in `services/api/`, `services/web/`, `migrations/`, or
  `gitops/`.

AUDIT_DONE: plans/risk/bug-7-audit.md
