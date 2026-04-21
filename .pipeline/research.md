# SLICE-021 Research: Application Interview and Waitlist Handling

## 1. Prototyping Assessment

**NO - production design can proceed without a disposable prototype.**

The unknowns in SLICE-021 are lifecycle semantics and integration points, not external API mechanics:

- SLICE-012 already shipped the application aggregate, optimistic locking, state transition table, reviewer ownership checks, form snapshot pinning, and Discord review command pattern in commit `dc62122`.
- The current application mutation path already serializes each aggregate through `mutate_entity()`, strong ETags, `aggregate_heads.current_seq`, and `SELECT ... FOR UPDATE` on the application projection.
- Discord thread creation and reuse can be represented as normal adapter behavior around a nullable stored `interview_thread_id`. No Discord-visible mutation should be executed during this research phase.
- SLICE-015 already provides configurable notification rules/envelopes and a Discord delivery adapter, but its current recipient resolver only supports explicit Discord recipients. It does not yet support "recipient is the application applicant" as a dynamic recipient selector.

The proposal phase must pin two choices that are semantic rather than exploratory:

- Whether `/reactivate` preserves the previous owner by default or defaults to the acting reviewer.
- Whether applicant-facing waitlist notification is direct Discord handler behavior for this slice or a small extension to SLICE-015 dynamic recipient resolution.

## 2. Local Baseline

### Application aggregate

Current application states are `submitted`, `queued`, `claimed`, `in_review`, `approved`, `denied`, and `withdrawn` in `ApplicationState` (`services/api/app/contracts/applications.py:33`). Current transition actions are `route`, `claim`, `review`, `approve`, `deny`, and `withdraw` (`services/api/app/contracts/applications.py:43`).

The transition table in `services/api/app/services/applications.py` currently allows:

- `submitted --route--> queued`
- `queued --claim--> claimed`
- `claimed --review--> in_review`
- `in_review --approve|deny--> approved|denied`
- `submitted|queued|claimed|in_review --withdraw--> withdrawn`

Those edges are encoded in `VALID_TRANSITIONS` (`services/api/app/services/applications.py:42`) and enforced by `validate_transition()` (`services/api/app/services/applications.py:332`). SLICE-021 must add new edges without removing or changing these existing SLICE-012 edges.

`transition_application()` is the only public service-level transition entry point today. It:

- Rejects public `route` calls (`services/api/app/services/applications.py:652`).
- Fetches the application and checks authority at `form_snapshot["target_scope"]` (`services/api/app/services/applications.py:659`).
- Builds an action payload and delegates to `_transition_application_locked()` (`services/api/app/services/applications.py:668`).
- Converts stale claim races into `ApplicationAlreadyClaimedError` only for `claim` (`services/api/app/services/applications.py:687`).

`_transition_application_locked()` locks the application row, validates the transition, checks owner-only behavior for `review`, `approve`, and `deny`, updates projection timestamps, inserts `application_reviews`, and records `application.transitioned` with `diff_json` (`services/api/app/services/applications.py:548`).

### Persistence constraints

The `applications` table currently has no interview thread column. Its state CHECK only allows the seven SLICE-012 states (`migrations/versions/wu-022_applications.py:70`).

The `application_reviews` table also constrains actions to the six SLICE-012 actions (`migrations/versions/wu-022_applications.py:156`) and requires `reviewer_id` only for `claim`, `review`, `approve`, and `deny` (`migrations/versions/wu-022_applications.py:160`). Any new `interview`, `waitlist`, or `reactivate` action that inserts a review row must extend this CHECK too.

Repository reads and writes enumerate application columns explicitly. `_APPLICATION_SELECT` must include any new `interview_thread_id`, `insert_application()` must initialize it, and `update_application()` must persist it (`services/api/app/repositories/applications.py:11`, `services/api/app/repositories/applications.py:40`, `services/api/app/repositories/applications.py:130`).

`ApplicationRead` currently exposes no `interview_thread_id` field, so Discord cannot discover/reuse an existing interview thread from the GET response until the contract is extended (`services/api/app/contracts/applications.py:232`).

### Discord baseline

The Discord application review handler already follows the desired GET-then-POST optimistic locking shape:

- Resolve Discord user to member UUID via `/api/v1/members/by-discord/{discord_user_id}`.
- GET `/api/v1/applications/{id}` to obtain the current ETag.
- POST a mutation with `If-Match`.
- Post an outcome summary only after API success.

This pattern is in `services/discord/app/handlers/application_review.py:51`. The current command contract only supports `claim`, `approve`, and `deny` (`services/discord/app/contracts/application_review.py:12`), and command registration only exposes those three commands (`services/discord/app/commands/application_review.py:10`).

Member lookup by internal UUID is available through `GET /api/v1/members/{member_id}` with global `member.read` authority (`services/api/app/api/v1/endpoints/members.py:130`). That is enough for a Discord handler to resolve `ApplicationRead.applicant_id` into a Discord user ID for direct applicant messaging, if the service actor has `member.read`.

### Notification baseline

SLICE-015 created:

- `notification_events`, with `emit()` enqueueing a `notifications_materialize` deferred effect in the same transaction (`services/api/app/services/notification_events.py:32`).
- `notification_rules` and `notification_envelopes`, including `dm`, `thread`, and `designated_channel` as schema-valid channels (`migrations/versions/wu-029a_notifications.py:62`, `migrations/versions/wu-029a_notifications.py:169`).
- Unique envelope indexes for per-event and per-root-cause idempotency (`migrations/versions/wu-029a_notifications.py:190`).
- Discord delivery for DM and designated-channel messages with deterministic nonce; thread delivery is explicitly rejected as out of scope for SLICE-015 (`services/discord/app/handlers/notifications.py:45`, `services/discord/app/handlers/notifications.py:63`, `services/discord/app/handlers/notifications.py:78`).

The current materializer only resolves explicit `discord_user` and `discord_users` recipient selectors. It cannot derive the applicant recipient from an application event payload without extension (`services/api/app/services/notifications_materialize.py:77`).

## 3. State Machine and Persistence Findings

### Required state extensions

Add `interview` and `waitlisted` to `ApplicationState`. Preserve all existing SLICE-012 states and edges.

The additional transition edges required by the ticket are:

- `in_review --interview--> interview`
- `in_review --waitlist--> waitlisted`
- `interview --waitlist--> waitlisted`
- `interview --approve|deny--> approved|denied`
- `waitlisted --reactivate--> claimed`

Do not add new withdrawal edges unless the proposal intentionally expands scope. The ticket says "waitlisted state; no state changes until reactivate," so `waitlisted --withdraw--> withdrawn` should be treated as out of scope unless the user explicitly changes the lifecycle contract.

### Interview thread linkage

Add nullable `applications.interview_thread_id TEXT`. It should be part of:

- Database migration column list.
- Repository SELECT/INSERT/UPDATE.
- `ApplicationRead`.
- `_row_to_read()`.
- `_transition_diff()` so audit diff captures first linkage and any attempted linkage mutations that are accepted.

The column should stay nullable because `ApplicationInterviewRequest.thread_id` is optional. For Discord commands, the normal successful path should provide a non-null thread ID after creating or rediscovering the thread.

AC3 implies the stored thread ID is immutable once set:

- If `interview_thread_id` is null and request has `thread_id`, store it.
- If `interview_thread_id` already equals the request `thread_id`, return success without creating a second thread or second state transition.
- If `interview_thread_id` is set and request has a different `thread_id`, reject with 409 Conflict.
- If request omits `thread_id` and the stored value is already set, return the current stored linkage in `ApplicationRead`.

This idempotent repeat should be implemented outside the formal `VALID_TRANSITIONS` graph, not as an `interview -> interview` edge. Otherwise the state machine would claim a real lifecycle transition occurred when the desired behavior is "reuse the recorded thread."

### Waitlist semantics

`waitlisted` should be a parking state. While in `waitlisted`, normal decision actions should be invalid. The only ticketed exit is `reactivate` to `claimed`.

The minimal schema does not add a dedicated waitlist reason column. Therefore `ApplicationWaitlistRequest.reason` must be persisted through existing review/audit surfaces:

- `application_reviews.notes` can carry the human reason.
- `activity_actions.request_json` for `application.waitlist` should include `reason`.
- `activity_state_changes.payload_json` should include the reason.
- `diff_json` can include notes/reason the same way current `_transition_diff()` includes notes.

For reactivation ownership, the cleanest reading of `ApplicationReactivateRequest(new_owner_id: UUID | None)` is:

- If `new_owner_id` is omitted, preserve the prior `owner_id`.
- If `new_owner_id` is supplied, set `owner_id` to that member UUID.
- If the prior owner is null and no `new_owner_id` is supplied, reject as an application data invariant conflict.

This matches the optional field name and avoids silently assigning ownership to the acting reviewer when the request did not say to do that. The review row's `reviewer_id` should still mean "actor who performed the reactivation," not necessarily the new owner.

### Migration shape

The migration is mechanically small but touches three constraints:

- Add `applications.interview_thread_id TEXT NULL`.
- Replace `applications_state_valid` with one that includes `interview` and `waitlisted`.
- Replace `application_reviews_action_valid` with one that includes `interview`, `waitlist`, and `reactivate`.
- Replace `application_reviews_reviewer_required` so user-reviewer actions include the new actions. `route` remains system/service-capable; `withdraw` keeps current behavior unless proposal changes it.

No new table is required for this slice.

## 4. API Contracts, Authority, and Audit Findings

### Request contracts

The ticketed request contracts fit in `services/api/app/contracts/applications.py`:

- `ApplicationInterviewRequest(thread_id: str | None = None)`
- `ApplicationWaitlistRequest(reason: str)`
- `ApplicationReactivateRequest(new_owner_id: UUID | None = None)`

Validation should reject blank strings for `thread_id` and `reason`. Discord snowflakes are strings elsewhere in this repo, so `thread_id` should remain `str`, not `int`.

Even though dedicated endpoint bodies do not need an `action` field, `ApplicationTransitionAction` or a separate review-action type must include `interview`, `waitlist`, and `reactivate` because `ApplicationReviewRead.action` and the database review row action constraint currently use that vocabulary.

### Endpoint shape

Add the three dedicated endpoints under the existing `/api/v1/applications` router:

- `POST /api/v1/applications/{application_id}/interview`
- `POST /api/v1/applications/{application_id}/waitlist`
- `POST /api/v1/applications/{application_id}/reactivate`

All three should require `If-Match` using the existing strong ETag parser (`services/api/app/api/v1/endpoints/applications/_shared.py:30`) and return `ApplicationRead` with a fresh ETag after mutation.

Dedicated endpoints are preferable to overloading `/transitions` because the request contracts have action-specific fields and idempotency rules. The existing `/transitions` endpoint should continue to serve SLICE-012 actions so existing edges do not break.

### Ownership checks

The ticket explicitly requires ownership checks for interview and waitlist: the reviewer must match `current.owner_id`.

Current code checks owner only for `review`, `approve`, and `deny` (`services/api/app/services/applications.py:563`). SLICE-021 needs that owner check to include at least `interview` and `waitlist`. It should not accidentally require ownership for `claim` or `route`.

For `reactivate`, the ticket names authority but does not explicitly require current-owner matching. Because `reactivate` may assign `new_owner_id`, requiring the actor to be the old owner would make reassignment by another authorized officer impossible. The research conclusion is that the proposal should treat `application.reactivate` authority as the gate, and should only add owner matching for reactivation if the user wants old-owner-only reactivation.

### Authority

Current transition authority maps each action to `application.{action}` at `form_snapshot.target_scope` (`services/api/app/services/applications.py:189`). This directly supports:

- `application.interview`
- `application.waitlist`
- `application.reactivate`

`require_application_read_authority()` currently lets applicants read their own application, or any reviewer with one of `application.claim`, `application.review`, `application.approve`, `application.deny`, or `application.withdraw` read it (`services/api/app/services/applications.py:206`). Add the three new permissions to that reviewer read set, otherwise an officer with only waitlist/interview/reactivate authority could mutate through dedicated endpoints only if the endpoint does its own pre-read internally, but could not GET the application for Discord reuse.

### Audit

The existing mutation substrate already records:

- `activity_actions.action_type`
- redacted `request_json`
- accepted/rejected/failed status
- `activity_state_changes.change_type`
- `payload_json`
- `diff_json`
- aggregate version advancement

SLICE-021 should add action types:

- `application.interview`
- `application.waitlist`
- `application.reactivate`

State changes should continue to use `application.transitioned` with `diff_json`, matching current non-route transitions (`services/api/app/services/applications.py:609`). The diff should include `state`, `owner_id`, `interview_thread_id`, timestamp changes, and notes/reason where applicable.

Current application transitions pass `scope_kind=None` and `scope_id=None` into `mutate_entity()` even though authority is evaluated at target scope (`services/api/app/services/applications.py:626`). For this slice, either keep that behavior uniformly or explicitly change all application transition audit rows to carry target scope. Do not scope only the new actions differently from existing application actions.

## 5. Discord Flow and Notification Findings

### Interview command flow

The Discord interview command should follow the existing review handler shape:

1. Defer the interaction if `ack_deferred` exists.
2. Resolve the Discord actor to a member UUID using existing `resolve_member_id()`.
3. GET the application with user actor headers.
4. If `interview_thread_id` is already present, reuse that thread and do not create a duplicate.
5. If it is absent, create the Discord thread.
6. POST `/api/v1/applications/{id}/interview` with `If-Match` and the created thread ID.
7. Only after API success should the command return/post a success result.

The ordering matters. Creating the Discord thread before the API call means a 409/412 can leave an unused Discord thread. Creating it after the API call means the API cannot atomically record the thread ID created by Discord. The ticket explicitly says "Discord command creates thread (if not exists), POSTs /interview with thread_id," so the proposal must include the recovery path: on retry, GET the application first and reuse `interview_thread_id` if the previous API call succeeded; if Discord creation succeeded but API failed before storing the ID, the handler must rediscover by deterministic name or report failure without creating another API state.

No current Discord helper abstracts thread creation for applications. The closest reusable pattern is ticket thread discovery/creation in `services/discord/app/handlers/tickets.py`, but application interview should be its own handler and contract, not folded into ticket state.

### Waitlist command flow

The waitlist command should:

1. Defer the interaction.
2. Resolve actor member UUID.
3. GET application to obtain ETag.
4. POST `/api/v1/applications/{id}/waitlist` with `reason` and `If-Match`.
5. On success only, post one applicant-facing status message.
6. On 409/412/API error, return an operator-facing failure and do not post applicant-facing status.

This preserves AC4: API conflicts or validation failures do not duplicate Discord status messages or create divergent thread-local state.

Applicant-facing status can be implemented two ways:

- Direct Discord handler message after API success. This is the smallest fit for WU-036b because `ApplicationRead.applicant_id` plus `GET /api/v1/members/{member_id}` can resolve the applicant Discord user ID. It requires `member.read` for the service actor.
- SLICE-015 notification event. This is durable and configurable, but current notification materialization cannot dynamically select "the applicant from this application event" as recipient; it only supports explicit `discord_user` or `discord_users` recipients.

The research conclusion is that SLICE-015 is useful for future applicant notification durability, but using it for WU-036b would require a recipient-resolution extension beyond this ticket's stated scope. The lower-risk SLICE-021 path is direct Discord posting after API success, with tests proving no post on conflict.

### Command registration

Add separate command modules and handlers for WU-036a and WU-036b:

- `services/discord/app/contracts/application_interview.py`
- `services/discord/app/handlers/application_interview.py`
- `services/discord/app/commands/application_interview.py`
- `services/discord/app/contracts/application_waitlist.py`
- `services/discord/app/handlers/application_waitlist.py`
- `services/discord/app/commands/application_waitlist.py`

Then register those commands in `services/discord/app/commands/__init__.py` and in `build_bot_with_registry()`, following the current review command registration pattern (`services/discord/app/commands/application_review.py:15`).

## 6. Open Questions, Risks, and Test Evidence

### Direct answers

1. **State machine extension:** add only the ticketed edges. Preserve SLICE-012 edges exactly.
2. **Interview thread linkage:** nullable `interview_thread_id TEXT`; immutable once set; repeat with same ID is no-op success; different ID is 409.
3. **Waitlist semantics:** `waitlisted` has no exits except `reactivate`. Reactivation should preserve prior owner unless `new_owner_id` is supplied.
4. **Request contracts:** add the three dedicated request models; validate nonblank `reason` and nonblank optional `thread_id`.
5. **Endpoints:** add three dedicated POST endpoints with `If-Match`; owner checks for interview/waitlist; authority check for all three.
6. **Discord flow:** interview GETs and reuses stored thread ID; waitlist posts applicant-facing status only after API success.
7. **Idempotency:** interview uses stored thread immutability; waitlist relies on state-machine rejection of second waitlist.
8. **Authority:** add `application.interview`, `application.waitlist`, `application.reactivate` at `form_snapshot.target_scope`; add them to read-authority permission set.
9. **Audit:** add action types and keep `application.transitioned` state change with `diff_json`.
10. **Migration:** add column and extend state/action CHECK constraints; no new tables.

### Open questions for proposal

- Should `/reactivate` require the actor to be the old owner, or is `application.reactivate` authority sufficient? Research recommends authority-only because `new_owner_id` implies reassignment is allowed.
- Should an interview request without `thread_id` be allowed to move to `interview`, or should the dedicated Discord/API contract require `thread_id` when the request surface is Discord? The request model says optional, but AC3 is only fully satisfied when Discord provides the ID.
- Should application transition audit rows start carrying target scope for all actions? Current behavior leaves application transition audit scope null.

### Test implications

API tests should cover:

- Existing SLICE-012 transitions still pass.
- `in_review -> interview`, `in_review -> waitlisted`, `interview -> waitlisted`, `interview -> approved|denied`, and `waitlisted -> claimed`.
- Invalid `waitlisted -> approve|deny|withdraw|waitlist` returns 409.
- Interview stores thread ID and returns it in `ApplicationRead`.
- Repeating interview with the same thread ID returns success without a duplicate review row or version advance.
- Repeating interview with a different thread ID returns 409.
- Waitlist requires owner and nonblank reason.
- Reactivate with no `new_owner_id` preserves prior owner; with `new_owner_id` assigns the new owner.
- Stale `If-Match` returns 412 for all three endpoints.
- Audit rows contain the new action types and `application.transitioned` state diffs.

Discord tests should cover:

- Interview handler GETs first, reuses existing `interview_thread_id`, and does not call thread creation.
- Interview handler creates a thread only when no stored thread exists, then POSTs `/interview` with `If-Match`.
- Interview API 409/412 does not post a success outcome.
- Waitlist handler posts applicant-facing status only after a 2xx API response.
- Waitlist handler does not post applicant-facing status on 409/412/API errors.
- Command registry includes the new interview and waitlist commands.

### Recommended magnitude

The ticket's **M** sizing is still credible. The API work is a compact lifecycle extension, but correctness depends on careful updates across contracts, database CHECK constraints, repository column lists, owner checks, audit allowlists, and Discord idempotency tests. The main risk is not volume; it is accidentally treating interview repeat as a real transition or posting applicant-facing waitlist messages before the API mutation has safely committed.
