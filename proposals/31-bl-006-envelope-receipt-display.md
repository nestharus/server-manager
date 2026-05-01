# Proposal 31 - BL-006: Envelope receipt display

## 1. Problem statement

The public submit receipt is currently a deliberately minimal create
acknowledgment:

```json
{
  "message": "Application received",
  "application_id": "<uuid>"
}
```

The API contract behind that body is `PublicApplicationSubmissionReceipt`,
which contains only `message` and `application_id` and rejects extra fields.
This is intentionally separate from `ApplicationRead`; `ApplicationRead`
contains applicant identity, form snapshot, responses, lifecycle state,
officer/reviewer fields, timestamps, and optimistic-locking version data that
do not belong in a public submit response.

The current envelope is minimal but sufficient for the deployed surface and
near-term support shape. The submit caller needs confirmation and, at most, a
stable handle that support can use to find the application later.
`application_id` already supplies that handle without widening the public
response into a read model.

The strongest current gap is in the SPA, not the API envelope. The public form
submit handler reads `submission.body.message` and displays only that message
in the success/status view. It does not render, store, route with, or otherwise
surface the returned `application_id`, so a human applicant cannot copy the
support reference even though the API already provides it.

## 2. Decisions

### Q1. Public submit response contract

Lock Option A.

The public submit response body remains:

```json
{
  "message": "Application received",
  "application_id": "<uuid>"
}
```

This is a contract decision for future slices. The public submit response is a
create acknowledgment, not a public application read surface. Future BL slices
must respect that boundary and must not widen this response as a shortcut for
support tooling, applicant status checks, officer workflows, Discord follow-up,
or e2e verification needs.

`application_id` is the stable support/status correlation handle. `message` is
display copy only; clients must not branch business logic on it.

### Q2. SPA receipt display

Lock the SPA-only hardening.

After a successful public submit, the applicant success/status view must display
the returned application id as a support reference, using copy equivalent to:

```text
Application received
Reference: 11111111-1111-4111-8111-111111111111
```

The exact layout can follow the existing `Submission status` UI in
`ApplicationFormRoute.tsx`, but the rendered text must include both the success
message and the application id string when `application_id` is present.

If the response body somehow omits `application_id`, the SPA may retain the
current fallback behavior for status/message display. This fallback does not
change the API contract; it is only resilience for malformed or non-201
responses flowing through the existing web client parser.

### Q3. Anti-scope

No API body changes.

Do not add Option B fields such as `submitted_at` in this slice. Do not return
mutable lifecycle state. Do not return target scope, form definition/version,
correlation id, applicant id, responses, form snapshots, owner/reviewer data,
decision data, timestamps, version, ETag, or any `ApplicationRead`-style field.

Do not implement Option C. The public submit response must not become
`ApplicationRead`.

## 3. Substrate

### Modified files

- `services/web/src/features/public/ApplicationFormRoute.tsx`
  - Extend the success/status update after `submitPublicApplication(payload)`
    so the rendered success view includes `Reference: <application_id>` when
    the body includes `application_id`.
  - Keep the submit payload, auth redirect behavior, draft preservation,
    upload checks, and API endpoint unchanged.

- `services/web/tests/ApplicationFormRoute.spec.tsx`
  - Extend the existing submit-success path or add a focused success test that
    uses the current mocked receipt body:
    `{"message": "Application received", "application_id":
    "11111111-1111-4111-8111-111111111111"}`.
  - Assert the success/status view renders the application id string, preferably
    through visible text such as `Reference:
    11111111-1111-4111-8111-111111111111`.

### Contract guard

- Keep or add a static API contract guard for the public submit response model
  (`PublicApplicationSubmissionReceipt`, equivalent to the public
  `PublicApplicationSubmitResponse`) that fails if the model fields widen
  beyond exactly `{message, application_id}`.

Existing coverage already asserts the minimal receipt dump and route response
keys in:

- `services/api/tests/test_public_application_contracts.py`
- `services/api/tests/test_public_application_route.py`

If those tests are not exact enough at implementation time, tighten them rather
than changing production API or contract code.

### Unmodified substrate

- No API endpoint changes.
- No Pydantic contract changes.
- No OpenAPI/client contract widening.
- No service, repository, migration, Discord daemon, officer queue, or e2e DB
  verification changes.

## 4. Test plan

### TG-1: SPA success view displays support reference

Run the web route spec covering public application submit success:

```bash
pnpm --filter @humility/web test -- ApplicationFormRoute.spec.tsx
```

Acceptance:

- the mocked submit endpoint returns the existing receipt shape;
- the form submits successfully;
- the `Submission status` success view contains `Application received`;
- the same success view contains the returned application id string, rendered
  as `Reference: <id>` or equivalent applicant-facing support-reference copy.

### TG-2: public submit response remains the minimal envelope

Run the static API contract guard:

```bash
pytest services/api/tests/test_public_application_contracts.py \
  services/api/tests/test_public_application_route.py
```

Acceptance:

- the public submit response/receipt model exposes exactly `message` and
  `application_id`;
- extra `ApplicationRead`-style fields remain rejected;
- the public route response body keys remain exactly
  `{"message", "application_id"}`.

This test must fail if anyone widens the public submit response body beyond
`{message, application_id}`.

## 5. Anti-scope

Per Option A, do not change the API envelope. This slice does not add
`submitted_at`, status/state, full `ApplicationRead`, or any new public read
surface.

Do not integrate the receipt with Discord, officer queues, support console
lookups, applicant status checking, notifications, or transcript/detail views.
Those consumers need purpose-built authenticated or internal read surfaces when
commissioned.

Do not use this slice to introduce copy-to-clipboard controls, routing by
application id, local persistence of the receipt, or mobile/third-party client
contracts. The only user-facing hardening is displaying the already-returned id
as a support reference after successful submit.

## 6. Diff budget

Expected production diff:

- `ApplicationFormRoute.tsx`: small success-status formatting change.

Expected test diff:

- `ApplicationFormRoute.spec.tsx`: one assertion or one focused test proving
  the reference id renders.
- API static contract guard: zero production diff; tighten existing API tests
  only if the current exact-envelope assertions are insufficient.

No migrations, no API contracts, no generated clients, no Discord daemon, no
officer UI, no infrastructure, and no policy changes are budgeted.

PROPOSAL_DONE: proposals/31-bl-006-envelope-receipt-display.md
