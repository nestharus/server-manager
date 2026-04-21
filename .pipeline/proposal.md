# SLICE-021 Proposal: Application Interview and Waitlist Handling

## 1. Overview - AC1-4 and D-Matrix

SLICE-021 extends the shipped SLICE-012 application aggregate in place. It adds an interview state, a waitlisted state, durable interview-thread linkage, and dedicated API/Discord surfaces for requesting interviews, waitlisting applications, and reactivating waitlisted applications. The API remains the source of truth; Discord commands only create or send visible Discord artifacts after the API state contract allows it.

Acceptance criteria mapping:

| AC | Required behavior | Implementation binding |
|---|---|---|
| AC1 | Requesting an interview is valid only from `in_review` and returns `interview`. | Add `request_interview` to `ApplicationTransitionAction`; add `("in_review", "request_interview"): "interview"` to the existing `VALID_TRANSITIONS`; endpoint `POST /api/v1/applications/{id}/interview` delegates to the same transition path. |
| AC2 | Waitlist is valid only from `in_review` or `interview`; reactivation returns `claimed` with optimistic locking. | Add `waitlist` and `reactivate` actions; add `in_review|interview -> waitlisted` and `waitlisted -> claimed`; all three dedicated endpoints require `If-Match` and use `mutate_entity()` aggregate OCC. |
| AC3 | Repeating an interview request reuses the recorded thread instead of creating a duplicate. | Persist `applications.interview_thread_id`; if a repeat request supplies the same stored thread id while already `interview`, return `200` with the current application and current ETag without a second transition. |
| AC4 | API conflicts or validation failures do not duplicate Discord status messages or create thread-local divergence. | Discord handlers GET first, reuse stored thread when present, POST with `If-Match`, and only send applicant/operator-visible success messages after API success. Conflict and validation paths return ephemeral/operator failure only. |

D-matrix:

| Decision | Proposal binding |
|---|---|
| D1 | Extend the existing `ApplicationState` enum with `interview` and `waitlisted`; no separate review/interview enum. |
| D2 | Extend the existing `VALID_TRANSITIONS` constant; no parallel lifecycle table or local Discord state machine. |
| D3 | Add migration `wu-035_application_interview.py` for `interview_thread_id` and state CHECK updates. |
| D4 | Add dedicated optimistic-locking endpoints for interview, waitlist, and reactivate. |
| D5 | Implement interview-thread idempotency against `applications.interview_thread_id`. |
| D6 | Keep waitlist non-idempotent; repeat waitlist from `waitlisted` is an invalid transition. |
| D7 | Enforce owner checks for interview/waitlist and `application.reactivate` authority for reactivate. |
| D8 | Add request contracts and extend action vocabulary with `request_interview`, `waitlist`, `reactivate`. |
| D9 | Add audit action names `application.interview`, `application.waitlist`, `application.reactivate`; keep `application.transitioned` state changes. |
| D10 | Add Discord interview/waitlist/reactivate work units that use API state and ETags. |
| D11 | Extend the existing `transition_application` service path; endpoint-specific functions may be thin wrappers only. |
| D12 | Extend `application_reviews` action constraints and application repository read/write columns. |
| D13 | Chain the migration from `wu_042_chapter_governance`; do not rewrite prior migrations. |

Non-scope: no new scope kinds, no interview table, no waitlist table, no notification-rule expansion, no Discord-only lifecycle state, no backwards-compatibility aliases.

## 2. Migration `wu-035_application_interview.py`

Create `migrations/versions/wu-035_application_interview.py`:

```python
revision = "wu_035_application_interview"
down_revision = "wu_042_chapter_governance"
```

Upgrade steps:

1. Add nullable interview thread linkage:

```sql
ALTER TABLE applications
    ADD COLUMN interview_thread_id TEXT NULL;
```

2. Replace `applications_state_valid` to include the new states while preserving existing states:

```sql
ALTER TABLE applications
    DROP CONSTRAINT applications_state_valid,
    ADD CONSTRAINT applications_state_valid
        CHECK (
            state IN (
                'submitted',
                'queued',
                'claimed',
                'in_review',
                'interview',
                'waitlisted',
                'approved',
                'denied',
                'withdrawn'
            )
        );
```

3. Replace `application_reviews_action_valid` to include new review actions:

```sql
ALTER TABLE application_reviews
    DROP CONSTRAINT application_reviews_action_valid,
    ADD CONSTRAINT application_reviews_action_valid
        CHECK (
            action IN (
                'route',
                'claim',
                'review',
                'request_interview',
                'waitlist',
                'reactivate',
                'approve',
                'deny',
                'withdraw'
            )
        );
```

4. Replace `application_reviews_reviewer_required` so user-reviewer actions require `reviewer_id`:

```sql
ALTER TABLE application_reviews
    DROP CONSTRAINT application_reviews_reviewer_required,
    ADD CONSTRAINT application_reviews_reviewer_required
        CHECK (
            (
                action IN (
                    'claim',
                    'review',
                    'request_interview',
                    'waitlist',
                    'reactivate',
                    'approve',
                    'deny'
                )
                AND reviewer_id IS NOT NULL
            )
            OR action IN ('route','withdraw')
        );
```

Downgrade drops the new CHECK constraints, restores the SLICE-012 constraints, then drops `applications.interview_thread_id`. The downgrade may only be valid before rows use `interview`, `waitlisted`, or the new review actions; follow the existing migration style and raise an explicit SQL exception if unsafe data exists.

## 3. Contracts

Extend `services/api/app/contracts/applications.py`.

State/action enums:

```python
class ApplicationState(str, Enum):
    submitted = "submitted"
    queued = "queued"
    claimed = "claimed"
    in_review = "in_review"
    interview = "interview"
    waitlisted = "waitlisted"
    approved = "approved"
    denied = "denied"
    withdrawn = "withdrawn"


class ApplicationTransitionAction(str, Enum):
    route = "route"
    claim = "claim"
    review = "review"
    request_interview = "request_interview"
    waitlist = "waitlist"
    reactivate = "reactivate"
    approve = "approve"
    deny = "deny"
    withdraw = "withdraw"
```

New endpoint request contracts:

```python
class ApplicationInterviewRequest(_ApplicationModel):
    thread_id: str | None = None
    reason: str | None = None
    originating_actor_kind: Literal["user", "service", "system"]
    originating_actor_id: str = Field(min_length=1)


class ApplicationWaitlistRequest(_ApplicationModel):
    reason: str
    originating_actor_kind: Literal["user", "service", "system"]
    originating_actor_id: str = Field(min_length=1)


class ApplicationReactivateRequest(_ApplicationModel):
    new_owner_id: UUID | None = None
    reason: str | None = None
    originating_actor_kind: Literal["user", "service", "system"]
    originating_actor_id: str = Field(min_length=1)
```

Validation rules:

- `thread_id` is optional, but if present it is stripped and must not be blank.
- Optional `reason` fields are stripped and must not be blank when present.
- `ApplicationWaitlistRequest.reason` is required, stripped, and non-blank.
- `originating_actor_id` is stripped and non-blank.
- Endpoint authority still comes from `ActorIdentity` headers, not from body `originating_*` fields. The body fields are preserved only in narrow audit request payloads.

Extend `ApplicationRead`:

```python
interview_thread_id: str | None = None
```

`ApplicationReviewRead.action` continues to use `ApplicationTransitionAction`, now with the three new actions.

## 4. Repositories

Update `services/api/app/repositories/applications.py`.

Required column propagation:

- Add `a.interview_thread_id` to `_APPLICATION_SELECT`.
- Add `interview_thread_id` to `insert_application()` column/value lists, initialized from the row with `None` during normal submission.
- Add `interview_thread_id = %s` to `update_application()`.
- Ensure `_row_to_read()` in `services/api/app/services/applications.py` maps the column to `ApplicationRead.interview_thread_id`.

No standalone `update_application_interview_thread()` helper is required if the first interview transition writes `interview_thread_id` through `update_application()` with the rest of the projection update. Add a helper only if implementation needs a narrowly scoped thread-only update; do not bypass the aggregate mutation path for accepted lifecycle changes.

`insert_review_row()` needs no shape change because `notes` can carry interview, waitlist, and reactivate reasons, and the action CHECK accepts the new action strings.

## 5. Services

Extend `services/api/app/services/applications.py`. The implementation must reuse the existing transition machinery instead of creating a parallel lifecycle service.

Action constants:

```python
VALID_TRANSITIONS.update({
    ("in_review", "request_interview"): "interview",
    ("in_review", "waitlist"): "waitlisted",
    ("interview", "waitlist"): "waitlisted",
    ("interview", "approve"): "approved",
    ("interview", "deny"): "denied",
    ("waitlisted", "reactivate"): "claimed",
    ("interview", "withdraw"): "withdrawn",
    ("waitlisted", "withdraw"): "withdrawn",
})

AUDIT_ACTION_TYPE.update({
    "request_interview": "application.interview",
    "waitlist": "application.waitlist",
    "reactivate": "application.reactivate",
})
```

Payload allowlists:

```python
TRANSITION_PAYLOAD_ALLOWLIST.update({
    "request_interview": {
        "action",
        "reviewer_id",
        "thread_id",
        "reason",
        "originating_actor_kind",
        "originating_actor_id",
    },
    "waitlist": {
        "action",
        "reviewer_id",
        "reason",
        "originating_actor_kind",
        "originating_actor_id",
    },
    "reactivate": {
        "action",
        "reviewer_id",
        "new_owner_id",
        "reason",
        "originating_actor_kind",
        "originating_actor_id",
    },
})
```

Service entry shape:

- Preferred: extend `transition_application()` to normalize endpoint-specific request contracts into a single internal transition object and route all actions through `_transition_application_locked()`.
- Acceptable: add thin public functions `request_interview()`, `waitlist_application()`, and `reactivate_application()` only if they immediately delegate into the same transition path. They must not maintain separate validation, state-transition, audit, or repository logic.

Required behavior:

- `request_interview(db, application_id, expected_version, request, actor)`:
  - Requires action authority at `form_snapshot["target_scope"]`.
  - Requires current owner match: `UUID(actor.actor_id) == current["owner_id"]`.
  - Valid formal transition is only `in_review -> interview`.
  - If `request.thread_id` is present and current `interview_thread_id` is null, store it on the transition.
  - If current state is already `interview` and stored `interview_thread_id` equals `request.thread_id`, return current application with current ETag and do not call `mutate_entity()`, insert a review row, or create an `application.transitioned` state change.
  - If stored `interview_thread_id` is set and differs from `request.thread_id`, raise `ApplicationInterviewThreadMismatchError` mapped to `409` with code `application_interview_thread_mismatch`.
  - If `request.thread_id` is omitted and a stored thread id exists, return the current stored linkage for the idempotent repeat only when the application is already `interview`.

- `waitlist_application(db, application_id, expected_version, request, actor)`:
  - Requires `application.waitlist` at target scope.
  - Requires current owner match.
  - Requires non-blank `reason`.
  - Valid transitions are `in_review -> waitlisted` and `interview -> waitlisted`.
  - Repeat from `waitlisted` fails through `InvalidApplicationTransitionError` as `409 invalid_application_transition`.
  - Store the reason in `application_reviews.notes`, state-change payload, and diff.

- `reactivate_application(db, application_id, expected_version, request, actor)`:
  - Requires `application.reactivate` at target scope. Do not reuse `application.claim`.
  - Does not require actor to be the old owner.
  - Valid transition is `waitlisted -> claimed`.
  - If `new_owner_id` is provided, set `owner_id` to that member id.
  - If `new_owner_id` is omitted, retain the existing `owner_id`.
  - If the existing `owner_id` is null and no `new_owner_id` is provided, reject with a service-level validation error because `claimed` must have an owner.
  - Store `reason` in `application_reviews.notes`, state-change payload, and diff when supplied.

Also extend:

- `_reviewer_id()` so `request_interview`, `waitlist`, and `reactivate` require a user actor.
- owner-only checks so `request_interview` and `waitlist` join `review`, `approve`, and `deny`.
- `validate_required_transition_fields()` so `waitlist` requires a non-blank reason. If the internal normalized object uses `notes`, the waitlist reason must be copied to `notes`.
- `_transition_diff()` so `interview_thread_id` appears when changed, and reason/notes appear for the new actions.
- `require_application_read_authority()` so `application.request_interview`, `application.waitlist`, and `application.reactivate` holders can GET the application for the ETag/reuse workflow.

## 6. Endpoints

Add a new endpoint module `services/api/app/api/v1/endpoints/applications/interviews.py` and include it from `services/api/app/api/v1/endpoints/applications/__init__.py`. Keeping the dedicated lifecycle operations in a separate module avoids overloading the existing generic `/transitions` endpoint while preserving the same service path.

Routes:

```text
POST /api/v1/applications/{application_id}/interview
POST /api/v1/applications/{application_id}/waitlist
POST /api/v1/applications/{application_id}/reactivate
```

Each route:

- Accepts its dedicated request contract.
- Calls `parse_if_match_strong(request)`.
- Uses `get_current_actor`.
- Calls the matching service function or the normalized `transition_application()` path.
- Returns `ApplicationRead`.
- Sets `ETag` from `MutationResult.etag` after writes, or from the current `ApplicationRead.version` for the idempotent interview no-op.
- Uses `raise_known_application_error()`.

Extend `services/api/app/api/v1/endpoints/applications/_shared.py`:

- Import and map `ApplicationInterviewThreadMismatchError` to:

```json
{
  "code": "application_interview_thread_mismatch",
  "message": "...",
  "current_thread_id": "...",
  "requested_thread_id": "..."
}
```

with HTTP `409 Conflict`.

The existing `POST /api/v1/applications/{id}/transitions` remains for SLICE-012-style generic actions and can accept the extended action enum. The new Discord handlers must use the dedicated endpoints.

## 7. Authority

Authority is evaluated at `application.form_snapshot["target_scope"]`; do not introduce a new scope kind.

Interview and waitlist:

- Require `application.request_interview`. The permission name follows the existing `application.{action}` rule, so the action `request_interview` maps to `application.request_interview`.
- Require `application.waitlist` for waitlist.
- Require the actor to be the current owner:

```text
actor.actor_kind == "user"
UUID(actor.actor_id) == current.owner_id
```

Reactivate:

- Require `application.reactivate` at the same target scope.
- Do not require current-owner match because reactivation is an ownership handoff.
- If `new_owner_id` is supplied, the service must confirm the member exists before storing it, matching the repository foreign-key expectation and producing a cleaner validation error.

Read authority:

- Add `application.request_interview`, `application.waitlist`, and `application.reactivate` to the reviewer permission set accepted by `require_application_read_authority()`.

The body `originating_actor_kind` and `originating_actor_id` fields do not grant authority and must not override the request actor headers.

## 8. State Machine (D2)

Extend only the existing `VALID_TRANSITIONS` constant.

Full post-SLICE-021 transition table:

| From | Action | To |
|---|---|---|
| `submitted` | `route` | `queued` |
| `queued` | `claim` | `claimed` |
| `claimed` | `review` | `in_review` |
| `in_review` | `request_interview` | `interview` |
| `in_review` | `waitlist` | `waitlisted` |
| `interview` | `waitlist` | `waitlisted` |
| `interview` | `approve` | `approved` |
| `interview` | `deny` | `denied` |
| `in_review` | `approve` | `approved` |
| `in_review` | `deny` | `denied` |
| `waitlisted` | `reactivate` | `claimed` |
| `submitted` | `withdraw` | `withdrawn` |
| `queued` | `withdraw` | `withdrawn` |
| `claimed` | `withdraw` | `withdrawn` |
| `in_review` | `withdraw` | `withdrawn` |
| `interview` | `withdraw` | `withdrawn` |
| `waitlisted` | `withdraw` | `withdrawn` |

Do not add `interview -> interview` or `waitlisted -> waitlisted`. Interview repeat is an idempotent read/return case around `interview_thread_id`, not a state-machine edge.

## 9. Idempotency (D5)

The duplicate-thread guard is on `applications.interview_thread_id`.

Rules:

| Current state | Stored thread | Request thread | Result |
|---|---|---|---|
| `in_review` | null | non-null | Transition to `interview`, store thread, return `200` with new ETag. |
| `in_review` | null | null | Transition to `interview`, leave thread null, return `200`; Discord normally should not use this path. |
| `interview` | `T` | `T` | Return `200` current application and current ETag; no new review row/state change. |
| `interview` | `T` | null | Return `200` current application and current ETag; no new review row/state change. |
| `interview` | `T` | `U` | Return `409 application_interview_thread_mismatch`. |
| any other state | any | any | Normal `InvalidApplicationTransitionError`, except mismatch still returns mismatch if the stored thread differs and the request attempts to relink it. |

The Discord handler must GET before creating a new thread. If the GET payload includes `interview_thread_id`, it reuses that thread and does not create a duplicate Discord thread.

If a Discord thread was created but the API POST failed before storing the id, the retry path must search by deterministic application thread marker/name before creating a second thread. The proposal binds a deterministic marker:

```text
application_id=<uuid>
```

The handler should include that marker in the thread starter message or thread name metadata available to tests, then discover existing matching threads on retry.

## 10. Audit

Add action type constants through `AUDIT_ACTION_TYPE`:

| Action | `activity_actions.action_type` |
|---|---|
| `request_interview` | `application.interview` |
| `waitlist` | `application.waitlist` |
| `reactivate` | `application.reactivate` |

State changes:

- Continue using `activity_state_changes.change_type = "application.transitioned"` for accepted lifecycle transitions.
- Keep `application.queued` only for the existing route behavior.
- The idempotent interview no-op does not create a state change because no lifecycle change was accepted.

Payload allowlists must remain narrow:

- `request_interview`: `action`, `reviewer_id`, `thread_id`, `reason`, `originating_actor_kind`, `originating_actor_id`.
- `waitlist`: `action`, `reviewer_id`, `reason`, `originating_actor_kind`, `originating_actor_id`.
- `reactivate`: `action`, `reviewer_id`, `new_owner_id`, `reason`, `originating_actor_kind`, `originating_actor_id`.

State-change payloads for accepted transitions include:

- `application_id`
- `application_review_id`
- `action`
- `from_state`
- `to_state`
- `reviewer_id`
- `thread_id` for interview when supplied/stored
- `new_owner_id` for reactivate when supplied
- `reason` for interview/waitlist/reactivate when supplied

`diff_json` must include changed lifecycle fields:

- `state`
- `owner_id`
- `interview_thread_id`
- `queued_at`
- `claimed_at`
- `review_started_at`
- `decided_at`
- `withdrawn_at`
- `notes` or `reason` when supplied

Keep application transition audit scope behavior consistent with the existing service. Do not scope only the new actions differently from existing application actions unless all application transition actions are intentionally changed together in a later slice.

## 11. Tests

The implementation phase must keep test and code authorship separated. The test writer sees the contracts and this proposal, not the implementation.

API tests: add `services/api/tests/test_application_interviews.py`.

Required cases:

- `request_interview` succeeds only from `in_review`:
  - submit application;
  - claim;
  - review with notes;
  - POST `/interview` with `If-Match`, `thread_id`, and originating actor fields;
  - assert `state == "interview"`, `interview_thread_id` is stored, version increments, review row action is `request_interview`;
  - assert queued/claimed/submitted sources return `409 invalid_application_transition`.
- Interview owner enforcement:
  - non-owner with `application.request_interview` gets `409 application_not_owner`.
- Thread idempotency:
  - repeat POST `/interview` with same thread id returns `200`, same state/thread, no additional `application_reviews` row, no version increment;
  - repeat with different thread id returns `409 application_interview_thread_mismatch`.
- Waitlist from `in_review` and `interview`:
  - assert both source states transition to `waitlisted`;
  - assert blank/missing reason is rejected;
  - assert waitlist from `waitlisted` returns `409 invalid_application_transition`;
  - assert non-owner gets `409 application_not_owner`.
- Reactivate from `waitlisted -> claimed` with OCC:
  - stale `If-Match` returns `412 stale_application_version`;
  - current `If-Match` returns `claimed`;
  - omitted `new_owner_id` retains old owner;
  - supplied `new_owner_id` changes owner;
  - actor needs `application.reactivate`, not owner match.
- Existing decision transitions still work from `interview`:
  - approve and deny from `interview` require owner and decision reason.
- Withdrawal from `interview` and `waitlisted` is valid per D2.

Discord tests: add `services/discord/tests/test_application_interview.py`.

Required cases:

- Handler defers, resolves member, GETs the application, creates a thread when `interview_thread_id` is absent, then POSTs `/api/v1/applications/{id}/interview` with `If-Match` and body `thread_id`.
- Existing `interview_thread_id` from GET is reused and no thread creation call occurs.
- Repeat after API success reuses the stored thread.
- API `409 application_interview_thread_mismatch`, `412 stale_application_version`, or validation error returns failure and sends no success/outcome message.
- If Discord creation succeeds but API fails, retry discovers the deterministic application marker/name before creating another thread.

Discord tests: add `services/discord/tests/test_application_waitlist.py`.

Required cases:

- Waitlist handler defers, resolves member, GETs application ETag, POSTs `/waitlist` with reason and originating actor fields, then sends exactly one applicant-facing status message after API success.
- `409`, `412`, `422`, and API transport failures send no applicant-facing status message.
- Reactivate handler GETs, POSTs `/reactivate` with `If-Match`, and posts/reuses the existing review thread only after API success.
- Reactivate conflict/failure sends no visible success or applicant status message.

Regression tests:

- Existing `services/api/tests/test_applications.py` claim/review/approve/deny tests continue to pass.
- Existing `services/discord/tests/test_application_review.py` continues to pass.
- Update `services/discord/tests/test_main.py` to assert new command handlers are registered.

## 12. AC to Implementation Trace

| AC | Files | Concrete checks |
|---|---|---|
| AC1 | `contracts/applications.py`, `services/applications.py`, `api/v1/endpoints/applications/interviews.py`, `test_application_interviews.py` | `ApplicationState.interview`; `ApplicationTransitionAction.request_interview`; `VALID_TRANSITIONS[("in_review","request_interview")]`; POST `/interview` returns `interview`; other source states fail. |
| AC2 | same API files plus migration | `ApplicationState.waitlisted`; `VALID_TRANSITIONS` for `waitlist` and `reactivate`; `If-Match` parsed on all dedicated endpoints; stale version returns `412`; reactivate returns `claimed`. |
| AC3 | `applications.interview_thread_id`, repository read/write, service idempotency branch, Discord interview handler tests | Stored thread is exposed on `ApplicationRead`; same-thread repeat returns current app without version/review-row increment; Discord GET-first path reuses existing thread. |
| AC4 | Discord interview/waitlist/reactivate handlers and tests | Visible Discord success/applicant messages occur only after API success; conflict/validation/transport failures do not create duplicate status messages; retry discovers or reuses existing thread state. |

Implementation order:

1. Migration and repository column propagation.
2. Contracts and endpoint skeletons.
3. Service transition extensions and error mapping.
4. API tests to green.
5. Discord contracts, handlers, command registration, and Discord tests to green.

This plan is binding for SLICE-021 implementation. Any change that adds lifecycle scope, new storage systems, new scope kinds, compatibility aliases, or Discord-local source-of-truth state requires a revised proposal and risk gate before implementation.
