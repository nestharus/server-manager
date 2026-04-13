# Shortcut Risk Re-Assessment: daemon/applications.py

## Overall: LOW

All four MEDIUM findings from the prior assessment have been addressed
in the revised proposal. The remaining items are minor specification
gaps that do not risk producing ad-hoc workarounds or deferred design
decisions during implementation.

## Prior MEDIUM Findings — Status

### Finding 1: Ad-hoc SQL instead of db.py helpers — RESOLVED

- Prior severity: MEDIUM
- Current severity: RESOLVED
- Resolution: The proposal now includes a dedicated "Required `db.py`
  helper contracts" section with five explicit signatures:
  `create_submission(...) -> int`,
  `update_submission_refs(...)`,
  `transition_submission_status(...) -> bool`,
  `load_active_submission_ids(...) -> list[int]`, and
  `has_active_submission(...) -> bool`. The proposal states
  "`applications.py` should never perform submission SQL directly" and
  includes contract notes specifying `cursor.lastrowid` return and
  atomic conditional `UPDATE ... WHERE status IN (...)` with
  `cursor.rowcount == 1`. The helpers appear in both the Module
  Structure and Data Flow sections with consistent signatures.

### Finding 2: No duplicate-submission guard — RESOLVED

- Prior severity: MEDIUM
- Current severity: RESOLVED
- Resolution: The Design Rules now require "duplicate-submission
  rejection happens after blacklist check and before any modal is
  opened." The interaction flow diagram shows an explicit
  "active-submission lookup from SQLite" gate with an ephemeral reject
  path. The `has_active_submission(conn, applicant_id, chapter_slug)`
  helper is specified with a contract note that it checks statuses
  `pending|claimed|interview`.

### Finding 3: In-memory sessions have no expiry or bound — RESOLVED

- Prior severity: MEDIUM
- Current severity: RESOLVED
- Resolution: The Design Rules now specify "applicant draft sessions
  use a 15-minute TTL and lazy eviction before new session creation."
  `ApplicationSessionState` includes `created_at` / `updated_at`
  fields, and the internal helpers list includes
  `_evict_expired_sessions(now)`. The error handling section reiterates
  the 15-minute TTL matching the interaction token lifetime.

### Finding 4: Post-decision queue-message cleanup not specified — RESOLVED

- Prior severity: MEDIUM
- Current severity: RESOLVED
- Resolution: The Review State Machine section now explicitly requires
  that after `approved` or `denied`, the queue message is edited to
  update the embed status/decision fields and disable all 4 review
  buttons. The internal helpers list includes
  `_edit_decided_queue_message(...)`. The message stays in place as
  the canonical reviewer-facing record.

## Prior LOW Findings — Status

### Finding 5: Guarded status transition mechanism unspecified — RESOLVED

- Prior severity: LOW
- Current severity: RESOLVED
- Resolution: The contract notes now specify that
  `transition_submission_status(...)` "must perform a single atomic
  conditional `UPDATE ... WHERE id = ? AND status IN (...)` and return
  `True` only when `cursor.rowcount == 1`." This eliminates the
  fetch-then-update TOCTOU ambiguity.

### Finding 6: Thread auto-archive duration not specified — LOW

- Severity: LOW
- Description: `TextChannel.create_thread()` requires an auto-archive
  duration from `{60, 1440, 4320, 10080}`. The revised proposal
  creates private review threads but still does not specify which
  value to use. The implementer will need to pick a value without
  guidance.
- Recommendation: Specify `auto_archive_duration=10080` (7 days) as
  the default for review threads, since applications may take days to
  process.

### Finding 7: Thread archive on approve/deny assumes bot permissions — LOW

- Severity: LOW
- Description: The interaction flow archives the review thread on
  approve and deny. The revised proposal does not list the required
  bot permissions for the applications channel
  (`VIEW_CHANNEL`, `SEND_MESSAGES`, `CREATE_PRIVATE_THREADS`,
  `MANAGE_THREADS`). If the bot lacks these, thread creation or
  archival silently fails at runtime.
- Recommendation: Add a note listing the required bot permissions for
  the applications channel, or delegate this to a startup-check
  routine.

## New Findings

No new shortcut risks were introduced by the revisions. The changes
are additive clarifications that close the prior gaps without
expanding scope or deferring new design decisions.
