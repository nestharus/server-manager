# INIT-133B-i — Audit risk gate

**Verdict:** LOW

The r11 proposal already absorbs the prior round's high-severity
findings (A1..A7 in §10): SPA principal probe is `/api/me` no-trailing-
slash with exact-path Pomerium protection and collision tests; the
bridge endpoints stay `async def` only because
`resolve_or_create_real_discord_member(...)` is async, while
`list_applications` and `transition_application` remain synchronous;
the claim handler destructures `read, result = transition_application(
...)` and writes `set_etag(response, result.etag)` before returning
`read`; resolver `ValueError` is mapped in a resolver-only block ahead
of the transition mapper; identity validation runs before
`parse_if_match_strong(request)` so missing identity + missing
`If-Match` returns 401 not 428; `auth.probe_endpoint` in
`infra/tests/fixtures/web-ui/contract.json` is already `/api/me`
(`infra/tests/fixtures/web-ui/contract.json:33`); `validate_web_ui_local.sh`
gains a live curl assertion.

The applicant-flow DOM contract preservation (selectors, sessionStorage
keys, payload shape, `#submit-status`, `/auth/discord/start`
redirect, `applicant_receipt` cookie) is enumerated in §3 "Applicant
form DOM contract" and §3 "HomeRoute (public route) DOM contract" with
explicit Playwright lock-in additions in §7. The officer authorization
chain (Pomerium principal → officers group → snowflake-shaped Discord
claim → `resolve_or_create_real_discord_member` → locally-constructed
`ActorIdentity(actor_kind="user", actor_id=str(member.id))`) is
explicit, and a Python-side route-tree dependency assertion
(`test_officer_endpoints_have_locked_actor_construction`) prevents
regressions that would re-introduce `applicant_receipt` or
`get_current_actor` into the officer surface. Optimistic locking goes
through the shared `parse_if_match_strong` / `set_etag` helpers, so
claim ETag symmetry is preserved with the direct
`/api/v1/applications/*` endpoints. Pomerium route ordering uses
exact `path:` for `/applications/queue` and `/api/me` plus nested
`prefix:` for `/applications/queue/`, `/api/web/admin/`, and
`/api/web/officer/` before the public catch-all, with collision-class
fixtures in the static test (`/applications/queue-foo`, `/api/me-foo`,
`/api/members/...`).

Findings below are residual and non-blocking. Two are MEDIUM (A2, A3)
because they introduce silent-failure risk that the existing test
plan does not catch; the others are LOW.

## A1 — Bridge transition mapper catches a narrower exception set than the direct lifecycle endpoint

**Concern:** The illustrative bridge claim mapper in proposal §4
enumerates nine exception types
(`ApplicationNotFoundError, StaleMutationError,
ApplicationAlreadyClaimedError, ApplicationNotOwnerError,
InvalidApplicationTransitionError, MissingAggregateError,
ApplicationListForbiddenError, DuplicateApplicationCreateError,
PermissionError`). The shared
`raise_known_application_error(...)` mapper in
`services/api/app/api/v1/endpoints/applications/_shared.py` covers
additional types
(`FormDefinitionNotFoundError`, `ApplicationInterviewThreadMismatchError`,
`ApplicationDecisionReasonRequiredError`,
`ApplicationReviewNotesRequiredError`,
`ApplicationWaitlistReasonRequiredError`,
`ApplicationReactivateOwnerRequiredError`,
`InvalidApplicationResponseError`). For the `claim` action most of
these will not fire today, but if a future change to
`transition_application` raises any of them on the claim path, the
bridge propagates them as a FastAPI default 500 instead of the
helper-mapped 4xx code, breaking parity with the direct endpoint and
the proposal's own promise that "claim errors preserve the same
status+code wire format as the direct `/api/v1/applications/*`
endpoints."

**Evidence:** `proposals/13-init-133B-i-officer-queue.md:282-293`
(narrow tuple in illustrative claim handler);
`proposals/13-init-133B-i-officer-queue.md:215, 300, 424` (proposal's
parity claim); `services/api/app/api/v1/endpoints/applications/_shared.py`
(`raise_known_application_error` enumerates the broader set).

**Severity:** LOW

**Recommendation:** After the resolver-only `ValueError` block, wrap
the `transition_application(...)` call in `try/except Exception as
exc: raise_known_application_error(exc)` so the bridge inherits every
mapping the helper supports without re-listing exception classes.
This also future-proofs the bridge against helper-mapper additions.
If broad-catch is undesirable, narrow the explicit tuple to *exactly*
what the helper supports today by referencing a single source-of-truth
constant the helper exports.

## A2 — `RootShell` officer-only queue nav has no specified discovery mechanism

**Concern:** §3 says `services/web/src/app/router.tsx` will "add queue
nav only when the route has officer state and have it navigate to
`/applications/queue/`," but `RootShell` today has no principal
fetch and the proposal's §5 "Signals / stores" explicitly scopes the
officer auth signal to the queue route. Without specification, an
implementer may either (a) skip the queue link entirely, leaving
officers without a nav entry, or (b) introduce a parallel `/api/me`
fetch from `RootShell` whose cache key collides with the queue
route's `createQuery`, causing duplicate fetches or stale-officer-on-
nav races. Neither outcome is tested by the proposal's Playwright
spec, since the listed officer-queue tests all navigate directly to
`/applications/queue/` and never exercise `RootShell` officer-link
visibility.

**Evidence:**
`proposals/13-init-133B-i-officer-queue.md:66` (queue-nav requirement);
`proposals/13-init-133B-i-officer-queue.md:402-411` (route-local-only
auth signal);
`proposals/13-init-133B-i-officer-queue.md:457-467` (officer-queue
tests, all direct-navigation).

**Severity:** MEDIUM

**Recommendation:** Either (1) explicitly defer the conditional queue
nav to a follow-up slice and ship `RootShell` without a queue link
in 133B-i, or (2) specify a single shared principal `createQuery` in
`AppProviders` (or a route-loader keyed identically to the queue
route's principal query) and add a Playwright assertion that the
queue link renders only when `groups` includes `officers` AND
`discord_user_id` is non-null, plus a negative test that anonymous /
non-officer principals do not see the link.

## A3 — Non-discord-member resolver branch matched by substring against `ValueError` message

**Concern:** The bridge's resolver-only mapper (proposal §4) maps
the "bound to a non-discord member row" case via
`if "non-discord member row" in str(exc): raise HTTPException(...,
"officer_discord_member_invalid")`. The current resolver actually
raises
`ValueError("discord_user_id is already bound to a non-discord member
row")` (per `services/api/app/services/members.py:~187`), and the
"invalid Discord snowflake" branch raises a different `ValueError`
with that exact phrase. A future refactor of `members.py` that
rephrases either message — e.g., "snowflake is already bound to a
non_discord member" or localization — silently breaks the bridge
mapper: the `ValueError` falls through, FastAPI renders 500
`internal_error`, and the officer UI treats it as a transient backend
fault instead of "Officer Discord identity is bound to a non-discord
member." The proposal's failure-mode table at §6 promises a 422 here,
but the substring lookup is the only guard.

**Evidence:**
`proposals/13-init-133B-i-officer-queue.md:253-262` (substring branch);
`proposals/13-init-133B-i-officer-queue.md:432-433` (failure-mode
table promising 422); `services/api/app/services/members.py:~180-200`
(message wording).

**Severity:** MEDIUM

**Recommendation:** Replace the substring match with a typed
exception. Either (a) introduce
`MemberDiscordIdentityConflictError(ValueError)` in
`services/api/app/services/members.py` and have
`resolve_or_create_real_discord_member` raise it for the non-discord-
member case, then the bridge `except` clauses on the typed class; or
(b) raise a typed `InvalidDiscordSnowflakeError` for the format case
and a typed `MemberKindMismatchError` for the bound-to-non-discord
case, mapping each in its own resolver-only branch. Add a regression
test in `services/api/tests/test_web_officer_applications.py` that
binds a snowflake to a non-discord member row and asserts the bridge
returns `422 officer_discord_member_invalid` — currently the
proposal's §7 test list mentions this case but does not pin the
mapper against the resolver's wording.

## A4 — `x-pomerium-claim-groups` parser assumes a single header instance at runtime, but only static config locks it

**Concern:** The version-tolerant parser in §3 / §6 (A6 corrective)
inspects "the value" of `x-pomerium-claim-groups`, treating it as a
single string. The proposal's static Pomerium test asserts the
header appears exactly once in `jwt_claims_headers` config, locking
the config side. But at runtime, headers can arrive duplicated for
reasons outside the Pomerium config — duplicate `add_header`
directives in the web nginx, a sidecar adding identity headers, or
an ingress that forwards repeated values. FastAPI's default
`request.headers.get("x-pomerium-claim-groups")` returns one of the
copies (typically the first); the parser sees only that value, the
other potentially silently dropped. If the duplicates split a real
officer's groups across two header instances, the officer is
mis-classified as non-officer.

**Evidence:**
`proposals/13-init-133B-i-officer-queue.md:72` (parser spec);
`proposals/13-init-133B-i-officer-queue.md:105` (static-config single-
instance assertion); `proposals/13-init-133B-i-officer-queue.md:512`
(static-test single-header lock).

**Severity:** LOW

**Recommendation:** Switch the parser to read all header instances
via `request.headers.getlist("x-pomerium-claim-groups")`, then apply
the existing JSON-array / CSV split logic across the concatenated
result. Add a unit test in
`services/api/tests/test_web_identity.py` covering two header
instances `["officers", "admins"]` resolving to
`groups == ["officers", "admins"]`. The static config-side single-
instance assertion remains, but defense-in-depth at the parser closes
the residual ingress-misconfiguration gap.

## A5 — Officer-group classification logic is duplicated between `/api/me` and the web-officer bridge

**Concern:** Per §6 step 6, "the web-officer bridge applies the same
exact group parsing rule" as `/api/v1/me`. Two implementations of the
same parser invite drift. If `/api/me`'s parser later accepts
trailing whitespace differently from the bridge's, an officer can be
classified as `officers` by the SPA UX (queue link visible) but
non-officer by the server (403 from `/api/web/officer/applications`),
or vice versa. The proposal's tests cover both layers but don't pin
them to a shared implementation.

**Evidence:**
`proposals/13-init-133B-i-officer-queue.md:72` (`me.py` parser);
`proposals/13-init-133B-i-officer-queue.md:421-422` (bridge applies
"the same exact group parsing rule").

**Severity:** LOW

**Recommendation:** Extract a single
`parse_pomerium_groups(request: Request) -> list[str]` helper in
`services/api/app/api/v1/endpoints/me.py` (or a shared module) and
call it from both the `/api/v1/me` endpoint and the web-officer
bridge. Add a test that imports the helper directly with the four
documented inputs (absent, `"officers"`, `"officers, admins"`, JSON
array) plus the empty-string case, so the parser surface is locked
once and reused.

## Verdict reasoning

LOW. The proposal correctly composes Pomerium identity, officer-group
membership, snowflake-shaped Discord claim, member resolution, and
the existing application authority model; it never reads
`applicant_receipt` from officer paths and never uses browser-supplied
actor headers; the claim path runs identity validation before
`parse_if_match_strong(request)`, preserves strong-ETag symmetry with
the direct endpoint via `set_etag(response, result.etag)`, and uses
the shared `raise_known_application_error` mapper after a separate
resolver-only `ValueError` block that prevents resolver errors from
being mis-mapped. Pomerium route ordering uses exact-path entries
plus nested prefixes ahead of the public catch-all and includes
collision-class static fixtures. The applicant flow DOM contract,
sessionStorage keys, payload shape, and `#submit-status` selector
are explicitly preserved with intentional tightening
(`checking`/`anonymous` no longer renders tabs/details) called out
in §3 and locked by added Playwright assertions. The two MEDIUM
findings (A2 RootShell officer-link discovery; A3 substring-matched
resolver `ValueError`) are silent-failure risks the test plan does
not currently catch, but neither breaks the applicant flow nor
introduces an authorization bypass — they degrade officer UX (missing
nav link) or fault rendering (500 instead of 422). The remaining
findings are LOW. With the recommendations applied, the gate is
clear for implementation.
