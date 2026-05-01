# BUG-5 RCA: INIT-135 chapter fixture missing from local e2e cluster

## Symptom + state

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

## What seeds chapters today

### 1. Alembic migrations

The migrations create the data model but do not seed fixture chapter data:

- `migrations/versions/wu-007a_chapter_templates_foundation.py:16-48` creates
  `chapter_templates`.
- `migrations/versions/wu-018_chapter_templates.py:16-41` adds template family
  versioning and backfills existing templates, but inserts no template rows.
- `migrations/versions/wu-019_chapter_lifecycle.py:16-62` creates `chapters`
  with a non-null `template_id` FK to `chapter_templates`.
- `migrations/versions/wu-019_chapter_lifecycle.py:107-141` seeds only the
  `discord-provisioner` authority grant for chapter/template operations, not
  any template or chapter.

So a fresh migrated database can have both tables present and still have zero
`chapter_templates` and zero `chapters`.

### 2. Local GitOps seed Jobs

The local server-manager kustomization includes only one application data seed
Job: `gitops/channels/local/applications/server-manager/kustomization.yaml:14-15`
lists `alembic-migration-job.yaml` and `seed-public-intake-form.yaml`.

`seed-public-intake-form.yaml` seeds a form, not a chapter:

- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:37-54`
  defines the INIT-135 v2 global public form seed.
- `seed-public-intake-form.yaml:46` adds the `chapter_select` field to
  `form_definitions.fields`.
- `seed-public-intake-form.yaml:83-110` inserts only into `form_definitions`.

A grep of `gitops/channels/local/applications/server-manager/` finds no
`INSERT INTO chapters`, no `INSERT INTO chapter_templates`, and no separate
chapter fixture Job.

### 3. E2E seed script

`infra/tests/e2e/tests/19-web-ui.sh:276-281` runs the web validator, then
`infra/tests/e2e/lib/seed-authority-grants.mjs`, then Playwright.

`seed-authority-grants.mjs` seeds only an officer member and application
authority:

- `infra/tests/e2e/lib/seed-authority-grants.mjs:62-67` sets permissions to
  `application.claim`, `application.review`, `application.approve`, and
  `application.message`.
- `infra/tests/e2e/lib/seed-authority-grants.mjs:83-118` inserts only into
  `authority_grants`.

It does not insert `chapter_templates`, `chapters`, `aggregate_heads` for
chapters, roster rows, or chapter-scoped authority.

### 4. Chapter creation API

There is a production API path capable of creating chapters, but it is not part
of the e2e bootstrap flow and it cannot create a chapter without an existing
template:

- `services/api/app/api/v1/endpoints/chapter_templates.py:57-74` can create a
  chapter template, gated by `chapter_template.write` at global scope.
- `services/api/app/api/v1/endpoints/chapters/base.py:119-136` can create a
  chapter, gated by `chapter.write` at global scope.
- `services/api/app/services/chapters.py:180-196` fetches the requested
  template and raises `ChapterTemplateNotFoundError` if absent before inserting
  a proposed chapter.
- `services/api/app/api/v1/endpoints/chapters/base.py:157-182` transitions the
  chapter state, and `services/api/app/api/v1/endpoints/chapters/base.py:185-200`
  patches Discord resources. Public chapter listing requires `state='active'`,
  so a created chapter is not enough by itself.

The web admin endpoint is read-only:

- `services/api/app/api/v1/endpoints/web.py:64-69` exposes only
  `GET /api/v1/web/admin/chapters`.
- `services/api/app/services/web.py:7-11` and
  `services/api/app/repositories/web.py:8-22` only list rows.

The seeded officer from `seed-authority-grants.mjs` has application permissions
only. That seed does not grant `chapter_template.write` or `chapter.write`, so
the seeded officer identity cannot create the missing template/chapter through
the chapter management API as currently bootstrapped.

### 5. API/unit test fixtures

The INIT-135 API tests do seed chapters, but only inside the test database:

- `services/api/tests/chapter_selector_fixtures.py:23-82` inserts a
  `chapter_templates` row, a `chapters` row, and a matching `aggregate_heads`
  row.
- `services/api/tests/test_public_chapters.py:39-54` uses that helper to prove
  the public endpoint returns active chapters only.
- `services/api/tests/test_chapter_selector_submit.py` uses the same fixture
  family for public submit behavior.

That fixture was not promoted into the local e2e cluster bootstrap.

## INIT-135 spec intent

`proposals/17-init-135-chapter-selector.md` scoped beta-1 around the public
chapter selector and chapter-scoped submit path. It explicitly named the public
chapter endpoint and e2e fixture expectations, but the only GitOps seed it
called out was the form seed:

- Goal: applicants select an active chapter and submissions become
  chapter-scoped (`proposals/17-init-135-chapter-selector.md:3-5`).
- Public chapter list returns active rows from `chapters`
  (`proposals/17-init-135-chapter-selector.md:13-15`,
  `proposals/17-init-135-chapter-selector.md:95-109`).
- E2E should verify chapter-scoped persistence
  (`proposals/17-init-135-chapter-selector.md:29-31`,
  `proposals/17-init-135-chapter-selector.md:251-255`).
- GitOps seed scope names only `seed-public-intake-form.yaml`, specifically a
  global current form with `chapter_select`
  (`proposals/17-init-135-chapter-selector.md:43-45`,
  `proposals/17-init-135-chapter-selector.md:67`).
- Anti-scope excludes chapter creation/deletion/admin UI changes
  (`proposals/17-init-135-chapter-selector.md:257-264`).

`research/29-init-135-hookpoints.md` is more explicit about the split:

- Backend tests may add `seed_active_chapter(db, name)` or a
  `chapter_selector_fixtures.py` helper (`research/29-init-135-hookpoints.md:228-239`).
- The web/e2e contract should gain a fixture active chapter block
  (`research/29-init-135-hookpoints.md:511-526`).
- The seed v1->v2 work is only the public intake form seed
  (`research/29-init-135-hookpoints.md:653-751`).
- Admin chapter routes stay read-only and unchanged
  (`research/29-init-135-hookpoints.md:794-810`).

The spec therefore created a runtime data dependency on an active chapter
fixture but did not include a local-cluster chapter/template seeding surface in
the implementation scope.

## Pre-INIT-135 e2e behavior

Before commit `36695cd` (`feat: SLICE-025 chapter selector for public form`),
`infra/tests/fixtures/web-ui/contract.json` had no `definition_endpoint`, no
`form.chapters` block, no `chapter_select` field, and no chapter-scoped payload.
The form fields were only `character_name` and `application_text`, and submit
expected `scope.scope_kind="global"` plus `scope.scope_id=null`.

That previous global submit path did not depend on any row in `chapters`.
INIT-135 changed the contract and browser flow to require a chapter option, but
no matching cluster seed was added.

## Why no chapter exists on humility-local

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

## Foreign key / template dependency

A chapter fixture cannot be a single `chapters` row. The schema requires:

- a `chapter_templates` row first (`wu-007a`, later made versioned by `wu-018`);
- a `chapters.template_id` value referencing that template
  (`migrations/versions/wu-019_chapter_lifecycle.py:21`,
  `migrations/versions/wu-019_chapter_lifecycle.py:46-50`);
- a chapter aggregate head if the row is expected to appear in admin chapter
  listings, because the admin list joins `chapters` to `aggregate_heads`.

The unit-test fixture models this by inserting all three:
`chapter_templates`, `chapters`, and `aggregate_heads`
(`services/api/tests/chapter_selector_fixtures.py:33-80`).

## Roster / authority side effects

No evidence shows that the e2e chapter fixture needs roster side effects.

`services/api/app/services/chapters.py:180-229` creates only a proposed chapter
projection plus the mutation/audit state change. It does not seed roster rows,
chapter officer grants, or chapter roles. The e2e browser flow needs the
chapter before submit so the public endpoint can render the select option; the
post-submit officer path is handled by the separate e2e authority seed rather
than by chapter creation.

The caveat is scope: application read/message/transition authorization evaluates
against the submitted application's target scope. `list_applications` has a
global fallback for list visibility, but detail/read/message/transition checks
evaluate against the application target scope. Existing e2e authority setup
currently seeds global application permissions only, while INIT-135 now submits
with target scope `chapter`. That is not why the observed select timeout occurs,
but it is an adjacent authority dependency once the chapter option exists.

## Affected paths

Paths that currently encode the missing runtime fixture dependency:

- `infra/tests/fixtures/web-ui/contract.json` — names the expected
  `chapter-alpha` / `Alpha Chapter` fixture.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` — selects the fixture value
  from the rendered dropdown.
- `infra/tests/e2e/tests/19-web-ui.sh` — runs e2e seeds and asserts the
  submitted application is chapter-scoped.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  — seeds the `chapter_select` form that creates the runtime dependency.
- `gitops/channels/local/applications/server-manager/kustomization.yaml` — lists
  the local data/bootstrap resources applied to the cluster.
- `infra/tests/e2e/lib/seed-authority-grants.mjs` — current e2e seed hook for
  database fixtures, but it only grants officer application authority.
- `services/api/tests/chapter_selector_fixtures.py` — test-only direct SQL model
  of the minimum template/chapter/aggregate rows needed by the public endpoint.

## Candidate intervention points, not fixes

This RCA is not proposing a fix. Candidate places where the missing fixture
could be addressed, depending on the chosen ownership boundary:

- local GitOps bootstrap data under
  `gitops/channels/local/applications/server-manager/`;
- e2e setup before Playwright in `infra/tests/e2e/tests/19-web-ui.sh`;
- a dedicated e2e DB fixture helper adjacent to
  `infra/tests/e2e/lib/seed-authority-grants.mjs`;
- the web UI contract fixture if the fixture identity should be derived from a
  seeded row rather than hardcoded as `chapter-alpha`;
- API-level setup through `chapter_templates` + `chapters` endpoints if the e2e
  actor/authority model is intentionally expanded.
