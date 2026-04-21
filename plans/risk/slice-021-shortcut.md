# SLICE-021 Shortcut Risk Assessment

**Rating: LOW-MEDIUM**

Two MEDIUM observations: Discord-thread-before-API ordering for the
interview command (mitigated by a deterministic discovery marker the
proposal binds), and per-test AC-trace docstrings not explicitly
required by §11.

## Scope

Reviewed `worktrees/slice-021/.pipeline/proposal.md` against
`worktrees/slice-021/.pipeline/synthesis.md`,
`worktrees/slice-021/.pipeline/research.md`, the shipped SLICE-012
substrate (`services/api/app/services/applications.py:42-69`,
`services/api/app/services/applications.py:533-642`,
`services/api/app/repositories/applications.py`,
`services/api/app/contracts/applications.py:33-49`,
`services/api/app/api/v1/endpoints/applications/_shared.py`),
the existing migration head chain
(`migrations/versions/wu-042_chapter_governance.py`,
`migrations/versions/wu-022_applications.py:70-160`), and the Discord
review handler pattern
(`services/discord/app/handlers/application_review.py:35-99`).

## Findings

### 1. Aggregate mutations via `mutate_entity` with explicit `payload_allowlist` — clean

Proposal §5 extends the existing `_transition_application_locked()`
path that already calls `mutate_entity()` with an explicit
`payload_allowlist` (`services/api/app/services/applications.py:626-642`).
Three new keys are added to `TRANSITION_PAYLOAD_ALLOWLIST` with
narrow allowlists scoped per action (proposal §5):

- `request_interview`: `{action, reviewer_id, thread_id, reason,
  originating_actor_kind, originating_actor_id}`
- `waitlist`: `{action, reviewer_id, reason,
  originating_actor_kind, originating_actor_id}`
- `reactivate`: `{action, reviewer_id, new_owner_id, reason,
  originating_actor_kind, originating_actor_id}`

The idempotent interview no-op deliberately does **not** call
`mutate_entity()` (proposal §5 service requirement). That is correct
because no projection, audit, or version change occurs — it is a
read-and-return on a stable ETag. This is not a substrate bypass: it
is the absence of a mutation.

Proposal §4 explicitly forbids a standalone
`update_application_interview_thread()` helper unless implementation
needs it for a narrow case, and even then "do not bypass the
aggregate mutation path for accepted lifecycle changes."

**Watch (LOW):** if implementation introduces a thread-only update
helper that writes `interview_thread_id` outside `mutate_entity()` for
any *accepted* state transition, the substrate guarantee breaks.

### 2. `VALID_TRANSITIONS` extended via constant — clean

Proposal §5 extends the existing module-level `VALID_TRANSITIONS`
constant in place (`services/api/app/services/applications.py:42-52`)
with the eight new edges via `VALID_TRANSITIONS.update({...})`.
`validate_transition()` continues to be the single resolver
(`services/api/app/services/applications.py:332-347`).

The owner-match check at
`services/api/app/services/applications.py:563` will be widened from
`{"review","approve","deny"}` to also include `request_interview` and
`waitlist` (proposal §5, "owner-only checks so `request_interview`
and `waitlist` join `review`, `approve`, and `deny`"). That is a set
membership extension, not an inline state compare.

The interview repeat is intentionally **not** modeled as
`interview -> interview` (synthesis D2; proposal §8 "Do not add
`interview -> interview` or `waitlisted -> waitlisted`"). The
idempotent return is a pre-`VALID_TRANSITIONS` short-circuit on the
stored `interview_thread_id`, not a self-edge.

**Watch (LOW):** implementation must not introduce a separate
`if from_state == "interview" and action == "request_interview":`
inline check in `_transition_application_locked()`. The short-circuit
belongs in the service entry path (before the locked transition runs)
so `validate_transition()` continues to be the only matrix checker.

### 3. Thread idempotency: exact match, mismatch rejected — clean

Proposal §5 and §9 codify the exact-match rule:

- stored null + request thread → store + transition (`200`, new ETag).
- stored `T` + request `T` → return current app + current ETag, no
  new review row, no new state change, no version increment.
- stored `T` + request null → return current app + current ETag (no-op).
- stored `T` + request `U` → `409
  application_interview_thread_mismatch` via
  `ApplicationInterviewThreadMismatchError` (proposal §6).

This is a strict "first writer wins, all subsequent writers must
match the stored value or fail" rule. There is no silent overwrite
path; mismatch is fail-closed. AC3/AC4 trace is in proposal §1 and
§12.

### 4. Ownership check at service layer + DB CHECK backstop — clean within substrate

Service-layer ownership for `request_interview` and `waitlist`:
proposal §5/§7 widens the owner check at
`services/api/app/services/applications.py:563`:

```text
actor.actor_kind == "user"
UUID(actor.actor_id) == current.owner_id
```

DB CHECK backstop (proposal §2 step 4): the
`application_reviews_reviewer_required` CHECK is replaced to require
`reviewer_id IS NOT NULL` for `request_interview`, `waitlist`, and
`reactivate`. Postgres row-level CHECKs cannot enforce
"reviewer_id == applications.owner_id" across rows, so the DB
guarantees existence of the reviewer column, and the service guards
the equality. This matches the SLICE-012 backstop strategy at
`migrations/versions/wu-022_applications.py:160` and is not a
regression.

`reactivate` is intentionally not owner-gated because it is the
ownership handoff (synthesis D7, proposal §7). Authority
`application.reactivate` is the gate; `new_owner_id` does the
handoff. This is a documented behavior, not a missed check.

### 5. Waitlist reason required — fail-closed

Three layers enforce it:

- Contract: `ApplicationWaitlistRequest.reason: str` (required, no
  default) (proposal §3).
- Pydantic validator: "stripped, and non-blank" (proposal §3
  validation rules).
- Service: `validate_required_transition_fields()` extended so
  `waitlist` requires non-blank reason (proposal §5).

Triple-layered, fail-closed at the contract boundary. No silent
fallback to empty notes.

### 6. No random/timestamp-based idempotency; persisted `interview_thread_id` is the key — clean

Proposal §5 and §9 use `applications.interview_thread_id` as the
durable idempotency key. No `uuid4()`, no `now()`, no nonce.

The Discord recovery path (§9 last paragraph) discovers a
previously-created Discord thread on retry by a deterministic marker:

```text
application_id=<uuid>
```

embedded in the thread starter or thread name. That is also
deterministic identity, not a random key.

**Watch (LOW):** if implementation adds a `client_request_id` /
`Idempotency-Key` header path for the interview endpoint, that would
be a parallel idempotency channel — proposal does not authorize one.

### 7. Migration chain linear onto `wu_042_chapter_governance` — clean

Verified via `grep -E "^(revision|down_revision)" migrations/versions/`:

- `wu-042_chapter_governance.py`: `revision = "wu_042_chapter_governance"`,
  `down_revision = "wu_022_applications"`.
- No migration currently chains *off* `wu_042_chapter_governance`,
  so it is the live head.

Proposal §2 sets:

```text
revision = "wu_035_application_interview"
down_revision = "wu_042_chapter_governance"
```

Linear, no branching head, no rewrite of prior shipped migrations
(synthesis D13). The numeric `wu-035` prefix is a label only — the
chain is by `down_revision` and `revision` strings, which are
correct. (The repo already has examples of out-of-order numeric
labels chained linearly: `wu-021_forms.py` chains off
`wu_030b_trust_profile_extensions`, etc.)

### 8. Discord flow ordering — MEDIUM observation, mitigated by deterministic marker

The waitlist and reactivate flows match the binding cleanly: defer
→ resolve member → GET → POST with `If-Match` → exactly one
applicant-facing message after API success (proposal §10/§11). On
409/412/422/transport failures, no applicant-facing message is sent
(proposal §11 Discord test cases).

The interview flow is the structural exception: the proposal binds
the order as defer → resolve → GET → "create or reuse" thread →
POST `/interview`. That means a Discord-visible artifact (a new
thread) is created **before** the API call succeeds — the API needs
the `thread_id` to store atomically.

This is a known tradeoff (research §5; proposal §9 last paragraph):

- Pre-API thread creation is unavoidable if `interview_thread_id`
  must be stored atomically with the state transition.
- The recovery path is GET-first reuse of `interview_thread_id`, and
  on retry without a stored ID, discovery by the deterministic
  marker `application_id=<uuid>` in the thread starter/name before
  creating a second thread.

**Risk (MEDIUM):** if implementation skips the deterministic marker
or only checks stored `interview_thread_id` without the discovery
fallback, a retry after partial failure (Discord create succeeded,
API POST failed) creates a duplicate Discord thread. AC4 explicitly
forbids "thread-local state divergence." Mitigation: the `§11`
Discord test "If Discord creation succeeds but API fails, retry
discovers the deterministic application marker/name before creating
another thread" must be implemented as a real assertion against the
discovery path, not a placeholder.

For the waitlist/reactivate handlers, the "exactly one
applicant-facing message" requirement is asserted in §11 and matches
the existing review handler pattern at
`services/discord/app/handlers/application_review.py:80-99`. LOW.

### 9. Tests without AC trace — MEDIUM observation

Proposal §11 enumerates required test cases and §12 maps each AC to
its file set, but it does not require each test to carry a per-test
docstring naming the AC it pins. Today the existing
`services/api/tests/test_applications.py` style does not carry AC
docstrings either, so absence is consistent with the substrate, but
the SLICE-021 focus item explicitly calls per-test docstrings out as
a shortcut risk.

**Risk (MEDIUM):** implementation will need to add per-test
docstrings of the form:

```python
def test_request_interview_from_in_review_succeeds() -> None:
    """AC1: request_interview is valid only from in_review and returns interview."""
```

on every test in `test_application_interviews.py`,
`test_application_interview.py`, and
`test_application_waitlist.py`. The proposal does not bind this
explicitly. Recommend the implementation work plan add a checklist
gate before merging tests: each new test name maps to one or more of
AC1-AC4.

### 10. Magic action_type / change_type constants — clean within substrate

`AUDIT_ACTION_TYPE` is the existing module-level constant
(`services/api/app/services/applications.py:54-61`) and is extended
via `AUDIT_ACTION_TYPE.update({...})` (proposal §5). New entries:

- `"request_interview" -> "application.interview"`
- `"waitlist" -> "application.waitlist"`
- `"reactivate" -> "application.reactivate"`

The state-change `change_type` strings (`"application.queued"`,
`"application.transitioned"`) are inline literals in
`_transition_application_locked()` today
(`services/api/app/services/applications.py:609-612`). The proposal
keeps them inline (proposal §10: "Continue using
`activity_state_changes.change_type = 'application.transitioned'`").
Extracting them into a named constant would be an improvement but is
consistent with the substrate; not a regression.

The error code `"application_interview_thread_mismatch"` is an inline
string in `_shared.py` (proposal §6), matching the existing
`"application_already_claimed"` and `"invalid_application_transition"`
inline-string pattern at the same file. Consistent.

**Watch (LOW):** action names like `"request_interview"`,
`"waitlist"`, `"reactivate"` appear in: `VALID_TRANSITIONS`,
`AUDIT_ACTION_TYPE`, `TRANSITION_PAYLOAD_ALLOWLIST`, the owner-check
set, the `_reviewer_id()` user-actor set, `validate_required_transition_fields()`,
`require_application_read_authority()`, the migration CHECK
constraints, the `ApplicationTransitionAction` enum, and the Discord
contracts. Implementation should drive these from the
`ApplicationTransitionAction.value` rather than re-typing string
literals in each location to avoid typo drift across surfaces.

## Summary Table

| Focus area                                              | Finding | Severity |
|---------------------------------------------------------|---------|----------|
| Aggregate mutations via `mutate_entity` + explicit `payload_allowlist` | Extends existing path; new allowlists narrow per action | None |
| `VALID_TRANSITIONS` extended via constant; no inline state compares | `update({...})` on existing constant; idempotent no-op short-circuits before matrix | None |
| Thread idempotency: exact match, mismatch rejected     | Triple-rule table in §9; fail-closed `409` on mismatch | None |
| Service-layer owner check + DB CHECK backstop           | Service equality + DB `reviewer_id NOT NULL`; matches SLICE-012 backstop strategy | None |
| Waitlist reason required — fail-closed                  | Required at contract + validator + service | None |
| Persisted `interview_thread_id` as idempotency key (no random/timestamp) | Stored column is the key; deterministic marker for Discord retry | None |
| Migration chain linear onto `wu_042_chapter_governance` | Confirmed live head; `down_revision` correct | None |
| Discord flow: defer → API → visible mutation; one applicant message | Waitlist/reactivate clean; interview creates thread pre-API per atomic-store requirement | Medium (mitigated) |
| Per-test AC trace docstrings                            | §11 lists tests by behavior, not AC docstring per test | Medium |
| `action_type`/`change_type` constants                   | `AUDIT_ACTION_TYPE` extended; `change_type` strings inline matches substrate | None |
| Originating-actor body fields treated as audit-only, not authority | §3, §7 explicit | None |
| Standalone `update_application_interview_thread()` helper | Disallowed for accepted transitions (§4) | None |

## What LOW-MEDIUM Requires

LOW-MEDIUM holds as long as implementation enforces the proposal's
explicit boundaries:

1. The idempotent interview no-op short-circuit lives in the service
   entry function (before `_transition_application_locked()`), not as
   an inline branch inside the locked projection. It returns the
   current `ApplicationRead` and the existing version-derived ETag
   without calling `mutate_entity()`, inserting a review row, or
   emitting an `application.transitioned` state change.

2. `VALID_TRANSITIONS.update({...})` and
   `TRANSITION_PAYLOAD_ALLOWLIST.update({...})` are the only places
   the new edges and allowlists are added. No parallel transition
   table, no per-endpoint payload allowlist redefinition.

3. The owner-match check set is widened in one place (current line
   `services/api/app/services/applications.py:563`) to include
   `request_interview` and `waitlist`. `reactivate` and `claim` are
   *not* added.

4. The interview Discord handler embeds the deterministic marker
   `application_id=<uuid>` in the thread starter or thread metadata
   visible to the discovery path, and the retry path actually
   discovers and reuses an existing thread before creating a new one.
   The §11 Discord test
   "If Discord creation succeeds but API fails, retry discovers the
   deterministic application marker/name before creating another
   thread" must assert against the discovery API surface, not just
   the happy path.

5. Each test in `test_application_interviews.py`,
   `test_application_interview.py`, and
   `test_application_waitlist.py` carries a docstring naming the AC
   (or ACs) it pins — `AC1`, `AC2`, `AC3`, `AC4`. Tests without an AC
   reference are flagged in review.

6. `interview_thread_id` flows through the same `update_application()`
   write inside `mutate_projection()` for the *first* `request_interview`
   acceptance. No standalone helper writes the column outside the
   aggregate mutation path.

7. The migration `wu-035_application_interview.py` chains
   `down_revision = "wu_042_chapter_governance"`. Adds the column,
   replaces three CHECK constraints (`applications_state_valid`,
   `application_reviews_action_valid`,
   `application_reviews_reviewer_required`) preserving all SLICE-012
   states/actions. Downgrade raises explicit SQL exceptions when
   `interview` / `waitlisted` / new review actions exist.

8. `require_application_read_authority()` is widened to accept
   `application.request_interview`, `application.waitlist`, and
   `application.reactivate` so officers with only the new permissions
   can GET for the ETag/reuse workflow (proposal §7). Without this,
   the Discord GET-first pattern fails with 403 for those officers.

9. The `originating_actor_kind` / `originating_actor_id` body fields
   on the three new request contracts must not influence authority
   evaluation; only `ActorIdentity` headers do (proposal §3, §7).

10. Action names (`request_interview`, `waitlist`, `reactivate`) are
    sourced from `ApplicationTransitionAction.value` wherever the
    service references them by string, to prevent typo drift across
    `VALID_TRANSITIONS`, `AUDIT_ACTION_TYPE`,
    `TRANSITION_PAYLOAD_ALLOWLIST`, the owner-check set,
    `_reviewer_id()`, and `validate_required_transition_fields()`.

If items 1, 2, 4, or 6 slip in implementation, risk rises to HIGH
(substrate bypass for an accepted state mutation, or duplicate
Discord state on retry — both AC4 violations). If only items 5, 8,
9, or 10 slip, risk stays MEDIUM (test traceability or surface drift,
no substrate breach).
