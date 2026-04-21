# SLICE-021 Audit Risk Report

Audit of `.pipeline/proposal.md` against SLICE-021 ticket, synthesis decisions
(D1–D13), and the shipped SLICE-012 substrate. Each finding lists the binding
constraint, where the proposal addresses it, residual risk, and the
implementation-time check that closes it.

Reference anchors (current code):
- `services/api/app/services/applications.py:42` — `VALID_TRANSITIONS`
- `services/api/app/services/applications.py:54` — `AUDIT_ACTION_TYPE`
- `services/api/app/services/applications.py:63` — `TRANSITION_PAYLOAD_ALLOWLIST`
- `services/api/app/services/applications.py:318` — `validate_required_transition_fields`
- `services/api/app/services/applications.py:332` — `validate_transition`
- `services/api/app/services/applications.py:350` — `_transition_diff`
- `services/api/app/services/applications.py:548` — `mutate_projection` / `StateChangeDraft` construction
- `services/api/app/services/applications.py:563` — owner-only guard (`review|approve|deny`)
- `services/api/app/services/applications.py:626` — `mutate_entity()` call with `payload_allowlist`
- `services/api/app/api/v1/endpoints/applications/_shared.py:66` — `StaleMutationError -> 412`
- `services/api/app/api/v1/endpoints/applications/_shared.py:76` — `ApplicationAlreadyClaimedError -> 409` (claim-only remap)

## 1. Explicit `payload_allowlist` on interview/waitlist/reactivate mutations

**Binding:** Every `mutate_entity()` call for a lifecycle action must pass a
narrow `payload_allowlist` so redacted audit payloads never widen by accident.

**Proposal coverage:** §5 extends `TRANSITION_PAYLOAD_ALLOWLIST` with the
three new actions. §10 repeats the same allowlists as an audit-layer guard.

| Action | Allowed keys (per proposal) |
|---|---|
| `request_interview` | `action`, `reviewer_id`, `thread_id`, `reason`, `originating_actor_kind`, `originating_actor_id` |
| `waitlist` | `action`, `reviewer_id`, `reason`, `originating_actor_kind`, `originating_actor_id` |
| `reactivate` | `action`, `reviewer_id`, `new_owner_id`, `reason`, `originating_actor_kind`, `originating_actor_id` |

The existing `_transition_application_locked()` already plumbs
`payload_allowlist=payload_allowlist` into `mutate_entity()` at
`applications.py:638`, so the only implementation work is adding the three
dictionary entries and making sure the normalized action payload dict is built
from them.

**Residual risk (low):**
1. The idempotent interview no-op must **not** call `mutate_entity()` at all
   (per §5), so no allowlist is consulted there — this is correct, but the
   test must assert no `activity_actions` row was written so the no-op path is
   not silently upgraded to a mutation in a later refactor.
2. `originating_actor_kind` / `originating_actor_id` are body-only audit
   fields. Proposal §7 explicitly says "The body `originating_actor_kind` and
   `originating_actor_id` fields do not grant authority and must not override
   the request actor headers." Implementation must pass actor headers through
   `ActorIdentity` and only include the body echoes inside the allowlisted
   audit payload — not into any authority evaluation.

**Closes:** unit tests that assert the stored `activity_actions.request_json`
contains exactly the keys listed above and nothing else for each new action.

## 2. `StateChangeDraft` with `application.transitioned` + diff_json coverage

**Binding (D9):** Accepted lifecycle transitions keep writing
`change_type = "application.transitioned"` with `diff_json` covering `state`,
`owner_id`, `interview_thread_id`, and reason/notes when supplied.

**Proposal coverage:** §5 extends `_transition_diff()` to include
`interview_thread_id`; §10 enumerates the full diff surface
(`state`, `owner_id`, `interview_thread_id`, `queued_at`, `claimed_at`,
`review_started_at`, `decided_at`, `withdrawn_at`, `notes`/`reason`).

The existing `_transition_diff()` at `applications.py:350` already iterates
through `owner_id`, `decision_reason`, `queued_at`, `claimed_at`,
`review_started_at`, `decided_at`, `withdrawn_at`, and emits `state` + `notes`
separately. Only `interview_thread_id` is missing, so the extension is
additive.

**Residual risk (medium):**
1. **`reason` vs `notes` coercion.** Current `_transition_diff()` accepts a
   `notes` kwarg only. The new `reason` fields on interview/waitlist/reactivate
   must be mapped somewhere. Proposal §5 says "If the internal normalized
   object uses `notes`, the waitlist reason must be copied to `notes`." This
   coercion must happen before `insert_review_row()` and before `_transition_diff()`,
   otherwise the review row's `notes` column will be null while the audit
   state-change payload carries the reason — a divergence between the two
   audit surfaces.
2. **Idempotent interview no-op writes no state change.** §10 says: "The
   idempotent interview no-op does not create a state change because no
   lifecycle change was accepted." This is correct but the implementation must
   skip both the review-row insert and the state-change emission — the
   existing code path does both unconditionally inside `mutate_projection`, so
   the no-op must short-circuit **before** `mutate_entity()` is invoked
   (the proposal already says this in §5).
3. **`change_type` stays `application.transitioned`.** Do not introduce
   `application.interviewed`, `application.waitlisted`, etc. as state-change
   types; D9 and §10 both bind this. Action-type differentiation lives on
   `activity_actions.action_type`, not on the state change.

**Closes:** API test assertions on `activity_state_changes` rows for all three
new transitions that check the diff contains `state`, `owner_id`
(for reactivate), `interview_thread_id` (for interview), and the
reason/notes key when supplied.

## 3. Ownership check: interview + waitlist require `actor == owner_id`; reactivate does not

**Binding (D7):** Interview and waitlist join the `review | approve | deny`
owner-only set. Reactivate requires `application.reactivate` authority but is
an explicit ownership *handoff* — no current-owner match.

**Proposal coverage:** §5 says "owner-only checks so `request_interview` and
`waitlist` join `review`, `approve`, and `deny`." §7 explicitly spells out
reactivate as non-owner-gated and restates the owner-match rule for the other
two.

**Residual risk (medium):**
1. The existing guard is a hardcoded set at `applications.py:563`:
   `if action in {"review", "approve", "deny"} ...`. Implementation must
   extend this to `{"review", "approve", "deny", "request_interview", "waitlist"}`
   and must not accidentally include `"reactivate"`. A test fixture where an
   authorized non-owner reactivates from `waitlisted` must pass; the same
   actor attempting interview or waitlist must return `409 application_not_owner`.
2. `_reviewer_id()` at `applications.py:138` currently raises `ValueError`
   for non-user actors on non-`route`, non-`withdraw` actions. The three new
   actions must follow the same rule (user-only reviewer). §5 states
   `_reviewer_id()` must be extended so `request_interview`, `waitlist`, and
   `reactivate` "require a user actor." Implementation must make this explicit
   because the current default path would already raise `ValueError`, but the
   implicit reliance is fragile.
3. Authority scope is `application.{action}` at `form_snapshot.target_scope`
   (§7). Proposal maps `request_interview` → `application.request_interview`,
   not `application.interview`. The action-name-to-permission mapping must be
   consistent — and the audit `action_type` ("application.interview") is
   deliberately a different string from the permission name
   ("application.request_interview"). Implementation must not collapse the two.

**Closes:** tests covering (a) non-owner with `application.request_interview`
on interview → 409 not_owner, (b) non-owner with `application.waitlist` on
waitlist → 409 not_owner, (c) non-owner with `application.reactivate` on
reactivate → 200 success with optional `new_owner_id` semantics.

## 4. Thread idempotency: match → 200 no-op (no second audit row); mismatch → 409

**Binding (D5 / AC3):** An interview request whose stored `interview_thread_id`
equals the request `thread_id` (or whose request `thread_id` is absent while
the state is already `interview`) returns 200 with the current
application/ETag and emits no second review row and no second audit entry. A
mismatch returns 409.

**Proposal coverage:** §5 explicitly binds: "do not call `mutate_entity()`,
insert a review row, or create an `application.transitioned` state change." §6
introduces `ApplicationInterviewThreadMismatchError` → 409 with code
`application_interview_thread_mismatch`. §9 enumerates the full truth table.
§11 binds test assertions on "no additional `application_reviews` row, no
version increment."

**Residual risk (high — this is the easiest AC to violate):**
1. **No-op ETag source.** §6 says "Sets `ETag` from `MutationResult.etag` after
   writes, or from the current `ApplicationRead.version` for the idempotent
   interview no-op." The endpoint must format the ETag identically in both
   paths (`f'"{version}"'` strong format) so clients see no round-trip
   perturbation on retry. A small bug here would break client caches.
2. **Decision point ordering.** The service must (a) re-fetch the application
   inside the request handler, (b) inspect state and `interview_thread_id`,
   and (c) branch to no-op **before** entering `mutate_entity()`. If the
   branch is placed inside `mutate_projection`, `mutate_entity()` will still
   advance `activity_actions`, violating "no second audit row." Proposal §5
   implies the branch is pre-mutation but does not bind the placement; the
   implementation must place the idempotency check outside `mutate_entity()`.
3. **Mismatch while not in `interview` state.** §9's table says "any other
   state | any | any | Normal `InvalidApplicationTransitionError`, except
   mismatch still returns mismatch if the stored thread differs and the
   request attempts to relink it." This means the mismatch check takes
   precedence over transition validation. The implementation order inside the
   idempotency branch must be:
   1. If stored thread set and request thread set and they differ → 409 mismatch.
   2. Else if state == `interview` and (stored thread matches or request thread absent) → 200 no-op.
   3. Else fall through to normal transition.
   A reversed ordering would let `submitted -> interview` with a mismatching
   thread get rejected as `invalid_application_transition` instead of
   `application_interview_thread_mismatch`. Test cases should exercise this
   ordering.
4. **Absent request thread while state is not `interview`.** The table shows
   `in_review | null | null → transition, leave thread null`. Discord
   shouldn't hit this path, but the API accepts it per contract
   (`thread_id: str | None = None`). Implementation must allow it;
   the absent-thread + already-interview row in the table is the no-op, not
   this one.

**Closes:** dedicated test cases in `test_application_interviews.py` for:
(a) repeat with same thread → no new review row, no version change,
(b) repeat with different thread from `interview` state → 409 mismatch,
(c) different thread attempted from `submitted` or `in_review` when stored
thread exists → still 409 mismatch (mismatch beats transition-validity),
(d) absent request thread from `interview` state with stored thread → no-op.

## 5. `VALID_TRANSITIONS` extends existing SLICE-012 constant; no parallel state machine

**Binding (D1, D2, D11):** Extend the shipped `VALID_TRANSITIONS` dict in
place; do not create a separate lifecycle service, a separate transition
table, or a parallel state enum.

**Proposal coverage:** §5 uses `VALID_TRANSITIONS.update({...})`. §8 prints
the full post-SLICE-021 table as a single machine. §11 binds: "Extend the
existing `transition_application` service path rather than creating separate
lifecycle services."

**Residual risk (low):**
1. §8's full table adds `interview -> approved` and `interview -> denied` —
   these are genuinely new edges that must be part of the `.update()` call.
   The existing approve/deny validation already requires a non-blank
   `decision_reason` via `validate_required_transition_fields()`; this
   behavior must also hold from `interview`, not just `in_review`.
   Verified: `validate_required_transition_fields()` branches on action only
   (`action in {"approve", "deny"}`), so approving from `interview` naturally
   still requires decision_reason.
2. The proposal's §5 "Acceptable" alternative — thin public functions per
   action — is fine as long as they "immediately delegate into the same
   transition path." Implementation must not let these wrappers grow private
   state-machine logic; the risk here is drift over time, not this slice.
3. The idempotent interview no-op is explicitly **not** a state-machine edge
   (no `interview -> interview` self-loop, per D2 and §8). The dict must not
   include it.

**Closes:** a test that snapshots the full `VALID_TRANSITIONS` dict after
SLICE-021 and fails on unexpected keys, plus regression coverage that
SLICE-012 edges (`submitted -> queued -> claimed -> in_review -> approved|denied|withdrawn`)
still succeed unchanged.

## 6. Decision-reason enforcement: waitlist required; interview/reactivate optional

**Binding (D2, D8):** Waitlist must reject blank/absent reason. Interview and
reactivate reasons are optional but, if present, must be stripped and
non-blank.

**Proposal coverage:** §3 contracts:
- `ApplicationInterviewRequest.reason: str | None = None`
- `ApplicationWaitlistRequest.reason: str`
- `ApplicationReactivateRequest.reason: str | None = None`

§3 also binds: "Reject blank `thread_id`, blank `reason`, and blank optional
reason strings when present."

§5 binds: "`validate_required_transition_fields()` so `waitlist` requires a
non-blank reason."

**Residual risk (medium):**
1. **Two-layer defense.** The required-field enforcement lives in two places:
   the Pydantic contract (first line) and `validate_required_transition_fields()`
   (service line). Both must be implemented — the Pydantic layer alone is
   bypassable if any internal callsite builds a normalized transition object
   without re-serializing. Existing approve/deny take this belt-and-suspenders
   approach (contract + service-layer check at `applications.py:322`), and
   waitlist should match it.
2. **Blank-string treatment.** The proposal says reasons are "stripped and
   must not be blank when present." Pydantic's default validators do not
   strip; a `field_validator` must enforce this. Interview
   `thread_id` has the same rule. Implementation must add explicit validators
   (or lean on an existing `_strip_nonblank` helper if one exists in this
   module) rather than assuming Pydantic catches whitespace-only strings.
3. **Reactivate reason semantics.** Proposal §10 says reactivate's state-change
   payload includes "`reason` when supplied." So an omitted reactivate reason
   should simply not appear in the audit payload; it should not become
   `reason: null` which widens the allowlist intent.

**Closes:** contract-level tests covering blank-string rejection for each
reason field, plus a service-level test that bypasses the contract (or uses
`model_construct`) to confirm `validate_required_transition_fields` fires
for waitlist.

## 7. Repository append-only: `application_reviews` gets new INSERT rows, not UPDATEs

**Binding:** Every accepted lifecycle transition, except the idempotent
interview no-op, inserts a new `application_reviews` row. No existing review
row is ever mutated.

**Proposal coverage:** §4 binds: "`insert_review_row()` needs no shape change
because `notes` can carry interview, waitlist, and reactivate reasons, and
the action CHECK accepts the new action strings." Migration §2 replaces
the `application_reviews_action_valid` CHECK and the
`application_reviews_reviewer_required` CHECK; no UPDATE path is introduced.

**Residual risk (low):**
1. The review row for the **first** interview transition carries
   `reviewer_id = actor`, `action = "request_interview"`, `notes = reason`.
   No second row is written for an idempotent repeat. Test assertions
   should query `COUNT(*)` on `application_reviews` after a repeat interview
   and confirm it did not grow.
2. The CHECK constraint migration (proposal §2 step 4) adds
   `request_interview`, `waitlist`, `reactivate` to the
   `reviewer_required` set. If the implementation ever tries to insert one
   of these actions with a null `reviewer_id`, the DB will reject it, which
   is the desired invariant. Any path that bypasses `_reviewer_id()`'s
   user-actor validation must not exist.
3. **`reviewer_id` for reactivate ≠ new owner.** The review row's
   `reviewer_id` is the acting actor (per §5: "The review row's `reviewer_id`
   should still mean 'actor who performed the reactivation,' not necessarily
   the new owner" — restated from research §4). `new_owner_id` goes onto the
   application row's `owner_id`, not into the review row.

**Closes:** tests asserting review row counts after idempotent interview
repeats, and tests that reactivate's review row has the actor's ID while the
application's `owner_id` reflects `new_owner_id` (or the retained prior owner).

## 8. OCC on reactivate: `StaleMutationError` → 412, not 409

**Binding (AC2):** Reactivation uses optimistic-locking protection; a stale
`If-Match` returns 412, matching the rest of the application surface.
Reactivate must **not** re-map stale to `ApplicationAlreadyClaimedError`
(which returns 409 and is specific to the claim race).

**Proposal coverage:** §6 binds endpoints to "Uses
`raise_known_application_error()`." §11 binds the test case: "stale `If-Match`
returns `412 stale_application_version`."

The existing `raise_known_application_error()` at `_shared.py:66` maps
`StaleMutationError` → `HTTPStatus.PRECONDITION_FAILED` (412) with code
`stale_application_version`. The claim-specific 409 remap at `_shared.py:76`
triggers only on `ApplicationAlreadyClaimedError`, which is raised by
`transition_application()` at the current
`applications.py:687` only for `action == "claim"`. Reactivate therefore
falls through to the 412 path naturally.

**Residual risk (medium):**
1. **Do not reintroduce claim-style remap for reactivate.** Since
   reactivate also assigns ownership (`new_owner_id` or retained), a
   well-meaning implementer might wrap stale reactivate races into an
   "already claimed" error. Proposal §5 is silent on this; the audit
   decision is: reactivate races on `waitlisted -> claimed` must propagate
   as `StaleMutationError → 412`. The 409 `application_already_claimed`
   remap stays claim-only. Test coverage must lock this in.
2. **OCC scope.** `mutate_entity()` performs `aggregate_heads.current_seq`
   check-and-set inside `SELECT ... FOR UPDATE`. Reactivate delegates to
   the same `_transition_application_locked()` path, so OCC is automatic.
   The only way to break this is to bypass `mutate_entity()` on the
   reactivate path — which the proposal does not do.
3. **412 on interview idempotent no-op.** The no-op short-circuit reads the
   current application; if the caller's `If-Match` is stale, the endpoint
   must still return 412 (not a spurious 200 echo of a stale version). The
   `parse_if_match_strong` check only validates format. Implementation
   must compare `expected_version` to current `version` before treating
   the request as idempotent — if the versions diverge, return 412 even
   for an identical thread id. Otherwise a stale client can "succeed"
   against a newer application state.

**Closes:** a dedicated test in `test_application_interviews.py` covering
reactivate with stale `If-Match` → 412 (explicit code:
`stale_application_version`), plus an interview idempotent no-op test where
the `If-Match` is stale — expected 412, not 200.

## Cross-cutting callouts

- **Migration chain (D3, D13).** Proposal §2 sets
  `down_revision = "wu_042_chapter_governance"`. This must remain the literal
  current head; any intervening slice that ships first will force a rebase.
  Not a risk today — surfaced for the executor.
- **Error class scope.** One new exception class,
  `ApplicationInterviewThreadMismatchError`, is introduced and mapped in
  `_shared.py`. Implementation must add the class in
  `services/api/app/contracts/applications.py` alongside the other
  lifecycle errors, keep its message payload to `application_id`,
  `current_thread_id`, `requested_thread_id`, and wire it into
  `raise_known_application_error()` before any production endpoint can
  return 409 for thread mismatch.
- **Read authority (D7 / §7).** Extending
  `require_application_read_authority()` with the three new permissions is
  necessary for Discord's GET-first flow. If this is missed, Discord
  handlers holding `application.request_interview` can mutate but cannot
  observe the current `interview_thread_id` via GET, breaking the
  idempotent reuse path and AC3/AC4. Test this explicitly: an actor with
  only `application.request_interview` grant must receive 200 on GET.

## Overall assessment

The proposal aligns with the synthesis' binding decisions (D1–D13) and with
the SLICE-012 substrate. No focus-point constraint is unaddressed. The
highest residual risks are concentrated in two places:

1. **Interview idempotency branch placement** (focus 4) — the no-op must
   short-circuit *before* `mutate_entity()`, must still honor `If-Match`
   freshness, and the mismatch check must beat transition-validity.
2. **Reason/notes coercion** (focus 2, 6) — the waitlist/interview/reactivate
   `reason` field must be mapped into the existing `notes`-shaped diff and
   review-row column consistently, and `validate_required_transition_fields`
   must enforce waitlist's non-blank reason as a second line of defense.

Both risks are addressable at implementation time through the test plan
already specified in §11 of the proposal, provided the test writer asserts
on `activity_actions` / `activity_state_changes` / `application_reviews`
row *counts* (not just final state) for the idempotent paths.
