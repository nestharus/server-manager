# INIT-136 hookpoints

Substrate inventory for INIT-136 / BL-010 β-2 (multi-page
+ conditional fields). Source proposal:
`proposals/27-init-136-multi-page-conditional.md` (esp.
§2 Decisions Q1–Q6, §3 Substrate, §4 Test Plan, §5
Anti-Scope, §6 Diff Budget). β-1 hookpoint reference:
`research/29-init-135-hookpoints.md`. Problem map:
`research/28-bl-010-problem-map.md`.

## Summary

INIT-136 ships two additive contract attributes
(`page: int`, `visible_when: FormFieldVisibleWhen | None`)
on the existing `_BaseFormField`, one publish-time
predicate-graph validator, one server-side visibility
pass inside `validate_application_responses`, one wizard
state machine + page navigation in
`ApplicationFormRoute.tsx`, and supporting fixtures /
component tests / e2e fixture extension. No new endpoint,
no new schema migration, no new persisted JSON shape.
The submit API stays the β-1 shape
(`scope` + `responses: dict[str, JSON]` + optional
`client_application_id`); β-1 `chapter_select`
routing/override is reused unchanged and explicitly
guarded against `visible_when` interactions.
Net change target: +760 / −80 lines (one PR;
proposal §6).

## Reuse (call directly)

### Backend (API)

- `app.contracts.applications._BaseFormField`
  (`services/api/app/contracts/applications.py:80-100`).
  Already the shared field base across all variants;
  `page` and `visible_when` are added here so every
  variant inherits them without per-class duplication.
- `app.contracts.applications.ApplicationFormField`
  discriminated TypeAlias
  (`services/api/app/contracts/applications.py:192-201`).
  `Annotated[... | FormFieldChapterSelect, Field(discriminator="type")]`
  — adding two attributes on `_BaseFormField` keeps the
  union shape; the union itself is not re-declared.
- `app.contracts.applications._APPLICATION_FORM_FIELD_ADAPTER`
  hoisted at
  `services/api/app/services/applications.py:181`
  (`TypeAdapter(ApplicationFormField)`). Reused in
  `validate_application_responses:496-508` and
  `_chapter_select_field_ids:575-581`. β-1 already
  switched off `model_validate` so β-2 inherits the
  fix — no additional adapter or call-site change is
  required.
- `app.contracts.applications.FormDefinitionPublish`
  (`services/api/app/contracts/applications.py:215-256`)
  with its existing `validate_unique_field_ids`
  (lines 230-241) and `validate_chapter_select_contract`
  (lines 243-256). Both reused unchanged; the new
  predicate-graph validator runs alongside them at the
  same `model_validator(mode="after")` boundary.
- `app.contracts.applications.PublicApplicationSubmission`
  (`services/api/app/contracts/applications.py:296-316`)
  and `ApplicationSubmission`
  (`services/api/app/contracts/applications.py:276-290`).
  β-2 keeps the submit body shape — `responses: dict[str,
  JSON]` already accommodates a sparse map of visible
  fields only. No contract churn on the submit side.
- `app.contracts.applications.ApplicationScope`
  (`services/api/app/contracts/applications.py:62-77`).
  Submit `scope` semantics unchanged; the β-1
  chapter-selector override remains the only routing
  branch that mutates `target_scope` from `responses`.
- `app.services.applications.validate_application_responses`
  (`services/api/app/services/applications.py:496-572`).
  Field-map build (lines 503-508), unknown-key check
  (lines 509-514), required-key check (lines 515-523),
  per-type dispatch (lines 525-572), and the existing
  `chapter_select` active-chapter recheck
  (lines 557-572) all reused; β-2 wraps them in a
  visibility pass (see Modify in place).
- `app.services.applications._chapter_selector_override`
  (`services/api/app/services/applications.py:584-619`).
  Reused unchanged. The override gate must remain narrow:
  it relies on the global form containing exactly one
  required `chapter_select` field, and β-2 must not let
  conditional visibility reduce that count to zero or
  hide the field at submit time. The contract guard
  `validate_chapter_select_contract`
  (lines 243-256) plus the new predicate-graph
  validator together prevent that.
- `app.services.applications._get_current_form_for_submit`
  (`services/api/app/services/applications.py:622-660`)
  and `app.services.applications.build_form_snapshot`
  (`services/api/app/services/applications.py:476-493`).
  Reused as-is. `form_snapshot.fields` already carries
  the JSON-serialized field list, so `page` and
  `visible_when` round-trip through JSONB without any
  snapshot-shape edit.
- `app.services.applications._submit_application_internal`
  (`services/api/app/services/applications.py:747-914`)
  and `submit_public_application_with_receipt`
  (`services/api/app/services/applications.py:930-981`).
  Reused as the single submit pipeline. The visibility
  pass is added inside the existing
  `validate_application_responses` call at line 814,
  not as a new pre-step.
- `app.services.applications.fetch_active_public_chapter`
  (imported at
  `services/api/app/services/applications.py:58`).
  β-1 surface; reused unchanged for the
  `chapter_select` active-chapter recheck.
- `app.services.forms._effective_routing_rules`
  (`services/api/app/services/forms.py:55-60`).
  Already special-cases `chapter_select` to skip the
  default `review_scope` injection. β-2 does not
  introduce additional routing variants, so this helper
  is reused unchanged.
- `app.services.forms.publish_form`
  (`services/api/app/services/forms.py:79-167`) and
  `app.services.forms.get_current_form`
  (`services/api/app/services/forms.py:170-184`).
  Reused. JSONB persistence accepts the extended
  `_BaseFormField` shape without an Alembic migration.
- `app.api.v1.endpoints.public_application_forms`
  router and `GET /api/v1/public/application-forms/current`
  endpoint
  (`services/api/app/api/v1/endpoints/public_application_forms.py:12-30`).
  Reused without signature or response-model change;
  `FormDefinitionRead` serializes the extended fields
  by virtue of inheritance from `_BaseFormField`.
- `app.api.v1.endpoints.public_chapters` router
  (β-1 surface) and the public chapters list. Untouched
  — β-2 adds no new public read.

### Frontend (SPA)

- `getJson<T>` helper
  (`services/web/src/api/client.ts:271-287`),
  `fetchPublicApplicationForm`
  (`services/web/src/api/client.ts:338-340`),
  `fetchPublicChapters`
  (`services/web/src/api/client.ts:333-336`),
  `submitPublicApplication`
  (`services/web/src/api/client.ts:351-364`),
  `fetchApplicantDiscordIdentity`
  (`services/web/src/api/client.ts:342-349`). All five
  helpers used as-is. Submit payload remains
  `{scope, responses, client_application_id}`.
- `services/web/src/api/client.ts:33-37`
  (`basePublicFormFieldSchema`) and
  `services/web/src/api/client.ts:39-67`
  (`publicFormFieldSchema` discriminated union over
  `type`). Reused as the union root; β-2 widens the
  base shape rather than re-declaring variants
  (see Modify in place).
- `services/web/src/api/client.ts:69-84`
  (`publicFormDefinitionSchema`). Reused; the schema
  reads `fields: z.array(publicFormFieldSchema)` so the
  extended base flows through automatically.
- `services/web/src/api/client.ts:107-110`
  (`applicationScopeSchema`). β-2 routing path stays
  on β-1 chapter-selector semantics; no shape change.
- `services/web/src/features/public/ApplicationFormRoute.tsx:121-123`
  (`chapterSelectField`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:125-137`
  (`responseValue` per-field reader),
  `services/web/src/features/public/ApplicationFormRoute.tsx:256-275`
  (`refreshPublicFormDefinition`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:277-297`
  (`refreshApplicantDiscordState`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:341-389`
  (`onSubmit`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:31-58`
  (`FALLBACK_FORM`),
  `services/web/src/features/public/ApplicationFormRoute.tsx:139-240`
  (`renderFormField` per-type dispatch). Reused; the
  wizard wraps these without re-implementing per-type
  rendering.
- `services/web/src/features/public/ApplicationFormRoute.tsx:80-119`
  (`preserveApplicationDraft` /
  `restoreApplicationDraft`) and the `DRAFT_KEY`
  sessionStorage convention. Reused; the visibility
  recompute layer runs after restore so hidden fields
  do not leak into the submit payload.
- `services/web/src/features/public/ApplicationFormRoute.tsx:299-339`
  (dialog focus trap, `onDialogKeyDown`,
  `dialogFocusableElements`). Reused unchanged — the
  Details dialog is independent of wizard state.
- `services/web/src/components/primitives/Button`
  — wizard `Next` / `Previous` / `Submit application`
  buttons reuse the same primitive that backs
  `ApplicationFormRoute.tsx:502-507`.

### Tests / e2e

- `services/api/tests/public_intake_fixtures.py`
  helpers `applicant_receipt_token` (lines 40-50),
  `audit_context` (lines 58-67),
  `seed_global_public_application_form` (lines 70-116),
  `create_real_member` (line 119+),
  `public_application_payload` (lines 24-37). All
  reused; β-2 adds a sibling
  `seed_global_multipage_form` helper (see New) but
  the receipt/audit/member plumbing stays identical.
- `services/api/tests/test_forms.py` — reused as the
  publish/read round-trip suite; β-2 adds rows for
  `page` and `visible_when` round-trip plus invalid
  predicate cases without restructuring the file.
- `services/api/tests/test_chapter_selector_submit.py`
  and `services/api/tests/test_public_intake_submit.py`
  — reused as the submit-time test surfaces. The β-1
  six-case `chapter_select` matrix (Positive 1–3 /
  Negative 1–3) must continue to pass; β-2 adds a
  guard case proving `chapter_select` cannot become
  hidden via `visible_when`.
- `services/web/tests/ApplicationFormRoute.spec.tsx`
  fixture builders (lines 14-74: `selectorForm`,
  `textOnlyForm`, `multiSelectForm`) and the
  `mockVerifiedApplicant` helper (line 76+). Reused;
  β-2 adds a `multiPageForm` and a `conditionalForm`
  fixture alongside.
- `services/web/tests/compat.spec.ts:53-60`
  (`payloadValue` dotted-path walker) and
  `services/web/tests/compat.spec.ts:115-141`
  (`publicSubmitApi` route stub). Reused; the
  payload-fields list grows but the stub semantics
  do not.
- `infra/tests/fixtures/web-ui/contract.json` — reused
  as the canonical fixture; β-2 extends `form.fields`
  with `page` markers and one conditional entry, and
  extends `submit.payload_fields` with the conditional
  response (see Modify in place).
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:91-108`
  (`field.type` dispatch loop). Already handles
  `chapter_select`, `select`, `multi_select`,
  `boolean`, and text/textarea. Reused; β-2 wraps the
  loop in a per-page submit-or-Next gate (see
  Modify in place) but does not change per-field
  filling.
- `infra/tests/e2e/tests/19-web-ui.sh:8-98`
  (`assert_public_submit_persisted`). Reused as the
  end-to-end assertion harness; the `target_scope` /
  `form_snapshot` checks stay; β-2 adds a `responses`
  visibility assertion (see Modify in place).
- `infra/tests/e2e/playwright/sessions/web-ui-public-submit.json`
  session-record convention. Reused; β-2 records the
  conditional answer alongside `selected_chapter_id`
  so the bash harness can assert it.

### GitOps / Kong

- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  — the v2 seed (`init-135:public-intake-global:v2`,
  lines 39-46) is reused as-is for β-2's local channel.
  Extending the seed to v3 with multi-page + conditional
  fields is anti-scope for this slice (proposal §2 Q5
  "JSON authoring is sufficient" — fixture-only).
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  and the catch-all Pomerium route
  (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:91-100`).
  Reused unchanged — no new ingress paths, no new
  Pomerium routes.

## New (write fresh)

### Backend (API)

- `app.contracts.applications.FormFieldVisibleWhen`
  (new class in
  `services/api/app/contracts/applications.py`,
  inserted near `_BaseFormField` around line 80).
  Shape locked at proposal §2 Q1:

  ```python
  class FormFieldVisibleWhen(_ApplicationModel):
      field_id: str
      op: Literal["eq", "neq", "in", "not_in"]
      value: JSONValue
  ```

  With validators: `field_id` must satisfy
  `FIELD_ID_PATTERN`
  (`services/api/app/contracts/applications.py:14`);
  `op in {"eq","neq"}` requires `value` to be a scalar
  (`str | int | float | bool`); `op in {"in","not_in"}`
  requires `value: list[scalar]` non-empty with no
  duplicates. Add to `__all__` (line 543+).
- `app.services.form_visibility` (new module at
  `services/api/app/services/form_visibility.py`),
  exporting `evaluate_visibility(fields:
  list[ApplicationFormField], responses: dict[str,
  Any]) -> dict[str, bool]`. Pure function: walks
  `fields` in authored order; for each field, evaluates
  `visible_when` against the running visible-response
  lookup; missing or hidden source responses make the
  predicate `False`; returns `{field_id: is_visible}`.
  Implementation choice: keeping this module separate
  from `services/applications.py` lets the predicate
  evaluator be unit-tested in isolation and shared
  between submit validation and any future seed-time
  authoring tools. Acceptable to inline as a private
  helper inside `services/applications.py` if the
  module-level import overhead is undesirable; flag
  the choice in the implementation PR.
- `services/api/tests/test_form_visibility.py` (or
  inlined cases inside
  `services/api/tests/test_public_intake_submit.py`)
  — predicate-evaluator unit tests for each op
  (`eq`, `neq`, `in`, `not_in`), missing-source-as-
  hidden, hidden-source-as-hidden, and authored-order
  invariants. These run without a database connection.
- `services/api/tests/test_visible_when_submit.py`
  (or extend `test_public_intake_submit.py`) —
  TG-2 / TG-3 server submit cases (see Tests).

### Frontend (SPA)

- `services/web/src/features/public/formVisibility.ts`
  — exports `evaluateVisibility(fields:
  PublicFormField[], responses: Record<string,
  unknown>) -> Record<string, boolean>`, mirroring the
  server-side evaluator op-for-op so client-side
  navigation, payload assembly, and required-field
  blocking all agree with the server's authoritative
  re-evaluation. Pure function; no Solid signals.
  Implementation choice: a separate `.ts` module makes
  it directly unit-testable in
  `services/web/tests/formVisibility.spec.ts`.
- `services/web/src/features/public/applicationWizard.ts`
  (or inline inside `ApplicationFormRoute.tsx`) —
  exports `derivePages(fields: PublicFormField[]):
  number[]` (sorted distinct `page` values) and
  `pageVisibleFields(fields, page, visibility):
  PublicFormField[]`. Wizard state itself
  (`currentPageIndex`, `responses` signal,
  `goNext` / `goPrevious`) is owned by the route
  component (Modify in place).
- `services/web/tests/formVisibility.spec.ts` (vitest
  or Playwright component test) — unit tests for the
  shared predicate evaluator and the page derivation
  helper. Independent of the rendered wizard.
- `services/web/tests/ApplicationFormRoute.wizard.spec.tsx`
  (or extend `ApplicationFormRoute.spec.tsx`) — TG-4
  multi-page + conditional cases (see Tests).

### Tests

- `services/api/tests/test_forms.py` — TG-1 cases:
  - publish/read round-trip with three pages and
    one `visible_when` field;
  - reject `page < 1`;
  - reject duplicate field ids (already covered;
    re-asserted with `page` set);
  - reject `visible_when` referencing a later field
    (forward reference);
  - reject `visible_when` referencing a same-page
    later field;
  - reject `visible_when` referencing an unknown
    `field_id`;
  - reject `visible_when` source field of type
    `multi_select` or `chapter_select`;
  - reject `visible_when` on a `chapter_select`
    field;
  - reject `op="in"` / `"not_in"` with non-list
    `value`;
  - reject `op="eq"` / `"neq"` with list `value`;
  - reject unknown `op`.
- `services/api/tests/test_visible_when_submit.py`
  (or extend `test_public_intake_submit.py`) — TG-2
  + TG-3 cases:
  - hidden required field omitted: 201;
  - visible required field omitted: 422;
  - visible required field blank string: 422
    (existing per-type validator fires);
  - hidden field submitted with a value: 422
    (rejected by hidden-key check);
  - controlling response toggles dependent visibility:
    submitting both controlling+dependent answers
    where predicate evaluates true → 201; submitting
    both where predicate evaluates false → 422 on the
    dependent value;
  - unknown response key still rejected (existing
    behavior preserved);
  - β-1 chapter-selector matrix (Positive 1–3,
    Negative 1–3) re-asserted alongside the new
    visibility pass — `chapter_select` cannot be
    hidden, `visible_when` cannot reference it.
  Risk annotation per case: `group=TG-2|TG-3;
  named_risk=visible_when_server_evaluates_authoritatively;
  level=component`.
- `services/web/tests/ApplicationFormRoute.wizard.spec.tsx`
  — TG-4 cases (multi-page fixture):
  - initial render shows page 1 fields and
    `Step 1 of N`;
  - `Next` blocks when a visible required field on
    the current page is empty;
  - `Next` advances after the visible required
    fields are filled;
  - `Previous` returns without losing entered
    values;
  - changing a controlling field shows/hides the
    dependent field;
  - hidden dependent field values are excluded from
    `submitPublicApplication` payload;
  - final `Submit application` posts visible filled
    fields from all pages, not only the last page;
  - if a page has no visible fields after toggle,
    wizard skips it for navigation and clamps
    progress.
- `services/web/tests/formVisibility.spec.ts` —
  predicate evaluator parity tests (each op,
  missing/hidden source, authored-order invariant).

## Modify in place (additive only)

### Backend (API)

- `services/api/app/contracts/applications.py:80-100`
  (`_BaseFormField`) — add two attributes:

  ```python
  page: int = Field(default=1, ge=1)
  visible_when: FormFieldVisibleWhen | None = None
  ```

  Every variant (`FormFieldShort`, `FormFieldLong`,
  `FormFieldNumber`, `FormFieldSelect`,
  `FormFieldMultiSelect`, `FormFieldBoolean`,
  `FormFieldChapterSelect`) inherits both. No
  per-variant override required for non-selector
  variants.
- `services/api/app/contracts/applications.py:172-189`
  (`FormFieldChapterSelect`) — pin
  `visible_when: None = None` so β-1 routing remains
  unconditional. Optionally pin `page: Literal[1] = 1`
  to keep the chapter selector on page 1 only; the
  proposal does not strictly require this and
  authoring conventions (`chapter_select` ordered
  first) typically achieve it implicitly. Implementation
  choice — flag in PR.
- `services/api/app/contracts/applications.py:215-256`
  (`FormDefinitionPublish`) — add a third
  `model_validator(mode="after")` named
  `validate_visible_when_graph` (sibling of
  `validate_unique_field_ids` and
  `validate_chapter_select_contract`). Walks
  `self.fields` in authored order, building a
  `seen_ids: dict[str, ApplicationFormField]`. For
  each field with `visible_when`:
  - referenced `field_id` must already be in `seen_ids`
    (forward reference and self reference both
    rejected);
  - referenced field's `type` must be in
    {`short`, `long`, `number`, `select`, `boolean`}
    (β-2 §2 Q1 — `multi_select` and `chapter_select`
    excluded);
  - referenced field must not be `chapter_select`
    (redundant with type-set check; explicit error
    message preferred);
  - the dependent field itself must not be
    `chapter_select` (cross-check with
    `validate_chapter_select_contract`).
  These checks live at the contract boundary, not in
  the service. Update `__all__` entry list to add
  `FormFieldVisibleWhen`.
- `services/api/app/services/applications.py:496-572`
  (`validate_application_responses`) — wrap the
  existing dispatch in a visibility pass. Approximate
  structural shape (no implementation):
  1. Build `field_list: list[ApplicationFormField]`
     in authored order via the existing TypeAdapter
     comprehension (line 506).
  2. Build `field_map: dict[str, ApplicationFormField]`
     as today.
  3. Compute `visibility = evaluate_visibility(
     field_list, responses)` from the new pure
     helper.
  4. Reject submitted keys whose corresponding field
     is hidden — emit through the existing
     "unknown response fields" error or a sibling
     "hidden response fields" error
     (`InvalidApplicationResponseError`); using a
     distinct error message helps test 422s
     differentiate visibility-bypass attempts from
     truly unknown fields.
  5. Required-key check (lines 515-523) limited to
     `visibility[field_id] is True`.
  6. Per-type dispatch (lines 525-572) iterates only
     visible submitted keys (existing loop already
     iterates `responses.items()`; with hidden keys
     rejected up-front, this is naturally satisfied).
  7. `chapter_select` active-chapter recheck
     (lines 557-572) untouched — `chapter_select` is
     always visible by contract, so the visibility
     pass cannot suppress it.
  Function signature stays
  `(fields, responses, *, connection, submitted_scope)`
  so call sites
  (`services/api/app/services/applications.py:814-819`)
  do not change.
- `services/api/app/services/applications.py:584-619`
  (`_chapter_selector_override`) — no body change.
  But the new contract validator
  (`validate_visible_when_graph`) plus the
  `FormFieldChapterSelect.visible_when: None`
  pinning together preserve the override gate's
  invariant that `_chapter_select_field_ids` returns
  exactly one id when a chapter-selector form is
  current. Add a regression test pinning that
  invariant
  (`services/api/tests/test_chapter_selector_submit.py`).
- `services/api/app/services/forms.py:55-60`
  (`_effective_routing_rules`) — no change. The
  `chapter_select` early-out remains; β-2 adds no
  new `review_scope` interactions.
- `services/api/app/api/v1/endpoints/public_application_forms.py:12-30`
  — no change. Response model `FormDefinitionRead`
  inherits the extended `_BaseFormField`, so `page`
  and `visible_when` serialize naturally.

### Frontend (SPA)

- `services/web/src/api/client.ts:33-37`
  (`basePublicFormFieldSchema`) — add two attributes:

  ```typescript
  page: z.number().int().min(1).default(1),
  visible_when: z
    .object({
      field_id: z.string(),
      op: z.enum(["eq", "neq", "in", "not_in"]),
      value: z.unknown(),
    })
    .nullable()
    .optional(),
  ```

  All variants inherit both. The
  `chapter_select` variant
  (`services/web/src/api/client.ts:62-66`) gains
  `visible_when: z.null().optional()` to mirror the
  server pin.
- `services/web/src/api/client.ts:218-220` —
  `PublicFormField` type alias picks up `page` and
  `visible_when` automatically through `z.infer`. No
  manual edit required.
- `services/web/src/features/public/ApplicationFormRoute.tsx:1`
  — import the new `formVisibility` helper and the
  `evaluateVisibility` / `derivePages` exports.
- `services/web/src/features/public/ApplicationFormRoute.tsx:242-254`
  (component opening + signal block) — add three
  signals:
  - `currentPageIndex: createSignal<number>(0)`;
  - `responses: createSignal<Record<string, unknown>>({})`
    — wizard state across pages;
  - derived `visibility`, `pages`, `currentVisibleFields`
    via `createMemo` over `formDefinition()` and
    `responses()`.
  Existing signals (`authState`, `activeTab`,
  `dialogOpen`, `submitStatus`, `formDefinition`,
  `publicChapters`) reused unchanged.
- `services/web/src/features/public/ApplicationFormRoute.tsx:341-389`
  (`onSubmit`) — replace the `Object.fromEntries`
  pass over all `form.fields` (line 360-362) with
  a pass over visible fields only:
  - read final `responses()` signal value (which has
    been kept in sync as the user navigated);
  - filter to `field_id` where
    `visibility[field_id] === true`;
  - assemble the submit payload from that filtered
    map.
  Existing chapter-selector branch (lines 363-372)
  is reused; `chapterSelectField` always returns
  the always-visible `chapter_select`.
- `services/web/src/features/public/ApplicationFormRoute.tsx:80-119`
  (`preserveApplicationDraft` /
  `restoreApplicationDraft`) — extend restore to
  recompute visibility after writing values back to
  form elements and clear hidden field values from
  the `responses()` signal. The sessionStorage key
  (`DRAFT_KEY`) and persistence shape stay the same.
- `services/web/src/features/public/ApplicationFormRoute.tsx:492-508`
  (form body) — wrap the existing
  `formDefinition().fields.map(...)` call in a
  wizard layout:
  - render only `currentVisibleFields()` for the
    current page;
  - add a progress line `Step {currentPageIndex()+1}
    of {visiblePages().length}`;
  - replace the single `Submit application` button
    with `Previous`, `Next`, and `Submit application`
    where `Submit application` shows only on the
    last visible page. Preserve the
    `application-submit-icon` test id on the final
    submit button so existing tests continue to pass;
  - `Next` runs HTML5 validity + visibility check on
    the current page's required visible fields before
    incrementing `currentPageIndex`;
  - `Previous` decrements without validation;
  - both navigation buttons skip pages whose visible
    field set is empty after recomputation.
- `services/web/src/features/public/ApplicationFormRoute.tsx:31-58`
  (`FALLBACK_FORM`) — add `page: 1` to both fallback
  fields (or rely on the schema default). No new
  fallback fields; the fallback shape stays a single
  page so no FALLBACK_FORM wizard regressions.

### GitOps / e2e

- `infra/tests/fixtures/web-ui/contract.json:99-165`
  — extend `form` block:
  - add `page` to each existing field entry (e.g.
    `chapter` and `character_name` on page 1,
    `application_text` on page 2);
  - add one new conditional field on page 2 with a
    `visible_when` predicate keyed on
    `character_name` truthy or a select/boolean
    helper field. (Implementation choice: pick the
    fixture so the conditional resolves to visible
    when the canonical fixture answers are filled,
    so the existing payload-fields list need only
    grow, not shrink.);
  - extend `submit.payload_fields` with the
    conditional response under
    `responses.<conditional_field_id>` and a
    `source_field` reference;
  - bump no field names that already feed
    e2e/Postgres assertions
    (`character_name`, `application_text`,
    `chapter` stay the same).
- `infra/tests/validate_web_ui_local.sh` field-name
  set assertions (cf. β-1 hookpoints
  `lines 118-124, 155-156`) — extend the assertion
  set to include the conditional field id.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:91-108`
  — wrap the `field.type` dispatch loop in a
  per-page submit gate. Approximate shape:
  - read `webContract.form.pages` (or derive from
    `field.page`);
  - for each page index `< last`: fill that page's
    fields, click `Next`, wait for the next page's
    first field locator to appear;
  - on the last page: fill, then click
    `Submit application`.
  Keep `selectedChapterId` capture
  (browser-flow.mjs:98) and the session record
  write (browser-flow.mjs:134-142) intact; add a
  `conditional_response` entry to the session record
  so the bash harness can assert it.
- `infra/tests/e2e/tests/19-web-ui.sh:8-98`
  (`assert_public_submit_persisted`) — extend the
  Postgres SELECT to read
  `a.responses->>'<conditional_field_id>'` and
  assert it equals the recorded conditional answer.
  Add a negative assertion that any
  ` always-hidden` fixture field id is `NULL` /
  absent in `responses`. Keep all β-1 assertions
  (state, target_scope, snapshot, notification
  fan-out) intact.
- `services/web/tests/compat.spec.ts:18-30, 115-141`
  — add `page` and conditional field entries to the
  `Contract` type (lines 18-37) and the
  `publicSubmitApi` route stub
  (`payloadValue` walker already supports
  dotted-path access for the new
  `responses.<conditional_field_id>` field; only the
  fixture data changes).

## Anti-scope (β-3) — do NOT touch

- File upload, presigned URLs, object storage,
  malware scanning, attachment response value type,
  or any new field variant. β-3 owns this entirely
  (proposal §5).
- Conditional pages or page-level predicates. Pages
  are derived from per-field `page` values and skipped
  only when their visible field set is empty. Do not
  add a top-level `pages: list[...]` schema, page
  titles, or per-page `visible_when`
  (proposal §2 Q2 + Q6).
- Chapter-selector interaction with `visible_when`.
  `FormFieldChapterSelect.visible_when` stays pinned
  to `None`, `chapter_select` stays always visible
  and routing-only, and `visible_when.field_id`
  cannot reference a `chapter_select` field
  (proposal §2 Q1 + Q6, §3 Submit Validator).
- Per-page submit API, draft API, server-side step
  tracking, or any new persisted state outside the
  existing `applications.responses` JSONB
  (proposal §1, §5).
- New form-builder admin UI, chapter officer
  authoring surface, or chapter creation/deletion
  endpoint. JSON authoring + the existing
  `services/api/app/api/v1/endpoints/forms.py`
  publish surface remain the only authoring path
  (proposal §2 Q5, §5).
- New schema migration. JSONB
  `form_definitions.fields` and
  `applications.responses` accept `page` /
  `visible_when` without an Alembic head bump beyond
  the current
  `wu_045_app_public_submit_notify`
  (β-1 hookpoints F-section reference).
- Officer review surfaces
  (`services/api/app/api/v1/endpoints/web.py:172-408`,
  `services/api/app/services/web.py`,
  officer queue/detail/transcript/messages routes).
  These read `responses` and `form_snapshot` as
  opaque maps and require no β-2 edit.
- Live Discord writes, channel changes, role/permission
  edits, or any change to
  `emit_application_public_submitted_event`
  (`services/api/app/services/applications.py:65-68,
  971-980`). Notification fan-out stays β-1.
- Backwards-compatibility aliases (`field_id`,
  `field_type`, parallel field unions, dual
  `visible_when` shapes). Existing JSON keys (`id`,
  `type`, `label`, `required`, `placeholder`,
  `max_length`, `options`) remain byte-compatible;
  `page` and `visible_when` are the only additions
  (proposal §3 Contracts).
- Feature flags or environment toggles.
  `visible_when` is gated on field-level presence;
  `page` defaults to `1`. No
  `ENABLE_MULTI_PAGE_FORMS` switch
  (proposal §2 Q5, §5).
- Predicate-language extensions: no JSONLogic, no
  dotted boolean expressions, no `and`/`or`/`not`
  composition, no `gt`/`lt`/`gte`/`lte`/`contains`
  ops. Supported ops are exactly
  {`eq`, `neq`, `in`, `not_in`} for β-2
  (proposal §2 Q1).
- Reusing a `multi_select` field as a predicate
  source. Beta-2 sources are scalar fields only
  (proposal §2 Q1).

HOOKPOINTS_DONE: research/40-init-136-hookpoints.md
