# INIT-133B-iii — Shortcut risk gate

**Verdict:** LOW

## S1 — `ApiError` reuse vs. parallel error class

**Choice:** §3 (Modified files / `services/web/src/api/client.ts`) and
§5 (API client functions and schemas) lock the new
`appendOfficerApplicationMessage` and `transitionOfficerApplication`
client functions to "the existing `ApiError` and fetch patterns
(`services/web/src/api/client.ts:80-84`,
`services/web/src/api/client.ts:280-303`)". No new error class is
introduced; the schemas widen `applicationTransitionRequestSchema`
beyond claim and add message append/read schemas, but error mapping
flows through the same `ApiError` envelope used by the queue and
detail clients in β-i / β-ii.

**Risk:** a parallel error class would split error-handling code
paths, drop status-code parity with the direct API, and force the
detail route to branch on two error shapes (queue / claim still
throw `ApiError`).

**Mitigation:** explicit reuse of `ApiError`; the proposal's
"stable notices" requirement for `409 / 412 / 428 / 403` and Zod
parse failures is implemented against the existing error shape, and
the transition bridge maps service exceptions through the same
shared `raise_known_application_error` helper used by the direct
lifecycle endpoint.

**Verdict:** Not a shortcut.

## S2 — Zod schemas mirror Pydantic; transition body uses `ApplicationTransitionRequest`

**Choice:** §3 says the transition bridge "body mirrors
`ApplicationTransitionRequest` (`services/api/app/contracts/applications.py:249-260`)",
which is the existing Pydantic contract whose discriminator is
`action: ApplicationTransitionAction` and whose optional fields are
`notes`, `decision_reason`, `thread_id`, `reason`, `new_owner_id`,
plus the service-only `originating_actor_*` fields. §5 declares
`applicationTransitionRequestSchema` includes the direct request
fields (`notes`, `decision_reason`, `thread_id`, `reason`,
`new_owner_id`).

There is one deliberate narrowing: the SPA's
`applicationTransitionActionSchema` is the β-iii exposed subset
(seven actions: `review`, `request_interview`, `waitlist`,
`approve`, `deny`, `reactivate`, `withdraw`) instead of the full
`ApplicationTransitionAction` enum. The proposal documents this
explicitly: "its action enum is the beta-iii exposed subset, not
`claim`, `route`, or `reassign`." The bridge mirrors the same
narrowing on the server side: `claim` stays on its own β-i route,
and `route` / `reassign` return `422 validation_error` rather than
rendering unusable controls. The Pydantic transition service still
sees the canonical `ApplicationTransitionRequest` because the bridge
passes through to `transition_application`.

**Risk:** an action enum drift between client Zod and Pydantic
would let an officer click a button the service then rejects, or
hide an action the service supports.

**Mitigation:** the narrowing is symmetric (client narrows + bridge
narrows + state-machine helper narrows), and §3 / §7 tie the helper
back to `VALID_TRANSITIONS` so the server table remains the source
of truth. The optional-field shape (`notes`, `decision_reason`,
`thread_id`, `reason`, `new_owner_id`) is preserved verbatim.

**Verdict:** Not a shortcut — bounded, documented narrowing, not
silent divergence.

## S3 — Bridge does NOT use `Depends(get_current_actor)`, `verify_applicant_receipt`, or `applicant_receipt` cookie

**Choice:** §3 (Modified files / `services/api/app/api/v1/endpoints/web.py`)
and §6 lock both new POST endpoints to the β-i actor lock: "Reuse
`_build_officer_actor` for Pomerium identity, officer group
membership, Pomerium `discord_user_id`, real Discord member
resolution, and `ActorIdentity(user, member_uuid)` construction
(`services/api/app/api/v1/endpoints/web.py:75-129`)." §7 extends
the dependency-tree guard: "Dependency-tree guard expands to
include the two POST routes while preserving no
`get_current_actor`, no `CURRENT_ACTOR.get`, no
`verify_applicant_receipt`, and no `applicant_receipt` source
assertions (`services/api/tests/test_web_officer_applications.py:170-177`)".
Q4 explicitly says: "the bridge fills author fields from
`_build_officer_actor` because the direct append request requires
author fields ... and browser-supplied author identity is not
trusted."

§7 message-append tests further lock this with named risks
`message_actor_binding` and `message_actor_spoofing`: "Message
append ignores applicant receipt and `X-Actor-*`, recording author
fields from the Pomerium-resolved officer."

**Risk:** the most dangerous shortcut — letting the browser forge
officer identity for message append or transitions, or silently
inheriting the applicant-receipt actor on officer routes.

**Mitigation:** same lock as β-i / β-ii (server-side identity
construction, dependency-tree assertion, attacker-headers test on
both new routes), explicit "no browser-supplied author fields" rule
on message append, and reuse of the β-i officer-bridge actor
machinery rather than a new identity path.

**Verdict:** Not a shortcut.

## S4 — Single transition bridge endpoint covers all 8 actions

**Choice:** §2 (Q1) and §3 lock "one bridge endpoint:
`POST /api/v1/web/officer/applications/{application_id}/transitions`",
mirroring the direct lifecycle single transition route. §3 (Bridge
endpoint shapes) reiterates: "The transition bridge accepts only
the beta-iii action set: `review`, `request_interview`, `waitlist`,
`approve`, `deny`, `reactivate`, and `withdraw`. `claim` stays on
`/claim`; `route` and `reassign` return `422 validation_error` from
bridge validation rather than rendering unusable controls."

There are no per-action shortcut endpoints (no
`/transitions/review`, no `/transitions/approve`, etc.). β-i's
`/claim` remains separate because β-i owns it; β-iii does not add
sibling per-action endpoints to that pattern.

**Risk:** per-action endpoints would multiply the bridge surface,
duplicate If-Match parsing and authority handling, and let one
endpoint drift from another in error mapping or audit-record
request surface.

**Mitigation:** single endpoint, single mapper call, single
If-Match path. Action set is gated by client narrowing + bridge
422 + state-machine helper, which collectively keep `claim`,
`route`, `reassign` from sneaking in.

**Verdict:** Not a shortcut.

## S5 — State machine helper is data-driven from `VALID_TRANSITIONS`

**Choice:** §3 (New files) introduces
`services/web/src/features/officer/applicationStateMachine.ts` as a
"route-local helper that maps `ApplicationState` to exposed
transition actions and required input metadata, derived from
`VALID_TRANSITIONS`." §2 (Q3) spells out the table: "`claimed ->
review, withdraw`; `in_review -> request_interview, waitlist,
approve, deny, withdraw`; `interview -> waitlist, approve, deny,
withdraw`; `waitlisted -> reactivate, withdraw`; terminal states
show no controls." §5 (State machine helper) declares
`validOfficerTransitionActions(state)` and
`transitionActionInput(action)` as the two table-driven entry
points, and says "The helper is intentionally small and
table-driven. It mirrors only the beta-iii exposed subset of
`VALID_TRANSITIONS`; direct API and service validation remain
authoritative."

The mapping in Q3 is consistent with the on-disk table at
`services/api/app/services/applications.py:65-89` (`claimed -> review`
maps to `in_review`; `in_review -> request_interview/waitlist/approve/deny`
all valid; `waitlisted -> reactivate` maps to `claimed`; withdraw
covers the documented states).

**Risk:** if the helper hardcoded scattered `if (state === "claimed"
&& action === "review") ...` conditionals across components, the
button visibility would drift from `VALID_TRANSITIONS` and the API
would reject clicks an officer was led to make.

**Mitigation:** explicit single helper, narrow API
(`validOfficerTransitionActions(state)` returns the readonly set),
component test
(`group=TG-4; named_risk=state_machine_visibility`)
asserts the per-state visibility matrix end-to-end, and the
authoritative `VALID_TRANSITIONS` table remains in the service
layer where transitions are still rejected if the helper drifts.

**Verdict:** Not a shortcut.

## S6 — Tests exercise REAL bridge round-trips with Postgres verification

**Choice:** §7 E2E plan extends `infra/tests/e2e/tests/19-web-ui.sh`
and `infra/tests/e2e/lib/playwright/browser-flow.mjs` with the
chain `submit -> claim -> review -> approve` and explicit Postgres
assertions:

> "Submit `review` with notes; assert the UI state becomes
> `in_review`, then query Postgres and assert `applications.state =
> 'in_review'` and an `application.review` audit row has request
> surface `/api/v1/web/officer/applications/{id}/transitions`."
>
> "Submit `approve` with decision reason; assert the UI state
> becomes `approved`, then query Postgres and assert
> `applications.state = 'approved'`, `decision_reason` is set, and
> action type is `application.decision`."

API bridge tests in §7 also cover real wire-format edges: 428 on
missing `If-Match`, 412 on stale, 409 on `application_not_owner`,
403 on `authority_decision_denied`, and the message bridge's 201/200
idempotency contract. Component tests assert mocked round-trips
(body, visibility, `client_message_id`, `If-Match` header) rather
than UI snapshots, with named risks `message_idempotency`,
`transition_optimistic_locking`, and `state_machine_visibility`.

**Risk:** Playwright snapshot-only tests would mask broken header
wiring, allow the bridge to silently fall through to the server
version, or hide message-visibility regressions where officer-only
content reaches the applicant transcript.

**Mitigation:** real Postgres assertions on `applications.state`,
`decision_reason`, and audit `request_surface` after the e2e
transition leg; mocked round-trip assertions on every contract
edge (header, query, body); audit request surface tied to the
bridge path, not the direct lifecycle path.

**Verdict:** Not a shortcut.

## S7 — Message composer `client_message_id` freshness + same-compose idempotency

**Choice:** Q4 locks the composer's idempotency contract: "After
success, clear the textarea, generate a fresh UUIDv4
`client_message_id`, and refetch transcript so the returned
`ApplicationMessageRead` is visible inline. If the same compose is
retried with the same `client_message_id`, preserve direct endpoint
idempotency: created returns 201 and duplicate returns 200
(`services/api/app/api/v1/endpoints/applications/messages.py:49-76`,
`services/api/app/services/application_messages.py:93-100`)."

§5 (Component contract preview) reiterates: "The component owns
`bodyMarkdown`, `visibility`, `clientMessageId`, and `submitting`
signals ... Successful append clears body, keeps the selected
visibility, rotates the idempotency UUID, and asks the route to
refetch transcript." §7 includes
`group=TG-2; named_risk=message_idempotency` to lock the 201/200
distinction in API tests.

**Risk:** reusing a single `client_message_id` across composes
would either reject the second send (if the service treats it as
duplicate of unrelated content) or, worse, allow duplicate
messages with the same idempotency token to slip through if the
content differed. Conversely, generating a new UUID on every retry
of the same compose would defeat idempotency.

**Mitigation:** UUID is rotated only on success (and on initial
mount); retry of the same compose reuses the token until success.
The proposal explicitly cites the direct service idempotency
behavior so the client/server contract is consistent.

**Verdict:** Not a shortcut.

## S8 — No "TODO: handle reassign later" / "we'll add bulk actions later" stubs

**Choice:** §2 (Q2 and Q8), §6, and §8 enumerate scope exclusions
as ownership transfers to other tickets, not as in-code TODOs:

- `route` is excluded because the service rejects it before
  state-machine execution (`services/api/app/services/applications.py:1068-1074`),
  so adding a button now would be "a deferred stub." The proposal
  refuses to ship one.
- `reassign` is excluded because it requires an owner picker; the
  follow-up is a future BL item, not a placeholder.
- Bulk actions, search/sort/filter expansion, message
  editing/deletion/threading, attachments, real-time updates,
  Discord-visible side effects, DM materialization, schema
  migrations, new permissions/actor kinds, feature flags,
  compatibility shims, deprecated aliases, and placeholder stubs
  are all in §8 anti-scope and ticket-routed (BL-009, BL-020, future
  BL items).

The permission table in §6 also avoids stubbing: it does not
pretend `reassign` is a one-line later add; it states that
`reassign` "requires owner selection" and is therefore out of
scope.

**Risk:** half-finished `// TODO: handle reassign` stubs or
greyed-out buttons with future-action tooltips would leak into the
SPA, break visual contracts in β-iv work, and let the diff budget
mask incomplete features.

**Mitigation:** Q8's anti-scope is concrete and ticket-routed; the
diff budget (§9) mandates that exceeding `+900` net lines or adding
`route`/`reassign` should "fail and split the work" rather than
ship stubs.

**Verdict:** Not a shortcut.

## S9 — Transition `If-Match` derived from latest `ApplicationRead.version`, not stale cache

**Choice:** Q5 locks the optimistic-locking flow: "Transitions
require `If-Match: \"<version>\"` derived from the current
`ApplicationRead.version`. The bridge calls
`parse_if_match_strong(request)` and forwards `expected_version`
into `transition_application`, then sets the returned ETag with
`set_etag(response, result.etag)`, matching the direct endpoint
(`services/api/app/api/v1/endpoints/applications/lifecycle.py:134-146`)
and the existing claim client pattern
(`services/web/src/api/client.ts:280-303`)."

§5 (Transition action button group) confirms client-side:
"Submission sends `expectedVersion: application.version`." §6 says
"On success, replace the route's application with the response,
then refetch detail and transcript. On `412 stale_application_version`
or `428 if_match_required`, show a stale/precondition notice and
refetch." Component test in §7 asserts "Transition success sends
`If-Match`, replaces application state/version, and refetches
transcript."

**Risk:** if the SPA cached an `ApplicationRead.version` from
mount and reused it after a successful prior transition (or after
a transcript-only refetch), a subsequent click would race on a
stale version, surfacing 412 to the user even though the local UI
already showed the new state.

**Mitigation:** the proposal explicitly threads
`application.version` through every transition, mandates a
post-success replace + refetch (so the next click sees the freshly
incremented version), and inherits the β-i `parse_if_match_strong`
helper rather than re-encoding 428 / 412 locally. Route also
refetches detail + transcript after success so any subsequent
action reads the updated version, not a stale cache.

**Verdict:** Not a shortcut.

## Verdict reasoning

INIT-133B-iii inherits the β-i actor / If-Match locks and the β-ii
read-only-detail substrate verbatim, then adds two POST bridge
endpoints (messages, transitions) plus their composer / button-group
components. The dangerous shortcuts the gate watches for are all
addressed:

- `ApiError`, `parse_if_match_strong`, `set_etag`, and
  `raise_known_application_error` are reused by direct import — no
  parallel error class, no bridge-local status re-encoding, no
  duplicate authority logic.
- The transition body mirrors `ApplicationTransitionRequest`; the
  client / bridge / state-machine helper narrow the action enum
  symmetrically to the seven β-iii actions, with `claim` staying on
  its β-i endpoint and `route` / `reassign` rejected at the bridge
  rather than rendered as TODO buttons.
- Both POST endpoints construct `ActorIdentity` server-side via
  `_build_officer_actor`, ignore `X-Actor-*`, and never read the
  `applicant_receipt` cookie; the dependency-tree guard expands to
  cover the new routes.
- One bridge endpoint covers all seven exposed transitions; the
  state-machine helper is a single table-driven function derived
  from `VALID_TRANSITIONS`, not scattered conditionals.
- E2E exercises a real submit → claim → review → approve chain
  with Postgres `applications.state`, `decision_reason`, and audit
  `request_surface` assertions. Component tests assert mocked
  round-trips (body, visibility, header, idempotency token), not
  pixel snapshots.
- The message composer rotates `client_message_id` on success and
  preserves it across same-compose retries, with the 201/200
  contract locked in API tests.
- Anti-scope is concrete and ticket-routed; no `route`/`reassign`
  stubs, no bulk-action placeholders, no feature flags, no TODO
  comments planned. The diff budget self-fails rather than ship a
  half-finished slice.
- Transitions thread the live `ApplicationRead.version` into every
  click, with post-success replace + refetch so the next action
  reads a fresh version, not a stale cache.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-133B-iii-shortcut.md
