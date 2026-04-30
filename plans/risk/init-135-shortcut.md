# INIT-135 — Shortcut risk gate

**Verdict:** LOW

Scope: BL-010 β-1 — chapter-selector public application form.
Adds a single new field type, a public chapter list endpoint,
data-driven SPA rendering, chapter-target submit handling, and
a seed-job v2. The shortcut gate inspects whether INIT-135
locks `chapter_select` as a real discriminated-union variant,
keeps the SPA renderer genuinely data-driven, returns a
Pydantic-validated public chapter response, validates chapter
identity server-side, avoids "chapter creation later" stubs,
exercises the new field type end-to-end in tests, and preserves
the existing global submit path.

## S1 — `chapter_select` is a real Pydantic discriminated-union variant

**Choice:** §5 (Component Contract Preview) locks
`FormFieldChapterSelect` as a real Pydantic model with a
`Literal["chapter_select"]` discriminator and a structurally
typed `required: Literal[True] = True`:

```python
class FormFieldChapterSelect(_ApplicationModel):
    id: str
    type: Literal["chapter_select"]
    label: str
    required: Literal[True] = True
    placeholder: str | None = None
```

The full field contract becomes a Pydantic discriminated union
across all variants (`Annotated[FormFieldShort | FormFieldLong
| FormFieldNumber | FormFieldSelect | FormFieldMultiSelect |
FormFieldBoolean | FormFieldChapterSelect, Field(discriminator
="type")]`). Existing `id`/`type` JSON keys are preserved (§3,
§11) — the proposal explicitly rejects the problem map's
`field_id`/`field_type` aliases (Q3, §11 "Delete or avoid: Do
not add `field_type`/`field_id` aliases; the contract uses
`type`/`id`").

`chapter_select.required = Literal[True]` is enforced at the
contract level rather than via runtime string check. Validation
of the response value against the active chapter list extends
`validate_application_responses`, not a parallel string-typed
branch (§4 API Surface).

**Risk:** the shortcut here would be (a) typing
`chapter_select` as a free-form string field with a magic
`type=="chapter_select"` runtime branch, or (b) shipping a new
field-type alias system (`field_type`) parallel to the existing
`type` discriminator. Either bypass would split the JSON
contract and force every consumer to special-case the new field.

**Mitigation:** real Pydantic union with `Field(discriminator
="type")`, `Literal["chapter_select"]` discriminator, locked to
existing JSON keys, JSONB serialization through the same
`field.model_dump(mode="json")` path as every other variant.

**Verdict:** Not a shortcut.

## S2 — SPA renderer is genuinely data-driven for `chapter_select`

**Choice:** §3 (Modified files) requires
`services/web/src/features/public/ApplicationFormRoute.tsx` to
"replace the current hardcoded two-field renderer with
data-driven field rendering, including a chapter select
populated from `/api/public/chapters`." §5 (SPA chapter-select
rendering) reinforces: "The SPA loads the current global form
definition, renders each field by API `type`, and loads public
chapters only when at least one `chapter_select` field is
present."

§11 (Delete or avoid) explicitly forbids the shortcut: "Do not
hardcode chapter options in the SPA or fixture-only code." The
client gets a generic form-definition fetch helper alongside
the public chapter fetch (§3 `services/web/src/api/client.ts`),
not a `chapter_select`-specific one-shot.

The submit branch is also data-driven: §5 says "If the loaded
form does not contain `chapter_select`, the SPA keeps the
existing global submit shape." Selection of `scope_kind` is
driven by field presence, not by a hardcoded `if` on the
current page route.

**Risk:** the natural shortcut would be `if (field.type ===
"chapter_select") { renderHardcodedChapterSelect() } else
renderTwoTextFields()` — a fake "data-driven" renderer that
branches once on the new type and otherwise stays hardcoded.

**Mitigation:** §3 mandates rewriting the renderer to walk
`form.fields` and dispatch by `type`, the chapter fetch is
gated on field-presence detection, and the submit payload's
scope is computed from the form definition rather than from
route knowledge.

**Verdict:** Not a shortcut.

## S3 — Public chapter list endpoint returns Pydantic-validated response

**Choice:** §5 (Public chapter list response shape) and §3
(New files) lock the contract:

```python
class PublicChapterSummaryRead(BaseModel):
    id: str
    name: str

class PublicChapterListRead(BaseModel):
    chapters: list[PublicChapterSummaryRead]
```

§3 lists `services/api/app/contracts/public_chapters.py` as a
new contract module and `services/api/app/services/public_chapters.py`
as the active-only service. The endpoint module
`services/api/app/api/v1/endpoints/public_chapters.py` is
mounted on the v1 router (§3 `services/api/app/api/v1/router.py`),
not handed a raw `dict[str, str]`.

The wrapper shape is deliberate: Q2 explains the choice in
favor of a wrapped `chapters` collection — the existing admin
chapter endpoint already wraps (`services/api/app/contracts/web.py:39-48`)
and the SPA client already has a matching `chapterListSchema`
wrapper (`services/web/src/api/client.ts:12-22`), so the new
public endpoint reuses the wrapper convention rather than
introducing a raw list. §6 (Authorization Model) confirms only
non-PII fields (`id`, `name`) are exposed; admin-only columns
(`state`, `version`, `created_at`, `templates`, `configuration`,
`discord_resources`) stay off the public surface.

**Risk:** the shortcut would be `return [{"id": c.id, "name":
c.name} for c in chapters]` returned untyped from the route, or
reuse of `/api/v1/web/admin/chapters` (which would leak admin
metadata). §11 "Do not reuse `/api/v1/web/admin/chapters` for
public applicants" closes the second variant explicitly.

**Mitigation:** typed Pydantic response, dedicated public
contract module, dedicated public service that filters to
`state = 'active'`, and a TG-2 test (`public_chapter_list_exposes_only_active_minimal_shape`)
that asserts the active filter and the minimal shape at the API
boundary.

**Verdict:** Not a shortcut.

## S4 — Submit validation: chapter existence/active check is server-side

**Choice:** §4 (Submit endpoint behavior with chapter scope)
locks the server-side validation contract for a chapter-scoped
public submit:

- `scope.scope_id` is present.
- The chapter exists and **is active**.
- The chapter-select response field exists.
- The response value equals `scope.scope_id`.
- The form used for validation is the current global public
  form.

§3 modifies `services/api/app/services/applications.py` to "add
public-submit chapter-selector handling: validate the selected
chapter response, use the current global form for validation,
and persist target scope from the submitted chapter." §4
extends `validate_application_responses` so `chapter_select`
values must be "non-blank when required, and an active chapter
id" — the chapter-active check is in the same validation
function the rest of the response shape goes through, not a
trust-the-client `chapter_select` opt-out.

The mismatch case is explicitly a 422: "A public submit using a
chapter selector must include the selected id in both
`responses[chapterFieldId]` and `scope.scope_id`; mismatch is a
422 validation error" (§3 form definition changes). §7 (Test
Plan) names the negative tests: "missing chapter response,
inactive chapter, and response/scope mismatch return validation
errors" (TG-3 `public_chapter_submit_uses_global_form_and_chapter_target`).

The selected chapter is independently confirmed against the
chapter table — the SPA cannot bypass with a fake id because
the submit service re-checks active state, not the public
chapter list response cache.

**Risk:** the shortcut would be (a) trusting the SPA's
`responses[chapter]` value without checking the chapter row, or
(b) checking only that the value parses as a UUID and skipping
the `state = 'active'` re-check (so an archived/proposed
chapter could be targeted). Either bypass would let a crafted
client target an inactive chapter or a non-existent id and
poison `target_scope_id`.

**Mitigation:** validation lives in `validate_application_responses`
(server-side, in the submit service), checks both existence and
active state, and asserts response/scope agreement at 422. TG-3
tests negative cases (missing/inactive/mismatch) at the API
contract level.

**Verdict:** Not a shortcut.

## S5 — No "chapter creation later" stub; if chapter doesn't exist, fail validation cleanly

**Choice:** §8 (Anti-scope) and §11 (Delete or avoid) hold the
line explicitly:

- §8: "No chapter creation/deletion/admin UI changes."
- §8: "No backwards-compatibility aliases, deprecated field
  names, feature flags for old behavior, or placeholder stubs."
- §11: "Do not create chapter-specific copies of the public
  intake form just to make form lookup pass."

When the selected chapter does not exist or is not active, the
submit service returns a 422 validation error (§4, §7 TG-3) —
not "create the chapter on the fly," not "fall back to global
scope silently," not "queue the application pending chapter
creation."

The chapter list endpoint also has no creation surface. §6
(Authorization Model) limits the public chapter endpoint to a
read-only active list. The SPA renders only the chapters
returned by `/api/public/chapters`; there is no
"add new chapter" affordance (§5 SPA chapter-select rendering),
and no client-side path that would surface a not-yet-active
chapter to the applicant.

**Risk:** the shortcut would be a `# TODO: officer can create
chapters from the public form later` stub or a silent
"if not chapters: create a default chapter" branch. Either
would either ship dead code or break the chapter lifecycle
state machine (`proposed` → `active` → `archived`) that the
admin tooling owns.

**Mitigation:** active filter on the public list, server-side
existence + active re-check on submit, 422 on miss, anti-scope
explicitly forbidding creation/deletion/admin UI changes, no
SPA affordance for chapter creation.

**Verdict:** Not a shortcut.

## S6 — Tests exercise REAL form definitions with `chapter_select`

**Choice:** §7 (Test Plan) names four test layers, each
exercising a real form definition that contains the new field
type and a real submit through the new chapter scope path:

- **API form contract** — `services/api/tests/test_forms.py`
  publishes a global form with fields `[chapter_select, short,
  long]`, then re-reads `/api/v1/application-forms/current?scope_kind=global`
  and asserts the `chapter_select` field round-trips exactly.
  Negative cases: duplicate `chapter_select`, `required=false`,
  non-global form scope, blank id/label, conflicting
  `routing_rules.review_scope`. (TG-1
  `chapter_select_form_contract_roundtrip`.)
- **API public chapter list** — seeds active + proposed +
  archived chapters, calls the unauthenticated endpoint, and
  asserts only active id/name comes back. (TG-2
  `public_chapter_list_exposes_only_active_minimal_shape`.)
- **API submit** — `test_public_intake_submit.py` +
  `public_intake_fixtures.py` seed a global public form
  containing `chapter_select`, seed an active chapter, submit
  with `scope_kind="chapter"`, and assert the persisted row's
  `target_scope_kind='chapter'`, `target_scope_id=<selected>`,
  `form_snapshot.scope_kind='global'`, plus negative cases
  (missing response, inactive chapter, response/scope
  mismatch). (TG-3.)
- **SPA compat** — `services/web/tests/compat.spec.ts` mocks
  `/api/public/chapters`, asserts the select renders, asserts
  submit is blocked while empty, selects, submits, and asserts
  the posted payload includes both
  `scope.scope_kind="chapter"` and `responses.<chapterFieldId>=scope.scope_id`.
  (TG-4 `spa_chapter_selector_payload_contract`.)
- **E2e** — extends test 19 to fill the chapter selector via
  Playwright (`infra/tests/e2e/lib/playwright/browser-flow.mjs`),
  then asserts the persisted application is chapter-scoped via
  Postgres queries on `target_scope_kind`/`target_scope_id`/
  `form_snapshot`. (TG-5 `e2e_public_chapter_submit_persisted`.)

The tests render *and* submit the field across every layer.
There is no "render the field but don't submit" or "submit but
don't validate persistence" shortcut.

**Risk:** the shortcut would be (a) only round-tripping the
field in form contract tests but not in submit tests, or (b)
mocking the chapter validation in submit tests so the active-
chapter check is never exercised, or (c) e2e asserting only the
SQL `applications` row exists without checking `target_scope_*`.

**Mitigation:** every layer exercises the new code path
through to its own boundary — contract, list, submit (with
persistence assertions), SPA payload, and e2e DB read of
`target_scope_kind`/`target_scope_id`. Negative cases are named
in the test plan, not deferred.

**Verdict:** Not a shortcut.

## S7 — Existing global-scope path (BL-002) remains functional

**Choice:** Q5 (Form lookup) and §3 (seed update) lock the
no-regression contract for forms without `chapter_select`:

- Q5: "Existing global submission remains valid for forms that
  do not contain a `chapter_select` field." The form lookup
  remains global for the chapter-selector form, so the seeded
  public-intake form's global scope is preserved
  (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:36-45`).
- §4 (Submit endpoint behavior with chapter scope): "Forms
  without `chapter_select` keep existing global behavior."
- §3 (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`):
  "seed a global public form with `chapter_select` while
  preserving the BL-002 no-op/fail-closed behavior" — fresh
  environments seed the new v2 form, but existing environments
  only advance "when the current global form is still the prior
  seed. If an officer-published global form is current, keep
  the existing no-op behavior."
- §11 (Delete or avoid): "Do not remove or bypass the BL-002
  seed-public-intake form job."

§3 also avoids breaking the authenticated chapter-specific
submit path: "Authenticated chapter-specific submit remains the
existing exact-scope form lookup path
(`services/api/app/services/applications.py:708-734`,
`services/api/app/services/applications.py:832-842`)." The
chapter-scoped public-submit handling is conditional on global
form + `chapter_select` field presence, not a wholesale rewrite.

The existing public submit tests (receipt/audit/notification
coverage in `test_public_intake_submit.py`) "must continue to
pass for the global no-selector path" (§7 API submit tests).

**Risk:** the shortcut would be (a) replacing the seed form
unconditionally, breaking the BL-002 fail-closed/no-op
invariant; (b) routing every public submit through the new
chapter-selector path so a global form without the field 422s;
or (c) deleting the existing global submit branch in
`_submit_application_internal` and replacing it with a
chapter-only path.

**Mitigation:** seed-job v2 preserves no-op behavior when the
current global form is officer-published; submit handling is
conditional on field presence, not on submit-time route;
existing global no-selector tests must keep passing; existing
authenticated chapter-specific submit path is untouched.

**Verdict:** Not a shortcut.

## Verdict reasoning

INIT-135 ships exactly the contour the gate watches for:

- `chapter_select` is a real Pydantic discriminated-union
  variant with `Literal["chapter_select"]` discriminator and
  `Literal[True]` required, joining the existing field union;
  no string-typed runtime branch and no parallel
  `field_id`/`field_type` alias system.
- The SPA renderer is rewritten to walk `form.fields` and
  dispatch by `type`, the chapter fetch is gated on field
  presence, the chapter-scoped submit shape is selected from
  the form definition; no `if (type === "chapter_select")
  hardcode` shortcut.
- The public chapter list endpoint returns a Pydantic
  `PublicChapterListRead` wrapper with active-only filter and a
  minimal `id`/`name` shape; no raw `dict[str, str]` and no
  reuse of the admin chapter endpoint.
- Submit validation re-checks chapter existence + active state
  server-side inside `validate_application_responses`, requires
  `responses[chapter] == scope.scope_id`, and 422s on missing /
  inactive / mismatch; the SPA cannot poison `target_scope_id`
  with a fake or archived chapter id.
- No "chapter creation later" stubs; chapter creation/deletion/
  admin UI is anti-scope; missing chapter fails clean as 422.
- Tests exercise real `chapter_select` form definitions
  end-to-end at every layer (contract round-trip, public list
  active-only, submit-with-persistence, SPA payload, e2e DB
  read) plus negative cases (duplicate, required=false, missing
  response, inactive chapter, response/scope mismatch).
- The existing BL-002 global-scope submit path remains
  functional: seed-job v2 preserves no-op/fail-closed behavior
  for officer-published forms; submit handling is conditional
  on field presence; existing global no-selector tests must
  keep passing; existing authenticated chapter-specific submit
  is untouched.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-135-shortcut.md
