# INIT-136 — Shortcut risk gate (BL-010 β-2)

**Verdict:** LOW

Scope: BL-010 β-2 — multi-page public application forms and
field-level conditional visibility. The slice extends the
β-1 chapter-selector ground state with a `page` attribute and
a `visible_when` predicate on every field, a wizard-style SPA
renderer, server-side visibility re-evaluation in the submit
validator, and publish-time validation of predicate shape.

The shortcut gate inspects whether INIT-136 ships a real
server-side `visible_when` evaluator (not a "trust the client"
client-only filter), a real wizard with page state (not a
"render-everything-then-CSS-hide-all-but-page-N" cheat), avoids
"support multi_select predicates later" placeholder stubs, has
tests that genuinely exercise the required-field-on-hidden-page
edge case, and locks a form-version bump if the seed contract
changes.

Source: `proposals/27-init-136-multi-page-conditional.md`,
`research/28-bl-010-problem-map.md`,
`proposals/17-init-135-chapter-selector.md`.

## C1 — Real `visible_when` evaluator on the server (not "trust the client")

**Pass.**

Q4 (proposal lines 65-78) locks the API contract: the submit path
must re-evaluate the visible field set server-side. Q4 enumerates
the four behaviors the validator extension must implement:

> - Hidden fields submitted by the client are rejected as invalid
>   response fields.
> - Required fields are required only when their field is visible
>   in the final visibility graph.
> - Optional visible fields may be omitted.
> - Submitted visible fields are type-validated with the existing
>   per-type rules.

§3 (Substrate → Submit Validator, lines 144-167) gives the
implementation contract: extend `validate_application_responses`
in `services/api/app/services/applications.py` with a
deterministic visibility pass that

1. Parses fields and preserves authored order.
2. Builds a response lookup from submitted responses.
3. Evaluates `visible_when` using only earlier visible source
   fields.
4. Produces the visible field map.
5. Rejects submitted response keys whose field is hidden.
6. Requires only visible required fields.
7. Type-validates submitted visible values.

The pass is positioned "after `_chapter_selector_override`
selects the effective form row and before persistence, at the
existing call site inside `_submit_application_internal`"
(proposal lines 165-166). It is not a parallel "trusted-client"
fast path; the same call site every public submit currently
goes through.

The semantics are deterministic: Q1 (lines 14-38) locks
"missing or hidden source responses evaluate the predicate as
false" so a hidden source can never resolve a dependent's
visibility to true. Combined with the earlier-field-only rule
("the referenced `field_id` must appear earlier in
`form_definition.fields`; same-page references are allowed only
when the source field is ordered before the dependent field"),
the visibility graph is acyclic and resolvable in a single
in-order pass — there is no "iterate until fixed point" or
"trust the client's recompute" escape hatch.

TG-3 (proposal lines 194-202) is dedicated to proving the server
does not trust the SPA, and names four negative cases:

> - If the client submits a response for a field whose predicate
>   evaluates false, submit returns validation error.
> - If the client omits a field whose predicate evaluates true
>   and `required=true`, submit returns validation error.
> - If the client submits an unknown field id, the existing
>   unknown-field validation still returns validation error.
> - If the controlling response changes from true to false,
>   stale dependent field values are rejected.

The chapter-selector override gate is also explicitly
preserved: "The beta-1 chapter-selector override gate must
remain narrow … INIT-136 must not let conditional visibility
hide that routing field or turn chapter routing into a
conditional form feature" (proposal lines 167-168).

**Risk:** the natural shortcut would be to (a) accept the
client's submitted response set verbatim and only validate
type/required on what the SPA chose to send, or (b) implement
visibility as a SPA-only filter and have the server simply
allow whatever responses arrive. Either bypass would let a
crafted client smuggle hidden-field values into persistence or
skip required visible fields by lying about what is "visible."

**Mitigation:** server-side deterministic visibility pass in
the same submit validator the rest of the response shape goes
through, with explicit reject-on-hidden and require-on-visible
rules, plus four named TG-3 negative cases at the API contract
level.

**Verdict:** Not a shortcut.

## C2 — Real wizard component, not "hide all but page N with CSS"

**Pass.**

Q3 (proposal lines 53-63) locks the SPA as a real wizard with
real page state, not a single-render with CSS visibility:

> - Current page shows only visible fields assigned to that
>   page.
> - Progress text shows `Step N of M`.
> - `Next` validates visible required fields on the current
>   page before advancing.
> - `Previous` returns to the prior derived page without losing
>   local responses.
> - `Submit application` appears only on the last derived page.

§3 (Substrate → SPA Renderer, lines 121-141) translates this
into a concrete renderer contract for
`services/web/src/features/public/ApplicationFormRoute.tsx`:

> - Derive ordered pages from `form.fields`.
> - Track the current derived page in a Solid signal.
> - Track local response state across pages instead of reading
>   only final `FormData` at submit.
> - Evaluate `visible_when` in a shared pure helper used by
>   render, navigation, and submit payload assembly.
> - Render only visible fields for the current derived page.
> - Skip derived pages that have no visible fields.
> - Build the final `responses` payload from visible fields
>   only, across all pages, not only the current page.

"Render only visible fields for the current derived page" is
the operative phrase: fields outside the current derived page
are not in the rendered output, not merely visually hidden.
Combined with "build the final `responses` payload from visible
fields only, across all pages" (lines 137-138), hidden values
are stripped from the payload at submit time, not carried as
DOM-hidden inputs that a CSS toggle could re-expose.

Q3 also locks the recompute-and-clamp behavior when answers
change: "When a prior response changes, the SPA must recompute
visibility for all fields, remove hidden field values from the
pending payload, and clamp the current page to the last still-
reachable page if the current page no longer has any visible
fields. If a page has no visible fields after recomputation,
the wizard skips it for navigation and progress" (proposal
lines 62-64). That rules out the "render once, toggle CSS"
shortcut twice over: navigation responds to live recomputation,
and pages with no visible fields are skipped from the page
sequence rather than displayed-empty or hidden-with-CSS.

Draft preservation is explicitly bounded: "Draft preservation
should keep working through `sessionStorage`, but restore must
not revive hidden fields into the submit payload after
visibility recomputation" (proposal lines 141-142). A
sessionStorage round-trip cannot smuggle hidden field values
back into the payload.

**Risk:** the shortcut would be (a) `<div style={{display: page
=== currentPage ? 'block' : 'none'}}>…fields…</div>` with all
fields rendered into the DOM and a single page-index toggle, or
(b) a "wizard" that keeps every page's `<input>` mounted and
relies on the server to ignore non-current-page values. Both
keep hidden-field DOM inputs alive and either let CSS bypass
restore them or send them in the payload regardless of page
state.

**Mitigation:** the SPA renders only the current page's visible
fields (not display-none-hidden), a Solid signal owns the
current page, recompute-and-clamp on response change, and the
submit payload is built from the visible-field map rather than
from iterating every `<input>` in the DOM.

**Verdict:** Not a shortcut.

## C3 — No "TODO: support multi_select predicates later" stubs

**Pass.**

Q1 (proposal lines 31-38) locks the predicate-source allowlist
explicitly at the contract level, not as a runtime check with a
follow-up TODO:

> For beta-2, predicate sources are scalar fields only:
> `short`, `long`, `number`, `select`, and `boolean`. Do not
> allow `multi_select` or `chapter_select` as predicate sources.
> This keeps the language deterministic and avoids array
> containment semantics or chapter-routing coupling.

The exclusion is enforced at publish time, per Q5 (lines 80-83):

> Contract validation must make authored JSON safe enough to
> publish: invalid page numbers, duplicate field ids, invalid
> predicates, forward references, and unsupported predicate
> sources fail at publish time.

§3 (Substrate → Contracts, lines 99-110) lists the required
publish-time checks against `FormDefinitionPublish`:

> - Publish-time validation in `FormDefinitionPublish` for page
>   values, predicate source existence, earlier-field ordering,
>   supported source field types, and `chapter_select`
>   restrictions.

TG-1 (lines 175-181) names the negative-case publish tests:

> Invalid predicates fail: unknown source, forward reference,
> unsupported source type, invalid op, `in` / `not_in` with
> non-list value, `visible_when` on `chapter_select`, and
> duplicate field ids.

§5 (Anti-Scope, lines 230-238) closes the "stub for later" door
in general:

> - Backwards-compatibility aliases, deprecated field names,
>   feature flags, transitional code paths, or placeholder
>   stubs.

So `multi_select` is not a runtime "warn and treat as always
visible" branch with a TODO; it is a publish-time
`FormDefinitionPublish` validation error, and any author who
writes a `visible_when` referencing a `multi_select` source can
never get that form into `form_definitions` at all. There is no
"support it in beta-3" code path waiting in the validator that
could trigger by accident.

The same line is held for chapter selectors: "`chapter_select`
remains the beta-1 routing field and must be always visible
when present. It cannot have `visible_when` and cannot be
referenced by another field's `visible_when`" (Q6, lines 90-91).
TG-3 (lines 200-202) names a guard test: "Keep beta-1 chapter-
selector override tests passing and add one guard case proving
`chapter_select` cannot be hidden or used as a predicate source."

**Risk:** the shortcut would be (a) a runtime branch that says
`if source.type == 'multi_select': return True  # TODO support
later` so authored forms publish but the predicate is silently
inert, or (b) a "lenient publish, strict submit" gap where the
publish step accepts unsupported source types and the submit
validator silently treats them as always-visible. Either
bypass would silently degrade the visibility contract and ship
dead-code stubs.

**Mitigation:** publish-time `FormDefinitionPublish` validation
rejects unsupported predicate sources before `form_definitions`
ever stores the form, named TG-1 negative cases enforce the
allowlist, anti-scope explicitly forbids placeholder stubs, and
the chapter-selector exclusion gets its own TG-3 guard test.

**Verdict:** Not a shortcut.

## C4 — Tests genuinely exercise the required-field-on-hidden-page edge case

**Pass.**

The test plan covers the required-field-on-hidden-page edge
case at four layers, with both positive and negative paths.

TG-2 (proposal lines 183-192) is the API submit validator
group:

> - A required field on page 2 with `visible_when` false may be
>   omitted and the submit succeeds.
> - The same required field with `visible_when` true must be
>   present.
> - If present but blank, the existing field-type required
>   validation fires.
> - A required always-visible field on any derived page remains
>   required on final submit.

The proposal also calls out the precise scope of "hidden page"
honestly:

> Although this test group may describe "hidden page" behavior,
> beta-2 implements field-level conditions only: the page is
> skipped only because it has no visible fields.

That is the right framing: β-2 does not have a `page-level`
predicate, so a "hidden page" is a page whose fields are all
hidden. TG-2 still exercises the resulting "required-on-hidden-
page" semantics from the validator's perspective.

TG-3 (lines 194-202) covers the server-side bypass shape: "If
the client omits a field whose predicate evaluates true and
`required=true`, submit returns validation error" — the
positive-required-when-visible case. And: "If the controlling
response changes from true to false, stale dependent field
values are rejected" — the controlling-flip case where the
client may have stale data.

TG-4 (lines 204-216) exercises the SPA-side wizard navigation
and conditional rendering, including the ones that surround
the required-on-hidden-page edge case:

> - `Next` blocks when visible required fields on the current
>   page are empty.
> - `Next` advances after current visible required fields are
>   filled.
> - Changing a controlling field toggles the dependent field.
> - Hidden dependent field values do not appear in the submitted
>   payload.

TG-5 (lines 218-226) extends e2e test 19 to exercise the same
condition end-to-end through Postgres:

> - A conditional required field that becomes visible from an
>   earlier answer.
> - Final persisted application `responses` contains the
>   visible fields and omits hidden fields.

The four layers together cover (i) required-on-hidden-page
omitted-and-OK, (ii) required-on-visible-page enforced, (iii)
controlling-flip stale-value rejected, (iv) SPA payload
strips hidden values, and (v) e2e DB read confirms the
persisted `responses` map only contains visible fields. The
edge case is not deferred to manual QA.

**Risk:** the shortcut would be (a) test only the
"all-fields-visible" case and skip the
required-on-hidden-page assertion, (b) test only the SPA layer
(which an attacker can bypass) and skip the API submit
validator, or (c) e2e check only that submit returned 200 and
skip the DB read of `responses`. Each would let the regression
"required field on hidden page rejects submit" or "hidden field
value persists" land silently.

**Mitigation:** TG-2 puts the omit-required-on-hidden assertion
at the validator boundary, TG-3 covers the controlling-flip
stale-value reject case, TG-4 exercises the SPA payload-strip
behavior, and TG-5 reads the persisted `responses` map from
Postgres. The edge case is named and tested at every layer.

**Verdict:** Not a shortcut.

## C5 — Form-version bump if contract changes (proposal locks v3 seed if needed)

**Pass with note.**

The contract change is intentionally backward-compatible at the
field-base level. §3 (Substrate → Contracts, lines 99-110)
adds the new attributes with safe defaults:

> - `page: int = Field(default=1, ge=1)` on `_BaseFormField`.
> - `visible_when: FormFieldVisibleWhen | None = None` on
>   `_BaseFormField`.

Defaults of `page=1` and `visible_when=None` mean the existing
INIT-135 seed v2 (`chapter_select + short + long`) parses
cleanly under the extended union without re-serialization: every
existing field implicitly resolves to page 1 with no predicate,
which is exactly its current rendered/persisted behavior. The
contract addition does not break the v2 seed payload.

Because the contract change is additive-with-defaults, no
mandatory `seed v3` is required for the contract itself to
land. The β-2 multi-page e2e fixture in TG-5 can be either:

- a separate API-published multi-page form created in-test
  (the form-publish endpoint already accepts the extended
  contract once the union is widened), or
- a seed v3 advance on the deterministic v2 seed (the same
  pattern INIT-135 used for v1 → v2).

Q5 (proposal lines 79-84) is conditional on whether seed data
is updated, not mandatory:

> If seed data is updated, keep the beta-1 seed discipline:
> deterministic JSON form payloads, no schema migration for
> JSONB field expansion, and no officer-published form
> overwrite.

This is the correct call: because the new attributes default
safely, the published v2 seed continues to function without
modification, and the BL-002 fail-closed/no-op invariant for
officer-published forms is preserved by deferring to
INIT-135's seed discipline rather than mandating a v3 advance
that would introduce migration complexity and an extra
deterministic seed UUID just to make e2e have a multi-page
fixture.

§5 (Anti-Scope, lines 230-238) holds the seed discipline line
explicitly:

> - Backwards-compatibility aliases, deprecated field names,
>   feature flags, transitional code paths, or placeholder
>   stubs.

So even if implementation chooses to bump to v3, it must
follow the v1 → v2 advance pattern (archive + insert + bump
aggregate head + skip officer-published) rather than introduce
a parallel old/new seed coexistence.

**Note (minor):** the proposal does not explicitly name
whether TG-5's "public form with at least two pages" e2e
fixture is delivered as a seed v3 advance or as an in-test
API publish. Either path is acceptable under the contract
change's backward compatibility, but implementation should
pick one and stay consistent — and if it picks the seed v3
path, it must reuse INIT-135's deterministic seed advance
pattern (`digest('init-136:public-intake-global:v3', 'sha256')`,
archive v2, insert v3, bump aggregate head, preserve no-op
on officer-published) and must not silently overwrite a v2
seed that an environment has already advanced past. This is
flagged here for the implementation to lock at the start of
the work, not as a proposal-level shortcut.

**Risk:** the shortcut would be (a) ship the contract
addition without re-validating that the existing v2 seed
re-parses cleanly under the new union, or (b) bump the seed
unconditionally and silently overwrite officer-published
global forms (breaking BL-002's fail-closed invariant), or
(c) carry a parallel "v2 + v3 coexistence" branch indefinitely
to avoid the advance. The proposal closes (b) and (c) by
binding any seed update to the β-1 discipline; (a) is a
functional risk that TG-1 ("`ApplicationFormField` union
parsing still accepts all existing field types plus
`chapter_select`") covers.

**Mitigation:** additive-with-defaults contract change so the
v2 seed re-parses cleanly, TG-1 explicitly asserts the union
still accepts all existing variants, anti-scope rules out
compat-shim coexistence, and any seed v3 advance must reuse
the v1 → v2 deterministic-seed-advance pattern that already
preserves the BL-002 no-op for officer-published forms.

**Verdict:** Not a shortcut. Minor implementation note logged.

## Verdict reasoning

INIT-136 ships exactly the contour the gate watches for:

- The submit validator gets a real server-side visibility pass
  in `validate_application_responses`: parse fields in order,
  build a response lookup, evaluate `visible_when` against
  earlier visible sources only, reject submitted-but-hidden
  responses, require only visible required fields, then
  type-validate. TG-3 names four server-bypass negative cases
  including the controlling-flip stale-value case. The
  chapter-selector override gate is preserved narrowly. No
  "trust the client" path.

- The SPA renderer becomes a real wizard with Solid-signal
  page state, visible-field-only rendering for the current
  page, recompute-and-clamp on response change, skip-empty-
  page navigation, sessionStorage draft preservation that
  cannot revive hidden fields, and final-payload assembly
  from the visible-field map across all pages. No
  "render-everything-then-CSS-hide" shortcut.

- `multi_select` and `chapter_select` are publish-time
  rejected as predicate sources via `FormDefinitionPublish`
  validation, with TG-1 negative cases naming each. No
  runtime "TODO support later" stub or lenient-publish-strict-
  submit gap. Anti-scope explicitly forbids placeholder
  stubs.

- TG-2 + TG-3 + TG-4 + TG-5 cover the required-field-on-
  hidden-page edge case at every layer: validator omits
  hidden required and enforces visible required, server
  rejects controlling-flip stale values, SPA payload strips
  hidden, e2e DB read confirms persisted `responses` only
  contains visible fields. The edge case is not deferred to
  manual QA.

- The contract change is additive-with-defaults
  (`page: int = 1`, `visible_when: ... | None = None`), so
  the existing v2 seed re-parses cleanly under the widened
  union without modification. TG-1 asserts the union still
  accepts every existing variant. Any seed v3 advance is
  conditional and must reuse INIT-135's v1 → v2 deterministic
  seed advance pattern, preserving the BL-002 fail-closed
  no-op for officer-published forms. One minor implementation
  note: the proposal does not lock whether TG-5's multi-page
  fixture lands via a seed v3 advance or an in-test API
  publish; implementation should pick one at the start and
  stay consistent.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-136-shortcut.md
