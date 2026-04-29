# INIT-133B-ii — Supported-surface risk gate

**Verdict:** LOW

## Surfaces touched

### 1. HTTP API

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `GET /api/v1/me` | `{subject, email, display_name, provider, groups, discord_user_id}` (β-i) | unchanged | none |
| `GET /api/v1/web/admin/chapters` | unchanged | unchanged | none |
| `GET /api/v1/web/officer/applications` | β-i list endpoint | unchanged | none |
| `POST /api/v1/web/officer/applications/{id}/claim` | β-i claim endpoint | unchanged | none |
| `GET /api/v1/web/officer/applications/{id}` | n/a | new (200/401/403/404/422) read-only bridge to `read_application` + `require_application_read_authority` | additive, new path under `/api/v1/web/officer/...` |
| `GET /api/v1/web/officer/applications/{id}/transcript` | n/a | new (200/401/403/404/422) read-only bridge to `read_application_transcript` (which delegates message-visibility to `read_application_messages`) | additive, new path under `/api/v1/web/officer/...` |
| `GET /api/v1/applications/{id}` | unchanged | unchanged | none — bridge does NOT proxy via HTTP self-call; it calls `read_application(...)` as a Python service function (proposal §4 "Bridge service calls") |
| `GET /api/v1/applications/{id}/transcript` (INIT-132) | unchanged | unchanged | none — same direct service-call pattern |
| `POST /api/v1/applications/{id}/transitions` | unchanged | unchanged | none |
| `POST /api/v1/applications/{id}/messages` (INIT-131) | unchanged | unchanged | none |
| `GET /api/v1/applications` (INIT-133A) | unchanged | unchanged | none |
| `POST /api/v1/applications` | unchanged | unchanged | none |
| `POST /api/v1/public/applications` | unchanged | unchanged | none — applicant submit untouched |
| `GET /auth/discord/me` | unchanged | unchanged | none — applicant only |
| `GET /auth/discord/start` / `GET /auth/discord/callback` | unchanged | unchanged | none |

The two new bridge routes preserve the β-i bridge shape (proposal §4):

- Both `async def`, awaiting only `_build_officer_actor` (which awaits `resolve_or_create_real_discord_member`); after the actor is built, service reads are synchronous Python calls (`services/api/app/api/v1/endpoints/web.py:67-116`). No `If-Match` parsing, no mutation body, no ETag emission.
- Detail GET error mapping reuses `raise_known_application_error` (`services/api/app/api/v1/endpoints/applications/_shared.py:64-182`); preserves direct lifecycle codes `application_not_found`, `authority_decision_denied`, `validation_error`.
- Transcript GET error mapping preserves direct transcript endpoint codes `application_not_found` and `application_transcript_forbidden` (`services/api/app/api/v1/endpoints/applications/transcript.py:22-36`).
- Bridge ignores `applicant_receipt` cookie and any browser-supplied `X-Actor-*` headers, identical to β-i. The β-i dependency-tree guard `test_officer_endpoints_have_locked_actor_construction` extends to the two new routes (proposal §7), so the negative invariants (no `get_current_actor`, no `CURRENT_ACTOR.get`, no `verify_applicant_receipt`, no `applicant_receipt` cookie source) are pinned across the full officer route set.

The browser SPA continues to address bridge endpoints under `/api/web/officer/...` and `/api/me` (the nginx-web `/api/` → `/api/v1/` rewrite is unchanged). No `/api/v1/...` literal is reintroduced in `services/web/src/`; the β-i negative grep guard in `validate_web_ui_local.sh` continues to enforce this.

### 2. Pomerium routing

| Path | Pre | Post | Risk |
|---|---|---|---|
| `https://web.local.humility.local/applications` (bare) | catch-all (public) | catch-all (public) — `prefix: /applications/` does NOT match `/applications` because the request path does not start with the trailing-slash prefix | none |
| `https://web.local.humility.local/applications/queue` | β-i `path: /applications/queue` (auth-gated) | unchanged — first-match-wins resolves to the existing exact-path entry before the new `/applications/` prefix | none |
| `https://web.local.humility.local/applications/queue/...` | β-i `prefix: /applications/queue/` (auth-gated) | unchanged — first-match-wins resolves to the existing nested-prefix entry before the new `/applications/` prefix | none |
| `https://web.local.humility.local/applications/<uuid>` (and any `/applications/<segment>` not under `/applications/queue`) | catch-all (public) | new `prefix: /applications/` (auth-gated) before the catch-all | additive — intentional gating of the officer detail surface |
| `https://web.local.humility.local/applications/queue-foo` | catch-all (public) | new `prefix: /applications/` (auth-gated) — broadens gating to any non-queue child of `/applications/` | LOW — no SPA route renders meaningful content here; behavior change is gating an unused surface, not a regression of a documented surface |
| `https://web.local.humility.local/admin/...` | β-i `prefix: /admin` (auth-gated) | unchanged ordering, still after the new `prefix: /applications/` | none |
| `https://web.local.humility.local/auth/discord/...` | `prefix: /auth/discord/` → API service, public-unauthenticated, `pass_identity_headers: false` | unchanged | none — applicant Discord OAuth path stays public and routes to API service; β-ii adds nothing on `/auth/discord/*` |
| `https://web.local.humility.local/api/me`, `/api/web/admin/...`, `/api/web/officer/...` | β-i auth-gated entries | unchanged | none |
| `https://web.local.humility.local/` (catch-all) | unchanged | unchanged: web service, public; remains last for the host | none |
| `https://protected-api.local.humility.local/...` | unchanged | unchanged | none |

**Insertion order (locked).** β-ii inserts exactly one new entry — `prefix: /applications/` targeting the web service with `preserve_host_header: true`, `pass_identity_headers: true`, `allow_any_authenticated_user: true` — immediately after the existing `prefix: /applications/queue/` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:73-78`) and before the existing `prefix: /admin` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:79-84`). Resulting web-host route order:

1. `path: /api/me`
2. `prefix: /api/web/admin/`
3. `prefix: /api/web/officer/`
4. `path: /applications/queue`
5. `prefix: /applications/queue/`
6. `prefix: /applications/`  ← **NEW**
7. `prefix: /admin`
8. `prefix: /auth/discord/` (public)
9. catch-all (public)

**`idp_scopes`, `jwt_claims_headers`, target service.** Unchanged. No new scope, no new claim header. The new entry uses the same identity headers β-i routes use.

**Existing static tests survive without modification.** `infra/tests/test_applicant_discord_pomerium.py` resolves routes by walking `_web_routes()` in declared order with `_matches(...)` (`infra/tests/test_applicant_discord_pomerium.py:69-78`). Replaying every assertion against the post-β-ii order:

- `_first_web_route_for("/applications")` — `"/applications".startswith("/applications/")` is False (the trailing slash in the prefix is load-bearing), so the new prefix does NOT match. Falls to catch-all. Existing assertion `_first_web_route_for("/applications").get("path") != "/applications/queue"` still holds (catch-all has no `path`). PASSES.
- `_first_web_route_for("/applications/queue")` — exact-path entry at index 4 wins. PASSES the `path == "/applications/queue"` assertion.
- `_first_web_route_for("/applications/queue/")` — nested-prefix entry at index 5 wins. PASSES the `prefix == "/applications/queue/"` assertion.
- `_first_web_route_for("/applications/queue-foo")` — does NOT match `path: /applications/queue` (not exact) or `prefix: /applications/queue/` (no slash). NOW matches new `prefix: /applications/` at index 6 (was: catch-all). Existing assertion is `.get("path") != "/applications/queue"` — the new prefix has no `path` key, returns None, None ≠ "/applications/queue". PASSES.
- `_first_web_route_for("/api/me")` / `/api/me-foo` / `/api/members/abc` — unaffected. PASS.
- `test_pomerium_idp_scopes_include_discord_user_id_exactly` and `test_pomerium_jwt_claims_headers_include_exact_identity_claims` — unchanged sets, PASS.
- `test_identity_bearing_web_routes_precede_public_catch_all` — iterates fixed `route_specs` for `/api/me`, `/api/web/admin/`, `/api/web/officer/`, `/applications/queue`, `/applications/queue/`. All five still resolve and still precede the catch-all. PASSES.

**β-ii adds new positive assertions** (proposal §3 "Modified files" → `infra/tests/test_applicant_discord_pomerium.py`): `/applications` resolves to the catch-all; `/applications/<uuid>` resolves to the new auth-gated `prefix: /applications/`; `/applications/queue` still resolves to the existing exact-path entry first; the new prefix entry exists exactly once and precedes the catch-all. These extend coverage rather than replace existing assertions.

### 3. Applicant Discord OAuth flow

Untouched. β-ii does not change:

- `prefix: /auth/discord/` Pomerium entry (still public, still targets the API service, still `pass_identity_headers: false`).
- `applicant_receipt` cookie issuance, validation, or consumption.
- `/auth/discord/me`, `/auth/discord/start`, `/auth/discord/callback`, or `/api/v1/public/applications`.
- `ApplicationFormRoute.tsx` selectors, conditional auth-state rendering, 9-minute re-probe timer, `return_to=/applications` redirect target, or DOM contract pinned by `compat.spec.ts:202-323`.
- `services/api/app/services/members.resolve_or_create_real_discord_member` defaults — β-i parameterized this with `originating_actor` / `request_surface` defaulted to the applicant path; β-ii does not retouch the function signature.

The four `compat.spec.ts` cases that bind to applicant DOM ids and the `/auth/discord/me` / `/api/public/applications` routes (`applicantDiscordTest applications page without receipt shows only Discord login`, `test_anonymous_state_dom_tightening`, `loggedInApplicantTest applications page with valid receipt shows form and Discord identity`, `loggedInApplicantTest test_verified_state_details_panel_hidden_initially`, `loggedInApplicantTest application form submits with a valid receipt and shows success`, `staleApplicantReceiptTest application submit with expired receipt redirects to Discord auth start`) are unaffected: β-ii adds the SPA route at `/applications/$applicationId` as a sibling, not a parent, and the applicant route at `/applications` continues to render `ApplicationFormRoute`. `compat.spec.ts` continues to pass without modification.

### 4. Build pipeline

`containers/server-manager/Containerfile.web`, `containers/server-manager/Containerfile.api`, and `infra/scripts/build-channel-image.sh` are unchanged. β-ii adds:

- One new TS file: `services/web/src/features/officer/ApplicationDetailRoute.tsx`.
- One new Playwright spec: `services/web/tests/officer-detail.spec.ts`.
- Modifications to existing TS files: `services/web/src/app/router.tsx`, `services/web/src/api/client.ts`, `services/web/src/features/officer/ApplicationQueueRoute.tsx`, `services/web/src/features/officer/officer.module.css`.
- Modification to one Python file: `services/api/app/api/v1/endpoints/web.py`.

No new top-level npm package, no new Python dependency, no new build script, no new dist path, no nginx config change, no new build-arg. `npm run build` (Vite) and `pip install -e .` continue to work as before.

### 5. K3d image rollout / GitOps

- `infra/tests/validate_web_ui_local.sh` retains its β-i asserts (negative `/api/v1/...` grep, positive `client.ts` allowlist, contract fixture schema check, Playwright spec coverage check, `npm run build`, image build, live `curl` against `/api/me`). β-ii additions per proposal §3: extend the allowlist for the two new browser API paths (`/api/web/officer/applications/{id}` and `/api/web/officer/applications/{id}/transcript`) and add coverage for the new Playwright spec. The negative grep guard continues to pass.
- `infra/tests/e2e/run-fullstack.sh` is unchanged. The suite count stays at 19 (proposal §7 forbids adding a new e2e number).
- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml` is unchanged — **no new Authentik blueprint, no new application/provider/source/scope mapping**. The β-i `discord-pomerium` source remains the officer identity chain.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` gains exactly one new route entry (the `prefix: /applications/` route described in §2). FluxCD reconciliation of the InfisicalSecret is unchanged — one new route entry alongside the existing β-i entries.
- **No new Infisical secret, no new env var.** `DISCORD_OFFICER_OAUTH_CLIENT_ID` / `DISCORD_OFFICER_OAUTH_CLIENT_SECRET` were added in β-i; β-ii does not introduce additional secrets.

### 6. e2e suite

`infra/tests/e2e/tests/19-web-ui.sh`:

- `assert_public_submit_persisted` — preserved unchanged. Reads `web-ui-public-submit.json`, asserts `applications.state='queued'`, `members.kind='discord'`, applicant `discord_user_id` matches the fixture.
- `assert_officer_claim_persisted` — preserved unchanged. Reads `web-ui-queue-claim.json`, asserts owner ≠ applicant, owner `members.kind='discord'`, owner `discord_user_id` equals the bootstrap fixture officer id.
- `run_validator validate-web-ui` — preserved.
- `seed-authority-grants.mjs` invocation — preserved.
- `run-browser-flow.sh web-ui` — preserved; only the inner `infra/tests/e2e/lib/playwright/browser-flow.mjs` gains an officer-detail navigation step **after** the existing claim leg.
- `e2e_init "19-web-ui"` — preserved; the suite count stays at 19, satisfying the "extend test 19, do not add a new e2e number" rule (proposal Q6).

`infra/tests/e2e/lib/playwright/browser-flow.mjs` (proposal §7 step 1–4): after the `await row.getByText("claimed").waitFor(...)` line at `infra/tests/e2e/lib/playwright/browser-flow.mjs:160`, β-ii adds (a) navigation to `/applications/{claimed_application_id}`, (b) detail-metadata assertions (claimed state, owner id prefix, version, at least one response value), (c) a transcript assertion that the claim transition appears as a state-change entry. Result is written to `web-ui-detail.json` (sibling to `web-ui-queue-claim.json`) or appended to the existing artifact. None of these additions invalidate the existing claim-leg assertions.

`infra/tests/fixtures/web-ui/contract.json`: β-ii adds `routes.officer_detail`, `applications.detail.endpoint`, and `applications.transcript.endpoint` keys. Existing keys (`routes.public`, `routes.application_form`, `routes.officer_queue`, `routes.admin`, `auth.*`, `applications.queue`, `applications.claim`, `form.*`, `ui_libraries.*`) are preserved; consumers (`compat.spec.ts:loadContract`, `validate_web_ui_local.sh:assert_contract_fixture`) keep working because the contract loader uses optional/named-key access, not exclusive shape checks.

### 7. Python module surface

| Symbol | Pre | Post |
|---|---|---|
| `app.api.v1.endpoints.web.router` | exposes `GET /api/v1/web/admin/chapters`, `GET /api/v1/web/officer/applications`, `POST /api/v1/web/officer/applications/{id}/claim` | adds `GET /api/v1/web/officer/applications/{id}` and `GET /api/v1/web/officer/applications/{id}/transcript` |
| `app.api.v1.endpoints.web._build_officer_actor` | β-i officer actor builder | unchanged — proposal §6 reuses verbatim |
| `app.api.v1.endpoints.web._db` | β-i request-state DB accessor | unchanged |
| `app.api.v1.endpoints.web._parse_state_query` | β-i state query parser | unchanged |
| `app.api.v1.endpoints.applications._shared.raise_known_application_error` | β-i mapper (covers list/transition/etag errors) | unchanged — already handles the codes the new bridges raise (`application_not_found`, `authority_decision_denied`, `validation_error`) |
| `app.services.applications.read_application` | existing | unchanged — called by detail bridge as a Python function, not via HTTP |
| `app.services.applications.require_application_read_authority` | existing | unchanged — called by detail bridge after `read_application` |
| `app.services.application_transcript.read_application_transcript` | INIT-132 service | unchanged — called by transcript bridge |
| `app.services.application_messages.read_application_messages` | INIT-131 service (visibility filter) | unchanged — invoked transitively via `read_application_transcript` |
| `app.api.v1.endpoints.applications.transcript` | INIT-132 direct endpoint | unchanged |
| `app.api.v1.endpoints.applications.lifecycle.read_application_endpoint` | direct lifecycle endpoint | unchanged |
| Existing applicant-receipt service + dependency | unchanged | unchanged |
| `app.contracts.applications.ApplicationRead` / `ApplicationTranscriptRead` | existing contracts | unchanged — bridge returns the existing Pydantic models |

**Edits to existing exports: none.** β-ii adds two new bridge route handlers under the existing `app.api.v1.endpoints.web.router` (the only new public symbols). Every other symbol the bridge consumes is reused as-is. This satisfies the gate's "only new exports in `web.py` and `client.ts`" requirement.

The β-i dependency-tree guard `test_officer_endpoints_have_locked_actor_construction` (`services/api/tests/test_web_officer_applications.py:660-758`) is extended (proposal §7) to walk all four officer bridge routes (list, claim, detail, transcript) and continue to forbid `get_current_actor`, `CURRENT_ACTOR.get`, `verify_applicant_receipt`, and any callable that reads `applicant_receipt` from request cookies.

### 8. Frontend module surface

| Symbol | Pre | Post |
|---|---|---|
| `services/web/src/api/client.ts` exports | β-i: `applicationStateSchema`, `applicationScopeSchema`, `applicationReadSchema`, `applicationListReadSchema`, `applicationTransitionRequestSchema`, `applicationTransitionResponseSchema`, `ApiError`, `getJson`, `fetchCurrentPrincipal`, `fetchAdminChapters`, `fetchApplicantDiscordIdentity`, `fetchOfficerApplicationQueue`, `claimOfficerApplication`, `CurrentPrincipal`, `AdminChapterSummary`, `ApplicationState`, `ApplicationRead`, `ApplicationListRead` | adds `applicationTranscriptStateChangeEntrySchema`, `applicationTranscriptMessageEntrySchema`, `applicationTranscriptEntrySchema`, `applicationTranscriptReadSchema`, `TranscriptStateChangeEntry`, `TranscriptMessageEntry`, `TranscriptEntry`, `ApplicationTranscriptRead`, `fetchOfficerApplication`, `fetchOfficerApplicationTranscript`. Also tightens `applicationReadSchema` to enumerate the detail-rendered fields rather than rely on `.passthrough()` (proposal §5: includes `form_definition_id`, `form_version`, `form_snapshot`, `responses`, `queued_at`, `claimed_at`, `review_started_at`, `decided_at`, `withdrawn_at`, `created_at`, `updated_at` alongside the β-i fields). The schema remains structurally compatible with β-i consumers because the existing fields are preserved and additional optional/nullable fields parse cleanly under any existing β-i `.parse(...)` call site that already expected `.passthrough()` behavior. |
| `services/web/src/app/router.tsx` | β-i routes: `/`, `/applications`, `/applications/queue`, `/admin/chapters` | adds dynamic `/applications/$applicationId` route alongside existing routes |
| `services/web/src/features/officer/ApplicationQueueRoute.tsx` | β-i queue route component | adds row-level navigation affordance to `/applications/{id}` (proposal §3 "Modified files"); claim behavior unchanged. The existing `data-application-id` attribute, the `Claim` button, the state filters, the `Refresh` button, and the auth-state rendering remain intact, so the e2e claim leg in `browser-flow.mjs` continues to work without modification. |
| `services/web/src/features/officer/officer.module.css` | β-i queue layout | adds detail/transcript layout classes; existing classes unchanged |
| `services/web/src/features/public/ApplicationFormRoute.tsx`, `services/web/src/features/public/HomeRoute.tsx`, `services/web/src/features/admin/AdminChaptersRoute.tsx`, `services/web/src/main.tsx`, `services/web/src/app/providers.tsx`, `services/web/src/components/primitives/Button.tsx` | β-i / pre-β-i shapes | unchanged |

**Frontend module deletions: none.** β-i deleted `RuntimeApp.tsx`, `DarkNemesisForm.tsx`, `features/forms/schema.ts`, `features/forms/form.module.css`. β-ii does not delete any source file.

Cross-source reference check confirms the new symbols are net-additive: the existing `services/web/tests/officer-queue.spec.ts` and `services/web/tests/compat.spec.ts` consume only symbols from `client.ts` that β-i already exports; β-ii does not rename or remove any of them.

### 9. Database schema

NONE. Both new endpoints are read-only and call existing services (`read_application`, `read_application_transcript`, `read_application_messages`) that operate on existing tables (`applications`, `aggregate_heads`, `activity_state_changes`, `application_messages`). No migration is added or modified.

### 10. Permission namespace

NONE. The detail bridge reuses `require_application_read_authority`, which the existing direct lifecycle endpoint already enforces (`services/api/app/api/v1/endpoints/applications/lifecycle.py:109-122`); read authority is applicant identity or any application review/decision permission on the target scope (`services/api/app/services/applications.py:159-168`). The transcript bridge reuses `read_application_transcript` → `read_application_messages`, which lets the applicant see applicant-visible messages and lets officers with `application.message` authority see both visibilities. **No new permission name is introduced.** Proposal §8 anti-scope explicitly rules out new permission names.

### 11. Authority grants

NONE issued by the slice itself. The slice runs against the existing β-i e2e seed (`infra/tests/e2e/lib/seed-authority-grants.mjs`) which grants `application.review` + `application.claim` on the resolved officer member UUID. Read authority on the application target scope is implied by `application.review` (which is in the read-authority decision set in `services/api/app/services/applications.py:365-390`); message authority on the transcript path is `application.message`, which the proposal flags is required for officers to see message entries (officer-only message visibility on the transcript bridge returns 403 if absent). **β-ii does not introduce a new auto-grant or new authority issuance path** beyond what β-i already seeds. Whether the e2e harness needs to seed `application.message` in addition to `application.review` / `application.claim` is an e2e operator decision (proposal §6 step 8), not a runtime authority change.

## Verdict reasoning

LOW. Every supported surface this slice touches is preserved or extended additively:

1. **HTTP API**: two net-new bridge endpoints under `/api/v1/web/officer/...`; every existing direct and bridge endpoint (including `/api/v1/applications/*`, `/api/v1/applications/{id}/transcript`, `/api/v1/web/officer/applications`, `/api/v1/web/officer/applications/{id}/claim`, applicant `/api/v1/public/applications`, and `/auth/discord/*`) is untouched. Bridges call services as Python functions, not HTTP self-calls, preserving the β-i pattern.
2. **Pomerium routing**: exactly one new entry (`prefix: /applications/`) is inserted between the β-i queue routes and the existing `/admin` prefix. The trailing-slash discipline keeps bare `/applications` on the public catch-all, the β-i `path: /applications/queue` and `prefix: /applications/queue/` win on first-match for the queue surface, and only `/applications/<uuid>` (and any future detail-owned children) becomes auth-gated. Every existing static Pomerium test passes against the post-β-ii order without modification; β-ii adds positive coverage for the new prefix.
3. **Applicant Discord OAuth flow**: `/auth/discord/*`, `applicant_receipt`, `/auth/discord/me`, `/api/v1/public/applications`, and `compat.spec.ts` are entirely unchanged; the slice adds no DOM tightening on the applicant route.
4. **Build pipeline / k3d / GitOps**: Containerfile.web, Containerfile.api, build-channel-image.sh, validate_web_ui_local.sh, run-fullstack.sh, and the FluxCD-reconciled blueprint configmap are untouched or extended additively (one Pomerium route entry, one validator allowlist extension). **No new env var, no new Infisical secret, no new Authentik blueprint.**
5. **e2e suite**: test 19 keeps its `assert_public_submit_persisted` and `assert_officer_claim_persisted` coverage; β-ii only adds detail/transcript navigation after the existing claim leg in `browser-flow.mjs`. Suite count stays at 19.
6. **Python module surface**: only new exports in `web.py` (two bridge route handlers); no edits to existing exports. The β-i `_build_officer_actor`, `raise_known_application_error`, `read_application`, `require_application_read_authority`, `read_application_transcript`, and `read_application_messages` are all reused as-is.
7. **Frontend module surface**: only additive `client.ts` exports (transcript schemas + two fetch functions), one new route component, one new Playwright spec, one router-table entry, additive CSS classes. The β-i `ApplicationQueueRoute.tsx` change is a row-level navigation affordance that does not alter existing claim, filter, refresh, pagination, or auth-state behavior, so the existing `services/web/tests/officer-queue.spec.ts` and the `browser-flow.mjs` claim leg keep passing. **No frontend module deletions.**
8. **Database schema, permission namespace, authority grants**: zero change in all three.

The single behavioral change beyond pure preservation is that any path under `/applications/` other than `/applications/queue` (e.g. `/applications/queue-foo`, `/applications/<uuid>`) now requires authentication. No documented or supported surface lives at those paths today, so this is intentional gating of the officer detail surface, not a regression. With the β-i invariants extended over the new bridge routes (officer dependency-tree guard, `applicant_receipt` cookie ban, `X-Actor-*` header ban, contract Zod schemas, route-order static tests), every supported surface this slice touches stays backward-compatible.

SUPPORTED_SURFACE_DONE: plans/risk/init-133B-ii-supported-surface.md
