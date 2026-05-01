# BUG-7 — Supported-surface risk gate

**Verdict:** LOW

BUG-7 (officer queue 500s for chapter-scoped applications because the
e2e authority seed inserts a raw `members` row without a corresponding
`aggregate_heads` row, so `fetch_member_by_discord_id` cannot resolve
the seeded officer and `_build_officer_actor` raises
`MemberNotFoundError`) is repaired by adding one CTE and a
fixture-shape guard inside the existing helper at
`infra/tests/e2e/lib/seed-authority-grants.mjs` (proposal §3, §6). The
fix lives entirely under `infra/tests/e2e/lib/**` and writes only to
the existing `members`, `authority_grants`, and `aggregate_heads`
tables already created by migrations `wu-002`, `wu-003a`, `wu-011`,
and `wu-043`. No production service code, no public API behavior, no
schema, no env var, no GitOps Job, and no Pomerium/Authentik resource
is touched (proposal §5 anti-scope explicitly forbids each of these).

## Surfaces touched

### 1. Public API surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/v1/web/officer/applications` (`services/api/app/api/v1/endpoints/web.py:172-196`) | currently 500s in the local e2e cluster because `_build_officer_actor` cannot resolve the seeded Discord member (RCA §5, §7) | unchanged route, query parameters, response shape, and authorization path; the only delta is that the seeded officer member is now visible to the existing `fetch_member_by_discord_id` query because its `aggregate_heads` row exists | none — proposal §5: "Do not modify `_build_officer_actor`", "Do not change the `fetch_member_by_discord_id` query" |
| `GET /api/v1/me` (`services/api/app/api/v1/endpoints/web.py`) | already returns 200 with `groups=["officers"]` and `discord_user_id` (RCA §7) | unchanged — does not call `_build_officer_actor`, so it is not affected by the fix or the bug | none |
| Officer member resolution (`services/api/app/services/members.py:resolve_or_create_real_discord_member`) | as defined today | unchanged — proposal §5 anti-scope: "Do not modify `resolve_or_create_real_discord_member`" | none |
| Officer actor construction (`services/api/app/api/v1/endpoints/web.py:87-141:_build_officer_actor`) | as defined today | unchanged — proposal §5: "Do not modify the bridge's `_build_officer_actor`" | none |
| Member repository (`services/api/app/repositories/members.py:fetch_member_by_discord_id`) | as defined today (joins `members` to `aggregate_heads`, selects `h.current_seq AS version`) | unchanged — the fix produces the matching `aggregate_heads` row that this query already requires; the query itself, its joins, and its projection are untouched | none — proposal §5: "Do not change the `fetch_member_by_discord_id` query" |
| Application list service (`services/api/app/services/applications.py:list_applications`) | authorizes via `APPLICATION_READ_PERMISSIONS` against authority grants (RCA §6); reads `authority_grants` directly without joining `aggregate_heads` (RCA §2) | unchanged — proposal §2 Q5 confirms authority-grant aggregate heads are not needed for this fix; the seeded grant row remains shape-identical to today | none — proposal §5: "Do not add authority-grant aggregate heads in this BUG-7 fix" |

Risk on §1: **none** — gate criterion 1 (no public API change) holds.
The fix introduces no new endpoint, no new field, no new query, and
no behavior change in any existing endpoint. The 500→200 transition
on the officer queue endpoint is a side effect of restoring the
fixture invariant that production code already assumes
(`fetch_member_by_discord_id` requires a matching aggregate head),
not a behavioral change in the production code path.

### 2. Database tables touched — only existing tables, no schema change

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `members` | created by `migrations/versions/wu-011_members.py` (`id` UUID PK, `discord_user_id` TEXT NOT NULL UNIQUE, `joined_at` TIMESTAMPTZ NOT NULL, `status` TEXT NOT NULL with CHECK `status IN ('active','suspended','departed')`); `kind` TEXT NOT NULL with CHECK `kind IN ('discord','public_intake')` added by `wu-043` | unchanged behavior from today — the helper still resolves or creates exactly one row for the officer Discord user via the existing `INSERT … ON CONFLICT (discord_user_id) DO UPDATE … RETURNING id, kind` block (`seed-authority-grants.mjs:69-82`); no new columns, no new values | none — already in use today; the fix only adds idempotency guarding around the existing insert |
| `authority_grants` | unchanged today (`grantee_id` TEXT, `scope_kind`, `scope_id`, `permissions` JSONB, lifecycle nullables) | unchanged shape — proposal §3 "preserve the existing idempotent grant insert behavior" | none — already in use today; no new columns, no new values |
| `aggregate_heads` | post-`wu-003a` schema: `aggregate_type TEXT NOT NULL`, `aggregate_id TEXT NOT NULL`, `current_seq BIGINT NOT NULL DEFAULT 0`, `latest_change_id BIGINT NULL FK→activity_state_changes(id) ON DELETE SET NULL`, PK `(aggregate_type, aggregate_id)`; no check constraints on the relationship between `current_seq` and `latest_change_id` | one fixture row inserted: `('member', checked_member.id::text, 1, NULL)` — identical shape to the existing unit-test fixture in `services/api/tests/public_intake_fixtures.py:129-137` (`INSERT INTO aggregate_heads (aggregate_type, aggregate_id, current_seq, latest_change_id) VALUES ('member', %s, 1, NULL)`), and consistent with BUG-5's `seed-chapter-fixture.mjs` (`('chapter', s.chapter_id, 1, NULL)`) and `wu-045_application_public_submit_notifications.py:124-134` (`('notification_rule', '<id>', 1, NULL)`) | none — schema unchanged; row references the `members.id` value resolved in the same transaction CTE; idempotent per proposal §2 Q3, with fail-closed abort if a pre-existing head has incompatible shape (`current_seq <> 1` or `latest_change_id IS NOT NULL`) |

Risk on §2: **none** — gate criterion 2 (uses existing
`aggregate_heads` table — no schema changes) holds. The fixture
inserts the member row first via the existing `resolved_member` CTE,
then the new `inserted_member_head` CTE references the resolved
member's `id::text`, all inside the same single SQL statement
executed through the existing kubectl/psql exec path
(`seed-authority-grants.mjs:125-140`). Because
`aggregate_heads.aggregate_id` is intentionally a generic `TEXT`
column without a foreign key to source tables (post-WU-003a
widening), no FK constraint links it to `members.id` — but the value
the helper writes is the live `members.id` returned from the same
transaction's `resolved_member` / `checked_member` CTE, so the row
points at a real, just-inserted `members` row.

### 3. Database schema / migrations — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head (`migrations/versions/...`) | current head | unchanged — proposal §5 anti-scope: implicit via §3 "Modify only `infra/tests/e2e/lib/seed-authority-grants.mjs`"; §6 budget: "Not expected: migrations" | none |
| Column definitions on `members`, `authority_grants`, `aggregate_heads` | as defined by `wu-002`, `wu-003a`, `wu-011`, `wu-043`, and authority-grants migrations | unchanged — proposal writes data only, no DDL | none |
| Constraints (`members.kind` CHECK, `members.status` CHECK, `members.discord_user_id` UNIQUE, `aggregate_heads` composite PK, `aggregate_heads.latest_change_id` FK to `activity_state_changes`) | as defined | unchanged; satisfied by the seeded row values listed above (`kind='discord'`, `current_seq=1`, `latest_change_id=NULL`) | none |

Risk on §3: **none** — gate criterion 4 (no DB migrations) holds.

### 4. Environment variables — none added

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `KUBECONFIG_PATH` / `KUBECONFIG` | already required and read by `seed-authority-grants.mjs:7-18` | reused verbatim — no change | none — pre-existing |
| `E2E_OFFICER_DISCORD_USER_ID` | already provided at `seed-authority-grants.mjs:12`, falls back to `webContract.auth.identity.discord_user_id` | reused verbatim | none — pre-existing |
| `E2E_APPLICATION_SCOPE_KIND` / `E2E_APPLICATION_SCOPE_ID` | already provided at `seed-authority-grants.mjs:13-14` | reused verbatim; the new chapter-fixture-dependency guard is gated by these existing variables (proposal §2 Q4: "When `E2E_APPLICATION_SCOPE_KIND=chapter` and `E2E_APPLICATION_SCOPE_ID=chapter-alpha`") | none — pre-existing |
| API/web service env (`VITE_API_BASE_URL`, etc.) | as today | unchanged | none |

Risk on §4: **none** — gate criterion 3 (no env vars) holds. Proposal
§6 budget: "keep existing environment variables".

### 5. GitOps surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/applications/server-manager/kustomization.yaml` | as today | unchanged — proposal §3 limits the modified set to `infra/tests/e2e/lib/seed-authority-grants.mjs` only | none |
| `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` and other seeds | as today | unchanged — the officer fixture is owned by e2e setup, not GitOps bootstrap | none |
| Local cluster bring-up (`infra/scripts/bring-up-local-channel.sh`) | as today | unchanged — no shell-script edits required (proposal §3 modifies only the helper file; the existing `19-web-ui.sh` invocations at lines 280-287 already call this helper without changes) | none |

Risk on §5: **none** — gate criterion 5 (no GitOps changes) holds.

### 6. Pomerium / Authentik — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/auth/pomerium/**` | as checked in | unchanged | none |
| `gitops/channels/local/auth/authentik/**` | as checked in | unchanged | none |
| OAuth round-trip / route allowlist / claim headers | unchanged | unchanged | none — `/api/v1/me` already returns 200 with the spoofed officer headers (RCA §7), proving Pomerium/Authentik configuration is not the failure point and is not touched by the fix |

Risk on §6: **none** — gate criterion 5 (no Pomerium/Authentik
changes) holds. The fix is below the auth boundary; Pomerium claim
headers continue to be parsed exactly as today.

### 7. Foreign-key and column-constraint verification

| Reference | Source | Target | Verification |
|---|---|---|---|
| `aggregate_heads.aggregate_type` | proposal §2 Q2 / §3 | TEXT NOT NULL, no FK, no CHECK | satisfied: literal `'member'` matches the discriminator value used by `fetch_member_by_discord_id` (`h.aggregate_type = 'member'`) and by the existing unit fixture at `public_intake_fixtures.py:129-137` |
| `aggregate_heads.aggregate_id` | proposal §2 Q2 / §3 | TEXT NOT NULL, no FK to `members.id` (intentionally generic post-WU-003a) | satisfied: helper writes `checked_member.id::text` resolved from the same transaction's `resolved_member` CTE; even though there is no DB-level FK, the value points at a real `members.id` because the row is inserted (or already present) in the same statement |
| `aggregate_heads.current_seq` | proposal §2 Q2 | BIGINT NOT NULL DEFAULT 0 | satisfied: literal `1` matches the existing fixture pattern (`public_intake_fixtures.py`, `chapter_selector_fixtures.py`, `seed-chapter-fixture.mjs`, `wu-045_…`); proposal §2 Q2 explicitly justifies `1` over `0` ("`current_seq = 0` represents the pre-create head inserted inside `mutate_entity` before the accepted state change. A direct-seeded existing member projection should be visible as version 1.") |
| `aggregate_heads.latest_change_id` | proposal §2 Q2 | BIGINT NULL, FK→`activity_state_changes(id)` ON DELETE SET NULL | satisfied: literal `NULL` is permitted by the column definition and trivially satisfies the FK; consistent with existing fixtures that do not synthesize an `activity_state_changes` row |
| `aggregate_heads` composite PK `(aggregate_type, aggregate_id)` | proposal §2 Q3 / §3 | unique combination | satisfied: helper inserts only when absent (`inserted_member_head` is a `NOT EXISTS`-guarded CTE); on re-run, an existing compatible row is a no-op; an existing incompatible row aborts via the `fixture_guard` CTE rather than overwriting |
| `members.kind` | proposal §2 Q3 / §3 (`fixture_guard` requires `kind = 'discord'`) | CHECK `kind IN ('discord','public_intake')` (`wu-043`) | satisfied: helper insert at `seed-authority-grants.mjs:71-72` already writes `'discord'` today; the new fixture-shape guard explicitly fails the run if the resolved row is not `kind='discord'` |
| Chapter fixture dependency (proposal §2 Q4) | `aggregate_heads('chapter', 'chapter-alpha', 1, NULL)` from BUG-5 `seed-chapter-fixture.mjs` | precondition for the chapter-scoped invocation | satisfied (or fail-closed): when `E2E_APPLICATION_SCOPE_KIND=chapter` and `E2E_APPLICATION_SCOPE_ID=chapter-alpha`, the helper asserts the BUG-5 chapter row + head are present and aborts with a clear fixture-dependency error otherwise; helper does not create or repair `chapter-alpha` (proposal §5: "Do not make `seed-authority-grants.mjs` create or repair `chapter-alpha`; that remains owned by `seed-chapter-fixture.mjs`") |

Risk on §7: **none** — gate criterion 6 (FK references valid, column
constraints satisfied) holds. The proposed insert
`('member', checked_member.id::text, 1, NULL)` is shape-compatible
with the current `aggregate_heads` schema, matches the established
fixture pattern across `services/api/tests/public_intake_fixtures.py`,
`services/api/tests/chapter_selector_fixtures.py`,
`infra/tests/e2e/lib/seed-chapter-fixture.mjs`, and
`migrations/versions/wu-045_application_public_submit_notifications.py`,
and is gated by an idempotent `NOT EXISTS` insert plus a fail-closed
abort guard for any pre-existing row whose shape diverges. The
chapter-scoped invocation additionally guards against the BUG-5
chapter fixture being absent or incomplete, which prevents the helper
from silently producing chapter-scoped authority for a chapter that
does not exist.

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS |
| 2. Existing `aggregate_heads` table — no schema changes | PASS |
| 3. No env vars | PASS |
| 4. No DB migrations | PASS |
| 5. No GitOps / Pomerium / Authentik changes | PASS |
| 6. Seeded row has valid foreign-key references and matches column constraints | PASS |

## Findings

1. **No public API surface is altered.** Proposal §3 limits all
   changes to `infra/tests/e2e/lib/seed-authority-grants.mjs`; §5
   anti-scope explicitly forbids editing
   `services/api/app/services/members.py`,
   `services/api/app/api/v1/endpoints/web.py`, and
   `services/api/app/repositories/members.py`. The 500→200 outcome on
   `GET /api/v1/web/officer/applications` is a side effect of
   restoring the fixture invariant that production code already
   assumes, not a behavioral change in production code.

2. **Only existing tables are written, with no schema change.** The
   helper inserts into `members`, `authority_grants`, and
   `aggregate_heads` — all three tables already exist and are
   already written by this helper or by parallel fixture code.
   The new row in `aggregate_heads` matches the shape used by
   `services/api/tests/public_intake_fixtures.py:129-137`,
   `services/api/tests/chapter_selector_fixtures.py:70-81`,
   `infra/tests/e2e/lib/seed-chapter-fixture.mjs`, and
   `migrations/versions/wu-045_…`.

3. **No new environment variables.** All four variables consumed by
   the helper (`KUBECONFIG_PATH` / `KUBECONFIG`,
   `E2E_OFFICER_DISCORD_USER_ID`, `E2E_APPLICATION_SCOPE_KIND`,
   `E2E_APPLICATION_SCOPE_ID`) are pre-existing on this helper's
   execution surface.

4. **No DB migrations.** Proposal §3 / §5 / §6 are explicit; the
   `aggregate_heads` schema (TEXT `aggregate_id` post-WU-003a) and
   the `members` schema (with `kind` post-WU-043) are sufficient for
   the proposed insert as-is.

5. **No GitOps / Pomerium / Authentik changes.** The fix is a single
   helper-file edit; no manifest, no Job, no auth resource is
   touched. `/api/v1/me` already returns 200 with spoofed officer
   headers (RCA §7), which is independent evidence that auth
   configuration is not the failure point and is not on the change
   surface.

6. **Seeded row satisfies all column constraints.** `aggregate_type`
   is `'member'` (TEXT, NOT NULL, no FK or CHECK); `aggregate_id` is
   `checked_member.id::text` resolved from the same transaction
   (TEXT, NOT NULL, no FK to `members.id` by design — the column is
   intentionally generic post-WU-003a, but the value points at a
   real `members` row written in the same statement); `current_seq`
   is `1` (BIGINT, NOT NULL, matches the existing fixture pattern);
   `latest_change_id` is `NULL` (BIGINT, nullable, FK to
   `activity_state_changes(id)` trivially satisfied). The composite
   PK `(aggregate_type, aggregate_id)` is respected via the
   `NOT EXISTS`-guarded insert with a fail-closed abort for any
   pre-existing incompatible row, and the new chapter-fixture-
   dependency guard prevents producing chapter-scoped authority
   when the BUG-5 chapter row is missing or incomplete.

## Out-of-scope items intentionally not addressed

- Authority-grant aggregate heads (proposal §2 Q5, §5 anti-scope:
  "Do not add authority-grant aggregate heads in this BUG-7 fix").
- Synthetic `activity_actions` / `activity_state_changes` rows for
  the seeded member (proposal §2 Q2, §5).
- Production member resolution, bridge actor construction, or the
  `fetch_member_by_discord_id` query (proposal §5 anti-scope).
- Repair or creation of `chapter-alpha` from this helper (proposal
  §5: "that remains owned by `seed-chapter-fixture.mjs`"; the helper
  only asserts the BUG-5 fixture is present and aborts otherwise).
- The SPA queue page, queue scope query parameters, or the
  `services/web/src/api/client.ts` request shape — RCA §2 / §4
  identify these as not the immediate failure point and proposal §5
  scopes them out of the BUG-7 fix.

## Verdict

**LOW** — the fix is an e2e-only fixture correction that adds one
guarded `aggregate_heads('member', member.id::text, 1, NULL)` insert
inside the existing `seed-authority-grants.mjs` SQL statement, plus a
fail-closed shape guard for incompatible pre-existing heads and a
chapter-fixture-dependency assertion for the chapter-scoped
invocation. It changes no public API, no schema, no env var, no
GitOps manifest, and no auth resource; the seeded row is
shape-identical to four existing fixture and migration patterns
already in this repo and is gated to abort rather than overwrite on
any pre-existing incompatible state.

SUPPORTED_SURFACE_DONE: plans/risk/bug-7-supported-surface.md
