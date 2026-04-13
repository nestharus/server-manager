# Scope Risk Assessment: daemon/applications.py (Revised)

**Overall risk level: LOW**

The revision tightened the proposal without expanding scope. Every
change either closes an ambiguity from the prior version, adds a cheap
guard condition, or specifies cleanup behavior that was already implicit
in the review flow. The public API is unchanged (3 symbols), the
anti-scope section is unchanged (10 exclusions), and the internal helper
count dropped from 14 to 12. No new features, states, or capabilities
were introduced.

## What changed between versions

| Area | Prior state | Revised state | Effect |
|---|---|---|---|
| DB approach | Uncommitted — might extend db.py or use raw SQL | 5 explicit db.py contract signatures | Narrowed (removed SQL from applications.py) |
| `_get_blacklist_entry` | Pass-through wrapper of db.py function | Removed from helper list | Narrowed |
| Session lifetime | Timestamps present but no described expiry | 15-minute TTL with lazy eviction | Clarified (gave timestamps a purpose) |
| Thread privacy | `create_thread(message=None)` mentioned | Added explicit `invitable=False` requirement | Tightened (one parameter) |
| Review authorization | Relied on channel visibility | Added `officer_role_id` check per callback | Tightened (defense in depth) |
| Duplicate submissions | Not addressed | `has_active_submission(...)` guard before modal | Tightened (guard condition) |
| Terminal decisions | Queue message left as-is | Edit embed + disable buttons on approve/deny | Clarified (cleanup was implicit) |

Net symbol count: 3 public + 1 dataclass + 3 internal views/modals +
12 internal helpers = ~19 total, down from ~21 in the prior version.

## Findings

### 1. DB contract specification is cross-partition but not scope creep

**Severity: INFO**

The proposal now prescribes 5 specific function signatures for
`daemon.db`:

- `create_submission(...) -> int`
- `update_submission_refs(conn, submission_id, *, queue_message_id, queue_channel_id, thread_id) -> None`
- `transition_submission_status(conn, submission_id, from_status, to_status, **kwargs) -> bool`
- `load_active_submission_ids(conn) -> list[int]`
- `has_active_submission(conn, applicant_id, chapter_slug) -> bool`

This is more prescriptive about another module than the prior version,
but it reduces scope for `applications.py` itself (no raw SQL). The
contracts are consumer-side specifications, not implementations. They
describe what the applications module needs, not how db.py should build
it. This is appropriate for a design-only proposal.

### 2. `withdrawn` status still absent from the review state machine

**Severity: LOW**

Carried forward from the prior assessment. The `submissions` table
schema in `docs/DAEMON_DESIGN.md` lists six statuses including
`withdrawn`. The proposal's state machine still covers only five. The
prior recommendation to add a one-line anti-scope note acknowledging
the omission was not picked up.

This remains low severity. `withdrawn` is an applicant action, not a
staff review action, so excluding it from `ApplicationReviewView` is
correct. The risk is only that a future implementer reads the omission
as accidental.

**Recommendation**: Same as prior — add a brief note in anti-scope or
the state machine section acknowledging that `withdrawn` exists in the
schema but is not handled by this module's review flow.

### 3. New helpers are proportionate to the problems they solve

**Severity: INFO**

Three helpers were added relative to the prior version:

- `_evict_expired_sessions(now)` — bounds abandoned draft state
- `_user_has_officer_role(...)` — defense-in-depth authorization check
- `_edit_decided_queue_message(...)` — cleanup on terminal decisions

Each serves a single, well-bounded purpose identified by the audit or
shortcut reviews. None introduces new flow branches, new public API, or
new external dependencies. The overall helper count decreased because
three prior helpers (`_get_blacklist_entry`,
`_insert_submission_and_get_id`, `_transition_submission_status`) were
removed in favor of direct db.py contract calls.

### 4. Anti-scope section remains comprehensive

**Severity: INFO**

The 10 anti-scope exclusions are unchanged. The new revision content
(authorization checks, session TTL, queue message cleanup, DB contracts)
all fall within the existing scope boundary — they are tightenings of
already-described behavior, not expansions into excluded territory.

### 5. Revision content traces cleanly to audit/shortcut findings

**Severity: INFO**

The "Risk Revisions" section at the bottom of the proposal lists six
changes. Each traces to a specific MEDIUM finding from the audit or
shortcut reviews:

- `invitable=False` → thread privacy audit finding
- officer role checks → authorization shortcut finding
- db.py contracts → SQL boundary audit finding
- duplicate submission guard → applicant flow shortcut finding
- session TTL → abandoned state shortcut finding
- queue message cleanup → terminal state shortcut finding

No revision content appears to be self-generated scope expansion. All
additions are responsive to identified risks.
