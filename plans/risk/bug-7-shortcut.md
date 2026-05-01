# BUG-7 — Shortcut risk gate (officer member aggregate head in e2e seed)

**Verdict:** LOW

Source: `proposals/22-bug-7-officer-aggregate-head.md`,
`research/35-bug-7-officer-queue-chapter-rca.md`,
`infra/tests/e2e/lib/seed-authority-grants.mjs`,
`services/api/app/repositories/members.py`,
`infra/tests/e2e/lib/seed-chapter-fixture.mjs`.

## C1 — Real INSERT with proper FKs (not just bumps a counter)

**Pass.**

The proposal specifies a real `INSERT INTO aggregate_heads (...)` of the four
schema columns named in the existing reference helper
(`infra/tests/e2e/lib/seed-chapter-fixture.mjs:236-240`):

```sql
INSERT INTO aggregate_heads (
  aggregate_type,
  aggregate_id,
  current_seq,
  latest_change_id
)
VALUES ('member', <member.id::text>, 1, NULL)
```

(proposal lines 30-40, restated in substrate at lines 112-113).

The `aggregate_id` is bound to the materialized member identity from the
`members` insert via `checked_member.id::text` — that is the same correlation
that makes `_MEMBER_SELECT` resolve the row in
`services/api/app/repositories/members.py:10-23`:

```sql
JOIN aggregate_heads AS h
  ON h.aggregate_type = 'member'
 AND h.aggregate_id = m.id::text
```

So the inserted head is keyed on the live members PK as text — a real
projection link, not a sequence bump on a counter row. `current_seq = 1` is
the version the read query exposes (`h.current_seq AS version`), not a
mutation of an existing row's counter; `latest_change_id = NULL` is the
fixture-shape invariant that `seed-chapter-fixture.mjs:170-172` already
fail-closes against ("incompatible sequence or latest_change_id").

Q5 (proposal lines 86-91) also rejects faking the dependency through
`activity_actions` / `activity_state_changes` — the read path doesn't join
those, so synthesizing them would have been the "look like real history"
shortcut. Choosing the head row alone is the minimum truthful insert, not a
counter bump.

## C2 — `aggregate_heads` INSERT correctly ordered AFTER the members INSERT

**Pass.**

The proposal pins the CTE chain at lines 105-114:

> `seed` → `resolved_member` → `checked_member` → `fixture_guard` →
> `inserted_member_head` → `inserted_grant`

`inserted_member_head` selects `checked_member.id::text` for `aggregate_id`,
and `checked_member` is derived from `resolved_member` (the members
INSERT … RETURNING) per the existing helper at
`infra/tests/e2e/lib/seed-authority-grants.mjs:70-82`:

```sql
resolved_member AS (
  INSERT INTO members (...)
    ON CONFLICT (discord_user_id) DO UPDATE
      SET discord_user_id = EXCLUDED.discord_user_id
  RETURNING id, kind
),
checked_member AS (
  SELECT id, kind FROM resolved_member
  UNION ALL
  SELECT id, kind FROM members WHERE discord_user_id = ... LIMIT 1
)
```

PostgreSQL CTEs execute in the same snapshot, but rows produced by an
upstream `INSERT … RETURNING` are visible to downstream CTEs that reference
that CTE's name. Because `inserted_member_head` references `checked_member`
(which references `resolved_member`), the data dependency forces the head
insert to consume the freshly materialized member id. This is the same
pattern `seed-chapter-fixture.mjs:233-256` already uses to insert a chapter
head only after the chapter row is produced upstream.

The existing `inserted_grant` (`seed-authority-grants.mjs:83-119`) also
hangs off `checked_member`, so adding `inserted_member_head` as a sibling
that reads from `checked_member` keeps the same shape. Both siblings see
the member; the head insert cannot run against a missing or stale member
row.

The "DO UPDATE … SET discord_user_id = EXCLUDED.discord_user_id" no-op
update in `resolved_member` is what makes the row visible via RETURNING on
re-runs even when the row already existed — without it, an existing-row
re-run would skip RETURNING and `checked_member`'s `UNION ALL … LIMIT 1`
fallback would carry the existing id forward. Either path lands a real
member id in `inserted_member_head`. No ordering hole.

## C3 — Idempotency check is real (queries DB, doesn't just count)

**Pass.**

Q3 (proposal lines 50-63) defines idempotency as field-shape predicates,
not a count:

> - Insert the member aggregate head only if missing.
> - Treat an existing compatible head as a no-op.
> - Abort if an existing member head has an incompatible fixture shape:
>   `aggregate_type = 'member'`, `aggregate_id = member.id::text`, but
>   `current_seq <> 1` or `latest_change_id IS NOT NULL`.

That maps directly onto two CTE shapes already proven in
`seed-chapter-fixture.mjs`:

1. **Drift guard via field comparison** (`seed-chapter-fixture.mjs:162-173`):

   ```sql
   SELECT 1
   FROM aggregate_heads h
   WHERE h.aggregate_type = 'chapter'
     AND h.aggregate_id = s.chapter_id
     AND (
       h.current_seq IS DISTINCT FROM 1
       OR h.latest_change_id IS NOT NULL
     )
   ```

   Same predicate shape applies to `aggregate_type='member'` for BUG-7.
   This is a real query against `aggregate_heads`, not `count(*) > 0`.

2. **Conditional insert via NOT EXISTS** (`seed-chapter-fixture.mjs:248-254`):

   ```sql
   WHERE NOT EXISTS (
     SELECT 1
     FROM aggregate_heads h
     WHERE h.aggregate_type = 'chapter'
       AND h.aggregate_id = s.chapter_id
   )
   ```

   The proposal's `inserted_member_head` will mirror this for
   `('member', checked_member.id::text)`.

Q3 also explicitly forbids the "force-rewrite to fixture shape" shortcut:

> The helper must not update an existing aggregate head to force it back to
> fixture shape. That would rewrite aggregate history and hide state drift.

That rules out an `INSERT … ON CONFLICT DO UPDATE SET current_seq = 1,
latest_change_id = NULL` shortcut that would silently paper over real
events committed by `mutate_entity` between fixture runs.

The proposal's Q3 final-`SELECT` requirement ("return a JSON summary that
includes whether the member row, member head, and authority grant were
inserted or already present") makes the no-op vs insert distinction
auditable — a count-based check could not produce that three-state report.

## C4 — No "TODO: also create activity_actions row later" stub

**Pass.**

Q5 (proposal lines 86-91) addresses activity rows head-on and rejects them
on substantive grounds:

> The failing lookup is `fetch_member_by_discord_id`, whose query joins
> `members` to `aggregate_heads` and selects `h.current_seq AS version`.
> It does not join `activity_actions` or `activity_state_changes`.

Verified against `services/api/app/repositories/members.py:10-23` —
`_MEMBER_SELECT` joins `aggregate_heads` only. A synthetic
`activity_actions` row would be ceremony with no read consumer in the
failing path.

Anti-scope (proposal lines 162-174) hard-blocks the stub variant:

> Do not create synthetic activity actions or state changes for the seeded
> member.
> Do not add authority-grant aggregate heads in this BUG-7 fix.

The authority-grant head exclusion is also justified by the RCA, not
deferred:

> `list_grants_for_grantee` delegates to `list_grants`, and that
> repository query reads raw `authority_grants` rows without joining
> `aggregate_heads`. Therefore this proposal only adds the missing member
> head and the chapter fixture dependency guard. Authority-grant aggregate
> heads remain outside this fix.

That's a scope decision backed by the read-path query shape, not "we'll
add them later." There is no `TODO` in the proposal, and the diff budget
(lines 178-192) is tight enough — "one file, roughly 50-90 changed lines"
— that an "add it later" stub would have to live somewhere visible; it
does not.

The chapter fixture guard (Q4, lines 64-83) also avoids the stub trap by
*asserting on existing fixture state* rather than creating it:

> When `E2E_APPLICATION_SCOPE_KIND=chapter` and
> `E2E_APPLICATION_SCOPE_ID=chapter-alpha`, `seed-authority-grants.mjs`
> should assert that BUG-5's chapter fixture is already present … If that
> guard fails, abort with a clear fixture-dependency error rather than
> creating the chapter or silently inserting chapter-scoped authority
> against a missing/incomplete chapter fixture.

That is the inverse of a stub: it forces upstream completeness instead of
papering over it.

## C5 — No production fallback that hides this kind of fixture incompleteness in the future

**Pass.**

Q1 (proposal lines 14-25) explicitly rejects both production-side fallback
options:

> Rejected:
> - Option b, bridge resilience: this would make `_build_officer_actor`
>   compensate for impossible production state and weaken the
>   aggregate-head-backed member read contract.
> - Option c, resolver repair: `resolve_or_create_real_discord_member`
>   should continue to create complete members through `mutate_entity`; it
>   should not backfill incomplete direct-seeded projection rows.

The fix is bounded to `infra/tests/e2e/lib/seed-authority-grants.mjs` (Q1
final pick, plus Substrate at lines 96-97: "Modify only
`infra/tests/e2e/lib/seed-authority-grants.mjs`").

Anti-scope (proposal lines 162-174) reinforces by enumerating production
files that must not change:

> Do not modify `resolve_or_create_real_discord_member`.
> Do not modify the bridge's `_build_officer_actor`.
> Do not change the `fetch_member_by_discord_id` query.

This matters because the production read contract — "a `members` row is
visible to the bridge only if its `aggregate_heads` row exists" — is
exactly the invariant that surfaced the fixture bug as a 500. Weakening
the read query (e.g. `LEFT JOIN aggregate_heads` with a fallback version
of 0) would let any incomplete projection row produced by direct SQL
silently flow through the bridge in the future, hiding the same class of
bug for other entities (chapters, grants, applications) that also depend
on aggregate heads as the visibility gate.

The Substrate's "No production code changes" block (proposal lines 116-121)
itemizes the production files left untouched:

> - no migration changes;
> - no changes to `services/api/app/services/members.py`;
> - no changes to `services/api/app/api/v1/endpoints/web.py`;
> - no changes to `services/api/app/repositories/members.py`.

That keeps the read-path contract — and the exception path
(`DiscordMemberRaceLost` → `MemberNotFoundError` → 500) — unchanged so the
*next* incomplete fixture surfaces the same way, immediately.

## Findings worth carrying into implementation

Not blockers — verdict is LOW — but the implementation phase should
preserve:

1. **`aggregate_id` cast must be `::text`.** Q2 (line 37) and the
   repository read at `services/api/app/repositories/members.py:22`
   (`AND h.aggregate_id = m.id::text`) both pin the cast. `members.id` is
   `uuid`; `aggregate_heads.aggregate_id` is `text`. Inserting the raw uuid
   without `::text` will fail the type check, and using a string literal of
   the uuid (without grounding it in `checked_member.id`) would skip the
   ordering dependency in C2. Always derive from `checked_member.id::text`.

2. **Drift guard must check `aggregate_id = checked_member.id::text`, not
   just discord_user_id.** Q3's drift predicate is keyed on the member's
   uuid-derived aggregate id. A guard keyed on `discord_user_id` instead
   would miss the case where a stale `aggregate_heads` row points at a
   *different* members row (e.g. after a manual reseed) — the read path
   would then resolve the wrong member. Pin the guard to the row produced
   by `checked_member` for the same run.

3. **Reuse the `seed-chapter-fixture.mjs` head-insert shape verbatim.** That
   helper already names the four columns and uses `NOT EXISTS` against
   `(aggregate_type, aggregate_id)` as the absence check
   (`infra/tests/e2e/lib/seed-chapter-fixture.mjs:236-256`). Mirror those
   column names and predicate exactly so the two e2e fixtures stay
   structurally identical and a future reader can read one to understand
   the other.

4. **Single `psql` invocation, single transaction.** Substrate (lines 102-114)
   keeps "one SQL statement executed through the existing kubectl/psql
   path." Splitting the head insert into a second `kubectl exec` would
   reintroduce the partial-state failure mode the C2 ordering rules out:
   the members insert could succeed and the head insert could fail in a
   later call, leaving exactly the broken state BUG-7 was about.

5. **JSON summary should distinguish member-head outcome from grant
   outcome.** Q3's "JSON summary that includes whether the member row,
   member head, and authority grant were inserted or already present" is
   what makes the C3 idempotency claim auditable from CI logs. The current
   helper only prints `member_id`, `discord_user_id`, `scope_*`, and
   `permissions` (`seed-authority-grants.mjs:160-168`). Add explicit
   per-row `inserted | already_present | aborted_drift` fields so a CI
   re-run can assert "no-op on second run" directly from stdout instead of
   re-querying the DB.

6. **TG-2 endpoint is the right canary, not `/api/v1/me`.** RCA section 5
   (`research/35-bug-7-officer-queue-chapter-rca.md:90-99`) shows
   `/api/v1/me` returned 200 even with the broken fixture because that
   endpoint never calls `_build_officer_actor`. The proposal's TG-2 (lines
   144-154) correctly uses
   `GET /api/v1/web/officer/applications?state=submitted,queued&scope_kind=chapter&scope_id=chapter-alpha`,
   which does invoke `_build_officer_actor` and so does prove the fix. Do
   not let an implementer "verify" the fix solely via `/api/v1/me`.

7. **Chapter guard must run only when scope is chapter / chapter-alpha.**
   Q4 (lines 64-83) is explicit that the chapter-fixture-presence guard
   gates only the chapter-scoped invocation. A guard that always runs
   would force every default-global seed to depend on
   `seed-chapter-fixture.mjs` having been run first, which is not the
   pre-BUG-7 contract and would break callers that don't need chapter-alpha
   at all.

## Verdict

LOW. No shortcuts. The proposal:

- Inserts a real `aggregate_heads` row keyed on the live `members.id::text`
  with the same four columns the existing chapter helper uses, not a
  counter bump and not a synthetic activity row that the read path doesn't
  consume.
- Orders the head insert after the member insert via CTE data dependency
  (`inserted_member_head` reads `checked_member` which derives from
  `resolved_member`'s `INSERT … RETURNING`), the same pattern
  `seed-chapter-fixture.mjs` already uses for chapters.
- Defines idempotency as field-shape predicates (`current_seq = 1`,
  `latest_change_id IS NULL`, `aggregate_id = member.id::text`) with a
  fail-closed abort on drift and a `NOT EXISTS` insert guard, mirroring
  the chapter helper, and forbids the force-rewrite shortcut that would
  hide history.
- Rejects synthetic `activity_actions` / `activity_state_changes` and
  authority-grant aggregate heads on substantive read-path grounds (the
  failing query joins only `aggregate_heads`; `list_grants` doesn't join
  `aggregate_heads`), not as deferred TODOs.
- Bounds the change to the e2e helper and itemizes the production files
  left untouched — bridge, resolver, repository — preserving the
  aggregate-head-backed read contract that surfaced this bug as a 500 so
  the next incomplete projection fixture surfaces the same way.

SHORTCUT_DONE: plans/risk/bug-7-shortcut.md
