READ:
- proposals/02-public-application-intake.md
- research/02-public-application-intake-problem-map.md
- .tmp/rca/public-application-intake-FINDINGS.md
- proposals/01-recovery-test-first.md (lines 397-413, 893-914)
- proposals/01-v1-scope.rev1.md (lines 500-504)
- ~/ai/workflows/implementation-pipeline.md (Phase 4)
- ~/ai/conventions/no-backwards-compatibility.md
- ~/ai/conventions/no-deferred-stubs.md

# INIT-120 Scope-Risk Report

## Inputs read

- Approved proposal: `proposals/02-public-application-intake.md`.
- Approved problem map: `research/02-public-application-intake-problem-map.md`.
- RCA: `.tmp/rca/public-application-intake-FINDINGS.md`.
- Recovery web surface contract: `proposals/01-recovery-test-first.md:397-413`,
  `proposals/01-recovery-test-first.md:893-914`.
- v1 web fallback note: `proposals/01-v1-scope.rev1.md:500-504`.
- Phase-4 rules: `~/ai/workflows/implementation-pipeline.md:90-113`.
- Convention guards: `~/ai/conventions/no-backwards-compatibility.md`,
  `~/ai/conventions/no-deferred-stubs.md`.
- Approved A-decisions: A1=Opt 1, A2=Opt 1, A3=Opt 2, A4=Opt 2.

## Scope ↔ Anti-scope check

Each design change below is paired with the Scope clause it satisfies and
the Anti-scope clause(s) it must not violate.

1. New public API route `POST /api/v1/public/applications`
   (proposal §Design:155-187).
   - Scope: "Add a public API route, `POST /api/v1/public/applications`,
     for unauthenticated public intake" (proposal:13).
   - Anti-scope guard: "No change to `POST /api/v1/applications`; it
     remains authenticated and actor-header based" (proposal:29);
     proposal:186 explicitly states the authenticated route "remains
     unchanged: it requires actor context, accepts `ApplicationSubmission`,
     returns `ApplicationRead`, and sets ETag". The authenticated lifecycle
     contract at `services/api/app/api/v1/endpoints/applications/lifecycle.py:26-41`
     is preserved.
   - Verdict: in scope, no smuggling.

2. Synthetic placeholder `members` row keyed
   `discord_user_id = "public:" || sha256(...)` (proposal:194-198).
   - Scope: "Add repository/service support for creating or reusing
     synthetic public applicant members" (proposal:16).
   - Anti-scope guard: "No Cedar tenant-policy redesign or tenant
     isolation model change" (proposal:27); the synthetic row uses the
     existing `members` table and existing FKs, with no new tenant or
     trust semantics.
   - Approved decision: A2=Opt 1 explicitly authorizes this synthetic
     applicant model (proposal:67-72).
   - Verdict: in scope.

3. SPA payload + fixture switch from `/api/applications` to
   `/api/public/applications` (proposal:207-228).
   - Scope: "Update the public SPA submit payload and response handling
     in `services/web/src/main.tsx`" + "Update the web contract fixture
     so the fixture binds to the new public route" (proposal:17-18).
   - Anti-scope guard: "No compatibility shim that keeps both
     `/api/applications` as a hidden backend route and the new public
     route. The SPA fixture and code move to the deliberate public
     route" (proposal:33). The proposal commits to a clean migration
     of both fixture and SPA, no dual path.
   - Verdict: in scope; convention-aligned with no-backwards-compat.

4. Cedar policy/matrix entries for `Action::"application:submit_public"`
   (proposal:254-259).
   - Scope: "Add Cedar policy/matrix entries for the public submit
     action" (proposal:19).
   - Anti-scope guard: "No Cedar tenant-policy redesign or tenant
     isolation model change" (proposal:27). The proposal adds a new
     principal/action/resource triple but does not retouch tenant
     policy structure (no edits to tenant policies named at
     `research/02-public-application-intake-problem-map.md:54`).
   - Verdict: in scope.

5. Kong path-specific rate-limit bindings on `web.local.../api/applications`
   and `api.local.../api/v1/public/applications` (proposal:266-273).
   - Scope: "Add Kong rate-limiting configuration for the public submit
     path in local GitOps and require the same channel-template contract
     for remote" (proposal:20).
   - Anti-scope guard: explicitly excludes binding to "the catch-all web
     ingress so static SPA loads are not rate-limited with the submission
     budget" and notes "The direct authenticated `POST /api/v1/applications`
     route should not inherit this public limit" (proposal:273).
   - Verdict: in scope.

## B-decisions inside scope?

- **B1 — small response envelope** (proposal:116-127): touches only the
  new `PublicApplicationSubmissionReceipt`, does not change
  `ApplicationRead`. In scope.
- **B2 — audit posture stamps `actor_kind="service"`,
  `actor_id="public-intake"`, `request_surface="api:/api/v1/public/applications"`**
  (proposal:130-133, 199-205). Implementation note at proposal:205
  factors a "private internal helper that accepts `request_surface` and
  a `submission_authority='public_intake'` enum" inside
  `services/api/app/services/applications.py`. This is an internal
  refactor of shared submit logic, not a contract change to the
  authenticated route, and the proposal explicitly forbids "a second
  parallel submit state machine". In scope, but flagged below as a
  notable observation because it is the only B-item that necessarily
  edits a file shared with the authenticated lifecycle path.
- **B3 — day-1 Kong rate limit** (proposal:136-139): direct mapping to
  the Scope Kong clause, no enlargement. In scope.
- **B4 — local + remote channel-template parity** (proposal:142-145):
  scope is "local channel first" with same channel-template contract for
  remote, no remote apply. The proposal explicitly leaves remote apply
  out (proposal:280). In scope.
- **B5 — test split (unit / component / particular-integration / e2e)**
  (proposal:148-151, 343-435): each test-intent entry maps to a Scope
  clause, none introduce protected-route or Discord-side-effect tests.
  In scope.

No B-item enlarges the touched surface beyond what Scope claims.

## Out-of-scope discipline

The proposal lists these as `Out of scope for follow-up`
(proposal:443-451). Cross-checked against `## Design`:

- Discord OAuth linking / synthetic→real conversion: not implemented;
  no auth-handoff in §Design or §Persistence; proposal:445.
- Legacy SQLite `/apply` migration/deletion: not touched; proposal:25
  ("No changes to the legacy SQLite-backed root `daemon/applications.py`")
  and proposal:110 ("legacy `/apply` path remains anti-scope").
- Authentik anonymous sentinel route: only mentioned to declare it
  unused for the chosen A1=Opt 1; proposal:447.
- Service-account JWT web-pod model: explicitly unused for A1=Opt 1
  and §Service identities (proposal:262-264); a guard at proposal:264
  even requires re-revision before risk gating if A1.2 were selected.
- Discord-visible queue / thread / role / DM mutations: anti-scope
  (proposal:30); §Discord Convergence (proposal:233-243) only describes
  what already exists in `services/discord/app/handlers/application_submission.py`,
  not new Discord-visible side effects.
- Public form builder / chapter selector / file uploads: not present;
  AS-3 (proposal:333) confirms day-1 represents only global scope with
  the existing two visible fields, and proposal:449 names richer forms
  as follow-up.
- Remote channel apply / runbook: explicitly excluded
  (proposal:280, 451).

None of the listed follow-ups are silently in scope.

## Convention compliance

`~/ai/conventions/no-backwards-compatibility.md`:

- Proposal:33 forbids "a compatibility shim that keeps both
  `/api/applications` as a hidden backend route and the new public
  route. The SPA fixture and code move to the deliberate public route."
  This is a clean migration: the SPA, the web contract fixture, and
  Playwright route fixture all move to `/api/public/applications`
  (proposal:207-228, 422-424), and the authenticated route keeps its
  separate path/contract. No version-gated branch, no deprecated alias,
  no dual-path keepalive.
- Migration order (proposal:303-310) is additive then cutover, not
  parallel paths, matching the migration protocol.

`~/ai/conventions/no-deferred-stubs.md`:

- Every test-intent entry (proposal:347-435) names a real assertion
  surface; no empty-body or `NotImplementedError` placeholder is
  authorized.
- No "TODO: implement" hooks are reserved inside the public service
  helper; the proposal demands a fully implemented public submit
  through existing lifecycle code (proposal:198-205).
- The synthetic-member identity scheme stores a real
  `discord_user_id = "public:..."` value (proposal:195), not a
  null/None placeholder.
- The internal helper refactor (proposal:205) is a real restructuring
  of `submit_application` for a sibling caller, not a stubbed deferral.

Both conventions are met by the proposal text.

## Adjacent-path discipline

Cross-check of proposal §Supported-surface track (proposal:275-300)
against problem-map adjacents (problem-map:58-72) and `Anti-scope`:

- `POST /api/v1/applications` (authenticated lifecycle): unchanged
  (proposal:186, 297). No edit to actor dependency, contract, or
  ETag behavior.
- Discord submission service handler
  (`services/discord/app/handlers/application_submission.py`): unchanged
  (proposal:233-235, 298: "should not learn the public route").
- Pomerium admin / protected API routes: unchanged
  (proposal:248-251, 291-292, 299). The `/admin` host rule and
  `protected-api.local.humility.local` ACL are preserved.
- Tenant isolation policy and `validate_tenant_isolation_local.sh`
  surface (problem-map:54): not altered. The new Cedar policy adds a
  new principal/action triple, not a tenant model edit.
- Public web shell `/` and admin `/admin/chapters`: unchanged
  (proposal:289, 291).
- Web NetworkPolicy egress: unaffected; the new route still goes
  through the existing web-pod → API path.

No silent adjacent-path mutation found.

## Notable observations

1. **Internal helper refactor crosses an adjacent file.** Proposal:205
   asks for a private helper inside
   `services/api/app/services/applications.py` so submit logic is shared
   between the authenticated and public callers. This file is on the
   authenticated lifecycle path. The proposal correctly constrains it to
   "must not create a second parallel submit state machine" and keeps
   the authenticated route's external contract intact. This is
   internal-restructure-for-a-sibling-caller, which is normal scope, but
   the implementation must avoid changing observable authenticated
   behavior (e.g. `request_surface` value for the authenticated path
   must remain `api:/api/v1/applications`). Worth a Phase 6 line check;
   it is not a scope creep on the proposal level.

2. **`members` table semantics widen.** Synthetic public rows with
   `discord_user_id = "public:<hash>"` (proposal:195) widen the implicit
   contract "every `members.discord_user_id` is a real Discord user" to
   "or a synthetic public-intake subject with a `public:` prefix". AS-2
   (proposal:331) and proposal:88 acknowledge the residual identity
   pollution and put richer identity in follow-up (proposal:445). This
   is approved by A2=Opt 1, so it is in scope, but downstream callers
   that filter on `discord_user_id` must remain correct; this is a
   surface-track concern, not a scope violation.

3. **New Cedar entity type `Public::"web-intake.<channel>"`.** AS-4
   (proposal:335) flags that OPAL/Cedar bootstrap may reject the new
   entity type. The risk is correctly captured as an assumption with an
   invalidating input, rather than smuggled scope. No tenant model edit.

4. **Idempotency key generation.** Proposal:197 generates
   `client_application_id = "public:<public_submission_id>"` when none
   is provided. This adds a synthetic id-generation behavior to the
   public path only; it does not change the authenticated route's
   duplicate semantics. In scope.

5. **`request_surface` constant change.** The current
   `submit_application` hardcodes `request_surface="api:/api/v1/applications"`
   (problem-map:11). The refactor must keep that exact string for the
   authenticated path while emitting `api:/api/v1/public/applications`
   for the public path. A Phase 6 grep-invariant test on the
   authenticated `request_surface` value would close the residual.

## Verdict

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```

No invalidated assumption breaks the problem framing; the supported
surface (R.22 web `/applications` + Postgres-backed lifecycle) keeps
positive value because the proposal converts the fixture-only public
submit path into a real audited API contract with day-1 rate limiting,
Cedar coverage, and adjacent-route auth preservation. The proposal
stays cleanly within Scope, honors the four user-confirmed product
decisions (A1=1, A2=1, A3=2, A4=2), keeps every Anti-scope item out of
§Design, complies with `no-backwards-compatibility` and
`no-deferred-stubs`, and does not silently mutate the authenticated
lifecycle, Discord submission service, Pomerium admin, or tenant
policy. The only adjacent-file touch is an internal helper refactor in
`services/api/app/services/applications.py` shared with the
authenticated submit path, which the proposal explicitly bounds to
internal-only.
