# Public Application Intake Proposal

## Summary

Add a deliberately named unauthenticated public application submission path for the existing public web form, backed by the same Postgres `applications` lifecycle used by the API-backed Discord submission service. The change reduces the current supported-surface risk where `https://web.local.humility.local/applications` appears to submit but only works against fixture-backed tests and fails against the real API with missing actor identity and mismatched payload shape. The deployment cohort is the local channel first, with the same code and channel-template contract carried for remote channel materialization when remote application workloads are enabled.

## Net-value statement

This proposal has positive net value if the public intake surface is accepted as a supported surface: it turns the already-exposed public web submit path from a fixture-only promise into a real, audited API path. The specific current-state risk reduced is that public web users can reach the application form, but the real proxied request becomes `POST /api/v1/applications`, lacks actor context, sends `character_name` / `application_text` instead of `ApplicationSubmission`, and is rejected before it can create a durable application (`.tmp/rca/public-application-intake-FINDINGS.md:11-14`; `research/02-public-application-intake-problem-map.md:24-37`). The added blast radius is a new public POST surface, synthetic applicant member rows, Cedar policy coverage for a public action, and ingress rate-limit configuration touching the web and direct API hosts (`research/02-public-application-intake-problem-map.md:44-56`). That migration burden is justified only with day-1 rate limiting, explicit audit stamping, and tests proving adjacent protected routes still require auth.

## Scope

- Add a public API route, `POST /api/v1/public/applications`, for unauthenticated public intake.
- Add public request/response contracts in `services/api/app/contracts/applications.py`.
- Add an API service path that maps a public submission into the existing `submit_application` behavior using a synthetic applicant member and an audit service actor.
- Add repository/service support for creating or reusing synthetic public applicant members.
- Update the public SPA submit payload and response handling in `services/web/src/main.tsx` to call the deliberate public route through the existing `/api/` web proxy.
- Update the web contract fixture so the fixture binds to the new public route and response envelope.
- Add Cedar policy/matrix entries for the public submit action.
- Add Kong rate-limiting configuration for the public submit path in local GitOps and require the same channel-template contract for remote.
- Add tests before implementation for public route success, malformed payloads, duplicate/idempotent submission, audit stamping, policy fixture coverage, ingress rate-limit binding, and adjacent-route auth preservation.

## Anti-scope

- No changes to the legacy SQLite-backed root `daemon/applications.py` `/apply` implementation.
- No Authentik anonymous/sentinel-user stage.
- No Cedar tenant-policy redesign or tenant isolation model change.
- No protected admin route behavior change.
- No change to `POST /api/v1/applications`; it remains authenticated and actor-header based.
- No Discord-visible queue message, private thread, role, channel, DM, kick, ban, or permission mutation in this slice.
- No applicant Discord OAuth linking or conversion flow.
- No officer review UI move out of Discord.
- No compatibility shim that keeps both `/api/applications` as a hidden backend route and the new public route. The SPA fixture and code move to the deliberate public route.

## Product decisions to surface

### A1. Authentication / Identity Model For The Public Form

Option 1: Anonymous Cedar principal on a deliberately named public route.

- Shape: `POST /api/v1/public/applications` does not require `X-Actor-*` headers. The endpoint authorizes a fixed public principal such as `Public::"web-intake"` for `Action::"application:submit_public"` on `Resource::"server-manager-api:public-applications"` through the existing Cedar client path.
- Security blast radius: any internet-reachable caller that reaches the route can attempt submissions. Blast radius is limited by the route name, request schema, rate limit, response envelope, and service-layer validation. It does not grant access to authenticated application lifecycle routes.
- Cedar / service-identities delta: add allow/deny cases to `infra/tests/fixtures/contracts/access_policy_matrix.yml` and matching policy JSON in `policy/cedar/channels/{channel}/services/server-manager-api/policies.json`; no service identity entry is added because there is no authenticated service principal.
- Rate-limit posture: mandatory Kong rate limit on both web-host `/api/applications` and direct API-host `/api/v1/public/applications`, because Cedar does not identify a caller-specific principal.
- Tradeoff: simplest for the current static SPA/nginx shape, but it creates a true public write surface and relies on ingress limits plus application validation for abuse control.

Option 2: Service-account JWT minted or attached by the web pod.

- Shape: the browser posts to the web pod; the pod forwards to the API with a service JWT mapped to `Service::"public-intake.<channel>"`.
- Security blast radius: callers cannot directly exercise the API route without a valid service token, assuming the direct API ingress also enforces token verification. Compromise of the web pod or token allows all public-intake writes until rotation.
- Cedar / service-identities delta: add a `public_intake_web` entry to `service-identities.json`, add `Action::"application:submit_public"` to that identity, and add allow/deny matrix cases for that service.
- Rate-limit posture: still requires Kong limiting on the public web path; API-side rate limiting can key on service identity but cannot distinguish individual applicants without additional client signals.
- Tradeoff: tighter API authentication and uses existing Service principal patterns, but it requires a real server-side web forwarding component or robust token injection/rotation. The current web workload is a static nginx SPA proxy (`containers/server-manager/nginx-web.conf:8-20`), so this is more infrastructure work.

Option 3: Authentik anonymous sentinel identity populated by Pomerium.

- Shape: Pomerium injects an authenticated sentinel identity for the public route, and the API maps it to a fixed actor.
- Security blast radius: public route writes are coupled to Authentik/Pomerium session behavior. Mistakes in route matching could blur public and authenticated admin/API surfaces.
- Cedar / service-identities delta: add a sentinel `User::"anonymous-public-intake@<channel>"` or equivalent to policy/matrix, no service identity entry.
- Rate-limit posture: Kong limit remains mandatory; Authentik/Pomerium identity does not create a useful per-person abuse key for anonymous traffic.
- Tradeoff: keeps all ingress identity flowing through Pomerium, but it makes anonymous public traffic look like an authenticated user and adds IdP complexity for a route whose product requirement is unauthenticated.

Recommendation: Option 1. The current public form is already admitted through the web host without Pomerium identity, and the static web pod can proxy `/api/` without new server-side token machinery (`research/02-public-application-intake-problem-map.md:24-25`, `containers/server-manager/nginx-web.conf:8-20`). A deliberately named public route with a public Cedar action is the most honest representation of the surface. The recommendation is conditional on day-1 Kong rate limiting and adjacent-route tests; without those, this option should not pass risk.

### A2. Applicant Identity / Persistence Model

Option 1: Synthetic placeholder member per public submission.

- Schema delta: no `applications` FK change is required. Add service/repository logic to create a `members` row whose `discord_user_id` is `public:<submission_token_hash>` and whose UUID becomes `applications.applicant_id`.
- FK/uniqueness consequences: satisfies `applications.applicant_id -> members.id` and preserves the existing `applications` table, form snapshot, state, review ledger, and `(applicant_id, client_application_id)` duplicate protection (`migrations/versions/wu-022_applications.py:19-118`). It pollutes `members` with non-Discord subjects because `members.discord_user_id` is currently unique and has no native anonymous/pending status (`migrations/versions/wu-011_members.py:17-43`).
- Audit actor requirement: audit rows use `actor_kind="service"` and `actor_id="public-intake"`; the synthetic member is the applicant subject, not the actor.
- Tradeoff: smallest application-domain change and immediate convergence with Postgres `applications`, but it requires clear naming and tests so synthetic public members are not mistaken for real Discord roster members.

Option 2: Separate `pending_applications` table until Discord OAuth link.

- Schema delta: add `pending_applications` with public responses, target scope, request metadata, timestamps, and later conversion fields. `applications` is written only after a real Discord member is linked.
- FK/uniqueness consequences: avoids fake members and keeps `applications.applicant_id` honest, but public submissions do not immediately share the existing `applications` records, review state, or duplicate semantics.
- Audit actor requirement: pending writes still need `actor_kind="service"` and `actor_id="public-intake"` if written through the mutation substrate, or a new audit path if not.
- Tradeoff: cleaner identity model long term, but it fails the near-term convergence goal with the existing Discord API submission service and creates a second intake state machine.

Option 3: Require Discord OAuth before web submit.

- Schema delta: no new persistence shape. The web form obtains a real Discord member identity first, then posts through authenticated application submission.
- FK/uniqueness consequences: preserves real `members` semantics and duplicate protection.
- Audit actor requirement: audit actor can be the real user actor.
- Tradeoff: strongest identity model, but it rejects the unauthenticated public intake contract and turns `/applications` into an auth handoff.

Recommendation: Option 1. The durable v1 fallback note says richer web forms, if used, must share the application form and application records and keep Discord as the review surface (`proposals/01-v1-scope.rev1.md:500-504`). The current API-backed Discord service already writes Postgres `applications` (`services/discord/app/handlers/application_submission.py:47-93`). A synthetic placeholder member is the only option here that creates the same records immediately without adding an OAuth prerequisite. The residual identity pollution is real and is captured in the assumption register and follow-up scope.

### A3. Web Form Scope: Fallback Or First-class

Option 1: Treat web as fallback only.

- Tradeoff: aligns with the v1 note that web replaces Discord intake only if Discord components cannot handle required inputs (`proposals/01-v1-scope.rev1.md:500-504`), but it leaves the already-exposed R.22 `/applications` contract as a fixture-only surface unless that route is removed.

Option 2: Treat web as a first-class intake surface for submission, while Discord remains first-class for review.

- Tradeoff: aligns with the R.22 recovery contract and fixture that expose `/applications` and `POST /api/applications` as supported web behavior (`proposals/01-recovery-test-first.md:397-413`, `proposals/01-recovery-test-first.md:893-914`, `infra/tests/fixtures/web-ui/contract.json:36-58`). It widens the public write surface and requires rate limiting and audit treatment.

Recommendation: Option 2. The current supported surface already includes a public web form path, and the RCA shows the risk is that this visible path is not backed by a real API contract (`.tmp/rca/public-application-intake-FINDINGS.md:11-33`). This proposal makes web first-class only for applicant submission. Discord remains the review, claim, decision, and later interview surface.

### A4. Discord-flow Convergence Target

Option 1: Converge with legacy SQLite-backed `/apply`.

- Tradeoff: follows the older Discord-first proposal in `proposals/18-applications.md`, but the current code path is incomplete and stores drafts in SQLite/in-memory session state rather than the API-backed `applications` lifecycle (`research/02-public-application-intake-problem-map.md:26`, `research/02-public-application-intake-problem-map.md:40`).

Option 2: Converge with the Postgres-via-API Discord submission service.

- Tradeoff: uses the current service handler that resolves a Discord member and posts `ApplicationSubmission` to `/api/v1/applications` with actor headers (`services/discord/app/handlers/application_submission.py:47-93`). It leaves the legacy `/apply` path unchanged until a later migration/deletion proposal.

Recommendation: Option 2. Public web intake and Discord intake should converge on Postgres `applications`, the current API submission state machine, and shared review records. The legacy SQLite path remains anti-scope.

## Implementation decisions taken in proposal

### B1. Public Success Response Shape

Chosen: return a small envelope, not full `ApplicationRead`.

```
{
  "message": "Application received",
  "application_id": "<uuid>"
}
```

Justification: the fixture only requires the message (`infra/tests/fixtures/web-ui/contract.json:52-58`), while full `ApplicationRead` exposes applicant UUID, form snapshot, responses, state timestamps, owner fields, and version intended for authenticated API callers (`services/api/app/contracts/applications.py:323-342`). The public response should give enough support/debug value without leaking the full application record. No ETag is returned from the public route because public submit is create-only and does not authorize follow-up transitions.

### B2. Audit Posture

Chosen: public submissions stamp `actor_kind="service"`, `actor_id="public-intake"`, and `request_surface="api:/api/v1/public/applications"`.

Justification: `activity_actions.actor_kind`, `actor_id`, and `request_surface` are non-null (`migrations/versions/wu-002_activity_substrate.py:17-49`), and application routing writes `application_reviews.actor_kind` / `actor_id` during the `route` transition (`services/api/app/services/applications.py:715-730`). Anonymous browser users are not authenticated actors, so the actor should be the intake service path; the synthetic member is recorded separately as `applicant_id`.

### B3. Rate-limit / Abuse Control Day 1

Chosen: Kong `KongPlugin` rate-limiting binding is required on day 1.

Justification: there is no visible application-specific Kong plugin today (`research/02-public-application-intake-problem-map.md:42`), and the recommended auth model intentionally allows unauthenticated callers to reach the public route. Application-level validation still exists, but it is not sufficient as the first resource boundary. A residual risk remains: IP-based or route-level Kong limiting does not prove human uniqueness and can be bypassed by distributed traffic.

### B4. Local + Remote Channel Representation

Chosen: local gets concrete GitOps manifests; remote gets the same channel-template contract, not a local-only route exception.

Justification: the current live proof target is local, while remote channel config exists as plan/contract rather than an applied workload (`research/02-public-application-intake-problem-map.md:67-72`). The local channel should add path-specific Kong rate-limit bindings for `web.local.humility.local/api/applications` and `api.local.humility.local/api/v1/public/applications`. Remote should use the same logical resources with channel-derived hosts once remote application GitOps is materialized; no code path may depend on `local`.

### B5. Test-intent Track

Chosen: split tests by risk level.

Justification: contract and mapper behavior can be unit-tested; application write/audit behavior needs database-backed component tests; Cedar and GitOps fixtures need particular-integration tests; the web-to-cluster path needs end-to-end proof because previous R.22/R.26 tests passed through Playwright interception rather than the live API (`.tmp/rca/public-application-intake-FINDINGS.md:31-33`).

## Design

### API Route, Contract, And Authorization Model

Add `POST /api/v1/public/applications` under a new public applications router module, included from the existing v1 router. The endpoint must not use `Depends(get_current_actor)`. It must:

1. Validate `PublicApplicationSubmission`.
2. Authorize the fixed public principal through Cedar using `Action::"application:submit_public"` and `Resource::"server-manager-api:public-applications"`.
3. Derive or create a synthetic applicant member for the public submission.
4. Build an internal `ApplicationSubmission`.
5. Call the application service path with `ActorIdentity(actor_kind="service", actor_id="public-intake")`.
6. Return `201` with `PublicApplicationSubmissionReceipt`.

Proposed public request:

```json
{
  "scope": {"scope_kind": "global", "scope_id": null},
  "responses": {
    "character_name": "Test Applicant",
    "application_text": "I want to join scheduled guild activities."
  },
  "client_application_id": "optional-client-token"
}
```

Contract rules:

- `scope` is required. The day-1 web fixture uses global scope because the current fixture has no chapter selector.
- `responses` must be a non-empty object and is validated against the current form definition by the existing application response validator.
- `client_application_id` is optional but, when present, is trimmed and used for idempotency with the synthetic applicant.
- Extra fields are forbidden, matching the current `_ApplicationModel` contract style (`services/api/app/contracts/applications.py:14-20`).

The existing authenticated `POST /api/v1/applications` route remains unchanged: it requires actor context, accepts `ApplicationSubmission`, returns `ApplicationRead`, and sets ETag (`services/api/app/api/v1/endpoints/applications/lifecycle.py:26-41`).

### Persistence: Schema Deltas, Applicant Identity Model, Audit Stamping

Use the existing `applications` table and existing submit state machine. The public service path creates or reuses a synthetic member row before calling the existing submit logic. No new `applications` FK or state column is added.

Synthetic applicant rules:

- Generate a server-side `public_submission_id` UUID for each accepted public submission unless `client_application_id` maps to an existing synthetic applicant/application pair.
- Store the member as `discord_user_id = "public:" || sha256(public_submission_id || channel_salt)` and `status = "active"` because `members.status` currently permits only `active`, `suspended`, and `departed` (`migrations/versions/wu-011_members.py:17-43`).
- Use the synthetic member UUID as `applications.applicant_id`.
- Set internal `ApplicationSubmission.client_application_id` to the submitted client id when provided; otherwise set it to `public:<public_submission_id>` so duplicate retries through the same token can return 409 with the existing duplicate semantics.

Audit rules:

- `application.submit` and the immediate `route` transition both use `ActorIdentity(actor_kind="service", actor_id="public-intake")`.
- `request_surface` is `api:/api/v1/public/applications`, not the authenticated route string currently used by `submit_application` (`services/api/app/services/applications.py:578-610`).
- Request audit payload remains redacted by `APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST`; the state change continues to store the authoritative application fact (`services/api/app/services/applications.py:135-143`, `services/api/app/contracts/mutations.py:1-19`).

Implementation implication: the current `submit_application` hardcodes `request_surface="api:/api/v1/applications"` and calls `_require_submit_authority` (`services/api/app/services/applications.py:244-260`, `services/api/app/services/applications.py:578-610`). The implementation should factor a private internal helper that accepts `request_surface` and a `skip_user_submit_authority` or `submission_authority="public_intake"` enum. It must not create a second parallel submit state machine.

### SPA: Payload And Response Handling

Update `services/web/src/main.tsx` so `/applications` posts to `/api/public/applications`. The nginx proxy maps that to API `/api/v1/public/applications` under the existing `/api/ -> /api/v1/` rule (`containers/server-manager/nginx-web.conf:8-20`).

The form can keep the two visible fields for day 1, but the payload changes from:

```json
{"character_name": "...", "application_text": "..."}
```

to:

```json
{
  "scope": {"scope_kind": "global", "scope_id": null},
  "responses": {
    "character_name": "...",
    "application_text": "..."
  },
  "client_application_id": "<browser-generated submission token>"
}
```

The response handler should read `message` and may render `application_id` for support visibility. It should not depend on `ApplicationRead` fields.

### Discord Convergence

The canonical Discord convergence target is the API-backed service handler in `services/discord/app/handlers/application_submission.py`. It already resolves a Discord user to a member, posts `ApplicationSubmission` to `/api/v1/applications`, passes user actor headers, and handles duplicate `client_application_id` responses (`services/discord/app/handlers/application_submission.py:47-93`; `services/discord/tests/test_application_submission.py:66-91`).

Public web and Discord submissions therefore share:

- `form_definitions` lookup and immutable form snapshot.
- `applications` rows.
- `application_reviews` route row.
- aggregate version behavior; accepted submit plus route yields queued state and version 2, as current tests expect for authenticated submit (`research/02-public-application-intake-problem-map.md:22`).

They differ only in applicant identity and actor identity: Discord uses a real member applicant and user actor; public web uses a synthetic member applicant and `public-intake` service actor.

### Pomerium / Cedar / Service-identities Deltas

Pomerium:

- Keep `web.local.humility.local` public except `/admin`, matching current config (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-62`).
- Do not add Pomerium identity headers for the public route.
- Do not change `protected-api.local.humility.local`.

Cedar:

- Add policy/matrix cases for the public action:
  - allow `Public::"web-intake.local"` to perform `Action::"application:submit_public"` on `Resource::"server-manager-api:public-applications"`;
  - deny that same principal for `Action::"api:read"` on `Resource::"server-manager-api"`;
  - deny ordinary sample/other users for `Action::"application:submit_public"` unless explicitly added later.
- Mirror the policy into the GitOps OPAL/Cedar ConfigMap path the access-policy validator already compares (`research/02-public-application-intake-problem-map.md:53`).

Service identities:

- No service identity entry is added for the recommended anonymous-public model.
- If the user selects the service-account JWT model instead, this proposal must be revised before risk gating because service identity issuance, web token forwarding, and API token verification become implementation scope.

### Kong / Rate-limit Posture

Add a Kong `rate-limiting` plugin for the public submit path with conservative local defaults, for example minute-level and hour-level caps keyed by IP/consumer as supported by the deployed Kong mode. Bind it path-specifically:

- `web.local.humility.local` path `/api/applications`, because this is the browser-visible route.
- `api.local.humility.local` path `/api/v1/public/applications`, because the direct API ingress currently exposes the API service (`research/02-public-application-intake-problem-map.md:64`).

The binding should be separate from the catch-all web ingress so static SPA loads are not rate-limited with the submission budget. The direct authenticated `POST /api/v1/applications` route should not inherit this public limit unless a separate authenticated API rate-limit proposal chooses that later.

## Supported-surface track

Deployment mode:

- Local channel is the first runtime target and must receive concrete API, web, Cedar, and Kong changes.
- Remote channel gets the same channel-template contract and fixture expectations; remote apply remains out of scope until the remote application workload channel is materialized (`research/02-public-application-intake-problem-map.md:67-72`).

Customer cohort:

- Public unauthenticated prospective applicants using `https://web.local.humility.local/applications`.
- Officers/reviewers are an adjacent cohort because accepted public submissions enter the same queued application records, but this slice does not change review commands or Discord-visible messages.

Adjacent public or user-reachable paths:

- `https://web.local.humility.local/` remains the public SPA shell.
- `https://web.local.humility.local/applications` remains the public form and now submits to the real public API path.
- `https://web.local.humility.local/admin/chapters` remains Pomerium-authenticated.
- `https://protected-api.local.humility.local/api/v1/protected/authz-proof` remains Pomerium-authenticated and Cedar-checked.
- `https://api.local.humility.local/api/v1/applications` remains the authenticated direct API route; `https://api.local.humility.local/api/v1/public/applications` becomes the new public direct API route with Kong rate limiting.

Blast-radius notes for unchanged adjacent paths:

- Authenticated `POST /api/v1/applications` keeps `Depends(get_current_actor)`, the `ApplicationSubmission` request shape, full `ApplicationRead` response, and ETag behavior.
- The Discord submission service remains on `/api/v1/applications` and should not learn the public route.
- Protected admin/API routes keep Pomerium identity requirements.
- The web shell remains public; only the submit path gains write behavior.

Migration path:

1. Add tests and contracts for the public route, public response envelope, policy fixture, synthetic applicant behavior, and GitOps rate-limit binding.
2. Add API contract and service helper.
3. Add public endpoint and Cedar authorization check.
4. Update SPA and fixture to `/api/public/applications`.
5. Add local Kong plugin/bindings and Cedar policy/configmap deltas.
6. Run API tests, web tests, policy validation, GitOps static validation, and local e2e without Playwright route fulfillment for submit.
7. Deploy local and verify the browser form returns `201`, an application row exists in `queued`, audit rows carry `public-intake`, and adjacent protected routes still reject unauthenticated requests.

Rollback path:

- Revert the SPA fixture/code to stop calling the public route or temporarily return a static "submission unavailable" state from the form.
- Remove the public API route registration.
- Remove the Cedar public action policy and matrix entry.
- Remove the path-specific KongPlugin bindings.
- Leave already-created `applications`, `application_reviews`, audit rows, and synthetic `members` intact for audit integrity. A later data cleanup proposal may mark synthetic members departed only if it proves no application record still depends on them.

Observability:

- Every accepted public submit creates `activity_actions` for submit and route under the request correlation id.
- The API response includes `X-Correlation-Id` from the existing correlation middleware (`services/api/app/core/context.py:111-133`).
- Request logs should include route, status, correlation id, and rate-limit status; logs must not print raw response bodies.
- Audit queries can trace the application aggregate by correlation id and `request_surface="api:/api/v1/public/applications"`.

## Assumption register

AS-1: The public web `/applications` route is a supported surface, not just a demo page. Evidence: R.22 names web routes, form submit, auth-gated API behavior, and local ingress as contract surface (`proposals/01-recovery-test-first.md:397-413`, `proposals/01-recovery-test-first.md:893-914`), and the fixture defines `/applications` plus submit expectations (`infra/tests/fixtures/web-ui/contract.json:36-58`). Invalidated by: a product decision removing public web intake from supported scope or reverting it to a non-submitting landing page.

AS-2: A synthetic member is acceptable for anonymous submissions until a real applicant identity/linking model exists. Evidence: `applications.applicant_id` is non-null and FK-backed to `members.id` (`migrations/versions/wu-022_applications.py:19-56`), and the v1 fallback note requires web fallback to use the same application records (`proposals/01-v1-scope.rev1.md:500-504`). Invalidated by: a user decision requiring Discord OAuth before submit or a prior approved identity model that forbids non-Discord member rows.

AS-3: The current form for the public route can be represented as global scope for day 1. Evidence: the current web fixture has no chapter/scope input (`infra/tests/fixtures/web-ui/contract.json:36-58`), while `ApplicationSubmission` requires a scope and the service looks up a current form by scope (`services/api/app/contracts/applications.py:200-204`; `services/api/app/services/applications.py:492-499`). Invalidated by: an existing seeded current form only for chapter scope, or a product decision that public applications must always target a selected chapter.

AS-4: Cedar can represent a public/anonymous principal for the public action in the local policy bundle. Evidence: the current policy bundle is a JSON list of Cedar permit statements and the access matrix already validates named principal/action/resource decisions (`policy/cedar/channels/local/services/server-manager-api/policies.json:1-26`; `infra/tests/fixtures/contracts/access_policy_matrix.yml:1-37`). Invalidated by: OPAL/Cedar bootstrap rejecting the `Public::"web-intake.local"` entity type or a policy schema that permits only `User`, `Service`, and `Tenant`.

AS-5: Kong path-specific plugin binding can protect the submit route without throttling all public web assets. Evidence: the web ingress is a Kong ingress to Pomerium and the problem map found no existing app-specific rate-limit binding (`gitops/channels/local/auth/pomerium/ingress.yaml:61-89`; `research/02-public-application-intake-problem-map.md:42`). Invalidated by: local Kong/KIC version or ingress composition not supporting path-specific plugin behavior as proposed.

AS-6: The API-backed Discord application submission service is the canonical convergence path. Evidence: the newer Discord handler posts to `/api/v1/applications` and tests pin that shape (`services/discord/app/handlers/application_submission.py:47-93`; `services/discord/tests/test_application_submission.py:66-91`), while legacy `/apply` is incomplete and SQLite-backed (`research/02-public-application-intake-problem-map.md:26`, `research/02-public-application-intake-problem-map.md:40`). Invalidated by: a user decision to revive SQLite `/apply` as canonical before public web intake implementation.

## Test-intent track

### Residual-risk artifact

Step 6b MUST emit `plans/risk/init-120-test-residuals.md` if any named test-intent risk below cannot be verified by the test set. Each residual entry must include the residual class, technique attempted, scope, budget/bound, result, remaining residual, invalidating inputs, and whether the residual changes the net-value case.

Public contract validation.

- Change or verification risk: the public route accepts the old fixture payload accidentally or returns full `ApplicationRead`.
- Intended behavior: `PublicApplicationSubmission` requires `scope` and non-empty `responses`, forbids extra fields, validates optional `client_application_id`, and `PublicApplicationSubmissionReceipt` contains only `message` and `application_id`.
- Selected level: unit.
- Fixture source/application point: new contract examples derived from `infra/tests/fixtures/web-ui/contract.json:36-58`.
- Assumption link: AS-1, AS-3.
- Expected observable signal: Pydantic validation passes/fails on exact cases; response model dump has no applicant/form/response/state fields.
- Residual risk: does not prove database writes or ingress routing.

Synthetic applicant persistence.

- Change or verification risk: public submissions cannot satisfy `applications.applicant_id` or pollute real Discord identity handling unpredictably.
- Intended behavior: service creates a `members.discord_user_id` with `public:` prefix, reuses the intended synthetic subject for idempotent retry when applicable, and never requires a Discord user id.
- Selected level: component.
- Fixture source/application point: migrated test database with `members` and `applications` migrations.
- Assumption link: AS-2.
- Expected observable signal: a synthetic member row exists, application row references it, and unique constraints hold.
- Residual risk: does not prove long-term roster/trust UX around synthetic members.

Public submit creates queued application through existing lifecycle.

- Change or verification risk: implementation builds a parallel submit path that skips validation, form snapshots, aggregate versioning, or route review rows.
- Intended behavior: public submit validates against current form, writes one `applications` row, transitions it to `queued`, returns 201 envelope, version is 2 internally, and creates one `application_reviews` route row.
- Selected level: component.
- Fixture source/application point: existing application test seed helpers for current form/member, extended with synthetic member setup.
- Assumption link: AS-2, AS-3, AS-6.
- Expected observable signal: database row state `queued`; audit/state change rows exist; review row action `route`.
- Residual risk: does not prove browser or ingress path.

Public audit stamping.

- Change or verification risk: anonymous submit violates non-null audit actor requirements or incorrectly impersonates the applicant.
- Intended behavior: submit and route audit/review records use `actor_kind="service"`, `actor_id="public-intake"`, and `request_surface="api:/api/v1/public/applications"`.
- Selected level: component.
- Fixture source/application point: activity/audit substrate tables from migrations.
- Assumption link: AS-2.
- Expected observable signal: `activity_actions` and `application_reviews` rows match actor and surface values under one correlation id.
- Residual risk: does not prove log redaction.

Unauthenticated public API route behavior.

- Change or verification risk: public route still depends on actor headers, or authenticated route accidentally becomes public.
- Intended behavior: `POST /api/v1/public/applications` succeeds without `X-Actor-*` headers when Cedar allows; malformed payload returns 422; Cedar deny returns 403 or configured authz error; `POST /api/v1/applications` still returns `401 actor_identity_missing` without actor headers.
- Selected level: particular-integration.
- Fixture source/application point: `httpx.AsyncClient` against FastAPI app with fake Cedar authorizer.
- Assumption link: AS-1, AS-4.
- Expected observable signal: exact status codes and response bodies; no actor headers required on public route only.
- Residual risk: fake Cedar does not prove OPAL policy bootstrap.

Cedar policy and service-identity fixture coverage.

- Change or verification risk: policy bundle omits the public action, or service identities accidentally gain broad submit permission.
- Intended behavior: access matrix has allow for public submit principal and deny cases for unrelated actions/principals; service-identities remain unchanged for the anonymous-public recommendation.
- Selected level: particular-integration.
- Fixture source/application point: `infra/tests/fixtures/contracts/access_policy_matrix.yml`, `policy/cedar/channels/local/services/server-manager-api/policies.json`, GitOps OPAL ConfigMap.
- Assumption link: AS-4.
- Expected observable signal: existing access-policy validation passes and runtime OPAL `/v1/is_authorized` proves allow/deny.
- Residual risk: does not prove production remote policy until remote materialization exists.

Kong/Pomerium public route binding.

- Change or verification risk: rate limit is absent, bound to all web paths, or misses direct API ingress.
- Intended behavior: rendered local GitOps has path-specific Kong rate-limit binding for web `/api/applications` and direct API `/api/v1/public/applications`; admin and protected API ingress rules remain authenticated.
- Selected level: particular-integration.
- Fixture source/application point: `gitops/channels/local/auth/pomerium/ingress.yaml`, `gitops/channels/local/applications/server-manager/api-ingress.yaml`, new KongPlugin manifests.
- Assumption link: AS-5.
- Expected observable signal: kustomize/static validation finds plugin annotations/resources on the intended path resources and not on the catch-all web route.
- Residual risk: static render does not prove live Kong counters enforce limits under load.

SPA submit contract.

- Change or verification risk: web continues posting old payload to `/api/applications` or assumes full `ApplicationRead`.
- Intended behavior: form submit posts `/api/public/applications`, sends `scope` plus `responses`, and displays `message` from the envelope.
- Selected level: component.
- Fixture source/application point: `infra/tests/fixtures/web-ui/contract.json` and Playwright route fixture, updated outside test bodies.
- Assumption link: AS-1, AS-3.
- Expected observable signal: intercepted request path/body exactly match fixture; status panel shows `Application received`.
- Residual risk: route interception still does not prove live API.

Local end-to-end public submit.

- Change or verification risk: browser path, Pomerium public route, nginx proxy, API route, Cedar, database, and audit do not compose in the deployed local channel.
- Intended behavior: browser at `https://web.local.humility.local/applications` submits without Playwright route fulfillment, receives 201 envelope, and local verification finds the queued application plus audit chain.
- Selected level: end-to-end.
- Fixture source/application point: local channel deployment, web fixture values for form input, no API fake for submit.
- Assumption link: AS-1, AS-3, AS-4, AS-5.
- Expected observable signal: browser-visible success text, HTTP 201 in network trace, `X-Correlation-Id` response header, queued application row, public-intake audit rows.
- Residual risk: does not exercise real remote channel or Discord-visible review/thread side effects.

## Migration / rollback

Migration is additive until the SPA switches to the new route. Apply in this order: tests and fixtures, API contract/service/route, Cedar policy, Kong rate-limit manifests, SPA route change, then local runtime validation. The public route should not be deployed without the rate-limit binding and policy tests in the same PR because that would introduce an unbounded public write path.

Rollback removes reachability before removing data support: switch the SPA away from submit or disable the public route, then remove the route registration, then remove Kong and Cedar deltas. Do not delete audit rows, application rows, review rows, or synthetic members during rollback. They are part of the historical record. If the public route created bad data, a separate cleanup proposal must identify affected synthetic `public:` members and dependent applications before any mutation.

## Out of scope for follow-up

- Discord OAuth linking or conversion from synthetic public applicant to real Discord member: follow-up identity/linking proposal.
- Legacy SQLite `/apply` migration, deletion, or convergence: follow-up Discord application-flow modernization proposal.
- Authentik anonymous/sentinel route design: only needed if the user rejects the recommended A1 option.
- Service-account JWT web-pod model: only needed if the user selects A1 option 2.
- Public form builder, chapter selector, file uploads, or multi-page web forms: follow-up web application form proposal.
- Discord-visible queue embeds, private review thread creation, and applicant notifications for public web submissions: follow-up Discord review-side effects proposal subject to Tier 3 approval rules.
- Remote channel apply/runbook for public intake: follow-up deployment proposal once remote application GitOps is materialized.
