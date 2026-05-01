# BUG-5 Proposal: Local e2e chapter fixture

## 1. Problem statement

`infra/tests/e2e/tests/19-web-ui.sh` reaches the admin UI and public application
form, then Playwright times out selecting the public form's `Chapter` control
with value `chapter-alpha`.

The current web UI contract requires that fixture:

- `infra/tests/fixtures/web-ui/contract.json:102-113` defines
  `/api/public/chapters` as returning `{"id":"chapter-alpha","name":"Alpha Chapter"}`.
- `infra/tests/fixtures/web-ui/contract.json:115-121` adds a
  `chapter_select` field whose value is `chapter-alpha`.
- `infra/tests/fixtures/web-ui/contract.json:143-154` expects public submit to
  post `scope.scope_kind="chapter"`, `scope.scope_id="chapter-alpha"`, and
  `responses.chapter`.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:93-99` selects
  `field.value`; with the contract above, that is `chapter-alpha`.

The cluster state supplied for the failure is:

```sql
SELECT id, name, state FROM chapters;
-- 0 rows
```

With zero `chapters` rows, `GET /api/public/chapters` has no active chapter
option to return, so the rendered `<select>` never contains the
`chapter-alpha` option Playwright is waiting for.

This is a missing runtime fixture/bootstrap path, not a failed chapter seed
implementation.

The concrete chain is:

1. INIT-135 changed the local form seed to publish a global form containing
   `chapter_select` (`seed-public-intake-form.yaml:46`).
2. INIT-135 changed the e2e/browser contract to select
   `chapter-alpha` / `Alpha Chapter` (`contract.json:102-121`).
3. The public chapter endpoint reads only existing active chapter rows:
   `services/api/app/repositories/public_chapters.py:12-24`.
4. The local GitOps resources seed the public form but do not seed
   `chapter_templates` or `chapters`.
5. The e2e seed script seeds officer application authority only, not chapters.
6. The production chapter API could create a chapter only after a template
   exists and with `chapter_template.write`/`chapter.write` authority, neither
   of which the e2e officer seed grants.

Because `chapters` is empty, `/api/public/chapters` returns an empty `chapters`
array. The SPA renders no `chapter-alpha` option, and Playwright times out in
`selectOption("chapter-alpha")`.

## 2. Decisions

### Q1. Where does the fixture live?

Pick: **Option c, a new e2e helper script invoked from `19-web-ui.sh`.**

Create `infra/tests/e2e/lib/seed-chapter-fixture.mjs` and call it from
`infra/tests/e2e/tests/19-web-ui.sh` after `validate-web-ui` and before
Playwright.

Rejected:

- Option a, extending `seed-authority-grants.mjs`: chapter projection rows and
  officer authority grants are different fixtures. Combining them would make
  the authority helper own unrelated chapter lifecycle data.
- Option b, a new GitOps Job: this fixture is tied to the e2e web contract
  (`chapter-alpha` / `Alpha Chapter`), not general local bootstrap data. A Job
  would also require kustomization wiring and cluster apply/reconcile behavior
  for a single Playwright fixture that can be seeded immediately in test setup.

### Q2. Idempotent?

Yes. Re-running the seed is a no-op when the complete fixture already exists.

The helper must use the same fail-closed posture as
`seed-public-intake-form.yaml`: insert the missing deterministic fixture rows,
return an explicit outcome, and fail loudly if `chapter-alpha` or the fixture
template exists in an incompatible shape.

Concrete idempotency rules:

- If the template, chapter, and `aggregate_heads` row already match the fixture,
  return `chapter fixture already present; no-op`.
- If none of the rows exist, insert the template, then chapter, then head.
- If a partial compatible fixture exists, insert only the missing dependency row
  needed to reach the complete fixture.
- If `chapters.id = 'chapter-alpha'` exists with a different name, state, or
  template association, abort.
- If the fixture template identity exists with a different schema, version, or
  non-empty structures, abort.
- If an `aggregate_heads` row for `('chapter', 'chapter-alpha')` exists with a
  non-fixture sequence/change shape, abort rather than rewriting history.

### Q3. Hardcoded id vs deterministic UUID?

Keep the hardcoded chapter id string: `chapter-alpha`.

`chapters.id` is `text`, and `contract.json` hardcodes `chapter-alpha` as the
SPA option value and submit target scope. The fixture must not generate a
different chapter id.

### Q4. Template dependency

The fixture creates its own minimal template and does not depend on a default
template.

Template fixture identity:

- Logical seed key/name: `e2e-template`.
- Physical `chapter_templates.id`: deterministic UUID derived from the
  `e2e-template` seed key, because `chapter_templates.id` is a UUID column in
  `wu-007a`/`wu-018`.
- `template_family_id`: same deterministic UUID as the fixture template id.
- `version`: `1`.
- `schema_version`: `1`.
- `channel_structure`, `role_structure`, `default_permission_intents`: empty
  JSON arrays, matching the unit-test minimum-row fixture.

The implementation must not look up or create a shared "default" template.

### Q5. aggregate_heads

Yes, the fixture must include an aggregate head row.

The unit-test minimum-row fixture inserts `chapter_templates`, `chapters`, and
`aggregate_heads`; the RCA notes the admin chapter listing expects chapter rows
to have aggregate heads. The e2e fixture should mirror that minimum shape:

```sql
INSERT INTO aggregate_heads (
  aggregate_type,
  aggregate_id,
  current_seq,
  latest_change_id
)
VALUES ('chapter', 'chapter-alpha', 1, NULL)
```

### Q6. Chapter state

Seed the chapter in `active` state.

`/api/public/chapters` filters `WHERE state = 'active'`, and the purpose of the
fixture is to make `chapter-alpha` available to the public SPA dropdown before
Playwright calls `selectOption("chapter-alpha")`.

## 3. Substrate

### New file

Add `infra/tests/e2e/lib/seed-chapter-fixture.mjs`.

It should follow the execution pattern already used by
`seed-authority-grants.mjs`:

- require `KUBECONFIG_PATH` or `KUBECONFIG`;
- locate the CNPG primary pod in namespace `server-manager`;
- read the `server-manager-postgres-url` secret;
- execute one `psql -v ON_ERROR_STOP=1` SQL statement through `kubectl exec`;
- use a local SQL literal helper for any string inserted into SQL;
- print a JSON summary with `chapter_id`, `chapter_name`, `template_id`,
  `template_name`, and `outcome`.

The helper should derive the expected chapter id/name from
`infra/tests/fixtures/web-ui/contract.json` and assert they are exactly
`chapter-alpha` and `Alpha Chapter`. If the contract changes, this seed should
fail instead of silently creating a fixture that no longer matches the browser
flow.

### SQL shape

Use a single transaction with CTEs modeled after
`seed-public-intake-form.yaml`:

- `seed`: constants for `chapter-alpha`, `Alpha Chapter`, `e2e-template`, the
  deterministic template UUID, empty JSON structures, and `active`.
- `fail_closed_guard`: drift checks for incompatible existing template,
  chapter, or head rows.
- `inserted_template`: insert the minimal template if absent.
- `inserted_chapter`: insert the active chapter if absent.
- `inserted_head`: insert the aggregate head if absent.
- final `SELECT`: one of `inserted chapter fixture`, `repaired partial chapter
  fixture`, or `chapter fixture already present; no-op`.

The chapter row should use a `template_snapshot` consistent with
`services/api/app/services/chapters.py`:

```json
{
  "template_id": "<template uuid>",
  "template_family_id": "<template uuid>",
  "template_version": 1,
  "schema_version": 1,
  "channel_structure": [],
  "role_structure": [],
  "default_permission_intents": []
}
```

### `19-web-ui.sh`

Invoke the new seed before Playwright:

1. Run `validate-web-ui` as today.
2. Run `seed-chapter-fixture.mjs` and write its JSON to
   `/tmp/seed-chapter-fixture.json`.
3. Seed officer authority with the existing `seed-authority-grants.mjs` global
   invocation as today, preserving queue/list visibility.
4. Reuse `seed-authority-grants.mjs` once more with
   `E2E_APPLICATION_SCOPE_KIND=chapter` and
   `E2E_APPLICATION_SCOPE_ID=chapter-alpha` so claim, detail, transitions, and
   messages continue through the chapter-scoped application target. This does
   not extend the authority helper; it uses the scope parameters it already
   provides.
5. Run Playwright.

No production API, repository, service, migration, or unit-test fixture changes
belong in this proposal.

## 4. Test plan

### TG-1. Seed row exists and is active

After the seed runs:

```bash
kubectl exec ... -- psql ... -Atc \
  "select count(*) from chapters where id = 'chapter-alpha' and state = 'active'"
```

Expected: `1`.

### TG-2. Public chapter endpoint returns the fixture

After the seed runs:

```bash
curl /api/public/chapters
```

Expected payload in the clean e2e cluster:

```json
{"chapters":[{"id":"chapter-alpha","name":"Alpha Chapter"}]}
```

### TG-3. Test 19 completes the chapter-scoped browser flow

Re-run `infra/tests/e2e/tests/19-web-ui.sh`.

Expected:

- Playwright finds the dropdown option and `selectOption("chapter-alpha")`
  succeeds.
- Public submit persists `target_scope_kind = 'chapter'` and
  `target_scope_id = 'chapter-alpha'`.
- Officer queue, claim, detail, transcript, message append, and transitions
  continue through the existing end-to-end assertions.

## 5. Anti-scope

- Do not add an admin chapter creation flow.
- Do not touch chapter authority/grants beyond what the existing
  `seed-authority-grants.mjs` provides.
- Do not add Discord roles or channels for the seeded chapter.
- Do not modify `services/api/tests/chapter_selector_fixtures.py`.
- Do not change `/api/public/chapters` behavior or ordering.
- Do not add an Alembic migration.
- Do not add a GitOps Job or kustomization resource for this e2e-only fixture.

## 6. Diff budget

Expected implementation size:

- `infra/tests/e2e/lib/seed-chapter-fixture.mjs`: one new helper, roughly
  120-180 lines.
- `infra/tests/e2e/tests/19-web-ui.sh`: under 15 net lines for seed invocation,
  pass/fail logging, and the chapter-scoped reuse of `seed-authority-grants.mjs`.

Total budget: under 220 net lines, two files. No service, repository,
migration, contract, or unit-test fixture edits.
