# BL-006 — Shortcut risk gate (envelope receipt display)

**Verdict:** LOW

Scope: BL-006 — keep the public submit response body locked to exactly
`{message, application_id}` (per problem map Option A) and close the
applicant-side gap by rendering the existing `application_id` as a visible
support reference in the SPA success/status view. Proposal 31 chooses Q1 =
preserve the minimal envelope (no Option B `submitted_at`, no Option C
`ApplicationRead`), Q2 = SPA-only hardening that displays
`Reference: <application_id>` in the existing `Submission status` panel,
and Q3 = explicit anti-scope on every `ApplicationRead`-style field, on
copy-to-clipboard controls, on routing-by-id, on persistence, and on
Discord/officer/support/notification integrations.

The shortcut gate inspects whether the slice (1) actually shows the
reference as visible/copyable applicant-facing text rather than smuggling
it into an aria-label or hidden input, (2) keeps the static API contract
guard structural — exact-field-set on the parsed model and the route body,
not a substring scan or a "contains both keys" check — and (3) makes the
SPA test assert visible reference text in the rendered DOM rather than a
hidden state, signal, or attribute.

Source: `proposals/31-bl-006-envelope-receipt-display.md`,
`research/46-bl-006-envelope-problem-map.md`,
`services/api/app/contracts/applications.py:419-421`,
`services/api/tests/test_public_application_contracts.py:65-109`,
`services/api/tests/test_public_application_route.py:210-213`,
`services/web/src/features/public/ApplicationFormRoute.tsx:617-672`,
`services/web/src/features/public/ApplicationFormRoute.tsx:894-897`,
`services/web/src/api/client.ts:121-128`,
`services/web/tests/ApplicationFormRoute.spec.tsx:262-276`.

## C1 — Real reference display, not aria-label or hidden field

**Pass.**

The proposal's user-facing language consistently demands rendered, visible
copy:

- Problem statement (proposal lines 30-33): "It does not render, store,
  route with, or otherwise surface the returned `application_id`, so a
  human applicant cannot copy the support reference even though the API
  already provides it." A copyable support reference is text that an
  applicant can read and select; an aria-label or `data-` attribute is
  not.
- Q2 (proposal lines 60-72): "the applicant success/status view must
  display the returned application id as a support reference, using copy
  equivalent to: `Application received` / `Reference: 11111111-…`. The
  exact layout can follow the existing `Submission status` UI in
  `ApplicationFormRoute.tsx`, but the rendered text must include both the
  success message and the application id string when `application_id` is
  present."
- Section 3 substrate (proposal lines 96-100): "Extend the success/status
  update after `submitPublicApplication(payload)` so the rendered success
  view includes `Reference: <application_id>` when the body includes
  `application_id`." "Rendered success view" again names visible content.

The natural target UI is also already visible text. The current
`Submission status` panel is `<aside class="runtimePanel"
aria-live="polite"><h2>Submission status</h2><pre id="submit-status">{
submitStatus()}</pre></aside>`
(`ApplicationFormRoute.tsx:894-897`). `submitStatus()` is a SolidJS
signal set at line 671 from `submission.body.message`. The natural
implementation is to extend the same string (or render an adjacent line)
so the `<pre>` already-visible to the applicant grows from `Application
received` to `Application received\nReference: <id>`. There is no
existing aria-label or hidden field on this surface, so a shortcut
implementer would have to *introduce* one specifically to dodge the
proposal's "rendered text" requirement — which the proposal already
forecloses.

The anti-scope (proposal lines 184-187) further forecloses
copy-to-clipboard controls, routing-by-id, and persistence as out-of-
scope hardening. That keeps the visible-text-only contour clean: the
implementer cannot redirect effort into a clipboard button instead of
showing the reference.

**Risk:** the natural shortcut would be (a) pass the application id
through `aria-label="<id>"` on the success panel and skip rendering it
visibly, which would let `getByLabel(...)` style tests pass without the
applicant ever seeing a copyable string; or (b) stash the id on a
`data-application-id` attribute or a hidden `<input type="hidden">`, which
some test runners can read but a human applicant cannot copy.

**Mitigation:** the proposal's repeated "rendered text" / "visible text"
/ "applicant can copy" language, combined with the existing target being
a visible `<pre>` block already rendered to the user, leaves no natural
hidden-field path. A would-be shortcut implementer would have to
*deliberately* substitute a hidden surface for the visible one the
proposal points at, which is detectable in code review and in TG-1's
"the success view contains the returned application id string, rendered
as `Reference: <id>`" acceptance line.

**Verdict:** Not a shortcut; the proposal nails visible-text rendering
in three places and the target UI is already visible text.

## C2 — Static test parses the contract structurally (exact field set)

**Pass.**

The existing static guard is structural, exact-set, parsed-model-shaped,
not a substring scan. Two independent layers cover the receipt:

1. `services/api/tests/test_public_application_contracts.py:65-86`
   exercises the Pydantic model directly:

   ```python
   receipt = PublicApplicationSubmissionReceipt.model_validate(
       {"message": "Application received", "application_id": application_id}
   )
   dumped = receipt.model_dump()
   assert dumped == {
       "message": "Application received",
       "application_id": application_id,
   }
   assert isinstance(receipt.application_id, UUID)
   ```

   That is full dict equality on the dumped model, not a key-presence
   check or `"application_id" in dumped` substring shape. If a future
   slice adds even one optional field to the model, `model_dump()` will
   include it and the dict comparison will fail.

2. `services/api/tests/test_public_application_contracts.py:89-109`
   parametrizes rejection of `applicant_id`, `state`, `version`, and
   `responses` against `model_validate`, asserting `ValidationError`. The
   model itself sets `extra="forbid"` via `_ApplicationModel`
   (`services/api/app/contracts/applications.py:26-27`,
   `services/api/app/contracts/applications.py:419-421`), so any extra
   key — not just the four named ones — is rejected at the model layer.
   The parametrized tests provide named `ApplicationRead`-shaped
   regression coverage on top of the model-level guard.

3. `services/api/tests/test_public_application_route.py:210-213`
   exercises the live route response:

   ```python
   assert response.status_code == HTTPStatus.CREATED, response.text
   assert response.json()["message"] == "Application received"
   application_id = UUID(response.json()["application_id"])
   assert set(response.json()) == {"message", "application_id"}
   ```

   `set(response.json()) == {"message", "application_id"}` is exact-set
   equality on the parsed JSON body, not a `>=` superset, not a
   `"application_id" in response.json()` membership check, not a regex
   over `response.text`. It will fail if anyone widens the response body
   by even one key.

The proposal explicitly endorses these existing guards (proposal lines
112-125): "Keep or add a static API contract guard for the public submit
response model … that fails if the model fields widen beyond exactly
`{message, application_id}`. … If those tests are not exact enough at
implementation time, tighten them rather than changing production API or
contract code." That last clause is the right escape hatch shape: it
points the implementer at tightening tests, not at relaxing the
contract.

**Risk:** the natural shortcut would be (a) replace `set(...) == {...}`
with `{"message", "application_id"} <= set(response.json())` (superset
check), which would pass even if a future slice added `submitted_at` or
`state` to the body; (b) drop the `dumped == {...}` exact-equality dict
comparison in favor of `assert dumped["application_id"] is not None` and
`assert dumped["message"]`, which would silently accept new fields; or
(c) use raw text matching like `"application_id" in response.text`,
which would also catch unrelated mentions in error messages.

**Mitigation:** the existing tests are already in the strict shape the
gate wants. The model uses `extra="forbid"`. The route test uses
`set(...) == {...}`. The contract test uses full `model_dump() == dict`
equality. Section 3 forecloses loosening: any tightening goes into the
test, not the contract. There is nothing for the slice to *do* to the
contract guard except optionally tighten further; production diff for
this layer is zero (proposal lines 198-200).

**Verdict:** Not a shortcut; the existing static guard is already
structural and exact-set on both the parsed model and the route JSON
body, and the proposal forbids loosening it.

## C3 — SPA test asserts visible reference text, not hidden state

**Pass with a small wording note.**

The web spec is Playwright-based
(`services/web/tests/ApplicationFormRoute.spec.tsx:1`,
`import { expect, test, type Page } from "@playwright/test"`), so
assertions run against the rendered DOM in a real browser — `getByText`,
`toContainText`, `toHaveText`, etc. operate on accessible/rendered text,
not internal SolidJS signals. The mocked submit body already uses the
canonical fixture id the proposal locks
(`ApplicationFormRoute.spec.tsx:262-276`):

```ts
async function mockPublicSubmit(page: Page) {
  ...
  await route.fulfill({
    status: 201,
    contentType: "application/json",
    body: JSON.stringify({
      message: "Application received",
      application_id: "11111111-1111-4111-8111-111111111111",
    }),
  });
  ...
}
```

That is the same `application_id` the proposal pins as the canonical
example in Q2 (proposal lines 67-68) and in TG-1 (proposal lines
105-109). The natural shape of the BL-006 SPA assertion is therefore an
exact-text assertion against the visible `Submission status` panel
content — e.g.,
`await expect(page.locator("#submit-status")).toContainText("Reference: 11111111-1111-4111-8111-111111111111")`
or `await expect(page.getByText("Reference: 11111111-1111-4111-8111-111111111111")).toBeVisible()`.

The proposal language is mostly tight on visible text:

- TG-1 acceptance (proposal lines 144-151): "the same success view
  contains the returned application id string, rendered as
  `Reference: <id>` or equivalent applicant-facing support-reference
  copy." "Rendered" plus "applicant-facing" plus the explicit
  `Reference: <id>` example is visible-DOM-text shape.
- Test substrate (proposal lines 105-109): "Assert the success/status
  view renders the application id string, preferably through visible
  text such as `Reference: 11111111-1111-4111-8111-111111111111`."
- Q2 (proposal lines 60-72) already locked "rendered text" on the
  production side, which the test mirrors.

**Wording caveat.** Proposal section 3 line 108 says the assertion
should be "preferably through visible text," which is slightly looser
than "must." A strict reading would prefer "must use a visible-DOM-text
assertion (Playwright `toContainText` / `getByText`); do not assert via
`toHaveAttribute('aria-label', ...)`, hidden inputs, `data-*`
attributes, or by reading SolidJS signals directly." However, the
*canonical example* the proposal cites — `Reference:
11111111-1111-4111-8111-111111111111` — is unambiguously a visible-text
shape (no attribute syntax, no hidden field, no signal name), and TG-1
acceptance commits to "rendered as `Reference: <id>`". The "preferably"
hedge appears to leave room for "Application reference: <id>" or
"Submission reference: <id>" wording variants, not for hidden-state
substitutes.

**Risk:** the natural shortcut would be (a) assert
`await expect(page.locator("#submit-status")).toHaveAttribute("aria-label", /11111111-1111-4111-8111-111111111111/)`,
which would pass even if the panel showed only "Application received"
visibly to the applicant; (b) read the SolidJS signal directly via a
test-only export, which would bypass DOM rendering entirely; (c) assert
against a `data-application-id` attribute on the panel, which a human
applicant cannot copy from screen reader output or selection.

**Mitigation:** the proposal's repeated "rendered text" / "visible text"
language plus the canonical example shape ("Reference: <id>" as plain
text content, not attribute syntax) plus the existing target being a
visible `<pre>` block leave the visible-DOM-text path as the only
natural one. Tightening section 3 line 108 from "preferably through
visible text" to "must use visible-DOM-text assertion" would make the
gate watertight, but the gap is wording-strength only — there is no
ambient incentive in the proposal to substitute hidden state for
visible text.

**Verdict:** Not a shortcut; the test's natural shape, the canonical
example, and the rendered-DOM Playwright runner all anchor on visible
text. The "preferably" wording is a minor softness, not a shortcut path.

## Verdict reasoning

BL-006 fits the contour the gate watches for on all three checks:

- The proposal anchors visible, applicant-facing rendering on the
  existing visible `Submission status` `<pre>` panel and uses
  "rendered text" / "applicant can copy" / "visible text" language in
  three places (problem statement, Q2, test substrate). The natural
  implementation is `setSubmitStatus("Application received\nReference:
  <id>")` on the same SolidJS signal that already drives the visible
  panel content; an aria-only or hidden-input shortcut would require
  the implementer to *introduce* a hidden surface specifically to dodge
  the proposal's stated requirement, which is both more work than the
  natural path and visibly off-spec at code review.

- The static API contract guard already lives at two layers:
  `model_dump() == {...}` exact dict equality at the contract test, and
  `set(response.json()) == {"message", "application_id"}` exact-set
  equality at the route test, both backed by `extra="forbid"` on the
  Pydantic model. Section 3 explicitly directs implementers to tighten
  these tests if they prove insufficient rather than touch the
  production contract or model. There is no substring-scan or
  superset-check escape hatch in the existing guard for BL-006 to
  inherit.

- The SPA test runs in Playwright against rendered DOM, the mocked
  receipt fixture already uses the canonical
  `11111111-1111-4111-8111-111111111111` id the proposal locks, and the
  proposal's TG-1 acceptance commits to "rendered as `Reference:
  <id>`." A shortcut to `aria-label`, `data-*`, hidden input, or a
  signal-internal assertion would clash both with the proposal's
  language and with the existing test runner's idiomatic shape
  (Playwright text locators, `toContainText`, `getByText`).

The slice is appropriately small (proposal §6 caps total churn at one
small `ApplicationFormRoute.tsx` formatting change plus one focused
`ApplicationFormRoute.spec.tsx` assertion or test, with zero production
API/contract diff), correctly chooses the SPA-only hardening lane that
the problem map recommends as Option A, and explicitly anti-scopes
every adjacent surface that could pull the receipt back toward
`ApplicationRead` (Discord, officer queues, support console, applicant
status checks, notifications, transcript views, copy-to-clipboard,
routing-by-id, persistence, mobile/third-party clients).

The single soft note is that proposal section 3 line 108 says
"preferably through visible text" rather than "must"; combined with
TG-1 line 151's "or equivalent applicant-facing support-reference
copy," there is mild room for the implementer to argue an aria-label or
data-attribute counts as "equivalent." The canonical example
(`Reference: <id>` as plain text), the "rendered text" lock on the
production side at Q2, and the existing visible `<pre>` target UI all
make this risk small in practice. Tightening that one line from
"preferably through visible text" to "must use a visible-DOM-text
assertion (Playwright `toContainText`/`getByText`); do not assert via
attributes or hidden state" would close the wording gap without changing
the substantive plan.

Verdict: LOW. All three checks pass; the only concrete improvement is a
one-word wording tightening on the SPA test acceptance line, not a
substantive scope or shape change.

SHORTCUT_DONE: plans/risk/bl-006-shortcut.md
