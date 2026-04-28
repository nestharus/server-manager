READ:
- proposals/02-public-application-intake.md
- research/02-public-application-intake-problem-map.md
- .tmp/rca/public-application-intake-FINDINGS.md
- AGENTS.md
- ~/ai/conventions/no-backwards-compatibility.md
- ~/ai/conventions/no-deferred-stubs.md
- ~/ai/workflows/implementation-pipeline.md

# INIT-120 Phase 4 — Shortcut Risk Report

## Inputs read

- `proposals/02-public-application-intake.md` (full file)
- `research/02-public-application-intake-problem-map.md` (full file)
- `.tmp/rca/public-application-intake-FINDINGS.md` (full file)
- `AGENTS.md` presence confirmed
- Pipeline rules (Phase 4) and the no-backwards-compatibility / no-deferred-stubs conventions

## Root-cause fix vs. relocation

The RCA names the root cause as: the public web form's `/applications` submit path is fixture-backed in tests but unauthorized against the real API, with mismatched payload shape, missing actor headers, and no domain authority for an anonymous caller (`.tmp/rca/public-application-intake-FINDINGS.md:11-14, 27-33`). The RCA explicitly warns that "treating this as a test-fixture-only stub would preserve green component tests but leave the live cluster behavior undefined" (FINDINGS.md:29).

The proposal fixes that root cause rather than relocating it:

- A real `POST /api/v1/public/applications` route is added in the API service (proposal §Design "API Route, Contract, And Authorization Model"), not a route stub or fixture rebind.
- The SPA fixture and SPA code are both moved to the deliberate public route in the same slice (proposal §Scope, §SPA, anti-scope item "no compatibility shim that keeps both `/api/applications`"). There is no hidden backend rename trick.
- The local end-to-end test in B5 explicitly requires "browser at `https://web.local.humility.local/applications` submits without Playwright route fulfillment" (proposal §Test-intent track, "Local end-to-end public submit"). That is the precise anti-pattern that produced the original RCA, and the proposal forbids it for this slice.
- Existing authenticated `POST /api/v1/applications` is untouched (proposal §Design "API Route…", §Supported-surface track). The bug is not papered over by widening the authenticated route to accept anonymous traffic.

The implementation guidance also forbids a parallel submit state machine: it instructs that the public service path call a refactored helper of the existing `submit_application` with a `submission_authority="public_intake"` enum and a different `request_surface`, not a duplicated lifecycle (proposal §Design "Persistence: Schema Deltas…" closing paragraph). That is the right factoring; it avoids creating a second drift-prone path.

Verdict on this question: the design fixes the RCA's root cause and does not push the problem somewhere else.

## B-decisions purpose check

### B1 — Public success envelope

Returning `{message, application_id}` rather than full `ApplicationRead`.

- Purpose served: the contract value is "applicant gets confirmation; support gets a correlation handle". The envelope keeps both. Full `ApplicationRead` would leak applicant UUID, form snapshot, response payload, owner fields, and ETag intended for authenticated lifecycle callers — none of which the unauthenticated browser caller needs. The fixture only requires `message`, so adding `application_id` is a useful debug affordance that does not exceed contract.
- Lossy concern: no. The authenticated route still returns full `ApplicationRead`, so reviewer/admin tooling is not degraded. The public route is intentionally narrower.
- Risk: LOW. B1 is a net-honest narrowing; it serves the surface without leaking record state.

### B2 — Audit stamping

`actor_kind="service"`, `actor_id="public-intake"`, `request_surface="api:/api/v1/public/applications"`, with the synthetic applicant recorded as `applicant_id` rather than as the actor.

- Purpose served: the audit substrate requires non-null actor fields (`migrations/versions/wu-002_activity_substrate.py:17-49`); both `application.submit` and the immediate `route` transitions stamp the same service actor (proposal §Design "Persistence", "Audit rules"). Distinguishing actor (service path) from subject (synthetic applicant) is structurally honest: the anonymous browser is not a real user, but the intake service path is what executed the write.
- Completeness: actor_kind, actor_id, and request_surface are all explicit. Correlation id is provided by existing middleware. Submit and route both audit-stamp.
- Risk: LOW. B2 satisfies operational visibility (correlation id traces the aggregate; `request_surface` distinguishes public vs. authenticated) and audit substrate non-null requirements without inventing a fictional user identity.

### B3 — Day-1 rate limiting

Kong `KongPlugin` rate-limit binding is required on day 1, bound path-specifically on both web-host `/api/applications` and direct API-host `/api/v1/public/applications`.

- Purpose served: the recommended A1 model intentionally accepts unauthenticated traffic, so abuse control cannot rely on authentication. The proposal makes the rate-limit mandatory and explicitly forbids deploying the public route without it: "The public route should not be deployed without the rate-limit binding and policy tests in the same PR because that would introduce an unbounded public write path" (proposal §Migration / rollback). This is exactly the anti-shortcut framing.
- Required, not deferred: yes. B3 is binding day-1 scope, with a particular-integration test asserting the rendered manifests carry the binding on the right paths and not on the catch-all (proposal §Test-intent track, "Kong/Pomerium public route binding").
- Residual: distributed-traffic bypass is named as a residual by the proposal itself, not concealed.
- Risk: LOW. The proposal resists the most obvious shortcut here.

### B4 — Local + remote channel parity

Local channel gets concrete GitOps manifests; remote channel gets the same channel-template contract; no `local`-only code path.

- Purpose served: matches the channel-template pattern locked in user memory (environments are channels with parent inheritance; same components run identically local + remote with per-channel provider/endpoint config). The proposal explicitly rules out a local-only route exception and requires hosts to be channel-derived (proposal §B4, §Supported-surface track "Deployment mode").
- Honesty about remote apply: remote is contract-only because remote application GitOps is not yet materialized (problem map lines 67–72; project's actual state). This is honestly bounded — the contract is the same, the apply is not yet in scope. Not a shortcut, just an accurate scope statement.
- Risk: LOW. Contract parity is the right durable shape; deferring remote *apply* (not contract) is honest.

### B5 — Test-intent split

Layered split: contract validation at unit, persistence/audit/lifecycle at component, route auth/policy/Kong-render at particular-integration, browser-to-cluster at end-to-end.

- Purpose served: the named risks each get the right level. Critically, the e2e test forbids Playwright route fulfillment for the submit path — the exact pattern the RCA identified as the cause of the false-green prior tests. That is the strongest single signal in the proposal that the design refuses to repeat the original mistake.
- Coverage breadth: contract shape, synthetic applicant persistence, queued lifecycle + version, audit stamping, unauthenticated route behavior + adjacent route auth preservation, Cedar policy + matrix, Kong/Pomerium binding, SPA payload, e2e are all distinct test entries.
- All-mock or all-e2e concern: no. The proposal explicitly does not collapse to component tests with stubbed routes (which is what the R.22 path did) and does not collapse to e2e-only (which would be slow and weak on contract precision).
- Risk: LOW. The split is risk-targeted and includes the specific anti-pattern guard.

## Anti-scope deferral honesty

The proposal explicitly defers four things:

1. **Discord OAuth linking / synthetic-to-real-member conversion.** Honest: AS-2 names the residual identity pollution; "Out of scope for follow-up" lists a follow-up identity/linking proposal. Slice still useful without it: applications are durably created, audited, queryable, and reviewable by existing officer commands that operate on `applications` rows. The missing capability is granting Discord-side privileges to a public submitter, which is not part of the intake contract anyway.

2. **Legacy SQLite root `daemon/applications.py /apply` migration.** Honest: anti-scope item is unambiguous, and A4 chooses convergence with the *API-backed* Discord submission service (which already writes Postgres `applications`), not the legacy SQLite path. The legacy `/apply` continues to exist but is not claimed as a convergence target. The slice is useful because the canonical convergence (API-backed Discord handler) is real today and shares the same `applications` rows.

3. **Discord-visible queue embeds, private review thread creation, applicant DM/notification side effects for public web submissions.** Honest: explicitly anti-scoped, with the rationale that officers/reviewers see queued applications via existing review-side commands operating on `applications` rows. The applicant gets confirmation; the officer can still find and review the application. The missing pieces are convenience/UX, not correctness.

4. **Remote-channel apply for public intake.** Honest: matches actual project state (remote channel config exists, apply does not). B4 enforces channel-template parity in the contract regardless. Slice is useful in the local channel because local *is* a real deployment target per the environment-agnostic-stack policy.

For each deferral, public web intake is still useful in this slice because the slice's core value (durable real `applications` rows from the public web form, with audit and reviewability) does not depend on the deferred capabilities.

## Discord convergence honesty

Claim under audit: web and Discord submissions share `form_definitions`, `applications`, `application_reviews`, and aggregate version behavior, differing only in applicant identity (synthetic vs. real Discord member) and actor identity (service vs. user) (proposal §Discord Convergence).

The convergence claim holds for the API-backed Discord handler (`services/discord/app/handlers/application_submission.py:47-93`), which the proposal explicitly names as canonical (A4 Option 2). It does not hold for the legacy SQLite `/apply` path, but the proposal does not claim convergence with that path; it leaves it anti-scope.

Member-row collision risk: synthetic members use `discord_user_id = "public:" || sha256(public_submission_id || channel_salt)`. Real Discord members use the numeric Discord snowflake. The structural prefix `public:` makes collision impossible by construction. The uniqueness column (`members.discord_user_id`) is preserved.

Bounded called-out concerns:

- The proposal explicitly admits synthetic-member pollution: "It pollutes `members` with non-Discord subjects because `members.discord_user_id` is currently unique and has no native anonymous/pending status," and "it requires clear naming and tests so synthetic public members are not mistaken for real Discord roster members."
- AS-2 admits the assumption that synthetic members are acceptable, with named invalidation conditions.

Residual not surfaced as cleanly as it could be: adjacent member-listing surfaces (roster counts, trust profile aggregations, member queries by status, anywhere code does `SELECT … FROM members`) will see the synthetic rows unless they explicitly filter on the `public:` prefix. The proposal mentions test coverage that "synthetic public members are not mistaken for real Discord roster members" but does not enumerate which adjacent queries it intends to verify against. This is a minor honesty gap — not a hollowed purpose, but the convergence claim's residual blast radius is not fully traced.

Per-submission member explosion: the synthetic-member rule generates a new `public_submission_id` for each accepted submission unless `client_application_id` maps to an existing pair. So each accepted public submission creates a new `members` row. Heavy but honest, and the proposal does not pretend otherwise.

Net: convergence claim is honest and bounded by the `public:` prefix invariant. Adjacent member-query honesty could be slightly tighter but does not defeat the purpose.

## Cedar / Pomerium honesty

Pomerium posture: keep `web.local.humility.local` public except `/admin`, do not add Pomerium identity headers for the public route, do not change `protected-api.local.humility.local` (proposal §Pomerium / Cedar / Service-identities Deltas). This matches the current Pomerium config and does not pretend the public route is authenticated. The proposal admits this directly: "Pomerium currently separates public web from protected admin/protected API by host/path, not by a named public form-intake API route" (problem map line 39, surfaced in the proposal's surface-track).

Cedar posture: a distinct entity type `Public::"web-intake.local"` with the dedicated action `Action::"application:submit_public"`, plus explicit deny entries for unrelated actions (`api:read` on the same principal, and deny ordinary sample/other users for `application:submit_public`). This is the most honest representation: Cedar is not asked to authorize a fictional `User::` or `Service::`; it gets a new principal class that names the surface for what it is.

Honest about Cedar's limits: the proposal admits Cedar cannot identify a caller-specific principal in this model and therefore cannot serve as the abuse-control boundary — it is a binary route allow/deny. That is why B3 makes Kong rate-limit mandatory. The factoring is correct: Cedar handles identity-shaped policy, Kong handles abuse control, application validation handles payload integrity. No layer is asked to do a job another layer should be doing.

Residual surfaced honestly via AS-4: the assumption that OPAL/Cedar bootstrap will accept the `Public::` entity type is explicitly listed as invalidatable. This is a real-but-bounded risk and not a shortcut.

Verdict on this section: honest. Not a deferral of authorization — it is a deliberate, narrow public surface with policy that says exactly what the surface is.

## Notable observations

1. **The strongest anti-shortcut signal is the e2e test specification in B5.** It explicitly forbids Playwright route fulfillment for submit. That is the precise pattern that produced the original RCA (`.tmp/rca/public-application-intake-FINDINGS.md:31-33`). The proposal refuses to repeat the mistake.

2. **B3 is binding day-1, not deferred.** The migration path explicitly forbids deploying the public route without rate-limit binding in the same PR. This is the rate-limit-shortcut counter-example.

3. **No backwards-compatibility shim.** Anti-scope item explicitly rules out keeping `/api/applications` as a hidden backend route alongside the new public route. SPA, fixture, and route all converge on the new path. Aligns with the no-backwards-compatibility convention.

4. **No deferred stubs.** The proposal forbids a parallel submit state machine and instructs implementation to extend the existing `submit_application` via a private helper with `submission_authority` enum and per-call `request_surface`. Aligns with the no-deferred-stubs convention.

5. **`channel_salt` is referenced but underspecified.** The synthetic `discord_user_id` is hashed with `channel_salt`, but the proposal does not say where that salt lives (channel config, environment variable, derived constant). This is an implementation detail to flesh out, not a shortcut, but worth noting so it does not become a fixture or `local`-only constant by accident.

6. **Member-table volume.** Each accepted public submission creates a fresh `members` row. Acceptable for the slice, but downstream queries (roster, trust, member counts) need explicit awareness. The proposal calls this out via test guidance but does not enumerate the adjacent member-query surfaces; that is a small honesty gap, not a defeat of purpose.

7. **`client_application_id` semantics.** The proposal preserves `(applicant_id, client_application_id)` duplicate protection by generating a server-side `public:<public_submission_id>` for the synthetic id when no client id is supplied. Honest retry idempotency is preserved; abuse-replay is bounded by Kong, not by app-layer dedup. Correct factoring.

8. **A1 conditional recommendation.** The proposal makes Option 1 conditional on day-1 rate limiting and adjacent-route tests. That conditional posture is the correct shortcut-resistant framing: the chosen option only earns the recommendation if the abuse-control prerequisite is met in the same slice.

9. **Rollback honesty.** The rollback path "removes reachability before removing data support" and explicitly preserves audit/application/review/synthetic-member rows. This honors the audit-substrate purpose under rollback (no audit deletion) and is the right call.

10. **No detection-evasion hooks.** Public submit logs route, status, correlation id, rate-limit status; logs must not print raw response bodies. This is the correct observability balance — visible to operators, not leaking applicant content.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
