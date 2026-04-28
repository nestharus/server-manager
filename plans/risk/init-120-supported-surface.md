# INIT-120 Phase 4 — Supported-Surface Risk Report

READ:
- proposals/02-public-application-intake.md
- research/02-public-application-intake-problem-map.md
- .tmp/rca/public-application-intake-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- ~/ai/conventions/gate-ownership.md
- proposals/01-v1-scope.rev1.md (lines 490-520)
- proposals/01-recovery-test-first.md (lines 395-425, 885-915)
- services/api/app/api/v1/endpoints/applications/lifecycle.py
- services/api/app/services/applications.py (lines 230-260, 470-615)
- services/api/app/contracts/applications.py
- services/api/app/api/v1/router.py
- services/discord/app/handlers/application_submission.py
- migrations/versions/wu-011_members.py
- migrations/versions/wu-022_applications.py (lines 1-170)
- gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml
- policy/cedar/channels/local/services/server-manager-api/policies.json
- policy/cedar/channels/local/services/server-manager-api/manifest.yaml
- infra/tests/fixtures/contracts/access_policy_matrix.yml
- infra/tests/fixtures/web-ui/contract.json
- containers/server-manager/nginx-web.conf

## Inputs read

- Approved proposal `proposals/02-public-application-intake.md` (full).
- Approved problem map `research/02-public-application-intake-problem-map.md` (full).
- RCA findings `.tmp/rca/public-application-intake-FINDINGS.md` (full).
- Implementation-pipeline gate text and gate-ownership table.
- Verifying source files for the assumption register: lifecycle endpoint, application service, contracts, v1 router, discord submission handler, members migration, applications migration, Pomerium config, Cedar policies/matrix/manifest, web fixture, nginx proxy.

## Termination evaluation

Per impl-pipeline.md:106 the supported-surface gate owns the termination signal. Run before the LOW/MEDIUM/HIGH verdict.

### a) Invalidated assumption?

I cross-checked AS-1..AS-6 against current source. None is contradicted by live evidence:

- AS-1 cited evidence (R.22 contract surface, web fixture binding `/applications` and `POST /api/applications`) is current at `proposals/01-recovery-test-first.md:397-413`, `proposals/01-recovery-test-first.md:893-914`, and `infra/tests/fixtures/web-ui/contract.json:36-58`. Not invalidated.
- AS-2 cited evidence (`applications.applicant_id` non-null FK to `members.id`, v1 fallback uses same `applications` records) is current at `migrations/versions/wu-022_applications.py:51-56` and `proposals/01-v1-scope.rev1.md:500-504`. Not invalidated. Wrinkle: `members.discord_user_id` carries a unique constraint and `members.status` allows only `active|suspended|departed` (`migrations/versions/wu-011_members.py:35-42`); the proposal's `public:<hash>` + `status="active"` choice fits within that constraint.
- AS-3 cited evidence (web fixture has no chapter selector; `ApplicationSubmission` requires scope; service looks up current form by scope) is current at `infra/tests/fixtures/web-ui/contract.json:36-58`, `services/api/app/contracts/applications.py:200-204`, and `services/api/app/services/applications.py:492-499`. Not invalidated.
- AS-4 cited evidence (Cedar policy bundle is a JSON list of permit statements; matrix validates principal/action/resource decisions) is current at `policy/cedar/channels/local/services/server-manager-api/policies.json:1-26` and `infra/tests/fixtures/contracts/access_policy_matrix.yml:1-37`. Not invalidated. The manifest `manifest.yaml` is review-check metadata only and does not enforce a Cedar schema; introducing a new principal type `Public` is not blocked by repository state.
- AS-5 cited evidence (web ingress is a Kong ingress; no app-specific rate-limit binding present) is current. A rendered Kong CRD bundle is committed at `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`, so KongPlugin / `konghq.com/plugins` annotations are mechanically available. Not invalidated.
- AS-6 cited evidence (current Discord service handler posts `ApplicationSubmission` to `/api/v1/applications` with user actor headers and duplicate handling) is current at `services/discord/app/handlers/application_submission.py:47-93`. Not invalidated.

Decision: no `INVALIDATED_ASSUMPTION`.

### b) Non-positive net value on the supported surface?

The current-state risk named by the RCA is concrete and reproducible: the public web SPA renders `/applications`, posts `character_name` / `application_text` to `/api/applications`, the nginx proxy forwards to `/api/v1/applications`, and `Depends(get_current_actor)` returns `401 actor_identity_missing`; the entire R.22/R.26 web→API submit contract is fixture-fulfilled, not live. The proposal converts that fixture-only path into a real, audited Postgres write through the existing `submit_application` lifecycle.

Added blast radius is bounded:

- A new public POST is created on a deliberately named route, not a hidden bypass of `get_current_actor`. The authenticated `POST /api/v1/applications` keeps `Depends(get_current_actor)`, `ApplicationSubmission`, full `ApplicationRead`, ETag.
- Day-1 Kong rate-limit is mandatory and bound path-specifically to `web.local.humility.local/api/applications` and `api.local.humility.local/api/v1/public/applications`, so static SPA loads and authenticated direct API are not throttled with the public submit budget.
- Synthetic member rows are isolated by `discord_user_id = "public:" || sha256(...)` prefix and audit actor `("service","public-intake")`, distinguishable from real Discord roster members.
- Audit and review rows are written through the same activity substrate as authenticated submit, so an oncaller can trace by correlation id and `request_surface="api:/api/v1/public/applications"`.

Net value is positive even on a strict reading. Decision: no `NON_POSITIVE_VALUE`.

### c) Decision

`SUPPORTED_SURFACE_TERMINATION: NONE`.

## Existing-state risk reduction

The RCA names a single, narrow brittle behavior: web SPA submit posts to a route that exists only as a fixture and 401s against the real API.

The proposal reduces that risk credibly:

- Adds `POST /api/v1/public/applications` with a public Pydantic contract that does not require `Depends(get_current_actor)`.
- Authorizes via Cedar `Action::"application:submit_public"` against a new `Public::"web-intake.<channel>"` principal, not by skipping authority.
- Maps the public submission into the existing `submit_application` lifecycle through a refactored internal helper that accepts `request_surface` and a public-submission authority mode, rather than building a parallel state machine.
- Updates the SPA payload (`scope` + `responses`) and endpoint (`/api/public/applications`) to match the new contract, so the fixture no longer drifts from the live API.
- Updates the web fixture in lockstep, preventing R.22/R.26 tests from passing again on a fictional contract.

The post-condition the proposal commits to (browser sees 201 envelope, queued application row exists, `application_reviews` route row exists, audit rows show `actor_id="public-intake"` and `request_surface="api:/api/v1/public/applications"`) is the inverse of the failing pre-condition the RCA documented. The fix is faithful to the diagnosis.

## Adjacent-path blast-radius bounding

The proposal preserves each adjacent host named in the problem map:

- `https://web.local.humility.local/`: Pomerium rule unchanged, public unauthenticated SPA shell. The proposal explicitly does not relax `/admin` or change the catch-all public route definition.
- `https://web.local.humility.local/admin/chapters`: Pomerium `/admin` route remains `allow_any_authenticated_user`; the test-intent track names "adjacent-route auth preservation" as a required test.
- `https://protected-api.local.humility.local/api/v1/protected/authz-proof`: untouched. Pomerium identity headers, Cedar allow, no policy edits land on this resource.
- `https://api.local.humility.local/api/v1/applications`: authenticated route stays exactly as today (`Depends(get_current_actor)`, `ApplicationSubmission`, `ApplicationRead`, ETag); the Discord submission service continues to use this route. The new public route is a sibling under a different URL prefix, so no FastAPI route-prefix collision exists in `services/api/app/api/v1/router.py`.

The test-intent track explicitly pins:
- `POST /api/v1/applications` still returns `401 actor_identity_missing` without actor headers.
- Cedar matrix has deny cases for the public principal on `Action::"api:read"` and for sample/other users on `Action::"application:submit_public"`.
- KongPlugin static validation finds bindings only on the intended path resources, not the catch-all web route.

Blast radius is bounded.

## Migration and rollback realism

Migration order is sound and respects PR-co-deploy rule (proposal §7 and §"Migration / rollback"):

1. Tests, contracts, fixtures.
2. API contract + service helper.
3. Public endpoint + Cedar authorization check.
4. SPA + fixture endpoint move.
5. Local KongPlugin manifests + Cedar policy/configmap.
6. API/web/policy/GitOps validation, then local e2e without Playwright submit fulfillment.
7. Local deploy, browser-verified 201 plus queued row plus public-intake audit chain.

The proposal is explicit that the public route MUST NOT deploy without rate-limit binding and Cedar policy in the same PR (§"Migration / rollback"). That is the right co-deploy invariant for a new public write surface.

Rollback removes reachability before removing data support: SPA off-switch first, then route registration, then KongPlugin bindings, then Cedar deltas. Audit rows, application rows, review rows, and synthetic members are not deleted in rollback; a separate cleanup proposal is required if data needs to be touched. That preserves audit integrity and is consistent with the activity-substrate non-null actor invariants.

Note: PR-ordering is asserted as a convention in the proposal text rather than being structurally locked at the SLICE level. The remaining risk is human PR splitting; the test-intent track partially mitigates this because Cedar/Kong static validation in the same PR is gated by tests.

## Observability

The proposal reuses existing substrates rather than inventing new ones:

- `activity_actions` (with non-null `actor_kind`/`actor_id`/`request_surface` per `migrations/versions/wu-002_activity_substrate.py:17-49`) carries the public submit and route state changes.
- `application_reviews` carries the `route` row with `actor_kind="service"`, `actor_id="public-intake"`. The wu-022 CHECK at `application_reviews_reviewer_required` permits `route` without `reviewer_id`, so this composes.
- `X-Correlation-Id` flows from existing correlation middleware (`services/api/app/core/context.py:111-133`) — proposal references this directly.
- `request_surface` is distinct from authenticated submit (`api:/api/v1/public/applications` vs `api:/api/v1/applications`), enabling audit segmentation by surface.
- Logs are constrained to route/status/correlation/rate-limit-state with no raw response bodies, and the existing `APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST` continues to redact request payloads.

An oncaller can trace a public submission incident from a correlation id back to the synthetic applicant, the application aggregate, and the public-intake actor without touching ad-hoc log scraping. Observability is sufficient.

## Channel-template parity

B4 mandates concrete local manifests plus the same channel-template contract for remote, with no local-only route exception and no code path keyed off `local`. This is consistent with the user's environment-agnostic stack stance and with `docs/deployment-substrate.md:13-21`.

The proposal correctly notes that remote application GitOps is not yet materialized under `gitops/channels/dev/`, so remote apply is plan-only until a separate deployment proposal lands. The test-intent track does not claim remote runtime proof; particular-integration tests validate static GitOps render and the e2e test runs only against the local channel. That is the right scope.

The Pomerium config is hard-coded to `web.local.humility.local` / `protected-api.local.humility.local` today — the proposal does not edit Pomerium identity behavior, so no remote/local divergence is introduced at the auth layer.

## Assumption register cross-check

| AS-# | Cited evidence exists | Invalidation observable | Notes |
|---|---|---|---|
| AS-1 | Yes — `proposals/01-recovery-test-first.md:397-413, 893-914`, `infra/tests/fixtures/web-ui/contract.json:36-58` confirmed. | Yes — a product decision removing public web intake or reverting `/applications` to non-submitting. | Solid. |
| AS-2 | Yes — `migrations/versions/wu-022_applications.py:51-56`, `proposals/01-v1-scope.rev1.md:500-504` confirmed. `members.discord_user_id` is unique and `status` enum is `active|suspended|departed` per `migrations/versions/wu-011_members.py:35-42`. | Yes — user mandates Discord OAuth before submit, or a prior approved identity model forbids non-Discord member rows. | Synthetic member design fits the constraint. Residual: per-submission unique synthetic members can grow `members` unboundedly absent rate limit; AS-5/Kong is the bound. |
| AS-3 | Yes — `services/api/app/contracts/applications.py:200-204`, `services/api/app/services/applications.py:492-499`, `infra/tests/fixtures/web-ui/contract.json:36-58` confirmed. | Yes — current form seed exists only for chapter scope, or product decision public app must target a chapter. | Day-1 global-scope form is a seed dependency. The proposal acknowledges the form lookup will fail if no current global form is seeded. |
| AS-4 | Yes — `policy/cedar/channels/local/services/server-manager-api/policies.json:1-26`, `infra/tests/fixtures/contracts/access_policy_matrix.yml:1-37` confirmed. The manifest is review-check metadata only, not a Cedar schema. | Yes — OPAL/Cedar bootstrap rejecting a `Public` entity type, or a schema permitting only `User`/`Service`/`Tenant`. | No schema is enforced today, so the new entity type is permitted. The runtime is_authorized assertion in the test-intent track is the right invalidation observation. |
| AS-5 | Yes — `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml` is committed; `gitops/channels/local/applications/server-manager/api-ingress.yaml:9-12` carries only cert-manager annotations. | Yes — Kong/KIC version not supporting path-specific binding as proposed. | Kong CRDs are present. Path-specific KongPlugin binding is the standard KIC pattern and is feasible. |
| AS-6 | Yes — `services/discord/app/handlers/application_submission.py:47-93` confirms POST to `/api/v1/applications` with `ApplicationSubmission` shape and user actor headers. | Yes — user revives SQLite `/apply` as canonical. | Solid. |

No assumption is contradicted by current source.

## Notable observations

- The existing `submit_application` hardcodes `request_surface="api:/api/v1/applications"` at `services/api/app/services/applications.py:578` and `:610`, and routes through `_require_submit_authority` at `:244-260`. The proposal correctly identifies that the implementation must factor a private internal helper accepting `request_surface` and a public-submission authority mode. That is a refactor-with-callers concern, not a risk-gate concern, but it is the load-bearing design assumption that prevents a parallel submit state machine.
- The `application_reviews` CHECK in wu-022 (`action_in ('route','claim','review','approve','deny','withdraw')`) and the route-row reviewer requirement (`route` does not require `reviewer_id`) compose with `actor_kind="service"`, `actor_id="public-intake"`. Good.
- Synthetic `members` row growth is bounded by the public route's Kong rate limit. A per-`client_application_id` reuse of synthetic applicants is a sensible amplifier for retry idempotency, but care is needed: the duplicate constraint is `(applicant_id, client_application_id)`. The proposal needs the synthetic-applicant lookup to key on `client_application_id` (not `applicant_id`) for retries to dedupe to the same synthetic member. The proposal indicates this with "unless `client_application_id` maps to an existing synthetic applicant/application pair," but the exact lookup index is not yet defined. This is a follow-up implementation concern, not a risk-gate blocker.
- The R.22 web fixture (`/applications` → `POST /api/applications`) is moved to the new public route in lockstep. The proposal anti-scope rules out a hidden compatibility shim, which is the right call. This means the SPA endpoint move and the Cedar/Kong/API endpoint addition must land together to avoid the same fixture-only-contract failure mode the RCA documented.
- CSRF is not explicitly named, but the route is unauthenticated and the only effect is creating a synthetic application; abuse amplification is bounded by Kong rate limits and audit. Not a risk-gate concern at this scope.
- Pomerium does not change. Public web routes remain `allow_public_unauthenticated_access: true` and the new public submit fits inside the existing permitted host/path posture. No identity assumption shifts at the proxy.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
