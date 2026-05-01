# BL-006 — Audit risk gate

**Verdict:** LOW

Scope: BL-006 — lock the public submit response as Option A
(`{message, application_id}`) and harden the SPA so the applicant
success view renders the returned `application_id` as a support
reference. The slice is SPA-render-only on the production side; the
API contract, route, services, and migrations are explicitly frozen.
Static API guards already exist; the proposal commits to extending
the SPA spec to assert the visible reference text.

The audit gate inspects: (1) Option A is locked with no PII added to
the public response; (2) SPA hardening exposes only `application_id`,
not responses/scope/applicant-discord-id; (3) a static test catches
future widening of `PublicApplicationSubmissionReceipt`; (4) the SPA
spec extension actually asserts the rendered reference text.

Source proposal: `proposals/31-bl-006-envelope-receipt-display.md`.
Source problem map: `research/46-bl-006-envelope-problem-map.md`.
Production receipt model: `services/api/app/contracts/applications.py:419`.
Production endpoint: `services/api/app/api/v1/endpoints/applications/public.py:25`.
Existing API guards: `services/api/tests/test_public_application_contracts.py:65,89`,
`services/api/tests/test_public_application_route.py:213`.
SPA render path: `services/web/src/features/public/ApplicationFormRoute.tsx:671,895`.
SPA spec: `services/web/tests/ApplicationFormRoute.spec.tsx`.

## A1 — Option A locked; no PII added to public response

**Surface (Q1, Q3, §3 unmodified substrate):** the proposal locks the
public submit body as exactly:

```json
{"message": "Application received", "application_id": "<uuid>"}
```

§2 Q3 enumerates the explicit anti-list (must NOT be returned):
`submitted_at`, mutable lifecycle state, `target_scope`,
`form_definition_id`/`form_version`, `correlation_id` (body),
`applicant_id`, `responses`, `form_snapshot`, owner/reviewer fields,
decision data, timestamps, `version`, ETag, "or any
`ApplicationRead`-style field." §3 "Unmodified substrate" reaffirms
"No API endpoint changes / No Pydantic contract changes / No
OpenAPI/client contract widening."

**Production reality check:** the receipt model at
`services/api/app/contracts/applications.py:419` is verbatim
`message: str` + `application_id: UUID`, and `_ApplicationModel`
carries `extra="forbid"` (problem map line 14, verified in source).
The endpoint at `public.py:25` constructs the receipt with exactly
those two fields. The proposal does not budget any production diff
for the API layer (§6: "Expected production diff: ApplicationFormRoute.tsx").

**Verdict:** Option A is contractually locked at the proposal level
and matches the current production code; no PII is added because the
proposal explicitly forbids any API body change. Audit risk LOW for
A1.

## A2 — SPA hardening surfaces application_id only; no responses/scope/member-id

**Surface (Q2, §3 modified files, §5 anti-scope):** the SPA change
is restricted to inserting `Reference: <application_id>` in the
existing `Submission status` view after a successful submit. §3
explicitly requires "Keep the submit payload, auth redirect behavior,
draft preservation, upload checks, and API endpoint unchanged." §5
explicitly forbids copy-to-clipboard controls, routing by application
id, local persistence of the receipt, or new client contracts.

**Reachable fields in the render path:** the SPA renders
`submitStatus` (a single signal) into `<pre id="submit-status">`
(`ApplicationFormRoute.tsx:361,896`). After submit, the only call
site that mutates the success branch is line 671:
`setSubmitStatus(submission.body.message ?? ...)`. The submit
response body is parsed by `submissionResponseBodySchema` in
`services/web/src/api/client.ts:121-128`, which accepts only
`{code?, message?, application_id?, parse_error?, raw_text?,
content_type?}` — no `responses`, no `scope`, no `applicant_id`,
no `applicant_discord_user_id` fields are reachable through
`submission.body`.

The applicant's own form responses (`responses()` signal) and
chapter selection (`selectedChapterId`) live in the route's local
state and are not piped into `submitStatus` anywhere. A reviewer
adding `Reference: <id>` to the success string therefore cannot
accidentally splice in scope or response data; those signals are
not in scope at the render site.

**Anti-scope coverage:** the proposal explicitly excludes Discord
follow-up integration, officer-queue integration, applicant
status-check flows, and copy-to-clipboard controls — all of which
would have been the natural vectors for adding member-id or scope
to the rendered output. None are budgeted.

**Verdict:** the SPA hardening surface is restricted to
`application_id` rendering, the surrounding code path has no
non-receipt PII reachable through `submission.body`, and the
proposal's anti-scope explicitly fences off the natural
PII-leak directions. Audit risk LOW for A2, with one observation
(F1) on the single-signal render shape.

## A3 — Static test catches future widening of the receipt model

**Existing API contract guards (verified):**

- `test_public_application_submission_receipt_is_minimal_envelope`
  (`test_public_application_contracts.py:65-86`) constructs the
  receipt and asserts:
  ```python
  assert dumped == {"message": "Application received",
                    "application_id": application_id}
  ```
  This is exact dict equality, not subset. Adding any field to the
  model and populating it would change `dumped` and fail the assert.
- `test_public_application_submission_receipt_rejects_application_read_fields`
  (`test_public_application_contracts.py:89-109`) parametrizes over
  `["applicant_id", "state", "version", "responses"]` and asserts
  `model_validate(...)` raises `ValidationError`. Backed by
  `_ApplicationModel`'s `extra="forbid"` config.
- `test_public_application_route.py:213`:
  ```python
  assert set(response.json()) == {"message", "application_id"}
  ```
  Exact set equality on the live route response keys. Adding a
  populated field to the response body would extend the JSON object
  and fail this assert.

**Coverage shape:** the contract test catches additions at the
*model* layer (Pydantic schema). The route test catches additions at
the *response* layer (what actually goes over the wire, including
hand-built dicts that bypass the model). Together they form a
two-layer guard: a developer cannot widen the public receipt by
either adding a field to the Pydantic model or by constructing a
dict response with extra keys without one of the two asserts
failing.

**Adjacent contract surfaces:** the SPA contract fixture at
`infra/tests/fixtures/web-ui/contract.json:140` and the SPA compat
spec at `services/web/tests/compat.spec.ts:134` both encode the
two-field shape. They are not strictly enforcement guards (they're
mocks, not assertions on production), but they would have to be
updated in lockstep with any widening, which raises the cost of
silently widening the envelope.

**Proposal posture:** §3 "Contract guard" says "If those tests are
not exact enough at implementation time, tighten them rather than
changing production API or contract code." The existing tests are
already exact (verified above), so no implementation work is
required to satisfy this clause; the guard is in place as-is.

**Verdict:** the existing static guards exactly enforce the
two-field envelope at both the model and response layers. No
implementation work required for A3. Audit risk LOW for A3.

## A4 — SPA test verifies the reference text actually renders

**Proposal commitment (§3 modified files, §4 TG-1):** the SPA spec
must be extended so that "the same success view contains the returned
application id string, rendered as `Reference: <id>` or equivalent
applicant-facing support-reference copy." The proposal explicitly
suggests asserting `Reference: 11111111-1111-4111-8111-111111111111`
through visible text.

**Existing spec state (verified):**
`services/web/tests/ApplicationFormRoute.spec.tsx:262-276` already
mocks the public submit endpoint with the canonical receipt body
(`message: "Application received"`,
`application_id: "11111111-1111-4111-8111-111111111111"`). A grep
for `Reference` or `11111111` in assertion positions in the spec
returns no current assert on the rendered application_id — this is
the expected pre-implementation state and is exactly the gap TG-1
will close.

**Render-path reality check:** the success view writes
`submission.body.message` into a single `submitStatus` signal
(`ApplicationFormRoute.tsx:671`) which is rendered into
`<pre id="submit-status">{submitStatus()}</pre>`
(`ApplicationFormRoute.tsx:896`). For the proposed reference text
to render, the implementation must change line 671 to concatenate
or interpolate the application_id (e.g.,
`setSubmitStatus(\`${message}\nReference: ${id}\`)`). The spec
assertion specified in TG-1 (search the rendered DOM for the
literal `Reference: 11111111-...` substring) will fail unless that
production change is made — i.e., the test is contractually
production-binding, not a no-op.

**Acceptance criteria fitness:** TG-1 acceptance lists three
distinct conditions: success message present, form submits
successfully, and the rendered view contains the application id
string. The third is the substantive new assertion; the first two
are the existing happy-path scaffolding. This is the right
decomposition — it does not weaken the existing happy-path
verification while adding the reference-text assertion.

**Verdict:** the proposal commits to a spec assertion that is
production-binding (it can only pass after the
`ApplicationFormRoute.tsx:671` render change lands), and the
existing mock body already supplies the `application_id` the
assertion needs. Audit risk LOW for A4, with one observation (F2)
on the single-signal render shape requiring a deliberate
concatenation choice in implementation.

## Findings

### F1 — SPA render shape is single-string concatenation, not structured

**Severity:** low (observation; no slice action required).

**Where:** `ApplicationFormRoute.tsx:361,671,896` (the
`submitStatus` signal and its `<pre>` render site).

**Risk:** the success view uses a single string signal rendered into
one `<pre>` element. The proposal's `Application received` +
`Reference: <id>` two-line format is achievable by interpolating
both into the same string (the `<pre>` element will preserve the
newline). This works correctly but means a future spec assertion
that searches the DOM for a structured element (e.g.,
`getByLabelText("Reference")` or `getByRole("term", {name:
"Reference"})`) would not find one. The applicant copy is also
appended to the same surface that handles error text ("Network
error. Please try again.", "Application returned 500"), so a future
re-styling that splits success vs. error rendering would have to
also re-thread the application_id.

**Action:** none required for the slice — the proposal's chosen
copy fits the existing `<pre>` shape. Implementation should pick a
single concatenation strategy (e.g., `\n` separator vs. ` — `
separator) that matches the spec assertion's expected substring.
The spec assertion should match the substring the implementation
produces; if it asserts `Reference: <id>` literally, the
implementation must use that literal token.

### F2 — Spec assertion shape must match implementation copy verbatim

**Severity:** low (developer-experience; coordination between
production change and test).

**Where:** the new TG-1 assertion in
`services/web/tests/ApplicationFormRoute.spec.tsx`.

**Risk:** the proposal allows "`Reference: <id>` or equivalent
applicant-facing support-reference copy." If the spec asserts the
literal substring `Reference: 11111111-1111-4111-8111-111111111111`
and the implementation writes `Ref: 11111111-...` or `Application
ID: 11111111-...`, the test fails for a copy-mismatch reason
unrelated to the underlying behavior. Conversely, if the spec
asserts only the bare uuid `11111111-1111-4111-8111-111111111111`,
it would pass even if the implementation merely echoes the uuid
without the "Reference" label, which weakens the support-reference
intent.

**Action:** during implementation, lock both the production copy
string and the spec assertion to the same literal token in the
same change. The proposal's example (`Reference:
11111111-1111-4111-8111-111111111111`) is a sensible default for
both surfaces.

### F3 — Adjacent receipt-shape mocks not enumerated as drift surfaces

**Severity:** low (completeness; out-of-scope but worth noting).

**Where:** `services/web/tests/compat.spec.ts:134` and
`infra/tests/fixtures/web-ui/contract.json:140` both encode the
two-field receipt shape as mocks/fixtures.

**Risk:** the proposal §3 enumerates the API-side static guards
(`test_public_application_contracts.py`,
`test_public_application_route.py`) as the drift catchers but does
not mention the SPA-side contract fixture or the compat spec. If a
future slice widens the receipt shape, the fixture and compat spec
would have to be updated in lockstep; failing to do so would
surface as a compat-spec or e2e mock mismatch rather than a
contract-test failure. The two-layer API-side guard already
catches the production drift before it reaches the SPA fixtures,
so this is a defense-in-depth observation, not a gap.

**Action:** none required for the slice. Future widening proposals
should enumerate the SPA-side fixture/mocks alongside the API-side
guards in their substrate section.

## Verdict reasoning

BL-006 holds the audit gate at LOW risk:

- **Option A locking (A1):** the proposal locks the body to
  `{message, application_id}` and matches current production code
  at `services/api/app/contracts/applications.py:419`. The §2 Q3
  anti-list explicitly forbids every plausible PII-bearing field.
  No API production diff is budgeted.
- **SPA hardening boundary (A2):** the change is restricted to
  rendering `application_id` in the existing `submitStatus`
  surface. The submit-response parser in `client.ts:121-128` does
  not expose responses, scope, or applicant-discord-id fields, and
  the route's local response/scope state is not reachable from the
  render site. Anti-scope explicitly fences off Discord follow-up,
  officer queues, applicant status checks, and clipboard controls.
- **Static drift guard (A3):** two existing exact-equality asserts
  (`dumped == {...}` at the model layer; `set(response.json()) ==
  {"message", "application_id"}` at the route layer) plus
  `extra="forbid"` form a two-layer guard that catches widening
  through either the schema or a hand-built response dict. No
  implementation work needed to satisfy A3.
- **SPA test commitment (A4):** TG-1 commits to asserting the
  rendered `Reference: <id>` substring against a spec mock that
  already supplies the canonical application_id. The assertion is
  production-binding because it requires a code change at
  `ApplicationFormRoute.tsx:671` to pass.

The slice is SPA-render-only on production (one small change in
`ApplicationFormRoute.tsx`), one new SPA spec assertion, and zero
API/contract diff. All four gate criteria are met. Findings F1–F3
are low-severity observations on render shape, copy/assertion
alignment, and adjacent fixture mocks; none block the slice.

Verdict: LOW.

AUDIT_DONE: plans/risk/bl-006-audit.md
