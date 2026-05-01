# Proposal 27 - INIT-136 / BL-010 beta-2: multi-page and conditional fields

## 1. Problem Statement

INIT-136 ships BL-010 beta-2: public application forms can be divided into ordered pages with progress indication, and individual fields can be conditionally visible based on earlier applicant responses. This follows the BL-010 decomposition in `research/28-bl-010-problem-map.md`: beta-1 delivered chapter selection and chapter-scoped submit, beta-2 owns multi-page plus conditional fields, and beta-3 owns file upload.

The submit response shape stays the beta-1 shape: `responses: dict[str, JSON]`. There is no per-page submit API and no draft API in this slice. The browser preserves cross-page answers locally, then posts every currently visible field the applicant filled. Hidden fields are not rendered, not browser-validated, not submitted, and not server-validated as required.

The server remains authoritative. The submit path re-evaluates conditional visibility against the submitted response set before persistence, so client-side bypasses cannot smuggle hidden fields or skip visible required fields.

## 2. Decisions

### Q1. `visible_when` predicate language: simple single predicate

Use option a: a small predicate object on each field:

```json
{
  "visible_when": {
    "field_id": "prior_field",
    "op": "eq",
    "value": "yes"
  }
}
```

Supported ops are `eq`, `neq`, `in`, and `not_in`.

Semantics:

- `eq`: referenced response strictly equals `value`.
- `neq`: referenced response does not strictly equal `value`.
- `in`: referenced response is one of the scalar values in `value`.
- `not_in`: referenced response is not one of the scalar values in `value`.

For beta-2, predicate sources are scalar fields only: `short`, `long`, `number`, `select`, and `boolean`. Do not allow `multi_select` or `chapter_select` as predicate sources. This keeps the language deterministic and avoids array containment semantics or chapter-routing coupling. The referenced `field_id` must appear earlier in `form_definition.fields`; same-page references are allowed only when the source field is ordered before the dependent field. Missing or hidden source responses evaluate the predicate as false.

Do not use JSONLogic or dotted boolean expressions in this slice. They are larger surface areas than the current form builder and submit validator need.

### Q2. Page model: `page` attribute on fields

Use option i: add `page: int` to each field, 1-indexed, with default `1`. Pages are derived from the distinct page numbers in the ordered field list. This is the smallest contract change because `form_definitions.fields` is already the rendered and persisted unit, and beta-1 established the discriminated `ApplicationFormField` union pattern in `services/api/app/contracts/applications.py`.

Validation rules:

- `page >= 1`.
- Page numbers may be sparse in authored JSON, but API read normalizes the runtime page sequence by sorting distinct page values. The UI displays contiguous steps based on that derived order.
- A field's `visible_when.field_id` must reference an earlier field, not merely an earlier page number.
- No top-level `pages` list in beta-2. Page titles, page-level conditions, and per-page metadata are future work.

### Q3. SPA navigation: wizard with page indicator

Render the public form as a wizard:

- Current page shows only visible fields assigned to that page.
- Progress text shows `Step N of M`.
- `Next` validates visible required fields on the current page before advancing.
- `Previous` returns to the prior derived page without losing local responses.
- `Submit application` appears only on the last derived page.

This fits the existing `ApplicationFormRoute.tsx` runtime renderer. It needs local step state and visibility evaluation, not a new route or server round-trip.

When a prior response changes, the SPA must recompute visibility for all fields, remove hidden field values from the pending payload, and clamp the current page to the last still-reachable page if the current page no longer has any visible fields. If a page has no visible fields after recomputation, the wizard skips it for navigation and progress.

### Q4. API validation: server re-evaluates `visible_when`

Yes. The submit path must re-evaluate the visible field set server-side.

`validate_application_responses` currently parses fields, rejects unknown response keys, checks required fields, and validates per-type values in `services/api/app/services/applications.py`. INIT-136 extends that validator so:

- Hidden fields submitted by the client are rejected as invalid response fields.
- Required fields are required only when their field is visible in the final visibility graph.
- Optional visible fields may be omitted.
- Submitted visible fields are type-validated with the existing per-type rules.
- The existing `chapter_select` validation and active chapter check remain intact.

Because final public submit is the only API write in this slice, the server treats final submission as all derived pages having been reached. The "page reached" rule is enforced in the browser's Next/Prev flow; the final server check validates the complete visible response set for the final form state.

### Q5. Form publishing: JSON authoring is sufficient

JSON upload / API publishing is sufficient for beta-2. Do not add a chapter officer form-builder admin UI in this slice. Contract validation must make authored JSON safe enough to publish: invalid page numbers, duplicate field ids, invalid predicates, forward references, and unsupported predicate sources fail at publish time.

If seed data is updated, keep the beta-1 seed discipline: deterministic JSON form payloads, no schema migration for JSONB field expansion, and no officer-published form overwrite.

### Q6. Anti-scope decisions

File upload remains beta-3.

Do not add conditional page support. Only fields have `visible_when`; pages are visible when they contain at least one visible field.

Do not add chapter-selector conditional routing. In beta-2, `chapter_select` remains the beta-1 routing field and must be always visible when present. It cannot have `visible_when` and cannot be referenced by another field's `visible_when`.

Do not add chapter creation/deletion UI or a form-builder admin UI.

## 3. Substrate

### Contracts

Modify `services/api/app/contracts/applications.py`.

The actual field contract lives in this file, not a separate `contracts/form_definitions.py`. It already defines `_BaseFormField`, typed field variants, `FormFieldChapterSelect`, and `ApplicationFormField = Annotated[..., Field(discriminator="type")]`. INIT-136 should extend the shared field base rather than duplicating each variant.

Add:

- `FormFieldVisibleWhen` model with `field_id`, `op`, and `value`.
- `page: int = Field(default=1, ge=1)` on `_BaseFormField`.
- `visible_when: FormFieldVisibleWhen | None = None` on `_BaseFormField`.
- Publish-time validation in `FormDefinitionPublish` for page values, predicate source existence, earlier-field ordering, supported source field types, and `chapter_select` restrictions.

Keep the existing `id` / `type` JSON keys. Do not introduce `field_id`, `field_type`, aliases, feature flags, or old/new dual support.

Update the SPA Zod form contract in `services/web/src/api/client.ts` to mirror `page` and `visible_when` on `publicFormFieldSchema`.

### Public Form Endpoint

`services/api/app/api/v1/endpoints/public_application_forms.py` can keep the same endpoint and response model: `GET /api/v1/public/application-forms/current` returns `FormDefinitionRead`.

No new public form endpoint is needed. The endpoint should naturally serialize the extended field models in `fields`. Existing browser path rewriting keeps the SPA call at `/api/public/application-forms/current`.

### SPA Renderer

Modify `services/web/src/features/public/ApplicationFormRoute.tsx`.

Current state:

- It fetches the public form and renders `formDefinition().fields.map(...)`.
- It already has data-driven rendering for `short`, `long`, `number`, `select`, `multi_select`, `boolean`, and `chapter_select`.
- Submit currently builds responses from every field in `form.fields`.

Required beta-2 extension:

- Derive ordered pages from `form.fields`.
- Track the current derived page in a Solid signal.
- Track local response state across pages instead of reading only final `FormData` at submit.
- Evaluate `visible_when` in a shared pure helper used by render, navigation, and submit payload assembly.
- Render only visible fields for the current derived page.
- Skip derived pages that have no visible fields.
- Build the final `responses` payload from visible fields only, across all pages, not only the current page.
- Keep `chapter_select` submit behavior from beta-1: if the current form has the always-visible chapter selector, submit `scope_kind="chapter"` with the selected chapter id; otherwise submit global.

Draft preservation should keep working through `sessionStorage`, but restore must not revive hidden fields into the submit payload after visibility recomputation.

### Submit Validator

Modify `validate_application_responses` in `services/api/app/services/applications.py`.

The current validator already:

- Parses raw field dictionaries through `_APPLICATION_FORM_FIELD_ADAPTER`.
- Rejects unknown response keys.
- Checks required fields.
- Type-validates submitted values.
- Handles `chapter_select` active-chapter checks.

Extend it with a deterministic visibility pass:

1. Parse fields and preserve authored order.
2. Build a response lookup from submitted responses.
3. For each field in order, evaluate `visible_when` using only earlier visible source fields.
4. Produce the visible field map.
5. Reject submitted response keys whose field is hidden.
6. Require only visible required fields.
7. Type-validate submitted visible values.

This pass must run after `_chapter_selector_override` selects the effective form row and before persistence, at the existing call site inside `_submit_application_internal`.

The beta-1 chapter-selector override gate must remain narrow: it should still fire only when the current global form contains the required `chapter_select` field and the submitted chapter scope matches the selector response. INIT-136 must not let conditional visibility hide that routing field or turn chapter routing into a conditional form feature.

## 4. Test Plan

### TG-1: contract - `visible_when` serializes and round-trips

Extend API form contract tests so a published form with multiple pages and a conditional field round-trips through publish/read with:

- `page` preserved.
- `visible_when` preserved.
- `ApplicationFormField` union parsing still accepts all existing field types plus `chapter_select`.
- Invalid predicates fail: unknown source, forward reference, unsupported source type, invalid op, `in` / `not_in` with non-list value, `visible_when` on `chapter_select`, and duplicate field ids.

Also extend `services/web/src/api/client.ts` schema tests or component fixtures so the browser accepts the new public form shape.

### TG-2: submit - hidden required fields are skipped; visible required fields are enforced

Add submit tests around `validate_application_responses` and public submit:

- A required field on page 2 with `visible_when` false may be omitted and the submit succeeds.
- The same required field with `visible_when` true must be present.
- If present but blank, the existing field-type required validation fires.
- A required always-visible field on any derived page remains required on final submit.

Although this test group may describe "hidden page" behavior, beta-2 implements field-level conditions only: the page is skipped only because it has no visible fields.

### TG-3: submit - server-side `visible_when` rejects client bypass

Add submit tests proving the server does not trust the SPA:

- If the client submits a response for a field whose predicate evaluates false, submit returns validation error.
- If the client omits a field whose predicate evaluates true and `required=true`, submit returns validation error.
- If the client submits an unknown field id, the existing unknown-field validation still returns validation error.
- If the controlling response changes from true to false, stale dependent field values are rejected.

Keep beta-1 chapter-selector override tests passing and add one guard case proving `chapter_select` cannot be hidden or used as a predicate source.

### TG-4: SPA - multi-page navigation and conditional rendering

Extend `services/web/tests/compat.spec.ts` or add a focused public-form spec:

- Public form fixture contains at least two pages.
- Initial render shows page 1 fields and `Step 1 of 2`.
- `Next` blocks when visible required fields on the current page are empty.
- `Next` advances after current visible required fields are filled.
- `Previous` returns without losing entered values.
- Changing a controlling field toggles the dependent field.
- Hidden dependent field values do not appear in the submitted payload.
- Final submit posts visible filled fields from all pages, not only the last page.

### TG-5: e2e - extend test 19 with multi-page fixture path

Extend `infra/tests/e2e/tests/19-web-ui.sh` and the Playwright browser flow fixture path so test 19 exercises:

- A public form with at least two pages.
- A conditional required field that becomes visible from an earlier answer.
- Navigation through Next/Previous.
- Final persisted application `responses` contains the visible fields and omits hidden fields.

Keep the existing beta-1 chapter-scoped assertion intact if the e2e fixture still includes `chapter_select`.

## 5. Anti-Scope

- File upload, object storage, presigned URLs, malware scanning, and attachment response values. That is beta-3.
- Form-builder admin UI beyond JSON upload / API publishing.
- Conditional pages or page-level predicates. Pages are derived from field page numbers and skipped only when they contain no visible fields.
- Chapter selector interaction with conditional visibility. `chapter_select` stays always visible and routing-only for this slice.
- Chapter creation/deletion UI.
- New submit response shape, per-page save API, draft persistence API, or server-side step tracking.
- Live Discord-visible writes, messages, channel changes, role changes, kicks, bans, or permission edits.
- Backwards-compatibility aliases, deprecated field names, feature flags, transitional code paths, or placeholder stubs.

## 6. Diff Budget

Estimated net: +760 / -80 lines.

- API contracts and publish validation: +170 / -20.
- Submit visibility evaluator and validation tests: +210 / -30.
- SPA Zod schema, wizard state, renderer, and payload assembly: +190 / -30.
- SPA component tests and fixture updates: +120.
- E2E test 19 fixture/browser-flow updates: +70.

This should remain one PR. If implementation exceeds roughly 1,100 net lines, split only along deployable boundaries: first API contract plus server validation, then SPA/e2e wiring. Do not split by adding parallel old/new field names, compatibility shims, or feature flags.
