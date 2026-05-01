# Risk audit — BUG-5 local e2e chapter fixture

Inputs:
- Proposal: `proposals/21-bug-5-chapter-fixture.md`
- RCA: `research/34-bug-5-chapter-fixture-rca.md`
- Substrate: `infra/tests/e2e/lib/seed-chapter-fixture.mjs` (new),
  `infra/tests/e2e/tests/19-web-ui.sh` (extend invocation block).

## Verdict

**Risk level: LOW.** APPROVED — proceed to implementation, with one
non-blocking refinement to TG-1 acceptance noted in F-6.

The proposal directly attacks the RCA's named root cause (zero `chapters`
rows in the local cluster, with the public chapter endpoint reading only
`state = 'active'`) by porting the same minimum-row shape that already
proves the contract in `services/api/tests/chapter_selector_fixtures.py`
(template → chapter → aggregate_heads). It reuses the established
e2e helper pattern (`seed-authority-grants.mjs` execution model and
`sqlLiteral` quoting convention), keeps fixture identity hardcoded to
match `contract.json`, isolates writes to fixture-owned rows, and
mirrors `seed-public-intake-form.yaml`'s fail-closed CTE shape so drift
aborts loudly. Anti-scope forbids the obvious wrong directions
(promoting the fixture into GitOps, extending the authority helper,
adding admin chapter create paths, touching `/api/public/chapters`
behavior, or migrations).

## Findings

### F-1 Helper inserts all three FK-required rows — PASS

Per RCA "Foreign key / template dependency" (lines 204–216), the schema
requires `chapter_templates` first (`wu-007a`, `wu-018`), then
`chapters.template_id` referencing it (`wu-019_chapter_lifecycle.py:21,
46-50`), then an `aggregate_heads` row for the chapter aggregate so
admin chapter listings can join. The unit-test fixture
(`services/api/tests/chapter_selector_fixtures.py:33-80`) inserts
exactly those three.

Proposal §3 "SQL shape" (lines 174–186) enumerates `inserted_template`,
`inserted_chapter`, `inserted_head` as separate CTEs in a single
transaction, and §Q4 (lines 110–122) + §Q5 (lines 125–140) lock the
template identity (deterministic UUID for `id`/`template_family_id`,
`version=1`, `schema_version=1`, empty JSON arrays) and the head
identity (`('chapter', 'chapter-alpha', 1, NULL)`). §Q3 (line 99) locks
the chapter id literal `chapter-alpha`, and §Q6 (lines 142–148) locks
`state='active'`. All three rows are present and identity-aligned with
the unit-test minimum-row fixture.

The `chapters.template_snapshot` shape in §3 (lines 191–201) matches
`services/api/app/services/chapters.py` and the unit fixture's
`Jsonb({"template_id": ..., "schema_version": 1})` plus the empty
structure arrays — production reads `template_snapshot` opaquely so the
extra structure keys are harmless.

### F-2 Idempotency rules cover all four states — PASS

§Q2 (lines 84–95) enumerates the four cases:

- All three rows match the fixture → no-op
  (`chapter fixture already present; no-op`).
- None exist → insert template, chapter, head
  (`inserted chapter fixture`).
- Partial compatible (some rows present, others missing) → insert only
  the missing rows (`repaired partial chapter fixture`).
- Conflicting (chapter id collision with different name/state/template,
  template UUID collision with different schema/version/structure, or
  head row with non-fixture sequence/change shape) → abort.

The fail-closed posture matches `seed-public-intake-form.yaml`'s drift
behavior the RCA already calls "loud failure on drift." The three
return-string outcomes are distinct so the helper's JSON summary lets
the test runner detect "I had to repair partial state" vs steady state
without changing exit code semantics. Consistent with §3 final SELECT
(lines 184–186).

The unique-index footprint is compatible: `uq_chapters__name` is on
`LOWER(name)` so a foreign chapter named "Alpha Chapter" would clash —
correctly hitting the abort path rather than silently creating a
duplicate. `uq_chapter_templates__family_version` on
`(template_family_id, version)` is satisfied by the deterministic
template+version=1 pair on re-run.

### F-3 SQL quoting/escaping — PASS

§3 substrate (lines 156–166) explicitly requires the helper to "use a
local SQL literal helper for any string inserted into SQL," patterned
on `seed-authority-grants.mjs`. The reference `sqlLiteral`
(`infra/tests/e2e/lib/seed-authority-grants.mjs:27-35`) uses
`E''`-prefixed literals with `\\`/`'`/`\0` escaping, which round-trips
correctly regardless of `standard_conforming_strings`.

Injection surface is small in practice: the helper's parameter inputs
are constants derived from `contract.json` (asserted to be
`chapter-alpha`/`Alpha Chapter`) and from a deterministic UUID literal,
not from user-controlled environment variables. Even if a future
change widens the inputs, the `sqlLiteral` helper is the right
guardrail. PASS.

### F-4 No global state mutation outside fixture rows — PASS

Helper writes are confined to:

- one `chapter_templates` row keyed by the deterministic fixture UUID;
- one `chapters` row keyed by `chapter-alpha`;
- one `aggregate_heads` row keyed by `('chapter', 'chapter-alpha')`.

It does not touch `authority_grants`, `members`, `form_definitions`,
`activity_actions`, `activity_state_changes`, or any other cluster-wide
table. §5 anti-scope (lines 264–272) forbids granting chapter authority
through this helper, adding Discord roles/channels, or touching
`/api/public/chapters` behavior — anything that would leak fixture
state into other test surfaces.

The deterministic template UUID is derived from the seed key
`e2e-template`, which the unit-test fixture does not use (it uses
`uuid4()`), so unit and e2e fixture identities cannot collide if both
ever run against the same database. PASS.

### F-5 Public chapter endpoint returns the seeded fixture — PASS

`services/api/app/repositories/public_chapters.py:12-24` filters
`WHERE state = 'active'` and selects `(id, name)`. §Q6 (lines 142–148)
seeds `state='active'`; §Q3 + §Q4 lock id `chapter-alpha` and name
`Alpha Chapter`. After the seed, `/api/public/chapters` returns
`{"chapters":[{"id":"chapter-alpha","name":"Alpha Chapter"}]}` — exactly
the contract.json expectation
(`infra/tests/fixtures/web-ui/contract.json:106-113`) and the TG-2
acceptance payload (proposal lines 244–248). PASS.

### F-6 TG-1 precision against partial seeding — PARTIAL, non-blocking refinement

TG-1 (proposal lines 226–235) is:

```sql
SELECT count(*) FROM chapters
 WHERE id = 'chapter-alpha' AND state = 'active'
```

Expected: `1`.

This verifies the public-facing row only. It does NOT independently
verify that the deterministic `chapter_templates` row exists, nor that
the `aggregate_heads` row exists for `('chapter', 'chapter-alpha')`. A
hypothetical implementation regression that wrote only the chapter row
(skipping head and/or relying on a pre-existing template that drifted
in shape) would still pass TG-1 because:

- the chapter FK constraint requires *some* template to exist, but not
  necessarily the fixture template — a stray test template would
  satisfy the FK;
- `aggregate_heads` has no FK to chapters (it's a `(text, text, ...)`
  table), so a missing head row is structurally legal and only breaks
  the admin chapter list join, not the public endpoint that test 19
  drives.

In practice, the helper itself is supposed to insert all three rows in
a single `ON_ERROR_STOP=1` transaction, so a true partial-state outcome
should fail the helper before TG-1 runs. And TG-2 (public endpoint
payload) plus TG-3 (full e2e flow) cover the chapter row and the
selectable option respectively. So this is a TG-1-only narrowness, not
a structural defect.

**Refinement (non-blocking):** extend TG-1 to assert the fixture
template UUID exists in `chapter_templates` and the
`('chapter','chapter-alpha')` row exists in `aggregate_heads`, e.g.:

```sql
SELECT
  (SELECT count(*) FROM chapters
     WHERE id = 'chapter-alpha' AND state = 'active') AS chapter_ok,
  (SELECT count(*) FROM chapter_templates
     WHERE id = '<fixture-uuid>') AS template_ok,
  (SELECT count(*) FROM aggregate_heads
     WHERE aggregate_type = 'chapter'
       AND aggregate_id = 'chapter-alpha') AS head_ok;
```

Expected `(1,1,1)`. This makes TG-1 a true partial-seed detector
without changing the helper or the proposal's idempotency rules.

## Observations (non-blocking)

1. **CTE write visibility.** §3 prescribes a single CTE-based statement
   (`fail_closed_guard` + three `inserted_*` CTEs). PostgreSQL
   data-modifying CTEs share a single snapshot and cannot see each
   other's row writes through `SELECT`, but the FK constraint check on
   `chapters.template_id` references the index/heap directly and works
   in this pattern; `aggregate_heads` has no FK to chapters so order
   independence is fine. The same pattern is already used in
   `seed-public-intake-form.yaml`, so this is project convention. No
   change needed; flagging only because the implementer should prefer
   explicit `WHERE NOT EXISTS` guards on each `inserted_*` CTE rather
   than chained `RETURNING` reads to avoid the snapshot-visibility
   surprise.

2. **Contract assertion as drift guard.** §3 (lines 167–171) requires
   the helper to read `infra/tests/fixtures/web-ui/contract.json` and
   assert the chapter id/name are exactly `chapter-alpha` /
   `Alpha Chapter`. This is good — the helper fails fast if a future
   contract.json edit changes the fixture identity. Implementer should
   read both `form.chapters.selected_id`/`selected_name` AND the
   `chapter_select` field's `value` (`contract.json:120`) so the helper
   blocks all three drift surfaces, not just one.

3. **Adjacent authority dependency.** §3 (lines 213–217) calls for a
   second invocation of `seed-authority-grants.mjs` with
   `E2E_APPLICATION_SCOPE_KIND=chapter` /
   `E2E_APPLICATION_SCOPE_ID=chapter-alpha`. RCA "Roster / authority
   side effects" (lines 219–235) confirms application
   detail/read/message/transition checks evaluate against the
   submission's target scope, so the chapter-scoped grant is required
   for the post-submit flow. The existing helper's idempotency check
   (`seed-authority-grants.mjs:108-116`) keys on
   `(scope_kind, scope_id, permissions)` so the two invocations create
   two distinct grants for the same officer member. Correct. No change
   to `seed-authority-grants.mjs` is implied or required.

4. **Diff budget.** §6 estimates under 220 net lines across two files
   (`seed-chapter-fixture.mjs` new, `19-web-ui.sh` extension). An
   implementation that adds a GitOps Job, kustomization wiring,
   admin-chapter-create code path, migration, contract.json change, or
   `/api/public/chapters` change is outside the proposal and should
   trigger risk re-review.

## Acceptance check (proposed)

When implementation lands, the following must all hold:

- `infra/tests/e2e/lib/seed-chapter-fixture.mjs` exists, requires
  `KUBECONFIG_PATH` or `KUBECONFIG`, locates the CNPG primary pod in
  namespace `server-manager`, reads the `server-manager-postgres-url`
  secret, executes one `psql -v ON_ERROR_STOP=1` statement through
  `kubectl exec`, uses an `E''`-quoting `sqlLiteral` helper for every
  string interpolated into SQL, and prints a JSON summary with
  `chapter_id`, `chapter_name`, `template_id`, `template_name`,
  `outcome`.
- The helper inserts (when missing) all three rows: a
  `chapter_templates` row with `id = template_family_id =
  <deterministic uuid for "e2e-template">`, `version=1`,
  `schema_version=1`, empty JSON-array structures; a `chapters` row
  with `id='chapter-alpha'`, `name='Alpha Chapter'`,
  `template_id=<that uuid>`, `state='active'`, `template_snapshot`
  per §3 lines 191–201, empty `configuration` and `discord_resources`;
  and an `aggregate_heads` row `('chapter', 'chapter-alpha', 1, NULL)`.
- The helper is idempotent across the four §Q2 cases and aborts on
  drift in any of: chapter name/state/template, template
  schema/version/structure, head sequence/change shape.
- The helper asserts `chapter-alpha` / `Alpha Chapter` are still the
  fixture identity in `infra/tests/fixtures/web-ui/contract.json` and
  fails if not.
- `infra/tests/e2e/tests/19-web-ui.sh` invokes the helper after
  `validate-web-ui` and before `seed-authority-grants.mjs`, writing
  the JSON summary to `/tmp/seed-chapter-fixture.json`, then runs
  `seed-authority-grants.mjs` once with global scope (current
  behavior) and once more with `E2E_APPLICATION_SCOPE_KIND=chapter`
  and `E2E_APPLICATION_SCOPE_ID=chapter-alpha`, then runs Playwright.
- TG-1: `chapters` has exactly one row matching
  `id='chapter-alpha' AND state='active'`. (Recommended refinement:
  also assert the fixture `chapter_templates` UUID and the
  `('chapter','chapter-alpha')` `aggregate_heads` row exist.)
- TG-2: `GET /api/public/chapters` against the seeded cluster returns
  `{"chapters":[{"id":"chapter-alpha","name":"Alpha Chapter"}]}`.
- TG-3: re-running `infra/tests/e2e/tests/19-web-ui.sh` completes
  Playwright's `selectOption("chapter-alpha")`; the public submit
  persists `target_scope_kind='chapter'` and
  `target_scope_id='chapter-alpha'`; officer queue, claim, detail,
  transcript, message append, and transitions all pass through the
  chapter-scoped target.
- No edits land in `services/api/`, `migrations/`,
  `gitops/channels/local/applications/server-manager/`,
  `infra/tests/fixtures/web-ui/contract.json`, or
  `services/api/tests/chapter_selector_fixtures.py`.

AUDIT_DONE: plans/risk/bug-5-audit.md
