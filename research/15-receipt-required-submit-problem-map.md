READ:
- `.tmp/rca/member-conversion-FINDINGS.md`
- `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- `plans/BACKLOG.md`
- `proposals/02-public-application-intake.md`
- `proposals/08-applicant-discord-oauth.md`
- `proposals/06-members-kind.md`
- `services/api/app/api/v1/endpoints/auth_discord.py`
- `services/api/app/services/applicant_discord_auth.py`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/members.py`
- `services/api/app/repositories/members.py`
- `services/web/src/main.tsx`
- `services/web/tests/compat.spec.ts`
- `infra/tests/fixtures/web-ui/contract.json`
- `infra/tests/test_web_ui_contract.py`
- `infra/tests/e2e/lib/playwright/browser-flow.mjs`
- `infra/tests/e2e/tests/19-web-ui.sh`
- `services/api/tests/test_public_application_route.py`
- `services/api/tests/test_public_intake_submit.py`
- `services/api/tests/test_auth_discord_callback.py`
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
- `containers/server-manager/nginx-web.conf`
- `services/api/app/services/notification_events.py`
- `services/api/app/services/notifications_materialize.py`
- `services/api/app/contracts/notifications.py`

## Touched surface

- `services/api/app/api/v1/endpoints/auth_discord.py`
  - `discord_auth_callback()` currently sets `applicant_receipt` with `path="/applications"`, `max_age=settings.applicant_receipt_ttl_seconds`, `secure=True`, `httponly=True`, and `samesite="Lax"`.
  - This slice is expected to change the cookie path/scope so a browser sends the receipt to both `/auth/discord/me` and the submit request path, currently `/api/public/applications` on the web host and `/api/v1/public/applications` in the API service.
  - `me()` already reads `applicant_receipt` from a cookie and verifies it; it is adjacent because the SPA will use it as the advisory login-state check.

- `services/api/app/services/applicant_discord_auth.py`
  - `sign_applicant_receipt()` emits an HS256 JWT containing exactly `discord_user_id`, `iat`, and `exp`.
  - `verify_applicant_receipt()` validates the signature, exact claim set, Discord snowflake shape, and freshness. It has no transport/cookie-path logic.
  - Expected submit binding should reuse this verifier rather than trusting SPA state.

- `services/api/app/api/v1/endpoints/applications/public.py`
  - `submit_public_application_endpoint()` currently accepts `PublicApplicationSubmission`, depends only on `authorize_public_intake`, and calls `submit_public_application()`.
  - Expected change: add a receipt dependency or equivalent endpoint-layer verification that returns `401` with a structured error code when the cookie is missing, malformed, tampered, signed with the wrong key, or expired.
  - The Cedar dependency remains: `Public::"web-intake.<channel>"` still gates `Action::"application:submit_public"` for the public route.

- `services/api/app/services/applications.py`
  - Current anonymous path is `submit_public_application()` -> `resolve_or_create_public_intake_member()` -> `_submit_application_internal(..., submission_authority=_SubmissionAuthority.PUBLIC_INTAKE)`.
  - Expected change: add a receipt-aware public submit entry point that resolves the verified Discord snowflake to a real `members.kind='discord'` row, builds `ApplicationSubmission(applicant_id=<real_member_id>, ...)`, and calls `_submit_application_internal(..., submission_authority=_SubmissionAuthority.USER)`.
  - The actor should be the real member UUID, not the Discord snowflake, because `_require_submit_authority()` treats a submit as self-authorized when `actor.actor_id == str(applicant_id)`.
  - `submit_public_application()` and `resolve_or_create_public_intake_member()` become legacy rollback-only paths, unreachable from the public route once this slice lands.

- `services/api/app/services/members.py`
  - `create_or_get_member()` already looks up by `discord_user_id`, inserts normal rows with repository default `_kind="discord"`, and recovers from unique races by fetching after `UniqueViolation`.
  - `resolve_or_create_public_intake_member()` is the current synthetic path and explicitly inserts `_kind="public_intake"`.
  - Expected change: add or reuse a real-Discord-member lookup-or-create helper that requires existing rows to be `kind == "discord"` and creates absent rows as `kind == "discord"`.

- `services/api/app/repositories/members.py`
  - `fetch_member_by_discord_id()` selects `m.kind` but does not constrain by kind.
  - Optional change: add `fetch_member_by_discord_id_and_kind()` if the service should enforce real-member binding in SQL rather than with a post-fetch kind check.

- `services/web/src/main.tsx`
  - The applications page has a Discord login button and calls `/auth/discord/me` to display login state.
  - Submit currently posts directly to `/api/public/applications` regardless of `/auth/discord/me` result.
  - Expected change: gate submit on `/auth/discord/me` returning 200, redirect to `/auth/discord/start?return_to=/applications` on 401, and only POST after a verified receipt exists.

- `services/web/tests/compat.spec.ts`, `infra/tests/fixtures/web-ui/contract.json`, and `infra/tests/test_web_ui_contract.py`
  - Current web component contract still permits anonymous submit; the test is explicitly named "application form still submits through the anonymous INIT-120 path".
  - Expected change: contract and tests must require Discord login/receipt gating before submit.

- `infra/tests/e2e/lib/playwright/browser-flow.mjs` and `infra/tests/e2e/tests/19-web-ui.sh`
  - Current e2e submits without an applicant receipt and then asserts the persisted applicant `discord_user_id` starts with `public:`.
  - Expected change: Phase 3 must pick either a full OAuth/AuthentiK browser path or a seeded-receipt bypass, then assert the persisted applicant is a real `kind='discord'` member with the verified snowflake.

- `services/api/tests/test_public_application_route.py`, `services/api/tests/test_public_intake_submit.py`, and `services/api/tests/test_auth_discord_callback.py`
  - Route tests currently prove the public route accepts valid bodies without actor headers.
  - Service tests currently prove public submit creates synthetic applicants.
  - Auth tests currently prove callback receipt issuance and `/auth/discord/me` verification only when tests manually provide a `Cookie` header.
  - Expected change: add missing/invalid/expired/tampered receipt tests for public submit, valid receipt tests for real member create/reuse, cookie path assertions, and tests proving synthetic creation is no longer reachable through the public route.

## Current supported paths

- INIT-120 anonymous public submit works today:
  - Browser posts `POST /api/public/applications`.
  - The nginx web proxy maps `/api/` to API `/api/v1/`, so the API receives `POST /api/v1/public/applications`.
  - The endpoint authorizes `Public::"web-intake.local"` for `Action::"application:submit_public"`.
  - `submit_public_application()` creates or reuses a synthetic `members.kind='public_intake'` row whose `discord_user_id` starts with `public:`.
  - `_submit_application_internal()` is called with `PUBLIC_INTAKE` authority and service actor `public-intake`, so queued applications persist without a real Discord member.

- INIT-127 applicant Discord OAuth works as a separate identity proof:
  - `/auth/discord/start` creates PKCE/state and redirects to Authentik.
  - `/auth/discord/callback` exchanges the code, validates the ID token, extracts `discord_user_id`, and sets an HttpOnly receipt cookie.
  - `/auth/discord/me` verifies `applicant_receipt` and returns `{"discord_user_id": "<snowflake>"}` if the cookie reaches that endpoint.

- These two surfaces do not communicate:
  - The public submit endpoint does not read or verify `applicant_receipt`.
  - The SPA calls `/auth/discord/me` only for display state; it does not block submit when unauthenticated.
  - No current code resolves a receipt snowflake to a real member for public submit.

## Known risky or brittle behavior already present

- The receipt cookie is currently scoped to `Path=/applications`.
  - Verified in `services/api/app/api/v1/endpoints/auth_discord.py`: `response.set_cookie(..., path="/applications", secure=True, httponly=True, samesite="Lax")`.
  - A browser will not send a `Path=/applications` cookie on requests to `/auth/discord/me`.
  - A browser will also not send it on the submit request to `/api/public/applications`.
  - Therefore the current browser path can show false negatives for `/auth/discord/me`, and a receipt-required submit implementation would fail in a real browser unless cookie scope changes.

- The API submit path and the SPA path differ by proxy layer:
  - SPA request path: `/api/public/applications` on `web.local.humility.local`.
  - API service path after nginx proxy: `/api/v1/public/applications`.
  - Cookie path matching happens before nginx proxying, against the browser-visible `/api/public/applications` path.
  - A fix scoped only to `/api/v1/public/applications` would not help the browser-posted request.

- Existing tests do not catch the cookie-path bug.
  - `test_auth_discord_callback.py` checks cookie attributes but does not currently assert `Path`.
  - `/auth/discord/me` tests pass explicit `Cookie` headers, bypassing browser path rules.
  - Web component tests use `context.addCookies()` and route mocks, not the real callback `Set-Cookie` path behavior.

- Public submit is intentionally unauthenticated today.
  - `submit_public_application_endpoint()` does not depend on actor headers or receipt verification.
  - `test_public_route_accepts_valid_body_without_actor_headers` encodes that behavior as supported INIT-120 coverage.

- Actor identity is easy to get subtly wrong in the new path.
  - `_SubmissionAuthority.USER` invokes `_require_submit_authority()`.
  - Self-submit succeeds only when the actor id is the member UUID string.
  - Using the Discord snowflake as `ActorIdentity(actor_kind="user", actor_id=<snowflake>)` would fall into grant checking and could reject a legitimate applicant.

- `create_or_get_member()` handles concurrent creation through a unique-violation recovery pattern, not through SQL `INSERT ... ON CONFLICT`.
  - This may be acceptable if the new helper reuses it exactly.
  - If a new helper bypasses it, the concurrent-submit race must be handled explicitly.

- The existing notification materializer supports static `discord_user` and `discord_users` recipient selectors.
  - It does not currently resolve "recipient is payload.applicant_discord_user_id".
  - A minimal submit-time DM event may require either a small dynamic-recipient extension or deferral.

## Adjacent surfaces inside the blast radius

- INIT-120 public web and e2e coverage.
  - Current component and e2e tests must be redesigned to OAuth-then-submit or forked so any legacy anonymous spec is explicitly unreachable from the active public route.

- INIT-124 and INIT-125A synthetic-member boundary guards.
  - The new receipt-aware path should pass a real `kind='discord'` member into `_submit_application_internal()`.
  - The existing `applicant_synthetic_not_allowed` rejection remains correct for authenticated/user-authority submit.
  - Synthetic `kind='public_intake'` rows from pre-slice submissions remain historical/orphaned data.

- Audit substrate.
  - The receipt-aware submit path should use `submission_authority=USER`, `request_surface` for the public submit route, and actor identity for the real applicant member.
  - This aligns new public web submit with the existing officer/user submit audit model rather than the anonymous `public-intake` service actor.

- Member persistence.
  - `members.discord_user_id` is unique.
  - `members.kind` is constrained to `discord` or `public_intake`.
  - No `member_links` table should be added for this slice under the locked direction.

- Cedar public-intake policy.
  - Policy remains a coarse route/action gate for `Public::"web-intake.<channel>"`.
  - The receipt is the applicant authentication proof; Cedar does not become a per-applicant Discord policy in this slice.

- Notification substrate.
  - Existing event emission queues a `notifications_materialize` deferred effect under the current audit context.
  - Applicant DM can fit the notification substrate only if Phase 3 keeps it minimal or defines the required dynamic recipient behavior.

## Adjacent public or user-reachable paths

- `/applications`
  - Public SPA form, Discord login button, advisory login-state display, and submit trigger.

- `/api/public/applications`
  - Browser-visible POST path on the web host.
  - Currently proxied by nginx to `/api/v1/public/applications`.

- `/api/v1/public/applications`
  - API service route that currently accepts anonymous public submits after Cedar public-intake authorization.

- `/auth/discord/start`
  - Starts the applicant Authentik/Discord OAuth flow and supports `return_to=/applications`.

- `/auth/discord/callback`
  - API-owned callback reached through the Pomerium `/auth/discord/` route on the web host.
  - Sets the `applicant_receipt` cookie.

- `/auth/discord/me`
  - API-owned receipt verification endpoint reached through the same Pomerium route.
  - Currently only works in a real browser if cookie scope allows the cookie to be sent to `/auth/discord/me`.

- Discord DM channel
  - User-reachable target for the optional immediate applicant notification.
  - Any actual send remains Discord-visible Tier 3 behavior at runtime, but emitting an internal event/envelope is a confined local/API change until a delivery worker sends it.

## Deployment mode and cohort

- Deployment mode is local first.
- Remote channels each have their own Authentik + Discord OAuth setup from BL-016 and should receive the same route/cookie/submit contract once the local slice is proven.
- Primary cohort is public web applicants submitting through `/applications`.
- Officers and protected admin surfaces remain on existing Pomerium auth and are adjacent only through shared application/audit/notification data.
- Pre-slice synthetic submissions are orphaned historical records. There is no retroactive auto-link in this slice; BL-018 owns cleanup/archival.

## Open questions for proposal

- **IMPLEMENTATION:** Cookie path/scope. The actual current callback sets `Path=/applications`, which does not cover `/auth/discord/me` or `/api/public/applications`. Should Phase 3 widen the receipt cookie to `/`, issue an additional cookie scoped to `/api/public/applications`, or move to a bearer-token-in-header design where the SPA reads a verified token from `/me` and sends `Authorization: Bearer` on submit?

- **IMPLEMENTATION:** Server-side receipt verification on submit. Should the endpoint add a FastAPI dependency such as `verify_applicant_receipt(request) -> DiscordIdentity`, with Cedar public-intake authorization remaining as the earlier route/action gate?

- **IMPLEMENTATION:** Real-member lookup-or-create. Should the create path reuse the existing `create_or_get_member()` unique-violation recovery, or add a repository-level `INSERT ... ON CONFLICT DO NOTHING` helper to handle concurrent receipt-required submits more directly?

- **PRODUCT:** Notification DM scope. Should this slice emit a notification event only, emit and materialize the applicant DM, or defer the DM entirely to a follow-on? The user's A5 direction says the applicant should receive an immediate DM with a link to the primary guild channel, which points toward event emission or full materialization unless Phase 3 explicitly keeps the identity-binding slice minimal.

- **UX:** Cookie banner or consent text on the form. This belongs to HCI research, not a user-facing proposal gate in this phase.

- **IMPLEMENTATION:** Receipt-only trust boundary. Should submit reject when the receipt's `discord_user_id` does not match an `X-Discord-User-Id` header, or should it trust the HMAC-signed receipt alone? The redundant header appears unnecessary because the receipt is signed and the SPA does not need to assert identity separately.

- **IMPLEMENTATION:** SPA verified-state caching. Should `/applications` call `/auth/discord/me` on every page load and again on submit, or cache the verified state in React/runtime state for the receipt TTL with a re-fetch on submit? The receipt TTL is 10 minutes by default.

- **AMBIGUOUS:** E2E refactor shape. Should `19-web-ui` perform the full OAuth/AuthentiK browser dance, or seed a valid receipt before submit? The seeded path is faster and less brittle but tests less of the live flow.
