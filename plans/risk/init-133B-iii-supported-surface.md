# INIT-133B-iii — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre (post-β-i / post-β-ii) | Post (β-iii) | Risk |
|---|---|---|---|
| `GET /api/v1/me` | β-i `{subject, email, display_name, provider, groups, discord_user_id}` | unchanged | none |
| `GET /api/v1/web/admin/chapters` | unchanged | unchanged | none |
| `GET /api/v1/web/officer/applications` | β-i list endpoint | unchanged | none |
| `GET /api/v1/web/officer/applications/{id}` | β-ii read-only detail bridge | unchanged | none |
| `GET /api/v1/web/officer/applications/{id}/transcript` | β-ii read-only transcript bridge | unchanged | none |
| `POST /api/v1/web/officer/applications/{id}/claim` | β-i claim endpoint (`If-Match` strong, ETag set, `application.claim`) | unchanged | none |
| `POST /api/v1/web/officer/applications/{id}/messages` | n/a | **new** — async bridge: `_build_officer_actor` → `append_application_message` with server-side author fields. Browser body: `{body_markdown, visibility, client_message_id}`. Returns `ApplicationMessageRead`; status 201 created / 200 duplicate (preserves direct endpoint idempotency at `services/api/app/api/v1/endpoints/applications/messages.py:49-76`). 401/403/404/422/5xx via `raise_known_application_error`. | additive — new path under existing `/api/v1/web/officer/...` |
| `POST /api/v1/web/officer/applications/{id}/transitions` | n/a | **new** — async bridge: `parse_if_match_strong(request)` → `_build_officer_actor` → `transition_application(...)` → `set_etag(response, result.etag)`. Browser body: `ApplicationTransitionRequest`. Returns `ApplicationRead`. 200/401/403/404/409/412/422/428/5xx; bridge restricts the `action` enum to `{review, request_interview, waitlist, approve, deny, reactivate, withdraw}` (returning 422 `validation_error` for `claim`, `route`, `reassign`). | additive — new path under existing `/api/v1/web/officer/...` |
| `POST /api/v1/applications/{id}/messages` (INIT-131) | unchanged | unchanged | none — message bridge calls `append_application_message` as a Python service function, not via HTTP self-call (proposal §4 "Bridge service calls and direct endpoints wrapped") |
| `POST /api/v1/applications/{id}/transitions` (direct lifecycle) | unchanged | unchanged | none — transition bridge calls `transition_application(...)` as a Python service function, not via HTTP self-call (proposal §4 "Bridge service calls and direct endpoints wrapped") |
| `GET /api/v1/applications/{id}` / `GET /api/v1/applications/{id}/transcript` (direct lifecycle, transcript) | unchanged | unchanged | none |
| `GET /api/v1/applications` (INIT-133A) / `POST /api/v1/applications` | unchanged | unchanged | none |
| `POST /api/v1/public/applications` | unchanged | unchanged | none — applicant submit untouched |
| `GET /auth/discord/me` / `GET /auth/discord/start` / `GET /auth/discord/callback` | unchanged | unchanged | none — applicant Discord OAuth path stays public; β-iii adds nothing on `/auth/discord/*` |

The two new bridge routes preserve the β-i / β-ii bridge shape:

- Both `async def`. The transition bridge calls `parse_if_match_strong(request)` (same helper β-i claim already uses at `services/api/app/api/v1/endpoints/web.py:208`) before `_build_officer_actor`; the message bridge has no `If-Match` parsing because append is not optimistic-locked. Both await `_build_officer_actor` (which awaits `resolve_or_create_real_discord_member`); after the actor is built, all service calls are synchronous Python, identical to the β-i claim and β-ii detail/transcript pattern.
- Bridge ignores `applicant_receipt` cookie and any browser-supplied `X-Actor-*` headers. `_build_officer_actor` is reused verbatim from β-i (`services/api/app/api/v1/endpoints/web.py:75-129`), so the dependency-tree guard `test_officer_endpoints_have_locked_actor_construction` (`services/api/tests/test_web_officer_applications.py:1110-1147`) extends to the two new POST routes. The forbidden-callable set (`get_current_actor`, `CURRENT_ACTOR.get`, `verify_applicant_receipt`) and the forbidden-source-substring set (`CURRENT_ACTOR.get(`, `verify_applicant_receipt`, `applicant_receipt`) hold across the now six-route officer router (proposal §7 "Dependency-tree guard expands to include the two POST routes while preserving … existing guard section").
- Message append builds author fields server-side. The direct `ApplicationMessageAppendRequest` requires `author_actor_kind` + `author_actor_id` (`services/api/app/contracts/application_messages.py:19-30`); the new bridge contract `OfficerApplicationMessageAppendRequest` deliberately *does not* expose those fields to the browser (proposal §3 "do not expose author fields to the browser"). The bridge constructs them from the Pomerium-resolved officer actor before delegating to `append_application_message`, so a browser cannot spoof author identity.
- Transition bridge restricts the `action` enum at the bridge contract level. `claim` stays on `/claim`; `route` is rejected by `transition_application` itself (`services/api/app/services/applications.py:1068-1074`); `reassign` is out of scope. The bridge returns 422 `validation_error` for any unsupported action without reaching the service.
- Error mapping reuses `raise_known_application_error` (`services/api/app/api/v1/endpoints/applications/_shared.py:64-202`); transition codes preserved include `application_not_found` (404), `authority_decision_denied` (403), `application_not_owner` (409), `invalid_application_transition` (409), `application_decision_reason_required` (409), `application_review_notes_required` (409), `application_waitlist_reason_required` (409), `application_reactivate_owner_required` (409), `stale_application_version` (412), `if_match_required` (428), `validation_error` (422). Message codes preserved include `application_message_forbidden` (403), `applicant_visibility_required` (422). All codes match the direct endpoints (`services/api/app/api/v1/endpoints/applications/lifecycle.py:125-146`, `services/api/app/api/v1/endpoints/applications/messages.py:49-76`).

The browser SPA continues to address bridge endpoints under `/api/web/officer/...` and `/api/me`. The β-i nginx-web `/api/` → `/api/v1/` rewrite is unchanged. No `/api/v1/...` literal is reintroduced in `services/web/src/`; the β-i negative grep guard in `validate_web_ui_local.sh:175-179` (`grep -rE "[\"']/api/v1/" "${REPO_ROOT}/services/web/src/"`) continues to pass — the new client functions `appendOfficerApplicationMessage` and `transitionOfficerApplication` use browser paths `/api/web/officer/applications/{id}/messages` and `/api/web/officer/applications/{id}/transitions`.

### 2. Pomerium routing

**No new entries. No re-ordering. No identity-header changes.** The `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` block stays at its β-ii post-state with these eight web-host routes (in declared order):

1. `path: /api/me`
2. `prefix: /api/web/admin/`
3. `prefix: /api/web/officer/`
4. `path: /applications/queue`
5. `prefix: /applications/queue/`
6. `prefix: /applications/`  ← already auth-gates the officer detail surface (β-ii)
7. `prefix: /admin`
8. `prefix: /auth/discord/` (public)

…followed by the public catch-all and the protected-api host. β-iii adds composer + transition controls *to the same `/applications/{id}` route* β-ii already shipped, and the two new bridge endpoints are at `/api/v1/web/officer/applications/{id}/{messages,transitions}`, which the existing `prefix: /api/web/officer/` (entry #3) already gates with `pass_identity_headers: true` and `allow_any_authenticated_user: true`. `idp_scopes` (`openid email profile discord_user_id`) and `jwt_claims_headers` (`x-pomerium-claim-{email,sub,groups,name,discord-user-id}`) are unchanged.

`infra/tests/test_applicant_discord_pomerium.py` is unchanged. The β-ii positive assertions (`/applications` → catch-all, `/applications/<uuid>` → new auth-gated `/applications/` prefix, `/applications/queue` → exact-path entry, `/api/web/officer/...` precedes the catch-all) continue to hold without modification because β-iii adds zero routes.

### 3. Applicant Discord OAuth flow

Untouched. β-iii does not change:

- The `prefix: /auth/discord/` Pomerium entry (still public, still targets API service, still `pass_identity_headers: false`).
- `applicant_receipt` cookie issuance, validation, or consumption.
- `/auth/discord/me`, `/auth/discord/start`, `/auth/discord/callback`, or `/api/v1/public/applications`.
- `ApplicationFormRoute.tsx` selectors, conditional auth-state rendering, the 9-minute re-probe timer, or the `return_to=/applications` redirect target.
- `services/api/app/services/members.resolve_or_create_real_discord_member` defaults — β-i parameterized this; β-ii and β-iii do not retouch the function signature.

The `compat.spec.ts` cases that bind to applicant DOM ids and the `/auth/discord/me` / `/api/public/applications` routes (`applicantDiscordTest applications page without receipt shows only Discord login`, `test_anonymous_state_dom_tightening`, `loggedInApplicantTest applications page with valid receipt shows form and Discord identity`, `loggedInApplicantTest test_verified_state_details_panel_hidden_initially`, `loggedInApplicantTest application form submits with a valid receipt and shows success`, `staleApplicantReceiptTest application submit with expired receipt redirects to Discord auth start`) are unaffected. β-iii adds officer composer + transition controls on `/applications/{id}` only; the applicant route at `/applications` continues to render `ApplicationFormRoute`, and `compat.spec.ts` continues to pass without modification.

### 4. Build pipeline

`containers/server-manager/Containerfile.web`, `containers/server-manager/Containerfile.api`, and `infra/scripts/build-channel-image.sh` are unchanged. β-iii adds:

- Three new TS source files: `services/web/src/features/officer/applicationStateMachine.ts`, `services/web/src/features/officer/ApplicationMessageComposer.tsx`, `services/web/src/features/officer/ApplicationTransitionActions.tsx`.
- One new (or extended) Playwright spec: `services/web/tests/officer-actions.spec.ts` (or an extension of `services/web/tests/officer-detail.spec.ts`).
- Modifications to existing TS files: `services/web/src/api/client.ts`, `services/web/src/features/officer/ApplicationDetailRoute.tsx`, `services/web/src/features/officer/officer.module.css`.
- Modifications to two Python files: `services/api/app/api/v1/endpoints/web.py` (two new route handlers), `services/api/app/contracts/web.py` (one new request contract).
- Modifications to test fixtures and validators: `infra/tests/fixtures/web-ui/contract.json` (additional keys), `infra/tests/validate_web_ui_local.sh` (allowlist for two more browser API paths and Playwright spec coverage assertion), `infra/tests/e2e/lib/playwright/browser-flow.mjs` (post-detail `review` then `approve` legs), `infra/tests/e2e/tests/19-web-ui.sh` (additional grant seed entries + Postgres assertions).

No new top-level npm package, no new Python dependency, no new build script, no new dist path, no nginx config change, no new Vite config, no new build-arg. `npm run build` (Vite) and `pip install -e .` continue to work unchanged.

### 5. K3d image rollout / GitOps

- `infra/tests/validate_web_ui_local.sh` retains its β-i / β-ii asserts (negative `/api/v1/...` grep, positive `client.ts` allowlist, contract fixture schema check, Playwright spec coverage check, `npm run build`, image build, live `curl` against `/api/me`, admin auth gate). β-iii additions per proposal §3: extend the allowlist for the two new browser API paths (`/api/web/officer/applications/{id}/messages`, `/api/web/officer/applications/{id}/transitions`); extend `assert_contract_fixture` for the new contract keys; either reuse `assert_officer_detail_contract_spec` or add a sibling `assert_officer_actions_contract_spec` for the new spec file. The negative grep guard continues to pass because the new client functions use browser-facing `/api/...` paths.
- `infra/tests/e2e/run-fullstack.sh` is unchanged. The suite count stays at 19 (proposal §3 keeps `e2e_init "19-web-ui"` and §7 step 1 reuses `infra/tests/e2e/tests/19-web-ui.sh`).
- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` is unchanged — **no new Authentik blueprint, no new application/provider/source/scope mapping**. The β-i `discord-pomerium` source remains the officer identity chain; β-iii surfaces no new auth integration.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` is unchanged — zero new route entries, zero re-ordering. FluxCD reconciliation of the InfisicalSecret is unchanged.
- **No new Infisical secret, no new env var.** β-i added `DISCORD_OFFICER_OAUTH_CLIENT_ID` / `DISCORD_OFFICER_OAUTH_CLIENT_SECRET`; β-ii added nothing; β-iii adds nothing.

### 6. e2e suite

`infra/tests/e2e/tests/19-web-ui.sh`:

- `assert_public_submit_persisted` — preserved unchanged (reads `web-ui-public-submit.json`, asserts `applications.state='queued'` and applicant `members.discord_user_id` equals the bootstrap fixture id).
- `assert_officer_claim_persisted` — preserved unchanged (reads `web-ui-queue-claim.json`, asserts owner is a real Discord member, asserts the `application.claim` audit `request_surface` equals `api:/api/v1/web/officer/applications/{id}/claim`).
- `assert_officer_detail_checked` — preserved unchanged (reads `web-ui-detail.json`, asserts detail state `claimed` and a `state_change`→`claimed` transcript entry).
- **β-iii adds** post-detail Postgres assertions for the new mutations (proposal §7 E2E steps 3 + 4): from the claimed detail page, append an officer-only message then submit `review` and `approve`; assert `applications.state` advances `claimed → in_review → approved`, `decision_reason` is set, `application.review` and `application.decision` audit rows appear with `request_surface=api:/api/v1/web/officer/applications/{id}/transitions`, and an `application_messages` row exists for the appended officer-only message. Existing assertions are not removed.
- `run_validator validate-web-ui` — preserved.
- `seed-authority-grants.mjs` invocation — preserved; it already grants `application.review` + `application.claim` (`infra/tests/e2e/lib/seed-authority-grants.mjs`).
- `grant_officer_message_authority` — preserved unchanged (already seeds `application.message` for the officer member at `infra/tests/e2e/tests/19-web-ui.sh:95-141`); β-iii reuses it as-is.
- **β-iii extends grant seeding** (proposal §7 step 1) to add `application.approve` (`review` is already in the seed set) at the same scope. This is a fixture-side seed, not a runtime authority change; the auto-grant pipeline is untouched.
- `e2e_init "19-web-ui"` — preserved; the suite count stays at 19, satisfying the gate's "extend test 19 (not new test)" requirement.

`infra/tests/e2e/lib/playwright/browser-flow.mjs` (proposal §7, step 2–5): after the existing detail/transcript leg ending at the `application-transcript` `state_change[data-to-state="claimed"]` wait at `infra/tests/e2e/lib/playwright/browser-flow.mjs:171-184`, β-iii adds (a) message-composer fill + submit, (b) `review` action with notes, (c) `approve` action with decision reason, (d) per-step waits for the updated `application-detail-state` and the corresponding new transcript entries. Result is written to `web-ui-actions.json` (sibling of `web-ui-detail.json`) or appended to the existing artifact. None of these additions invalidate the existing public-submit, claim, or detail-leg assertions.

`infra/tests/fixtures/web-ui/contract.json`: β-iii adds `applications.messages.{endpoint, method, success_status_created, success_status_duplicate}` and `applications.transitions.{endpoint, method, success_status, if_match_header, exposed_actions}` keys (or equivalent). Existing keys (`routes.public`, `routes.application_form`, `routes.officer_queue`, `routes.officer_detail`, `routes.admin`, `auth.*`, `applications.queue`, `applications.claim`, `applications.detail`, `applications.transcript`, `form.*`, `ui_libraries.*`, `host_loopback`, `host_https_port`) are preserved verbatim; consumers (`compat.spec.ts:loadContract`, `validate_web_ui_local.sh:assert_contract_fixture`, `officer-queue.spec.ts`, `officer-detail.spec.ts`) keep working because the contract loader uses optional/named-key access.

### 7. Python module surface

| Symbol | Pre (post-β-ii) | Post (β-iii) |
|---|---|---|
| `app.api.v1.endpoints.web.router` | exposes `GET /api/v1/web/admin/chapters`, `GET /api/v1/web/officer/applications`, `GET /api/v1/web/officer/applications/{id}`, `POST /api/v1/web/officer/applications/{id}/claim`, `GET /api/v1/web/officer/applications/{id}/transcript` | adds `POST /api/v1/web/officer/applications/{id}/messages` and `POST /api/v1/web/officer/applications/{id}/transitions`. **No edits to existing route handlers** — the five β-i / β-ii handlers remain byte-identical. |
| `app.api.v1.endpoints.web._build_officer_actor` / `get_officer_actor` / `_db` / `_parse_state_query` | β-i / β-ii officer actor builder + dependency factory + DB accessor + state query parser | unchanged — proposal §6 reuses verbatim. |
| `app.contracts.web.OfficerApplicationMessageAppendRequest` | n/a | **new** Pydantic class under `app.contracts.web` (proposal §3 "Modified files"): `body_markdown: str`, `visibility: ApplicationMessageVisibility`, `client_message_id: str \| None = None`. Author fields are *not* exposed; the bridge attaches `author_actor_kind="user"` / `author_actor_id=<member uuid>` from the Pomerium-resolved actor before delegating. The existing `app.contracts.web.CurrentPrincipalRead`, `AdminChapterListRead`, `AdminChapterSummaryRead` and the module's `_WebModel` base are unchanged. |
| `app.api.v1.endpoints.applications._shared.{parse_if_match_strong, raise_known_application_error, set_etag}` | β-i / β-ii / INIT-131 / INIT-132 helpers | unchanged — already handle every code the new bridges raise (transition codes `application_not_found`, `authority_decision_denied`, `application_not_owner`, `invalid_application_transition`, `application_{decision_reason,review_notes,waitlist_reason,reactivate_owner}_required`, `stale_application_version`, `if_match_required`, `validation_error`; message codes `application_message_forbidden`, `applicant_visibility_required`). |
| `app.services.applications.transition_application` | INIT-128 / INIT-129 service | unchanged — called by the transition bridge as a Python function with the same `(actor=, application_id=, expected_version=, request=, request_surface=)` keyword shape β-i claim already uses (`services/api/app/api/v1/endpoints/web.py:213-223`). No signature edit; no change to `VALID_TRANSITIONS` (`services/api/app/services/applications.py:65-89`); no change to `validate_required_transition_fields`, `validate_transition`, `_reviewer_id`, or `require_transition_authority` (`services/api/app/services/applications.py:266-273`, `:348-362`, `:585-620`). |
| `app.services.application_messages.append_application_message` | INIT-131 service | unchanged — called by the message bridge with the existing `(actor=, application_id=, request=ApplicationMessageAppendRequest(...), request_surface=)` shape. |
| `app.services.application_messages.read_application_messages` | INIT-131 service (visibility filter) | unchanged. |
| `app.services.application_transcript.read_application_transcript` | INIT-132 / β-ii service | unchanged. |
| `app.services.applications.{read_application, require_application_read_authority}` | β-ii direct lifecycle / read-authority | unchanged. |
| `app.api.v1.endpoints.applications.{lifecycle, transcript, messages}` direct endpoints | INIT-128 / INIT-131 / INIT-132 | unchanged. |
| `app.contracts.applications.ApplicationTransitionRequest` | direct API request shape (`action`, `notes`, `decision_reason`, `thread_id`, `reason`, `new_owner_id`, `originating_actor_*`) (`services/api/app/contracts/applications.py:249-270`) | unchanged — the bridge constructs the existing Pydantic model from the browser-supplied subset (no `originating_actor_*` from the browser). |
| `app.contracts.application_messages.{ApplicationMessageAppendRequest, ApplicationMessageRead, ApplicationMessageVisibility}` | INIT-131 contracts (`services/api/app/contracts/application_messages.py:19-30`) | unchanged. |
| Existing applicant-receipt service + dependency | unchanged | unchanged |

**Edits to existing exports: zero.** β-iii adds two new bridge route handlers under the existing `app.api.v1.endpoints.web.router` and one new Pydantic contract under `app.contracts.web` — *all* of these are the new exports. Every other symbol the bridges consume (`_build_officer_actor`, `parse_if_match_strong`, `set_etag`, `raise_known_application_error`, `transition_application`, `append_application_message`, `read_application`, `require_application_read_authority`, `VALID_TRANSITIONS`, `_reviewer_id`, `require_transition_authority`, `validate_required_transition_fields`, `validate_transition`) is reused as-is. The gate's "only new exports in `web.py`" requirement is satisfied across both the endpoint module (`app.api.v1.endpoints.web`) and the contract module (`app.contracts.web`); both are named `web.py`.

The β-i / β-ii dependency-tree guard `test_officer_endpoints_have_locked_actor_construction` (`services/api/tests/test_web_officer_applications.py:1110-1147`) is extended (proposal §7) so its expected route set becomes `{/api/v1/web/officer/applications, /api/v1/web/officer/applications/{application_id}, /api/v1/web/officer/applications/{application_id}/claim, /api/v1/web/officer/applications/{application_id}/transcript, /api/v1/web/officer/applications/{application_id}/messages, /api/v1/web/officer/applications/{application_id}/transitions}` and the same forbidden-callable + forbidden-source-substring assertions continue to hold for the now six-route officer router. The proposal explicitly preserves the existing guard substrings (`get_current_actor`, `CURRENT_ACTOR.get`, `verify_applicant_receipt`, `applicant_receipt`).

### 8. Frontend module surface

| Symbol | Pre (post-β-ii) | Post (β-iii) |
|---|---|---|
| `services/web/src/api/client.ts` exports | β-ii: `applicationStateSchema`, `applicationScopeSchema`, `applicationReadSchema`, `applicationListReadSchema`, `applicationTransitionRequestSchema = z.object({ action: z.literal("claim") })`, `applicationTransitionResponseSchema`, `applicationStateChangeEntrySchema`, `applicationMessageEntrySchema`, `applicationTranscriptEntrySchema`, `applicationTranscriptReadSchema`, `ApiError`, `getJson`, `fetchCurrentPrincipal`, `fetchAdminChapters`, `fetchApplicantDiscordIdentity`, `submitPublicApplication`, `fetchOfficerApplicationQueue`, `fetchOfficerApplication`, `fetchOfficerApplicationTranscript`, `claimOfficerApplication`, types `CurrentPrincipal`, `AdminChapterSummary`, `ApplicationState`, `ApplicationRead`, `ApplicationListRead`, `ApplicationTranscriptEntry`, `ApplicationTranscriptRead`, `SubmissionResponseBody` | adds `applicationMessageVisibilitySchema`, `applicationMessageAppendRequestSchema` (browser shape: no author fields), `applicationMessageReadSchema`, `applicationTransitionActionSchema` (β-iii enum: `review`, `request_interview`, `waitlist`, `approve`, `deny`, `reactivate`, `withdraw`), `appendOfficerApplicationMessage`, `transitionOfficerApplication`. Types: `ApplicationMessageAppendRequest`, `ApplicationMessageRead`, `ApplicationTransitionRequest`. **Widens** `applicationTransitionRequestSchema` from `{ action: "claim" }` to the full transition request shape; backward-compatible because the only existing consumer is the new transition function — `claimOfficerApplication` constructs no body and never invokes this schema's `parse`. **Widens** `applicationTransitionResponseSchema` (alias of `applicationReadSchema`) — already widened additively in β-ii. |
| `services/web/src/app/router.tsx` | β-ii routes: `/`, `/applications`, `/applications/queue`, `/applications/$applicationId`, `/admin/chapters` | unchanged — composer + transition actions mount inside the existing `ApplicationDetailRoute` at `/applications/$applicationId`. **No new router-table entry.** |
| `services/web/src/features/officer/ApplicationDetailRoute.tsx` | β-ii read-only detail route | mounts `ApplicationMessageComposer` and `ApplicationTransitionActions` below the existing metadata/transcript layout; owns refetch-after-mutation + conflict / stale-version notice rendering. The β-ii `data-application-id`, `application-detail-state`, `application-transcript` test ids and the principal probe / detail / transcript loading flow remain intact, so the e2e detail-leg assertions in `browser-flow.mjs:165-184` and `assert_officer_detail_checked` continue to work without modification. |
| `services/web/src/features/officer/ApplicationQueueRoute.tsx` | β-i / β-ii queue route component (claim button + row navigation to `/applications/{id}`) | unchanged — β-iii does not retouch the queue. The e2e claim leg in `browser-flow.mjs:130-159` and `services/web/tests/officer-queue.spec.ts` continue passing. |
| `services/web/src/features/officer/ApplicationMessageComposer.tsx` | n/a | **new** — owns `bodyMarkdown`, `visibility`, `clientMessageId`, `submitting` route-local Solid signals; sends `body_markdown`, `visibility`, `client_message_id` to the bridge; does not send author fields. Calls back into the route on append success / failure. |
| `services/web/src/features/officer/ApplicationTransitionActions.tsx` | n/a | **new** — renders one compact control per valid action (visibility derives from `applicationStateMachine.validOfficerTransitionActions(state)`); collects required fields per action; submits with `If-Match: "<application.version>"`; calls back into the route on transition success / failure. |
| `services/web/src/features/officer/applicationStateMachine.ts` | n/a | **new** — table-driven helper exporting `OFFICER_TRANSITION_ACTIONS`, `OfficerTransitionAction`, `validOfficerTransitionActions(state)`, `transitionActionInput(action)`. Mirrors the β-iii subset of `services/api/app/services/applications.py:VALID_TRANSITIONS` only. |
| `services/web/src/features/officer/officer.module.css` | β-i / β-ii queue + detail layout | adds compact action / composer layout classes; existing classes unchanged. |
| `services/web/src/features/public/ApplicationFormRoute.tsx`, `services/web/src/features/public/HomeRoute.tsx`, `services/web/src/features/admin/AdminChaptersRoute.tsx`, `services/web/src/main.tsx`, `services/web/src/app/providers.tsx`, `services/web/src/components/primitives/Button.tsx` | unchanged | unchanged |

**Frontend module deletions: none.** β-i deleted `RuntimeApp.tsx`, `DarkNemesisForm.tsx`, `features/forms/schema.ts`, `features/forms/form.module.css`. β-ii deleted nothing. β-iii deletes nothing — only adds three component files, optionally adds one new spec file, and modifies four existing files (router unchanged at the route-table level; detail route gains internal mounts; client gains schemas + functions; CSS gains classes).

Cross-source reference check: the existing `services/web/tests/officer-queue.spec.ts`, `services/web/tests/officer-detail.spec.ts`, and `services/web/tests/compat.spec.ts` consume only β-i / β-ii symbols from `client.ts`. β-iii does not rename or remove any of them; the widened `applicationTransitionRequestSchema` is structurally compatible with β-i call sites because no existing call site invokes its `parse`.

### 9. Database schema

NONE. Both new endpoints are mutating but write to existing tables only:

- `application_messages` (INIT-131, message append)
- `applications` + `aggregate_heads` + `activity_state_changes` + `activity_actions` (INIT-128 / INIT-129, transition write path inside `transition_application`)

No new column, no new index, no new constraint, no new table, no migration is added or modified. Proposal §8 anti-scope rules out schema migrations explicitly.

### 10. Permission namespace

NONE. The proposal §6 mapping uses only existing permission names already enforced by `require_transition_authority` (`services/api/app/services/applications.py:348-362`) and the message-append authority gate (`services/api/app/services/application_messages.py:52-82`):

| Action | Permission (existing) |
|---|---|
| message append | `application.message` (INIT-131) |
| `review` | `application.review` |
| `request_interview` | `application.request_interview` |
| `waitlist` | `application.waitlist` |
| `approve` | `application.approve` |
| `deny` | `application.deny` |
| `reactivate` | `application.reactivate` |
| `withdraw` | `application.withdraw` |

`application.{review, claim, route, message, withdraw, reassign, request_interview, waitlist, approve, deny, reactivate}` are all already in the system's permission namespace. **No new permission name is introduced.** Proposal §8 anti-scope rules out new permissions explicitly.

### 11. Authority grants

NONE issued by the slice itself. The slice runs against:

- `infra/tests/e2e/lib/seed-authority-grants.mjs` — already seeds `application.review` + `application.claim` for the resolved officer member UUID.
- `grant_officer_message_authority` in `infra/tests/e2e/tests/19-web-ui.sh:95-141` — already seeds `application.message` for the resolved officer member UUID.
- β-iii extends the seed set with `application.approve` (the e2e flow advances `claimed → review → approve`). `review` is already covered. This is a fixture-side seed only — neither the auto-grant pipeline (INIT-104 / INIT-128 wiring) nor any runtime authority issuance path is touched. Whether to add `approve` via `seed-authority-grants.mjs` or via a new sibling helper is an e2e operator decision, not a runtime authority change.

**β-iii does not introduce a new auto-grant, new authority issuance path, new actor kind, or new identity chain** beyond what β-i / β-ii already seed. Proposal §8 anti-scope rules out new actor kinds and new authority issuance paths explicitly.

## Verdict reasoning

LOW. Every supported surface this slice touches is preserved or extended additively:

1. **HTTP API**: two net-new POST bridge endpoints under `/api/v1/web/officer/...` (`/messages`, `/transitions`); every existing direct and bridge endpoint (including the β-i claim, β-ii detail/transcript, the direct `/api/v1/applications/{id}/{transitions,messages,transcript}`, applicant `/api/v1/public/applications`, and `/auth/discord/*`) is byte-identical. Bridges call services as Python functions (not HTTP self-calls), preserving the β-i / β-ii pattern. Browser-supplied author fields and `originating_actor_*` are not honored — the bridge attaches actor identity from `_build_officer_actor`. The transition bridge restricts its `action` enum to the β-iii subset at the bridge contract layer, so `claim` / `route` / `reassign` cannot reach `transition_application` through this route.
2. **Pomerium routing**: zero new entries. `prefix: /applications/` (β-ii) already auth-gates the officer detail surface, and `prefix: /api/web/officer/` (β-i) already auth-gates the new bridge endpoints. `idp_scopes`, `jwt_claims_headers`, target service, and route ordering are unchanged. Existing static Pomerium tests pass without modification.
3. **Applicant Discord OAuth flow**: `/auth/discord/*`, `applicant_receipt`, `/auth/discord/me`, `/api/v1/public/applications`, `ApplicationFormRoute.tsx`, and `compat.spec.ts` are entirely unchanged.
4. **Build pipeline / k3d / GitOps**: Containerfile.web, Containerfile.api, build-channel-image.sh, run-fullstack.sh, the FluxCD-reconciled blueprint configmap, and the Pomerium InfisicalSecret are untouched. `validate_web_ui_local.sh` extends additively (allowlist for two more browser API paths, contract-fixture key checks for messages/transitions, optional Playwright spec coverage assertion). **No new env var, no new Infisical secret, no new Authentik blueprint.**
5. **e2e suite**: test 19 keeps `assert_public_submit_persisted`, `assert_officer_claim_persisted`, and `assert_officer_detail_checked`; β-iii adds post-detail message + `review` + `approve` legs in `browser-flow.mjs` and the matching Postgres assertions in `19-web-ui.sh`. Suite count stays at 19.
6. **Compat tests + β-i + β-ii tests preserved**: `services/web/tests/compat.spec.ts`, `services/web/tests/officer-queue.spec.ts`, `services/web/tests/officer-detail.spec.ts`, `infra/tests/test_applicant_discord_pomerium.py`, and the `services/api/tests/test_web_officer_applications.py` cases for list / claim / detail / transcript are not modified destructively. The dependency-tree guard's expected route set grows from four officer routes to six; its forbidden-callable and forbidden-source-substring sets are preserved.
7. **Python module surface**: only new exports — two new bridge route handlers in `app.api.v1.endpoints.web` and one new request contract in `app.contracts.web`. **No edits to existing transition or message service signatures** (`transition_application`, `append_application_message`, `read_application_transcript`, `read_application_messages`, `read_application`, `require_application_read_authority`, `parse_if_match_strong`, `set_etag`, `raise_known_application_error`, `_build_officer_actor`, `get_officer_actor`, `_db`, `_parse_state_query`, `VALID_TRANSITIONS`, `_reviewer_id`, `require_transition_authority`, `validate_required_transition_fields`, `validate_transition`).
8. **Frontend module surface**: only additive `client.ts` exports (message + transition schemas + two fetch functions; the existing `applicationTransitionRequestSchema` widening is structurally compatible because no existing call site parses through it); three new feature files; optional one new Playwright spec; one router-table entry unchanged; additive CSS classes; the β-ii `ApplicationDetailRoute.tsx` test ids and loading flow are preserved. **No frontend module deletions.**
9. **Database schema, permission namespace, authority grants**: zero change in all three.

The behavioral change beyond pure preservation is: officers with the existing `application.{review, request_interview, waitlist, approve, deny, reactivate, withdraw, message}` permissions can now drive non-claim transitions and append messages from the same `/applications/{id}` route β-ii shipped, instead of needing the direct `/api/v1/applications/...` endpoints. No new identity chain, no new audit code path, no new permission name, no new schema column, and no Pomerium / Authentik configuration changes are required. With the β-i / β-ii invariants extended over the new bridge routes (officer dependency-tree guard for six routes, `applicant_receipt` cookie ban, `X-Actor-*` header ban, server-side author-field construction, server-side actor identity construction, `If-Match` strong parse + ETag emission on the transition write path, browser action enum restricted to the β-iii subset, contract Zod schemas widened additively), every supported surface this slice touches stays backward-compatible.

SUPPORTED_SURFACE_DONE: plans/risk/init-133B-iii-supported-surface.md
