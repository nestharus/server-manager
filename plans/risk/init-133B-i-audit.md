# INIT-133B-i — Audit risk gate

**Verdict:** MEDIUM

## A1 ... A8 — Findings

### A1 — Officer ↔ Discord-receipt actor identity is unbound

**Concern:** The web-officer bridge composes Pomerium officer identity (proof of "you are signed in as an officer") with a separate `applicant_receipt` cookie that carries a Discord snowflake set by `/auth/discord/callback` (`services/api/app/api/v1/endpoints/auth_discord.py:75-85`). The bridge then resolves the receipt's `discord_user_id` via `resolve_or_create_real_discord_member` (`services/api/app/services/members.py:192-268`) and uses the resulting member UUID as `ActorIdentity(actor_kind="user", actor_id=<member uuid>)` for both list authorization and `application.claim` audit writes (`proposals/13-init-133B-i-officer-queue.md:15`, `services/api/app/services/applications.py:266-273`, `services/api/app/services/applications.py:946-955`). Nothing in the proposal binds the receipt's `discord_user_id` to the Pomerium subject. The `applicant_receipt` cookie is set by Discord OAuth from any browser session that completes the applicant flow, with `Path=/`, so an officer can simultaneously hold a Pomerium officer session for subject X and an applicant receipt for an unrelated Discord user Y — and the bridge will authorize the list call against Y's grants, write `owner_id = <Y's member UUID>` on claim, and record the audit actor as Y in `application_reviews.actor_id` and `activity_actions.actor_id`. The proposal's section 6 states "claim ownership must be a real member UUID" but does not require that UUID identify the Pomerium principal.

**Evidence:** `proposals/13-init-133B-i-officer-queue.md:15` (bridge composition), `proposals/13-init-133B-i-officer-queue.md:208-214` (auth model), `services/api/app/services/applicant_discord_auth.py:207-236` (receipt verifier returns only `discord_user_id`), `services/api/app/api/v1/endpoints/auth_discord.py:75-85` (cookie path `/`, no Pomerium binding), `services/api/app/services/applications.py:266-273` (reviewer_id derived from actor.actor_id), `services/api/app/services/applications.py:1001-1015` (reviewer_id and actor_id persisted into `application_reviews`).

**Severity:** HIGH

**Recommendation:** The proposal must lock one of: (a) read the Discord member id from the Pomerium claim chain (e.g., a `discord_user_id` claim emitted by Authentik for officers and forwarded as `x-pomerium-claim-*`) and stop trusting the applicant cookie for officer routes; (b) require a server-side `member_links` lookup that maps the Pomerium subject to a Discord member UUID and reject the request when the receipt's `discord_user_id` does not match; or (c) explicitly redefine the actor identity for officer-side review writes so the recorded actor is the Pomerium subject rather than a Discord-side member, and document the audit semantics. As written, the slice will let an officer act on the queue under another Discord user's identity whenever both cookies are present, which the existing review-write contract treats as authoritative for ownership and audit.

### A2 — Solid Router migration risks dropping the "Application form" nav link asserted by `compat.spec.ts`

**Concern:** `compat.spec.ts` exercises a fixture-driven assertion that a top-nav link with role=link and accessible name "Application form" exists and resolves to `/applications` (`services/web/tests/compat.spec.ts:228-246`, `infra/tests/fixtures/web-ui/contract.json:98-101`). The current vanilla `main.tsx` renders this link in the shell (`services/web/src/main.tsx:48`). The current Solid `RootShell` exposes only "Public" and "Admin" nav links (`services/web/src/app/router.tsx:23-30`), and the proposal's "Modified files" entry for `router.tsx` says "add `/applications` and `/applications/queue`; keep `/` and `/admin/chapters`; add queue nav only when the route has officer state" without naming the "Application form" nav link (`proposals/13-init-133B-i-officer-queue.md:54`). If the migration mounts the Solid shell as-is and adds only the queue route, the contract test for the navigation link breaks even though the underlying route exists.

**Evidence:** `services/web/src/main.tsx:46-50`, `services/web/src/app/router.tsx:23-30`, `services/web/tests/compat.spec.ts:228-246`, `infra/tests/fixtures/web-ui/contract.json:88-101`, `proposals/13-init-133B-i-officer-queue.md:54`.

**Severity:** MEDIUM

**Recommendation:** The proposal should explicitly require the Solid `RootShell` to mount a `<Link to="/applications">Application form</Link>` (alongside Public and Admin) so the existing contract assertion in `compat.spec.ts` continues to pass. Officer queue nav can remain conditional, but the public applicant nav link is contractually fixed.

### A3 — Solid mirror of the applicant route does not enumerate the receipt re-probe / 9-minute timer or the submit-time receipt recheck

**Concern:** Today the applicant route preserves three behaviors that the existing component tests pin: (i) probe `/auth/discord/me` on route entry to swap between "Login with Discord" and the form (`services/web/src/main.tsx:176-178`, `services/web/src/main.tsx:258-278`), (ii) re-arm a 9-minute timeout that flips state back to "checking" (`services/web/src/main.tsx:32-33`, `services/web/src/main.tsx:270-276`), and (iii) on submit, perform a defensive `/auth/discord/me` recheck and, on 401, preserve draft and redirect to `/auth/discord/start?return_to=/applications` without POSTing (`services/web/src/main.tsx:180-216`, `services/web/tests/compat.spec.ts:160-200`, `services/web/tests/compat.spec.ts:272-291`). The proposal's "Signals / stores" list (section 5.3) only enumerates queue-route signals — `selectedStates`, `items`, `nextAfterId`, `claimingId`, `notice` — and section 3 introduces `ApplicationFormRoute.tsx` with the prose "mirror of the current receipt-gated applicant form behavior." There is no explicit lock for an applicant auth signal, the timer, the on-submit recheck, or draft preservation in `humility.publicApplication.draft`/`humility.publicApplication.clientApplicationId` sessionStorage keys.

**Evidence:** `services/web/src/main.tsx:32-33,151-158,176-178,180-216,238-311`, `services/web/tests/compat.spec.ts:160-200,202-291`, `proposals/13-init-133B-i-officer-queue.md:45,196-204`.

**Severity:** MEDIUM

**Recommendation:** The proposal should explicitly lock the `ApplicationFormRoute` contract: an applicant auth signal with the three states `checking | anonymous | verified(discord_user_id, expires_at)`, the 9-minute re-probe, the on-submit recheck that aborts the POST and redirects to `/auth/discord/start?return_to=/applications`, and the two sessionStorage keys (`humility.publicApplication.clientApplicationId`, `humility.publicApplication.draft`). All four `applicantDiscordTest`/`loggedInApplicantTest`/`staleApplicantReceiptTest` cases in `compat.spec.ts:202-291` must continue to pass against the migrated route.

### A4 — Pomerium target service for `/api/web/officer/` is unspecified, and the `/api/...` rewrite only fires through the web nginx

**Concern:** The proposal adds Pomerium protection for `/api/web/officer/` (`proposals/13-init-133B-i-officer-queue.md:62`) but does not lock the `to:` target. The browser-facing prefix `/api/web/officer/applications` is the SPA's URL; the FastAPI endpoint is `/api/v1/web/officer/applications` (proposal section 4) and the only `/api/` → `/api/v1/` rewrite lives in the web image's nginx (`containers/server-manager/nginx-web.conf:8-20`). If the new Pomerium route targets `server-manager-api...:8000` directly (mirroring the existing `/auth/discord/` route, which targets the API service), the API will receive `/api/web/officer/applications`, which does not exist. The route must target the web service so nginx can apply the `/api/` → `/api/v1/` rewrite. The `/admin` route already does this with `pass_identity_headers: true`, but the proposal does not call it out for the officer route.

**Evidence:** `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-63` (existing route targets), `containers/server-manager/nginx-web.conf:8-20` (rewrite only on web), `proposals/13-init-133B-i-officer-queue.md:62,100-101`.

**Severity:** MEDIUM

**Recommendation:** Lock the Pomerium route shape in the proposal: `from: https://web.local.humility.local`, `prefix: /api/web/officer/`, `to: http://server-manager-web.web.svc.cluster.local:8080`, `preserve_host_header: true`, `pass_identity_headers: true`, `allow_any_authenticated_user: true`. Add an assertion in `infra/tests/test_applicant_discord_pomerium.py` that this route's `to:` is the web service (not the API service), so the rewrite cannot be silently bypassed.

### A5 — Officer authority test surface omits the "officer Pomerium group but no `application.*` grant on resolved member" case

**Concern:** Section 7's API tests cover Pomerium identity missing, no `officers` group, no receipt, success, claim member resolution, and stale version (`proposals/13-init-133B-i-officer-queue.md:230-238`). They do not cover the case where Pomerium has the `officers` group, the receipt resolves to a real Discord member, but that member has no `application.review`/`application.claim` grant at the relevant scope — which is the path through `_has_application_list_authority` / `require_transition_authority` (`services/api/app/services/applications.py:393-417`, `services/api/app/services/applications.py:348-362`). This is the most realistic 403 case in production once chapter-scoped officers exist (BL-019A): a member is in the `officers` Pomerium group but only has authority on a different chapter scope. Without this test, the bridge could silently regress to "officer group implies access" if the implementation skips `_has_application_list_authority` reliance.

**Evidence:** `proposals/13-init-133B-i-officer-queue.md:230-238`, `services/api/app/services/applications.py:348-362,393-446`.

**Severity:** MEDIUM

**Recommendation:** Add an API test case "web officer list returns 403 when resolved Discord member has no `application.*` grant at the requested scope" and the analogous claim case mapping `PermissionError` to `403 authority_decision_denied` (`services/api/app/api/v1/endpoints/applications/_shared.py:166-170`). This pins the contract that officer-group membership alone is not authorization; authority grants on the resolved Discord member are.

### A6 — Pomerium prefix `/applications/queue` ordering vs `/applications` form must be locked, not implied

**Concern:** The proposal adds a protected route for `/applications/queue` before the public catch-all (`proposals/13-init-133B-i-officer-queue.md:62`). The applicant form lives at `/applications` and must remain public (it falls through to the catch-all today, `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:60-63`). Pomerium prefix matching is order-sensitive: a route with `prefix: /applications` would shadow `/applications/queue`, and a route with `prefix: /applications/` would shadow the form. The proposal does not state the exact prefix string (`/applications/queue` vs `/applications/queue/`) or test that the applicant form remains publicly reachable after the change.

**Evidence:** `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-63`, `proposals/13-init-133B-i-officer-queue.md:62-63,277`, `infra/tests/test_applicant_discord_pomerium.py:35-80`.

**Severity:** LOW

**Recommendation:** Lock the prefix string explicitly (`prefix: /applications/queue`), and extend `infra/tests/test_applicant_discord_pomerium.py` with two assertions: (i) the new officer-protected prefixes do not shadow `/applications` (the form route remains in catch-all territory and is unauthenticated-allowed), and (ii) the new prefixes precede the public catch-all index, consistent with the existing `_web_catch_all_index` pattern.

### A7 — Optimistic locking shape in the bridge: `expected_version` body field vs `If-Match` header

**Concern:** The browser POSTs `{"expected_version": 3}` and the bridge synthesizes `If-Match: "3"` for the core endpoint (`proposals/13-init-133B-i-officer-queue.md:115-123`). This works, but the existing core surface treats `If-Match` as the authoritative ETag carrier (`services/api/app/api/v1/endpoints/applications/_shared.py:33-56`) and the SPA already has access to ETags returned via `set_etag` on every read. Carrying `expected_version` in the body re-encodes the same value in a second place, and the bridge silently dropping or fabricating it on partial input is not specified — e.g., if the body is `{}`, does the bridge 422, or does it default to the server's current version (which would silently bypass the precondition)?

**Evidence:** `proposals/13-init-133B-i-officer-queue.md:113-123`, `services/api/app/api/v1/endpoints/applications/_shared.py:33-56`, `services/api/app/services/applications.py:887-894` (read returns `f'"{read.version}"'` ETag).

**Severity:** LOW

**Recommendation:** Either (a) specify that the bridge treats `expected_version` as required and 422s on missing/invalid input — never falling through to "use current server version" — and require a test that asserts this; or (b) have the bridge accept `If-Match` from the browser directly (mirroring the core endpoint) and drop the `expected_version` body field. The latter aligns with the rest of the application surface and removes an avoidable layering.

### A8 — `compat.spec.ts` "Application form" link assertion uses `getByRole("link")` and expects a hard navigation to `/applications`

**Concern:** Related to A2, the test relies on `getByRole("link", { name: "Application form" })` followed by `expect(page).toHaveURL(...)` (`services/web/tests/compat.spec.ts:228-246`). Solid Router's `<Link>` will produce role=link, but it intercepts navigation as client-side. This is fine for `toHaveURL`, but only if the route is registered and the migration does not regress to an `<a href>` outside the router. Conversely, the applicant route's `discord-login`, `start-application`, and post-401 redirect cases must remain HARD navigations to `/auth/discord/start?return_to=/applications` and `/applications` respectively (the tests assert URL transitions and the targets are Pomerium-served paths, not Solid routes — `services/web/tests/compat.spec.ts:212-214,289-290`). The proposal does not call out the distinction between client-side `<Link>` and `window.location.assign` for these specific actions.

**Evidence:** `services/web/src/main.tsx:168-174,280-282`, `services/web/tests/compat.spec.ts:202-214,272-291`, `proposals/13-init-133B-i-officer-queue.md:45,54-58`.

**Severity:** LOW

**Recommendation:** The proposal should explicitly require: (i) "Application form" nav uses Solid `<Link>`; (ii) the `Login with Discord` button and the post-submit redirect on 401 perform `window.location.assign("/auth/discord/start?return_to=/applications")` (NOT a Solid `navigate()`), since `/auth/discord/*` is a different Pomerium upstream that the SPA must not intercept. The same applies to the future officer-side `return_to=/applications/queue`.

## Verdict reasoning

The proposal is structurally sound on the read side — the consume-existing-services pattern is right, optimistic locking maps cleanly to the existing strong-ETag contract, the Pomerium gate plus Discord-receipt bridge captures the right backend constraint that browsers cannot supply trusted actor identity, and the deletions/migrations are scoped to the named parallel-systems instances. The blocker is A1: the bridge derives the audit actor from the receipt cookie's `discord_user_id` without binding that Discord identity to the Pomerium subject, so an officer can act under an unrelated Discord member's identity whenever both cookies are present, and the audit/`application_reviews` rows will record the receipt-holder rather than the officer. A2–A4 are real correctness regressions waiting to happen at the boundaries the slice is touching: the Solid migration is a behavior-mirror exercise where a single missed nav link, missed timer, or missed Pomerium target breaks a contract test or the queue itself. A5–A8 are smaller specification gaps that should be locked before implementation rather than discovered in review. None of these require redesigning the slice, but A1 in particular needs a binding decision in the proposal — not just the implementation — before this lands. Overall verdict: MEDIUM, conditional on A1 being resolved (or escalated to a separate INIT) and A2–A4 being explicitly locked.
