# INIT-133B-i — Shortcut risk gate

**Verdict:** LOW

## S1 — `any`, TODO, "for now" markers

**Choice:** the proposal's section 5 says "All client functions
validate with Zod; no `any`" and explicitly commits to removing
the existing `router: any` in `services/web/src/app/providers.tsx:24`.
Section 10's shortcut self-review repeats: "No `TODO`, no `any`,
no feature flag, no old vanilla fallback, no browser actor
headers, and no UI-only test skip."

**Risk:** if the implementation slips a `// for now` past review,
the migration becomes a parallel-systems hazard for 133B-ii.

**Mitigation:** Zod schemas are required for the principal
(`groups: list[str]`), `ApplicationRead`, `ApplicationListRead`,
the transition request/response, and the applicant Discord
identity — i.e. every payload the route consumes. The proposal
also names the pre-existing `any` site that must be removed,
so a residual `any` would be a regression caught in code review.

**Verdict:** Not a shortcut.

## S2 — Tests weakened because "it's a UI slice"

**Choice:** three test layers: a new
`services/web/tests/officer-queue.spec.ts` (Playwright component
mocks), a new `services/api/tests/test_web_officer_applications.py`
(real bridge tests), and an extension of
`infra/tests/e2e/tests/19-web-ui.sh` + `browser-flow.mjs` that
performs a real claim and verifies in Postgres that
`state='claimed'` and `owner_id` resolves to a non-synthetic
Discord member. The fixture-loading and risk-annotation pattern
from `services/web/tests/compat.spec.ts:36-48,202-220` is
preserved.

**Risk:** if component tests carried the entire burden, the
suite would only prove "the UI sends what we mocked," not "the
backend honors the real claim." That would be a UI-slice
shortcut.

**Mitigation:** the API-level tests directly assert
"web officer claim maps receipt to member actor" and
"web officer claim stale version returns conflict/precondition
failure" against the real bridge, and the e2e test asserts the
Postgres state change. There is no UI-only path through claim
or list.

**Verdict:** Not a shortcut.

## S3 — Zod schemas thinned to `unknown`

**Choice:** "Zod schemas must mirror Pydantic contracts instead
of parsing untyped JSON" (section 10) and section 5 enumerates
the required schemas including `applicationStateSchema`,
`applicationReadSchema`, `applicationListReadSchema`, principal,
and Discord identity. The schemas mirror
`services/api/app/contracts/applications.py:352-372` and
`:375-377`.

**Risk:** if a future hand thins these to
`z.object({ /* ... */ }).passthrough()` or `z.unknown()`,
contract drift between API and SPA becomes silent.

**Mitigation:** the proposal locks the schemas to specific
Pydantic counterparts and runs the contract fixture
(`infra/tests/fixtures/web-ui/contract.json`) against them. The
existing `compat.spec.ts` precedent of contract-derived
fixtures is reaffirmed.

**Verdict:** Not a shortcut.

## S4 — `If-Match` / optimistic locking on the claim path

**Choice:** Q6 explicitly: "The web-officer bridge sends
`If-Match: \"<row.version>\"`, because the endpoint requires a
strong ETag" — matching `parse_if_match_strong` in
`services/api/app/api/v1/endpoints/applications/_shared.py:33-56`.
The browser sends `{ "expected_version": 3 }`; the bridge
translates that into the `If-Match` header before calling the
existing transition service. `412 stale_application_version`
and `409 application_already_claimed` are handled in both UI
and tests.

**Risk:** if the bridge swallowed `If-Match` or fabricated a
permissive value, two officers could claim the same row.

**Mitigation:** the bridge is required to build `If-Match` from
the client-supplied `expected_version`, and the test plan
includes "web officer queue claim conflict refetches" plus
"web officer claim stale version returns conflict/precondition
failure". The 412/409 paths are not collapsed into a generic
error.

**Verdict:** Not a shortcut.

## S5 — Browser-supplied actor identity headers

**Choice:** Q2 and the anti-scope (section 8) ban
browser-supplied `X-Actor-Kind` / `X-Actor-Id`. The bridge
verifies the existing `applicant_receipt` cookie via
`verify_applicant_receipt`
(`services/api/app/services/applicant_discord_auth.py:207-236`),
resolves the Discord member UUID via
`resolve_or_create_real_discord_member`
(`services/api/app/services/members.py:192-268`), and only then
constructs `ActorIdentity(actor_kind="user", actor_id=<member uuid>)`
server-side. The `compat.spec.ts:114-125` assertion that no
`x-discord-user-id` header reaches the API is preserved.

**Risk:** if any actor field came from the browser, the
`_reviewer_id` UUID conversion at
`services/api/app/services/applications.py:266-273` would
trust attacker-controlled data.

**Mitigation:** the bridge is the only place actor identity is
constructed; Pomerium provides the principal, the receipt
cookie provides the Discord snowflake, and the member service
maps it to a real member UUID. Browsers cannot inject an actor
id.

**Verdict:** Not a shortcut.

## S6 — Mocked-only behavior

**Choice:** every route the SPA hits has an API-level test
against the real FastAPI app
(`services/api/tests/test_web_officer_applications.py`) plus an
e2e test that exercises a real Pomerium-fronted claim against
Postgres in `19-web-ui.sh`.

**Risk:** if the slice only had Playwright mocks, the bridge
could appear correct while routing to nowhere or returning a
shape the core service does not produce.

**Mitigation:** the API tests cover Pomerium identity required,
officers group required, applicant receipt required, list
returning real `ApplicationListRead`, claim mapping receipt to
member actor (asserted via `owner_id` equality), and stale
version. The e2e test asserts a Postgres `state='claimed'`
transition with a non-synthetic owner.

**Verdict:** Not a shortcut.

## S7 — Bridge re-implementing list/claim logic

**Choice:** Q2 says the bridge "calls the existing application
list/transition services with
`ActorIdentity(actor_kind=\"user\", actor_id=<member uuid>)`,"
and the hookpoint preview (section 11) reuses "Existing
application list and transition services/contracts; do not
duplicate list/claim logic." Authority continues to be enforced
by `_has_application_list_authority` and
`require_transition_authority` inside the existing service
(`services/api/app/services/applications.py:393-446,348-362`).

**Risk:** a parallel implementation would diverge from the
core authority/transition rules, eroding the "single source of
truth" the core endpoints provide.

**Mitigation:** the bridge is a thin Pomerium + receipt-to-actor
adapter; list filtering, ordering, paging, transition state
machine, and authority checks are all delegated. The proposal
does not introduce new permission names or new state-machine
edges.

**Verdict:** Not a shortcut.

## S8 — `HomeRoute` / `AdminChaptersRoute` parity vs redesign

**Choice:** section 3 says `HomeRoute.tsx` becomes a "Solid
mirror of the current public home route" and
`AdminChaptersRoute.tsx` "preserves the current chapter table
behavior while using the corrected browser-facing
`/api/web/admin/chapters` client path." The vanilla
`main.tsx` routes for `/`, `/applications`, and `/admin/chapters`
are migrated, not redesigned. The unmounted `RuntimeApp.tsx` and
`features/forms/DarkNemesisForm.tsx` are deleted because they
were never the live runtime.

**Risk:** if the migration drifted into a redesign, it would
both blow scope and risk regressing the live applicant flow
(which `compat.spec.ts:202-291` exercises today).

**Mitigation:** section 10 Audit names every load-bearing
behavior the migration must preserve — receipt probing, draft
preservation, submit endpoint, the
`#submit-status` selector — and pins them to the existing
`compat.spec.ts` and `browser-flow.mjs` assertions. Behavior
parity, not redesign.

**Verdict:** Not a shortcut.

## S9 — Test rigor on filter, pagination, claim conflict, stale version

**Choice:** the component tests assert query-string shape on
state filter changes, request body shape on claim
(`{ expected_version: row.version }`), append-vs-replace on
load-more, and the conflict paths (`409
application_already_claimed`, `412 stale_application_version`).
These are mocked round-trips with assertions on request and
response, not snapshots.

**Risk:** snapshot-only tests would lock in the rendered DOM
without proving the request shape.

**Mitigation:** the proposal explicitly names the assertions on
request method, query string, and body — i.e. it is a
round-trip test. The matching API-level tests cover the same
contracts against the real bridge.

**Verdict:** Not a shortcut.

## S10 — E2E proof: real Postgres transition vs screenshot

**Choice:** section 7 E2E: after the existing applicant submit
in `19-web-ui.sh`, the test navigates as the Pomerium officer,
clicks claim, records the application id, and verifies in
Postgres that `state='claimed'` and `owner_id` is a real
(non-synthetic) Discord member. No screenshot-only assertion.

**Risk:** a route-hit-only e2e would not prove the state
machine, the actor mapping, or the persistence.

**Mitigation:** the test reads the state and owner directly
from Postgres via `kubectl ... psql`, mirroring the
existing `assert_public_submit_persisted` rigor at
`infra/tests/e2e/tests/19-web-ui.sh:8-37`.

**Verdict:** Not a shortcut.

## S11 — No feature flag, parallel runtime, compatibility shim, or deferred stub

**Choice:** anti-scope: "No feature flag, legacy vanilla route
fallback, or retained `RuntimeApp` parallel entry." Section 10
Audit: "removing the parallel runtime before 133B-ii and 133B-iii
build on top of it." `RuntimeApp.tsx`, demo `DarkNemesisForm`,
and the vanilla DOM bootstrap in `main.tsx` are all deleted in
this slice. `AGENTS.md`'s "No Backwards Compatibility" and
"No Deferred Stubs" sections are honored.

**Risk:** the most attractive shortcut here would be option C
from the problem map — mounting Solid Router beside `main.tsx`
— which would lock in dual-system limbo permanently. The
proposal explicitly rejects it.

**Mitigation:** option B (Solid Router as the real entry) is
chosen, and the deletions are listed in section 3 by file. The
diff budget caps at +1,250 net lines with an instruction to
fail the scope gate and split the auth bridge if exceeded —
this prevents a "ship it and iterate" expansion.

**Verdict:** Not a shortcut.

## S12 — "Officer without Discord receipt" deferred to 133B-ii

**Choice:** the officer-without-receipt case is fully handled
in 133B-i. Section 6 (authorization model) describes the
state explicitly: `/api/me` succeeds with the `officers` group
but `/auth/discord/me` returns `applicant_receipt_required`,
and the page renders a Discord login action pointing to
`/auth/discord/start?return_to=/applications/queue`. The
rationale is that `services/api/app/services/applications.py:266-273`
rejects non-UUID user actor ids on review actions, so claim
literally cannot work without a real member UUID — it must be
solved here.

**Risk:** if this were deferred, an officer without a receipt
could see the UI but every claim would 422, or worse, the
slice would silently skip the receipt check and let the bridge
mint a synthetic actor id.

**Mitigation:** the test plan includes the dedicated component
test "officer queue asks officer for Discord receipt before
data" plus the API-level test "web officer list requires
applicant receipt" returning `applicant_receipt_required`. The
e2e test injects a real applicant receipt before exercising
claim, mirroring the existing `browser-flow.mjs:47-68` cookie
fixture flow.

**Verdict:** Not a shortcut.

## Verdict reasoning

The proposal is unusually explicit about anti-shortcut
guarantees: it names every `AGENTS.md` rule that applies
("No Backwards Compatibility", "No Deferred Stubs",
"no parallel systems"), pins the diff to behavior parity for
the migrated routes, mirrors Pydantic contracts in Zod,
preserves `If-Match` optimistic locking through the bridge,
keeps actor identity construction server-side, and proves the
claim path with both a real API test and an e2e Postgres
transition. The one place the slice exceeds a "pure frontend"
shape — the web-officer API bridge — is justified by the
hard fact that the core service requires a UUID actor id that
Pomerium alone cannot provide, and the proposal explicitly
considers and rejects splitting it into a separate INIT
because the queue page cannot be honestly tested without it.
No shortcut detected.
