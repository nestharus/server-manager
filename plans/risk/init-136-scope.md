# INIT-136 — Scope risk gate

**Verdict:** LOW

INIT-136 ships BL-010 β-2 only: `page` plus `visible_when`
on the existing field shape, server-side visibility re-eval
on submit, and a wizard renderer inside the existing public
form route. The proposal explicitly defers file upload to β-3
and refuses page-level predicates, top-level page lists, a
form-builder admin UI, and any new field type
(`proposals/27-init-136-multi-page-conditional.md` §1, §2 Q6,
§5). Diff budget +760 / -80 stays under the 1,100-line single-PR
threshold (§6). Two new attributes on the shared field base,
one nested predicate model, one validator extension, one
renderer extension, zero auth or permission changes.

## Gate checks

### 1. Only adds `page` + `visible_when` to existing `form_definition.fields` shape

**PASS.** §3 (Contracts) restricts the contract delta to two
attributes on the shared `_BaseFormField`:

- `page: int = Field(default=1, ge=1)`
- `visible_when: FormFieldVisibleWhen | None = None`

plus one nested predicate model `FormFieldVisibleWhen` with
`field_id`, `op` (one of `eq` / `neq` / `in` / `not_in`), and
`value`. Both attributes default to backwards-compatible
behavior (`page=1`, `visible_when=None`), so existing seeded
and officer-published forms continue to parse and render
without rewriting. The predicate model is a contract sub-shape
that supports `visible_when`, not a new field-type variant
(check 2).

§3 also extends `_BaseFormField` rather than duplicating page
/ visible_when on each typed variant ("INIT-136 should extend
the shared field base rather than duplicating each variant"),
which keeps the discriminated union from β-1 untouched and
preserves on-the-wire shape for every existing variant.

The contract delta is mirrored once in the SPA Zod schema
(§3: "Update the SPA Zod form contract in
`services/web/src/api/client.ts` to mirror `page` and
`visible_when` on `publicFormFieldSchema`") — no second source
of truth.

Publish-time validation is added in `FormDefinitionPublish`
(§3) to reject:

- `page < 1`.
- Predicate references to unknown / forward / non-scalar
  source fields.
- Predicate sources of type `multi_select` or `chapter_select`
  (§2 Q1: "predicate sources are scalar fields only").
- `visible_when` on a `chapter_select` field (§2 Q6).
- Invalid op / non-list value with `in` / `not_in` /
  duplicate field ids (§4 TG-1).

These constraints make the new attributes safe to publish
without an admin UI and prevent the predicate language from
silently expanding (check 5, check 7).

### 2. No new field types — still the seven from β-1 (`short`, `long`, `number`, `select`, `multi_select`, `boolean`, `chapter_select`)

**PASS.** §3 enumerates contract additions and they are all
either base attributes or nested predicate sub-shape:

- `FormFieldVisibleWhen` — predicate model nested under
  `_BaseFormField.visible_when`, not a field variant in the
  `ApplicationFormField` discriminated union.
- `page` / `visible_when` — attributes on the shared base.

The β-1 discriminated union (`FormFieldShort` | `FormFieldLong`
| `FormFieldNumber` | `FormFieldSelect` | `FormFieldMultiSelect`
| `FormFieldBoolean` | `FormFieldChapterSelect`,
`Field(discriminator="type")`) is preserved verbatim. §3
explicitly says "Keep the existing `id` / `type` JSON keys.
Do not introduce `field_id`, `field_type`, aliases, feature
flags, or old/new dual support." No new `type` literal value
is added.

§2 Q1 further bounds the predicate language so it cannot
implicitly birth new variant behavior: predicate sources are
scalar fields only (`short`, `long`, `number`, `select`,
`boolean`); `multi_select` and `chapter_select` are excluded
to "keep the language deterministic and avoid array
containment semantics or chapter-routing coupling."

### 3. No top-level `pages` list (per anti-scope)

**PASS.** §2 Q2 locks the page model to "option i: add `page:
int` to each field, 1-indexed, with default `1`." It
explicitly forbids a top-level list: "No top-level `pages`
list in beta-2. Page titles, page-level conditions, and
per-page metadata are future work."

§5 (Anti-Scope) reinforces: "Conditional pages or page-level
predicates. Pages are derived from field page numbers and
skipped only when they contain no visible fields."

The page model is purely derived: §2 Q2 says "Pages are
derived from the distinct page numbers in the ordered field
list" and "API read normalizes the runtime page sequence by
sorting distinct page values. The UI displays contiguous
steps based on that derived order." This means there is no
new persisted page resource, no `pages: [...]` attribute on
`form_definition`, no per-page id, title, or metadata
shape — exactly the anti-scope intent.

### 4. No file upload (β-3 territory)

**PASS.** §5 (Anti-Scope): "File upload, object storage,
presigned URLs, malware scanning, and attachment response
values. That is beta-3." §1 reaffirms BL-010 decomposition
("β-3 owns file upload"). No file / attachment field type,
storage backend, presigned-URL flow, or attachment response
shape appears anywhere in §3 (Substrate), §4 (Test Plan), or
§6 (Diff Budget).

The submit response shape stays "the beta-1 shape: `responses:
dict[str, JSON]`" (§1) — no new attachment-shaped values.

### 5. No admin form-builder UI

**PASS.** §2 Q5 locks publishing to existing API surface:
"JSON upload / API publishing is sufficient for beta-2. Do
not add a chapter officer form-builder admin UI in this
slice. Contract validation must make authored JSON safe enough
to publish."

§5 (Anti-Scope): "Form-builder admin UI beyond JSON upload /
API publishing."

The safety burden moves into publish-time validators
(`FormDefinitionPublish` extensions in §3), which is the
right place — they reject malformed page numbers, unknown /
forward predicate references, unsupported source types,
duplicate ids, and `visible_when` on `chapter_select` at
publish time, so the absence of a UI does not produce
unsafe published forms.

### 6. Wizard nav stays in the existing `ApplicationFormRoute.tsx`

**PASS.** §3 (SPA Renderer): "Modify
`services/web/src/features/public/ApplicationFormRoute.tsx`."
§2 Q3 explicitly bounds wizard plumbing to that one file:
"This fits the existing `ApplicationFormRoute.tsx` runtime
renderer. It needs local step state and visibility evaluation,
not a new route or server round-trip."

The wizard-state additions in §3 (derived pages, current-page
signal, cross-page response state, shared visibility helper,
visible-only render, visible-only submit payload) are
in-component refactors of the existing data-driven renderer
that β-1 just produced. No new route, no per-page POST API,
no draft API, no server-side step tracking (§5 Anti-Scope:
"No new submit response shape, per-page save API, draft
persistence API, or server-side step tracking").

Existing β-1 chapter-selector submit semantics are preserved
(§3: "Keep `chapter_select` submit behavior from beta-1: if
the current form has the always-visible chapter selector,
submit `scope_kind=\"chapter\"`..."). The renderer extension
does not displace β-1's data-driven dispatch — it wraps it
in pagination plus visibility evaluation.

Draft persistence keeps using the existing `sessionStorage`
draft path; §3 only adds the constraint that "restore must
not revive hidden fields into the submit payload after
visibility recomputation," which is a hidden-field cleanup
inside the existing draft path, not a new persistence
mechanism.

### 7. No Pomerium / Cedar / DB schema changes

**PASS.**

**DB schema:** unchanged. `form_definitions.fields` is JSONB
(established in INIT-135 §3 and verified against current
migration head `wu_045_app_public_submit_notify`), so adding
`page` and `visible_when` to the field dictionaries is a
contract-level change absorbed by the existing JSONB column.
§3 (Contracts) and §6 (Diff Budget) contain no Alembic
migration line item. The β-1 anti-pattern §11 ("Do not add a
schema migration for JSONB field-type expansion") carries
forward implicitly; INIT-136's seed-discipline note ("If seed
data is updated, keep the beta-1 seed discipline:
deterministic JSON form payloads, no schema migration for
JSONB field expansion") makes it explicit. No new column,
table, index, constraint, or routing-rule shape.

**Pomerium:** unchanged. §3 modifies API contracts, the
existing public form GET endpoint, the existing public
submit service, the SPA Zod schema, and the SPA renderer.
No new public endpoint is added (§3 "Public Form Endpoint":
"`GET /api/v1/public/application-forms/current` ... can keep
the same endpoint and response model"). No
`gitops/.../pomerium/...yaml` policy change appears in §3.
No new principal, prefix, or auth posture is introduced.

**Cedar:** unchanged. No Cedar policy, action, or resource
shape appears anywhere in §3, §4, §5, or §6. The visibility
predicate (`field_id` / `op` / `value`) is a form-engine
construct, not an authorization construct — server-side
re-eval happens inside `validate_application_responses`
(§3 Submit Validator), not via a Cedar `is_authorized` call.
The β-1 chapter-selector override stays narrow ("must remain
narrow: it should still fire only when the current global
form contains the required `chapter_select` field..."), so
conditional visibility cannot turn chapter routing into a
Cedar-policy concern (§3, §5).

**Auth posture:** unchanged. The public submit endpoint
keeps its existing `verify_applicant_receipt` posture (β-1,
not modified by §3). The actor remains the resolved Discord
member from the receipt. Visibility evaluation is data-driven,
not identity-driven; nothing in the predicate references
the applicant identity, chapter membership, role, or any
other auth-derived attribute.

## In scope (justified)

- **No Alembic migration.** `form_definitions.fields` JSONB
  absorbs `page` + `visible_when`; predicate model is nested
  inside the field dict; no responses-table column change
  (responses remain `dict[str, JSON]`).
- **`page` + `visible_when` on `_BaseFormField`** in
  `services/api/app/contracts/applications.py`. Both default
  to existing behavior (`page=1`, `visible_when=None`).
- **`FormFieldVisibleWhen` predicate model** with the four
  ops (`eq`, `neq`, `in`, `not_in`), scalar source fields
  only, earlier-field-only references.
- **Publish-time validation** in `FormDefinitionPublish` for
  page values, predicate source existence, earlier-field
  ordering, supported source field types, `chapter_select`
  restrictions, and duplicate field ids — the safety net
  that lets §2 Q5 ship with no admin UI.
- **Server-side visibility re-eval** in
  `validate_application_responses`
  (`services/api/app/services/applications.py`) after the β-1
  `_chapter_selector_override` fires. Rejects hidden-field
  submissions, omits hidden required-field requirement,
  type-validates only visible submitted values. The β-1
  chapter-selector override gate remains narrow (§3) so
  conditional visibility cannot disturb chapter routing.
- **SPA wizard plumbing** added in
  `services/web/src/features/public/ApplicationFormRoute.tsx`
  only: derived pages, current-page signal, cross-page
  response state, shared visibility helper, Next / Previous /
  Submit-on-last-page navigation with skip-empty-page
  behavior. β-1 chapter-selector submit semantics preserved.
- **SPA Zod schema** mirror of `page` + `visible_when` in
  `services/web/src/api/client.ts` — single mirror, no
  parallel old/new schemas.
- **Test wiring.** TG-1 contract round-trip + invalid
  predicates; TG-2 hidden-required vs visible-required submit
  paths; TG-3 server-side bypass-resistance; TG-4 SPA
  multi-page navigation and conditional rendering with
  hidden values not in payload; TG-5 e2e test 19 extension
  with multi-page fixture path. β-1 chapter-selector
  assertions preserved.
- **Diff budget +760 / -80** under the 1,100 single-PR
  ceiling (§6) with documented split fallback along
  deployable boundary (API + server validation, then SPA +
  e2e wiring).

## Out of scope (deferred / explicit anti-scope §5)

- **File upload / object storage / presigned URLs / malware
  scanning / attachment response type** — β-3.
- **Form-builder admin UI** beyond JSON / API publishing —
  separate work, never in BL-010 β-X.
- **Conditional pages, page-level predicates, top-level
  `pages: [...]` list, page titles, per-page metadata** — pages
  derive from field `page` attribute only.
- **Chapter selector interaction with conditional visibility.**
  `chapter_select` stays always visible and routing-only;
  cannot have `visible_when`; cannot be referenced by another
  field's `visible_when`.
- **Chapter creation / deletion UI.**
- **New submit response shape, per-page save API, draft
  persistence API, server-side step tracking.**
- **Live Discord-visible writes / messages / channel changes
  / role changes / kicks / bans / permission edits** — Tier 3,
  separate user-approved action.
- **Backwards-compatibility aliases / deprecated field names
  / feature flags / transitional code paths / placeholder
  stubs.**
- **JSONLogic or dotted-boolean predicate language** (§2 Q1:
  "Do not use JSONLogic or dotted boolean expressions in this
  slice. They are larger surface areas than the current form
  builder and submit validator need").
- **`multi_select` or `chapter_select` as predicate sources**
  (§2 Q1).
- **JSONB schema migration for field-shape expansion** —
  none needed; β-1 discipline preserved.
- **New public endpoint.** §3 keeps
  `GET /api/v1/public/application-forms/current` shape.
- **Pomerium policy changes / Cedar policy changes / new
  ingress paths.**

## Risk surface

| Area | Pre (β-1) | Post (INIT-136 β-2) | Justification |
|---|---|---|---|
| Migration head | `wu_045_app_public_submit_notify` | Identical — no Alembic migration | `form_definitions.fields` JSONB absorbs `page` + `visible_when`; responses shape unchanged |
| Field-type set | 7 (`short`, `long`, `number`, `select`, `multi_select`, `boolean`, `chapter_select`) | Identical | Only base-attribute additions; no new variant in the discriminated union |
| Field base shape | `_BaseFormField` (id, type, label, required, ...) | + `page: int = 1`, `visible_when: FormFieldVisibleWhen \| None = None` | Defaults preserve existing seeded + officer-published forms |
| Predicate language | none | `FormFieldVisibleWhen { field_id, op ∈ {eq, neq, in, not_in}, value }` | Scalar-only sources, earlier-field-only, no JSONLogic, no `multi_select` / `chapter_select` sources |
| Top-level form shape | `fields: [...]`, no `pages` | Identical | Pages are derived from distinct field `page` values; no `pages: [...]` attribute |
| Public form endpoint | `GET /api/v1/public/application-forms/current` | Identical — same path, same response model | Existing endpoint serializes the extended field shape naturally |
| Public submit endpoint | `POST /api/v1/public/applications` (auth: `verify_applicant_receipt`) | Identical — same path, same auth | Server adds visibility re-eval inside the existing service; no new endpoint, no new auth surface |
| Public submit service | `validate_application_responses` (parse, unknown-key, required, per-type, β-1 chapter-selector) | + visibility pass after β-1 chapter-selector override; reject hidden submissions; require only visible required; type-validate visible values | Single-pass deterministic eval over authored field order; β-1 chapter-selector override remains narrow |
| Submit response shape | `responses: dict[str, JSON]`, `scope: {scope_kind, scope_id}` | Identical | §1: "submit response shape stays the beta-1 shape"; no per-page submit API, no draft API |
| SPA renderer | Data-driven dispatch over field types (β-1) | + derived pages, current-page signal, cross-page response state, shared visibility helper, Next / Previous / submit-on-last-page nav | One-file extension in `ApplicationFormRoute.tsx`; no new route, no server round-trip |
| SPA chapter-selector submit | Submit `scope_kind=chapter` with selected chapter id when `chapter_select` present (β-1) | Identical | §3: "Keep `chapter_select` submit behavior from beta-1" |
| SPA Zod schema | `publicFormFieldSchema` | + `page` + `visible_when` mirror | Single mirror; no parallel old/new schema |
| SPA draft persistence | `sessionStorage` draft restore | + hidden-field-cleanup constraint on restore | Existing path; constraint prevents reviving hidden values into final payload |
| Permission surface | Unchanged | Unchanged | No new permission name in §3 |
| Actor kinds | Resolved Discord member from receipt | Identical | No new auth branch; visibility is data, not identity |
| Pomerium auth | Public submit + public chapters via existing posture | Unchanged | No new public endpoint; no new policy / prefix / principal |
| Cedar policies | Application submit / officer review (existing) | Unchanged | Visibility is form-engine logic, not authorization logic |
| Kong ingress / rate-limit | Public submit + public chapters paths enumerated (β-1) | Unchanged | No new public path |
| Authentik | Unchanged | Unchanged | Not in §3 modified files |
| Discord daemon | Existing INIT-134 surface | Untouched | No new Discord surface |
| Discord-visible writes | Existing submit notification | Identical | Conditional visibility is form-engine; does not gate or alter Discord events |
| Idempotency | Existing public-submit dedupe by `client_application_id` | Identical | No new dedupe key |
| Seed job | β-1 v2 global form with `chapter_select` | Optional update preserving β-1 seed discipline (deterministic JSON, no schema migration, no officer-published overwrite) | If β-2 fixture rev is needed, follows β-1 seed-advance pattern |
| E2e test 19 | Asserts public submit + officer queue + chapter target (β-1) | + multi-page fixture path; conditional required field visible from earlier answer; Next / Previous nav; persisted `responses` contains visible, omits hidden | β-1 chapter-scoped assertions intact; no live Discord write |
| Diff budget | — | +760 / -80 (under 1,100 single-PR ceiling, documented split fallback at >1,100) | One PR; split boundary is API + server validation, then SPA + e2e wiring |

## Splittable concerns

- **Contract additions (`page`, `visible_when`,
  `FormFieldVisibleWhen`) + publish-time validation + server
  visibility re-eval in `validate_application_responses`**
  are the API half. **SPA Zod mirror + wizard plumbing in
  `ApplicationFormRoute.tsx` + e2e test 19 multi-page fixture
  path** are the SPA / e2e half. §6 documents this as the
  split boundary if the diff exceeds 1,100 net lines. Bundling
  is the right call at the +760 estimated diff because the
  SPA cannot exercise the wizard without the contract /
  validator changes, and the contract changes would otherwise
  sit dormant behind a feature gate (banned in §5: "No ...
  feature flags").
- **Server-side visibility re-eval is not splittable from the
  contract additions** — without `visible_when` parsing in
  the contract, the validator has nothing to re-eval, and
  without server re-eval the SPA's client-side hide could be
  bypassed (TG-3 explicitly proves this).
- **Wizard plumbing is not splittable from server visibility
  re-eval** — without server enforcement, a wizard that
  hides required fields client-side would create
  silently-invalid applications (TG-3 hidden-required-omitted
  case).
- **Predicate source restriction (scalar-only, no
  `multi_select`, no `chapter_select`)** is not splittable
  from the predicate model — relaxing later is a deliberate
  β-N decision; allowing it now would expand the language
  surface beyond what §2 Q1 deems "deterministic."

## Verdict reasoning

LOW. Every gate check passes:

1. **Only `page` + `visible_when` on the existing field
   shape**, both as base-attribute additions with
   backwards-compatible defaults plus one nested
   `FormFieldVisibleWhen` predicate model. Existing variants
   are untouched. ✅ check 1.
2. **No new field types** — discriminated union from β-1 is
   preserved verbatim; no new `type` literal value. ✅ check 2.
3. **No top-level `pages` list** — pages are derived from
   distinct field `page` values; §2 Q2 and §5 ban any
   top-level pages attribute, page titles, page-level
   predicates, or per-page metadata. ✅ check 3.
4. **No file upload** — §5 explicitly defers to β-3; no
   storage / presigned / attachment surface anywhere in §3,
   §4, or §6. ✅ check 4.
5. **No form-builder admin UI** — §2 Q5 and §5 lock
   publishing to JSON / API surface; publish-time validators
   carry the safety burden. ✅ check 5.
6. **Wizard nav stays in `ApplicationFormRoute.tsx`** — §3
   modifies that one file; §2 Q3 forbids new routes or
   server round-trips; β-1 chapter-selector submit semantics
   preserved. ✅ check 6.
7. **No Pomerium / Cedar / DB schema changes** — JSONB
   absorbs the new attributes; no migration, no Pomerium
   policy file in §3, no Cedar policy / action / resource
   shape; auth posture unchanged. ✅ check 7.

Three judgment calls worth naming explicitly — all LOW-risk:

- **Server-side re-evaluation of `visible_when` inside
  `validate_application_responses`** is the right anti-bypass
  posture (TG-3 explicitly tests it). The alternative —
  trusting the SPA — would let a malicious client smuggle
  hidden fields or skip visible required ones. The β-1
  chapter-selector override gate is preserved as narrow (§3),
  so the new visibility pass cannot turn `chapter_select`
  into a conditional routing field.
- **Page model as a per-field `page: int` attribute** instead
  of a top-level `pages: [...]` list is the smaller contract
  change because the field list is already the rendered and
  persisted unit. It sacrifices per-page titles / metadata
  (§2 Q2 calls those "future work"), but ships the multi-page
  experience without an admin UI and without a new persisted
  resource. Sparse page numbers are explicitly handled by
  read-time normalization, so authored JSON does not need to
  be contiguous.
- **Predicate language locked to four ops + scalar-only
  sources** (§2 Q1) is the deliberately small predicate
  surface. No JSONLogic, no dotted boolean expressions, no
  `multi_select` / `chapter_select` sources. The alternative
  — a richer expression language now — would either need an
  admin UI to author safely or force the publish-time
  validator to grow into a parser. Locking it small lets β-2
  ship without either.

No "while we're at it" cleanups. No audits of pre-existing
form / submit logic. No β-3 file-upload surface sneaking in.
No expansion of the chapter-selector routing path. No
backwards-compatibility shims, feature flags, or `field_type`
/ `field_id` aliases (§5 explicitly bans them).

SCOPE_DONE: plans/risk/init-136-scope.md
