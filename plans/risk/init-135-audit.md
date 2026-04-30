# INIT-135 — Audit risk gate

**Verdict:** LOW

Scope: BL-010 β-1 — public chapter selector. Adds
`GET /api/public/chapters`, a `chapter_select` form field
type, data-driven SPA rendering, chapter-target submit
handling on the existing public submit endpoint, and a
seed v2.

The audit gate inspects the proposal for: PII leakage on
the new public read, scope/identity confusion on the
public submit path, regression risk for the existing
global submit, Pomerium routing posture, form-definition
round-trip, and form-publish persistence.

Source proposal: `proposals/17-init-135-chapter-selector.md`.
Source problem map: `research/28-bl-010-problem-map.md`.

## A1 — `GET /api/public/chapters` is public and free of PII

**Surface:** Q2 (Public chapter list endpoint) and §4 (API
Surface) lock the contract:

```json
{ "chapters": [ {"id": "...", "name": "..."} ] }
```

The response shape is enforced by Pydantic
`PublicChapterListRead` / `PublicChapterSummaryRead`
(§5 Component Contract Preview, §3 New files
`services/api/app/contracts/public_chapters.py`). Admin-only
columns are explicitly excluded: §2 Q2 names `state`,
`version`, `created_at`, `templates`, `configuration`,
and `discord_resources` as off-limits, citing
`services/api/app/contracts/web.py:39-48` and
`services/api/app/repositories/web.py:9-21` as the admin
shape that is *not* reused.

The proposal explicitly forbids reusing the admin
endpoint for the public surface (§11 "Delete or avoid: Do
not reuse `/api/v1/web/admin/chapters` for public
applicants"). This blocks the most common leak vector —
returning the admin DTO and trusting the route to filter.

**PII inventory:** chapter `id` (UUID assigned at chapter
creation, opaque to applicants today via
`/api/v1/web/admin/chapters` + chapter-scoped officer
surfaces) and chapter `name` (operator-chosen guild label,
not member-derived). Neither field carries member,
applicant, Discord, or audit metadata. Discord channel
IDs / role IDs / category IDs live under
`discord_resources` and stay admin-only.

**Active-only filter:** §4 ("active-only", reads
`chapters` filtered on `state = 'active'`, ordered
`name ASC`, capped 200). §11 "Delete or avoid: Do not
hardcode chapter options". The TG-2 test
(`public_chapter_list_exposes_only_active_minimal_shape`)
seeds active + proposed + archived chapters and asserts
only the active id/name returns, so the filter is
exercised at the API contract level.

**Residual risk:** chapter `name` is operator-controlled
free text (cf. `services/api/app/contracts/chapters.py`
`ChapterCreate.name`). If an operator names a chapter
with PII (e.g., a member's real name) and transitions it
to `active`, the public endpoint will surface that name.
Not a contract bug — it is a substrate property already
present at admin/officer surfaces — but the audit notes
that public exposure widens the blast radius from
authenticated officers to anonymous web visitors.
Operators who already trust officer-visible chapter names
will not be surprised by public exposure.

**Verdict:** No PII leak in the contract. Active-only
filter exercised by TG-2. Audit risk LOW for A1.

## A2 — `chapter_select` round-trips through `form_definitions` JSONB

**Storage:** `form_definitions.fields` is JSONB
(`services/api/app/services/forms.py:87-110`) and accepts
arbitrary serialized field dicts. The proposal locks (§3
Migration) "No Alembic schema migration. `form_definitions.fields`
is already JSONB-backed and persists serialized field
dictionaries." Adding a new variant is a contract change,
not a table change.

**Serialization symmetry:** `publish_form` already
serializes via `[field.model_dump(mode="json") for field
in validated.fields]` (forms.py:87). Read returns the
JSONB row; the contract `FormDefinitionRead.fields:
list[ApplicationFormField]` revalidates each entry
through the discriminated union, which now accepts
`type: "chapter_select"`. Same JSON keys (`id`, `type`,
`label`, `required`, `placeholder`) — no parallel
`field_id`/`field_type` aliases (§11, Q3).

**Discriminator wiring:** §5 locks the union as
`Annotated[FormFieldShort | ... | FormFieldChapterSelect,
Field(discriminator="type")]` with
`Literal["chapter_select"]` on the new variant. Pydantic
discriminated unions persist and revalidate the same JSON
shape, so contract round-trip is structural, not
post-processed.

**Refactor footprint that the audit must flag:**
`services/api/app/services/applications.py:499` calls
`ApplicationFormField.model_validate(raw)` inside
`validate_application_responses`. After the refactor,
`ApplicationFormField` becomes a `TypeAlias` for an
`Annotated[Union, Field(discriminator)]`, which does not
expose `.model_validate`. The implementation must switch
this call site (and any other direct `.model_validate`
on `ApplicationFormField`) to
`pydantic.TypeAdapter(ApplicationFormField).validate_python(raw)`
or wrap the union in a root model. The proposal does not
explicitly call this out, so the implementation should
flag it during code review. Round-trip will fail at
submit time if this is missed.

**TG-1 coverage:** `services/api/tests/test_forms.py`
publishes `[chapter_select, short, long]`, re-reads via
`/api/v1/application-forms/current?scope_kind=global`,
and asserts the field round-trips exactly (§7 API form
definition). Negative cases cover duplicate, blank,
non-global scope, and `required=false`.

**Verdict:** Storage, serialization, and revalidation are
structurally sound. One implementation detail
(`TypeAdapter` for the union alias) must land cleanly.
Audit risk LOW for A2 with one finding (F1 below).

## A3 — Public submit with `scope_kind=chapter` validates correctly

**Submit validation contract (§4 Submit endpoint
behavior):** for a chapter-selector public submit:

- `scope.scope_id` is present.
- The chapter exists and is active.
- The chapter-select response field exists.
- The response value equals `scope.scope_id`.
- The form used for validation is the current global
  public form.

Mismatch returns 422 (§3 Form definition changes:
"mismatch is a 422 validation error"). §7 TG-3 tests
"missing chapter response, inactive chapter, and response/
scope mismatch return validation errors."

**Server-side enforcement:** validation lives in
`validate_application_responses`
(`services/api/app/services/applications.py:493-548`),
which runs after form snapshot is built and inside the
public submit transaction. The active-chapter re-check
is server-side, not derivable from the public chapter
list response alone — a crafted client cannot bypass with
an arbitrary or archived chapter id. §11 "Delete or
avoid: Do not hardcode chapter options" reinforces that
the SPA's chapter list is informational and the source
of truth is the database row.

**Form-lookup override:** §2 Q5 explicitly relaxes the
existing `_get_current_form_for_submit` constraint for
chapter-selector submits — when the public submitter
sends `scope_kind=chapter, scope_id=X`, the new code
path looks up the *current global* form rather than a
chapter-specific one. This is a meaningful behavior
change to `_submit_application_internal`'s form
discovery, gated on `chapter_select` field presence, and
must be implementation-tight: an unconditional override
would let public submitters target a global form even
when they sent unrelated chapter scope, while a too-tight
override would 404 when global form has no
`chapter_select`. The proposal locks the gate ("when the
current global public form contains exactly one required
`chapter_select` field"), and §3 names the modified files
(`services/api/app/services/applications.py:473-490`,
`493-548`, `676-829`, `845-896`) where the override
lands.

**Authorization integrity (§6 Authorization Model):**
public submit auth remains receipt-backed via
`verify_applicant_receipt` (public.py:30-41). The
chapter selector "does not allow browser-supplied
identity headers and does not create a new authorization
branch; the applicant can submit only as the receipt
Discord identity." The selected chapter is a routing
target, not an identity claim — no authority
re-evaluation against the chapter is needed for the
applicant. `_require_submit_authority` continues to
receive `form_row["scope_kind"]` (global) and `scope_id`
(None), which the receipt-backed applicant clears
trivially via the actor==applicant branch.

**Target scope persistence:** §4 ("Persisted application
behavior") locks the snapshot/target split:
- `form_snapshot.scope_kind` / `scope_id` remain
  `global` / `null` (form-definition source).
- `form_snapshot.target_scope` and the application row
  `target_scope_kind` / `target_scope_id` become the
  *selected chapter*.

This is consistent with how `build_form_snapshot`
already produces `target_scope` from
`routing_rules.review_scope` or the form scope. To make
the chapter override work, the proposal updates
`_effective_routing_rules` so a chapter-selector form
does not default `review_scope` to global at publish
time (§3 modified file
`services/api/app/services/forms.py:55-59, 78-110`); the
submit-time override then injects the selected chapter
as the actual target. The data flow is testable end-to-
end at TG-3 and TG-5 (e2e Postgres read of
`target_scope_kind`/`target_scope_id`).

**Risk surface:** the most adversarial bypass is a
client sending `scope: {chapter, X}` while
`responses[chapter_field]` is *missing* or set to a
different id. §3 explicitly closes this: "A public
submit using a chapter selector must include the
selected id in both `responses[chapterFieldId]` and
`scope.scope_id`; mismatch is a 422 validation error."
Both conditions are negative-tested by TG-3.

A second bypass would be `responses[chapter_field] = X`
where X is an inactive chapter; the active-state re-check
in `validate_application_responses` closes this. TG-3
covers "inactive chapter" explicitly.

A third bypass — a client sending a chapter id that does
not exist — fails at the existence check (TG-3 "missing
chapter response" covers the absent-field case; the
"inactive chapter" / "response/scope mismatch" cases
extend symmetrically to non-existent ids since the
service reads from the chapter table).

**Verdict:** Server-side validation is comprehensive and
testable; authorization model is unchanged; target scope
override has a clean data-flow path through existing
`build_form_snapshot` semantics. Audit risk LOW for A3,
with one implementation finding (F2 below) on the
form-lookup override gate.

## A4 — BL-002 global-scope submit path is preserved

**Form preservation (§3 Migration, §3 GitOps):** the
seed job is updated to seed a global public form *with*
`chapter_select`, but the BL-002 fail-closed/no-op
guard (`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:14-31`)
remains. Fresh environments seed v2; existing
environments only advance the deterministic seed form
when the current global form is still the prior seed
(v1 deterministic id). If an officer-published global
form is current, the seed is no-op (per the existing
"officer-published form present; skipping seed" branch
at lines 203-208).

**Submit-path preservation (§2 Q4, §4):** "Existing
global submission remains valid for forms that do not
contain a `chapter_select` field" and "Forms without
`chapter_select` keep existing global behavior." The
chapter-selector handling is conditional on field
presence, not a wholesale replacement of the submit
function. The existing
`test_public_intake_submit.py:48-139` receipt/audit/
notification tests must continue to pass for the global
no-selector path (§7 API submit tests).

**Authenticated chapter submit (§3, §4):** "Authenticated
chapter-specific submit remains the existing exact-scope
form lookup path
(`services/api/app/services/applications.py:708-734`,
`832-842`)." The override only applies when the public
submit path detects a global form with `chapter_select`.

**Seed migration risk:** the v2 seed must use a new
deterministic UUID (e.g., `'init-135:public-intake-global:v2'`)
so the v1 seed row coexists during the upgrade window
and the seed knows when to advance vs no-op. The
proposal acknowledges this conceptually but does not
land the SQL — implementation must reconcile the
existing `current_global` / `existing_seed` CTEs with a
new "advance seed if current is v1 seed" branch that
archives v1 and inserts v2 in the same transaction,
preserving the form-publish action/state-change/
aggregate-head invariants. F3 below.

**Verdict:** Conceptual preservation is locked at every
boundary (seed, submit branch, authenticated path).
Implementation risk concentrates in the seed SQL.
Audit risk LOW for A4, with one finding (F3 below).

## A5 — Backwards compatibility: existing tests + e2e

**Contract back-compat (§3 contracts/applications.py):**
"replace the monolithic `ApplicationFormField` shape
with a discriminated union over existing field variants
plus `FormFieldChapterSelect`, keeping existing `id`/
`type` JSON keys." The current
`ApplicationFormField.type` literal `"short" | "long" |
"number" | "select" | "multi_select" | "boolean"` becomes
seven variant classes. Existing JSON payloads
(stored fields, request bodies, fixture rows) are byte-
compatible because the discriminator is the same `type`
key.

**Refactor risk:** the union-as-typealias pattern means
direct method access on `ApplicationFormField` (e.g.,
`.model_validate`, `(...)` constructor) is no longer
valid. Grep finds two call sites that touch the symbol:
- `services/api/app/contracts/applications.py:80` (the
  class definition, replaced by the alias);
- `services/api/app/services/applications.py:499`
  (`ApplicationFormField.model_validate(raw)` inside
  `validate_application_responses`).
The latter must move to `TypeAdapter`. Same applies to
test code that constructs the field directly. F1 below.

**Routing-rules default change (§3 forms.py:55-59):**
`_effective_routing_rules` currently sets
`review_scope = scope.as_persisted()` when null.
The proposal adjusts this for chapter-selector forms
(do not default to global), which means existing
non-`chapter_select` global forms still default
`review_scope` to global; only the new variant skips
the default. The discriminator-driven check is
testable. Existing `test_forms.py` cases for routing-
rules default behavior remain valid because they don't
include `chapter_select`.

**E2e test 19 (§3 infra/tests/e2e/tests/19-web-ui.sh):**
the current e2e asserts `target_scope_kind='global'`,
`target_scope_id IS NULL`. The proposal extends it to
assert `target_scope_kind='chapter'` and the matching
`target_scope_id`. This is a behavior change for the
seeded form (now includes `chapter_select`), so the
existing test 19 assertions are intentionally
overridden, not regressed.

**Fixture changes (§3 contract.json + validate_web_ui_local.sh):**
the contract fixture grows to include the chapter field,
the public chapter endpoint payload, and the chapter-
scoped submit payload. The validator is updated from
"two hardcoded fields" to the richer contract. Existing
SPA tests (`compat.spec.ts`) are extended, not
replaced, for the chapter selector path.

**Verdict:** Compat work is concentrated in three spots
(union method calls, routing-rules default, e2e
assertions) and the proposal accounts for each. Audit
risk LOW for A5, subsumed by F1.

## A6 — PII (chapter list metadata)

Already covered in A1. Restated for the gate's
explicit numbering:

- Response payload: `{id, name}` only.
- Excluded: `state`, `version`, `created_at`,
  `template_snapshot`, `configuration`,
  `discord_resources`, role/channel/category ids, and
  every officer/admin metadata field that the chapter
  table carries.
- Operator-control caveat (chapter `name` is
  operator-supplied) noted in A1; not a proposal-level
  bug.

**Verdict:** No PII in the contract. Audit risk LOW.

## A7 — Pomerium routing posture for the new public route

**Existing public-unauth posture:** the Pomerium config
(`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-100`)
exposes `/auth/discord/` with
`allow_public_unauthenticated_access: true` and
`pass_identity_headers: false`, plus a catch-all `/`
route to the SPA with `allow_public_unauthenticated_access:
true`. There is no Pomerium *route* for `/api/public/...`
— the public submit endpoint reaches the API via:
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  (Kong ingress on `web.local.humility.local`, paths
  `/api/public/applications` and `/api/applications`,
  via `pomerium-proxy`), and
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  (Kong ingress on `api.local.humility.local`, path
  `/api/v1/public/applications`, via
  `server-manager-api`).

The public submit path is reachable through the SPA host
because the SPA-side ingress fronts pomerium-proxy and
the catch-all SPA route handles unauthenticated access
without injecting identity headers.

**Proposed change (§3 GitOps):** add `/api/public/chapters`
to *both* ingress YAMLs alongside the existing public
submit path. The proposal does not add a Pomerium-config
route for `/api/public/chapters`, mirroring the absence
of a config-level route for `/api/public/applications`.

**Identity-header check:** since the new route shares
the same ingress fronting and the Pomerium config has no
explicit route forcing identity injection on
`/api/public/...`, identity headers will not be passed
to the API for the public chapter list. The endpoint
implementation must not depend on identity headers
(§6 Authorization Model: "requires no Pomerium
principal, officer authority, applicant receipt, or
Discord identity"). The implementation's FastAPI
dependency tree for the new route should not include
`get_pomerium_principal` or `verify_applicant_receipt`
— this is the audit trip-wire to confirm during code
review.

**Rate-limit posture:** the Kong plugin
`public-intake-rate-limit` already applies (5/min,
50/hour, local policy) on the public-intake ingress.
Adding `/api/public/chapters` to the same ingress
inherits the rate limit, which is conservative for a
read endpoint but acceptable for β-1.

**Residual risk:** if a future change adds an explicit
Pomerium route for `/api/public/` with
`pass_identity_headers: true`, the public chapter
endpoint would start receiving Pomerium-injected
identity claims that the FastAPI route does not
authenticate. This is not introduced by INIT-135, but
the audit notes that the Pomerium config's "implicit
public via catch-all" pattern is fragile. F4 below.

**Verdict:** New route follows the same pattern as
`/api/public/applications`; no identity-header
contamination; rate-limited via existing plugin.
Audit risk LOW for A7, with one observation (F4).

## A8 — Form publishing accepts `chapter_select` and persists it

**Publish path (`services/api/app/services/forms.py`):**
`publish_form` validates via
`FormDefinitionPublish.model_validate(request)`. With
the discriminated union, `request.fields` accepts
mixed-type variants, including `FormFieldChapterSelect`.
Each field is dumped via `field.model_dump(mode="json")`
into JSONB. No serializer-level change is needed because
Pydantic emits the discriminator key naturally.

**Validator constraints (§3 form definition changes):**
- `chapter_select` is allowed only on global forms (β-1
  scope lock).
- A form may contain at most one `chapter_select`.
- `chapter_select.required` is locked to `True`
  (`Literal[True] = True`).

These constraints belong in
`FormDefinitionPublish.fields` validation (or in a
post-validator on the union). §7 TG-1 covers them
(duplicate, `required=false`, non-global scope, blank id/
label, conflicting `routing_rules.review_scope`).

**Routing-rules default (§3 forms.py:55-59):**
`_effective_routing_rules` adjusted so a global form
containing `chapter_select` does *not* default
`review_scope` to global. Submit-time override sets
the actual `target_scope` from the selected chapter.

**Authority for publish:** unchanged from current — the
authority/officer publish path still applies through
`mutate_entity(scope_kind=scope.scope_kind, scope_id=scope.scope_id)`.
No new permission is introduced for `chapter_select`.

**Verdict:** Publishing accepts the new variant via the
same Pydantic + JSONB path that handles existing
variants. Validator constraints land at the contract
boundary, not at the service. Audit risk LOW for A8.

## Findings

### F1 — `ApplicationFormField.model_validate` call site after union refactor

**Severity:** medium-low (regression risk, easy to miss).

**Where:** `services/api/app/services/applications.py:499`
calls `ApplicationFormField.model_validate(raw)`. After
the discriminated-union refactor (§3
`services/api/app/contracts/applications.py`),
`ApplicationFormField` becomes a TypeAlias for
`Annotated[Union[...], Field(discriminator="type")]` and
no longer exposes `.model_validate`.

**Action:** during implementation, switch to
`pydantic.TypeAdapter(ApplicationFormField).validate_python(raw)`
(or wrap with a thin RootModel and validate through it).
Add a unit test that publishes a form, reads it back, and
exercises `validate_application_responses` against the
re-parsed fields with at least one `chapter_select` and
one of every existing variant — this catches the regression
end-to-end.

### F2 — Form-lookup override gate

**Severity:** medium-low (correctness, scope-sensitive).

**Where:** the new public-submit chapter-selector
handling in
`services/api/app/services/applications.py` (the
`_submit_application_internal` path, per §3 modified
files `:473-490`, `:493-548`, `:676-829`, `:845-896`).

**Risk:** the override that swaps `validated.scope` for
the global form lookup must trigger only when the
*current global* form contains a required
`chapter_select` field *and* the public submitter sent
`scope_kind=chapter`. A too-broad override would let
public submitters target a global form with mismatched
scope; a too-tight override would 404 when the global
form contains a chapter selector but the SPA, for any
reason, sent global scope.

**Action:** unit-test the gate explicitly with three
positive and three negative cases:
- positive: chapter-selector global form + `scope_kind=chapter`
  + matching response → submitted as chapter-scoped;
- positive: chapter-selector global form + `scope_kind=chapter`
  + missing/mismatched response → 422;
- positive: non-selector global form + `scope_kind=global`
  → existing global path (no override);
- negative: non-selector global form + `scope_kind=chapter`
  → existing chapter form lookup path (404 if no chapter
  form exists);
- negative: chapter-selector global form + `scope_kind=global`
  → 422 (selector required);
- negative: missing chapter-select response on a
  chapter-selector form → 422.

TG-3 covers most of these; ensure the "non-selector +
chapter scope" case is not accidentally redirected to the
global form by an over-broad override.

### F3 — Seed v2 SQL must coexist with v1 + advance only when v1 is current

**Severity:** medium (data-migration correctness).

**Where:**
`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`.

**Risk:** the existing seed uses a deterministic UUID
(`'init-122:public-intake-global:v1'`) and relies on the
`current_global` / `existing_seed` CTEs to be no-op when
either is present. The v2 seed must:
1. Use a new deterministic UUID (e.g.,
   `'init-135:public-intake-global:v2'`).
2. Insert v2 only when (a) no current global form exists
   *or* (b) the current global form is the v1 seed
   (deterministic id match).
3. When advancing v1 → v2, archive the v1 row in the
   same transaction (set `status='archived'`,
   `archived_at`), bump aggregate version, write the
   `form.publish` action and `form.published`
   state-change with `version: 2`, and update
   `aggregate_heads.current_seq=2`.
4. Preserve the existing "officer-published form present;
   skipping seed" branch when current is neither v1 nor
   v2 deterministic id.
5. Preserve the BL-002 fail-closed guard (lines 14-31).

**Action:** during implementation, write the v2 seed SQL
with explicit branches and add an integration test that
exercises:
- empty DB → v2 inserted at version 1;
- v1 current → v1 archived, v2 current at version 2;
- officer-published current → no-op;
- v2 already current → no-op.

The seed today does not handle case (b) — it only
no-ops or inserts. This is a real upgrade path that
must land cleanly.

### F4 — Pomerium "implicit public via catch-all" pattern is fragile

**Severity:** low (observation, not blocking).

**Where:**
`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
+ `public-intake-rate-limit.yaml` ingress combination.

**Risk:** the public chapter endpoint reaches the API
through a catch-all `/` Pomerium route that allows
public unauthenticated access; there is no explicit
Pomerium route for `/api/public/...`. If a future change
adds an explicit Pomerium prefix-route for `/api/`
*without* `allow_public_unauthenticated_access` and
*with* `pass_identity_headers: true`, all public-intake
endpoints would silently start receiving Pomerium
identity headers and may fall behind authentication.

**Action:** the FastAPI route for `/api/v1/public/chapters`
must not depend on `get_pomerium_principal`,
`verify_applicant_receipt`, or any identity dependency.
Document the public-no-auth posture in the endpoint
docstring. If Phase 6+ tightens Pomerium config, an
explicit `/api/public/` prefix-route with
`allow_public_unauthenticated_access: true` and
`pass_identity_headers: false` should be added in the
same PR — but that is out of scope for INIT-135.

## Verdict reasoning

INIT-135 holds the audit gate at LOW risk:

- **PII (A1, A6):** the public chapter list is a typed
  `{id, name}` wrapper; admin/officer metadata is
  excluded by contract; active-only filter is exercised
  by TG-2; the only operator-controlled field is the
  chapter `name`, which is already officer-visible and
  not member-derived.
- **Round-trip (A2):** discriminated union with the same
  JSON keys; JSONB storage is unchanged; one
  implementation detail (F1) on `TypeAdapter` for the
  union alias must land cleanly.
- **Submit (A3):** server-side re-check of chapter
  existence + active state inside
  `validate_application_responses`; explicit `responses[chapter]
  == scope.scope_id` agreement check; 422 on missing /
  inactive / mismatch; no new authorization branch; F2
  flags the form-lookup override gate as a correctness
  hot spot for explicit unit tests.
- **BL-002 preservation (A4):** seed-job v2 retains the
  fail-closed/no-op invariant for officer-published
  forms; submit handling is conditional on field
  presence; authenticated chapter-specific submit is
  untouched; F3 flags the v1→v2 seed advance as a
  migration that must be tested explicitly.
- **Backwards compat (A5):** byte-compatible JSON for
  existing field variants; only the union-method-call
  refactor (F1) is structurally invasive; e2e and
  validator updates are intentional, not regressive.
- **Pomerium (A7):** new route follows the existing
  `/api/public/applications` ingress pattern; identity
  headers are not injected; rate-limited via the
  existing Kong plugin; F4 is a future-proofing
  observation, not a blocker for β-1.
- **Form publish (A8):** discriminated union accepts
  `chapter_select` through the same Pydantic +
  `model_dump(mode="json")` + JSONB path; validator
  constraints (single, required, global-only) are
  contract-level; routing-rules default change is
  scoped to chapter-selector forms.

Verdict: LOW.

AUDIT_DONE: plans/risk/init-135-audit.md
