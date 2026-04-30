# INIT-133B-iii — Audit risk gate

**Verdict:** LOW

Scope under audit: `proposals/15-init-133B-iii-messages-transitions.md` —
two new POST officer bridge endpoints
(`POST /api/v1/web/officer/applications/{id}/messages` and
`POST /api/v1/web/officer/applications/{id}/transitions`), a SPA
message composer, a transition action button group, an
`OfficerApplicationMessageAppendRequest` bridge contract, Zod schema
extensions, and Playwright + e2e coverage. β-i and β-ii audit
invariants (M1 actor binding from Pomerium-asserted Discord claim, no
`applicant_receipt` use, no `X-Actor-*` honoring, `raise_known_application_error`
reuse, `parse_if_match_strong` for optimistic locking, direct service
calls — no HTTP self-calls, DOM contracts preserved) are preserved.

The proposal explicitly self-rates Audit LOW (proposal §10) and the
findings below confirm that. Two LOW findings (F1, F2) recommend
explicit corrections before implementation; three INFORMATIONAL notes
(F3..F5) flag documentation drift between the proposal and the
service it wraps.

## A1..A10 — Audit checks

### A1 — Bridge identity reuse and validation order — PASS

Both new bridges depend on `_build_officer_actor` via
`get_officer_actor("api:/api/v1/web/officer/applications/{application_id}/messages")`
/ `…/{application_id}/transitions` (proposal §3, §6, §11). The β-i
helper rejects non-officer Pomerium principals, missing/invalid
Discord claim, and synthetic-member resolutions before the endpoint
body runs (`services/api/app/api/v1/endpoints/web.py:75-129`).

For transitions, identity validation runs at FastAPI dependency time;
`parse_if_match_strong(request)` runs in the body (after `Depends`),
so missing identity returns `401`/`403`/`422` before the `If-Match`
`428` is reachable. This matches β-i's claim path
(`services/api/app/api/v1/endpoints/web.py:199-208`) and the proposal's
Q5 lock that the bridge "calls `parse_if_match_strong(request)` and
forwards `expected_version` into `transition_application`."

No per-action helpers are introduced; one bridge endpoint covers all
exposed transitions.

### A2 — Message append idempotency boundary — PASS

The bridge contract `OfficerApplicationMessageAppendRequest`
(`services/api/app/contracts/web.py`) carries only `body_markdown`,
`visibility`, and `client_message_id`; author fields are filled
server-side from the Pomerium-resolved actor (proposal §3 modified
files, §4). The bridge passes `client_message_id` through
unchanged; `append_application_message` enforces idempotency via
`find_application_message_by_client_message_id`
(`services/api/app/services/application_messages.py:93-100`) and the
direct endpoint sets `201 Created` for new and `200 OK` for duplicate
(`services/api/app/api/v1/endpoints/applications/messages.py:75`).
The proposal locks both status codes (Q4, §4 message-bridge response
shape).

### A3 — Single transition bridge, no per-action specialization — PASS (with F1 caveat)

Q1 and §3 lock one `POST /transitions` endpoint that mirrors
`ApplicationTransitionRequest` and forwards the parsed `If-Match`
into `transition_application` (`services/api/app/services/applications.py:1059`).
There is no per-action HTTP route, no per-action handler branch, no
`skip_authority_check` use, and no HTTP self-call.

The bridge accepts the request body directly typed as
`ApplicationTransitionRequest`. Action-specific behavior comes from
the service alone:

- `route` is rejected up-front by `transition_application`
  (`services/api/app/services/applications.py:1068-1074`).
- `claim` is owned by β-i's `/claim` route; behavior on this endpoint
  is undefined by the proposal (see F1).
- `reassign` would require `new_owner_id` and is out of scope (§8).

See **F1** for the bridge-side validator gap.

### A4 — Authorization mapping matches `require_transition_authority` — PASS

`require_transition_authority` maps every action except `reassign` to
`application.{action}` (`services/api/app/services/applications.py:348-362`).
The proposal §6 table lists each exposed action against its
`application.{action}` permission (`application.review`,
`application.request_interview`, `application.waitlist`,
`application.approve`, `application.deny`, `application.reactivate`,
`application.withdraw`) and `application.message` for the message
endpoint, matching the helper exactly. Officer-group membership
gates the bridge entry; permission grants gate each action — no
group-level bypass.

The proposal explicitly corrects the β-iii problem map's earlier
guess that `request_interview` would map to `application.waitlist`
(`research/24-init-133B-iii-problem-map.md:128-129`). The corrected
mapping in §6 matches the helper code.

### A5 — State-machine UI mirrors `VALID_TRANSITIONS` — PASS (with F3 caveat)

Q3 derives action visibility from `VALID_TRANSITIONS`
(`services/api/app/services/applications.py:65-89`) and exposes:

- `claimed → review, withdraw`
- `in_review → request_interview, waitlist, approve, deny, withdraw`
- `interview → waitlist, approve, deny, withdraw`
- `waitlisted → reactivate, withdraw`
- terminal states show no controls

Cross-check against `VALID_TRANSITIONS` for the exposed action subset:
every documented (state, action) pair exists in the table. Buttons
that would send invalid transitions don't render (Q3) and any
race-induced invalid transition surfaces a `409
invalid_application_transition` plus refetch (proposal §4 line 111,
Q5). See **F3** for the missing `submitted`/`queued` →
`withdraw` paths (which are valid in the table but absent from the
documented UI mapping).

### A6 — Stale-version handling on transition — PASS

Q5 locks: missing/malformed `If-Match` → `428 if_match_required` /
`412 invalid_if_match` (via shared `parse_if_match_strong`); stale
version → `412 stale_application_version` (via `raise_known_application_error`,
which already handles `StaleMutationError` at
`services/api/app/api/v1/endpoints/applications/_shared.py:79-88`); on
either, show a notice and refetch detail + transcript. This mirrors
β-i's claim flow (`services/web/src/api/client.ts:280-303` and
`services/web/src/features/officer/ApplicationQueueRoute.tsx:34-40,
96-115`).

### A7 — Officer-side `withdraw` actor semantics — PASS (with F5 informational)

The proposal exposes `withdraw` for officers and §6's row notes
"User actor reviewer id is recorded by `_reviewer_id`."
`_reviewer_id` returns `UUID(actor.actor_id)` for any user actor and
`None` for non-user actors when action == "withdraw"
(`services/api/app/services/applications.py:266-273`). Because the
officer bridge always builds `ActorIdentity(actor_kind="user",
actor_id=<member uuid>)`, the audit row will record the *officer's*
member UUID as the reviewer — i.e., a force-withdraw on the
applicant's behalf, gated by `application.withdraw` permission (not
applicant identity). The audit row is therefore distinguishable from
applicant self-withdraw by actor_id alone.

This is the correct semantics for an officer review surface, but the
proposal does not call it out explicitly. See **F5**.

### A8 — Message visibility preserved without coercion — PASS (with F2 caveat)

The bridge forwards `visibility` verbatim from the body into the
constructed `ApplicationMessageAppendRequest`; no coercion logic
exists in the proposal. The composer ships a segmented control
(`applicant_visible | officer_only`, Q4) and the composer cleans only
local UI state (textarea + idempotency UUID rotation) on success.
`append_application_message` (`services/api/app/services/application_messages.py:115-125`)
raises `ApplicationMessageVisibilityError` only for *applicant-authored*
messages with non-applicant-visible visibility; officer-authored
messages bypass that branch entirely. See **F2** for the dead-letter
422 code listed in proposal §4 line 110.

### A9 — Anti-scope adherence — PASS

Section 8 explicitly excludes:

- Discord-visible side effects, channels, embeds, role changes
  (deferred to BL-009).
- Applicant DM materialization (deferred to BL-020).
- `route` UI / endpoint (service rejects route).
- `reassign` UI, owner picker, owner search.
- Bulk actions, multi-select, queue batch transitions.
- Message editing/deletion/threading/attachments.
- New permissions, schema migrations, actor kinds, Authentik /
  Pomerium policy changes, feature flags, deprecated aliases,
  deferred stubs.

Diff budget (§9) is `+720 / -30` with a hard split-gate at `+900` net
or any of: new permissions, schema, route policy, `route`/`reassign`
implementation. This is consistent with β-i and β-ii budgeting.

### A10 — Transcript refetch after every mutation — PASS

Q4 (message append): "After success, clear the textarea, generate a
fresh UUIDv4 `client_message_id`, and refetch transcript so the
returned `ApplicationMessageRead` is visible inline."

Q5 (transitions): "On success, replace the route's application with
the response, then refetch detail and transcript."

§3 modified files for `ApplicationDetailRoute.tsx`: "own
refetch-after-mutation, conflict notices, and stale-version
recovery." The detail route already has a `loadDetail(id)` helper
that fetches both detail and transcript in parallel
(`services/web/src/features/officer/ApplicationDetailRoute.tsx:199-216`),
so the mutation handlers can reuse it.

## Findings

### F1 (LOW) — Bridge transition contract for action subset is locked but not scoped

**Concern:** The "Bridge endpoint shapes" section locks: "`route` and
`reassign` return `422 validation_error` from bridge validation
rather than rendering unusable controls" (proposal §3 line 101).
However §3's modified-files list adds only
`OfficerApplicationMessageAppendRequest` to
`services/api/app/contracts/web.py` and does not add a parallel
`OfficerApplicationTransitionRequest` whose `action` enum excludes
`claim | route | reassign`. Without that narrower contract or an
explicit pre-service field validator on the bridge handler, the
declared bridge-level rejection is not implementable as written:

- A POST with `action: "route"` would pass Pydantic validation (the
  full `ApplicationTransitionRequest` enum includes `route`,
  `services/api/app/contracts/applications.py:49-59`) and then fail
  inside `transition_application` with `InvalidApplicationTransitionError`
  → `409 invalid_application_transition` (not `422 validation_error`).
- A POST with `action: "claim"` would pass Pydantic validation; if
  the application happens to be in `queued` state, it would succeed
  — bypassing β-i's dedicated `/claim` route surface and any future
  claim-specific bridge logic. β-i locks claim ownership to
  `/claim` (proposal §3 line 101 explicitly: "`claim` stays on
  `/claim`"), so this is a real correctness hazard.
- A POST with `action: "reassign"` would require `new_owner_id`
  validation and `application.review` permission, neither of which
  the bridge is designed to handle.

**Evidence:**
- `services/api/app/contracts/applications.py:49-59`
  (`ApplicationTransitionAction` enum has 10 actions including
  `claim`, `route`, `reassign`).
- `services/api/app/services/applications.py:1068-1074` (route
  rejection emits `InvalidApplicationTransitionError` → 409, not
  422).
- Proposal §3 modified-files list at `services/api/app/contracts/web.py`
  adds `OfficerApplicationMessageAppendRequest` only.
- Proposal §3 line 101 locks 422 for the unsupported actions.

**Severity:** LOW. No security regression — `_build_officer_actor`
plus `require_transition_authority` still gate every action — but
the locked status code (422) and surface invariant (claim stays on
`/claim`) cannot be honored without a bridge-side validator.

**Recommendation:** Implementation must add either
(a) a new `OfficerApplicationTransitionRequest` in
`services/api/app/contracts/web.py` whose `action: Literal[
"review", "request_interview", "waitlist", "approve", "deny",
"reactivate", "withdraw"]` enum excludes the unsupported subset, OR
(b) an explicit field validator on the existing
`ApplicationTransitionRequest` parameter that raises
`HTTPException(422, "validation_error")` for `claim | route |
reassign`. Option (a) is preferred because Pydantic emits the 422
before the endpoint body runs and the validation is visible at the
contract surface. Add an API bridge test asserting each rejected
action returns 422 with code `validation_error`.

### F2 (LOW) — `ApplicationMessageVisibilityError` listed but unmapped on the bridge

**Concern:** Proposal §4 line 110 lists `422 applicant_visibility_required`
as a status the message-bridge SPA handles. The shared error mapper
at `services/api/app/api/v1/endpoints/applications/_shared.py:68-202`
does not have a branch for `ApplicationMessageVisibilityError`; it is
a `ValueError` subclass
(`services/api/app/contracts/application_messages.py:51-52`) and
would fall through to the generic
`if isinstance(error, ValueError)` branch at line 197 → `422
validation_error` (different code from `applicant_visibility_required`).
The direct messages endpoint
(`services/api/app/api/v1/endpoints/applications/messages.py:30-46`)
maps it locally as `applicant_visibility_required`.

In practice this error path is unreachable from the officer bridge
because `ApplicationMessageVisibilityError` fires only when an
applicant-authored message is non-`applicant_visible`
(`services/api/app/services/application_messages.py:115-119`), and
the bridge always sends an officer (`actor_kind="user"`,
`actor_id=<officer member uuid>`) where `actor_id !=
str(applicant_id)`. So the listed code is dead-letter for this
endpoint.

**Evidence:**
- `services/api/app/contracts/application_messages.py:51-52`
  (`ApplicationMessageVisibilityError(ValueError)`).
- `services/api/app/api/v1/endpoints/applications/_shared.py:68-202`
  (no isinstance branch for `ApplicationMessageVisibilityError`).
- `services/api/app/api/v1/endpoints/applications/messages.py:30-46`
  (direct endpoint's local mapper handles it).
- `services/api/app/services/application_messages.py:115-119`
  (raised only for applicant-authored messages).
- Proposal §4 line 110 lists `422 applicant_visibility_required` for
  the message bridge.

**Severity:** LOW (dead-letter, no security or correctness impact).

**Recommendation:** Either (a) drop `applicant_visibility_required`
from the message-bridge §4 listed responses (it cannot fire from
this bridge), or (b) add a `ApplicationMessageVisibilityError` →
`422 applicant_visibility_required` branch to
`raise_known_application_error` and document that the bridge mirrors
the direct endpoint mapping for completeness. Option (a) is more
honest to the surface; option (b) is more defensive against future
changes that might admit applicant-authored messages through this
bridge (none are planned).

### F3 (INFORMATIONAL) — State-machine helper omits `withdraw` from `submitted`/`queued`

**Concern:** `VALID_TRANSITIONS` admits `withdraw` from
`submitted`, `queued`, `claimed`, `in_review`, `interview`, and
`waitlisted`
(`services/api/app/services/applications.py:83-88`). Q3's documented
helper mapping only exposes `withdraw` from
`claimed | in_review | interview | waitlisted` — i.e., a strict
subset. Officers who navigate to a `submitted` or `queued` row's
detail view (reachable from the queue's "View" link
(`services/web/src/features/officer/ApplicationQueueRoute.tsx:198-204`)
on any state, not just `queued`) will see no transition controls
even though the service would accept `withdraw`.

**Evidence:**
- `services/api/app/services/applications.py:83-88` (VALID_TRANSITIONS
  withdraw set).
- Proposal §2 Q3 mapping omits `submitted` and `queued` rows.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx:198-204`
  (View link does not gate by state).

**Severity:** INFORMATIONAL.

**Recommendation:** Either (a) extend Q3's mapping to include
`submitted → withdraw` and `queued → withdraw` so the helper
faithfully mirrors `VALID_TRANSITIONS` for the exposed action set,
or (b) document the deliberate restriction in §8 anti-scope
("officers must claim before withdrawing on the applicant's behalf").
Both choices are defensible; the proposal should pick one explicitly
so the implementer does not silently extend or restrict the helper.

### F4 (INFORMATIONAL) — §6 owner-equals-actor footnote is broader than the service enforces

**Concern:** §6's permission table footnotes "Also requires current
owner equals officer" for `review`, `request_interview`,
`waitlist`, `approve`, `deny`. The service enforces explicit
`ApplicationNotOwnerError` only for `request_interview` and
`waitlist` (`services/api/app/services/applications.py:1086-1093`).
For `review`, `approve`, and `deny` the service relies on
state-machine validity alone (state must be `claimed` for `review`;
`in_review | interview` for `approve`/`deny`) plus the
permission. A non-owner officer with `application.review` could move
a claimed application authored by a different officer into
`in_review`. This is existing service behavior and not introduced
by this slice.

**Evidence:**
- `services/api/app/services/applications.py:1086-1093` (explicit
  owner check covers only request_interview and waitlist).
- `services/api/app/services/applications.py:71-79`
  (VALID_TRANSITIONS gates `review`, `approve`, `deny` by state, not
  ownership).
- Proposal §6 permission table footnote applies "current owner
  equals officer" too broadly.

**Severity:** INFORMATIONAL — documentation-only.

**Recommendation:** Tighten the §6 footnote to mention the owner
constraint only on `request_interview` and `waitlist`. The other
actions are gated by state-machine validity plus permission. No
service change required.

### F5 (INFORMATIONAL) — Officer force-withdraw semantics not explicitly locked

**Concern:** §6 documents that `withdraw` requires
`application.withdraw` and that "User actor reviewer id is recorded
by `_reviewer_id`," but does not explicitly state that:

1. Officer-side `withdraw` is a **force-withdraw** — the audit row
   records the *officer's* member UUID as `actor_id`, not the
   applicant's, and the action is permitted by
   `application.withdraw` grants alone (no applicant consent
   gating).
2. Applicant self-withdraw (handled elsewhere) is distinguishable
   from officer force-withdraw by actor_id at audit-read time.

This is the correct behavior for an officer review surface, but ops
and audit consumers should see it called out explicitly so a
force-withdraw row is not misread as an applicant self-withdraw.

**Evidence:**
- `services/api/app/services/applications.py:266-273`
  (`_reviewer_id` for `withdraw` returns the user actor's UUID).
- Proposal §6 row for `withdraw` mentions reviewer id but not the
  force-withdraw semantics.
- Q2 (proposal §2) lists `withdraw` for officers without
  semantic distinction from applicant self-withdraw.

**Severity:** INFORMATIONAL.

**Recommendation:** Add a one-sentence note in §6 explaining the
force-withdraw semantics and the actor_id distinction. Optionally
extend the e2e plan (§7) with a transition that compares the
audit row's `actor_id` to the officer's member UUID after a
withdraw to lock the property.

## Required-reading coverage

- [x] `proposals/15-init-133B-iii-messages-transitions.md` — full read
- [x] `proposals/13-init-133B-i-officer-queue.md` — relevant §s for
      `_build_officer_actor`, claim pattern, identity invariants
- [x] `proposals/14-init-133B-ii-detail-transcript.md` — relevant §s
      for detail route and transcript bridge mapper
- [x] `research/24-init-133B-iii-problem-map.md` — full read
- [x] `services/api/app/api/v1/endpoints/web.py` — full read (β-i + β-ii)
- [x] `services/api/app/api/v1/endpoints/applications/lifecycle.py` —
      direct transitions reference
- [x] `services/api/app/api/v1/endpoints/applications/messages.py` —
      direct messages reference, including local mapper
- [x] `services/api/app/api/v1/endpoints/applications/_shared.py` —
      `parse_if_match_strong`, `raise_known_application_error`
- [x] `services/api/app/services/applications.py` —
      `transition_application`, `VALID_TRANSITIONS`,
      `require_transition_authority`, `_reviewer_id`
- [x] `services/api/app/contracts/applications.py` —
      `ApplicationTransitionAction`, `ApplicationTransitionRequest`
- [x] `services/api/app/contracts/application_messages.py` —
      `ApplicationMessageAppendRequest`,
      `ApplicationMessageVisibilityError`,
      `ApplicationMessageForbiddenError`
- [x] `services/api/app/services/application_messages.py` —
      `append_application_message`, visibility branch
- [x] `services/web/src/features/officer/ApplicationDetailRoute.tsx`
- [x] `services/web/src/features/officer/ApplicationQueueRoute.tsx` —
      claim mutation pattern reference
- [x] `services/web/src/api/client.ts` — current schemas + claim
      function

## Summary

The β-iii audit risk is **LOW**. The proposal preserves every
β-i / β-ii audit invariant (Pomerium-bound officer actor, no
applicant_receipt, no X-Actor honoring, shared If-Match parser, shared
error mapper, direct service calls, server-side author construction,
transcript refetch on mutation, anti-scope on Discord/DM/owner-picker
side surfaces). Two LOW findings recommend pre-implementation
corrections to lock surface invariants the proposal already claims
(F1 bridge action validator, F2 dead-letter status code). Three
informational findings point at documentation drift between the
proposal and service behavior (F3 missing withdraw states, F4 owner
footnote scope, F5 force-withdraw semantics) — none of which block
the gate.

AUDIT_DONE: plans/risk/init-133B-iii-audit.md
