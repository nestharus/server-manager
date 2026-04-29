READ:
- proposals/09-receipt-required-submit.md
- research/15-receipt-required-submit-problem-map.md
- .tmp/rca/member-conversion-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md
- proposals/08-applicant-discord-oauth.md
- plans/risk/init-127-supported-surface.md
- plans/risk/init-125a-supported-surface.md
- plans/audit-history/init-128-audit-history.md
- plans/BACKLOG.md
- services/api/app/api/v1/endpoints/auth_discord.py
- services/api/app/api/v1/endpoints/applications/public.py
- services/api/app/services/applicant_discord_auth.py
- services/api/app/services/applications.py
- services/api/app/services/members.py
- services/api/app/services/notification_events.py
- services/api/app/services/notifications_materialize.py
- services/api/app/contracts/notifications.py
- services/api/app/core/factory.py
- services/web/src/main.tsx

# INIT-128 Phase 4 — Supported-Surface Risk (Round 2)

## Inputs read

- `proposals/09-receipt-required-submit.md` — full revised proposal: scope (lines 39-47), anti-scope (49-60), implementation decisions (62-71), design (73-189), supported-surface track (191-220), assumption register A1–A3 (222-226), test-intent track TG-1..TG-14 (228-245), residual-risk artifact link (247-251), migration/rollback (253-274), out-of-scope follow-ups (276-281).
- `research/15-receipt-required-submit-problem-map.md` — approved Phase 2.5 problem map: touched surface (29-78), current supported paths (80-97), known brittle behavior including the cookie-path bug (99-129), adjacent surfaces in blast radius (135-160), public/user-reachable paths (162-187), deployment cohort (189-195), open questions (197-213).
- `.tmp/rca/member-conversion-FINDINGS.md` — RCA: anonymous-submit gap (43-47), forward-path member matching (61-78), receipt-to-submit binding (80-97), Option B locked recommendation (99-119), pre-BL-017 orphan stance (121-133), notification-event emit pattern (143-158), member_links not needed (160-170), e2e impact under Option B (172-186), Cedar unchanged (188-200), recommended file-level surface (202-217), suggested decomposition (219-231), test-intent surface (233-263).
- `~/ai/workflows/implementation-pipeline.md` — Phase 4 risk-gate rules and the supported-surface termination rule (line 106) requiring orthogonal evaluation: invalidated-assumption check first → return to research at Phase 2.5; otherwise non-positive-value check → terminate; otherwise NONE then proceed to LOW/MEDIUM/HIGH.
- `proposals/08-applicant-discord-oauth.md` — adjacent INIT-127 contract: separate `server-manager-applicant` Provider/Application, `identify` scope, server-side code exchange, HMAC-signed receipt with exactly `discord_user_id`/`iat`/`exp`, 10-min TTL, no INIT-120 contract change in BL-016.
- `plans/risk/init-127-supported-surface.md` — adjacent INIT-127 verdict (LOW); confirms that the receipt is HMAC-signed/HttpOnly/Secure/SameSite=Lax and that the SPA is intended to drive submit-time login (deferred to BL-009/BL-017 there, owned here).
- `plans/risk/init-125a-supported-surface.md` — adjacent INIT-125A verdict (LOW); confirms `members.kind` is now a typed schema column (`CHECK (kind IN ('discord','public_intake'))`) and that synthetic guards now read kind not prefix.
- `plans/audit-history/init-128-audit-history.md` — round 1 had `shortcut=MEDIUM` (e2e split contradiction); round 2 D5 locks "19-web-ui converted in this slice; no new spec; suite stays at 19".
- Cited evidence from current source: `services/api/app/api/v1/endpoints/auth_discord.py:36-85` (callback sets `applicant_receipt` cookie with `path="/applications"`, `secure=True`, `httponly=True`, `samesite="Lax"`, `max_age=settings.applicant_receipt_ttl_seconds`); `services/api/app/api/v1/endpoints/auth_discord.py:88-105` (`/auth/discord/me` reads cookie + `verify_applicant_receipt`); `services/api/app/api/v1/endpoints/applications/public.py:21-38` (current anonymous public submit, only `Depends(authorize_public_intake)`); `services/api/app/services/applications.py:298-307` (`_require_submit_authority` self-bypass requires `actor.actor_id == str(applicant_id)`); `services/api/app/services/members.py:115-176` (existing `create_or_get_member()` with `mutate_entity` + `UniqueViolation` recovery); `services/api/app/services/notification_events.py:32-84` (`emit()` inserts `notification_events` and enqueues `notifications_materialize` deferred effect under current audit context); `services/api/app/services/notifications_materialize.py:77-122` (recipient resolution supports static `discord_user`/`discord_users`, not payload-driven); `services/api/app/core/factory.py:73-81` (HTTPException dict detail flattens to top-level JSON object — confirms `{"code":"applicant_receipt_required","message":...}` shape); `services/web/src/main.tsx:140-179` (current SPA submit posts to `/api/public/applications` regardless of `/auth/discord/me`).

## Termination evaluation

Per `~/ai/workflows/implementation-pipeline.md:106`, evaluate orthogonal termination signals first, in this order: invalidated assumption that breaks the current problem framing → return to research and resume at Phase 2.5; otherwise non-positive value on the current supported surface → terminate; otherwise NONE.

### Invalidated-assumption check

I cross-checked each proposal assumption against current source.

- **A1** — HMAC receipt is sufficient auth proof without a redundant identity header. Verified: `services/api/app/services/applicant_discord_auth.py` (`sign_applicant_receipt` / `verify_applicant_receipt`) emits HS256 JWT with exactly `discord_user_id`, `iat`, `exp`; validates the snowflake shape; rejects extra claims; expires after the configured short TTL. Verified: `services/api/app/api/v1/endpoints/auth_discord.py:75-84` sets the cookie HttpOnly, Secure, SameSite=Lax, max-age from `applicant_receipt_ttl_seconds`. Verified: `services/api/app/core/factory.py:73-81` flattens dict `HTTPException.detail` to the top-level JSON object that the proposal's structured `{"code":"applicant_receipt_required",...}` body relies on. Invalidation observable: discovered receipt forgery against the production HMAC verifier; signing-key leakage; or a new product/security requirement for server-side receipt revocation before TTL (which would invalidate the no-revocation contract built into `applicant_discord_auth.verify_applicant_receipt`). None observed.
- **A2** — `INSERT ON CONFLICT DO NOTHING + SELECT` handles concurrent same-snowflake submits. Verified: `migrations/versions/wu-011_members.py:35-38` declares the `members.discord_user_id` unique constraint; `migrations/versions/wu-043_members_kind.py:15-31` constrains `members.kind` to `discord` or `public_intake` (INIT-125A is now landed and live per its supported-surface verdict and the recent `feat: INIT-125A (BL-008 sub-slice A) members.kind discriminator` commit). Invalidation observable: PostgreSQL uniqueness or `ON CONFLICT` semantics changing under us; another writer (e.g. a future migration tool or a test fixture path that bypasses the unique constraint). The proposal's TG-5 component test for the resolver and TG-6 corruption rejection cover the primary observable cases. None observed.
- **A3** — `application.public_submitted` can be emitted in this slice without DM materialization blocking. Verified: `services/api/app/services/notification_events.py:32-84` shows `emit()` inserts `notification_events` and enqueues a `notifications_materialize` deferred effect under the current audit context — both side effects happen inside the connection-bound block. Verified: `services/api/app/services/notifications_materialize.py:77-122` resolves only static `discord_user`/`discord_users` rule recipients today, with no payload-driven resolution; an event whose only intended downstream is a payload-addressed DM correctly materializes as `recipient_unresolved` rather than as a hard failure that would roll back the submit transaction. Invalidation observable: a future change that promotes "no matching rule resolution" from `recipient_unresolved` to a synchronous failure inside `emit()`; or a product requirement that the DM be delivered atomically with submit. The proposal explicitly defers DM materialization to BL-020 (depends on BL-019), and the audit history's D4 locks that decomposition. None observed.

The proposal's assumption register also explicitly names a concrete invalidation surface for each assumption (proposal lines 224-226), and the test-intent track wires TG-1/TG-2/TG-3/TG-9 to those invalidation surfaces.

No INVALIDATED_ASSUMPTION signal.

### Non-positive-value check

Existing-state risk on the supported surface is concrete, named in the problem map, and unaddressed today.

1. **Active anonymous-write surface.** `services/api/app/api/v1/endpoints/applications/public.py:21-38` accepts a `PublicApplicationSubmission` body with only Cedar route gate and creates/reuses a synthetic `members.kind='public_intake'` row whose `discord_user_id` starts with `public:`. Each new public submission persists synthetic identity even though the locked product direction (`plans/BACKLOG.md:262-280`) requires Discord OAuth before submitting.
2. **INIT-127 surface is plumbed but unused on the active path.** The OAuth callback issues a valid receipt and `/auth/discord/me` verifies it, but no submit code reads the receipt, the SPA's `/auth/discord/me` call is advisory display state (`services/web/src/main.tsx:140-179`), and the cookie path is `/applications` so a real browser would not even send the cookie to the submit endpoint at `/api/public/applications` (`research/15-receipt-required-submit-problem-map.md:101-105`). INIT-127 alone delivers no end-to-end identity binding without this slice.
3. **Cedar gate is the only authorization on the public submit route today.** Cedar answers "is the route enabled for this channel?" but cannot answer "who is submitting?" The receipt dependency is the missing trust boundary.

The proposal closes 1, 2, 3 in a single bounded slice:

- One endpoint dependency change (`services/api/app/api/v1/endpoints/applications/public.py`) adds the receipt verifier alongside the existing Cedar gate.
- One service-layer entry point (`submit_public_application_with_receipt`) replaces the anonymous service path on the active route while reusing the existing `_submit_application_internal(..., _SubmissionAuthority.USER)` lifecycle.
- One member helper (`resolve_or_create_real_discord_member`) builds on the unique `members.discord_user_id` constraint and the typed `members.kind` from INIT-125A.
- One cookie-path widening (`/applications` → `/`) fixes the latent INIT-127 cookie-delivery bug; the receipt is HttpOnly, Secure, SameSite=Lax, short-TTL, and HMAC-signed, so the additional same-origin reachability is bounded.
- One SPA gate adds the submit-time `/auth/discord/me` re-check and redirect.
- One notification event (`application.public_submitted`) emits an audit-traceable handoff for BL-020 without forcing DM materialization in scope.
- Zero schema migration; zero changes to the authenticated `POST /api/v1/applications` actor/header contract; zero Cedar policy edits; zero changes to officer Pomerium auth; zero member_links table; zero retroactive synthetic-to-real linking.

Rollback is code-only. Real Discord member rows created while the slice is live are legitimate `kind='discord'` members and stay valid after rollback; existing `kind='public_intake'` rows remain readable historical data and are explicitly assigned to BL-018.

The reduction in concrete current-state risk (anonymous public-write surface closes; identity-verified path opens; INIT-127 stops being a half-wired surface) clearly outweighs the additive blast radius (one endpoint dependency, one service entry point, one member helper, one cookie-path widening, one SPA submit-gate branch, one notification event) plus the migration/rollback burden (no schema changes, reversible code paths, e2e seeded-receipt update inside the existing 19-web-ui spec).

No NON_POSITIVE_VALUE signal.

Termination outcome: NONE. Proceed to LOW/MEDIUM/HIGH verdict.

## Existing-state risk reduction (anonymous-write surface closes; identity-verified path opens)

The proposal targets the exact gap the RCA names.

- **Anonymous-write surface closes on the active route.** `submit_public_application_endpoint()` adds `Depends(verify_applicant_receipt)` ahead of service entry; the existing anonymous `submit_public_application()` function remains in source as a rollback-only path, unreachable from the active endpoint, and explicitly assigned to BL-018 cleanup. Anti-scope (proposal lines 51-60) forbids retaining an anonymous submit path "including in the e2e suite", which closes the round-1 shortcut concern.
- **Identity-verified path opens on the same route.** The receipt is verified server-side via the existing HMAC verifier; the verified `discord_user_id` resolves to a real `members.kind='discord'` row; the resolver is constraint-backed by `members.discord_user_id` unique + `members.kind` CHECK from INIT-125A; the application is submitted with `_SubmissionAuthority.USER` and `actor=ActorIdentity("user", str(member.id))` so `_require_submit_authority` self-bypasses correctly (`services/api/app/services/applications.py:298-307`).
- **The latent INIT-127 cookie-path bug closes.** Today's callback sets `path="/applications"` (`services/api/app/api/v1/endpoints/auth_discord.py:80`); a real browser does not send that cookie to `/auth/discord/me` or `/api/public/applications`. The proposal widens to `/`, preserving HttpOnly, Secure, SameSite=Lax, and the short TTL. The security tradeoff is explicit (proposal lines 75-79): more same-origin paths receive the cookie, but the receipt is HMAC-signed and short-lived. The tradeoff is sound for a confidential identity-receipt cookie that is not script-readable.
- **Audit posture aligns with the user submit model.** Audit actions for application submit/route now record actor as the real applicant member UUID, not the legacy `public-intake` service actor. `request_surface` is `api:/api/v1/public/applications`. This makes pre-/post-INIT-128 audit rows distinguishable by actor id pattern (real UUID vs. service actor).
- **Notification handoff is added without scope creep.** `notification_events.emit()` is called after the application row exists (proposal lines 152-165); recipient resolution is encoded into the event payload (`discord_user_id`), and the materializer's current `recipient_unresolved` path correctly handles the absence of a matching rule until BL-020 lands the dynamic-recipient extension. This avoids forcing a DM materialization design into the identity-binding slice.
- **No new error code surface, no Cedar churn.** A single new structured 401 (`applicant_receipt_required`) joins the existing INIT-124/125A guard error code family. Cedar still owns the route gate; the receipt owns the per-applicant identity proof.

Fragility shifts from "anonymous public submit creates synthetic members with no durable applicant identity proof" to "receipt-required public submit creates real Discord members under the existing user-authority lifecycle, with the cookie-path bug fixed and the notification handoff defined".

Verdict on this dimension: **LOW**.

## Adjacent path safety

This is the dimension to scrutinize most closely because INIT-128 explicitly removes the active INIT-120 anonymous path. That is a real surface change, not a no-op.

Adjacent paths I checked:

- **INIT-127 OAuth surface.** `proposals/08-applicant-discord-oauth.md` ships `/auth/discord/start`, `/auth/discord/callback`, `/auth/discord/me`, plus the HMAC-signed `applicant_receipt` cookie. INIT-128 changes one attribute of that surface (cookie `path` from `/applications` to `/`) and adds one consumer (the receipt dependency on the public submit endpoint). Cookie attributes preserved: HttpOnly, Secure, SameSite=Lax, max-age, name. The Authentik/OIDC redesign and the receipt JWT shape are unchanged. INIT-127's existing `/auth/discord/me` test that passes an explicit `Cookie` header keeps passing; the new cookie-jar test (TG-3) is the additional integration that proves browser path delivery now actually works. **Net effect on INIT-127:** the slice fixes a latent INIT-127 bug rather than regressing it. Watch item: the broader cookie scope means `/auth/discord/me` and `/api/public/applications` both receive the cookie on every request, including pre-flight CORS or unrelated GETs, but the cookie is opaque/HttpOnly and the receiver only validates it where required. Safe for a same-origin SPA; bounded for a confidential receipt.

- **INIT-124 / INIT-125A synthetic-member boundary guards.** The new submit goes through `_submit_application_internal(..., _SubmissionAuthority.USER)` with a real `kind='discord'` member. The synthetic-applicant guard at `services/api/app/services/applications.py:324-336` calls `is_synthetic_member()` against the fetched member row; a real Discord row has `kind='discord'`, so the guard short-circuits without raising `applicant_synthetic_not_allowed`. The existing public-intake authority exception (the only path on which a synthetic `kind='public_intake'` member can submit) keeps working for the legacy rollback-only `submit_public_application()`. No new error code is introduced; the six shipped INIT-124 error codes (`applicant_synthetic_not_allowed`, etc.) are unchanged. INIT-125A's `members.kind` CHECK constraint is now load-bearing for the resolver: a row with `discord_user_id == <snowflake>` and `kind != 'discord'` is structurally impossible to create through the production `_insert_member()` path, and TG-6 documents the corruption-rejection contract for any out-of-band insert.

- **INIT-120 anonymous public submit path — REMOVAL.** This is a real surface change, not a refactor.
  - **Active behavior change:** `POST /api/v1/public/applications` and `POST /api/public/applications` (after nginx rewrite) now return structured `401 {"code":"applicant_receipt_required","message":...}` for missing/invalid/expired/tampered receipts, instead of `201 {"message":"Application received","application_id":...}`.
  - **Test contract change:** `services/api/tests/test_public_application_route.py`'s `test_public_route_accepts_valid_body_without_actor_headers` and `services/web/tests/compat.spec.ts`'s "application form still submits through the anonymous INIT-120 path" must be updated to assert the receipt-required behavior. The proposal's TG-1/TG-2/TG-12 cover these.
  - **E2E contract change:** `infra/tests/e2e/tests/19-web-ui.sh` plus `infra/tests/e2e/lib/playwright/browser-flow.mjs` are updated in this slice to seed a valid applicant receipt before submit and assert the persisted member is `kind='discord'` with the verified snowflake. Audit-history D5 locks "no new spec; suite stays at 19", which closes the round-1 shortcut MEDIUM (`init-128-audit-history.md:11-14, 28-29`) and removes the contradiction between "remove anon path" and "keep anon spec".
  - **External API consumers:** the public submit endpoint is browser-facing; there is no documented external API client for the anonymous path. The web shell is the only known consumer, and it is updated in the same slice.
  - **Pre-existing anonymous data:** `members.kind='public_intake'` rows remain readable historical data. They cannot be used for new public submissions because the active route now requires a receipt. BL-018 owns archival/cleanup. No migration deletes data.

- **Authenticated `POST /api/v1/applications` (officer/Discord-bot path).** Unchanged. `AUTHENTICATED_SUBMIT_SURFACE`, actor headers, grant lookup via `_require_submit_authority`, and Pomerium identity headers all keep working. The receipt dependency is scoped only to the public endpoint.

- **Cedar policy.** Unchanged. `Public::"web-intake.<channel>"` still gates `Action::"application:submit_public"` for the public route. The receipt verifies "which Discord user", which is orthogonal to Cedar's "is the route enabled". No new Cedar principal (`User::"discord:<snowflake>"`, `Applicant::"discord"`) is introduced; the proposal's `.tmp/rca/member-conversion-FINDINGS.md:188-200` evidence and the explicit anti-scope on Cedar policy edits both confirm.

- **Officer Pomerium OIDC and `/auth/...` ingress.** Unchanged. INIT-127 already established the `/auth/discord/*` ingress and the separate `server-manager-applicant` Authentik Provider/Application; INIT-128 only widens the cookie path, which is a per-cookie attribute and does not touch Pomerium routes, Authentik blueprints, or the officer OIDC client.

- **Notification materializer behavior.** The new `application.public_submitted` event type is unknown to current notification rules. The materializer's `_resolve_recipients()` returns `recipient_unresolved` when no matching rule exists; that is the documented behavior, not a hard failure. The event row still lands and the deferred effect still queues, which is the intended audit-traceable handoff for BL-020. Watch item: a future product change that requires the DM to be delivered synchronously inside submit would invalidate A3; explicitly noted in the assumption register.

- **Channel-template materialization.** Local first. Remote channels inherit the same route, cookie, and receipt contract through `gitops/channels/<channel>/...` material. The proposal explicitly forbids a local-only code path (proposal lines 191-194). The receipt signing key is per-channel via Infisical (BL-016 plumbing). No template churn.

- **Public-intake rate limits.** `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` and `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml` apply to `/api/public/applications`. INIT-128 does not change those ingresses; the route path is unchanged. Rate-limit rejection precedes receipt verification, which is the correct order (limit anonymous request volume before doing any cryptographic work). Adjacent path safe.

The INIT-120 removal is a real and intentional surface change. The proposal handles it honestly: anti-scope locks "no retained anonymous submit path, including in the e2e suite"; D5 locks the e2e to be converted in this slice; TG-12/TG-14 prove the contract change at the test layer; rollback restores anonymous behavior at the endpoint level without database cleanup.

Verdict on this dimension: **LOW**.

## Migration / rollback realism

Migration sequence (proposal lines 257-264):

1. Add tests for receipt-required API behavior, real member resolver, notification event emission, SPA gating, cookie path, and updated `19-web-ui`.
2. Widen `applicant_receipt` cookie path to `/`.
3. Add the receipt dependency and structured 401 code.
4. Add the real Discord member resolver with `ON CONFLICT DO NOTHING + SELECT`, preserving the aggregate_heads/audit invariant.
5. Add `submit_public_application_with_receipt(...)` and route the public endpoint through it.
6. Emit `application.public_submitted` after successful receipt submit.
7. Update SPA submit gating and web contract tests.
8. Update `19-web-ui.sh` and `browser-flow.mjs` to seed a valid applicant receipt before submit; keep the suite at 19 specs.

Strengths:

- Order is correct: tests precede production code (Phase 6 firstness), cookie-path fix lands before the dependency that depends on the cookie reaching submit, the dependency lands before the service entry point, the service entry point lands before the SPA flips its submit gate, and the e2e refactor lands last so the suite is consistent at every commit.
- The slice is **code-only** — no Alembic migration, no schema change, no data backfill. INIT-125A (now landed) carried the only `members.kind` schema work that this slice depends on. That makes the rollback trivially reversible.
- Rollback (proposal lines 266-274) walks the surface in reverse: SPA submit gating → endpoint dependency removal + revert to `submit_public_application()` → optional cookie-path revert → disable `application.public_submitted` emission → revert e2e seeding only if the slice is fully rolled back. Each step is an independent commit-revert and does not require coordinated deployment.
- Data created while the slice is live (`members.kind='discord'` rows + applications attached to them) is legitimate after rollback. The proposal explicitly states "Any real Discord member rows created while the slice was live may remain; they are valid real members and do not need rollback deletion" (proposal lines 213-214, 274). Rollback-data correctness is a real strength here.
- The cookie-path revert is conditional ("only if INIT-127 alone is being restored; otherwise keeping `/` is harmless"). That's correct: a `/`-scoped HttpOnly Secure SameSite=Lax cookie is safe to leave behind; reverting it would only re-introduce the latent INIT-127 cookie-delivery bug.

Watch items:

- **Resolver implementation choice (proposal lines 122-128).** The proposal locks the race posture (`ON CONFLICT DO NOTHING + SELECT`) and the kind-check semantics, but says Step 5 must "pick an implementation that preserves the aggregate_heads/audit invariant". Two implementation paths exist: (a) reuse `create_or_get_member()` which calls `mutate_entity()` and gets `member.create` audit + aggregate_heads for free but uses `UniqueViolation` recovery rather than `ON CONFLICT`; (b) write a new repo helper that does the `ON CONFLICT DO NOTHING + SELECT` and then explicitly creates the aggregate_heads row + audit action. Path (a) is simpler and matches existing convention but means the assumption-register A2 statement about `ON CONFLICT` is documenting a constraint rather than the actual SQL. Path (b) matches A2 literally but is more code surface. Step 6a should pick one explicitly and document why; the audit-gate / shortcut-gate may have an opinion. Not a blocker for supported-surface; it's an implementation-discipline question.
- **Cookie-path revert is a nuanced rollback.** The literal sequence (revert SPA → revert dependency → revert cookie path) restores INIT-127's pre-128 broken state for `/auth/discord/me` if the operator follows step 3. The proposal flags this; an operator should be guided by the conditional ("only if INIT-127 alone is being restored").
- **Pre-existing anonymous data.** `members.kind='public_intake'` rows and applications attached to them remain. The proposal explicitly assigns cleanup to BL-018. After rollback, anonymous submit creates new such rows again — this is the intended behavior, but it means rollback is "back to broken anonymous", not "back to a clean state". Acceptable because the alternative (data deletion on rollback) would itself be destructive.
- **The legacy `submit_public_application()` source remains in `services/api/app/services/applications.py` for rollback.** Per `~/ai/conventions/no-backwards-compatibility.md` (referenced from the implementation pipeline), retaining unreachable shim code is normally a violation. The proposal frames this as "rollback path, not active contract" and assigns its eventual removal to BL-018. This is a reasonable interpretation given the slice's rollback contract, but it is a watch item: BL-018 must own the actual deletion to avoid permanent dead code accumulation.

Verdict on this dimension: **LOW**.

## Observability

- **Structured 401 error code.** `applicant_receipt_required` is distinguishable from validation errors (422 with field-level detail), Cedar denials (403 from `authorize_public_intake`), and other auth failures. The factory exception handler (`services/api/app/core/factory.py:73-81`) flattens dict detail to the top-level JSON object, so consumers see `{"code":"applicant_receipt_required","message":...}` directly. SPA can branch on `code` deterministically (proposal lines 173-176).
- **Audit actions.** `application.submit` and `application.route` actions now record `actor_kind="user"`, `actor_id=str(member.id)` (real Discord member UUID), and `request_surface="api:/api/v1/public/applications"`. This matches the existing officer/user submit audit posture and makes pre-/post-INIT-128 submissions distinguishable in audit by actor identity pattern.
- **Notification events.** `notification_events` rows with `event_type="application.public_submitted"` provide an audit-traceable internal handoff for BL-020. Even when the materializer can't resolve a payload-driven recipient, the event row itself lands and the deferred-effect row lands; an operator can `SELECT * FROM notification_events WHERE event_type='application.public_submitted'` to count submits.
- **Member create observability.** The resolver creates a `member.create` audit action when a new real Discord member is provisioned. The current `create_or_get_member()` request surface is `api:/api/v1/members`; if Step 6a chooses path (a) above, that surface is what audit will record. If Step 6a chooses path (b), the proposal notes this could be narrowed to `api:/api/v1/public/applications:applicant-member`. Either is observable; the choice is implementation-discipline, not a supported-surface gap.
- **Existing logs for callback handler.** INIT-127 already established explicit log lines for state validation, token exchange, JWKS validation, missing claim, receipt issued, callback completed (`plans/risk/init-127-supported-surface.md:128-130`). INIT-128 does not modify those.
- **No new metrics/alerts subsystem.** Consistent with INIT-124/125A/127 posture. Local-first deployment cohort uses pod-scoped logs and direct DB inspection. Acceptable for the supported-surface track.

Verdict on this dimension: **LOW**.

## Channel-template parity

- **Local-first deployment mode.** Proposal lines 191-194: "Deployment mode: local first. Remote channels inherit the same route, cookie, Authentik, and submit contract through channel-template materialization; do not create a local-only code path."
- **Same component everywhere.** Per auto-memory `environment-agnostic-stack.md`: local IS a deployment target; same components run identically local + remote. INIT-128 introduces no `if local` or `if dev` branches in shared API code. The receipt dependency, the resolver, the service entry point, the SPA gate, and the notification event are channel-agnostic.
- **Channel-specific config.** Receipt signing key (`APPLICANT_RECEIPT_SIGNING_KEY`), applicant OIDC client id/secret, Authentik issuer/JWKS/token URLs, and Discord OAuth client id/secret are per-channel via Infisical from the BL-016/INIT-127 plumbing. No new per-channel config keys are added by INIT-128.
- **Cookie domain / scope.** The cookie path widens to `/`, which is per-cookie not per-channel. The cookie domain is implicit (request host), so the cookie is correctly scoped to each channel's web host without channel-specific configuration. Same-origin scope is preserved.
- **E2E surface.** `19-web-ui.sh` and `browser-flow.mjs` exercise the local channel; the receipt-seeding mechanism (test-helper endpoint or Playwright-injected test-mode HMAC cookie) needs to be channel-template-aware so remote channels can run the same e2e shape. Watch item: Step 6a should confirm the test-helper endpoint or the test-mode HMAC cookie is gated behind a config flag that remote channels can opt out of in production deployment. The proposal says "test-helper endpoint or Playwright-injected cookie with a test-mode HMAC key" without locking which; either choice can be channel-template-safe with explicit production gating.
- **Synthetic data** (`members.kind='public_intake'`) is per-channel; cleanup is BL-018's, not INIT-128's, and is consistent across channels.

Verdict on this dimension: **LOW**.

## LOW/MEDIUM/HIGH verdict

Existing-state risk reduction: **LOW**. Adjacent path safety: **LOW**. Migration / rollback realism: **LOW**. Observability: **LOW**. Channel-template parity: **LOW**.

Overall verdict: **LOW**.

## Assumption register cross-check

| ID | Statement | Evidence | Invalidation observable | Status |
|---|---|---|---|---|
| A1 | HMAC receipt is sufficient auth proof without a redundant identity header. | `services/api/app/services/applicant_discord_auth.py` (`sign_applicant_receipt` HS256 with exact `discord_user_id`/`iat`/`exp` claim set; `verify_applicant_receipt` validates signature, exact claims, snowflake shape, freshness); `services/api/app/api/v1/endpoints/auth_discord.py:75-84` (HttpOnly, Secure, SameSite=Lax, max_age from `applicant_receipt_ttl_seconds`); `services/api/app/core/factory.py:73-81` (flattened 401 dict body). | Discovered receipt forgery against the production HMAC verifier; signing-key leakage; or a new product/security requirement for server-side receipt revocation before TTL. | Cleared. Concrete evidence + observable invalidation. |
| A2 | `INSERT ON CONFLICT DO NOTHING + SELECT` handles the concurrent-submit race for the same Discord user. | `migrations/versions/wu-011_members.py:35-38` (`members.discord_user_id` unique constraint); `migrations/versions/wu-043_members_kind.py:15-31` (`members.kind` CHECK constraint, INIT-125A landed); `services/api/app/services/members.py:115-176` (existing `create_or_get_member()` proves the unique-constraint race posture works in practice via `UniqueViolation` recovery — equivalent semantics to `ON CONFLICT DO NOTHING + SELECT`). | PostgreSQL uniqueness or `ON CONFLICT` semantics changing under us; another writer bypassing the unique `discord_user_id` contract (e.g. a future migration or a fixture path that disables the constraint). | Cleared. Concrete evidence + observable invalidation. Implementation-discipline note: Step 6a should pick literal `ON CONFLICT` SQL or document that the existing `UniqueViolation` recovery is the equivalent satisfying A2. |
| A3 | `application.public_submitted` can be emitted in this slice without DM materialization blocking. | `services/api/app/services/notification_events.py:32-84` (`emit()` inserts `notification_events` and enqueues `notifications_materialize` deferred effect under current audit context); `services/api/app/services/notifications_materialize.py:77-122` (recipient resolution returns `recipient_unresolved` for unmatched rules — soft failure, not a hard rollback); `migrations/versions/wu-003c_notification_events.py:16-41` (event schema persists type/correlation/scope/payload JSON). | A future change that promotes `recipient_unresolved` into a synchronous failure inside `emit()`; or a product requirement that the DM be delivered atomically with submit (which would force BL-020 into scope). | Cleared. Concrete evidence + observable invalidation. BL-020 (dynamic-recipient materialization) explicitly owns the eventual DM. |

All three assumptions resolve at their cited locations. Each has an observable invalidation condition. None is contradicted by current source.

## Watch signals (not blocking, do not flip the verdict)

1. **Cookie-path widening (`/applications` → `/`).** Broader same-origin reachability for the receipt cookie. The cookie remains HttpOnly, Secure, SameSite=Lax, short-TTL, HMAC-signed. Safe; called out explicitly in the proposal's security tradeoff (lines 75-79). TG-3 covers cookie-jar delivery at the integration layer; the residual ("ASGI jar approximates browser path rules") is honestly named.
2. **Resolver implementation choice (Step 6a).** Path (a) `create_or_get_member()` reuse vs. path (b) new `ON CONFLICT` repo helper. Both satisfy A2; (a) is simpler and matches existing convention; (b) is more literal. Step 6a should pick and document. Audit/shortcut gates may want to opine.
3. **Legacy `submit_public_application()` retained for rollback.** Reasonable for the slice's rollback contract; BL-018 must own the eventual deletion to prevent dead-code accumulation. Anti-scope is clear that this function is unreachable from the active route.
4. **TG-6 corruption-rejection test may be unconstructible.** The combination of `members.discord_user_id` unique + `members.kind` CHECK makes a "real snowflake row with `kind != 'discord'`" structurally impossible to insert through the production path. The proposal acknowledges this: "If DB constraints make the row unconstructible, this becomes a documented non-applicability case" (TG-6 residual). Step 6b should explicitly emit the documented non-applicability reason in the Step 6b output index per the implementation-pipeline rule.
5. **e2e seeding mechanism (test-helper endpoint vs. Playwright-injected test-mode HMAC cookie).** Either is acceptable; the production-gating story matters for channel-template parity. Step 6a should pick and pin the production gate (e.g., test-helper endpoint registered only when `settings.app_env == "test"` or behind an explicit feature flag).
6. **`/auth/discord/me` SPA caching window.** The proposal caches verified state "for at most the configured receipt TTL" and re-fetches before submit. The SPA cache is advisory; the API receipt verifier remains the trust boundary. No verdict impact, but Step 6c should ensure the cache key includes the receipt TTL so a key rotation invalidates cached state correctly.
7. **Pre-existing `members.kind='public_intake'` rows remain readable.** Trust profile reads, active-signal lists, and roster reads continue to surface them. INIT-125A's residual; INIT-128 does not change it. BL-018 owns read-side hardening.

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
