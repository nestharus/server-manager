READ:
- `.tmp/rca/member-conversion-FINDINGS.md`
- `research/15-receipt-required-submit-problem-map.md`
- `proposals/08-applicant-discord-oauth.md`
- `proposals/02-public-application-intake.md`
- `proposals/06-members-kind.md`
- `plans/BACKLOG.md`
- `/home/nes/ai/workflows/implementation-pipeline.md`
- `services/api/app/api/v1/endpoints/auth_discord.py`
- `services/api/app/services/applicant_discord_auth.py`
- `services/api/app/api/v1/endpoints/applications/public.py`
- `services/api/app/services/applications.py`
- `services/api/app/services/members.py`
- `services/api/app/repositories/members.py`
- `services/api/app/services/notification_events.py`
- `services/api/app/services/notifications_materialize.py`
- `services/api/app/contracts/notifications.py`
- `services/web/src/main.tsx`
- `services/web/tests/compat.spec.ts`
- `infra/tests/e2e/lib/playwright/browser-flow.mjs`
- `infra/tests/e2e/tests/19-web-ui.sh`
- `migrations/versions/wu-011_members.py`
- `migrations/versions/wu-043_members_kind.py`

## Summary

Make public application submit receipt-required and bind every new public web submission to a real Discord member. The browser must first complete the INIT-127 applicant Discord OAuth flow, receive the HMAC-signed `applicant_receipt` cookie, and then submit `POST /api/public/applications`. The API verifies that cookie server-side, resolves or creates `members.kind='discord'` for the receipt's Discord snowflake, and submits through the existing application lifecycle with `_SubmissionAuthority.USER`.

This removes the active anonymous public submit behavior introduced by INIT-120. Synthetic `members.kind='public_intake'` rows that already exist remain historical orphans; this slice does not link, convert, or clean them.

## Net-value statement

This proposal has positive net value because it reduces a concrete current-state identity risk on the supported `/applications` surface: the public route currently accepts anonymous bodies, creates a synthetic public-intake member, and persists that synthetic row as `applications.applicant_id`, even though the product direction now requires Discord OAuth before submitting (`.tmp/rca/member-conversion-FINDINGS.md:43-47`, `plans/BACKLOG.md:262-280`). INIT-127 already added the Discord OAuth receipt surface, but submit does not read it and the SPA still posts directly to `/api/public/applications` (`.tmp/rca/member-conversion-FINDINGS.md:55-59`, `services/web/src/main.tsx:158-179`).

The added blast radius is limited to the applicant public web cohort, the public submit endpoint, real-member creation, SPA submit gating, and a new notification event. That migration burden is justified because it stops creating new synthetic applicants, uses existing application/audit lifecycle code, keeps Cedar's route gate unchanged, and leaves historical cleanup to BL-018.

## Scope

- Widen the applicant receipt cookie path in `services/api/app/api/v1/endpoints/auth_discord.py` so browser requests to both `/auth/discord/me` and `/api/public/applications` include it.
- Add a FastAPI dependency `verify_applicant_receipt(request) -> DiscordIdentity` that reads the `applicant_receipt` cookie, verifies it with the existing HMAC verifier, and returns structured `401` error code `applicant_receipt_required` for missing, invalid, tampered, or expired receipts.
- Change `POST /api/v1/public/applications` to require the receipt dependency while retaining the existing Cedar public-intake route authorization.
- Replace the active anonymous public-submit service path with `submit_public_application_with_receipt(...)`, resolving the receipt snowflake to a real `members.kind='discord'` row and calling the existing `_submit_application_internal(..., _SubmissionAuthority.USER)`.
- Add `resolve_or_create_real_discord_member(discord_user_id) -> Member` in `services/api/app/services/members.py`, backed by `INSERT ON CONFLICT DO NOTHING` plus a final `SELECT`.
- Emit notification event `application.public_submitted` with recipient `discord_user_id` and payload `application_id`.
- Update the SPA to check `/auth/discord/me` on `/applications`, cache verified receipt state for the cookie TTL, re-check before submit, and redirect unauthenticated users to `/auth/discord/start?return_to=/applications`.
- Add API, service, web component, and e2e tests for the receipt-required path.
- Update `19-web-ui.sh` and `browser-flow.mjs` to seed a valid applicant receipt before form submit and exercise the receipt-required e2e path; no new e2e spec is added, so the suite stays at 19 specs.

## Anti-scope

- No `member_links` table.
- No auto-conversion or application re-pointing for historical synthetic/public-intake orphans.
- No DM materialization or Discord send.
- No `members.kind` schema changes.
- No Cedar policy edits.
- No chapter channel config.
- No `X-Discord-User-Id` or other redundant identity header.
- No authenticated officer route behavior change.
- No retained anonymous submit path, including in the e2e suite.
- No private review channel, transcript, or in-product chapter management work.

## Implementation decisions taken in proposal

- Receipt-required submit: choose RCA Option B because it matches the product direction and stops new synthetic applicants instead of preserving two identity models (`.tmp/rca/member-conversion-FINDINGS.md:107-119`).
- Forward-path member binding: verify receipt, resolve or create `members.discord_user_id=<snowflake>` with `kind='discord'`, and use that member UUID as `applicant_id` because `_require_submit_authority()` self-authorizes only when `actor.actor_id == str(applicant_id)` (`services/api/app/services/applications.py:298-307`).
- No `member_links` table: historical synthetic submissions lack a durable ownership proof, so automatic synthetic-to-real linking would be dishonest (`.tmp/rca/member-conversion-FINDINGS.md:121-170`).
- Cookie path widened to `/`: the current callback sets `path="/applications"`, which does not cover `/auth/discord/me` or the browser-visible `/api/public/applications` submit path (`services/api/app/api/v1/endpoints/auth_discord.py:75-84`, `.tmp/rca/member-conversion-FINDINGS.md:97-98`).
- No `X-Discord-User-Id` redundancy: the HS256 receipt is the trust boundary; a browser-supplied duplicate identity header would add mismatch cases without improving trust.
- Notification event in this slice, DM materialization deferred: event emission can land in audit now, while the DM body/link depends on BL-019 chapter-channel/product-review config (`plans/BACKLOG.md:279-295`).
- E2E update: INIT-128 updates `19-web-ui.sh` and `browser-flow.mjs` to seed a valid applicant receipt before the form submit step, using the new `/api/v1/auth/discord/test-helper-issue-receipt` endpoint or a Playwright-injected cookie with a test-mode HMAC key. The submit step now exercises the receipt-required path. No new e2e spec is added; the suite stays at 19 specs.
- SPA receipt state caching: `/applications` reads `/auth/discord/me` on load, caches the verified state only for the receipt TTL, and re-fetches before submit because SPA state is advisory and the API remains authoritative.

## Design

### Cookie path widening

In `discord_auth_callback()`, change the `response.set_cookie("applicant_receipt", ...)` path from `"/applications"` to `"/"` while preserving `HttpOnly`, `Secure`, `SameSite=Lax`, and the settings-driven `max_age` (`services/api/app/api/v1/endpoints/auth_discord.py:75-84`). The broader path is acceptable here because the cookie is not readable by JavaScript, is sent only over HTTPS, is same-site constrained for ordinary cross-site POSTs, has a 10-minute default TTL, and carries only an HMAC-signed Discord snowflake receipt (`services/api/app/services/applicant_discord_auth.py:142-158`, `services/api/tests/test_auth_discord_callback.py:513-519`).

The security tradeoff is explicit: more same-origin request paths receive the cookie, but the receipt cannot be modified or forged without the signing key and the submit endpoint still verifies it server-side before trusting it. Path widening is required because browser cookie path matching happens before nginx rewrites `/api/public/applications` to API `/api/v1/public/applications` (`containers/server-manager/nginx-web.conf:8-20`).

### FastAPI receipt dependency

Add a dependency named `verify_applicant_receipt(request) -> DiscordIdentity`. To avoid name confusion with `app.services.applicant_discord_auth.verify_applicant_receipt()`, the endpoint dependency may live in `public.py` or a small shared public-auth module and call the service verifier by module-qualified name.

Contract:

```python
class DiscordIdentity(BaseModel):
    discord_user_id: str

def verify_applicant_receipt(request: Request) -> DiscordIdentity:
    ...
```

Behavior:

- Read `request.cookies.get("applicant_receipt")`.
- On missing cookie, invalid JWT, tampered signature, wrong signing key, expired receipt, future `iat`, wrong claims, or non-snowflake value, raise `HTTPException(status_code=401, detail={"code": "applicant_receipt_required", "message": "Discord login receipt is required to submit an application."})`.
- On success, return `DiscordIdentity(discord_user_id=payload["discord_user_id"])`.

The factory exception handler already maps dict `HTTPException.detail` to a top-level JSON object, so the expected response body is `{"code": "applicant_receipt_required", "message": ...}` rather than `{"detail": {...}}` (`services/api/app/core/factory.py:73-81`).

### Public submit endpoint

Update `services/api/app/api/v1/endpoints/applications/public.py`:

- Keep `PublicApplicationSubmission` and `PublicApplicationSubmissionReceipt`.
- Keep `Depends(authorize_public_intake)` because Cedar still gates whether the public submit route is enabled for this channel.
- Add `identity: DiscordIdentity = Depends(verify_applicant_receipt)`.
- Call `submit_public_application_with_receipt(db, body, receipt=identity)` instead of `submit_public_application(db, body)`.
- Keep the success response shape as `{"message": "Application received", "application_id": ...}`.
- Remove the anonymous happy path from the active endpoint. Missing/invalid receipt returns the structured `401`; it must not create a member, application, audit action, or notification event.

Current endpoint behavior accepts the body with only Cedar auth and calls `submit_public_application()` (`services/api/app/api/v1/endpoints/applications/public.py:21-38`). That becomes the rollback path, not the active contract.

### Real Discord member resolver

Add `resolve_or_create_real_discord_member(db, discord_user_id) -> MemberRead` in `services/api/app/services/members.py`.

The helper must:

- Validate the Discord snowflake with the same shape as the receipt verifier.
- `SELECT` by `discord_user_id` first.
- If a row exists with `kind == "discord"`, return it.
- If a row exists with any other kind, fail as data corruption rather than silently treating a synthetic row as real.
- If absent, insert a real Discord member using `kind='discord'`, `status='active'`, and `joined_at=now`.
- Use `INSERT INTO members (...) VALUES (...) ON CONFLICT (discord_user_id) DO NOTHING`, then `SELECT` by `discord_user_id`.
- Ensure the selected row has a corresponding member aggregate head/version. Current member reads join `members` to `aggregate_heads` (`services/api/app/repositories/members.py:10-23`), and current creation uses `mutate_entity()` to create the aggregate head plus audit action (`services/api/app/services/members.py:115-176`, `services/api/app/services/mutations.py:97-185`). The Step 5 hookpoint must pick an implementation that preserves that invariant while still using the locked `ON CONFLICT DO NOTHING + SELECT` race posture.

The existing `members.discord_user_id` uniqueness constraint is the race boundary (`migrations/versions/wu-011_members.py:35-38`), and `members.kind` is already constrained to `discord` or `public_intake` (`migrations/versions/wu-043_members_kind.py:15-31`).

### Receipt-aware application submit service

Add `submit_public_application_with_receipt(db, public_submission, receipt) -> ApplicationReceipt` in `services/api/app/services/applications.py`. The existing public receipt contract is `PublicApplicationSubmissionReceipt`; the service may return an internal result with the application UUID, but the endpoint response remains unchanged.

Flow:

1. Validate `PublicApplicationSubmission`.
2. Resolve the real Discord member with `resolve_or_create_real_discord_member(receipt.discord_user_id)`.
3. Build `ApplicationSubmission(applicant_id=member.id, scope=validated.scope, responses=validated.responses, client_application_id=validated.client_application_id)`.
4. Call `_submit_application_internal(...)` with:
   - `actor=ActorIdentity(actor_kind="user", actor_id=str(member.id))`
   - `request_surface="api:/api/v1/public/applications"`
   - `submission_authority=_SubmissionAuthority.USER`
5. Return the created application id.

Using the member UUID as actor id is required. The existing user submit authority check bypasses grant lookup only for the applicant's own member UUID; using the Discord snowflake would fall through to authority grants and reject a legitimate self-submit (`services/api/app/services/applications.py:298-315`).

The new service must not call `resolve_or_create_public_intake_member()` and must not derive a `public:<hash>` id. The old `submit_public_application()` can remain only if it is unreachable from active routes and explicitly treated as BL-018 legacy/e2e cleanup surface.

### Notification event

Emit `application.public_submitted` from the new submit entry after the application row exists and within the same audit context as application submit/route. Payload allowlist:

```json
{
  "application_id": "<uuid>",
  "applicant_member_id": "<uuid>",
  "discord_user_id": "<snowflake>"
}
```

Set recipient semantics in the event payload, not by sending a Discord DM. The event draft should carry `event_type="application.public_submitted"`, `scope_kind` and `scope_id` from the application target scope, and payload containing `discord_user_id` as the downstream recipient. `notification_events.emit()` already inserts `notification_events` and queues a `notifications_materialize` deferred effect under the current audit context (`services/api/app/services/notification_events.py:32-84`). `notification_events` persist event type, correlation, scope, and JSON payload (`migrations/versions/wu-003c_notification_events.py:16-41`).

DM materialization is deferred because the current materializer resolves static `discord_user` / `discord_users` rule recipients and does not resolve "recipient comes from event payload" (`services/api/app/services/notifications_materialize.py:77-122`). BL-020 owns that dynamic recipient/materialization work once BL-019 defines the primary guild channel/product link.

### SPA changes

Update `services/web/src/main.tsx`:

- On `/applications` page load, call `/auth/discord/me` and cache `{discord_user_id, verified_at, expires_at}` in memory or session storage for at most the configured receipt TTL.
- The UI may display verified login state, but it must not rely on display state as authorization.
- On submit, re-fetch `/auth/discord/me` before posting the application.
- If `/auth/discord/me` returns `401`, preserve the draft fields and redirect to `/auth/discord/start?return_to=/applications`.
- If verified, POST the existing public application payload to `/api/public/applications`; do not add `X-Discord-User-Id`.
- If POST returns structured `401` with code `applicant_receipt_required`, redirect to `/auth/discord/start?return_to=/applications`.

Current SPA code already has a login button and calls `/auth/discord/me` for display, but submit does not check that state before posting (`services/web/src/main.tsx:150-179`, `services/web/src/main.tsx:197-210`). This slice changes that from advisory to submit-gating.

### Test surface

Tests must prove:

- Valid receipt submits, creates or reuses `members.kind='discord'`, persists a queued application, and does not create a new `public_intake` member.
- Missing, expired, tampered, malformed, and wrong-key receipts return structured `401` with `code="applicant_receipt_required"` and create no rows.
- Cookie path is `/`, and a browser/ASGI cookie jar sends the callback-issued cookie to both `/auth/discord/me` and `/api/public/applications`.
- Notification event `application.public_submitted` is emitted with `discord_user_id` and `application_id`.
- SPA submit gates on `/auth/discord/me`, redirects unauthenticated applicants, and never sends redundant identity headers.
- `19-web-ui` seeds a valid applicant receipt before submit, then covers receipt cookie to submit and verifies persisted member `kind='discord'` with the expected snowflake.

## Supported-surface track

Deployment mode: local first. Remote channels inherit the same route, cookie, Authentik, and submit contract through channel-template materialization; do not create a local-only code path.

Cohort: web applicants submitting through `/applications`. Officers, protected admin APIs, Pomerium officer auth, and authenticated officer review paths are unaffected.

Adjacent paths:

- INIT-127 OAuth surface: no Authentik/OIDC redesign. `/auth/discord/start`, `/auth/discord/callback`, and `/auth/discord/me` stay the identity proof surface; this slice only fixes cookie path and consumes the receipt on submit.
- INIT-124/125A boundary guards: still apply. The new submit goes through the existing USER authority path with a real `kind='discord'` member, so `applicant_synthetic_not_allowed` does not fire.
- INIT-120 anonymous path: removed from active public submit and from the e2e suite; all supported submit coverage requires a receipt.
- Cedar policy: unchanged. The `Public::"web-intake.<channel>"` route gate remains responsible for enabling the public submit route; receipt verification answers which Discord user is submitting (`.tmp/rca/member-conversion-FINDINGS.md:188-200`).

Blast-radius for unchanged adjacent paths:

- Authenticated `POST /api/v1/applications` continues to require actor headers and use `AUTHENTICATED_SUBMIT_SURFACE`; this slice does not modify the protected endpoint contract.
- Existing `members.kind='public_intake'` rows remain readable historical data but cannot be used for new public submissions.
- Notification materialization/delivery workers may see a new event type but are not required to send a DM in this slice.
- Direct Discord-visible writes remain absent; event emission is an internal API/database effect.

Migration / rollback in this track:

- Migration is code/config only: cookie path, endpoint dependency, service path, SPA gating, tests. No schema migration.
- Rollback reverts SPA gating and removes the endpoint receipt dependency/call to the new service, restoring the previous anonymous `submit_public_application()` route behavior. Any real Discord member rows created while the slice was live may remain; they are valid real members and do not need rollback deletion.

Observability:

- Structured 401 error code `applicant_receipt_required` distinguishes missing/invalid applicant receipt from validation and Cedar failures.
- Audit actions for application submit/route use the real applicant member actor and the public submit request surface.
- `notification_events` rows with `event_type='application.public_submitted'` provide an audit-traceable internal handoff for BL-020.

## Assumption register

- A1: HMAC receipt is sufficient auth proof without a redundant identity header. Evidence: receipts are HS256 JWTs with exactly `discord_user_id`, `iat`, and `exp`, validate the snowflake shape, reject extra claims, and expire after the configured short TTL (`services/api/app/services/applicant_discord_auth.py:142-197`); the callback sets the cookie HttpOnly, Secure, SameSite=Lax, and max-age from the receipt TTL (`services/api/app/api/v1/endpoints/auth_discord.py:75-84`). Invalidated by discovered receipt forgery, signing-key leakage, or a requirement for server-side receipt revocation before TTL.
- A2: `INSERT ON CONFLICT DO NOTHING` handles the concurrent-submit race for the same Discord user. Evidence: `members.discord_user_id` has a unique constraint (`migrations/versions/wu-011_members.py:35-38`), and `members.kind` lets the resolver distinguish real Discord rows from public-intake rows (`migrations/versions/wu-043_members_kind.py:15-31`). Invalidated by PostgreSQL uniqueness or `ON CONFLICT` semantics changing, or by another production writer bypassing the unique `discord_user_id` contract.
- A3: Notification event `application.public_submitted` can be emitted in this slice without DM materialization blocking. Evidence: `notification_events.emit()` inserts a notification event under current audit context and enqueues `notifications_materialize` (`services/api/app/services/notification_events.py:32-84`), while the event schema stores type, correlation, scope, and payload JSON (`migrations/versions/wu-003c_notification_events.py:16-41`). Invalidated if notification materialization becomes required for the event itself to land in audit or if event rows without a matching materialization rule are treated as failed submissions.

## Test-intent track

| Test / group | Change or verification risk | Intended behavior / acceptance condition | Selected level | Fixture source or fixture application point | Assumption link | Expected observable signal | Residual risk |
|---|---|---|---|---|---|---|---|
| TG-1 Receipt dependency rejects missing receipt | Public submit remains anonymously writable | `POST /api/v1/public/applications` without `applicant_receipt` returns `401` body code `applicant_receipt_required`; no member, application, audit action, or notification event is created | particular-integration | `services/api/tests/test_public_application_route.py` with `public_intake_fixtures.py` payload/form fixtures and fake Cedar allow | A1 | HTTP 401, exact code, DB counts unchanged for members/applications/notification_events | Does not prove browser redirect; SPA tests cover UX |
| TG-2 Receipt dependency rejects invalid receipts | Tampered, expired, malformed, or wrong-key receipts are accepted | Each invalid receipt class returns `401` with code `applicant_receipt_required` before service mutation | particular-integration | API route test using receipt helper fixtures from `services/api/tests/test_auth_discord_callback.py` patterns | A1 | Parametrized invalid receipt cases all 401; no persisted rows | Does not prove future revocation because receipts are TTL-only |
| TG-3 Cookie path delivery | Callback cookie is scoped too narrowly for `/auth/discord/me` and submit | Callback sets `Path=/`; a real cookie jar sends `applicant_receipt` to `/auth/discord/me` and `/api/public/applications` | particular-integration | ASGI/httpx cookie-jar test around `/auth/discord/callback`, `/auth/discord/me`, and public submit route; callback uses mock Authentik fixture | A1 | Set-Cookie includes `Path=/`; subsequent requests succeed without manual `Cookie` header | ASGI jar approximates browser path rules but does not prove every browser quirk |
| TG-4 Valid receipt creates real member | New public submit still creates `public_intake` synthetic members | Valid receipt with no existing member creates one `members.kind='discord'` row for the receipt snowflake, queues application, and creates no `public:%` applicant | component | `services/api/tests/test_public_intake_submit.py` with seeded global form and fresh receipt identity | A1, A2 | Application row joins to `members.kind='discord'` and expected snowflake; state `queued`; version follows existing submit lifecycle | Does not prove full web/OAuth flow |
| TG-5 Valid receipt reuses real member and handles race | Concurrent submits create duplicate member rows or fail intermittently | Existing `kind='discord'` member is reused; concurrent same-snowflake resolver calls converge on one member via `ON CONFLICT DO NOTHING + SELECT` | component | Service-level member resolver tests with dedicated DB fixture and two concurrent calls | A2 | One member row for snowflake; both calls return same member id and `kind='discord'` | Bounded concurrency test cannot prove all scheduler interleavings |
| TG-6 Non-discord row collision rejected | Resolver silently reuses a non-real row | If a row with the receipt snowflake exists but `kind != 'discord'`, resolver fails with a corruption error and submit does not proceed | component | Direct DB fixture inserts a deliberately invalid/corrupt non-discord row if the constraint permits, or repository monkeypatch if not constructible | A2 | Expected service error; no application created | If DB constraints make the row unconstructible, this becomes a documented non-applicability case |
| TG-7 USER authority and audit posture | Receipt submit uses Discord snowflake actor or public-intake service actor | Receipt submit calls `_submit_application_internal` with `ActorIdentity(user, <member_uuid>)`, `_SubmissionAuthority.USER`, public submit surface, and accepted application submit/route audit rows | component | Application service test querying `activity_actions` and `application_reviews` using `public_intake_fixtures.py` helpers | A1 | Audit rows actor_kind `user`, actor_id real member UUID, request_surface `api:/api/v1/public/applications`; route review uses same actor | Does not verify external audit log shipping |
| TG-8 Duplicate client id scoped to real applicant | Idempotency changes scope or leaks across applicants | Same real applicant plus same `client_application_id` gets existing duplicate behavior; different Discord member with same client id can submit independently | component | Application service tests with two receipt identities and seeded global form | A2 | Duplicate response/error for same member; separate application for different member | Does not address historical synthetic duplicate conflicts, owned by BL-018 |
| TG-9 Notification event emitted | Submit succeeds but downstream notification/audit handoff is missing | Valid receipt submit emits exactly one `application.public_submitted` event with `application_id`, `applicant_member_id`, and `discord_user_id` payload, under the submit correlation | component | DB-backed service test querying `notification_events` and deferred effects after receipt submit | A3 | One event row, payload keys present, deferred `notifications_materialize` effect queued | Does not prove DM envelope delivery; BL-020 owns materialization |
| TG-10 SPA unauthenticated gate | Browser submits anonymously before OAuth | `/applications` submit re-fetches `/auth/discord/me`; when it returns 401, SPA preserves draft and redirects to `/auth/discord/start?return_to=/applications` without POSTing submit | component | `services/web/tests/compat.spec.ts` Playwright component test with route mocks | A1 | No request to `/api/public/applications`; URL matches auth start; draft restoration assertion passes if implemented | Does not prove live Authentik |
| TG-11 SPA verified submit | SPA sends redundant identity header or skips re-check | With verified `/auth/discord/me`, submit posts existing payload to `/api/public/applications`, sends cookies implicitly, and does not send `X-Discord-User-Id` | component | Playwright component test with mocked `/auth/discord/me` and submit route inspecting headers/body | A1 | Submit route receives expected payload and no redundant header; success message renders | Route mocks do not prove server receipt verification |
| TG-12 Web contract update | Fixture still encodes anonymous INIT-120 behavior | Web contract and tests name receipt-required/OAuth gating and remove active "anonymous submit succeeds" assertion from component coverage | particular-integration | `infra/tests/fixtures/web-ui/contract.json`, `infra/tests/test_web_ui_contract.py`, `services/web/tests/compat.spec.ts` | A1 | Static and component tests fail if anonymous success remains the active contract | E2E coverage is also receipt-required through `19-web-ui` |
| TG-13 Updated e2e receipt submit | Local browser flow does not cover receipt cookie to submit | `19-web-ui` obtains a valid applicant receipt through a test-helper endpoint or Playwright-injected test-mode HMAC cookie, submits, and verifies persisted member `kind='discord'` with expected snowflake | end-to-end | Existing `infra/tests/e2e/tests/19-web-ui.sh` and `infra/tests/e2e/lib/playwright/browser-flow.mjs` | A1, A2 | E2E record contains application id; DB join shows queued application and real Discord member; suite count remains 19 specs | External Discord OAuth is not exercised; deterministic receipt seeding covers the submit contract |
| TG-14 Receipt-required submit e2e | Receipt-required submit e2e regresses to anonymous success | `19-web-ui` fails unless a valid applicant receipt is seeded before form submit and the active submit path rejects anonymous operation | end-to-end | Existing `infra/tests/e2e/tests/19-web-ui.sh` and browser-flow target | A1 | CI/e2e output identifies receipt-required submit coverage, and no e2e spec asserts anonymous submit success | Does not clean historical synthetic rows; BL-018 owns data cleanup |

### Residual-risk artifact

`plans/risk/init-128-test-residuals.md`

If Step 6b cannot verify any named test-intent risk above, it must emit `plans/risk/init-128-test-residuals.md`. Each residual entry must include residual class, technique attempted or considered, scope, budget or bound, result, remaining residual, invalidating inputs, and whether the residual changes the net-value case, matching the implementation pipeline residual rule (`/home/nes/ai/workflows/implementation-pipeline.md:163-167`).

## Migration / rollback

Migration:

1. Add tests for receipt-required API behavior, real member resolver, notification event emission, SPA gating, cookie path, and updated `19-web-ui`.
2. Widen `applicant_receipt` cookie path to `/`.
3. Add the receipt dependency and structured 401 code.
4. Add the real Discord member resolver with `ON CONFLICT DO NOTHING + SELECT` and aggregate/audit invariants preserved.
5. Add `submit_public_application_with_receipt(...)` and route the public endpoint through it.
6. Emit `application.public_submitted` after successful receipt submit.
7. Update SPA submit gating and web contract tests.
8. Update `19-web-ui.sh` and `browser-flow.mjs` to seed a valid applicant receipt before submit; keep the e2e suite at 19 specs.

Rollback:

1. Revert SPA submit gating to the prior direct POST behavior.
2. Remove the public endpoint receipt dependency and call `submit_public_application()` again.
3. Revert cookie path to `/applications` only if INIT-127 alone is being restored; otherwise keeping `/` is harmless but no longer required by submit.
4. Disable `application.public_submitted` emission from the public submit service.
5. Revert the `19-web-ui` receipt-seeding update only if the receipt-required submit slice is fully rolled back.

Rollback does not require database deletion. Any `members.kind='discord'` rows created while the slice was active are valid real member rows. Any applications submitted while the slice was active remain correctly attached to those real members.

## Out of scope for follow-up

- BL-018 historical synthetic cleanup: report, archive, or clean old `public_intake` orphan rows and any read-side residuals.
- BL-019 in-product chapter management: review channels, officer/application-manager role assignment, claim UI, private reviewer-applicant channels, transcript persistence, and product links.
- BL-020 (new) applicant DM materialization: materialize and deliver the applicant DM once BL-019 defines the channel/link configuration.
- BL-009 Discord-side queue embed in the review channel: officer-facing queue notification and chapter role mentions, also dependent on BL-019.
