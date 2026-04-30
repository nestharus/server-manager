# INIT-133B-iii hookpoints

## Summary

INIT-133B-iii should extend the beta-ii officer detail route with two additive mutation surfaces: application message append and non-claim transitions. The backend hookpoint is the existing Pomerium officer bridge in `services/api/app/api/v1/endpoints/web.py`; new POST routes should stay thin, build the officer actor with `_build_officer_actor` / `get_officer_actor`, construct trusted request bodies server-side where needed, then call existing application services.

The frontend hookpoint is the existing `/applications/$applicationId` route in `services/web/src/features/officer/ApplicationDetailRoute.tsx`. Add a message composer and transition controls under the current metadata/transcript layout, then use browser-facing `/api/web/officer/...` client functions from `services/web/src/api/client.ts`. Do not alter direct `/api/v1/applications/...` endpoints, the queue claim flow, Pomerium/Auth configuration, Discord-visible behavior, or application state-machine internals.

## Reuse (call directly)

### Backend

- `services/api/app/api/v1/endpoints/web.py::_db`, `_build_officer_actor`, and `get_officer_actor` are the bridge entry points. The new POST routes should follow the existing list/detail/claim/transcript endpoints: resolve Pomerium identity, require `officers`, validate `discord_user_id`, resolve/create the real Discord member, and use `ActorIdentity(actor_kind="user", actor_id=<member_uuid>)`.
- `services/api/app/api/v1/endpoints/web.py::officer_claim_application` is the closest transition bridge pattern: parse `If-Match`, build/accept an `ApplicationTransitionRequest`, call `transition_application`, map known errors, set the response ETag, and return `ApplicationRead`.
- `services/api/app/api/v1/endpoints/applications/lifecycle.py::transition_application_endpoint` is the direct transition endpoint shape. The officer transition bridge should mirror its `ApplicationTransitionRequest` body and strong ETag behavior, while restricting beta-iii unsupported actions at the bridge.
- `services/api/app/api/v1/endpoints/applications/messages.py::append_application_message_endpoint` is the direct message append pattern. The officer bridge differs only by not trusting browser author fields; it must fill `author_actor_kind` and `author_actor_id` from the Pomerium-resolved officer actor.
- `services/api/app/api/v1/endpoints/applications/_shared.py::parse_if_match_strong`, `set_etag`, and `raise_known_application_error` are reusable for transition optimistic locking and known service errors.
- `services/api/app/services/applications.py::transition_application` is authoritative for transitions, authority, owner constraints, required fields, audit mutation, and version increments.
- `services/api/app/services/applications.py::VALID_TRANSITIONS` is authoritative for state-machine visibility. The frontend helper should mirror only the exposed beta-iii subset, not invent a second state machine.
- `services/api/app/services/applications.py::require_transition_authority` maps all exposed beta-iii actions to `application.{action}`. Keep that service behavior; do not add bridge-level permission shortcuts.
- `services/api/app/services/application_messages.py::append_application_message` is authoritative for message idempotency, `application.message` authority, officer-only visibility, correlation context, and created-vs-duplicate status.
- `services/api/app/contracts/applications.py::ApplicationTransitionAction` and `ApplicationTransitionRequest` are the transition request contract. Expose only `review`, `request_interview`, `waitlist`, `approve`, `deny`, `reactivate`, and `withdraw` through the officer bridge/UI.
- `services/api/app/contracts/application_messages.py::ApplicationMessageAppendRequest` and `ApplicationMessageRead` are the service/direct response contracts. The browser bridge needs a narrower web request contract without author fields.

### Frontend

- `services/web/src/features/officer/ApplicationDetailRoute.tsx` already owns officer principal bootstrap, detail/transcript loading, auth/forbidden/identity-incomplete states, refresh, notices, metadata rendering, response rendering, and transcript rendering. Extend this route; do not create a parallel detail runtime.
- `services/web/src/features/officer/ApplicationTranscriptList` already renders state changes and messages from transcript entries. After append/transition success, refetch detail and transcript so this existing list reflects the mutation.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx::claim` is the closest mutation UI pattern: submit with current `application.version`, show 409/412/428/403 notices, refetch after both success and failure, and keep mutation state route-local.
- `services/web/src/api/client.ts::ApiError`, `readErrorPayload`, `applicationReadSchema`, `applicationTranscriptReadSchema`, `fetchOfficerApplication`, `fetchOfficerApplicationTranscript`, and `claimOfficerApplication` are the client-side error, schema, fetch, and ETag patterns to extend.
- `services/web/src/components/primitives/Button.tsx` and `services/web/src/features/officer/officer.module.css` are the local UI/styling hookpoints. Keep actions compact and route-local.

### Test fixtures

- `services/api/tests/test_web_officer_applications.py` is the backend bridge test owner. Reuse `OFFICER_APPLICATIONS_URL`, `_pomerium_headers`, `_officer_member_with_grants`, `_create_application`, `_claim_application`, `_grant`, `_latest_activity_action`, `_append_application_message_via_api`, and the dependency-tree guard.
- `services/web/tests/officer-detail.spec.ts` is the Playwright component-test style to extend or mirror: fixture-loaded contract paths, `page.route` mocks, auth-state tests, detail/transcript assertions, and read-only regression checks.
- `infra/tests/fixtures/web-ui/contract.json` already contains officer queue, claim, detail, and transcript paths. Add message and transition endpoint entries here before extending validators/e2e.
- `infra/tests/validate_web_ui_local.sh` already validates fixture shape, officer specs, client endpoint literals, and the `/api/v1/` source ban. Extend these static checks for message and transition paths.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` already reaches claimed detail and verifies the claim transcript entry. Extend from that point for message append, review, and approve.
- `infra/tests/e2e/tests/19-web-ui.sh` already seeds review/claim plus separate message authority and asserts claim/detail persistence. Extend the existing test rather than adding a new numbered e2e.

### Config

- No new Pomerium route is needed. Beta-i protects `/api/web/officer/`, and beta-ii protects `/applications/` detail paths.
- No Authentik/Pomerium claim changes are needed. The bridge uses the existing `x-pomerium-claim-groups` and `x-pomerium-claim-discord-user-id` parsing through `/api/me` / `get_pomerium_principal`.
- No database migration or new authority permission is needed. Existing `application.message`, `application.review`, `application.request_interview`, `application.waitlist`, `application.approve`, `application.deny`, `application.reactivate`, and `application.withdraw` grants cover this slice.

## New (write fresh)

### Backend

- Add `OfficerApplicationMessageAppendRequest` to `services/api/app/contracts/web.py` with `body_markdown`, `visibility`, and optional `client_message_id`. Keep `_WebModel` extra-forbid behavior and do not expose `author_actor_kind` or `author_actor_id` to the browser.
- Add `POST /api/v1/web/officer/applications/{application_id}/messages` in `services/api/app/api/v1/endpoints/web.py`.
  - Dependency: `actor: ActorIdentity = Depends(get_officer_actor("api:/api/v1/web/officer/applications/{application_id}/messages"))`.
  - Construct `ApplicationMessageAppendRequest` with browser body fields plus `author_actor_kind=actor.actor_kind` and `author_actor_id=actor.actor_id`.
  - Call `append_application_message(db, application_id=application_id, request=actor_scoped_body)`.
  - Return `ApplicationMessageRead`; set status `201 Created` when created and `200 OK` when `client_message_id` is duplicate.
- Add `POST /api/v1/web/officer/applications/{application_id}/transitions` in `services/api/app/api/v1/endpoints/web.py`.
  - Body uses `ApplicationTransitionRequest`.
  - Reject `claim` before calling the service with 400 `claim_action_uses_dedicated_endpoint`; the dedicated claim route remains the browser path for claim ownership.
  - Parse `If-Match` with `parse_if_match_strong(request)`.
  - Call `transition_application(..., request_surface=f"api:/api/v1/web/officer/applications/{application_id}/transitions", allow_route_transition=True)` so the web route supports `route`.
  - Set the returned ETag with `set_etag(response, result.etag)` and return `ApplicationRead`.
- Message append mapper parity is handled locally in `web.py`: `_raise_officer_application_message_error` maps `ApplicationMessageVisibilityError -> 422 applicant_visibility_required`, matching the direct messages endpoint behavior.

### Frontend

- Add `services/web/src/features/officer/applicationStateMachine.ts`.
  - Export the beta-iii action subset.
  - Export `validOfficerTransitionActions(state)` mirroring `VALID_TRANSITIONS` for exposed actions only.
  - Export field metadata for required inputs: `review.notes`, `waitlist.reason`, `approve.decision_reason`, `deny.decision_reason`; optional inputs for `request_interview.thread_id/reason`, `reactivate.reason`, and `withdraw.notes`.
- Add `services/web/src/features/officer/ApplicationMessageComposer.tsx`.
  - Own textarea body, visibility segmented control, `client_message_id`, and submitting state.
  - Disable/block empty or whitespace-only body.
  - On success, clear body, preserve selected visibility, rotate a UUIDv4 idempotency token, and notify the route to refetch transcript.
  - Do not send author fields.
- Add `services/web/src/features/officer/ApplicationTransitionActions.tsx`.
  - Render only actions returned by `validOfficerTransitionActions(application.state)`.
  - Collect required fields before enabling submit.
  - Submit with `expectedVersion: application.version`.
  - On success, hand returned `ApplicationRead` to the route and trigger detail/transcript refetch.
- Extend `services/web/src/api/client.ts`.
  - Add message visibility, message append request, message read, and widened transition request schemas.
  - Add `appendOfficerApplicationMessage`.
  - Add `transitionOfficerApplication` using `If-Match: "<version>"`.
  - Keep browser paths under `/api/web/officer/...`; do not add `/api/v1/` literals.

### Tests

- Extend `services/api/tests/test_web_officer_applications.py` for:
  - message append happy path, 201 created, duplicate `client_message_id` 200, transcript visibility, `application.message` denial, actor spoofing via `X-Actor-*`, applicant receipt ignored, and server-side author binding;
  - transition missing/malformed/stale `If-Match`, happy `review` and `approve`, ETag update, audit `request_surface`, authority denial, owner denial, invalid action rejection for `claim`/`route`/`reassign`, and required-field failures;
  - dependency guard route set including the two new POST routes.
- Add `services/web/tests/officer-actions.spec.ts` or extend `services/web/tests/officer-detail.spec.ts` for:
  - composer payload and no author fields;
  - composer success clears textarea and refetches transcript;
  - state-based action visibility for `claimed`, `in_review`, `interview`, `waitlisted`, and terminal states;
  - required field behavior for `review`, `waitlist`, `approve`, and `deny`;
  - transition `If-Match`, success refresh, 409/412/428/403 notices, parse failure, and network/5xx recovery.
- Extend `infra/tests/e2e/lib/playwright/browser-flow.mjs` to append an officer-only message, submit `review`, then submit `approve` from the existing claimed detail page.
- Extend `infra/tests/e2e/tests/19-web-ui.sh` to assert final `in_review` / `approved` persisted states, `decision_reason`, message row, and audit request surfaces.

## Modify in place (additive only)

- `services/api/app/contracts/web.py` - add only the narrow message append bridge request model.
- `services/api/app/api/v1/endpoints/web.py` - add imports for web message request, application message request/read/error types, `append_application_message`, and the two POST endpoints. Preserve existing list/detail/claim/transcript behavior.
- `services/api/app/api/v1/endpoints/applications/_shared.py` - only add message visibility error mapping if the implementation chooses shared mapping over a local `web.py` helper.
- `services/api/tests/test_web_officer_applications.py` - add beta-iii tests and update the locked route set; keep existing beta-i/beta-ii tests intact.
- `services/web/src/api/client.ts` - add schemas/types/functions; preserve `claimOfficerApplication`.
- `services/web/src/features/officer/ApplicationDetailRoute.tsx` - mount composer and transition actions below the current metadata/transcript content; keep principal bootstrap and read error panels intact.
- `services/web/src/features/officer/officer.module.css` - append route-local styles for composer, visibility control, action group, field rows, and notices.
- `services/web/tests/officer-detail.spec.ts` or new `services/web/tests/officer-actions.spec.ts` - use existing contract fixture style.
- `infra/tests/fixtures/web-ui/contract.json`, `infra/tests/validate_web_ui_local.sh`, `infra/tests/e2e/lib/playwright/browser-flow.mjs`, and `infra/tests/e2e/tests/19-web-ui.sh` - extend existing beta-i/beta-ii coverage.
- `infra/tests/e2e/lib/seed-authority-grants.mjs` or `19-web-ui.sh` grant SQL - include `application.approve` for the officer; keep `application.message` seeding available.

## Anti-scope (do not touch)

- Do not change direct `/api/v1/applications/{id}/messages` or `/api/v1/applications/{id}/transitions` semantics.
- Do not change `services/api/app/services/applications.py` state machine, `VALID_TRANSITIONS`, transition authority, owner checks, required-field validation, audit action types, or optimistic locking.
- Do not change `services/api/app/services/application_messages.py` idempotency, visibility, authority, or persistence behavior.
- Do not alter beta-i queue claim endpoint/UI or claim-specific conflict handling.
- Do not add route/reassign UI, owner picker, member search, route action support, or bulk actions.
- Do not add Discord-visible messages, DMs, embeds, channels, roles, moderation actions, or permission mutations.
- Do not add applicant DM materialization, message editing/deletion/replies/threading, attachments, markdown rendering infrastructure, real-time updates, pagination, or transcript filters.
- Do not add schema migrations, new actor kinds, new permissions, compatibility shims, feature flags, deprecated aliases, or deferred stubs.
- Do not change Authentik/Pomerium route policy or applicant auth/receipt machinery.

## Dependency ordering

1. Extend API bridge tests in `services/api/tests/test_web_officer_applications.py` for the message and transition contracts, including dependency guard expectations for the two new POST routes.
2. Add `OfficerApplicationMessageAppendRequest` in `services/api/app/contracts/web.py`.
3. Add the message bridge endpoint in `web.py`, reusing `_build_officer_actor`, server-side author construction, `append_application_message`, and created/duplicate status handling.
4. Add the transition bridge endpoint in `web.py`, reusing `parse_if_match_strong`, beta-iii action validation, `transition_application`, `raise_known_application_error`, and `set_etag`.
5. Extend `services/web/src/api/client.ts` schemas and add `appendOfficerApplicationMessage` / `transitionOfficerApplication`.
6. Add `applicationStateMachine.ts`, `ApplicationMessageComposer.tsx`, and `ApplicationTransitionActions.tsx`.
7. Mount the new components in `ApplicationDetailRoute.tsx` and append route-local CSS.
8. Add/extend Playwright component tests for composer, transition controls, notices, and refetch behavior.
9. Extend `contract.json` and `validate_web_ui_local.sh` for message/transition paths and client literal checks.
10. Extend e2e authority seeding, browser flow, and `19-web-ui.sh` persistence/audit assertions for message -> review -> approve.

## Implementer notes

- Browser code must call `/api/web/officer/applications/{id}/messages` and `/api/web/officer/applications/{id}/transitions`; nginx handles `/api/` to `/api/v1/` rewriting.
- The transition bridge should parse/build the Pomerium officer actor before `parse_if_match_strong`, matching the claim endpoint's identity-first behavior.
- The transition bridge should not special-case service validation except for excluding `claim`, `route`, and `reassign` from the officer bridge. Required fields and owner constraints belong to `transition_application`.
- `reactivate` may omit `new_owner_id` when the waitlisted application already has an owner. If no owner exists, the existing service raises `application_reactivate_owner_required`; do not add an owner picker in this slice.
- `request_interview` is idempotent when the service's interview-thread logic says it is; the bridge should pass through the service result and ETag.
- For message append, `client_message_id` idempotency is service-owned. The frontend should preserve the same UUID while a compose is being retried and rotate only after success.
- The frontend action helper should be table-driven and colocated with officer features. Keep the service as the source of truth; the helper only prevents rendering known-invalid controls.
- Notices should distinguish stale/precondition (`412`/`428`), transition conflict (`409`), forbidden (`403`), validation (`422`), network, parse, and server failures, then refetch where the current application version may have changed.
- Transcript message text should continue to render as text. Do not add markdown rendering unless an existing safe renderer is already in the route dependency surface.
- E2E audit assertions should expect transition `request_surface` to be `api:/api/v1/web/officer/applications/{id}/transitions`.

## Open questions for the orchestrator

- None blocking. One implementation choice remains: map `ApplicationMessageVisibilityError` through `raise_known_application_error` for shared parity, or keep a tiny local message mapper in `web.py` mirroring the direct message endpoint.
