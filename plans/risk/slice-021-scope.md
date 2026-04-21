# SLICE-021 Scope Risk: **LOW**

Rating: **LOW** — the proposal delivers AC1-4 inside the three named work units (WU-035, WU-036a, WU-036b), extends the SLICE-012 application aggregate in place, adds no new scope kind, and limits Discord surface to the three lifecycle commands. Code-boundary expansions beyond the ticket's enumerated file list (repository, migration, endpoint router include, `_shared.py` error map) are the minimum infra glue required by the binding synthesis decisions and follow the same pattern SLICE-018 used.

## SLICE-021 ACs (ticket)

1. Requesting an interview is valid only from `in_review` and returns `interview`.
2. Waitlist is valid only from `in_review` or `interview`; reactivate returns `claimed` with optimistic-locking protection.
3. Repeating an interview request reuses the recorded thread instead of creating a duplicate.
4. API conflicts or validation failures do not duplicate Discord status messages or create thread-local divergence.

## Findings

### 1. AC trace maps to specific proposal sections

| AC | Proposal sections | Named tests |
|---|---|---|
| AC1 | §1 AC-matrix, §5 `request_interview`, §6 interview endpoint, §8 transition table row `in_review -> request_interview -> interview`. | `test_application_interviews.py` — "`request_interview` succeeds only from `in_review`" (queued/claimed/submitted return `409 invalid_application_transition`); "non-owner with `application.request_interview` gets `409 application_not_owner`". |
| AC2 | §1 AC-matrix, §2 migration CHECK update, §5 `waitlist_application` + `reactivate_application`, §6 dedicated endpoints with `parse_if_match_strong`, §8 transition rows for waitlist/reactivate. | `test_application_interviews.py` — waitlist from `in_review` and `interview` succeed, waitlist from `waitlisted` returns `409 invalid_application_transition`, reactivate with stale `If-Match` returns `412 stale_application_version`, reactivate returns `claimed`, `new_owner_id` present/absent variants, non-owner with `application.reactivate` passes. |
| AC3 | §1 AC-matrix, §2 `interview_thread_id` column, §4 repository propagation, §5 `request_interview` idempotency branch, §9 idempotency table, §11 Discord test matrix. | `test_application_interviews.py` — "repeat POST `/interview` with same thread id returns `200`, same state/thread, no additional `application_reviews` row, no version increment"; "repeat with different thread id returns `409 application_interview_thread_mismatch`"; `test_application_interview.py` — "existing `interview_thread_id` from GET is reused and no thread creation call occurs". |
| AC4 | §1 AC-matrix, §9 deterministic thread marker, §11 Discord handler behavior for conflict/validation/transport failures. | `test_application_interview.py` — "API `409 application_interview_thread_mismatch`, `412 stale_application_version`, or validation error returns failure and sends no success/outcome message"; "If Discord creation succeeds but API fails, retry discovers the deterministic application marker/name before creating another thread"; `test_application_waitlist.py` — "`409`, `412`, `422`, and API transport failures send no applicant-facing status message". |

All four ACs have at least one direct test. No AC is validated only transitively.

### 2. Deferred items are absent from the proposal

| Deferred to | Present in SLICE-021 proposal? |
|---|---|
| Applicant portal (SLICE-017) | **No.** No web UI, no applicant-facing portal routes, no portal auth flow. Only API + Discord surfaces. |
| Review dashboards (SLICE-017) | **No.** No list/filter/summary endpoint; no aggregate metric surface. `ApplicationRead` is the only read contract affected (adds `interview_thread_id`). |
| Notification rules | **No.** §1 non-scope: "no notification-rule expansion." |
| Separate waitlist/interview aggregates or tables | **No.** §1 non-scope: "no interview table, no waitlist table." D3 migration adds one column + two CHECK replacements; no table creation. |
| Backwards-compat aliases | **No.** §1 non-scope. |

### 3. Code boundary mapping per WU

Ticket-declared boundaries (SLICE-021 §Work Units) vs. proposal-touched files:

**WU-035**
- `services/api/app/contracts/applications.py` — declared; proposal §3 extends enums + adds 3 request contracts + adds `interview_thread_id` on `ApplicationRead`. ✔
- `services/api/app/services/applications.py` — declared; proposal §5 extends `VALID_TRANSITIONS`, `AUDIT_ACTION_TYPE`, `TRANSITION_PAYLOAD_ALLOWLIST`, owner/read authority helpers. ✔
- `services/api/app/api/v1/endpoints/applications/interviews.py` — declared; proposal §6 adds this module. ✔
- `services/api/tests/test_application_interviews.py` — declared; proposal §11 defines the test matrix. ✔

**WU-036a**
- `services/discord/app/contracts/application_interview.py` — declared; proposal §11 implies contract definition; no contradictory detail. ✔
- `services/discord/app/handlers/application_interview.py` — declared; proposal §11 defines handler behavior. ✔
- `services/discord/app/commands/application_interview.py` — declared; proposal §11 defines command registration (`/apply-interview`). ✔
- `services/discord/tests/test_application_interview.py` — declared; proposal §11 defines the test matrix. ✔

**WU-036b**
- `services/discord/app/contracts/application_waitlist.py` — declared; ✔
- `services/discord/app/handlers/application_waitlist.py` — declared; proposal §11 defines handler behavior. ✔
- `services/discord/app/commands/application_waitlist.py` — declared; proposal §11 registers `/apply-waitlist` and `/apply-reactivate`. ✔
- `services/discord/tests/test_application_waitlist.py` — declared; proposal §11 defines test matrix. ✔

**Code-boundary extensions beyond the ticket table (all infra glue with D-backing):**

| File | Reason | D-decision |
|---|---|---|
| `migrations/versions/wu-035_application_interview.py` | Add `interview_thread_id`, extend state and review-action CHECK constraints. Required to durably store interview linkage and persist the three new review actions. | D3, D13 |
| `services/api/app/repositories/applications.py` | Propagate `interview_thread_id` through `_APPLICATION_SELECT`, `insert_application`, `update_application`, and `_row_to_read`. Required for D5 idempotency against a stored column. | D5, D12 |
| `services/api/app/api/v1/endpoints/applications/__init__.py` | Include the new `interviews.py` router. Trivial. | D4 |
| `services/api/app/api/v1/endpoints/applications/_shared.py` | Map `ApplicationInterviewThreadMismatchError` to `409 application_interview_thread_mismatch`. | D5 |
| `services/discord/app/__main__.py` | Register the three new command handlers. | D10 |
| `services/discord/tests/test_main.py` | Regression update to assert the three new command handlers are registered. | D10 |

These are the minimum set needed to honor D3, D4, D5, D10, D12, and D13. They parallel SLICE-018's pattern of extending the declared Code Boundary with migration + repository + `_shared` error-map glue. None introduces a parallel aggregate, mutation surface, or storage system.

### 4. Application state machine is extended in place (D1/D2)

- Single `ApplicationState` enum (contracts/applications.py) extended with `interview` and `waitlisted`; no parallel review-status enum.
- Single `VALID_TRANSITIONS` table in `services/applications.py` extended with 8 new edges (§8 transition table); no parallel state-machine object.
- Single `transition_application()` service entry point; §5 explicitly forbids a parallel lifecycle service ("implementation must reuse the existing transition machinery instead of creating a parallel lifecycle service"). Thin wrapper functions `request_interview()`, `waitlist_application()`, `reactivate_application()` are permitted only if they "immediately delegate into the same transition path."
- Single optimistic-locking path via `mutate_entity()`; all three dedicated endpoints require `If-Match` (D4).
- No `interview -> interview` or `waitlisted -> waitlisted` self-transitions; interview repeat is handled as an idempotent read/return case around `interview_thread_id`, not a state-machine edge (§8 + §9).

### 5. No new scope kinds

- Authority is evaluated at `application.form_snapshot["target_scope"]` (§7). Current scope kinds (`global`, `chapter`, `member`) are unchanged.
- §7 binding: "do not introduce a new scope kind."
- `application.request_interview`, `application.waitlist`, `application.reactivate` are new **permission names** under the existing `application.{action}` naming rule; they are not new scope kinds. This parallels how SLICE-012 introduced `application.claim`, `application.review`, `application.approve`, `application.deny`, `application.withdraw` under the same rule.

### 6. No service actor grants beyond the existing SLICE-012 set

- The proposal adds no new service actor.
- The Discord daemon's existing service actor already reaches the application lifecycle through `ActorIdentity` headers; endpoint authority continues to come from those headers, not body `originating_*` fields (§7: "The body `originating_actor_kind` and `originating_actor_id` fields do not grant authority and must not override the request actor headers.").
- No migration in this slice seeds a service actor with the three new `application.*` permissions (the migration in §2 is schema-only). Operators are the subjects of the new permissions — consistent with SLICE-012's pattern, where `application.claim` / `application.approve` / `application.deny` are operator grants, not service-actor grants.
- `require_application_read_authority()` gains `application.request_interview`, `application.waitlist`, `application.reactivate` in its reviewer-permission set (§5, §7), but this mirrors the existing SLICE-012 treatment of `application.claim` / `application.review` / `application.approve` / `application.deny` / `application.withdraw`, not an expansion of the service-actor grant surface.

### 7. Discord command surface is limited to the three lifecycle commands

Existing application-related Discord commands before SLICE-021:

- `/apply-submit` (WU-023b)
- `/apply-claim`, `/apply-approve`, `/apply-deny` (WU-026)

SLICE-021 adds:

- `/apply-interview` (WU-036a)
- `/apply-waitlist` (WU-036b)
- `/apply-reactivate` (WU-036b)

Nothing in §11 or §5 modifies the behavior of existing command handlers. Registration is additive (three `register_*` calls in `__main__.py`), and the regression guard in `test_main.py` is the minimum update needed to reflect the new command set. No DM/thread channel types, no audit-log surfaces, no ephemeral admin tooling beyond the three slash commands.

`POST /api/v1/applications/{application_id}/transitions` (the generic action endpoint from SLICE-012) remains and will implicitly accept the extended action enum (§6 closing paragraph). This is a natural consequence of extending `ApplicationTransitionAction`, not a second mutation surface; the proposal is explicit that "the new Discord handlers must use the dedicated endpoints" so the idempotency rules in D5 are enforced for interview. LOW observation only — flagged in §9 below.

### 8. Migration chain is clean (D13)

- `down_revision = "wu_042_chapter_governance"` matches the current head recorded in synthesis §Resolved Existing State.
- No detached migration head, no rewriting of prior migrations (§2 migration header + §1 D13 row).
- Downgrade follows the existing "raise on unsafe data" pattern rather than silently deleting rows in new states.

### 9. Minor observations (not severity escalations)

| Observation | Verdict |
|---|---|
| The extended `ApplicationTransitionAction` enum is also accepted by the pre-existing generic `POST /transitions` endpoint. A privileged caller could drive interview/waitlist/reactivate through the generic endpoint, bypassing the idempotency + error-shape contracts of the dedicated endpoints. | **Acceptable.** The `request_interview` idempotency lives inside `_transition_application_locked()` per §5 ("branch on action name for optional interview reason and thread handling"), so the stored-thread guard applies from either entry point. Discord is bound to the dedicated endpoints (D10), which is where AC4's user-visible behavior is exercised. Future auditors should confirm the idempotency branch is unconditional on the action, not on the route. |
| Proposal §5 introduces a thread-discovery requirement for the deterministic marker `application_id=<uuid>` in a Discord thread starter message / name. This slightly widens WU-036a's thread-management responsibility beyond "create or reuse via stored id." | **Acceptable.** Required by AC4's no-duplicate-thread invariant when the API POST fails after Discord thread creation. Bounded: the marker is a format convention and a discovery lookup — no new storage system, no admin tooling, no scheduled reconciler. Parallels the `roster_sync_retry` idempotency-key pattern from SLICE-018 as a deterministic join key. |
| `_reviewer_id()` must be updated so `request_interview`, `waitlist`, and `reactivate` all require a user actor (§5). Reactivate is a handoff and may be initiated without owner match, but it still requires a user reviewer. | **Correct and narrow.** No service-actor bypass is introduced. |
| Audit payload for the idempotent interview no-op intentionally does not create a state change (§10). | **Correct.** Avoids polluting `activity_state_changes` with no-op rows while still returning `200` + current ETag. |

### 10. No scope leakage into downstream slices

| Downstream | Would depend on | Present in proposal? |
|---|---|---|
| SLICE-017 applicant portal & review dashboards | Web UI routes, list/filter endpoints, applicant-facing portal | **No.** Not referenced; no UI surface. |
| SLICE-022 compliance | Compliance hook on interview/waitlist transitions | **No.** Only `activity_actions` / `activity_state_changes` / `application_reviews` writes, consistent with existing SLICE-012 behavior. |
| Notification templates / applicant DMs | Template system or templated embed content | **No.** §1 non-scope "no notification-rule expansion." The `/apply-waitlist` handler posts "exactly one applicant-facing status message" (§11), not a templated rule. |
| Automated interview scheduling | Calendar integration, scheduler, reminder worker | **No.** Interview is a state + a thread linkage, nothing more. |
| Parallel review adjudication system | Independent review service or aggregate | **No.** §1 non-scope + D11 extension of the existing `transition_application` path. |
| Cross-slice scope kind introduction | New `target_scope` kinds | **No.** §7 "do not introduce a new scope kind." |

## Summary table

| Risk category | Severity | Notes |
|---|---|---|
| Scope creep beyond WU-035/036a/036b | None | The three WUs plus minimum infra glue (migration, repository propagation, `_shared` error map, `__init__` router include, `__main__` registration, `test_main.py` regression). Every extension is backed by a D-decision and parallels the SLICE-018 scope pattern. |
| Deferred applicant portal / review dashboards leaking in | None | §1 non-scope + no web UI surface introduced. |
| AC test coverage gaps | None | All 4 ACs have direct named tests in §11. |
| Parallel application aggregate or mutation surface | None | D1/D2 in-place extension of `ApplicationState`, `VALID_TRANSITIONS`, `transition_application`. No parallel service, storage, or state machine. |
| New scope kinds | None | §7 explicitly forbids; current scope kinds unchanged. |
| Service actor grants beyond SLICE-012 set | None | No new service actor seeded; new permissions are operator grants in the existing `application.{action}` namespace; Discord daemon authority unchanged. |
| Discord command surface beyond interview/waitlist/reactivate | None | Three additive slash commands + `test_main.py` registration regression; no edits to existing command handlers. |
| Generic `/transitions` endpoint double-mutation surface | Low observation | Implementation must keep the `interview_thread_id` idempotency guard inside `_transition_application_locked()` so it applies regardless of entry point; not a scope-gate concern. |

## What LOW requires (already met)

1. Each AC has at least one direct named test — **yes** (§11 test matrix).
2. Deferred items (SLICE-017 portal/dashboards, notification rules, parallel aggregates) absent from proposal body — **yes** (§1 non-scope + verification in §10 table).
3. Code-boundary extensions beyond the ticket table are the minimum set required by binding D-decisions — **yes** (§3 table above).
4. State machine is extended in place with no parallel aggregate — **yes** (D1/D2 + §5).
5. No new scope kinds — **yes** (§7).
6. No new service actor grants beyond the SLICE-012 set — **yes** (§7, migration schema-only).
7. Discord surface limited to `/apply-interview`, `/apply-waitlist`, `/apply-reactivate` — **yes** (§11 + §6 of this assessment).

No scope reductions or additions are required. The proposal is right-sized for AC1-4, and every extension beyond the ticket's minimal shape is backed by a binding synthesis decision.
