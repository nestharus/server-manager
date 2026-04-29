# INIT-133B-i — Shortcut risk gate

**Verdict:** LOW

## S1 — `any` types in client / providers

**Choice:** §3 removes the `any` router prop type from
`services/web/src/app/providers.tsx`. §5 states "All client
functions validate with Zod; no `any`." Zod schemas mirror the
Pydantic contracts: `applicationStateSchema`,
`applicationReadSchema`, `applicationListReadSchema`,
`principalSchema` (with new `groups` and `discord_user_id`
fields).

**Risk:** browser silently accepts a malformed contract
response and the SPA renders junk or skips authorization gating.

**Mitigation:** the proposal explicitly forbids `any`; Zod
schemas are strict mirrors of `ApplicationRead`,
`ApplicationListRead`, and `CurrentPrincipalRead`; and the
existing `AppProviders` `router: any` is replaced. Tests assert
exact `/api/v1/me` JSON shape including the two new fields.

**Verdict:** Not a shortcut.

## S2 — `If-Match` / optimistic locking on the claim path

**Choice:** §3, §4, §6, and §7 lock the claim path to a real
`If-Match` header workflow. The bridge calls
`parse_if_match_strong(request)` directly from
`services/api/app/api/v1/endpoints/applications/etag.py`
(post-rename) to validate the browser-supplied header, and the
bridge passes the helper's HTTPException verbatim — 428
`if_match_required`, 412 `invalid_if_match`. After identity
validates, the bridge captures
`expected_version = parse_if_match_strong(request)` and forwards
it to the synchronous `transition_application(...,
expected_version=expected_version)`.

The proposal is explicit: "The bridge must never silently fall
through to 'use current server version.'" §7 adds
`web officer claim missing If-Match returns 428 ... / malformed
returns 412 invalid_if_match / stale returns 412
stale_application_version`. A6 in the audit history flags an
ordering shortcut (parsing `If-Match` before identity), and §6
order locks identity → group → claim → member resolution → then
`parse_if_match_strong`, with `web officer claim missing
identity headers and missing If-Match returns 401` proving the
order.

**Risk:** an officer's claim accidentally races on the current
server version, overwriting another officer's recent action.

**Mitigation:** real reuse of the shared helper (no bridge-local
re-encoding), real version threading through the service call,
and explicit negative tests that the bridge cannot default to
the current server version.

**Verdict:** Not a shortcut.

## S3 — Browser-supplied actor headers

**Choice:** §2 (Q2), §6, and §8 forbid the bridge from reading
`X-Actor-Kind`, `X-Actor-Id`, `X-Discord-User-Id`, or any other
browser-asserted actor identity. The bridge ignores those
headers entirely and is built to NOT depend on
`app.core.dependencies.get_current_actor`,
`app.core.context.get_current_actor`, or any callable that reads
`CURRENT_ACTOR.get()`. It also does not consult
`applicant_receipt`. Identity comes only from
`x-pomerium-claim-discord-user-id`, then
`resolve_or_create_real_discord_member` to a real `MemberRead`,
then `ActorIdentity(actor_kind="user", actor_id=str(member.id))`
constructed locally.

§7 adds two server-side guards:
- `test_officer_endpoints_have_locked_actor_construction` walks
  the FastAPI dependency tree for every `/api/v1/web/officer/`
  route and asserts none of the forbidden dependencies are
  present (Python test, survives literal-string refactors).
- `test_officer_claim_ignores_x_actor_headers` sends a valid
  Pomerium officer + Discord claim plus an attacker-controlled
  `X-Actor-Kind` / `X-Actor-Id`, and asserts the resulting
  `ApplicationRead.owner_id` is the Pomerium-resolved member
  UUID, not the attacker UUID.

**Risk:** the most dangerous shortcut — letting the browser
forge officer identity. This was rejected.

**Mitigation:** server-side identity construction, dependency
tree assertion, attacker-headers test, and all officer routes
explicitly outside the actor middleware's `_requires_actor`
allowlist.

**Verdict:** Not a shortcut.

## S4 — Reuse of `applicant_receipt` for officer actor identity

**Choice:** §2, §6, and §8 explicitly remove any reuse of the
`applicant_receipt` cookie for officer identity. The cookie
remains scoped to `/applications`, `/auth/discord/me`, and
public submit. Officer endpoints do not read it. §7 includes
`web officer list ignores applicant receipt`: a mismatched
receipt cookie does not change the resolved actor.

§3 also parameterizes `resolve_or_create_real_discord_member`
with optional `originating_actor` and `request_surface`. The
bridge passes `originating_actor=ActorIdentity(actor_kind=
"service", actor_id="web-officer-bridge")` and
`request_surface="api:/api/v1/web/officer/applications"` so
first-login officer member creation is attributed to the bridge,
not the applicant receipt service. The proposal explicitly calls
out all three audit-record sites in
`services/api/app/services/members.py:200-256` that must be
threaded — `_make_request(..., actor=..., request_surface=...)`,
`action_payload` literals, and `StateChangeDraft.payload_json`
literals — and warns that "missing any of the three sites
silently leaks the `applicant-receipt` actor into officer
member-creation audit records." §7 adds `web officer first login
records member creation under web-officer-bridge actor` to lock
all three sites.

**Risk:** audit forensics confused officer-bridge writes with
applicant-receipt writes; or worse, the receipt cookie gating
officer auth.

**Mitigation:** explicit removal, named sites, three test
points (member-creation actor; claim audit `request_surface`;
receipt-ignored list).

**Verdict:** Not a shortcut.

## S5 — Bridge re-implementing list/claim logic

**Choice:** §3, §4, and §6 keep all list/claim business logic
in the existing service functions. The bridge is exactly:

1. Pomerium principal validation
2. Officer group check
3. Discord claim regex (`DISCORD_SNOWFLAKE_RE` imported from
   `services/api/app/services/applicant_discord_auth.py`, no
   bridge-local copy)
4. `await resolve_or_create_real_discord_member(...)`
5. `parse_if_match_strong(request)` (imported from the existing
   etag helper)
6. `list_applications(...)` or `transition_application(...)`
   called as synchronous Python functions (NOT HTTP self-call)
7. `raise_known_application_error(...)` mapping for typed
   service exceptions
8. `set_etag(response, result.etag)` for ETag symmetry

Step 1 of the implementation is to fold the
`ApplicationListForbiddenError → 403 application_list_forbidden`
mapping into `raise_known_application_error` and update the
direct lifecycle endpoint to delegate to it, so the bridge
inherits identical wire format. §7 includes
`raise_known_application_error maps
ApplicationListForbiddenError` as a direct-helper unit test that
lands before the bridge tests.

**Risk:** the bridge re-encodes status codes or duplicates
authorization, drifting from the direct API surface and
creating two sources of truth for officer review semantics.

**Mitigation:** explicit "delegate, don't reimplement" rule,
shared helper migration as Step 1, status-code parity tests,
and an audit-row request-surface assertion proving the bridge
calls into the same service path.

**Verdict:** Not a shortcut.

## S6 — Tests as mocked round-trips vs. UI snapshots

**Choice:** §7 component tests assert mocked HTTP round-trips:
state filter sent to `/api/web/officer/applications?state=...`,
pagination via `after_id`, claim sends
`If-Match: "<row.version>"` with no `expected_version` body,
conflict (409 / 412) refetches, opaque/302 fetch failures
classified as auth-required. API tests assert exact status +
code wire format for missing identity, missing `If-Match`,
malformed `If-Match`, stale version, application-not-found,
application-not-owner, invalid-transition,
non-discord-member-row, no-grant. E2E in §7 is real Postgres:
after the claim button is clicked, the test queries the
primary application pod via psql and asserts
`state='claimed'`, `owner_id != applicant_id`,
`members.discord_user_id = E2E_OFFICER_DISCORD_USER_ID`, and
`members.kind='discord'`.

The proposal explicitly chooses to add server-side dependency
tree tests (Python) on top of grep-based static checks because
the latter would not survive literal-string refactors.

**Risk:** UI screenshot/route-existence tests masking missing
behavior or miswired headers.

**Mitigation:** mocked round-trip assertions on every contract
edge, real Postgres assertions on the e2e claim, and Python
dependency-tree assertions on the bridge.

**Verdict:** Not a shortcut.

## S7 — `HomeRoute` / `AdminChaptersRoute` migration: parity vs. redesign

**Choice:** §3 mandates that `HomeRoute.tsx` preserves the
`#start-application` button, click handler, and element type;
`AdminChaptersRoute.tsx` preserves the chapter table behavior;
`ApplicationFormRoute.tsx` preserves all selector ids,
data-testids, accessible names, and exact `discord-login-state`
text strings from `services/web/src/main.tsx`. The migrated
applicant form must keep all four `applicantDiscordTest` /
`loggedInApplicantTest` / `staleApplicantReceiptTest` cases at
`services/web/tests/compat.spec.ts:202-291` passing.

The one departure is "intentional contract tightening" —
`#tab-overview`, `#tab-details`, `#details-panel` are now
auth-state-conditional (only rendered in `verified`), where the
live vanilla template renders them in all auth states. This is
explicitly flagged in the proposal as tightening (not pure
preservation), justified by "no existing `compat.spec.ts` test
or downstream consumer depends on the tabs/details-panel being
present pre-verification," and locked with new explicit
assertions: tabs/details-panel NOT in DOM under
`checking`/`anonymous`, plus a new `#details-panel`
`[hidden]`-toggle assertion in `verified`.

**Risk:** "while we're at it" redesign smuggled into a
load-bearing migration, breaking applicant flow or e2e test 19.

**Mitigation:** the parity surface is named at the selector +
text level; the one tightening is documented and locked; no
other tightening is allowed; and `compat.spec.ts` and e2e test
19 must pass against the migrated route. The contract
tightening is bounded, defended, and pinned with new tests —
this is an intentional, reviewed change, not silent drift.

**Verdict:** Not a shortcut.

## S8 — Officer-without-Discord-receipt deferred to 133B-ii

**Choice:** §2, §6, and §10 commit to fully resolving officer
Discord identity in 133B-i, not deferring to 133B-ii. The
Authentik blueprint
(`init-133B-pomerium-officer-discord.yaml`) declares the
`pomerium` OAuth2 application with a distinct `discord-pomerium`
OAuth source, separate Discord developer credentials
(`DISCORD_OFFICER_OAUTH_CLIENT_ID` /
`DISCORD_OFFICER_OAUTH_CLIENT_SECRET`), and a
`discord_user_id` scope mapping. Pomerium config extends
`idp_scopes` and `jwt_claims_headers`. The `/api/v1/me`
endpoint exposes the new claim.

If the claim is missing, the bridge returns
`401 officer_discord_identity_missing` and the SPA shows an
identity-incomplete panel with a hard
`/.pomerium/sign_in` redirect — i.e., the officer is forced
through the Discord OAuth flow before queue access works.

**Risk:** "officers without Discord identity" path silently
papered over with a placeholder, leaving 133B-ii to deal with
the OAuth integration work.

**Mitigation:** the OAuth integration is in this slice; the
"missing claim" path is a hard error, not a degraded UX; and the
e2e test verifies the bootstrap fixture user authenticates with
the expected snowflake reaching member creation.

**Verdict:** Not a shortcut.

## S9 — Feature flag / parallel runtime / compatibility shim

**Choice:** §2 (Q1), §3, §8, and §11 commit to option B —
TanStack Solid Router as the real entry. `RuntimeApp.tsx` is
deleted. Vanilla DOM rendering in `main.tsx` is removed; only
the `render(() => <AppProviders router={router} />, root)`
bootstrap remains. Demo-only form scaffolding
(`DarkNemesisForm.tsx`, `forms/schema.ts`, `forms/form.module.css`)
is deleted. Anti-scope explicitly prohibits "feature flag,
legacy vanilla route fallback, or retained `RuntimeApp` parallel
entry."

**Risk:** parallel runtime limbo persists, two systems drift,
133B-ii/iii inherit the dual-system problem.

**Mitigation:** delete-list is concrete; `validate_web_ui_local.sh`
adds a negative grep for `/api/v1/...` literals across all
`services/web/src/` source (not just `client.ts`), which would
catch a re-introduced vanilla path; the migration is the
explicit answer to the load-bearing Q1 question.

**Verdict:** Not a shortcut.

## S10 — TODOs / "for now" / deferred stubs

**Choice:** No `TODO`, `// for now`, "ship it and iterate", or
deferred-stub language anywhere in the proposal. Anti-scope
items are listed concretely (detail page, transcript, message
thread, route action, scope selector, owner filter, sorting,
bulk actions, export, mobile polish, Storybook, schema, new
permissions, new actor kinds), each owned by a named follow-up
ticket (133B-ii, 133B-iii, BL-009, BL-020), so deferrals are
ownership transfers rather than hidden stubs.

The Authentik blueprint additions are not stubs — they declare
real Pomerium/Authentik objects that the e2e test exercises end
to end via the bootstrap fixture user.

**Risk:** half-finished stub left in the diff, future task
ambiguity.

**Mitigation:** anti-scope is concrete and ticket-routed; no
TODO comments planned; the diff budget acknowledges that
exceeding the ceiling should fail the scope gate and split the
router migration out, not paper over it with stubs.

**Verdict:** Not a shortcut.

## S11 — `application_list_forbidden` mapper migration ordering

**Choice:** §3, §4, and §6 require Step 1 (must land first) to
fold the `ApplicationListForbiddenError → 403
application_list_forbidden` branch into
`raise_known_application_error` in
`services/api/app/api/v1/endpoints/applications/_shared.py` (or
the renamed `etag.py`/stable mapper module), update the direct
list endpoint at
`services/api/app/api/v1/endpoints/applications/lifecycle.py:106-110`
to delegate to the helper, and add a unit test that calls the
helper directly and asserts the 403 mapping. Only after that
can the bridge be implemented.

**Risk:** the bridge silently re-encodes the forbidden mapping
locally, bridge and direct API drift.

**Mitigation:** explicit step ordering, named test, the bridge
must consume the shared helper. This is a refactor that
*precedes* the bridge work and is itself a code-correctness
move (today's direct list endpoint maps locally — that's the
existing minor wart, and 133B-i fixes it as a prerequisite
rather than working around it).

**Verdict:** Not a shortcut — it's a deliberate prerequisite
refactor.

## Verdict reasoning

This proposal is the post-audit revision (r11 per §10) and
answers the most dangerous classes of shortcut head-on: it
forbids browser-asserted actor headers with a Python
dependency-tree test plus an attacker-headers test; it forbids
applicant-receipt reuse and threads a distinct
`request_surface` / `originating_actor` through every
audit-record site; it preserves real `If-Match` optimistic
locking by directly importing the shared helper, with negative
tests that missing/malformed/stale `If-Match` cannot default to
the server version; it delegates to existing list/transition
services and folds a remaining mapper inconsistency into the
shared helper as a prerequisite step (Step 1 with its own unit
test). The one place behavior changes (auth-state-conditional
tabs/details-panel rendering) is explicitly flagged as a
contract tightening and locked with new tests, not silent
drift. There is no `any`, no TODO, no feature flag, no parallel
runtime, no deferred stub, and no "officer without Discord
receipt" deferral — the Authentik blueprint, Pomerium config,
and `/api/v1/me` surface ship together so the OAuth flow is
real in this slice. Mocked Playwright round-trips assert exact
header/query wire format, and the e2e proves a real Postgres
state transition with a real Discord member row. Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-133B-i-shortcut.md
