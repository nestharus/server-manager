# INIT-133B-ii hookpoints

## Summary

INIT-133B-ii should extend the beta-i officer surface with a read-only application detail page and transcript. The backend services, contracts, authorization checks, Pomerium identity bridge, and frontend API/error patterns already exist; the implementation should add two thin web bridge GET endpoints, one Solid detail route, route-local transcript rendering, fixture-driven tests, and one protected Pomerium route prefix. Do not change lifecycle semantics, message append, transitions, database schema, public applicant auth, or Discord-visible state.

## Reuse (call directly)

### Backend

- `services/api/app/api/v1/endpoints/web.py::_db` and `_build_officer_actor` are the bridge entry points. New detail/transcript endpoints should resolve the Pomerium officer to `ActorIdentity(actor_kind="user", actor_id=<member_uuid>)` through this helper, just like beta-i list/claim.
- `services/api/app/services/applications.py::read_application` returns the existing `ApplicationRead` plus direct-API ETag. The bridge detail endpoint should use the read value and does not need `If-Match`.
- `services/api/app/services/applications.py::require_application_read_authority` is the existing detail authorization gate. Do not add officer-group bypasses; group membership only permits bridge entry.
- `services/api/app/api/v1/endpoints/applications/_shared.py::raise_known_application_error` already maps `ApplicationNotFoundError` to `404 application_not_found` and `PermissionError` to `403 authority_decision_denied`; use it for detail-read failures.
- `services/api/app/services/application_transcript.py::read_application_transcript` is the transcript service used by the direct endpoint. It reads state changes plus messages, filters message visibility server-side, sorts by `occurred_at`, and returns `ApplicationTranscriptRead`.
- `services/api/app/api/v1/endpoints/applications/transcript.py` has the direct transcript error mapping to mirror: `ApplicationNotFoundError` -> `404 application_not_found`; `ApplicationMessageAppendForbiddenError` -> `403 application_transcript_forbidden`.
- `services/api/app/contracts/applications.py::ApplicationRead` is the detail response contract. It already includes `form_snapshot`, `responses`, timestamps, owner, state, and version.
- `services/api/app/contracts/applications_transcript.py::ApplicationTranscriptRead` is the transcript response contract. Its discriminated union uses field `type`, with values `state_change` and `message`.

### Frontend

- `services/web/src/features/officer/ApplicationQueueRoute.tsx` is the route pattern to mirror: route-local signals, `onMount` bootstrap, `fetchCurrentPrincipal`, officer group and `discord_user_id` gating before officer API calls, `ApiError` status handling, and simple refresh/retry state.
- `services/web/src/api/client.ts::ApiError` and `getJson` are the browser API pattern. New functions must use browser-facing `/api/...` paths, not `/api/v1/...`.
- Existing `applicationReadSchema` is the base Zod contract to expand for detail fields consumed from `ApplicationRead`.
- `services/web/src/app/router.tsx` is the only router hookpoint. Add the dynamic route beside `/applications` and `/applications/queue`; do not create a second router tree.
- `services/web/src/features/officer/officer.module.css` is the route-local stylesheet for officer UI. Add detail/transcript classes there instead of global CSS.
- Existing primitives such as `Button` and TanStack `Link` are sufficient for refresh, queue/detail navigation, and back-to-queue affordances.

### Test fixtures

- `services/api/tests/test_web_officer_applications.py` already owns beta-i officer bridge tests, Pomerium header helpers, officer grant fixtures, application creation helpers, and the dependency-tree guard. Extend this file rather than adding a second backend bridge test module.
- `services/api/tests/test_applications_list.py` helpers `_create_application`, `_create_member`, `_grant`, and `_claim_application` can set up detail/transcript fixtures and a claimed transcript event.
- `services/web/tests/officer-queue.spec.ts` is the Playwright component-test style to mirror: load `infra/tests/fixtures/web-ui/contract.json`, mock `/api/me`, mock officer endpoints with `page.route`, and assert UI behavior through accessible text/buttons plus `data-application-id`.
- `infra/tests/test_applicant_discord_pomerium.py` has the Pomerium route loader, route matching helper, catch-all index helper, and identity-route assertions needed for the new `/applications/` prefix tests.
- `infra/tests/fixtures/web-ui/contract.json` is the shared route/API fixture. Add detail and transcript entries here so component, validator, and e2e checks stay aligned.
- `infra/tests/validate_web_ui_local.sh` already checks fixture shape, Playwright spec presence, `/api/v1/` source bans, and positive client endpoint literals. Extend those checks for detail/transcript.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` already records the claimed application id after queue claim; reuse that value for post-claim detail navigation.
- `infra/tests/e2e/tests/19-web-ui.sh` remains the e2e entry. Extend test 19; do not create a new numbered e2e test.

### Config

- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` already forwards Pomerium identity headers, protects `/api/web/officer/`, and protects `/applications/queue` plus `/applications/queue/`.
- Add one web-host route with `prefix: /applications/`, `pass_identity_headers: true`, and `allow_any_authenticated_user: true`.
- Insert that route after the existing queue exact/prefix routes and before `/admin` and the public catch-all. This preserves public `path: /applications`, keeps queue matched by its dedicated routes, and protects `/applications/<id>`.

## New (write fresh)

### Backend

- Add `GET /api/v1/web/officer/applications/{application_id}` in `services/api/app/api/v1/endpoints/web.py`.
- Backend detail shape: build officer actor, call `read_application(db, application_id=application_id)`, call `require_application_read_authority(db, actor=actor, application=read)`, return `ApplicationRead`, and map errors with `raise_known_application_error`.
- Add `GET /api/v1/web/officer/applications/{application_id}/transcript` in `services/api/app/api/v1/endpoints/web.py`.
- Backend transcript shape: build officer actor, call `read_application_transcript(db, application_id=application_id, viewer_actor_kind=actor.actor_kind, viewer_actor_id=actor.actor_id)`, return `ApplicationTranscriptRead`, and mirror the direct transcript endpoint's `404` / `403 application_transcript_forbidden` mapping.
- If the transcript error mapping needs reuse, prefer a tiny local helper in `web.py` or a deliberate shared helper. Do not import a private helper from `transcript.py` just to avoid a few lines.

### Frontend

- Add `services/web/src/features/officer/ApplicationDetailRoute.tsx`.
- The detail route should read `applicationId` from TanStack params, bootstrap principal state like `ApplicationQueueRoute`, fetch detail and transcript only after officer auth passes, expose refresh/retry, and render read-only metadata, responses, and transcript.
- Add `ApplicationTranscriptList` in the detail route file unless it grows large enough to justify a separate component. It should render `state_change` and `message` entries chronologically with distinct styling.
- Extend `services/web/src/api/client.ts` with:
  - fuller `applicationReadSchema` fields consumed by the detail page;
  - `applicationTranscriptReadSchema` using `z.discriminatedUnion("type", [...])`;
  - `fetchOfficerApplication(applicationId)`;
  - `fetchOfficerApplicationTranscript(applicationId)`.
- Add route registration in `services/web/src/app/router.tsx` using TanStack's dynamic path syntax, expected as `/applications/$applicationId`.
- Add detail navigation from queue rows in `ApplicationQueueRoute.tsx`, without changing claim behavior. A row-level "View" link is enough; after a successful claim, the e2e flow must be able to reach `/applications/{claimed_application_id}`.
- Extend `officer.module.css` with detail layout, metadata/responses, transcript feed, and responsive stacked/mobile classes.

### Tests

- Extend `services/api/tests/test_web_officer_applications.py` with detail happy path, transcript happy path, missing Pomerium identity, non-officer, missing/invalid Discord claim reuse, detail not found, transcript not found, detail authority denied, transcript authority denied, first-login/member resolution reuse, and no `If-Match` requirement.
- Expand `test_officer_endpoints_have_locked_actor_construction` so the expected route set includes the two new GET routes and still forbids `get_current_actor`, context actor reads, `verify_applicant_receipt`, and applicant receipt cookie use.
- Add `services/web/tests/officer-detail.spec.ts` for auth states, identity-incomplete state, detail render, response rendering, transcript render for both entry types, detail `404`, transcript `403`, network/API failure notices, and refresh/retry.
- Extend `infra/tests/test_applicant_discord_pomerium.py` so `/applications` remains public, `/applications/queue` and `/applications/queue/` still resolve to queue routes, `/applications/<uuid>` resolves to the new protected prefix, and the prefix precedes the catch-all.
- Extend `infra/tests/fixtures/web-ui/contract.json` with `routes.officer_detail`, `applications.detail.endpoint`, and `applications.transcript.endpoint`.
- Extend `infra/tests/validate_web_ui_local.sh` to require `officer-detail.spec.ts`, the new contract fixture keys, and positive client literals for `/api/web/officer/applications/${applicationId}` and `/api/web/officer/applications/${applicationId}/transcript`.
- Extend `infra/tests/e2e/lib/playwright/browser-flow.mjs` after claim to navigate to the claimed detail route and assert detail metadata plus a `state_change` transcript entry for the claim.
- Extend `infra/tests/e2e/tests/19-web-ui.sh` to validate the detail/transcript record produced by the browser flow and keep the existing queue/claim persistence checks.

## Modify in place (additive only)

- `services/api/app/api/v1/endpoints/web.py` - add imports for `read_application`, `require_application_read_authority`, `read_application_transcript`, `ApplicationTranscriptRead`, and transcript error types; add only the two read endpoints and any small local transcript error helper.
- `services/api/tests/test_web_officer_applications.py` - add tests and update the dependency guard route set.
- `services/web/src/api/client.ts` - add schemas, types, and fetchers; keep existing queue/claim functions stable.
- `services/web/src/app/router.tsx` - import `ApplicationDetailRoute` and add the dynamic child route.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx` - add detail navigation affordance only; do not alter the state filter, claim `If-Match`, conflict handling, or queue fetch semantics.
- `services/web/src/features/officer/officer.module.css` - append detail/transcript styles.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` - insert the protected `/applications/` prefix route at the locked position.
- `infra/tests/test_applicant_discord_pomerium.py`, `infra/tests/fixtures/web-ui/contract.json`, `infra/tests/validate_web_ui_local.sh`, `infra/tests/e2e/lib/playwright/browser-flow.mjs`, and `infra/tests/e2e/tests/19-web-ui.sh` - extend existing beta-i coverage.

## Anti-scope (do not touch)

- Do not change direct `/api/v1/applications/{id}` or `/api/v1/applications/{id}/transcript` behavior except through shared helpers if absolutely necessary.
- Do not change `services/api/app/services/applications.py` state machine, transition authority, ownership, audit semantics, list behavior, or optimistic locking.
- Do not change application message append endpoints or services; transcript is read-only.
- Do not add detail actions: no claim button, transition controls, approve/deny/waitlist, reassign, message append, comments, or Discord thread controls.
- Do not add new permissions, actor kinds, member-link tables, migrations, or authority compatibility shims.
- Do not change Authentik officer OAuth configuration; beta-i already handled identity claim plumbing.
- Do not change public `/applications` applicant form, applicant receipt machinery, `/auth/discord/*`, or public submit behavior.
- Do not add live updates, SSE/WebSocket, transcript pagination, transcript filtering UI, markdown rendering infrastructure, or actor display-name lookup.
- Do not perform Discord-visible writes.

## Dependency ordering

1. Extend backend bridge tests in `test_web_officer_applications.py`, including the locked dependency guard for the two new routes.
2. Add the two backend bridge GET endpoints in `web.py`, reusing `_build_officer_actor`, `read_application`, `require_application_read_authority`, and `read_application_transcript`.
3. Expand `client.ts` schemas and add the two browser-facing fetch functions.
4. Add `ApplicationDetailRoute.tsx` and register `/applications/$applicationId` in the router.
5. Add queue-row detail navigation while preserving beta-i queue/claim behavior.
6. Add `officer-detail.spec.ts` using the existing fixture/mocking style.
7. Add the Pomerium `/applications/` protected prefix and extend static route-order/collision tests.
8. Extend `contract.json`, `validate_web_ui_local.sh`, `browser-flow.mjs`, and `19-web-ui.sh` for post-claim detail/transcript verification.

## Implementer notes

- Browser code must call `/api/web/officer/applications/...`; nginx rewrites `/api/` to API `/api/v1/`. Do not introduce `/api/v1/` literals in `services/web/src`.
- The transcript discriminator is `type`, not `kind`. State-change fields are `occurred_at`, `change_type`, `from_state`, `to_state`, `actor_kind`, `actor_id`, and `aggregate_seq`; message fields are `occurred_at`, `message_seq`, `author_actor_kind`, `author_actor_id`, `visibility`, and `body_markdown`.
- `read_application_transcript` lives in `app.services.application_transcript`, even though the direct endpoint is under `endpoints/applications/transcript.py`.
- Detail read authorization is not "officer group means all applications." The officer actor still needs an applicable application permission grant through `require_application_read_authority`.
- For `ApplicationRead.responses`, render plain key/value JSON for v1. Do not attempt form-field-specific widgets beyond readable labels/values.
- Treat `body_markdown` as display text unless an existing safe markdown renderer is already in the route's dependency surface.
- Keep the detail page read-only. Any button that mutates an application belongs to beta-iii or later.
- The `/applications/` Pomerium prefix intentionally does not match bare `/applications`; the applicant form remains public.

## Open questions for the orchestrator

- None blocking. One non-blocking parity choice: the direct detail GET sets an ETag, while the beta-ii proposal/problem map says no `If-Match` or `set_etag` complexity for the bridge. The implementation should omit bridge ETag handling unless the orchestrator overrides that locked scope.
