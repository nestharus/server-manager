# Shortcut Risk: daemon/claim.py

**Overall risk level: LOW**

The proposal is deliberately narrow and honest about its boundaries. Every
major gap identified in the research is either addressed in the design rules
or explicitly placed in anti-scope with stated rationale. The module avoids
owning policy, persistence, or message-editing concerns that belong to
callers. The few findings below are minor underspecifications and one
deferred tension that the proposal acknowledges but does not flag for
upstream correction.

## Findings

### 1. Concurrent claims are not addressed (MEDIUM)

Two handlers can press "Claim" simultaneously on the same queue message.
The proposal defines `execute_claim_visibility` as a sequence of
`fetch_members` → add claimer/requester → remove others, with no mention of
locking, compare-and-swap, or idempotency guards against a second caller
interleaving the same sequence. Since the proposal explicitly delegates
authorization ("decide whether the acting user is allowed to claim") to the
caller, concurrency protection would also need to live in the caller. But
the proposal does not flag this as a caller responsibility or document the
expected behavior when two claims race.

**Severity:** MEDIUM — the window is small (button press → REST calls), but
the consequence is real: two claimers could each remove the other's
membership, leaving the thread in a state matching neither claim. The
`ClaimVisibilityResult` would faithfully report what happened in each call,
but the combined effect would be inconsistent.

**Recommendation:** Add a sentence to the caller-responsibilities section
of `execute_claim_visibility` stating that the caller must serialize or
gate concurrent claims (e.g., check-and-set on `status` in SQLite before
invoking the helper).

### 2. Partial failure leaves thread in an intermediate state (LOW)

`execute_claim_visibility` performs multiple `remove_user` calls in
sequence. If one call raises `discord.Forbidden` or `discord.HTTPException`
mid-way, the thread is left with some members removed and others still
present. The proposal says discord.py exceptions surface directly to the
caller, which is correct for v1, but neither the result object nor the
caller-responsibilities section addresses recovery from a half-completed
claim.

**Severity:** LOW — Discord REST failures on individual member removal are
rare in practice, and the idempotency of the helper means re-calling it
would finish the job. The main risk is a caller that catches the exception,
marks the claim as complete in SQLite, and moves on with stale membership.

**Recommendation:** Add a note that callers should not persist claim
success until the helper returns without exception, or should treat
exceptions as "claim incomplete, retry or revert."

### 3. DAEMON_DESIGN.md SEND_MESSAGES tension not flagged (LOW)

The research identifies a factual conflict: DAEMON_DESIGN.md describes
Trial Mod read-only as denying `SEND_MESSAGES` on the parent channel, but
Discord actually controls thread posting via `SEND_MESSAGES_IN_THREADS`.
The proposal correctly scopes this out of `claim.py` (it is a
channel-provisioning concern), but does not flag the upstream design
document for correction.

**Severity:** LOW — `claim.py` is not affected because it does not touch
parent-channel overwrites. The conflict lives in DAEMON_DESIGN.md and
will surface when `tickets.py` provisions `#mod-tickets`.

**Recommendation:** File this as a known issue against DAEMON_DESIGN.md so
it is corrected before `tickets.py` implements the Trial Mod overwrite.

### 4. `invitable` flag assumption undocumented (LOW)

The research documents that `Thread.add_user` on a private thread with
`invitable=False` requires the bot to have `manage_messages` in addition to
`send_messages_in_threads`. The proposal's operational-assumptions section
says the bot has "the Discord permissions required to add and remove users
from the target private thread" but does not call out the `invitable`
dependency specifically.

**Severity:** LOW — the assumption is covered by the generic permission
statement, and the bot will likely have `manage_messages` anyway. A
`discord.Forbidden` at runtime would surface the issue clearly.

**Recommendation:** Add `invitable` to the operational-assumptions section
as a specific note: if private threads are created with `invitable=False`,
the bot needs `manage_messages` on the parent channel.

### 5. manage_threads users removed but still see the thread (LOW)

The proposal preserves only members with `guild_permissions.administrator`
and documents that users with effective `manage_threads` can still see a
private thread after explicit removal. This is not a shortcut — the
"Explicit Membership Vs Effective Visibility" section is transparent about
it. The minor gap is that callers might assume the `removed_member_ids`
list means those users lost visibility, when in practice some of them
retain read access through `manage_threads`.

**Severity:** LOW — the proposal already documents this distinction. The
affected set (non-admin moderators) is small in the Humility server, and
the claim flow's purpose is membership-list hygiene rather than
cryptographic exclusion.

**Recommendation:** None required. The existing documentation is adequate.
