# BUG-7 — Scope risk gate

**Verdict:** LOW

BUG-7 extends the existing e2e authority seed helper
(`infra/tests/e2e/lib/seed-authority-grants.mjs`) so it also inserts
the officer member's `aggregate_heads` row, plus a fail-closed guard
that the BUG-5 chapter fixture is already present when the helper is
invoked under `E2E_APPLICATION_SCOPE_KIND=chapter` /
`E2E_APPLICATION_SCOPE_ID=chapter-alpha`. The RCA
(`research/35-bug-7-officer-queue-chapter-rca.md` §"Root Cause")
establishes that the bug is a missing aggregate-head projection row
created by a direct-SQL e2e fixture: `fetch_member_by_discord_id`
joins `members` to `aggregate_heads`, the seeded member has no head,
so the officer bridge's `_build_officer_actor` raises
`MemberNotFoundError` and the queue endpoint 500s. The proposal locks
"Option a, extend `seed-authority-grants.mjs` to also insert the
officer member aggregate head" (§2 Q1) and explicitly rejects bridge
resilience (Option b — would weaken the aggregate-head-backed read
contract) and resolver repair (Option c — would have
`resolve_or_create_real_discord_member` backfill incomplete
direct-seeded projection rows). Diff budget is one file, ~50–90 lines
(§6).

## Gate checks

### 1. Only modifies `seed-authority-grants.mjs`

**PASS.** §3 "Modified file" is unambiguous: "Modify only
`infra/tests/e2e/lib/seed-authority-grants.mjs`." §6 reaffirms:
"Expected implementation budget: one file, roughly 50-90 changed
lines." The structural changes are all scoped to the existing single
SQL statement in `seed-authority-grants.mjs:69-123`: new CTEs (`seed`,
`resolved_member`, `checked_member`, `fixture_guard`,
`inserted_member_head`, `inserted_grant`) wrapped around the existing
member upsert + idempotent grant insert, and a richer final `SELECT`
to expose insert/no-op/abort outcomes (§3 "SQL shape"). No new helper
file is added — §6 explicitly disallows "new helper files." The
existing kubectl lookup and `sqlLiteral` helper are kept (§6 "keep
existing environment variables, kubectl lookup, SQL literal helper,
and grant idempotency behavior"). ✅

### 2. No production code changes

**PASS.** §3 "Substrate" enumerates the production surfaces that
remain untouched:

- "no migration changes;"
- "no changes to `services/api/app/services/members.py`;"
- "no changes to `services/api/app/api/v1/endpoints/web.py`;"
- "no changes to `services/api/app/repositories/members.py`."

§5 anti-scope reinforces with five separate prohibitions:

- "Do not modify `resolve_or_create_real_discord_member`."
- "Do not modify the bridge's `_build_officer_actor`."
- "Do not change the `fetch_member_by_discord_id` query."
- "Do not add authority-grant aggregate heads in this BUG-7 fix."
- "Do not create synthetic activity actions or state changes for the
  seeded member."

The fix is intentionally pushed to the fixture rather than to
production code precisely because, per RCA §"Root Cause", the seed
helper is producing an *incomplete* projection that production
repository reads correctly treat as nonexistent. Patching production
to tolerate seed-only states is the rejected Option b (§2 Q1). ✅

### 3. No GitOps changes

**PASS.** The proposal does not touch any path under
`gitops/**` or any kustomization manifest. The aggregate-head row is
created at e2e setup time via the same `kubectl exec` / `psql` path
that the helper already uses for `members` and `authority_grants`
(`seed-authority-grants.mjs:125-140`), not by reconciling a desired
state into the cluster. This is consistent with BUG-5's scope ruling
that e2e fixture data does not belong in GitOps. ✅

### 4. No new dependencies

**PASS.** §6 explicitly preserves the existing execution shape:
"keep existing environment variables, kubectl lookup, SQL literal
helper, and grant idempotency behavior." The change is a SQL-only
extension of the single statement already passed to `psql -v
ON_ERROR_STOP=1` through `kubectl exec`. No npm package, no new
binary, no new container image, no new env var. The new chapter
guard (§2 Q4) is implemented as an additional CTE/`SELECT 1` against
the already-present `chapters` and `aggregate_heads` tables — not via
a new Node module or external HTTP call. ✅

### 5. No schema changes

**PASS.** §3 "Substrate" states "no migration changes." §5 anti-scope
implicitly reinforces by forbidding any change to repository or
service code that would require a schema motion. The helper writes
into the existing `aggregate_heads` table (`aggregate_type`,
`aggregate_id`, `current_seq`, `latest_change_id`) using the same
column shape established in
`services/api/tests/chapter_selector_fixtures.py`,
`services/api/tests/public_intake_fixtures.py`, and BUG-5's
`seed-chapter-fixture.mjs` (§2 Q2 "Direct minimum-row fixtures already
use `current_seq = 1, latest_change_id = NULL` for materialized
entities"). No new column, no new table, no new index, no Alembic
revision. ✅

### 6. Doesn't touch members or applications service code

**PASS.** §3 enumerates the untouched service surfaces:

- `services/api/app/services/members.py` — unchanged.
- `services/api/app/repositories/members.py` — unchanged.
- `services/api/app/api/v1/endpoints/web.py` — unchanged.

§5 anti-scope adds three more pinning constraints around the
members/bridge surface specifically:

- `resolve_or_create_real_discord_member` (members service) — not
  modified.
- `_build_officer_actor` (web bridge) — not modified.
- `fetch_member_by_discord_id` (members repository query) — not
  modified.

Applications service code is not touched either: §1 establishes that
"Scope filtering and the SPA row selector are not the immediate
failure point" (the bridge fails before
`services/api/app/services/applications.py:list_applications` is
called), and §5's "Do not add authority-grant aggregate heads in this
BUG-7 fix" rules out the related authority-grant aggregate work that
would otherwise have crossed into the applications-listing
authorization path. The proposal is a fixture-only correction to
make production reads see the seeded member as it would see any
real member. ✅

## Findings

- **Idempotency posture is fail-closed.** §2 Q3 makes the helper
  fail-closed under partial drift: "Abort if an existing member head
  has an incompatible fixture shape: `aggregate_type = 'member'`,
  `aggregate_id = member.id::text`, but `current_seq <> 1` or
  `latest_change_id IS NOT NULL`." Critically, "The helper must not
  update an existing aggregate head to force it back to fixture
  shape. That would rewrite aggregate history and hide state drift."
  This mirrors BUG-5's fail-closed posture and prevents the helper
  from silently corrupting aggregate metadata in a long-lived dev
  cluster — keeping it safe for the per-test cluster bring-up that
  test 19 actually runs.
- **Cross-fixture dependency is asserted, not reconstructed.** §2 Q4
  adds a chapter-guard `SELECT` so that when the chapter-scoped
  invocation runs, the helper aborts with a clear fixture-dependency
  error if BUG-5's `chapter-alpha` row + head are missing or
  incompatible. The guard does *not* create or repair the chapter:
  §5 explicitly states "Do not make `seed-authority-grants.mjs`
  create or repair `chapter-alpha`; that remains owned by
  `seed-chapter-fixture.mjs`." This preserves single-ownership of the
  chapter fixture established by BUG-5 and turns this helper into a
  load-bearing tripwire if BUG-5's seed regresses or is invoked out
  of order — exactly the cross-coupling the gate wants visible.
- **Aggregate sequence shape is contract-driven, not invented.** §2
  Q2 locks `current_seq = 1` / `latest_change_id = NULL` and
  documents the precedent in three sibling fixtures
  (`chapter_selector_fixtures.py`, `public_intake_fixtures.py`,
  `seed-chapter-fixture.mjs`). It also explicitly rules out
  `current_seq = 0` ("represents the pre-create head inserted inside
  `mutate_entity` before the accepted state change") and synthetic
  `activity_actions` / `activity_state_changes` rows. This pins the
  fixture to the same minimum-row shape the unit tests already use,
  so the seeded member is observable to `fetch_member_by_discord_id`
  exactly the way a real materialized member is.
- **Scope of aggregate-head insertion is intentionally narrow.** §2
  Q5 confirms that only the *member* aggregate head is needed:
  "`fetch_member_by_discord_id` … joins `members` to
  `aggregate_heads`. It does not join `activity_actions` or
  `activity_state_changes`," and "`list_grants_for_grantee` delegates
  to `list_grants`, and that repository query reads raw
  `authority_grants` rows without joining `aggregate_heads`."
  Authority-grant heads are explicitly out of scope (§5) and are not
  required to unblock the queue. This keeps the diff at one head
  insert in one CTE rather than spreading across grants/actions/state
  changes.
- **Fix is at the correct ownership boundary.** RCA §"Intervention
  Points, Not Fix Proposals" enumerated five candidate locations; §2
  Q1 picks the e2e fixture path — the only one that matches the
  failure cause (a direct-SQL fixture creating an incomplete
  projection). Patching the resolver, the bridge, or the repository
  query would all weaken production invariants to accommodate a
  test-only data shape; instead, the fixture is brought into line
  with what production reads expect.
- **Test plan distinguishes layers.** §4 TG-1 verifies the
  `members` ↔ `aggregate_heads` join directly via SQL; TG-2 verifies
  the bridge actor construction by hitting
  `/api/v1/web/officer/applications` (which calls
  `_build_officer_actor`) rather than `/api/v1/me` (which doesn't);
  TG-3 re-runs `infra/tests/e2e/tests/19-web-ui.sh` end-to-end. This
  separation matches RCA §7's "API logs for the queue call show
  `_build_officer_actor` fails before list filtering" finding and
  prevents a green `/api/v1/me` from masking a still-broken bridge.
- **Diff budget headroom.** §6 caps the implementation at 50–90 lines
  in one file. The change is structurally CTE additions
  (`fixture_guard`, `inserted_member_head`) plus a richer final
  `SELECT` against the existing `seed-authority-grants.mjs:69-123`
  body, which fits comfortably in that envelope.

## Verdict

**LOW.** All six gate checks pass. The proposal is a single-file,
e2e-only fixture extension that adds the missing
`aggregate_heads` row for the seeded officer member and a
fail-closed cross-fixture guard for the chapter-scoped invocation,
without touching any production service, repository, endpoint,
schema, GitOps manifest, or external dependency. The five
anti-scope clauses (§5) pin out every escape hatch — bridge
resilience, resolver repair, query rewrite, authority-grant
aggregate heads, and chapter-fixture creation — that the RCA's
candidate-intervention list would otherwise have invited. Cleared
for shortcut gate.

SCOPE_DONE: plans/risk/bug-7-scope.md
