# INIT-128 Phase 5 - Receipt-Required Submit Hookpoints

## Inputs read

- `proposals/09-receipt-required-submit.md`
- `research/15-receipt-required-submit-problem-map.md`
- `plans/risk/init-128-audit.md`
- `plans/risk/init-128-scope.md`
- `plans/risk/init-128-shortcut.md`
- `plans/risk/init-128-supported-surface.md`
- `.tmp/rca/member-conversion-FINDINGS.md`
- `plans/audit-history/init-128-audit-history.md`
- `proposals/08-applicant-discord-oauth.md`
- `proposals/06-members-kind.md`
- `services/api/app/api/v1/endpoints/auth_discord.py`
- `services/api/app/services/applicant_discord_auth.py`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/members.py`
- `services/api/app/repositories/members.py`
- `services/api/app/contracts/members.py`
- `services/api/app/services/notification_events.py`
- `services/api/app/services/notifications_materialize.py`
- `services/api/app/contracts/notifications.py`
- `services/api/app/core/factory.py`
- `services/api/app/core/settings.py`
- `services/api/app/api/v1/router.py`
- `services/web/src/main.tsx`
- `services/web/tests/compat.spec.ts`
- `infra/tests/fixtures/web-ui/contract.json`
- `infra/tests/test_web_ui_contract.py`
- `infra/tests/validate_web_ui_local.sh`
- `infra/tests/e2e/lib/playwright/browser-flow.mjs`
- `infra/tests/e2e/lib/playwright/run-browser-flow.sh`
- `infra/tests/e2e/lib/playwright/package.json`
- `infra/tests/e2e/tests/19-web-ui.sh`
- `services/api/tests/test_public_application_route.py`
- `services/api/tests/test_public_intake_submit.py`
- `services/api/tests/test_auth_discord_callback.py`
- `services/api/tests/public_intake_fixtures.py`
- `migrations/versions/wu-011_members.py`
- `migrations/versions/wu-043_members_kind.py`
- `migrations/versions/wu-003c_notification_events.py`
- `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml`
- `gitops/channels/local/applications/server-manager/api-deployment.yaml`

Round-2 risk reports remain LOW and do not invalidate A1, A2, or A3. No `INVALIDATED_ASSUMPTION` condition was found.

## Cookie path hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/auth_discord.py:75` creates the callback redirect response.
- `services/api/app/api/v1/endpoints/auth_discord.py:76` starts the `response.set_cookie(...)` call for `applicant_receipt`.
- `services/api/app/api/v1/endpoints/auth_discord.py:79` already binds `max_age` to `settings.applicant_receipt_ttl_seconds`.
- `services/api/app/api/v1/endpoints/auth_discord.py:80` is the exact change point: `path="/applications"` becomes `path="/"`.
- `services/api/app/api/v1/endpoints/auth_discord.py:81-83` preserve `secure=True`, `httponly=True`, and `samesite="Lax"`.
- `services/api/tests/test_auth_discord_callback.py:366-370` already asserts receipt cookie attributes; add `cookie["path"] == "/"` there.

No new file is needed. This is a one-argument edit plus test assertion updates.

Conflicting systems:

- Browser cookie path matching happens before nginx rewrites `/api/public/applications` to the API route. Any narrower server-internal path such as `/api/v1/public/applications` would not cover the browser-visible submit path.
- Existing tests at `services/api/tests/test_auth_discord_callback.py:530-533` manually pass a `Cookie` header to `/auth/discord/me`, bypassing browser path rules. Add a cookie-jar test rather than relying only on explicit headers.

Deletion candidates:

- None for the cookie path itself. Do not add a second cookie with a different path; that would create a dual receipt surface.

## verify_applicant_receipt dep hookpoints

Reusable hookpoints:

- `services/api/app/services/applicant_discord_auth.py:20` exposes `DISCORD_SNOWFLAKE_RE`.
- `services/api/app/services/applicant_discord_auth.py:28` defines `ApplicantReceiptError`.
- `services/api/app/services/applicant_discord_auth.py:161-197` is the existing HMAC receipt verifier. Reuse it rather than reimplementing JWT validation.
- `services/api/app/api/v1/endpoints/auth_discord.py:88-105` currently factors endpoint-level cookie reading and verifier error mapping inside `/auth/discord/me`.
- `services/api/app/core/factory.py:73-81` flattens dict `HTTPException.detail` to a top-level JSON object, so `HTTPException(status_code=401, detail={"code": ..., "message": ...})` returns the required structured body.
- `services/api/app/core/settings.py:53-57` owns `applicant_receipt_signing_key` and `applicant_receipt_ttl_seconds`.

Recommended shape:

- Add an endpoint dependency helper named `verify_applicant_receipt(request: Request) -> DiscordIdentity` in `services/api/app/services/applicant_discord_auth.py`, alongside the existing verifier. To avoid name collision with the lower-level token verifier, name the existing imported call module-qualified when needed, or name the dependency `verify_applicant_receipt_cookie`.
- Add a small `@dataclass(frozen=True)` or Pydantic model `DiscordIdentity` with `discord_user_id: str` in the same module. No new module is required.
- The helper should read `request.cookies.get("applicant_receipt")`, call the existing token verifier with `request.app.state.settings.applicant_receipt_signing_key`, and convert all missing/invalid/tampered/expired cases to `401` with code `applicant_receipt_required`.
- Refactor `/auth/discord/me` at `services/api/app/api/v1/endpoints/auth_discord.py:88-105` to reuse the dependency helper if the dependency returns exactly the same `discord_user_id`; otherwise leave `/me` as-is and use the new helper only in public submit. Factoring is preferred because it keeps cookie/error handling in one place.

New files:

- None required. A new public-auth module would be permissible, but it adds routing-layer sprawl for one dependency.

Conflicting systems:

- The lower-level verifier is already named `verify_applicant_receipt` at `services/api/app/services/applicant_discord_auth.py:161`. If the FastAPI dependency uses the same name, imports in endpoint modules can become ambiguous. Prefer a cookie-specific dependency name or import the service module, not the function.

Deletion candidates:

- Inline `/auth/discord/me` cookie-verification code at `services/api/app/api/v1/endpoints/auth_discord.py:93-105` if it is factored into the new dependency.

## Public submit endpoint hookpoints

Reusable hookpoints:

- `services/api/app/api/v1/endpoints/applications/public.py:18` defines the public route prefix `/api/v1/public/applications`.
- `services/api/app/api/v1/endpoints/applications/public.py:26-30` is the exact endpoint signature insertion point. Add `identity: DiscordIdentity = Depends(verify_applicant_receipt...)` alongside the existing `db` and `_authz` dependencies.
- `services/api/app/api/v1/endpoints/applications/public.py:29` keeps `Depends(authorize_public_intake)`. Do not remove Cedar's route gate.
- `services/api/app/api/v1/endpoints/applications/public.py:31-34` is the exact dispatch point. Replace `submit_public_application(db, body)` with `submit_public_application_with_receipt(db, body, receipt=identity)`.
- `services/api/app/api/v1/endpoints/applications/public.py:35-38` keeps the response shape.
- `services/api/app/services/applications.py:153-154` already defines the authenticated and public submit audit surfaces.

Required deletion/update:

- Remove the active anonymous happy path from the endpoint by deleting the import of `submit_public_application` at `services/api/app/api/v1/endpoints/applications/public.py:12` and importing the new service entry instead.
- Missing/invalid receipts should fail in the dependency before this endpoint calls any mutation service. That means no member, application, audit action, or notification event should be created on 401.

Conflicting systems:

- `services/api/tests/test_public_application_route.py:43-76` currently encodes "valid body without actor headers" as 201. That becomes a receipt-required test: no actor headers is still allowed, but a valid `applicant_receipt` cookie is required.
- `services/api/tests/test_public_application_route.py:102-125` proves Cedar denial maps to 403. Dependency ordering matters: if missing receipt is evaluated before Cedar, a denied route with no cookie will return 401 rather than 403. The proposal does not require a specific ordering for simultaneous missing receipt + Cedar deny, but tests should explicitly cover each condition with the other prerequisite satisfied.

New files:

- None required.

## Real-member helper hookpoints

Reusable hookpoints:

- `services/api/app/services/members.py:115-176` is the existing real member create-or-get path. It preserves `aggregate_heads` and `member.create` audit via `mutate_entity`, but it handles races through `UniqueViolation`, not literal `ON CONFLICT DO NOTHING`.
- `services/api/app/services/members.py:179-255` is the existing synthetic public-intake resolver. The new helper belongs adjacent to this function, but must not call it.
- `services/api/app/repositories/members.py:37-45` fetches by `discord_user_id` and selects `kind`.
- `services/api/app/repositories/members.py:59-83` inserts normal members with `_kind="discord"` by default.
- `services/api/app/contracts/members.py:19-23` defines `MemberCreate`, which intentionally has no caller-supplied `kind`.
- `services/api/app/contracts/members.py:26-34` defines `MemberRead` including `kind`.
- `migrations/versions/wu-011_members.py:35-38` is the unique race boundary for `discord_user_id`.
- `migrations/versions/wu-043_members_kind.py:27-30` constrains `kind` to `discord` or `public_intake`.

Recommended shape:

- Add `resolve_or_create_real_discord_member(db, *, discord_user_id: str) -> MemberRead` in `services/api/app/services/members.py` near `resolve_or_create_public_intake_member`.
- Validate `discord_user_id` with `applicant_discord_auth.DISCORD_SNOWFLAKE_RE` or a shared local helper before any DB mutation.
- First `SELECT` by `discord_user_id`. If found, require `row["kind"] == "discord"` and return `_member_from_row(row)`. If found with any other kind, fail closed as corruption.
- If absent, create a real member with `kind="discord"`, `status="active"`, and `joined_at=datetime.now(UTC)`.

Implementation tension to close in Phase 6a:

- The approved proposal locks the race posture as `INSERT ON CONFLICT DO NOTHING + SELECT`, but existing member creation relies on `mutate_entity()` to create the aggregate head and audit action. A raw `INSERT ... ON CONFLICT DO NOTHING` into `members` alone would violate `services/api/app/repositories/members.py:20-22`, where reads join to `aggregate_heads`.
- Preferred implementation: add a repository helper that executes the `members` insert with `ON CONFLICT (discord_user_id) DO NOTHING`, and wrap it in a service transaction that also creates the aggregate head/audit action only for the inserted row. If that becomes too invasive, explicitly document that `create_or_get_member()`'s `UniqueViolation` recovery is the equivalent race posture being used to preserve audit invariants. Do not silently weaken both constraints.

Conflicting systems:

- `create_or_get_member()` returns any existing row at `services/api/app/services/members.py:120-123` without checking `kind`. The new helper must add the kind check and should not expose that looser behavior to receipt submit.
- Test fixtures can direct-insert members at `services/api/tests/public_intake_fixtures.py:102-121`; any new resolver tests must include aggregate head rows if direct inserts are used.

Deletion candidates:

- `resolve_or_create_public_intake_member()` at `services/api/app/services/members.py:179-255` becomes unreachable from active public submit if the endpoint is updated. Under the no-backwards-compat convention, prefer deleting it in this slice if no other references remain. If retained for BL-018 rollback/history, mark it explicitly as inactive and ensure no route imports it.

## Submit service entry hookpoints

Reusable hookpoints:

- `services/api/app/services/applications.py:30-39` imports `ApplicationSubmission` and `PublicApplicationSubmission`; the new entry can build the former from the latter.
- `services/api/app/services/applications.py:55` imports `resolve_or_create_public_intake_member`; replace or add an import for `resolve_or_create_real_discord_member`.
- `services/api/app/services/applications.py:153-155` defines `PUBLIC_SUBMIT_SURFACE` and the legacy public-intake actor.
- `services/api/app/services/applications.py:160-162` defines `_SubmissionAuthority.USER` and `_SubmissionAuthority.PUBLIC_INTAKE`.
- `services/api/app/services/applications.py:298-307` is the authority invariant: USER self-submit succeeds only when `actor.actor_id == str(applicant_id)`.
- `services/api/app/services/applications.py:596-756` is the shared application lifecycle. Reuse `_submit_application_internal`.
- `services/api/app/services/applications.py:773-805` is the anonymous service entry to replace on the active route.

Recommended shape:

- Add `async def submit_public_application_with_receipt(db, public_submission: PublicApplicationSubmission, *, receipt: DiscordIdentity) -> UUID` near `submit_public_application`.
- Validate `PublicApplicationSubmission`, resolve the real Discord member from `receipt.discord_user_id`, then build:
  - `ApplicationSubmission(applicant_id=member.id, scope=validated.scope, responses=validated.responses, client_application_id=validated.client_application_id)`
  - `ActorIdentity(actor_kind="user", actor_id=str(member.id))`
- Call `_submit_application_internal(..., request_surface=PUBLIC_SUBMIT_SURFACE, submission_authority=_SubmissionAuthority.USER)`.
- Return `created.read.id`, preserving the endpoint response shape.

Notification insertion point:

- Emit `application.public_submitted` after `_submit_application_internal` creates the application and before returning the UUID, but keep it inside the same audit context. `_submit_application_internal` currently creates a temporary context only around itself at `services/api/app/services/applications.py:604-612`; that context is gone after the call returns. The new entry should therefore wrap both `_submit_application_internal(...)` and `notification_events.emit(...)` in an outer `use_audit_context(_generated_audit_context())` when no context exists, or move the emit into `_submit_application_internal` after `read = _row_to_read(...)` at `services/api/app/services/applications.py:755`.

Conflicting systems:

- The legacy `submit_public_application()` generates `public:` client IDs when `client_application_id` is missing at `services/api/app/services/applications.py:777-780`. The new receipt-aware path should not create a synthetic member, but it can still preserve the generated `client_application_id` behavior if the public payload omits it. The SPA currently always sends a UUID from `services/web/src/main.tsx:128-134`.
- Existing duplicate-client-id behavior is scoped by `applicant_id` at `services/api/app/services/applications.py:642-649`; using real member IDs preserves that scope.

Deletion candidates:

- `submit_public_application()` at `services/api/app/services/applications.py:773-805` is the primary deletion candidate after the endpoint stops importing it.
- `PUBLIC_INTAKE_ACTOR`, `PUBLIC_INTAKE_MEMBER_SALT`, `PUBLIC_INTAKE_NAMESPACE`, and `_SubmissionAuthority.PUBLIC_INTAKE` at `services/api/app/services/applications.py:155-162` may also become unused if the old service entry and public-intake resolver are deleted. Verify with `rg` before deleting.

## Notification event hookpoints

Reusable hookpoints:

- `services/api/app/services/notification_events.py:32-84` is the internal event emission helper. It inserts `notification_events` and enqueues `notifications_materialize`.
- `services/api/app/contracts/notifications.py:103-108` defines `NotificationEventDraft`.
- `migrations/versions/wu-003c_notification_events.py:16-41` shows the event table supports `event_type`, correlation, scope, and JSON payload.
- `services/api/app/services/notifications_materialize.py:77-122` currently resolves only static `discord_user` and `discord_users` recipients. This supports A3 because the slice emits the event, not a DM.

Recommended shape:

- Import `NotificationEventDraft` and `notification_events.emit` into `services/api/app/services/applications.py`.
- Emit:
  - `event_type="application.public_submitted"`
  - `scope_kind=created.read.target_scope.scope_kind`
  - `scope_id=created.read.target_scope.scope_id`
  - payload keys `application_id`, `applicant_member_id`, `discord_user_id`
  - `payload_allowlist=frozenset({"application_id", "applicant_member_id", "discord_user_id"})`
- Use the same actor as the submit call: `ActorIdentity(actor_kind="user", actor_id=str(member.id))`.

Conflicting systems:

- `notification_events.emit()` raises `MissingCorrelationContextError` if no audit context is active at `services/api/app/services/notification_events.py:40-42`. The implementation must either emit inside an active audit context or wrap the new service in one.
- No current materializer rule resolves "recipient from event payload"; do not add DM materialization in this slice.

Deletion candidates:

- None. The notification system is reusable as-is.

## SPA gating hookpoints

Reusable hookpoints:

- `services/web/src/main.tsx:21-23` defines the `/auth/discord/me` response shape.
- `services/web/src/main.tsx:69-107` renders the application page. This is where the form should become conditional on verified receipt state.
- `services/web/src/main.tsx:94-95` currently renders the Login button and login state below the form.
- `services/web/src/main.tsx:137-195` binds application-route events.
- `services/web/src/main.tsx:150-152` already redirects the Login button to `/auth/discord/start?return_to=/applications`.
- `services/web/src/main.tsx:154-156` calls `/auth/discord/me` for advisory display only.
- `services/web/src/main.tsx:158-179` is the submit handler. Add the pre-submit `/auth/discord/me` re-check before building/posting the application payload.
- `services/web/src/main.tsx:172-176` is the active POST to `/api/public/applications`; keep the payload and do not add identity headers.
- `services/web/src/main.tsx:197-210` is the existing `/auth/discord/me` helper.

Recommended shape:

- Add an applicant-auth state helper that fetches `/auth/discord/me` with `Accept: application/json`.
- On `/applications` load:
  - If `/auth/discord/me` returns 200, render or enable the form and show verified state.
  - If 401, render the Login button only and hide or disable the form. The proposal says "render the Login button only"; implement that literally unless UX scope is revised.
- On submit:
  - Re-fetch `/auth/discord/me`.
  - If 401, preserve current draft values in `sessionStorage` and redirect to `/auth/discord/start?return_to=/applications`.
  - If 200, POST the existing payload to `/api/public/applications`.
  - If POST returns `401` with `code === "applicant_receipt_required"`, redirect to `/auth/discord/start?return_to=/applications`.
- Do not send `X-Discord-User-Id` or any redundant identity header.

Conflicting systems:

- The current markup renders the form before login at `services/web/src/main.tsx:79-92`. That conflicts with the required "Login button only" state and must be changed, not merely augmented with a warning message.
- Existing component test "application form still submits through the anonymous INIT-120 path" at `services/web/tests/compat.spec.ts:243-257` conflicts directly with the new contract.

Deletion candidates:

- Remove the anonymous submit branch in `services/web/tests/compat.spec.ts:243-257`.
- Remove or rewrite UI copy that says public intake remains available without login if it becomes misleading; `services/web/src/main.tsx:54` says public intake stays available, not explicitly anonymous, so it can remain if desired.

## Web fixture + component test hookpoints

Reusable hookpoints:

- `infra/tests/fixtures/web-ui/contract.json:22-35` owns auth fixture shape.
- `infra/tests/fixtures/web-ui/contract.json:52-78` owns submit contract shape.
- `infra/tests/test_web_ui_contract.py:28-47` validates the fixture's current anonymous submit contract.
- `infra/tests/test_web_ui_contract.py:56-68` asserts required strings in the Playwright spec.
- `infra/tests/test_web_ui_contract.py:80-89` asserts the shell validator covers the current public route.
- `services/web/tests/compat.spec.ts:88-127` is the current component test that submits without auth.
- `services/web/tests/compat.spec.ts:149-218` already has mocked `/auth/discord/me` and seeded-cookie fixtures from INIT-127.
- `services/web/tests/compat.spec.ts:220-240` already tests login start and identity display.

Fixture changes:

- Add a receipt/login contract section, for example:
  - `auth.applicant_me_endpoint = "/auth/discord/me"`
  - `auth.discord_start_endpoint = "/auth/discord/start?return_to=/applications"`
  - `auth.applicant_discord_user_id = "123456789012345678"`
  - `form.submit.requires_applicant_receipt = true`
  - `form.submit.missing_receipt_status = 401`
  - `form.submit.missing_receipt_code = "applicant_receipt_required"`
- Keep `form.submit.endpoint`, method, success status, response message, and payload fields unchanged.
- Add a negative assertion target that no redundant identity header is sent.

Component test changes:

- Rewrite `services/web/tests/compat.spec.ts:88-127` so the happy-path submit first satisfies `/auth/discord/me` with a cookie/route fixture.
- Rewrite `services/web/tests/compat.spec.ts:243-257` from "anonymous INIT-120 path" to "unauthenticated applicants are redirected to Discord login and do not POST".
- Extend `publicSubmitApi` at `services/web/tests/compat.spec.ts:173-198` to assert the request does not include `x-discord-user-id`.
- Add a route handler for POST returning structured `401` and assert redirect to `/auth/discord/start?return_to=/applications`.

Conflicting systems:

- `infra/tests/validate_web_ui_local.sh:111-116` validates only the old submit fields. It must learn the receipt-required fields or it can false-green on an anonymous contract.
- `infra/tests/test_web_ui_contract.py:56-68` should require new spec strings such as `applicant_receipt_required`, `/auth/discord/me`, and no identity header assertion.

New files:

- None required.

## e2e seeded-receipt hookpoints

Reusable hookpoints:

- `infra/tests/e2e/lib/playwright/browser-flow.mjs:7-13` reads required env vars. Add optional/required receipt seed env vars for `web-ui` flow.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:33-77` is the `web-ui` flow. Insert receipt seeding before `page.goto("https://web.local.humility.local/applications", ...)` at `browser-flow.mjs:38`.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:46-53` waits for the public submit response. Keep this because the endpoint path is unchanged.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs:71-74` writes the application id/correlation id record. Include the seeded `discord_user_id` in that JSON so the shell assertion can verify it.
- `infra/tests/e2e/lib/playwright/run-browser-flow.sh:17-22` already reads Authentik secrets with `kubectl`. Add reads for `APPLICANT_RECEIPT_SIGNING_KEY` and `APPLICANT_RECEIPT_TTL_SECONDS` from `Secret/server-manager-runtime`.
- `infra/tests/e2e/lib/playwright/run-browser-flow.sh:24-30` passes env into Node. Add `E2E_APPLICANT_RECEIPT_SIGNING_KEY`, `E2E_APPLICANT_RECEIPT_TTL_SECONDS`, and `E2E_APPLICANT_DISCORD_USER_ID`.
- `infra/tests/e2e/lib/playwright/package.json:8-10` has only Playwright. Use Node's built-in `crypto` for HS256 JWT signing; do not add a dependency.
- `infra/tests/e2e/tests/19-web-ui.sh:8-33` is the DB assertion to update.
- `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml:31-42` and `api-deployment.yaml:96-105` show the signing key and TTL already exist in the `server-manager-runtime` secret consumed by the API.

Recommended seeding mechanism:

- Prefer Playwright `context.addCookies()` with an HMAC-signed receipt computed in `browser-flow.mjs` from the same `APPLICANT_RECEIPT_SIGNING_KEY` that the API uses. This avoids adding a test-only production endpoint and keeps seeding confined to e2e tooling.
- Cookie parameters:
  - `name: "applicant_receipt"`
  - `value: <HS256 JWT with discord_user_id, iat, exp>`
  - `url: "https://web.local.humility.local/"`
  - `httpOnly: true`
  - `secure: true`
  - `sameSite: "Lax"`
  - `expires: now + ttl`
- Use a fixed test snowflake such as `123456789012345678`, passed as `E2E_APPLICANT_DISCORD_USER_ID`.

Shell assertion changes:

- `infra/tests/e2e/tests/19-web-ui.sh:23-26` should select `a.state, m.discord_user_id, m.kind`.
- Replace `[[ "$discord_user_id" == public:* ]]` at `infra/tests/e2e/tests/19-web-ui.sh:31` with:
  - `state == queued`
  - `kind == discord`
  - `discord_user_id == <seeded snowflake>`
- Update the pass message at `infra/tests/e2e/tests/19-web-ui.sh:32` from synthetic member to real Discord member.

Conflicting systems:

- A test-only API endpoint would touch production routing and create a new auth bypass surface. It is not needed.
- If the shell retrieves the signing key, ensure it does not echo the secret into logs. `run-browser-flow.sh` currently redirects Node output to the log at `run-browser-flow.sh:24-30`; do not print the key in Node.

New files:

- None required.

## Test surface hookpoints

`services/api/tests/test_public_application_route.py`:

- `test_public_route_accepts_valid_body_without_actor_headers` at `services/api/tests/test_public_application_route.py:43-76` should become "accepts valid body with valid applicant receipt and no actor headers". Add a valid cookie helper using `app.services.applicant_discord_auth.sign_applicant_receipt`.
- Add missing receipt, malformed receipt, tampered receipt, expired receipt, and wrong-key tests. These belong here because they assert route-level 401 body `{"code": "applicant_receipt_required", ...}` and no mutation.
- Keep `test_public_route_rejects_malformed_payload` at `services/api/tests/test_public_application_route.py:79-100`; decide whether validation or receipt runs first and set the test cookie accordingly to keep this focused on payload validation.
- Keep Cedar deny coverage at `services/api/tests/test_public_application_route.py:102-125`, but provide a valid receipt if the expected assertion remains 403.

`services/api/tests/test_public_intake_submit.py`:

- `test_public_submit_creates_queued_application_through_lifecycle` at `services/api/tests/test_public_intake_submit.py:36-71` currently asserts `public:` applicant and public-intake actor. Replace or add a new group for `submit_public_application_with_receipt` asserting:
  - queued application
  - `applicant_kind == "discord"`
  - expected snowflake
  - version remains 2
  - route review actor is the real member user actor
  - request surface remains `api:/api/v1/public/applications`
- `test_public_submit_without_client_id_uses_public_idempotency_namespace` at `services/api/tests/test_public_intake_submit.py:73-95` conflicts if it asserts synthetic namespace behavior for the active public submit. Either delete it with the old service or rewrite it to assert only generated client id behavior under the real member.
- `test_public_submit_stamps_audit_actions_with_public_intake_actor` at `services/api/tests/test_public_intake_submit.py:140-174` must be replaced with USER-authority audit assertions.
- Add resolver tests for create, reuse, concurrent same-snowflake calls, and kind-mismatch corruption. These can live in this file or a focused member service test if one exists.
- Add notification event assertions querying `notification_events` and deferred effects after valid receipt submit.

`services/api/tests/test_auth_discord_callback.py`:

- `test_callback_exchanges_code_validates_id_token_and_sets_receipt_cookie` at `services/api/tests/test_auth_discord_callback.py:341-380` should assert `cookie["path"] == "/"`.
- `test_me_returns_discord_user_id_from_valid_cookie` at `services/api/tests/test_auth_discord_callback.py:522-536` can remain.
- Add a cookie-jar/path test that obtains the callback-issued cookie and proves the jar sends it to `/auth/discord/me`. If a full callback-to-public-submit cookie-jar test is too heavy in this file because it needs DB/Cedar fixtures, cover submit cookie delivery in `test_public_application_route.py`.
- Existing helper tests at `services/api/tests/test_auth_discord_callback.py:461-510` already cover sign/verify/tamper/wrong-key/expired at the token-helper level; route tests still need to assert those map to `applicant_receipt_required`.

Shared fixtures:

- `services/api/tests/public_intake_fixtures.py:145-167` already fetches `applicant_kind` and `applicant_discord_user_id`; reuse it for real-member assertions.
- Add helpers to fetch notification events and count public-intake member rows if they do not already exist.

## Conflicting systems / deletion candidates

Conflicts:

- Active anonymous submit in `services/api/app/api/v1/endpoints/applications/public.py:31-34` conflicts with the approved receipt-required contract.
- Legacy anonymous service path in `services/api/app/services/applications.py:773-805` conflicts if it remains reachable from any route.
- Synthetic resolver `services/api/app/services/members.py:179-255` conflicts with "no new public_intake applicants" if used by new submit.
- `services/web/src/main.tsx:158-179` posts to `/api/public/applications` without checking `/auth/discord/me`.
- `services/web/tests/compat.spec.ts:243-257` explicitly protects the anonymous INIT-120 path.
- `infra/tests/e2e/tests/19-web-ui.sh:31` explicitly expects a `public:*` synthetic member.
- `infra/tests/fixtures/web-ui/contract.json:52-78` lacks any receipt-required/auth-gating fields.

Deletion candidates:

- Delete or make unreachable `submit_public_application()` in `services/api/app/services/applications.py:773-805`.
- Delete or make unreachable `resolve_or_create_public_intake_member()` in `services/api/app/services/members.py:179-255`.
- Delete old public-intake constants in `services/api/app/services/applications.py:155-157` if no references remain.
- Delete `_SubmissionAuthority.PUBLIC_INTAKE` at `services/api/app/services/applications.py:162` if no legacy submit path remains.
- Delete the anonymous Playwright component test at `services/web/tests/compat.spec.ts:243-257`.
- Delete the e2e synthetic-member assertion in `infra/tests/e2e/tests/19-web-ui.sh:31`.

Retained historical data:

- Existing `members.kind='public_intake'` rows and applications attached to them remain historical orphans. This slice should not link, convert, repoint, or delete them.

## New files required

- No production source files are required.
- No test files are required if the implementation updates the existing API, web, fixture, and e2e tests listed above.
- The only new file required by this Phase 5 task is this artifact: `research/16-receipt-required-submit-hookpoints.md`.

Optional but not recommended:

- A new public-auth module for the FastAPI dependency. Existing `services/api/app/services/applicant_discord_auth.py` is sufficient and keeps receipt behavior centralized.
- A test-only API endpoint to issue receipts. Prefer Playwright-injected signed cookies in e2e tooling to avoid adding an application auth bypass surface.

## Notable observations

- A1 is not contradicted. The existing HMAC verifier is strict about exact claim set, snowflake shape, signature, and expiry at `services/api/app/services/applicant_discord_auth.py:161-197`; no redundant identity header is needed.
- A2 is not contradicted, but it is the main implementation-risk point. The codebase currently preserves member aggregate/audit invariants through `mutate_entity`, not raw upserts. Phase 6a must pin the exact race-safe member creation strategy before code is written.
- A3 is not contradicted. `notification_events.emit()` only persists an internal event and deferred effect; current dynamic recipient limitations live in materialization, which remains BL-020.
- The public endpoint response shape can remain unchanged on success. The visible API contract change is only that unauthenticated/malformed receipts now return structured 401 before mutation.
- Dependency ordering should be made explicit in tests. To test Cedar denial, provide a valid receipt. To test receipt missing, allow Cedar.
- The e2e seeded-cookie approach is the least invasive because it uses already-existing API runtime secrets and avoids any new production endpoint.
- Cookie path widening to `/` is necessary for both `/auth/discord/me` and browser-visible `/api/public/applications`; path widening to `/api/v1/...` would not work because browser matching sees the pre-proxy path.
