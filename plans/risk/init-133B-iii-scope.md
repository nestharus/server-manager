# INIT-133B-iii — Scope risk gate

**Verdict:** LOW

β-iii is the third (final) β-slice. The proposal stays tightly bounded to two
new bridge POSTs plus mutation controls inside the existing detail route, with
no Pomerium policy change, no schema/permission/actor-kind churn, no new e2e
number, and no Discord-visible side effects.

## In scope (justified)

- **Two new bridge POSTs in `services/api/app/api/v1/endpoints/web.py`:**
  `POST /api/v1/web/officer/applications/{application_id}/messages` and
  `POST /api/v1/web/officer/applications/{application_id}/transitions`.
  Both reuse `_build_officer_actor` verbatim (verified at `web.py:75`),
  `_db` (verified at `web.py:48`), `parse_if_match_strong` / `set_etag`
  for transitions (β-i pattern), and `raise_known_application_error` for
  service-error mapping. No edits to β-i `_build_officer_actor`, no edits
  to β-i `officer_list_applications` (`web.py:147`) or
  `officer_claim_application` (`web.py:199`), no edits to β-ii
  `officer_read_application` (`web.py:180`) or
  `officer_read_application_transcript` (`web.py:262`).
- **One new bridge contract:** `OfficerApplicationMessageAppendRequest` in
  `services/api/app/contracts/web.py` carrying `body_markdown`, `visibility`,
  `client_message_id`. Author fields are *not* exposed to the browser —
  bridge fills them from `_build_officer_actor` so that browser-supplied
  identity is never trusted. Transitions reuse the existing
  `ApplicationTransitionRequest` direct contract verbatim
  (`services/api/app/contracts/applications.py:249-260`). No new
  identity claim, no new actor kind, no new permission.
- **`ApplicationDetailRoute.tsx` extension** (β-ii's existing route): mount
  the composer and transition action group below metadata/transcript, own
  refetch-after-mutation, conflict notices, and stale-version recovery.
  No new top-level route. `services/web/src/app/router.tsx` is **not**
  in the modified-files list (proposal §3) — confirmed by absence.
- **Three new SPA components colocated under `services/web/src/features/officer/`:**
  `applicationStateMachine.ts` (table-driven helper deriving exposed action
  set from `VALID_TRANSITIONS`, verified to exist at
  `services/api/app/services/applications.py:65`),
  `ApplicationMessageComposer.tsx`, and `ApplicationTransitionActions.tsx`.
  Each has a single, route-local responsibility.
- **`services/web/src/api/client.ts` expansion:** add
  `applicationMessageVisibilitySchema`, `applicationMessageAppendRequestSchema`,
  `applicationMessageReadSchema`, `applicationTransitionActionSchema`,
  widen `applicationTransitionRequestSchema` from claim-only to the
  β-iii supported subset, and add `appendOfficerApplicationMessage` /
  `transitionOfficerApplication` using the existing `ApiError` and fetch
  patterns. Schema additions are additive; the widened transition schema
  retains the claim shape β-i ships.
- **Compact mutation styles in `services/web/src/features/officer/officer.module.css`.**
  Existing module, no global system change.
- **API tests in `services/api/tests/test_web_officer_applications.py`:**
  extend with message append (binding, spoofing guard, idempotency),
  transition (`If-Match` 412/428, happy `review`/`approve`, denied permission,
  not-owner 409, required-field mappers), and expand the dependency-tree
  guard from list+claim+detail+transcript to **6 routes** while preserving
  the locked no-`get_current_actor` / no-`CURRENT_ACTOR.get` /
  no-`verify_applicant_receipt` / no-`applicant_receipt` source assertions.
- **Component tests** in `services/web/tests/officer-actions.spec.ts`
  *or* extending `services/web/tests/officer-detail.spec.ts` — proposal
  §3 admits both paths; either is bounded.
- **Test 19 e2e + browser-flow extension:** seed `application.review` and
  `application.approve` grants, drive `claim → review → approve` from the
  detail route, and assert Postgres state + audit-row request surface
  after each transition. Test number stays 19. No new e2e number.
- **Static fixture/check extensions:** `infra/tests/fixtures/web-ui/contract.json`
  and `infra/tests/validate_web_ui_local.sh` add the two new browser API
  paths and confirm absence of `/api/v1/` literals in SPA source.

## Out of scope (deferred / explicit anti-scope §8)

- **`route` action.** Service rejects route before state-machine execution
  (`services/api/app/services/applications.py:1068-1074`); β-iii does not
  ship a deferred stub. Route stays unexposed.
- **`reassign` UI / owner picker / member search.** Requires owner-selection
  UX outside this slice. A future BL item owns it.
- **Claim button on the detail page.** β-i queue remains the claim surface.
- **Bulk actions / multi-select queue / batch transitions.**
- **Discord-visible side effects on transitions** — DMs, channels, embeds,
  role changes, moderation. **BL-009** owns Discord rollout
  (`plans/BACKLOG.md:646-647`).
- **Applicant DM materialization.** **BL-020** owns it.
- **Message editing, deletion, threading, replies, attachments, markdown
  rendering beyond escaped text, transcript pagination/filters/SSE/WebSocket/polling.**
- **Schema migration, new permission, new actor kind, new Authentik/Pomerium
  route, applicant-receipt-as-officer-identity, browser actor headers,
  feature flags, compatibility shims, deprecated aliases, placeholder
  stubs** (§8 + `AGENTS.md:564-583`).
- **Edits to β-i queue route, β-i claim endpoint, β-ii detail/transcript
  GETs, `_build_officer_actor`, applicant-form route, public submit
  endpoints, admin chapters route, applicant-receipt machinery.**

## Risk surface

| Area | Pre (post-β-ii) | Post (β-iii) | Justification |
|---|---|---|---|
| Officer bridge surface | 4 endpoints: `GET /admin/chapters`, `GET /officer/applications`, `GET /officer/applications/{id}`, `POST /officer/applications/{id}/claim`, `GET /officer/applications/{id}/transcript` (verified `web.py:52,146,179,195,258`) | + `POST /officer/applications/{id}/messages`, + `POST /officer/applications/{id}/transitions` | Two POST adds; reuse `_build_officer_actor`, `_db`, `parse_if_match_strong`, `set_etag`, `raise_known_application_error` verbatim |
| `_build_officer_actor` | Single helper, β-i shape | Identical | No edits; both new endpoints call it as-is |
| SPA routes | `/`, `/applications`, `/applications/queue`, `/applications/$applicationId`, `/admin/chapters` | Identical | No new route; mutation lives inside β-ii's `ApplicationDetailRoute` |
| `ApplicationQueueRoute.tsx` | β-i+β-ii claim + filter + per-row detail nav | Identical | Not in §3 modified-files; explicitly out of scope per check-list item 2 |
| `ApplicationDetailRoute.tsx` | β-ii read-only metadata + responses + transcript | Same + composer mount + transition action group + post-mutation refetch + conflict/stale notices | Localized extension; no auth-bootstrap or fetch-pattern rewrite |
| `client.ts` | β-ii fetchers + `applicationReadSchema` (explicit fields) + claim-only `applicationTransitionRequestSchema` | + 3 message schemas, + transition action enum, + widened transition request schema, + 2 mutation fetchers | Additive; β-i claim caller continues to work because widened schema still admits the claim shape |
| Pomerium routes | β-i `/api/web/officer/` (line 62) + β-ii `/applications/` (line 80) | Identical | New POSTs fall under existing prefixes; gitops yaml not in §3 modified-files |
| Identity / authority | Pomerium → officers group → discord_user_id → real Discord member → `ActorIdentity(user, member uuid)` | Identical | No new claim, no new group, no new actor kind |
| Permission surface | Existing `application.message` + `application.{review,request_interview,waitlist,approve,deny,reactivate,withdraw}` (verified `applications.py:348-362`) | Identical | β-iii consumes existing permissions; no new permission name introduced. e2e seeds 3 grants for the live leg |
| Action set exposed to UI | β-i: `claim` only | + 7 non-claim actions | `route` and `reassign` and `claim` excluded; bridge validation rejects `route`/`reassign` to prevent broken-control shipping |
| Backend services touched | None — read paths only | None — message append delegates to `append_application_message`, transitions delegate to `transition_application` and `require_transition_authority` (all pre-existing) | Reuses INIT-131 messages substrate and INIT-133A transition machinery |
| Database / schema | Unchanged since β-i | Unchanged | No migration, no new column, no new table, no new index |
| Authentik | β-i officer Discord OAuth source + officers group | Unchanged | No new app, source, scope, or group |
| `applicant_receipt` cookie | Untouched by bridge | Untouched | Bridge ignores receipts and `X-Actor-*` for all 6 officer routes; guard test extended to cover the 2 new routes |
| Optimistic locking | β-i claim uses `If-Match` round-trip | Same pattern reused for transitions | Bridge calls `parse_if_match_strong` and `set_etag` (β-i pattern) — no new locking primitive |
| Idempotency | β-i claim has no client-side dedupe (single action) | Message append uses direct-API `client_message_id` semantics: 201 created / 200 duplicate (verified `services/api/app/services/application_messages.py:93-100`) | No new idempotency mechanism — preserves the direct endpoint's contract |
| Test surface | β-ii detail/transcript bridge tests + officer-detail spec + e2e post-claim leg + Pomerium route-order assertion | + message + transition bridge tests, + officer-actions spec (or extended officer-detail), + e2e `review→approve` leg with Postgres assertions, + 6-route dependency-tree guard | Each test covers code shipped here; e2e number stays 19 |

## Splittable concerns

- **Messages POST vs transitions POST could in principle land separately.**
  They do not depend on each other at the bridge layer. The proposal
  bundles them because (a) both are bound to the same detail-route surface,
  (b) the e2e leg verifies append + `review` + `approve` together as one
  proof of claim → review → approve, and (c) the diff budget (`+720/-30`,
  fail at `+900`) is well below twice the per-endpoint cost of split slices.
  Bundling is a correct call.
- **Action button group could in principle ship per-action.** The proposal
  ships the supported subset together because action visibility is a single
  table-driven helper derived from `VALID_TRANSITIONS`, and per-action
  shipping would require shipping the same helper N times or shipping
  half-disabled buttons. Bundle is correct.
- **The `applicationTransitionRequestSchema` widening is NOT separately
  splittable** from the transition POST — they are the same wire contract.

## Verdict reasoning

LOW. The slice extends β-ii's detail surface with mutation, and is
additive across every check on the gate:

1. **Bridge** — Two POSTs reusing `_build_officer_actor` verbatim
   (verified `web.py:75`); no helper edits, no new identity logic. β-i
   claim's `If-Match`/ETag pattern is reused, not duplicated. Error
   mapping reuses `raise_known_application_error` already in `_shared.py`.
   ✅ check 1.
2. **SPA** — Composer + transition group + state-machine helper colocated
   in `features/officer/`, mounted inside β-ii's `ApplicationDetailRoute`.
   No new top-level route. Queue route not modified. ✅ check 2.
3. **No new permission, schema, or actor kind.** §6 mapping consumes
   existing `application.{message,review,request_interview,waitlist,
   approve,deny,reactivate,withdraw}` permissions. `route` is excluded
   because the service rejects it; `reassign` is excluded pending owner
   picker. ✅ check 3.
4. **No Pomerium policy change.** β-i `prefix: /api/web/officer/` (line 62)
   covers the new POSTs; β-ii `prefix: /applications/` (line 80) covers
   the detail route the SPA mutation surface lives on. gitops yaml not
   in §3 modified-files. ✅ check 4.
5. **Test 19 extended, not duplicated.** Browser-flow gains a
   `review → approve` leg after the existing claim assertion; Postgres
   assertions verify state and audit request-surface. ✅ check 5.
6. **No reassign UI, no bulk actions, no Discord-visible side effects.**
   §8 anti-scope is explicit; BL-009 (Discord rollout) and BL-020 (DM
   materialization) are deferred by name. ✅ check 6.
7. **Diff budget** is `+720 / -30` with a documented fail-condition at
   `+900` net or any new permission / schema migration / Authentik /
   Pomerium / `route`-or-`reassign` implementation.

Two judgment calls worth naming explicitly — both LOW-risk:

- The β-i `applicationTransitionRequestSchema` is widened from claim-only
  to the β-iii supported subset. Existing β-i claim caller remains valid
  because the widened union still admits the claim shape; this tightens
  the SPA contract rather than breaking it.
- The proposal admits both a new spec file (`officer-actions.spec.ts`)
  and folding into `officer-detail.spec.ts`. Either is in-scope; the
  choice is a small implementation call, not a scope decision.

No "while we're at it" cleanups, no audits of pre-existing systems, no
scope leakage outside the officer detail surface, no Discord-visible work
sneaking in ahead of BL-009.

SCOPE_DONE: plans/risk/init-133B-iii-scope.md
