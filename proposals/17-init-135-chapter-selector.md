# Proposal 17 - INIT-135 / BL-010 beta-1: Chapter selector

## 1. Goal

INIT-135 ships BL-010 beta-1: a public application form field that lets an applicant select an active chapter, validates that selection through the API, and creates a chapter-scoped application from the existing public intake flow. The slice keeps the public form definition globally published so the BL-002 seed-public-intake form path remains intact, but the selected chapter becomes the submitted application's target scope. Out of scope: multi-page forms, conditional fields, and file upload, which remain beta-2/beta-3 (`plans/BACKLOG.md:323-334`, `research/28-bl-010-problem-map.md:8-18`).

## 2. Locked Decisions Q1..Q7

### Q1. Decomposition: beta-1 only

Lock this INIT to the chapter selector and chapter-scoped submit path. BL-010 contains four separate features, but the problem map already separates chapter selector as beta-1 and reserves multi-page/conditional fields and file upload for beta-2/beta-3 (`research/28-bl-010-problem-map.md:49-62`). This keeps the change focused on one new field type, one public chapter list endpoint, SPA rendering, fixtures, and submit validation.

### Q2. Public chapter list endpoint: wrapper response, active chapters only

Add a public `GET /api/public/chapters` surface that returns active chapters only as `{"chapters": [{"id": "...", "name": "..."}]}`. The problem map suggested a raw list (`research/28-bl-010-problem-map.md:64-68`), but the existing admin chapter endpoint already uses a wrapped `chapters` collection (`services/api/app/contracts/web.py:39-48`) and the SPA client already has a matching `chapterListSchema` wrapper (`services/web/src/api/client.ts:12-22`). The public response intentionally omits `state`, `version`, `created_at`, templates, configuration, and Discord resources; those remain admin-only (`services/api/app/api/v1/endpoints/web.py:64-69`, `services/api/app/repositories/web.py:9-21`).

### Q3. New field type: `chapter_select`

Add `chapter_select` to the form definition field union using the existing `id`/`type` naming, not new `field_id`/`field_type` keys. The requested `services/api/app/contracts/form_definitions.py` path is not present in this worktree; the actual contract lives in `services/api/app/contracts/applications.py`, where current fields are keyed by `id` and discriminated by `type` values such as `short`, `long`, and `select` (`services/api/app/contracts/applications.py:80-143`). `chapter_select` is a real response field: the selected chapter id is submitted in `responses[<field_id>]` and must match `scope.scope_id`.

### Q4. Submit flow: selected chapter drives target scope

When the current global public form contains exactly one required `chapter_select` field, the SPA submits `scope: {"scope_kind": "chapter", "scope_id": selectedChapterId}` and includes the same selected id in the chapter-select response. The public submit service must accept that chapter scope, validate the selected chapter against the active public chapter list, and persist `target_scope_kind="chapter"` plus `target_scope_id=<selectedChapterId>`. Existing global submission remains valid for forms that do not contain a `chapter_select` field (`research/28-bl-010-problem-map.md:85-91`).

### Q5. Form lookup: global form definition, chapter target

The form lookup remains global for the public chapter-selector form. Current submit code looks up the form using the submitted scope (`services/api/app/services/applications.py:708-714`), so a direct chapter-scoped public submit would look for a chapter-specific form and miss the seeded global form. INIT-135 changes the public submit path so chapter-selector submissions validate against the current global form while overriding the application target scope to the selected chapter. This preserves the seed-public-intake form's global scope (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:36-45`) and fixes the beta-1 chapter routing gap.

### Q6. Test shape

Tests cover the contract at API, SPA, and local e2e layers. API tests prove `chapter_select` form definitions round-trip, the public chapter list returns only active chapters, and public submit accepts a chapter scope from the global form. SPA tests prove the select renders, requires a value, and posts both the chapter scope and chapter-select response. E2e extends test 19 to verify the persisted application is chapter-scoped in Postgres (`research/28-bl-010-problem-map.md:100-108`, `infra/tests/e2e/tests/19-web-ui.sh:8-80`).

### Q7. Anti-scope boundary

Do not add multi-page form state, conditional visibility, upload storage, presigned URLs, chapter creation/deletion UI, officer review workflow changes, or live Discord-visible actions. These are explicitly outside beta-1 (`research/28-bl-010-problem-map.md:110-115`) and Discord-visible writes remain Tier 3 under AGENTS (`AGENTS.md:18-26`).

## 3. Scope

### Migration

No Alembic schema migration. `form_definitions.fields` is already JSONB-backed and persists serialized field dictionaries (`services/api/app/services/forms.py:87-110`), so adding a new field variant is a contract/service validation change, not a table change. If a later implementation discovers a schema migration is unavoidable, it must follow current head `wu_045_app_public_submit_notify` (`migrations/versions/wu-045_application_public_submit_notifications.py:10-13`), but the intended beta-1 path has no migration.

The seed job is a data/config change, not an Alembic migration: update the local `seed-public-intake-form` SQL so fresh environments seed a global current form that includes `chapter_select`, and existing environments only advance the deterministic seed form when the current global form is still the prior seed. If an officer-published global form is current, keep the existing no-op behavior (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:193-211`). This preserves BL-002's fail-closed seed invariant (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`).

Seed v2 uses a new deterministic UUID, for example `digest('init-135:public-intake-global:v2', 'sha256')`, rather than reusing the v1 seed id. The SQL inserts v2 only when no current global form exists or when the current global form is the deterministic v1 seed. The v1 -> v2 advance happens in one transaction: archive v1 with `status='archived'` and `archived_at`, insert v2 as current, write the `form.publish` action and `form.published` state-change with `version: 2`, bump the aggregate version, and update `aggregate_heads.current_seq=2`. Preserve the "officer-published form present; skipping seed" branch when current is neither the v1 nor v2 deterministic seed, and preserve the BL-002 fail-closed guard at `seed-public-intake-form.yaml:14-31`.

### New files

- `services/api/app/contracts/public_chapters.py` - `PublicChapterSummaryRead` and `PublicChapterListRead`.
- `services/api/app/api/v1/endpoints/public_chapters.py` - unauthenticated public chapter list route mounted at the API's v1 public path and exposed to the SPA as `/api/public/chapters`. The route must not include `get_pomerium_principal`, `verify_applicant_receipt`, or any identity dependency; the endpoint docstring must state the public-no-auth posture.
- `services/api/app/services/public_chapters.py` - active-only list service.
- `services/api/tests/test_public_chapters.py` - endpoint contract and active-filter coverage.

### Modified files

- `services/api/app/contracts/applications.py` - replace the monolithic `ApplicationFormField` shape with a discriminated union over existing field variants plus `FormFieldChapterSelect`, keeping existing `id`/`type` JSON keys (`services/api/app/contracts/applications.py:80-143`).
- `services/api/app/services/forms.py` - keep `publish_form` serialization via `field.model_dump(mode="json")`; adjust `_effective_routing_rules` so a global form containing `chapter_select` does not default `review_scope` to global and can be targeted by the submitted chapter (`services/api/app/services/forms.py:55-59`, `services/api/app/services/forms.py:78-110`).
- `services/api/app/services/applications.py` - add public-submit chapter-selector handling: validate the selected chapter response, use the current global form for validation, and persist target scope from the submitted chapter (`services/api/app/services/applications.py:473-490`, `services/api/app/services/applications.py:493-548`, `services/api/app/services/applications.py:676-829`, `services/api/app/services/applications.py:845-896`).
- `services/api/app/api/v1/router.py` - mount the new public chapter endpoint alongside existing v1 routers (`services/api/app/api/v1/router.py:36-58`).
- `services/web/src/api/client.ts` - add public chapter and form-definition schemas/fetch helpers; keep submit as the existing `/api/public/applications` POST surface (`services/web/src/api/client.ts:206-221`, `services/web/src/api/client.ts:277-290`).
- `services/web/src/features/public/ApplicationFormRoute.tsx` - replace the current hardcoded two-field renderer with data-driven field rendering, including a chapter select populated from `/api/public/chapters` (`services/web/src/features/public/ApplicationFormRoute.tsx:10-20`, `services/web/src/features/public/ApplicationFormRoute.tsx:172-183`, `services/web/src/features/public/ApplicationFormRoute.tsx:300-328`).
- `infra/tests/fixtures/web-ui/contract.json` - add the chapter field, public chapter endpoint fixture, selected chapter fixture, and chapter-scoped submit payload expectations (`infra/tests/fixtures/web-ui/contract.json:99-141`).
- `infra/tests/validate_web_ui_local.sh` - update fixture assertions from two hardcoded fields to the richer contract and require `/api/public/chapters` coverage (`infra/tests/validate_web_ui_local.sh:118-124`, `infra/tests/validate_web_ui_local.sh:155-156`).
- `services/web/tests/compat.spec.ts` - mock the public chapter endpoint and assert the chapter select posts the selected scope and response (`services/web/tests/compat.spec.ts:18-30`, `services/web/tests/compat.spec.ts:115-140`, `services/web/tests/compat.spec.ts:278-299`).
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` - fill select fields from the web contract and persist the selected chapter id in the submit session record (`infra/tests/e2e/lib/playwright/browser-flow.mjs:91-129`).
- `infra/tests/e2e/tests/19-web-ui.sh` - assert `applications.target_scope_kind='chapter'`, `target_scope_id=<selectedChapterId>`, and the form snapshot remains sourced from the global public form (`infra/tests/e2e/tests/19-web-ui.sh:8-80`).
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` - seed a global public form with `chapter_select` while preserving the BL-002 no-op/fail-closed behavior (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:33-50`, `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:193-211`).
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml` and `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` - expose/rate-limit the public chapters path next to the existing public submit path (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:33-43`, `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:21-30`).

### Tests

- API contract tests in `services/api/tests/test_forms.py` for publishing/reading `chapter_select` (`services/api/tests/test_forms.py:88-175`).
- API submit tests in `services/api/tests/test_public_intake_submit.py` and fixtures in `services/api/tests/public_intake_fixtures.py` for chapter-selector public submit (`services/api/tests/test_public_intake_submit.py:48-139`, `services/api/tests/public_intake_fixtures.py:71-117`).
- Public chapters endpoint tests in the new `services/api/tests/test_public_chapters.py`.
- SPA compatibility tests in `services/web/tests/compat.spec.ts`.
- Local validators and e2e test 19 updates (`infra/tests/validate_application_workloads_local.sh:207-213`, `infra/tests/e2e/tests/19-web-ui.sh:238-268`).

### Form definition changes

- Existing field variants remain accepted with the same JSON keys and semantics.
- `chapter_select` is allowed only on global application forms for this slice.
- A form may contain at most one `chapter_select`.
- `chapter_select.required` is locked to `true` for beta-1.
- A public submit using a chapter selector must include the selected id in both `responses[chapterFieldId]` and `scope.scope_id`; mismatch is a 422 validation error.

### Audit r1 implementation pitfalls

- `services/api/app/services/applications.py:499` currently calls `ApplicationFormField.model_validate(raw)` inside `validate_application_responses`. After the contract refactor, `ApplicationFormField` is a `TypeAlias` for `Annotated[Union[...], Field(discriminator="type")]` and does not expose `.model_validate`. Implementation must switch this call site, and any other direct `.model_validate` on the alias, to `pydantic.TypeAdapter(ApplicationFormField).validate_python(raw)` or an equivalent root-model wrapper.
- The form-lookup override must be gated to public chapter-selector submissions only: current global form contains exactly one required `chapter_select`, request sends `scope_kind=chapter`, and the submitted chapter response matches `scope.scope_id`. Non-selector forms must continue through the existing exact-scope lookup.
- The seed SQL must handle both fresh insert and v1 -> v2 advance. A current officer-published global form remains a no-op, and the BL-002 fail-closed guard remains before mutation.
- The public chapter endpoint is intentionally unauthenticated at the FastAPI layer. The audit gate's observation that current ingress relies on an implicit public catch-all is a follow-up note, not a beta-1 blocker; if later Pomerium work adds an explicit `/api/public/` route, it should use `allow_public_unauthenticated_access: true` and `pass_identity_headers: false`.

## 4. API Surface

### `GET /api/public/chapters`

Public, unauthenticated, active-only. Internally this should mount under the v1 API router consistently with existing API paths, then be exposed at the web/public path in local ingress the same way `/api/public/applications` maps to the existing `/api/v1/public/applications` route (`services/api/app/api/v1/endpoints/applications/public.py:22-47`, `services/web/src/api/client.ts:277-290`, `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:37-43`, `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:24-30`).

Response:

```json
{
  "chapters": [
    {"id": "chapter-id", "name": "Chapter name"}
  ]
}
```

The repository query should read from `chapters`, filter `state = 'active'`, order by `name ASC`, and cap at 200. It can reuse the chapter table shape already read by admin listing, but must not expose admin-only columns (`services/api/app/repositories/web.py:9-21`, `services/api/app/contracts/web.py:39-48`).

### Form definition field type addition

Add `type: "chapter_select"` to the API form field contract. The persisted JSON continues to live in `form_definitions.fields`; no table change is required (`services/api/app/services/forms.py:87-110`). Response validation extends `validate_application_responses` so `chapter_select` values must be strings, non-blank when required, and an active chapter id (`services/api/app/services/applications.py:493-548`).

### Submit endpoint behavior with chapter scope

`POST /api/public/applications` auth remains receipt-backed (`services/api/app/api/v1/endpoints/applications/public.py:25-47`). For a global public form containing `chapter_select`, a request with `scope_kind="chapter"` is valid when:

- `scope.scope_id` is present.
- The chapter exists and is active.
- The chapter-select response field exists.
- The response value equals `scope.scope_id`.
- The form used for validation is the current global public form.

Persisted application behavior:

- `form_snapshot.scope_kind` / `form_snapshot.scope_id` remain the form-definition source: `global` / `null`.
- `form_snapshot.target_scope` and application row `target_scope_kind` / `target_scope_id` become the selected chapter.
- Forms without `chapter_select` keep existing global behavior.

This is a targeted public-submit change. Authenticated chapter-specific submit remains the existing exact-scope form lookup path (`services/api/app/services/applications.py:708-734`, `services/api/app/services/applications.py:832-842`).

## 5. Component Contract Preview

### Pydantic `FormFieldChapterSelect`

```python
class FormFieldChapterSelect(_ApplicationModel):
    id: str
    type: Literal["chapter_select"]
    label: str
    required: Literal[True] = True
    placeholder: str | None = None
```

The full field contract should become a Pydantic discriminated union over `type`, preserving current variants and JSON:

```python
ApplicationFormField = Annotated[
    FormFieldShort
    | FormFieldLong
    | FormFieldNumber
    | FormFieldSelect
    | FormFieldMultiSelect
    | FormFieldBoolean
    | FormFieldChapterSelect,
    Field(discriminator="type"),
]
```

The contract keeps current `FIELD_ID_PATTERN` and label validation rules (`services/api/app/contracts/applications.py:14-14`, `services/api/app/contracts/applications.py:88-103`).

### SPA chapter-select rendering

The SPA loads the current global form definition, renders each field by API `type`, and loads public chapters only when at least one `chapter_select` field is present. For `chapter_select`, it renders a native `<select>` with an empty disabled placeholder option and active chapter options. On submit, it includes:

```json
{
  "scope": {"scope_kind": "chapter", "scope_id": "selected-chapter-id"},
  "responses": {
    "chapter": "selected-chapter-id",
    "character_name": "Test Applicant",
    "application_text": "I want to join scheduled guild activities."
  }
}
```

If the loaded form does not contain `chapter_select`, the SPA keeps the existing global submit shape (`services/web/src/features/public/ApplicationFormRoute.tsx:172-183`).

### Public chapter list response shape

```python
class PublicChapterSummaryRead(BaseModel):
    id: str
    name: str


class PublicChapterListRead(BaseModel):
    chapters: list[PublicChapterSummaryRead]
```

No pagination is needed for beta-1; use a fixed cap of 200 to match the admin listing cap (`services/api/app/repositories/web.py:18-20`).

## 6. Authorization Model

`GET /api/public/chapters` is public and requires no Pomerium principal, officer authority, applicant receipt, or Discord identity. Its FastAPI route must not depend on `get_pomerium_principal`, `verify_applicant_receipt`, or any identity dependency, and the endpoint docstring must document that it is public/no-auth by design. It returns only active chapter ids and names, which are non-PII and already visible in officer/admin surfaces with additional metadata (`services/api/app/api/v1/endpoints/web.py:64-69`, `services/api/app/contracts/web.py:39-48`).

The audit gate noted that the current ingress posture is implicitly public via the catch-all route rather than an explicit `/api/public/` Pomerium route. Record that as a follow-up observation only; it does not block beta-1 as long as the FastAPI endpoint remains identity-free and the public ingress/rate-limit entries are added alongside the existing public submit path.

Submit auth is unchanged: `POST /api/public/applications` still requires `verify_applicant_receipt`, resolves/creates a real Discord member, and records the applicant as the actor (`services/api/app/api/v1/endpoints/applications/public.py:30-41`, `services/api/app/services/applications.py:859-875`). The chapter selector does not allow browser-supplied identity headers and does not create a new authorization branch; the applicant can submit only as the receipt Discord identity.

## 7. Test Plan

### API: form definition with `chapter_select` round-trips

Extend `services/api/tests/test_forms.py` to publish a global form with fields `[chapter_select, short, long]`, then read `/api/v1/application-forms/current?scope_kind=global` and assert the `chapter_select` field is preserved exactly. Add invalid-shape coverage for duplicate `chapter_select`, `required=false`, non-global form scope, blank id/label, and `routing_rules.review_scope` that would conflict with applicant-selected routing (`services/api/tests/test_forms.py:130-160`). Add a unit test that exercises `validate_application_responses` against re-parsed field dictionaries with at least one `chapter_select` variant so the `TypeAdapter(ApplicationFormField).validate_python(raw)` path is covered after the union refactor.

Risk annotation: `group=TG-1; named_risk=chapter_select_form_contract_roundtrip; level=contract`.

### API: public chapter list endpoint returns active chapters

Add tests that seed one active chapter and one proposed/archived chapter, call the public endpoint without auth headers, and assert only `{id, name}` for the active chapter is returned. Do not reuse `/api/v1/web/admin/chapters`; that endpoint is authenticated and returns admin metadata (`services/api/app/api/v1/endpoints/web.py:64-69`).

Risk annotation: `group=TG-2; named_risk=public_chapter_list_exposes_only_active_minimal_shape; level=api`.

### API: public submit accepts `scope_kind=chapter`

Extend `services/api/tests/test_public_intake_submit.py` using `public_intake_fixtures.py` or add `services/api/tests/test_chapter_selector_submit.py`: seed a global public form containing `chapter_select`, seed an active chapter, submit with `scope_kind="chapter"` and matching chapter response, then assert:

- the application row is queued/submitted under `target_scope_kind='chapter'`;
- `target_scope_id` equals the selected chapter id;
- `form_snapshot.scope_kind` remains `global`;
- `form_snapshot.target_scope` is the selected chapter;
- missing chapter response, inactive chapter, and response/scope mismatch return validation errors.

Explicitly cover the form-lookup override gate with these six cases:

- Positive 1: chapter-selector global form + `scope_kind=chapter` + matching response -> submitted as chapter-scoped.
- Positive 2: chapter-selector global form + `scope_kind=chapter` + mismatched or missing response -> 422.
- Positive 3: non-selector global form + `scope_kind=global` -> existing global path and no override fires.
- Negative 1: non-selector global form + `scope_kind=chapter` -> existing chapter form lookup path, returning 404 if no chapter form exists.
- Negative 2: chapter-selector global form + `scope_kind=global` -> 422 because the selector-driven chapter target is required.
- Negative 3: missing chapter-select response on a chapter-selector form -> 422.

Existing public receipt/audit/notification tests must continue to pass for the global no-selector path (`services/api/tests/test_public_intake_submit.py:48-139`).

Risk annotation: `group=TG-3; named_risk=public_chapter_submit_uses_global_form_and_chapter_target; level=component`.

### GitOps: seed v2 advances only deterministic v1

Add an integration test for `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml` that exercises four cases: empty DB -> v2 inserts at version 1; v1 current -> v1 is archived and v2 becomes current at version 2 with aggregate head `current_seq=2`; officer-published current -> no-op; v2 already current -> no-op. The test must also preserve the BL-002 fail-closed guard where an aggregate head exists but no current global form exists.

Risk annotation: `group=TG-3; named_risk=public_intake_seed_v2_advances_only_v1_seed; level=integration`.

### SPA: chapter selector renders, validates, submits

Extend `services/web/tests/compat.spec.ts` and the contract fixture. Mock `/api/public/chapters`, render the form, assert the select is visible, assert submit does not post while the required select is empty, select the fixture chapter, submit, and assert the posted payload includes both `scope.scope_kind="chapter"` and `responses.<chapterFieldId>=scope.scope_id` (`services/web/tests/compat.spec.ts:115-140`, `services/web/tests/compat.spec.ts:278-299`).

Risk annotation: `group=TG-4; named_risk=spa_chapter_selector_payload_contract; level=component`.

### E2e: test 19 chapter-scoped application

Extend the web UI contract and Playwright browser flow to fill the chapter selector from fixture data (`infra/tests/e2e/lib/playwright/browser-flow.mjs:91-105`). Extend `assert_public_submit_persisted` to read `target_scope_kind`, `target_scope_id`, and `form_snapshot` from Postgres and verify the submitted application is chapter-scoped while the form definition source remains global (`infra/tests/e2e/tests/19-web-ui.sh:18-38`). Keep existing officer queue/detail assertions intact.

Risk annotation: `group=TG-5; named_risk=e2e_public_chapter_submit_persisted; level=e2e`.

## 8. Anti-scope

- No multi-page forms, progress model, or page schema.
- No conditional visibility, dependency graph, or `visible_when` contract.
- No file upload, object storage, presigned URLs, malware scanning, or attachment response type.
- No chapter creation/deletion/admin UI changes.
- No officer review workflow changes beyond reading the existing chapter-scoped application in test 19.
- No live Humility Discord writes, sends, channel changes, or role changes.
- No backwards-compatibility aliases, deprecated field names, feature flags for old behavior, or placeholder stubs.

Future BL-010 slices: beta-2 multi-page + conditional fields; beta-3 file upload.

## 9. Diff Budget

Estimated net: +820 / -70 lines.

- API contracts + validation: +170 / -20
- Public chapter endpoint/service/tests: +170
- Public submit chapter-selector handling/tests: +210 / -20
- SPA renderer/client/compat tests: +190 / -30
- E2e fixture/browser/test 19 updates: +80
- GitOps seed + public ingress validator updates: +100

This stays under 1000 net lines and should remain one PR. If implementation exceeds 1200 net lines, split only along deployability boundaries: first API contract + public chapter endpoint + submit validation, then SPA/e2e wiring. Do not split by adding compatibility shims or parallel old/new field names.

## 10. Risk Gates (self-review LOW x 4)

### Audit risk: LOW

The new public endpoint returns only active chapter id/name and no PII. Public submit auth remains applicant-receipt based, and the selected chapter is a routing target, not an identity claim (`services/api/app/api/v1/endpoints/applications/public.py:30-41`). No live Discord-visible action is introduced, so Tier 3 is not triggered (`AGENTS.md:18-26`).

### Scope risk: LOW

The slice touches one field type, one public chapter list endpoint, the existing public submit path, the SPA form renderer, and fixtures/tests. It explicitly excludes beta-2/beta-3 work and does not alter officer transitions, messages, notifications, chapter lifecycle, or Discord resources.

### Shortcut risk: LOW

The proposal avoids hardcoding chapter options in the SPA and avoids treating `chapter_select` as a special frontend-only field. The selected chapter is validated by API contracts and persisted through the same application target-scope model already used by `_submit_application_internal` (`services/api/app/services/applications.py:733-744`).

### Supported-surface risk: LOW

The seed remains a global public form source and keeps the BL-002 fail-closed/no-op behavior (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`, `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:193-211`). Existing global no-selector forms continue to submit globally, while forms with `chapter_select` gain a supported chapter-scoped path. No unsupported admin endpoint is reused for public applicants.

Conclusion: LOW.

## 11. Hookpoint Preview

### Reuse

- Current form field storage in `form_definitions.fields` and `publish_form` JSON serialization (`services/api/app/services/forms.py:78-110`).
- Existing `ApplicationScope` validation for `global` vs `chapter` scope ids (`services/api/app/contracts/applications.py:62-77`).
- Existing public submit endpoint and receipt auth (`services/api/app/api/v1/endpoints/applications/public.py:25-47`).
- Existing public submit member resolution and actor stamping (`services/api/app/services/applications.py:859-875`).
- Existing application persistence target-scope fields (`services/api/app/services/applications.py:733-744`).
- Existing admin chapter table/query shape as a reference, not as the public endpoint (`services/api/app/repositories/web.py:9-21`).
- Existing SPA API client fetch helper and submit function (`services/web/src/api/client.ts:206-221`, `services/web/src/api/client.ts:277-290`).
- Existing web UI fixture and test 19 browser flow (`infra/tests/fixtures/web-ui/contract.json:99-141`, `infra/tests/e2e/lib/playwright/browser-flow.mjs:91-129`).

### New

- Minimal public chapter list contract/service/endpoint.
- `FormFieldChapterSelect` and discriminated field union.
- Public-submit form-scope resolver for global chapter-selector forms.
- API validation that selected chapter response, submitted scope, and active chapter state agree.
- SPA data-driven renderer for current form fields and active chapter options.
- Seed-job v2 global public form payload containing `chapter_select`.

### Delete or avoid

- Do not create chapter-specific copies of the public intake form just to make form lookup pass.
- Do not add `field_type`/`field_id` aliases; the contract uses `type`/`id`.
- Do not reuse `/api/v1/web/admin/chapters` for public applicants.
- Do not hardcode chapter options in the SPA or fixture-only code.
- Do not add a schema migration for JSONB field-type expansion.
- Do not remove or bypass the BL-002 seed-public-intake form job.
