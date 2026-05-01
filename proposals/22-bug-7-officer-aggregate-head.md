# BUG-7 Proposal: Officer member aggregate head in e2e authority seed

## 1. Problem statement

The e2e authority seed helper creates the officer member and grants with direct SQL projection inserts, but does not create aggregate metadata. The live `members` row for officer Discord user `210987654321098765` exists, but it has no `aggregate_heads` row.

The officer bridge does not use raw `members` rows. `_build_officer_actor` calls `resolve_or_create_real_discord_member`, whose initial lookup uses `fetch_member_by_discord_id`. That repository query joins `members` to `aggregate_heads`. Because the seeded member lacks an aggregate head, the lookup returns no member.

The resolver then attempts to create the member. The raw `members.discord_user_id` unique constraint rejects the insert via `ON CONFLICT DO NOTHING`, so the resolver raises `DiscordMemberRaceLost`. Its race-lost recovery path again uses the same aggregate-head-joined lookup, still cannot see the raw seeded member, and raises `MemberNotFoundError`. FastAPI surfaces that unhandled exception as a 500.

Therefore, the queue does not return the chapter-alpha application because the bridge cannot construct the officer actor. Scope filtering and the SPA row selector are not the immediate failure point.

## 2. Decisions

### Q1. Where does the fix live?

Pick: **Option a, extend `infra/tests/e2e/lib/seed-authority-grants.mjs` to also insert the officer member aggregate head.**

This is the narrow fixture correction. The failure is caused by a direct SQL e2e seed creating a projection row that production repository reads intentionally treat as incomplete. Fix the test fixture, not production member resolution or bridge actor construction.

Rejected:

- Option b, bridge resilience: this would make `_build_officer_actor` compensate for impossible production state and weaken the aggregate-head-backed member read contract.
- Option c, resolver repair: `resolve_or_create_real_discord_member` should continue to create complete members through `mutate_entity`; it should not backfill incomplete direct-seeded projection rows.

### Q2. Aggregate sequence number

Use the actual activity-substrate schema names in this repo:

```sql
INSERT INTO aggregate_heads (
  aggregate_type,
  aggregate_id,
  current_seq,
  latest_change_id
)
VALUES ('member', <member.id::text>, 1, NULL)
```

Lock `current_seq = 1` and `latest_change_id = NULL`.

Reasoning:

- `fetch_member_by_discord_id` reads `h.current_seq AS version`; it only needs a matching head row.
- Direct minimum-row fixtures already use `current_seq = 1, latest_change_id = NULL` for materialized entities, including `services/api/tests/chapter_selector_fixtures.py`, `services/api/tests/public_intake_fixtures.py`, and BUG-5's `seed-chapter-fixture.mjs`.
- `current_seq = 0` represents the pre-create head inserted inside `mutate_entity` before the accepted state change. A direct-seeded existing member projection should be visible as version 1.
- Do not create a synthetic `activity_actions` or `activity_state_changes` row for this fixture.

### Q3. Idempotent?

Yes. Match BUG-5's fail-closed fixture shape.

The helper should:

- Resolve or create exactly one officer member row for `discord_user_id`.
- Insert the member aggregate head only if missing.
- Treat an existing compatible head as a no-op.
- Abort if an existing member head has an incompatible fixture shape: `aggregate_type = 'member'`, `aggregate_id = member.id::text`, but `current_seq <> 1` or `latest_change_id IS NOT NULL`.
- Return a JSON summary that includes whether the member row, member head, and authority grant were inserted or already present.

The helper must not update an existing aggregate head to force it back to fixture shape. That would rewrite aggregate history and hide state drift.

### Q4. Chapter aggregate head assertion

Yes, but only as a guard for the chapter-scoped invocation.

When `E2E_APPLICATION_SCOPE_KIND=chapter` and `E2E_APPLICATION_SCOPE_ID=chapter-alpha`, `seed-authority-grants.mjs` should assert that BUG-5's chapter fixture is already present:

```sql
SELECT 1
FROM chapters c
JOIN aggregate_heads h
  ON h.aggregate_type = 'chapter'
 AND h.aggregate_id = c.id
WHERE c.id = 'chapter-alpha'
  AND c.state = 'active'
  AND h.current_seq = 1
  AND h.latest_change_id IS NULL
```

If that guard fails, abort with a clear fixture-dependency error rather than creating the chapter or silently inserting chapter-scoped authority against a missing/incomplete chapter fixture.

For the default global invocation, do not perform this chapter guard.

### Q5. Are actions/state changes also needed?

No. `aggregate_heads` alone is sufficient for this bug.

The failing lookup is `fetch_member_by_discord_id`, whose query joins `members` to `aggregate_heads` and selects `h.current_seq AS version`. It does not join `activity_actions` or `activity_state_changes`.

The officer list authorization path also does not require authority-grant aggregate heads for the current queue flow: `list_grants_for_grantee` delegates to `list_grants`, and that repository query reads raw `authority_grants` rows without joining `aggregate_heads`. Therefore this proposal only adds the missing member head and the chapter fixture dependency guard. Authority-grant aggregate heads remain outside this fix.

## 3. Substrate

### Modified file

Modify only `infra/tests/e2e/lib/seed-authority-grants.mjs`.

### SQL shape

Keep the helper as one SQL statement executed through the existing kubectl/psql path.

Add CTEs around the current `resolved_member` / `checked_member` flow:

- `seed`: constants for `discord_user_id`, generated `member_id`, generated `grant_id`, `scope_kind`, `scope_id`, and seeded permissions.
- `resolved_member`: existing insert/upsert behavior for `members`.
- `checked_member`: the resolved `members` row.
- `fixture_guard`: fail-closed checks:
  - member row must be `kind = 'discord'`;
  - existing member aggregate head, if present, must be `current_seq = 1` and `latest_change_id IS NULL`;
  - chapter guard must pass when the requested authority scope is `chapter` / `chapter-alpha`.
- `inserted_member_head`: insert `('member', checked_member.id::text, 1, NULL)` when absent and guard passes.
- `inserted_grant`: preserve the existing idempotent grant insert behavior.
- final `SELECT`: return JSON or the member id as today, with enough detail to diagnose no-op/inserted/aborted outcomes.

No production code changes:

- no migration changes;
- no changes to `services/api/app/services/members.py`;
- no changes to `services/api/app/api/v1/endpoints/web.py`;
- no changes to `services/api/app/repositories/members.py`.

## 4. Test plan

### TG-1. Member aggregate head exists after seed

After running the seed for officer Discord user `210987654321098765`, this query returns exactly one row:

```sql
SELECT m.discord_user_id, ah.current_seq
FROM members m
JOIN aggregate_heads ah
  ON ah.aggregate_type = 'member'
 AND ah.aggregate_id = m.id::text
WHERE m.discord_user_id = '210987654321098765';
```

Expected row:

```text
210987654321098765 | 1
```

### TG-2. Bridge actor construction no longer 500s

There is no current `/api/v1/web/officer/me` endpoint. Use the officer queue endpoint that triggers `_build_officer_actor`:

```text
GET /api/v1/web/officer/applications?state=submitted,queued&scope_kind=chapter&scope_id=chapter-alpha
```

With spoofed Pomerium officer headers for Discord user `210987654321098765`, the response should be `200`, not `500`.

`GET /api/v1/me` remains useful only as a header/principal sanity check; it does not prove member aggregate resolution because it does not call `_build_officer_actor`.

### TG-3. Re-run e2e test 19

Re-run `infra/tests/e2e/tests/19-web-ui.sh`.

Expected outcome: the officer queue page renders the chapter-scoped application row and Playwright finds `[data-application-id="<id>"]`.

## 5. Anti-scope

Do not modify `resolve_or_create_real_discord_member`.

Do not modify the bridge's `_build_officer_actor`.

Do not change the `fetch_member_by_discord_id` query.

Do not add authority-grant aggregate heads in this BUG-7 fix.

Do not create synthetic activity actions or state changes for the seeded member.

Do not make `seed-authority-grants.mjs` create or repair `chapter-alpha`; that remains owned by `seed-chapter-fixture.mjs`.

## 6. Diff budget

Expected implementation budget: one file, roughly 50-90 changed lines.

Allowed changes:

- add guard CTEs and `inserted_member_head` to `seed-authority-grants.mjs`;
- adjust the final JSON/console output to expose fixture outcome details;
- keep existing environment variables, kubectl lookup, SQL literal helper, and grant idempotency behavior.

Not expected:

- new helper files;
- production code edits;
- migrations;
- broad e2e shell rewiring.
