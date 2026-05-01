# INIT-136 — Audit risk gate

**Verdict:** LOW

Scope: BL-010 β-2 — multi-page application forms plus
field-level conditional visibility. Adds `page: int` and
`visible_when: FormFieldVisibleWhen | None` to the shared
`_BaseFormField` in
`services/api/app/contracts/applications.py:80-101`,
extends `FormDefinitionPublish` validation
(`services/api/app/contracts/applications.py:215-256`),
extends `validate_application_responses` with a
visibility pass
(`services/api/app/services/applications.py:496-573`),
mirrors the schema in `services/web/src/api/client.ts`,
and converts the public form renderer
(`services/web/src/features/public/ApplicationFormRoute.tsx`)
into a wizard with progress, Next/Previous, and
visibility-driven payload assembly.

The audit gate inspects: server-side re-evaluation of
`visible_when` (no client bypass), required-vs-hidden
asymmetry, predicate-source ordering and cycle prevention,
predicate-source type restriction, page-number invariants
(>= 1, sparse OK), last-page detection under sparse
numbering, hidden-field PII non-leakage on submit, and
preservation of the β-1 `chapter_select` round-trip.

Source proposal:
`proposals/27-init-136-multi-page-conditional.md`.
Source problem map: `research/28-bl-010-problem-map.md`.
β-1 ground state:
`proposals/17-init-135-chapter-selector.md` and the audit
`plans/risk/init-135-audit.md`.

## A1 — `visible_when` is re-evaluated server-side

**Surface:** Q4 (§2.4) explicitly locks server-side
re-evaluation: "The submit path must re-evaluate the
visible field set server-side." §3 Substrate / Submit
Validator names the call site:
`validate_application_responses` in
`services/api/app/services/applications.py:496-573` (the
existing parser, response-key check, required check, and
type validator). The proposal extends it with a
deterministic, ordered visibility pass that runs after
`_chapter_selector_override` selects the effective form
row and *before* persistence, at the existing call site
inside `_submit_application_internal`
(`services/api/app/services/applications.py:780`).

**Algorithm lock (§3 Submit Validator):**

1. Parse fields and preserve authored order via
   `_APPLICATION_FORM_FIELD_ADAPTER`.
2. Build a response lookup from submitted responses.
3. For each field in order, evaluate `visible_when` using
   only earlier visible source fields.
4. Produce the visible field map.
5. Reject submitted response keys whose field is hidden.
6. Require only visible required fields.
7. Type-validate submitted visible values.

The order matters: a hidden field's response is rejected
*before* the type validator runs, which prevents a
crafted client from smuggling a typed-and-required value
for a hidden source. The "earlier visible source" rule
also prevents a chain where a hidden parent could
spuriously make a child visible — predicates evaluated
against a hidden source resolve to false (Q1: "Missing or
hidden source responses evaluate the predicate as
false").

**TG-3 coverage:** "If the client submits a response for
a field whose predicate evaluates false, submit returns
validation error"; "If the client omits a field whose
predicate evaluates true and `required=true`, submit
returns validation error"; "If the controlling response
changes from true to false, stale dependent field values
are rejected." All three exercise server-side
re-evaluation, not client behavior.

**Verdict:** Server-side re-evaluation is locked at the
contract, algorithm, call-site, and test-plan layers.
Audit risk LOW for A1. One implementation finding (F1)
on hidden-source semantics under negative operators.

## A2 — Required is enforced for visible fields, skipped for hidden

**Surface:** Q4 (§2.4): "Required fields are required
only when their field is visible in the final visibility
graph. Optional visible fields may be omitted. Submitted
visible fields are type-validated with the existing
per-type rules. The existing `chapter_select` validation
and active chapter check remain intact."

**Existing validator behavior:** today
`validate_application_responses` flags any required
field absent from the response set
(`services/api/app/services/applications.py:515-523`).
After β-2, the "missing required" check operates over
the *visible* required set only. Optional visible fields
remain omittable. Hidden fields are removed from the
response set as unknown/invalid keys (step 5 of the
algorithm above), so a submitted-but-hidden required
value never reaches the per-type check.

**Always-visible behavior preserved:** `chapter_select`
remains always-visible (Q6 anti-scope: "It cannot have
`visible_when` and cannot be referenced by another
field's `visible_when`"). The β-1 active-chapter and
response/scope-agreement checks at
`services/api/app/services/applications.py:557-572` stay
in the per-type validator and run after visibility
filtering, which is a no-op for `chapter_select`.

**TG-2 coverage:** "A required field on page 2 with
`visible_when` false may be omitted and the submit
succeeds. The same required field with `visible_when`
true must be present. If present but blank, the existing
field-type required validation fires. A required
always-visible field on any derived page remains
required on final submit." All four cases exercise the
required-vs-visible asymmetry directly at the validator
boundary, not via the SPA.

**Verdict:** Required-when-visible is locked. Audit risk
LOW for A2.

## A3 — Predicate must reference an earlier field; cycles prevented

**Ordering lock (Q1, §2.1):** "The referenced `field_id`
must appear earlier in `form_definition.fields`;
same-page references are allowed only when the source
field is ordered before the dependent field."

**Cross-page lock (Q2, §2.2):** "A field's
`visible_when.field_id` must reference an earlier field,
not merely an earlier page number."

**Publish-time enforcement (§3 Contracts):**
`FormDefinitionPublish` already runs
`validate_unique_field_ids`
(`services/api/app/contracts/applications.py:230-241`)
and `validate_chapter_select_contract`
(`:243-256`). The β-2 extension adds publish-time
validation for "page values, predicate source existence,
earlier-field ordering, supported source field types,
and `chapter_select` restrictions." Earlier-field
ordering is checked at publish time, so an authored form
with a forward reference (or a self-reference, which is
the trivial cycle) fails before the row is ever stored.

**Cycle prevention is structural:** by enforcing that
each `visible_when.field_id` references a field strictly
earlier in `fields[]`, the visibility-dependency graph
is a DAG with topological order = field-array order.
There is no walk that reaches itself. The runtime
visibility pass mirrors this — "evaluate `visible_when`
using only earlier visible source fields" — so even if
an attacker bypassed publish-time validation
(impossible without a contract change), the validator
would not loop.

**TG-1 coverage:** "Invalid predicates fail: unknown
source, forward reference, unsupported source type,
invalid op, `in` / `not_in` with non-list value,
`visible_when` on `chapter_select`, and duplicate field
ids." Forward-reference is named explicitly. Unknown
source covers references to non-existent fields.
Self-reference is structurally impossible because a
field cannot precede itself.

**Verdict:** Ordering is locked at publish time and
mirrored at submit time. Cycle prevention is structural,
not heuristic. Audit risk LOW for A3.

## A4 — Predicate source restricted to scalar field types

**Source-type lock (Q1, §2.1):** "For beta-2, predicate
sources are scalar fields only: `short`, `long`,
`number`, `select`, and `boolean`. Do not allow
`multi_select` or `chapter_select` as predicate sources.
This keeps the language deterministic and avoids array
containment semantics or chapter-routing coupling."

**Operator semantics:** `eq` / `neq` are strict scalar
equality; `in` / `not_in` test scalar membership in a
configured `value` list. None of these have meaningful
semantics over a `multi_select` array (which would
require a containment-vs-equality decision the proposal
explicitly defers) or over `chapter_select` (which is a
β-1 routing field, not a content predicate source).

**Chapter-routing decoupling (Q6, §2.6 anti-scope):**
"`chapter_select` remains the beta-1 routing field and
must be always visible when present. It cannot have
`visible_when` and cannot be referenced by another
field's `visible_when`." This guard is enforced at
publish time alongside the source-type check, and is
exercised by TG-1 ("`visible_when` on `chapter_select`")
and TG-3 ("`chapter_select` cannot be hidden or used as
a predicate source").

**Future-proofing:** the `op` set is locked to
`{eq, neq, in, not_in}`. JSONLogic / dotted boolean
expressions are explicitly excluded ("Do not use
JSONLogic or dotted boolean expressions in this slice"),
so the publish-time validator can enumerate supported
ops directly.

**Verdict:** Source-type whitelist is enforced at the
contract layer; chapter-routing decoupling is double-
locked (no `visible_when` *on* `chapter_select`, and no
reference *to* `chapter_select`). Audit risk LOW for A4.

## A5 — Page numbers: `>= 1`, sparse-allowed, derived sequence

**Field contract (§3 Contracts):**
`page: int = Field(default=1, ge=1)` on
`_BaseFormField`. Authored JSON without a `page` key
defaults to 1, so the existing β-1 seed and any
officer-published forms continue to validate (no
migration needed). Page < 1 fails at the Pydantic
field-level constraint.

**Sparse handling (Q2, §2.2):** "Page numbers may be
sparse in authored JSON, but API read normalizes the
runtime page sequence by sorting distinct page values.
The UI displays contiguous steps based on that derived
order."

This means an authored form with pages `[1, 1, 4, 4, 7]`
collapses to a derived 3-step wizard
(Step 1 of 3 / Step 2 of 3 / Step 3 of 3). The page
attribute is a *grouping key*, not a step index.
The SPA derives step indices from the sorted distinct
page values; the API contract does not require
contiguous pages.

**Top-level pages list (Q2 anti-scope):** "No top-level
`pages` list in beta-2. Page titles, page-level
conditions, and per-page metadata are future work." The
absence of a separate pages descriptor avoids two
sources of truth (authored pages list vs. derived from
fields).

**Publish-time validation (§3 Contracts):** "page values"
is in the publish-time validation list. Field-level
`ge=1` covers per-field validation; the publish-time
hook should also confirm that at least one field exists
(already enforced by `min_length=1` on
`FormDefinitionPublish.fields`) so the derived page set
is non-empty.

**Verdict:** Page > 0 is contract-enforced; sparse is
explicitly allowed and normalized at read time. Audit
risk LOW for A5.

## A6 — Last-page detection works for sparse + skipped pages

**Wizard derivation (Q3, §2.3):** "Render the public
form as a wizard: Current page shows only visible fields
assigned to that page. Progress text shows `Step N of M`.
Next validates visible required fields on the current
page before advancing. Previous returns to the prior
derived page without losing local responses. Submit
application appears only on the last derived page."

**Skip-empty-pages rule (Q3):** "When a prior response
changes, the SPA must recompute visibility for all
fields, remove hidden field values from the pending
payload, and clamp the current page to the last still-
reachable page if the current page no longer has any
visible fields. If a page has no visible fields after
recomputation, the wizard skips it for navigation and
progress."

**Last-page invariants — what's locked:**

- `M` is the count of *non-empty* derived pages after
  visibility recomputation, not the count of distinct
  authored page values.
- `Submit application` appears only on the last
  non-empty derived page, even if that page is not the
  largest authored page number.
- A controlling response that hides every field on
  every page after the current must surface Submit on
  the current page (since the "last derived page" set
  is recomputed after every controlling change).

**Sparse-numbering example:** authored pages `[1, 5, 9]`
where page 5 has only one field with `visible_when`
false. Derived pages without recomputation = {1, 5, 9};
after recomputation = {1, 9} (page 5 is empty). Wizard
shows "Step 1 of 2" then "Step 2 of 2" with Submit on
page 9. Sparse page numbers are independent of
last-page detection because both rely on the derived
non-empty page list, not on `max(page)`.

**TG-4 coverage:** "Initial render shows page 1 fields
and `Step 1 of 2`"; "Changing a controlling field
toggles the dependent field"; "Final submit posts
visible filled fields from all pages, not only the last
page." TG-4 also covers Next/Previous flow but does not
explicitly assert "submit appears on a page that is not
the maximum authored page number" — see F2 below.

**Verdict:** Sparse pages and skipped-empty-pages
combine cleanly because both feed the same derived list.
Audit risk LOW for A6, with one finding (F2) on
explicit last-page-after-recomputation test coverage.

## A7 — Hidden field values are not sent on submit (PII / anti-bypass)

**Anti-bypass surface (§1 Problem Statement):** "Hidden
fields are not rendered, not browser-validated, not
submitted, and not server-validated as required. The
server remains authoritative. The submit path
re-evaluates conditional visibility against the
submitted response set before persistence, so client-
side bypasses cannot smuggle hidden fields or skip
visible required fields."

**Defense-in-depth at four layers:**

1. **Render gate (SPA, §3):** "Render only visible
   fields for the current derived page" — the user
   never sees an input for a hidden field, so they
   cannot enter a value through the UI.
2. **Payload assembly (SPA, §3):** "Build the final
   `responses` payload from visible fields only, across
   all pages, not only the current page" and "Evaluate
   `visible_when` in a shared pure helper used by
   render, navigation, and submit payload assembly."
   The pure helper guarantees the same visibility set
   drives render and payload, eliminating the
   "rendered hidden / submitted visible" or vice-versa
   class of bug.
3. **Draft restore (SPA, §3):** "Draft preservation
   should keep working through `sessionStorage`, but
   restore must not revive hidden fields into the
   submit payload after visibility recomputation." This
   is a UX foot-gun (see F4) but the *server-side*
   guard catches it regardless.
4. **Server validator (§3 Submit Validator):** "Hidden
   fields submitted by the client are rejected as
   invalid response fields" — step 5 of the visibility
   pass. A crafted client cannot bypass the SPA's
   payload assembly because the server runs the same
   evaluator and rejects 422 on any hidden submitted
   key.

**TG-3 directly tests bypass:** "If the client submits a
response for a field whose predicate evaluates false,
submit returns validation error" and "If the
controlling response changes from true to false, stale
dependent field values are rejected." The latter case
is the specific PII risk — a value entered before the
applicant changed their mind, then carried in the
sessionStorage draft into the final submit.

**PII inventory:** hidden field values may contain
free-text PII (an applicant who started typing into a
disability-disclosure field, then unchecked the
disclose-disability boolean controlling its visibility,
must not have that text reach the server). The
defense-in-depth makes both the SPA elision and the
server rejection independent paths to the same outcome.
Even a defective SPA that forgets to elide the value
still produces a 422 with no persistence — the
applicant must explicitly resubmit, the value never
reaches `applications.responses` JSONB, and there is no
audit row.

**Residual risk:** the 422 path itself can leak via
error messages. The validator should reject hidden
keys with a generic "unknown response fields" or "field
is not currently visible" message, not echo the
submitted value back. F3 below.

**Verdict:** Hidden fields are blocked at four
independent layers and exercised at TG-3. Audit risk
LOW for A7, with one finding (F3) on validator error-
message PII discipline.

## A8 — Form-definition round-trip preserved (`chapter_select` still works)

**Contract extension shape (§3 Contracts):** "INIT-136
should extend the shared field base rather than
duplicating each variant. Add: `FormFieldVisibleWhen`
model with `field_id`, `op`, and `value`. `page: int =
Field(default=1, ge=1)` on `_BaseFormField`.
`visible_when: FormFieldVisibleWhen | None = None` on
`_BaseFormField`."

Adding fields to the base means *every* variant
(`FormFieldShort`, `FormFieldLong`, `FormFieldNumber`,
`FormFieldSelect`, `FormFieldMultiSelect`,
`FormFieldBoolean`, `FormFieldChapterSelect`)
inherits `page` and `visible_when` for free. The
discriminated union at
`services/api/app/contracts/applications.py:192-201`
is unchanged structurally — same `Annotated[Union,
Field(discriminator="type")]`, same JSON keys
(`id`, `type`, `label`, `required`, `placeholder`).

**JSONB byte-compatibility:** existing seeded forms with
no `page` and no `visible_when` deserialize cleanly:
`page` defaults to 1, `visible_when` defaults to `None`.
Re-serialization via `field.model_dump(mode="json")`
emits `page: 1` and `visible_when: null` (or omits
`visible_when` if `exclude_none=True` — the
implementation must pick one and stick to it). Either
choice round-trips because both the absent key and
explicit null parse to `None`.

**chapter_select preservation (Q6, §3 Contracts):**
"`chapter_select` remains the beta-1 routing field and
must be always visible when present. It cannot have
`visible_when` and cannot be referenced by another
field's `visible_when`." This adds two publish-time
guards but does not remove or alter
`FormFieldChapterSelect`. The existing
`validate_chapter_select_contract` model-validator at
`services/api/app/contracts/applications.py:243-256`
remains intact; the β-2 extension layers a new model-
validator that asserts `visible_when is None` for
`chapter_select` variants and that no other field's
`visible_when.field_id` points at a `chapter_select`.

**Active-chapter validation chain:** the β-1 path at
`services/api/app/services/applications.py:557-572`
(per-type validation for `chapter_select`, including
`fetch_active_public_chapter` and the
`responses[chapter] == scope.scope_id` check) runs
inside the per-type loop *after* the visibility filter.
Because `chapter_select` is always visible, the filter
is a no-op for that field, and the β-1 active-chapter
guard runs unchanged.

**Form-lookup override preservation (§3 Submit
Validator):** "The beta-1 chapter-selector override
gate must remain narrow: it should still fire only when
the current global form contains the required
`chapter_select` field and the submitted chapter scope
matches the selector response. INIT-136 must not let
conditional visibility hide that routing field or turn
chapter routing into a conditional form feature." The
β-1 `_chapter_select_field_ids`
(`services/api/app/services/applications.py:575`) and
`_chapter_selector_override`
(`:584-597`) helpers are not modified; β-2 only adds
the visibility pass *after* the override has selected
the form row.

**TG-1 coverage:** "extends API form contract tests so
a published form with multiple pages and a conditional
field round-trips through publish/read with: `page`
preserved. `visible_when` preserved. `ApplicationFormField`
union parsing still accepts all existing field types
plus `chapter_select`. Invalid predicates fail: ...
`visible_when` on `chapter_select`."

**Verdict:** Round-trip is structural via the same
discriminator-keyed union; β-1 helpers and active-
chapter validation are untouched; visibility is a no-op
for the always-visible `chapter_select`. Audit risk LOW
for A8.

## Findings

### F1 — Hidden-source predicate evaluation under `neq` / `not_in`

**Severity:** medium-low (correctness, easy to get
backwards).

**Where:** the new visibility pass in
`validate_application_responses`
(`services/api/app/services/applications.py:496-573`)
and the SPA helper
(`services/web/src/features/public/ApplicationFormRoute.tsx`).

**Risk:** Q1 (§2.1) locks "Missing or hidden source
responses evaluate the predicate as false." This is the
correct safe-default for the *visibility decision*, but
the implementation must apply it before per-op
semantics, not by encoding it inside each operator. The
bug shape: a developer writes `eq` and `neq` as `==` and
`!=` on the source value; for a missing source, `None ==
"yes"` is False (correct, field stays hidden) but `None
!= "yes"` is True (incorrect — field would become
visible without a source response). The proposal locks
the right rule at the contract layer; the implementation
must enforce it as a precondition: "if source is missing
or hidden, predicate is False, regardless of `op`."
The same applies to `not_in` against a missing source.

**Action:** unit-test the visibility evaluator with
explicit cases for each op against (a) absent source
response, (b) hidden source response (source field's
own `visible_when` is false), and (c) present-but-empty
source response (e.g., empty string for a `short`
field). Required result for all three: `False` for any
operator. Add the same tests to the SPA evaluator so
the shared-helper assertion (§3 SPA Renderer:
"Evaluate `visible_when` in a shared pure helper used
by render, navigation, and submit payload assembly")
holds for the negative-operator cases.

### F2 — Last-page detection after visibility recomputation

**Severity:** medium-low (UX correctness, sparse-page
edge case).

**Where:** SPA wizard logic in
`services/web/src/features/public/ApplicationFormRoute.tsx`.

**Risk:** Q3 locks "Submit application appears only on
the last derived page" and "If a page has no visible
fields after recomputation, the wizard skips it for
navigation and progress." Combined, this means Submit
must appear on the last *non-empty* derived page after
every controlling-field change, not on the page with
the largest authored `page` number. A naive
implementation that caches `lastPage = max(distinct
page values)` and shows Submit only when
`currentPage === lastPage` will fail when a controlling
response makes the highest-numbered page empty: the
wizard would skip that empty page (per the skip rule),
clamp to the previous page, but never show Submit
because `currentPage !== lastPage`.

**Action:** TG-4 covers the basic two-page wizard flow
but does not explicitly assert "Submit appears on a
page that is not the maximum authored `page`." Extend
TG-4 with two cases: (a) a 3-page form where the
controlling response on page 1 hides every field on
page 3 — assert Submit appears on page 2 with `Step 2
of 2`; (b) a sparse-page form authored as `[1, 5, 9]`
where page 5's only field is conditionally hidden —
assert Submit appears on page 9 with `Step 2 of 2`,
not `Step 3 of 3`. Implementation: derive
`lastDerivedPage` and `M` from the visibility-filtered
non-empty page set on every recomputation, not from
the static authored page set.

### F3 — Server validator error messages must not echo hidden values

**Severity:** low (PII hygiene).

**Where:** the new "reject hidden submitted keys"
branch in
`validate_application_responses`
(`services/api/app/services/applications.py:496-573`).

**Risk:** when the client submits
`responses[hidden_field] = "some value"` and the
visibility pass marks it hidden, the validator raises
`InvalidApplicationResponseError`. Today's analogous
"unknown response fields" message includes only the
field id (`services/api/app/services/applications.py:512-513`).
The β-2 extension must follow the same discipline —
reject with the field id (or a generic "field is not
currently visible" message), never echo the submitted
value. Echoing the value would leak hidden free-text
PII into the API error response, which the SPA may
display, which a third-party error monitor may
ingest, etc.

**Action:** match the existing `unknown response
fields: {ids}` shape exactly, listing only field ids,
no values. Add a unit test that submits a hidden
required `long`-type field with a long PII-shaped
string value; assert the 422 body contains the field
id but not the value. The same discipline applies if
the validator emits a "stale dependent field" message
(TG-3 case "If the controlling response changes from
true to false, stale dependent field values are
rejected") — log the field id, not the value.

### F4 — sessionStorage draft restore must filter through visibility before payload assembly

**Severity:** low (UX, server catches the failure mode).

**Where:** SPA draft restore in
`services/web/src/features/public/ApplicationFormRoute.tsx`.

**Risk:** §3 SPA Renderer locks "Draft preservation
should keep working through `sessionStorage`, but
restore must not revive hidden fields into the submit
payload after visibility recomputation." A naive
implementation reads the draft into local state, then
runs visibility, then assembles payload. If the order
is "read draft → assemble payload → run visibility",
or if the draft is read directly in the submit
handler instead of through the visibility-aware
helper, hidden field values can leak into the
submitted payload. The server's hidden-key rejection
(A1, A7) catches this as a 422, so it is not a PII
*leak* — but it is a UX failure mode where applicants
who refresh mid-form get blocked at submit with a
confusing error.

**Action:** the shared visibility helper (§3 SPA: "Use
in render, navigation, and submit payload assembly")
must also wrap the sessionStorage read at the
component-state boundary, so the local response state
never contains values for fields whose `visible_when`
is currently false. TG-4 should add a refresh-mid-form
case: enter values across two pages, change a
controlling response so a previously-filled page
becomes hidden, refresh the page (sessionStorage
restores the draft), then submit. Assert the submitted
payload contains only the visible-after-recomputation
field values, and that the request returns 200, not
422.

## Verdict reasoning

INIT-136 holds the audit gate at LOW risk:

- **Server-side re-evaluation (A1):** the visibility
  pass is locked at the algorithm, call-site, and
  test-plan layers. TG-3 directly exercises three bypass
  classes (smuggled hidden, omitted required, stale
  dependent). F1 flags an implementation hot spot for
  negative operators.
- **Required-when-visible (A2):** the missing-required
  check operates over the visible required set only.
  Optional visible fields remain omittable. The β-1
  always-visible `chapter_select` keeps its existing
  active-chapter and scope-agreement guards.
- **Predicate ordering and cycles (A3):** the
  earlier-field rule produces a topological field-array
  order, making cycles structurally impossible. Publish-
  time validation forbids forward references and
  unknown sources.
- **Predicate source restriction (A4):** sources are
  whitelisted to scalar types (`short`, `long`,
  `number`, `select`, `boolean`); `multi_select` and
  `chapter_select` are excluded by name. The β-2 op set
  (`eq`, `neq`, `in`, `not_in`) is closed and
  enumerable.
- **Page numbers (A5):** field-level `ge=1` and
  publish-time validation enforce `page >= 1`. Sparse
  authored pages are explicitly allowed and normalized
  at read time via sorted distinct page values.
- **Last-page detection (A6):** Submit appears on the
  last non-empty derived page after every visibility
  recomputation, independent of authored page numbers.
  F2 flags a sparse-page test gap.
- **Hidden-field anti-bypass (A7):** four independent
  defense layers (render gate, shared visibility
  helper, draft-restore filter, server reject). TG-3
  exercises the most adversarial path (controlling
  response flips true → false). F3 flags validator
  error-message PII discipline; F4 flags the
  sessionStorage UX foot-gun.
- **`chapter_select` round-trip (A8):** the
  contract extension layers `page` and `visible_when`
  on `_BaseFormField`, leaving the discriminated union
  and per-variant validators (including
  `validate_chapter_select_contract`) intact. The β-1
  form-lookup override and active-chapter checks run
  unchanged.

Verdict: LOW.

AUDIT_DONE: plans/risk/init-136-audit.md
