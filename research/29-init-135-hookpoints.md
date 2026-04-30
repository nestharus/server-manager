# INIT-135 hookpoints

Substrate inventory for INIT-135 / BL-010 β-1 (chapter
selector). Source proposal: `proposals/17-init-135-chapter-selector.md`
(esp. §3 Substrate, §3 Audit r1 implementation pitfalls,
§6 Authorization Model, §7 Test Plan). Source audit:
`plans/risk/init-135-audit.md` (F1–F4). Source problem
map: `research/28-bl-010-problem-map.md`.

## Summary

INIT-135 ships one new public read surface
(`GET /api/v1/public/chapters`), one new form-field variant
(`chapter_select`), one new public-submit branch (form-
lookup override + chapter-target persistence), one
data-driven SPA renderer change, one seed v1→v2 advance,
and supporting fixtures/tests/ingress entries. The
implementation reuses the existing public submit
endpoint, receipt auth, application persistence, and form
JSONB storage paths unchanged. New surface area is
intentionally identity-free for the public read and
gated on `chapter_select` field presence for the
submit-side override. Net change: +820 / −70 lines (one
PR).

## Reuse (call directly)

### Backend (API)

- `app.contracts.applications.ApplicationScope` for
  validating `scope_kind` ∈ {global, chapter, member}
  and stripping/empty-checking `scope_id`
  (`services/api/app/contracts/applications.py:62-77`).
  Submit body already nests `ApplicationScope`; no shape
  change required.
- `app.contracts.applications.ApplicationSubmission` /
  `PublicApplicationSubmission` for request shape
  (`services/api/app/contracts/applications.py:201-241`).
  Responses already typed `dict[str, JSONValue]`, so a
  string chapter id under
  `responses[<chapterFieldId>]` round-trips without
  contract churn.
- `app.contracts.applications.FormDefinitionPublish`,
  `FormDefinitionRead`, `FormRoutingRules`
  (`services/api/app/contracts/applications.py:155-198`)
  — keep their existing import sites; only
  `ApplicationFormField` changes shape (see Modify).
- `app.services.applications.build_form_snapshot`
  (`services/api/app/services/applications.py:473-490`).
  Already produces `target_scope` from
  `routing_rules.review_scope` or the form scope; the
  chapter-selector override injects the selected
  chapter as `target_scope` before snapshot persistence.
- `app.services.applications.validate_application_responses`
  (`services/api/app/services/applications.py:493-548`).
  Reuse its existing field-map / required / type
  dispatch; extend with a `chapter_select` branch (see
  Modify in place).
- `app.services.applications._submit_application_internal`
  (`services/api/app/services/applications.py:676-829`).
  Reused as the single submit pipeline; the
  chapter-selector override runs inside it before the
  existing `_get_current_form_for_submit` call (see
  Modify in place).
- `app.services.applications.submit_public_application_with_receipt`
  (`services/api/app/services/applications.py:845-896`).
  No signature change. Member resolution
  (`resolve_or_create_real_discord_member`), actor
  identity stamping, and notification emit
  (`emit_application_public_submitted_event`) all stay
  intact for the chapter-target path.
- `app.services.applications._get_current_form_for_submit`
  (`services/api/app/services/applications.py:551-589`).
  Reused as-is for the non-selector path; the new
  override picks the global form via the same helper
  with `scope_kind="global", scope_id=None`.
- `app.services.applicant_discord_auth.verify_applicant_receipt`
  — receipt auth dependency for the public submit
  endpoint
  (`services/api/app/api/v1/endpoints/applications/public.py:14-15,
  32`). Untouched.
- `app.services.authorization.authorize_public_intake`
  — public-intake authority dependency
  (`services/api/app/api/v1/endpoints/applications/public.py:17,
  34`). Untouched.
- `app.repositories.forms.get_current_form_for_scope`
  (already imported by services/forms.py and
  services/applications.py). Used for the global-form
  lookup branch.
- `psycopg.Connection` + `psycopg.rows.dict_row` pattern
  used in `app.repositories.web.list_admin_chapters`
  (`services/api/app/repositories/web.py:9-22`) —
  template only. The new public chapter repo function
  must NOT call `list_admin_chapters` (which exposes
  `state`, `created_at`, and `version`).
- `FastAPI APIRouter` mount-prefix pattern from
  `services/api/app/api/v1/endpoints/health.py:8` and
  `services/api/app/api/v1/endpoints/ready.py:9` as the
  identity-free endpoint template. Neither route
  imports `get_pomerium_principal` /
  `verify_applicant_receipt`; mirror that posture.

### Frontend (SPA)

- `getJson<T>(path, schema)` zod fetcher
  (`services/web/src/api/client.ts:206-222`). Reused
  unchanged for the new `fetchPublicChapters()` and the
  new `fetchPublicApplicationForm()` helpers.
- `submitPublicApplication(payload)`
  (`services/web/src/api/client.ts:277-290`). Reused
  as-is; only the payload shape grows to include
  `scope.scope_kind="chapter", scope.scope_id=<id>` and
  `responses[<chapterFieldId>]=<id>` for selector-form
  submits.
- `fetchApplicantDiscordIdentity`
  (`services/web/src/api/client.ts:268-275`) and
  `redirectToDiscordAuth`
  (`services/web/src/features/public/ApplicationFormRoute.tsx:46-48`).
  Receipt-gating, draft preserve/restore, and login
  redirect logic remain intact.
- `applicationScopeSchema`
  (`services/web/src/api/client.ts:45-48`). Already
  accepts `scope_kind: string, scope_id: string|null`,
  so `chapter` flows without schema churn.
- `Button`
  (`services/web/src/components/primitives/Button.tsx`)
  — submit button keeps its existing usage at
  ApplicationFormRoute.tsx:322.

### Test fixtures / e2e

- `infra/tests/fixtures/web-ui/contract.json:99-141`
  (`form` block) — reuse the same submit/endpoint/
  success-status keys; extend `fields` and
  `payload_fields` rather than re-shaping.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:91-129`
  (`for (const field of webContract.form.fields)
  await page.getByLabel(field.label).fill(field.value)`)
  — extend the loop to dispatch on field `type`
  (text/textarea/select); keep the submit-response
  assertion and the `web-ui-public-submit.json` write.
- `services/web/tests/compat.spec.ts:115-140`
  (`publicSubmitApi` route stub) — reused; the
  `payloadValue` walker already supports dotted paths
  like `scope.scope_kind`, `responses.character_name`,
  so adding `responses.chapter` and the new
  `scope.scope_id` value is data-only.
- `services/api/tests/public_intake_fixtures.py:71-117`
  (`seed_global_public_application_form`) — reuse for
  base seeding; add a sibling helper that seeds a
  global form with `chapter_select` (see New).
- `services/api/tests/public_intake_fixtures.py`
  helpers `applicant_receipt_token`, `audit_context`,
  `create_real_member`, `fetch_application_row`,
  `fetch_application_actions`,
  `fetch_public_submitted_events`,
  `assert_risk_annotation` — all reused unchanged.
- `services/api/tests/test_forms.py:50-76` (`_payload`)
  — reused as the chapter-scope payload generator
  for negative cases asserting `chapter_select` is
  rejected on chapter-scope forms.
- `infra/tests/e2e/tests/19-web-ui.sh:8-80`
  (`assert_public_submit_persisted`) — reused harness;
  the new chapter-target assertions live inside it
  (see Modify in place).

### GitOps / Kong

- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-12`
  (the `KongPlugin` definition `public-intake-rate-limit`
  with 5/min, 50/hour). Reused — the new path inherits
  the existing rate-limit annotation
  (`konghq.com/plugins: public-intake-rate-limit`)
  without a new plugin.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:91-100`
  (catch-all `/` route on web.local with
  `allow_public_unauthenticated_access: true`).
  Reused unchanged. The new public chapter path reaches
  pomerium-proxy through the same catch-all and inherits
  no identity-header injection
  (`pass_identity_headers` is implicitly false on the
  unauthenticated catch-all). F4 trip-wire only;
  no edit.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`
  (BL-002 fail-closed guard) — reused verbatim. Must
  remain the first statement in the seed transaction.

## New (write fresh)

### Backend (API)

- `services/api/app/contracts/public_chapters.py` —
  exports `PublicChapterSummaryRead` and
  `PublicChapterListRead`. Shape locked at proposal
  §5: `{id: str, name: str}` and
  `{chapters: list[PublicChapterSummaryRead]}`. Both
  inherit from a `_PublicModel(BaseModel)` with
  `extra="forbid"` to mirror the existing
  `_WebModel` pattern at
  `services/api/app/contracts/web.py:11-12`. No
  `state`, `version`, `created_at`,
  `template_snapshot`, `configuration`,
  `discord_resources` fields.
- `services/api/app/repositories/public_chapters.py` —
  exports `list_public_active_chapters(connection)`.
  Reads `SELECT id, name FROM chapters WHERE state =
  'active' ORDER BY name ASC LIMIT 200` via
  `dict_row`. Distinct from
  `list_admin_chapters` (which selects `state`,
  `created_at`, joins `aggregate_heads`).
- `services/api/app/services/public_chapters.py` —
  exports `list_public_chapters(db: PostgresDatabase)
  -> PublicChapterListRead`. Wraps the repo call and
  validates each row through
  `PublicChapterSummaryRead.model_validate(row)`.
- `services/api/app/api/v1/endpoints/public_chapters.py`
  — exports `router = APIRouter(prefix="/api/v1/public/chapters")`
  with one `GET ""` route. Signature:
  `def list_public_chapters_endpoint(db: PostgresDatabase
  = Depends(get_db)) -> PublicChapterListRead`. The
  `get_db` helper imports from
  `app.api.v1.endpoints.applications._shared` to match
  the public submit endpoint. Docstring must state:
  "Public, no auth — returns active chapters only."
  No `Depends(get_pomerium_principal)`, no
  `Depends(verify_applicant_receipt)`,
  no `Depends(authorize_public_intake)`.
- `services/api/tests/test_public_chapters.py` —
  contract + active-filter tests for the new
  endpoint (see Tests).
- `services/api/tests/test_chapter_selector_submit.py`
  (or extend `test_public_intake_submit.py`) — public
  submit chapter-selector cases (TG-3, F2 gate).
- `services/api/tests/chapter_selector_fixtures.py`
  (optional) — exports
  `seed_global_chapter_selector_form(db) -> UUID`
  and `seed_active_chapter(db, name) -> str` for
  reuse by the new tests. May also live as additional
  helpers inside `public_intake_fixtures.py` to avoid
  a new file (call this implementation choice).

### Frontend (SPA)

- New zod schemas + helpers exported from
  `services/web/src/api/client.ts`:
  `publicChapterListSchema = z.object({ chapters:
  z.array(z.object({id: z.string(), name: z.string()}))
  })`, `fetchPublicChapters()` (calls
  `getJson("/api/v1/public/chapters",
  publicChapterListSchema)`),
  `publicFormFieldSchema` (discriminated union over
  `type`), `publicFormDefinitionSchema`, and
  `fetchPublicApplicationForm()` (calls
  `getJson("/api/public/application-forms/current",
  publicFormDefinitionSchema)` — the existing
  `/api/v1/application-forms/current` is officer-auth-
  only and is not reused; if the proposal expects the
  SPA to load the form definition without auth,
  implementation should add a public read route under
  the same public-no-auth posture; otherwise the SPA
  reads field definitions from a server-rendered
  bootstrap or from a public form snapshot endpoint —
  flag this open question for Phase 6a, since the
  proposal's SPA story implies a public form-definition
  read path that is not currently in §3 New files).
- `services/web/src/features/public/ApplicationFieldRenderer.tsx`
  (or inline in `ApplicationFormRoute.tsx`) — exports
  a `<ApplicationFieldRenderer field=... value=...
  onChange=... chapters=... />` component that
  dispatches on `field.type` ∈ {`short`, `long`,
  `number`, `select`, `multi_select`, `boolean`,
  `chapter_select`}. The `chapter_select` branch
  renders a native `<select>` with empty disabled
  placeholder option and one `<option>` per active
  chapter from
  `fetchPublicChapters()`.

### Tests

- `services/api/tests/test_public_chapters.py` —
  - active-only filter (seed one active + one
    proposed/archived; assert only active returned);
  - {id, name} shape (no `state`, `version`, etc.);
  - 200 OK without any auth headers;
  - empty list returns
    `{"chapters": []}`;
  - ordering by `name ASC` and 200-row cap (seed >200
    actives, assert response capped).
- `services/api/tests/test_chapter_selector_submit.py`
  (or extend `test_public_intake_submit.py`) — six F2
  cases (Positive 1/2/3, Negative 1/2/3) at proposal
  §7 TG-3.
- `services/api/tests/test_forms.py` — `chapter_select`
  round-trip, duplicate, `required=false`,
  non-global scope, blank id/label,
  `routing_rules.review_scope` conflict cases (TG-1).
- `services/api/tests/test_seed_public_intake_form_v2.py`
  — four cases: empty DB, v1 current, officer-published
  current, v2 already current (TG-3 integration; F3).
- `services/web/tests/compat.spec.ts` — chapter-selector
  render, required validation, mocked
  `/api/v1/public/chapters` route, payload assertions
  (TG-4). Extends existing `loggedInApplicantTest`
  variants.

## Modify in place (additive only)

### Backend (API)

- `services/api/app/contracts/applications.py:80-143`
  — replace the monolithic `class
  ApplicationFormField(_ApplicationModel)` with seven
  variant classes (`FormFieldShort`, `FormFieldLong`,
  `FormFieldNumber`, `FormFieldSelect`,
  `FormFieldMultiSelect`, `FormFieldBoolean`,
  `FormFieldChapterSelect`) plus a discriminated-union
  TypeAlias:
  `ApplicationFormField = Annotated[FormFieldShort | …
  | FormFieldChapterSelect, Field(discriminator="type")]`.
  Keep `FIELD_ID_PATTERN` (line 14), `id` /
  `type` / `label` / `required` JSON keys, the label
  validator (lines 95-103), and the per-type shape
  validators (lines 105-140) — split the existing
  `validate_shape` body into per-class
  `model_validator(mode="after")` blocks. New variant
  constraints from §3 Form definition changes:
  `Literal["chapter_select"]`, `required:
  Literal[True] = True`, `placeholder: str | None =
  None`, no `options` / `max_length`. Update
  `__all__` (lines 468-509) to add
  `FormFieldChapterSelect` (and any other variant
  classes the implementation chooses to export).
- `services/api/app/contracts/applications.py:170-181`
  — extend `FormDefinitionPublish.validate_unique_field_ids`
  (or add a sibling validator on `fields`) to enforce
  three β-1 contract rules:
  - at most one `chapter_select` field per form;
  - `chapter_select` allowed only when
    `scope.scope_kind == "global"`;
  - `routing_rules.review_scope` not set when a
    `chapter_select` is present (or set to a
    non-default value compatible with the override).
  These checks live at the contract boundary, not in
  the service.
- `services/api/app/services/applications.py:499`
  — F1: replace
  `ApplicationFormField.model_validate(raw)` with
  `pydantic.TypeAdapter(ApplicationFormField).validate_python(raw)`.
  Hoist the `TypeAdapter` instance to a module-level
  constant
  (`_APPLICATION_FORM_FIELD_ADAPTER =
  TypeAdapter(ApplicationFormField)`) and call
  `validate_python` inside the comprehension. No other
  call site uses `ApplicationFormField.model_validate`
  in the worktree (audit r1 §A5).
- `services/api/app/services/applications.py:517-548`
  — extend the response-validation dispatch with a
  `chapter_select` branch:
  - value must be `str` and non-blank (mirror
    `short` checks);
  - server-side re-check: read the chapter row by
    id; assert state = 'active' (call a thin reader
    in `app.repositories.public_chapters` or extend
    an existing chapter reader). If missing or
    inactive, raise
    `InvalidApplicationResponseError`.
- `services/api/app/services/applications.py:692-714`
  — F2: insert a chapter-selector override branch
  before the existing
  `_get_current_form_for_submit` call. Pseudocode
  shape (no implementation):
  - look up current global form via
    `_get_current_form_for_submit(scope_kind="global",
    scope_id=None)`;
  - count `chapter_select` fields in
    `current_global["fields"]`;
  - gate (all must hold): `validated.scope.scope_kind
    == "chapter"`, `validated.scope.scope_id` set,
    exactly one required `chapter_select` field
    present in the global form, and
    `validated.responses[<chapter_field_id>] ==
    validated.scope.scope_id`;
  - if gate true: `form_row = current_global` and
    skip the existing scope-direct lookup; if false
    and `validated.scope.scope_kind == "chapter"`:
    fall through to the existing chapter-scope lookup
    (so a non-selector chapter form still 404s
    correctly);
  - if `validated.scope.scope_kind == "global"` AND
    the current global form has a required
    `chapter_select`: raise
    `InvalidApplicationResponseError` (F2 Negative 2,
    422).
- `services/api/app/services/applications.py:733-744`
  — when the chapter-selector gate fires, inject the
  selected chapter into `target_scope` BEFORE
  `build_form_snapshot` returns or by overriding the
  snapshot's `target_scope` after the call.
  `target_scope_kind = "chapter"`,
  `target_scope_id = validated.scope.scope_id`.
  `form_snapshot.scope_kind` / `scope_id` remain
  `global` / `None` (the form-definition source).
- `services/api/app/services/forms.py:55-59`
  (`_effective_routing_rules`) — when
  `request.fields` contains a `chapter_select` and
  `request.routing_rules.review_scope is None`, do
  NOT default to `request.scope.as_persisted()`.
  Leave `review_scope` as `None`; the submit-time
  override sets the actual chapter target. Existing
  non-selector forms keep the current default-to-form-
  scope behavior.
- `services/api/app/api/v1/router.py:11-34` — add
  `public_chapters` to the
  `from app.api.v1.endpoints import (...)` import
  block and `router.include_router(public_chapters.router,
  tags=["public-chapters"])` alongside the other
  public surface (around line 50-58).

### Frontend (SPA)

- `services/web/src/api/client.ts:12-22` — keep
  `chapterListSchema` as the admin schema; add a
  separate `publicChapterListSchema` (id+name only) and
  `fetchPublicChapters()` (see New). Do not widen the
  admin schema to include the public shape.
- `services/web/src/features/public/ApplicationFormRoute.tsx:10-20`
  — replace the hardcoded `FormPayload` type with a
  derived type that accepts the form definition fields
  + a `responses: Record<string, unknown>` map.
- `services/web/src/features/public/ApplicationFormRoute.tsx:50-77`
  (draft preserve/restore) — generalize over the
  current form's field ids (read field ids from the
  loaded form definition rather than hardcoding
  `character_name` / `application_text`).
- `services/web/src/features/public/ApplicationFormRoute.tsx:155-198`
  (`onSubmit`) — derive `scope` from the loaded form:
  - if any field is `chapter_select`, set
    `scope.scope_kind = "chapter"` and
    `scope.scope_id = responses[<chapterFieldId>]`;
  - else keep `scope.scope_kind = "global", scope_id =
    null`.
  Build `responses` from the form definition's field
  ids (not from a hardcoded shape).
- `services/web/src/features/public/ApplicationFormRoute.tsx:300-328`
  (the form body) — replace the two hardcoded
  `<label>` / `<input>` / `<textarea>` blocks with a
  loop over the loaded form definition's `fields`
  rendered through `<ApplicationFieldRenderer>`.
  Preserve test ids (`application-submit-icon`,
  `application-status-icon`) and the dialog/Open
  details flow.

### GitOps

- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:33-43`
  — add a second path entry under
  `rules[0].http.paths` for
  `/api/v1/public/chapters` (pathType `Prefix`) routed
  to the same `server-manager-api:8000` backend.
  Inherits `konghq.com/plugins:
  public-intake-rate-limit` from the ingress
  annotation.
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:21-30`
  — add a second path entry for `/api/v1/public/chapters`
  next to `/api/public/applications`, routed through
  `pomerium-proxy:80`. No Pomerium-config route is
  added; the catch-all `/` SPA route handles
  unauthenticated access without injecting identity
  headers.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:33-50`
  — replace the v1 seed CTE with a v2 seed CTE:
  - new deterministic UUID
    `digest('init-135:public-intake-global:v2',
    'sha256')` truncated to 32 hex → uuid;
  - `fields` JSONB includes a leading
    `{"id":"chapter","type":"chapter_select",
    "label":"Chapter","required":true}` entry plus
    the existing `character_name` / `application_text`
    entries;
  - `routing_rules` stays `'{}'::jsonb`.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:52-211`
  — F3: add a v1→v2 advance branch:
  - add a `prior_seed` CTE that selects the
    deterministic v1 UUID
    (`digest('init-122:public-intake-global:v1', …)`)
    if it is current;
  - extend `inserted_form` to insert v2 when EITHER
    no current global form exists OR the current
    global form id matches the deterministic v1
    seed id — the latter case must also archive the
    v1 row in the same transaction
    (`UPDATE form_definitions SET status='archived',
    archived_at=CURRENT_TIMESTAMP WHERE id =
    <v1_id>`);
  - bump `inserted_action`'s `request_json` /
    `inserted_change`'s `payload_json` `version` to
    2 in the advance case;
  - `inserted_head` → on advance, `UPDATE
    aggregate_heads SET current_seq = 2,
    latest_change_id = c.id WHERE aggregate_type =
    'application_form' AND aggregate_id =
    'application_form|global|'`;
  - extend the final outcome `CASE` with a fifth
    branch ("advanced v1 to v2 seed") and preserve
    the existing "officer-published form present;
    skipping seed" branch (lines 203-208) when the
    current global form id is neither v1 nor v2.

### Tests / e2e

- `infra/tests/fixtures/web-ui/contract.json:99-141`
  — extend the `form` block:
  - add a `chapter_select` field entry to
    `fields`: `{"type": "chapter_select", "name":
    "chapter", "label": "Chapter", "value": "<fixture
    chapter id>"}`;
  - add a top-level
    `public_chapters: {"endpoint":
    "/api/v1/public/chapters", "method": "GET",
    "active_chapter": {"id": "<fixture id>",
    "name": "<fixture name>"}}` block;
  - extend `submit.payload_fields` so
    `scope.scope_kind` is `"chapter"`,
    `scope.scope_id` is `<fixture id>`, and add
    `responses.chapter` sourced from the chapter
    field.
- `infra/tests/validate_web_ui_local.sh:118-124,
  155-156` — replace the two-field assertion with a
  richer field-name set
  (`application_text,character_name,chapter`) and
  a payload-fields assertion that includes
  `responses.chapter` and the chapter-scoped
  `scope.scope_id`. Add an assertion that
  `contract.public_chapters.endpoint ===
  "/api/v1/public/chapters"`.
- `services/web/tests/compat.spec.ts:18-30,
  115-140, 278-299` — add a
  `publicChaptersApi` route stub at
  `**/api/v1/public/chapters` returning
  `{chapters: [contract.public_chapters.active_chapter]}`,
  and update the submit-payload assertion to expect
  `scope.scope_kind === "chapter"` and
  `responses.chapter === contract.public_chapters.active_chapter.id`.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:91-129`
  — replace the unconditional
  `await page.getByLabel(field.label).fill(field.value)`
  with a `field.type` dispatch:
  - `text` / `textarea` → `.fill(field.value)`;
  - `chapter_select` (or `select`) →
    `.selectOption({ label: field.value })` or
    `.selectOption({ value: field.value })`. Persist
    the selected chapter id into the
    `${flow}-public-submit.json` session record so
    the e2e shell assertion can read it.
- `infra/tests/e2e/tests/19-web-ui.sh:8-80`
  (`assert_public_submit_persisted`) — extend the
  Postgres SELECT to include
  `a.target_scope_kind`, `a.target_scope_id`, and
  `a.form_snapshot->>'scope_kind'`; assert
  `target_scope_kind = 'chapter'`,
  `target_scope_id = <selected chapter id from
  session record>`,
  `form_snapshot->>'scope_kind' = 'global'`. Keep the
  notification/state assertions (lines 39-79)
  intact.

## Audit r1 pitfalls (F1–F4) hookpoint mapping

### F1 — `TypeAdapter` for the union alias

- **Code:**
  `services/api/app/services/applications.py:497-500`.
  Replace `ApplicationFormField.model_validate(raw)`
  inside the `_field_map` comprehension with
  `_APPLICATION_FORM_FIELD_ADAPTER.validate_python(raw)`,
  where `_APPLICATION_FORM_FIELD_ADAPTER =
  TypeAdapter(ApplicationFormField)` is hoisted to a
  module-level constant near the existing imports
  (top of `applications.py`).
- **Surface to grep before merge:** repo-wide
  `ApplicationFormField.model_validate` call sites
  (currently only line 499). Grep also for
  `ApplicationFormField(` constructor calls and any
  test that constructs the field directly — those
  must move to the per-variant classes
  (`FormFieldShort(...)`, `FormFieldChapterSelect(...)`)
  or use `TypeAdapter(...).validate_python({...})`.
- **Tests:**
  - `services/api/tests/test_forms.py` —
    publish-then-read round-trip with mixed variants
    (proposal §7 TG-1). Must include at least one
    `chapter_select` entry alongside `short`,
    `long`, `select`, `multi_select`, `boolean`,
    `number`.
  - `services/api/tests/test_chapter_selector_submit.py`
    (or `test_public_intake_submit.py`) — a unit
    test that calls
    `validate_application_responses` directly with
    a re-parsed JSONB fields list and asserts
    each variant validates without raising. This
    single assertion catches the missing
    `TypeAdapter` switch end-to-end.

### F2 — Form-lookup override gate

- **Code:**
  `services/api/app/services/applications.py:692-734`
  (the `_submit_application_internal` body between
  `validated = ApplicationSubmission.model_validate`
  and `_require_submit_authority`). The override
  branch lands here, before the existing
  `_get_current_form_for_submit` call.
- **Tests** — six explicit cases, all in
  `services/api/tests/test_chapter_selector_submit.py`
  (or extending `test_public_intake_submit.py`). All
  share the receipt/audit fixture pattern from
  `public_intake_fixtures.py`:
  - **Positive 1:** seed chapter-selector global
    form + active chapter + matching response.
    Assert 201; row has
    `target_scope_kind='chapter'`,
    `target_scope_id=<chapter_id>`,
    `form_snapshot->>'scope_kind'='global'`,
    `form_snapshot->'target_scope'->>'scope_id' =
    <chapter_id>`.
  - **Positive 2:** chapter-selector global form +
    `scope_kind=chapter` + responses missing
    `chapter` key (or different id). Assert 422,
    `InvalidApplicationResponseError`.
  - **Positive 3:** non-selector global form +
    `scope_kind=global` + matching responses.
    Assert existing global path:
    `target_scope_kind='global'`,
    `target_scope_id IS NULL`. The override
    must not trigger.
  - **Negative 1:** non-selector global form +
    `scope_kind=chapter` + active chapter id, no
    chapter-specific form. Assert
    `FormDefinitionNotFoundError` → 404. Must NOT
    fall through to the global form via the
    override.
  - **Negative 2:** chapter-selector global form +
    `scope_kind=global`. Assert 422 (selector
    requires chapter scope).
  - **Negative 3:** chapter-selector global form +
    `scope_kind=chapter`, but
    `responses[chapter_field_id]` missing. Assert
    422.
- **Risk annotation per case:** `group=TG-3;
  named_risk=public_chapter_submit_uses_global_form_and_chapter_target;
  level=component`.

### F3 — Seed v1→v2 advance branch

- **Code:**
  `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:33-211`.
  The v2 seed must be a single transaction that
  branches on the current global form id. SQL skeleton
  (no implementation; structural shape only):

  ```sql
  WITH
    seed_v2 AS (
      SELECT
        (substring(encode(digest('init-135:public-intake-global:v2',
                                  'sha256'), 'hex'), 1, 32))::uuid AS form_id,
        ...,
        '[{"id":"chapter","type":"chapter_select",...},
          {"id":"character_name",...},
          {"id":"application_text",...}]'::jsonb AS fields,
        ...
    ),
    seed_v1 AS (
      SELECT (substring(encode(digest('init-122:public-intake-global:v1',
                                       'sha256'), 'hex'), 1, 32))::uuid AS form_id
    ),
    current_global AS (
      SELECT f.id, f.version
        FROM form_definitions f
       WHERE f.scope_kind = 'global'
         AND f.scope_id IS NULL
         AND f.status = 'current'
         FOR UPDATE
    ),
    archived_v1 AS (  -- only fires when current is v1
      UPDATE form_definitions
         SET status = 'archived',
             archived_at = CURRENT_TIMESTAMP
       WHERE id = (SELECT form_id FROM seed_v1)
         AND id = (SELECT id FROM current_global)
       RETURNING id
    ),
    inserted_form AS (
      INSERT INTO form_definitions (...)
      SELECT ..., COALESCE((SELECT version FROM current_global), 0) + 1, ...
        FROM seed_v2
       WHERE NOT EXISTS (SELECT 1 FROM current_global)  -- empty DB → v1
          OR EXISTS (SELECT 1 FROM archived_v1)         -- v1→v2 advance
       RETURNING id
    ),
    inserted_action AS ( ... 'form.publish', version=COALESCE(..., 1) ... ),
    inserted_change AS ( ... 'form.published', version=...,
                            payload_json includes new fields ... ),
    inserted_head AS (
      INSERT INTO aggregate_heads (...)
      SELECT ..., COALESCE((SELECT version FROM current_global), 0) + 1, ...
       WHERE NOT EXISTS (SELECT 1 FROM aggregate_heads
                          WHERE aggregate_type = 'application_form'
                            AND aggregate_id = 'application_form|global|')
      ON CONFLICT (aggregate_type, aggregate_id)
      DO UPDATE SET current_seq = EXCLUDED.current_seq,
                    latest_change_id = EXCLUDED.latest_change_id
       WHERE EXISTS (SELECT 1 FROM archived_v1)
      RETURNING aggregate_id
    )
  SELECT CASE
    WHEN EXISTS (SELECT 1 FROM archived_v1)        THEN 'advanced v1 to v2'
    WHEN EXISTS (SELECT 1 FROM inserted_head)      THEN 'inserted seed v2'
    WHEN (SELECT id FROM current_global) =
         (SELECT form_id FROM seed_v2)             THEN 'seed v2 already current; no-op'
    WHEN (SELECT id FROM current_global) IS NOT NULL
                                                    THEN 'officer-published form present; skipping seed'
    ELSE 'seed made no change'
  END AS outcome;
  ```

  The exact CTE structure is implementation-tight; the
  required behavior is enumerated below.
- **Behavior asserted by tests** (in
  `services/api/tests/test_seed_public_intake_form_v2.py`):
  - **Empty DB:** v2 inserted at version 1; aggregate
    head created with `current_seq=1`. `form.publish`
    + `form.published` both written; outcome
    "inserted seed v2".
  - **v1 current:** v1 row archived (status='archived',
    archived_at set); v2 inserted at version 2;
    aggregate head updated to `current_seq=2`;
    `form.publish` action and `form.published`
    state-change written with `version: 2`. Outcome
    "advanced v1 to v2".
  - **Officer-published current:** no insert, no
    archive, no aggregate-head change. Outcome
    "officer-published form present; skipping seed".
  - **v2 already current:** no-op. Outcome
    "seed v2 already current; no-op".
  - **BL-002 fail-closed guard:** preserved at
    `seed-public-intake-form.yaml:14-31`; if
    `aggregate_heads` row exists for
    `application_form|global|` but no current global
    form exists, RAISE EXCEPTION fires before any
    mutation.

### F4 — Public chapter endpoint identity-free

- **Code:**
  `services/api/app/api/v1/endpoints/public_chapters.py`.
  The endpoint dependency tree must contain ONLY
  `db = Depends(get_db)`. Specifically:
  - NO `Depends(get_pomerium_principal)` (cf.
    `services/api/app/api/v1/endpoints/web.py:14, 66`);
  - NO `Depends(verify_applicant_receipt)` (cf.
    `services/api/app/api/v1/endpoints/applications/public.py:14, 32`);
  - NO `Depends(authorize_public_intake)` (cf.
    `services/api/app/api/v1/endpoints/applications/public.py:17, 34`);
  - NO header-reading `Request` parameter that pulls
    Pomerium claim headers.
- **Docstring requirement:** the route function
  docstring must state "Public, no auth — returns
  active chapters only. No identity headers consumed."
  This is the audit-time grep target for F4.
- **Tests** (in
  `services/api/tests/test_public_chapters.py`):
  - request with no auth headers → 200 with
    `{chapters: [...]}`;
  - request with stray Pomerium claim headers
    (`x-pomerium-claim-email`, `x-pomerium-claim-sub`,
    `x-pomerium-claim-discord-user-id`) → 200, same
    body — confirms the endpoint does not branch on
    identity.
  - active filter: seed one `active`, one `proposed`,
    one `archived` chapter; assert only the active
    chapter appears.
  - shape: assert response keys are exactly
    `{"chapters"}` and each item's keys are exactly
    `{"id", "name"}` — guards against accidental
    admin-shape leak.
- **Ingress trip-wire:** if a future Phase 6+ change
  adds an explicit Pomerium prefix-route for
  `/api/public/`, it must use
  `allow_public_unauthenticated_access: true` and
  `pass_identity_headers: false`. Out of scope for
  INIT-135; record as observation only.

## Anti-scope (β-2/β-3) — do NOT touch

- No multi-page form state, page schema, progress
  indicator, or `page` field on
  `ApplicationFormField` (β-2).
- No conditional visibility / `visible_when` / field
  dependency graph (β-2).
- No file upload, presigned URL, object-storage
  backend, malware scanning, or attachment response
  type (β-3).
- No chapter creation/deletion/admin UI changes — admin
  chapter routes
  (`services/api/app/api/v1/endpoints/web.py:64-69`,
  `services/api/app/services/web.py`,
  `services/api/app/contracts/web.py:39-48`,
  `services/api/app/repositories/web.py:9-22`) stay
  read-only and unchanged.
- No officer review workflow changes
  (`app/api/v1/endpoints/web.py:172-408` and the
  officer message/transition surfaces). The chapter-
  scoped application is read by the existing officer
  detail/queue surfaces unchanged.
- No live Humility Discord writes or notification-
  channel changes — `emit_application_public_submitted_event`
  is reused as-is and remains Tier 2 (notification
  emit, not Discord I/O).
- No backwards-compatibility aliases (`field_id`,
  `field_type`, parallel field unions, deprecated
  shape shims). Existing JSON keys (`id`, `type`,
  `label`, `required`, `placeholder`,
  `max_length`, `options`) stay byte-compatible.
- No new feature flag, no `ENABLE_CHAPTER_SELECTOR`
  toggle. Behavior is gated on form-field presence
  (`chapter_select`), not config.
- No new schema migration. JSONB
  `form_definitions.fields` accepts the new variant
  with no Alembic head bump beyond the current
  `wu_045_app_public_submit_notify`
  (`migrations/versions/wu-045_application_public_submit_notifications.py:10-13`).
- Do not reuse `/api/v1/web/admin/chapters` for
  applicants — proposal §11 "Delete or avoid".
- Do not hardcode chapter options in the SPA or in
  `infra/tests/fixtures/web-ui/contract.json` outside
  the fixture's `public_chapters.active_chapter`
  block — the SPA reads them from
  `/api/v1/public/chapters` at render time.
