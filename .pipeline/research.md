# SLICE-024 Research: Leadership Succession + Context Transfer

Scope: Phase 1 research for `SLICE-024`, using the bound ticket, proposal/problem references, and the shipped authority, roster, tickets, applications, chapter-governance, and read-model slices.

## 1. Existing Data Model

### `authority_grants` today

- Physical table columns today are:
  `id`, `grantee_id`, `scope_kind`, `scope_id`, `permissions`, `expires_at`, `revoked_at`, `predecessor_grant_id`, `created_at`, `revoked_by`, and `revocation_reason`. `predecessor_grant_id` was present from the original foundation, not added later; `revoked_by` and `revocation_reason` arrived in WU-014. There is no `granted_by`, no `granted_at`, and no transfer-specific column on the table itself. ([wu-004_authority_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-004_authority_foundation.py:17), [wu-014_authority_api.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-014_authority_api.py:15))
- Table constraints/indexes relevant to succession:
  self-FK on `predecessor_grant_id`,
  `predecessor_grant_id != id`,
  scope-kind validity,
  indexes on `grantee_id`, `(scope_kind, scope_id)`, and active `expires_at`.
  There is no unique constraint on `predecessor_grant_id`, so the schema does not prevent multiple successor rows from pointing at the same predecessor grant. ([wu-004_authority_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-004_authority_foundation.py:37), [wu-004_authority_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-004_authority_foundation.py:47), [wu-004_authority_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-004_authority_foundation.py:56))
- Service/repository behavior already shipped:
  `grant_authority(...)` inserts a new row and emits `authority.grant`;
  `revoke_authority(...)` updates `revoked_at`, `revoked_by`, and `revocation_reason` through the mutation primitive and emits `authority.revoke`;
  `fetch_grant(...)` joins `aggregate_heads` to expose the current version for OCC, but the version is not stored on `authority_grants` itself. ([services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:95), [services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:169), [repositories/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/authority.py:48))

### `chapter_roles` today

- Physical table columns today are:
  `id`, `chapter_id`, `template_id`, `name`, `ordinal`, `triggers_succession`, `created_at`.
  `triggers_succession` already exists from WU-007B. It does not need to be added for this slice unless the schema is being repurposed for something else. ([wu-007b_chapter_roles_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-007b_chapter_roles_foundation.py:17))
- Later roster work added the `(chapter_id, id)` uniqueness needed for same-chapter roster FKs, but did not add any succession-specific column beyond the already-existing `triggers_succession`. ([wu-033_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-033_roster.py:35), [wu-033_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-033_roster.py:40))
- Current contracts/repositories still treat `triggers_succession` as a first-class field. ([contracts/chapter_roles.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/chapter_roles.py:13), [repositories/chapter_roles.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/chapter_roles.py:17))
- Important gap: chapter creation copies template `role_structure` into `chapters.template_snapshot`, but `create_chapter(...)` does not seed `chapter_roles` rows. In current code, `chapter_roles` are created separately; roster tests seed them manually. That means some chapters may have a template snapshot that names succession-triggering roles even if the `chapter_roles` table is empty. ([services/chapters.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/chapters.py:158), [services/chapters.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/chapters.py:172), [services/chapter_roles.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/chapter_roles.py:25), [test_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/tests/test_roster.py:74))

### Where role holders are tracked

- There is no `chapter_members` table and no separate role-holder join table. Live holder state is on `roster_entries`. Physical columns today are:
  `id`, `chapter_id`, `member_id`, `role_id`, `status`, `created_at`, `updated_at`, `removal_metadata`. ([wu-007c_roster_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-007c_roster_foundation.py:17), [wu-033_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-033_roster.py:17))
- History is on `roster_transitions`. Physical columns today are:
  `id`, `roster_entry_id`, `chapter_id`, `aggregate_seq`, `from_status`, `to_status`, `from_role_id`, `to_role_id`, `actor_kind`, `actor_id`, `originating_actor_kind`, `originating_actor_id`, `reason`, `removal_metadata`, `recorded_at`. ([wu-033_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-033_roster.py:63))
- Current repository/service code confirms that `roster_entries.role_id` is the live holder position and `roster_transitions` is the audit/history surface. ([repositories/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/roster.py:11), [repositories/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/roster.py:94), [services/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/roster.py:65))

### Application ownership today

- Physical `applications` columns relevant to succession are:
  `id`, `target_scope_kind`, `target_scope_id`, `state`, `owner_id`, `submitted_at`, `queued_at`, `claimed_at`, `review_started_at`, `decided_at`, `withdrawn_at`, `created_at`, `updated_at`, plus `interview_thread_id` from WU-035. `owner_id` is a `UUID` FK to `members.id`. ([wu-022_applications.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-022_applications.py:19), [wu-035_application_interview.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-035_application_interview.py:33))
- Review history is on `application_reviews`, which records `reviewer_id`, `action`, `from_state`, `to_state`, and timestamps. ([wu-022_applications.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-022_applications.py:120))
- Ownership semantics today:
  `claim` sets `owner_id`,
  `review` requires the current owner,
  `request_interview`/`waitlist` require the current owner,
  `reactivate` can optionally move ownership to `new_owner_id`, but only from `waitlisted -> claimed`.
  There is no generic "reassign owner without changing lifecycle state" action. ([services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:48), [services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:629), [services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:662))
- The repository has an owner-state index, but no shipped query helper that lists applications by `owner_id`; current repository code only reads single rows and updates ownership. This is an inference from the current repository surface and SQL search, not an implemented list-by-owner API. ([wu-022_applications.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-022_applications.py:102), [repositories/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/applications.py:95), [repositories/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/applications.py:133))

### Ticket ownership today

- Physical `tickets` columns relevant to succession are:
  `id`, `category_id`, `category_snapshot`, `state`, `priority`, `owner_id`, `resolution`, `terminal_at`, `created_at`, `updated_at`.
  `owner_id` is `TEXT`, not an FK. Open-vs-terminal is represented by `terminal_at IS NULL`, not by a fixed state set. ([wu-025a_tickets_create.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-025a_tickets_create.py:17))
- History is on `ticket_transitions`, which records `from_owner_id` and `to_owner_id` alongside the state transition. ([wu-025b_ticket_transitions.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-025b_ticket_transitions.py:17))
- Ownership semantics today:
  the ticket service only changes owner inside a valid category state-machine edge, and only if that edge has `allow_owner_change`. There is no dedicated ticket reassignment or handoff helper outside that transition system. ([services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:152), [services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:171), [services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:390))
- As with applications, the schema has an owner-state index, but the shipped repository surface does not yet expose a list-by-owner query helper. ([wu-025a_tickets_create.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-025a_tickets_create.py:76), [repositories/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/tickets.py:70), [repositories/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/tickets.py:103))

### Audit and OCC substrate relevant to succession

- All of the relevant mutable aggregates already ride the shared mutation substrate:
  `aggregate_heads.current_seq` is the OCC version source;
  `activity_actions` carries `correlation_id` and `causation_id`;
  `activity_state_changes` stores the accepted state facts. ([contracts/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/mutations.py:28), [services/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/mutations.py:58), [repositories/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/mutations.py:46))
- `mutate_entity(...)` propagates the ambient audit context, but it returns only `version` and `etag`. It does not return the inserted action ID, so direct parent-child causation chaining between successive mutations is not yet first-class. Shared `correlation_id` is easy; strict per-step `causation_id` chaining is not. ([services/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/mutations.py:74), [services/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/mutations.py:150), [contracts/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/mutations.py:44))

### What "role holder departs" looks like today

- Operationally, a role-holder departure is a roster action, not a chapter-governance action.
  `ChapterGovernanceAction` only covers `suspend`, `restore`, and `archive`, while roster transitions handle individual member state changes. ([contracts/chapters.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/chapters.py:21), [api/v1/endpoints/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/api/v1/endpoints/roster.py:187))
- The roster endpoint requires `roster.remove` for `to_status="removed"` and `roster.write` for the non-terminal statuses. `removed` is terminal in the shipped tests. ([api/v1/endpoints/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/api/v1/endpoints/roster.py:201), [test_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/tests/test_roster.py:484))
- There is no explicit `departing` flag, no `departed_at`, and no dedicated departure reason enum. The only persisted signals are `status`, `reason` on the transition row, and free-form `removal_metadata`. That means "departing" vs "departed" is not currently a schema-level distinction. ([contracts/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/roster.py:35), [services/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/roster.py:197))

### Identifier mismatch that matters for this slice

- Current ID types are inconsistent across the exact tables SLICE-024 wants to join:
  `authority_grants.grantee_id` is `TEXT`,
  `roster_entries.member_id` is `TEXT`,
  `tickets.owner_id` is `TEXT`,
  but `applications.owner_id` is `UUID` FK to `members.id`.
  Succession can join grants to roster holders directly on text, but application handoff only works cleanly if the roster/member/grant identity being transferred is a real member UUID string. ([wu-004_authority_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-004_authority_foundation.py:20), [wu-007c_roster_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-007c_roster_foundation.py:21), [wu-022_applications.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-022_applications.py:30), [wu-025a_tickets_create.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-025a_tickets_create.py:36))

## 2. Succession Plan Computation Algorithm

Given the shipped substrate, a `GET /chapters/{chapter_id}/succession-plan` can be computed without a successor designation. The transfer/handoff steps are separate from the plan read.

### Computable now

1. Fetch succession-triggering roles from `chapter_roles`:
   `WHERE chapter_id = :chapter_id AND triggers_succession = TRUE`, ordered by `ordinal`. The flag already exists and is queryable. ([wu-007b_chapter_roles_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-007b_chapter_roles_foundation.py:23), [repositories/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/roster.py:77))
2. Find current holders from `roster_entries` by `role_id`, excluding removed entries if the plan is meant to identify currently-filled offices. If the intent is specifically "holder flagged as departing/departed", the plan then needs a policy over `status` and `removal_metadata`.
3. Fetch each holder's active authority grants from `authority_grants` by `grantee_id = roster_entries.member_id`, with the same active predicate already used by the archive plan:
   `revoked_at IS NULL` and `(expires_at IS NULL OR expires_at > now)`. ([repositories/archive_queries.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/archive_queries.py:79))
4. Fetch open tickets by holder ownership:
   `terminal_at IS NULL` and `owner_id IN departing_holder_ids`. Existing ticket open/closed semantics already use `terminal_at`, not a fixed state list. ([wu-025a_tickets_create.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-025a_tickets_create.py:39), [repositories/archive_queries.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/archive_queries.py:58))
5. Fetch pending applications by holder ownership:
   new query required. The current codebase has two different "still operational" application state sets:
   archive plan uses `submitted`, `queued`, `claimed`, `in_review`,
   while operational overview uses `submitted`, `queued`, `claimed`, `in_review`, `interview`, `waitlisted`. ([repositories/archive_queries.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/archive_queries.py:37), [services/read_models.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/read_models.py:31))

### Not computable from existing state alone

- `successor_designated` and `successor_member_id` are not stored anywhere in the current schema. No chapter, roster, or authority table presently carries successor designation metadata. That is new state. ([contracts/chapters.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/chapters.py:53), [contracts/roster.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/roster.py:17), [contracts/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/authority.py:20))
- "Departing" is not distinct from "removed" in the schema. If the slice wants a plan to surface role holders who are still present but marked for imminent succession, that needs either a convention inside `removal_metadata` or new explicit state.

### Proposed `SuccessionPlanRead` fit to the current substrate

- `chapter_id`: directly available.
- `departing_roles: list[{role_id, holder_member_id, triggers_succession}]`: computable if synthesis defines which roster statuses count.
- `affected_grants: list[{grant_id, scope_kind, scope_id, permissions}]`: directly derivable from active grants for the departing holder set.
- `pending_applications: list[{application_id, owner_id}]`: requires a new owner-based query and a decision on the open-state set.
- `pending_tickets: list[{ticket_id, owner_id}]`: requires a new owner-based query but the open-state predicate already exists.
- `successor_designated` / `successor_member_id`: new persisted state or new request-time input.

Conclusion for AC1:
the plan can be fetched without a designated successor, because all of the "what is at risk" inputs are derivable from existing chapter-role, roster, authority, and work-item ownership state. The actual transfer is a separate write path.

## 3. Authority Transfer Semantics + Idempotency

### Existing reusable lifecycle

- `grant_authority(...)` already creates a successor-style row with arbitrary `predecessor_grant_id`, scope, permissions, and expiry copied from caller input, then records the write through `mutate_entity(...)`. ([services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:95))
- `revoke_authority(...)` already revokes the predecessor row through OCC and records the revoke event through the same mutation substrate. ([services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:169))
- That means WU-044B can reuse the service-layer lifecycle path cleanly:
  create successor grant,
  revoke predecessor grant,
  keep both writes under the same audit context.

### Transfer semantics that fit the existing code

- Create the new grant with:
  `grantee_id = successor_id`,
  same `scope_kind`, `scope_id`, `permissions`, and `expires_at`,
  `predecessor_grant_id = old_grant.id`.
- Revoke the old grant with:
  `revoked_at = now`,
  `revoked_by = actor.actor_id`,
  `revocation_reason = "succession_transfer"` or the final synthesis-approved equivalent.
- Validate before transfer:
  predecessor grant exists,
  predecessor grant is still active,
  successor is eligible under the active succession plan if that remains an AC,
  successor is not already holding an active duplicate grant that would trip the duplicate-guard.

### Current idempotency and double-transfer constraints

- The current duplicate guard only blocks an already-active grant for the same `grantee_id + scope + permissions`. It does not block multiple successor rows for the same `predecessor_grant_id`. ([repositories/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/authority.py:118), [services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:107))
- The current revoke path is explicitly non-idempotent on second call: a second revoke raises `GrantAlreadyRevokedError` and the HTTP endpoint returns `409`. ([services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:182), [test_authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/tests/test_authority.py:492))
- Therefore WU-044B needs a service-level idempotency guard before it calls `revoke_authority(...)`:
  either:
  return the already-created successor grant when `predecessor_grant_id = :grant_id` already exists,
  or:
  reject with `409` when any prior transfer is detected.
- If the desired behavior is "re-invoking returns the existing successor grant", the current schema supports that lookup, but only if the service adds a repository query for `predecessor_grant_id = :grant_id`. No such helper exists today.

### One more important existing behavior

- The authority HTTP endpoints for create/list/revoke currently require actor identity, but they do not use `RequireAuthority(...)` or any explicit authority permission gate. If SLICE-024 wants transfer to require operational authority, that is a new endpoint-level policy, not something inherited automatically from the current authority endpoints. ([api/v1/endpoints/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/api/v1/endpoints/authority.py:70), [api/v1/endpoints/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/api/v1/endpoints/authority.py:126))

## 4. Handoff (Applications + Tickets) Flow

### Applications handoff

- What exists:
  application ownership is already modeled,
  owner changes already happen in `claim` and `reactivate`,
  owner-based OCC and audit are already there. ([services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:648), [services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:662))
- What does not exist:
  a generic ownership reassignment action for open applications.
  The only shipped owner-reassignment path is `waitlisted -> claimed` via `reactivate`, optionally with `new_owner_id`. That is too narrow for leadership handoff across all non-terminal states. ([services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:59), [services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:663), [test_application_interviews.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/tests/test_application_interviews.py:566))
- Research conclusion:
  WU-045A-applications cannot be implemented as a thin wrapper around today's `transition_application(...)` unless synthesis intentionally narrows handoff to waitlisted items only, which does not match the slice. The codebase needs either:
  a new application transition action such as `reassign`/`handoff`,
  or a separate batch handoff service that still writes through the mutation substrate and `application_reviews`.

### Tickets handoff

- What exists:
  ticket ownership is modeled on the ticket row and `ticket_transitions` history;
  ownership changes are already captured when a valid category edge allows them. ([wu-025b_ticket_transitions.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-025b_ticket_transitions.py:29), [services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:217))
- What does not exist:
  a generic ticket reassignment API. `transition_ticket(...)` requires a valid state-machine edge, and owner changes are forbidden unless that edge explicitly allows them. ([services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:130), [services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:171), [services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:390))
- Research conclusion:
  WU-045A-tickets also needs new semantics, unless synthesis is willing to make handoff depend on per-category state-machine support for owner-changing edges. The current substrate is not a generic reassign-by-owner system.

### Cross-scope and manual handoff

- Both subsystems already encode scope on the item itself:
  applications via `form_snapshot.target_scope`,
  tickets via `category_snapshot.routing_scope`.
  That gives a clean predicate for "within the predecessor grant's scope" vs "manual handoff required". ([services/applications.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/applications.py:267), [services/tickets.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/tickets.py:461))

### Handoff idempotency

- The simple idempotency key already exists in both tables:
  if `owner_id == successor_id`, the item has already been handed off and the batch can no-op it.
- However, if the implementation routes through current mutation helpers, it must avoid issuing unnecessary lifecycle writes, because those helpers are OCC-sensitive and not designed as no-op batch reassignment wrappers.

### Causal chain reality check

- Shared `correlation_id` across one succession flow is straightforward:
  keep one audit context around transfer and handoff calls. (`mutate_entity(...)` will reuse the ambient context.) ([services/mutations.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/mutations.py:74))
- Strict parent-child `causation_id` chaining is not currently ergonomic:
  the mutation primitive stores `causation_id`, but it does not return the action ID needed to make "handoff B was directly caused by transfer A" precise at the activity-action level.
- Existing code uses the audit context to share correlation and sometimes a run-level causation UUID, but not a directly linked action-by-action chain. Chapter archive is the closest precedent, and it threads one run correlation/causation pair across many effects rather than reconstructing direct per-step parentage. ([services/chapters.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/chapters.py:875), [services/chapters.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/chapters.py:928))

## 5. Leadership Context View Data Sources

### What exists today

- The read-model substrate today is minimal:
  `read_model_cursors` plus a service that computes live counts from base tables and uses the cursor only to expose projector lag/staleness. There are no dedicated materialized projection tables for operator views yet. ([wu-031_read_models.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-031_read_models.py:18), [services/read_models.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/read_models.py:93), [repositories/read_models.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/read_models.py:13))
- `read_operational_overview(...)` is the current precedent:
  it reads base tables directly,
  then computes `is_stale` from cursor lag, not from missing domain handoff state. ([services/read_models.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/read_models.py:128))

### Data sources needed for `GET /members/{member_id}/leadership-context`

- `active_grants`:
  already derivable from authority grant listing for the member/grantee. ([services/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/services/authority.py:279))
- `inherited_from`:
  derivable from the `predecessor_grant_id` chain, but no current repo helper traverses predecessor lineage or joins predecessor grant -> previous holder member. New query/helper needed. ([contracts/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/contracts/authority.py:20), [repositories/authority.py](/home/nes/projects/server-manager/worktrees/slice-024/services/api/app/repositories/authority.py:48))
- `current_applications`:
  ownership is already on the application row, but current repo/service code has no list-by-owner helper. New query/helper needed.
- `current_tickets`:
  same story for tickets: the row has `owner_id`, but the repo surface currently exposes single-row reads and updates, not owner-based list queries.
- `is_stale` as defined by SLICE-024:
  this is a new domain staleness signal, not the same thing as the read-model projector staleness signal from SLICE-017.
  Existing read-model `is_stale` means "the projector is behind";
  SLICE-024 `is_stale` means "the successor context is incomplete because predecessor-owned work still exists".

### Research conclusion

- If synthesis means "follow the current SLICE-017 pattern", leadership context can probably be implemented as a live query service plus cursor-based freshness metadata.
- If synthesis means "reads only from projection state" literally, the current codebase does not yet have the projection tables to support that. That would require new projection storage, not just a new endpoint.

## 6. Migration Needs

### Confirmed non-needs

- `authority_grants.predecessor_grant_id` does not need a new migration. It already exists from WU-004. ([wu-004_authority_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-004_authority_foundation.py:30))
- `chapter_roles.triggers_succession` does not need a new migration. It already exists from WU-007B. ([wu-007b_chapter_roles_foundation.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-007b_chapter_roles_foundation.py:24))
- A migration named `wu-044_chapter_roles_succession.py` that only adds `triggers_succession` would be redundant against the current schema.

### Possible schema additions, depending on synthesis decisions

- If "departing/departed" must be explicit and queryable:
  add dedicated departure metadata somewhere durable.
  Today that is only implicit in `status` and free-form `removal_metadata`.
- If successor designation must persist before transfer:
  add a new successor-designation field or table.
  No current table carries it.
- If WU-045B truly requires projection-state reads:
  add projection tables, not just cursor rows.
- If transfer idempotency must be strongly enforced at the DB level:
  consider a unique constraint around successor lineage, because the current schema does not prevent multiple rows for one predecessor.

### One migration question that is probably "no"

- Adding `departed_at` directly to `chapter_roles` would not fit the current model, because role occupancy is not on `chapter_roles`; it is on `roster_entries`.
  If a departure timestamp is needed, it belongs on roster state or a succession-specific table, not on the role definition table.

## 7. Service Actor

- Current seeded service actors include:
  `discord-ticket-bot`,
  `roster-syncer`,
  `read-model-projector`,
  `chapter-archiver`.
  None are succession-specific. ([wu-022_applications.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-022_applications.py:171), [wu-031_read_models.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-031_read_models.py:49), [wu-033_roster.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-033_roster.py:134), [wu-042_chapter_governance.py](/home/nes/projects/server-manager/worktrees/slice-024/migrations/versions/wu-042_chapter_governance.py:165))
- For the slice as written, a dedicated service actor is probably not needed.
  Transfer and handoff are operator-triggered writes, not scheduled automation.
- A service actor only becomes necessary if synthesis expands scope to scheduled follow-up, automatic stale-context sweeps, or delayed transfer execution.

## 8. PR Decomposition Question

Research conclusion: this slice splits cleanly, and the current code seams argue for splitting.

- PR A: WU-044A + WU-044B
  Succession plan + authority transfer.
  This stays mostly inside chapter/roster/authority data gathering and the authority lifecycle substrate.
- PR B: WU-045A-applications + WU-045A-tickets
  Handoff execution.
  This is the riskiest part because both subsystems need new ownership-transfer semantics, and those semantics are different between applications and tickets.
- PR C: WU-045B
  Leadership context view.
  This can land after the transfer/handoff semantics are settled, because its `is_stale` signal depends on what "handoff completed" means.

Reasons the split is cleaner than one atomic PR:

- Applications and tickets do not share a common handoff primitive today.
- Read-model work is separable from transfer semantics.
- The largest unknowns are in WU-045A, so isolating them makes review and rollback easier.

The only caveat:
if synthesis insists that `leadership-context` must read from brand-new projection tables that are populated directly by handoff events, PR C depends on the final event shapes from PR B.

## 9. Open Questions for Synthesis

- What exact roster condition means "departing" for succession planning?
  `removed` only,
  `on_leave`,
  `under_review`,
  or a new explicit departure marker?
- Are `chapter_roles` guaranteed to exist for all live chapters?
  Current chapter creation snapshots template role structure but does not populate `chapter_roles`.
- What identifier should `successor_id` use?
  A member UUID,
  or the broader string actor/grantee ID used by authority/roster/tickets?
- For pending applications, should the handoff set include `interview` and `waitlisted`?
  Current codebase disagrees between archive-plan logic and operational-overview logic.
- Should WU-044B return the existing successor grant on retry, or reject with `409` after any prior transfer?
  The schema allows either, but only service logic can enforce it today.
- Does transfer need an explicit authority permission gate?
  Existing authority-grant endpoints do not currently require one.
- Should application handoff be modeled as a new application lifecycle action, or as a separate reassignment mutation outside the current lifecycle?
- Should ticket handoff bypass category state-machine owner-change rules, or must it remain a valid ticket transition under each category's edge definitions?
- Does AC3 require true direct-cause chaining in `causation_id`, or is shared `correlation_id` across the succession flow sufficient?
  Current primitives make the former awkward and the latter easy.
- Does WU-045B mean literal projection tables, or the current read-model style of live queries plus cursor-based freshness reporting?
- Where is successor designation persisted before transfer?
  No current table or contract has a place for it.

## Final Summary

- The core succession schema pieces already exist: `authority_grants.predecessor_grant_id` is live, and `chapter_roles.triggers_succession` is already on the table.
- Live role occupancy is in `roster_entries`, not in a chapter-members join, and current code models departure as a roster transition rather than a chapter-governance action.
- Authority transfer can reuse the existing grant/revoke lifecycle cleanly, but idempotency and double-transfer detection need new service logic because the schema does not constrain one-successor-per-predecessor.
- Application and ticket handoff are the biggest substrate gaps: both subsystems model ownership, but neither ships a generic batch reassignment path today.
- `leadership-context` can be aggregated from current tables, but true "projection-state only" support and the SLICE-024 stale-context signal are both new work, not already provided by the current read-model slice.
