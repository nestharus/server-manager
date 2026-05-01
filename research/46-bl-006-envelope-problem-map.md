# BL-006 problem map — public submit envelope long-term shape

## Current envelope (verbatim)

The public submit receipt model is exactly:

```python
class PublicApplicationSubmissionReceipt(_ApplicationModel):
    message: str
    application_id: UUID
```

Source: `services/api/app/contracts/applications.py:419`.
`_ApplicationModel` has `extra="forbid"`, so this model rejects
additional public-read fields.

The public endpoint returns `201 Created` with:

```json
{
  "message": "Application received",
  "application_id": "<uuid>"
}
```

Source: `services/api/app/api/v1/endpoints/applications/public.py:25`.
The endpoint receives `PublicApplicationSubmission`, verifies the
applicant receipt, calls `submit_public_application_with_receipt(...)`,
then constructs `PublicApplicationSubmissionReceipt(message="Application
received", application_id=application_id)`.

This is deliberately not `ApplicationRead`. `ApplicationRead` includes
`applicant_id`, `form_definition_id`, `form_version`, `form_snapshot`,
`target_scope`, `responses`, lifecycle state, owner/thread/decision
fields, timestamps, and `version` (`services/api/app/contracts/applications.py:563`).

## Current consumers

SPA:

- `services/web/src/api/client.ts:121` parses submit bodies with optional
  `message`, optional `application_id`, and error/fallback fields.
- `services/web/src/features/public/ApplicationFormRoute.tsx:656` sends
  `scope`, `responses`, and `client_application_id`.
- `services/web/src/features/public/ApplicationFormRoute.tsx:660` calls
  `submitPublicApplication(payload)`.
- On `401`, it preserves the draft and redirects to Discord auth.
- On every other response, it only displays
  `submission.body.message ?? "Application returned <status>"`
  (`ApplicationFormRoute.tsx:671`).
- The SPA does not read, store, render, route with, or branch on
  `application_id`.

Other current consumers:

- API/component tests assert the receipt is exactly `{message,
  application_id}` and rejects `ApplicationRead`-style extra fields
  (`services/api/tests/test_public_application_contracts.py:75`,
  `services/api/tests/test_public_application_route.py:211`).
- Web route tests and the web UI contract fixture mock the same receipt
  shape (`services/web/tests/ApplicationFormRoute.spec.tsx:270`,
  `services/web/tests/compat.spec.ts:134`,
  `infra/tests/fixtures/web-ui/contract.json:140`).
- Local e2e infrastructure uses `application_id` to find the submitted
  row in the officer queue and to verify persisted DB/notification state
  (`infra/tests/e2e/lib/playwright/browser-flow.mjs:131`). This is a
  test/verification consumer, not an applicant-facing SPA dependency.
- Officer queue does not consume the public submit response. It uses
  `/web/officer/applications`.
- Discord daemon does not consume the public submit response.
- Mobile / third-party clients do not exist today.
- Applicant self-service "check my application status" does not exist
  today.

## Plausible future consumers

| Consumer | Likely shape wanted | Current fields enough? | Missing / noise |
| --- | --- | --- | --- |
| Applicant web confirmation | Human success copy plus a stable reference the applicant can give support. | API envelope is enough; SPA currently fails to expose `application_id` to the applicant. | Missing at UI layer, not necessarily response layer: display/copy the existing `application_id` if support references are desired. |
| Support console / operator lookup | A reference ID, possibly correlation id, applicant Discord id, submitted time, state, and selected chapter. | The public response should not be the console's data source. `application_id` is enough as a lookup key. | Console should query internal/officer APIs. `message` is noise to tooling. `X-Correlation-Id` exists as a response header in e2e, but is not part of the body. |
| Applicant "check status" flow | A durable application handle plus a separate authenticated/receipt-bound read endpoint returning status. | `application_id` is enough as the handle. | The missing piece is the status endpoint and its authorization model, not a larger submit receipt. Adding `state` now would be a weak substitute and may ossify the submit response as a read surface. |
| Mobile first-party client | Machine-readable ID, display message or localized copy key, maybe submitted timestamp and next-step copy. | Enough for a first submit confirmation. | `message` is useful for a simple client but poor as a long-term localization contract. `submitted_at` could be convenient, but no mobile client exists. |
| Third-party client | Stable ID, status location, documented errors. | Enough for create acknowledgment if the third party only submits. | `message` is mostly noise. If third parties are allowed, they likely need formal OpenAPI docs, error contracts, rate-limit semantics, and a status endpoint rather than `ApplicationRead` on create. |
| Discord-bot-driven follow-up | Application id, applicant Discord id, event payload, notification materialization state. | Public submit response is irrelevant; the daemon should consume internal events/API. | No response field helps unless the bot is directly acting as the HTTP submitter, which is not current design. |
| File-upload / e2e verification paths | Application id to correlate object keys, DB rows, queue rows, and notification events. | Current `application_id` is enough. | None for the receipt. |

## Is the current envelope minimal-but-sufficient?

Yes, for the current deployed surface and the likely near-term support
shape.

B1's original framing still holds:

- The public submit caller needs confirmation and, at most, a support
  correlation handle.
- `application_id` supplies the handle without leaking applicant UUID,
  form snapshot, responses, owner fields, lifecycle timestamps, or
  optimistic-locking version.
- Full `ApplicationRead` remains appropriate for authenticated API and
  officer surfaces, not for public submit.
- Current SPA usage only needs `message`.
- Current e2e/support verification usage only needs `application_id`.

The strongest gap is not the API envelope. It is that the applicant SPA
does not show the existing `application_id`, so a human applicant cannot
currently copy the support reference even though the response provides it.
That can be fixed in UI copy without changing the receipt schema.

The second likely gap is future status checking. That should be modeled
as a separate read contract with its own authorization rules. Stuffing
`state`, timestamps, owner fields, or response echoes into the create
receipt would turn a create acknowledgment into an under-specified read
surface.

## Recommendation

Option A: leave as-is; defer until real deployment-data feedback per the
deferred reason.

Recommended.

Keep `{message, application_id}` as the submit receipt. If pre-deployment
hardening is desired, spend it on making the SPA display the existing
`application_id` as a support reference, not on widening the API body.
That preserves B1's privacy boundary while making the already-returned
field useful to humans.

Option B: add a small set of fields likely needed by support/applicant-status
flows.

Not recommended now. If a concrete caller is commissioned before launch,
the only defensible small addition is:

- `submitted_at`: server acceptance timestamp for receipt display.

Fields to exclude from a small receipt extension:

- `state`: belongs to a status/read endpoint and changes after submit.
- `target_scope`, `form_definition_id`, `form_version`: useful internally
  but unnecessary for applicant confirmation.
- `correlation_id`: already available as an HTTP header and primarily
  useful to logs/operators, not public UI.
- `applicant_id`, `responses`, `form_snapshot`, `owner_id`, `version`,
  lifecycle timestamps: these cross into `ApplicationRead` territory.

Option C: more invasive change — full `ApplicationRead`.

Do not pursue. It contradicts B1, leaks response and workflow data to a
public submit caller, and turns a create route into a public application
read surface without solving status authorization.

## What the proposal must lock if proceeding

- The public submit receipt remains a separate contract from
  `ApplicationRead`.
- The response body remains create-acknowledgment only, not a read model.
- `application_id` is the stable support/status correlation handle.
- `message` is display text only; clients should not branch business logic
  on it.
- No public receipt field may expose applicant UUID, submitted responses,
  form snapshots, owner/reviewer data, decision data, version/ETag, or
  mutable lifecycle state.
- Applicant status, support console, and Discord follow-up must use
  purpose-built authenticated/internal read surfaces.
- If a proposal chooses Option B despite this map, it must name the
  concrete caller and lock every added field's consumer, retention value,
  and privacy boundary.

## Diff budget

Option A API diff: zero.

Optional UI-only hardening if desired:

- Small SPA change to display/copy the existing `application_id` after a
  successful submit.
- Small web test update proving the reference is visible.
- No API contract, service, migration, Discord daemon, officer queue, or
  e2e DB-verification changes.

Option B API diff, if separately commissioned:

- Add one field such as `submitted_at` to
  `PublicApplicationSubmissionReceipt`.
- Populate it from the committed application row or service result.
- Update API contract tests, route tests, web parser expectations, and
  OpenAPI/client documentation.
- Re-run the public submit tests and e2e browser flow.

Option C diff:

- Not budgeted. It would require public-contract redesign, privacy review,
  tests for every newly exposed `ApplicationRead` field, and a status/read
  authorization decision.

PROBLEM_MAP_DONE: research/46-bl-006-envelope-problem-map.md
