# Audit Risk Assessment: daemon/applications.py (Revised)

## Overall: LOW

All prior MEDIUM findings have been addressed in the revised proposal.
The two former MEDIUM items — missing `invitable=False` on private
review threads and sole reliance on Discord channel permissions for
review authorization — are now explicitly specified in the Design Rules
and supporting sections. No new risks were introduced by the revisions.

## Prior MEDIUM Findings — Resolution

### Finding 1: Private review threads now require `invitable=False`

- Prior severity: MEDIUM
- Current severity: RESOLVED
- Evidence: Design Rules specify `_create_review_thread(...)` must pass
  `invitable=False` (proposal line 51). Section 5 repeats the
  requirement with `invitable=False` in the thread creation step
  (proposal line 373). Risk Revisions section confirms this was a
  targeted fix (proposal line 688).
- Assessment: The one-parameter fix closes the thread-invitation leak.
  No residual risk.

### Finding 2: Review callbacks now require `officer_role_id` check

- Prior severity: MEDIUM
- Current severity: RESOLVED
- Evidence: Design Rules require every review callback to verify
  `interaction.user` has the chapter's `officer_role_id`, with
  ephemeral rejection and logging (proposal lines 55-57). The
  interaction flow diagram shows `officer-role guard` on all four
  review action paths (proposal lines 273-276). The Review State
  Machine section elaborates the defense-in-depth rationale (proposal
  lines 421-426). Risk Revisions section confirms this was a targeted
  fix (proposal lines 690-693).
- Assessment: The code-level guard adds cheap defense in depth without
  requiring a policy engine. No residual risk.

## Remaining LOW Findings

### Finding 3: Duplicate-submission guard now specified

- Severity: LOW (improved from prior)
- Description: The revised proposal adds `has_active_submission(conn,
  applicant_id, chapter_slug) -> bool` to the `db.py` contract
  (proposal line 224) and specifies the check in Design Rules after
  blacklist lookup and before any modal is opened (proposal lines
  42-43). This was a prior LOW finding that is now fully addressed.
- Recommendation: None. Implementation should follow the specified
  contract.

### Finding 4: Atomic status transitions now explicitly specified

- Severity: LOW (improved from prior)
- Description: The revised proposal now explicitly requires
  `transition_submission_status(...)` to perform a single atomic
  `UPDATE ... WHERE id = ? AND status IN (...)` and return `True` only
  when `cursor.rowcount == 1` (proposal lines 229-231). This was a
  prior LOW finding about an implicit pattern that is now named.
- Recommendation: None. The specified pattern is the standard
  optimistic-lock approach for SQLite.

### Finding 5: `create_submission` return value now specified

- Severity: LOW (improved from prior)
- Description: The revised proposal explicitly states
  `create_submission(...)` returns the inserted row ID via
  `cursor.lastrowid` (proposal lines 227-228). This was a prior LOW
  finding that is now addressed.
- Recommendation: None. Do not query back with `SELECT max(id)`.

### Finding 6: SQL injection risk remains structurally mitigated

- Severity: LOW
- Description: User-supplied modal answers flow into `answers_json` via
  JSON serialization, then into SQLite via parameterized queries. The
  existing `db.py` uses named-parameter style (`:param`) exclusively.
  The revised proposal further strengthens this by routing all
  submission SQL through explicit `daemon.db` helper contracts
  (proposal lines 215-234), so `applications.py` never issues raw SQL.
- Recommendation: Implementation review should verify all new SQL uses
  parameterized queries.

### Finding 7: `custom_id` forgery blocked by Discord interaction model

- Severity: LOW
- Description: Review button `custom_id`s embed the submission ID in
  plaintext (`app:claim:42`). Discord's interaction gateway only
  dispatches component interactions for buttons that actually exist on
  messages the user clicked. The `custom_id` is a routing key, not a
  bearer token. No change from prior assessment.
- Recommendation: None. The plaintext ID format is safe.

### Finding 8: Applicant session token generation unspecified

- Severity: LOW
- Description: The proposal says the modal `custom_id` should include
  "a compact opaque session token" but does not specify the generation
  method. If the token is predictable, one user could theoretically
  predict another's session token. In practice this has no exploit path
  because `MODAL_SUBMIT` interactions are sent only to the user who
  opened the modal, and sessions are keyed by `(applicant_id,
  chapter_slug)`.
- Recommendation: Use `secrets.token_urlsafe(8)` or similar. This is
  cheap and eliminates the theoretical concern.

### Finding 9: Thread visibility to `MANAGE_THREADS` holders

- Severity: LOW
- Description: Users with `MANAGE_THREADS` on the parent channel can
  see all private threads regardless of explicit membership. This is
  inherent to Discord's permission model. In Humility's case, such
  users are likely already staff. No change from prior assessment.
- Recommendation: Document as known Discord platform behavior. No code
  change needed.

### Finding 10: In-memory session state now bounded

- Severity: LOW (improved from prior)
- Description: The revised proposal specifies a 15-minute TTL for
  applicant draft sessions with lazy eviction before new session
  creation (proposal lines 61-62). This was a prior LOW finding that
  is now addressed.
- Recommendation: None. The specified TTL matches Discord's interaction
  token lifetime.

## New Risks Introduced by Revisions

None identified. The revisions are narrowly scoped to address the two
prior MEDIUM findings and clarify the `db.py` helper contracts. No new
interaction surfaces, state transitions, or authorization paths were
added.
