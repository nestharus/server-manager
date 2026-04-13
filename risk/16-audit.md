# Audit Risk Assessment: daemon/claim.py

## Overall: LOW

The proposal defines a thin async helper module with two public
coroutines that reconcile explicit private-thread membership. It
introduces no database writes, no authorization decisions, no channel
overwrites, and no policy logic. The design is intentionally narrow and
documents its own visibility limitations. All identified findings are
low severity — most stem from inherent Discord platform constraints
rather than design flaws.

## Findings

### Finding 1: Membership removal does not guarantee visibility removal
- Severity: LOW
- Description: Removing a user from a private thread only removes
  explicit membership. Users who retain effective `manage_threads` on the
  parent channel can still see and interact with the thread. The proposal
  explicitly acknowledges this (proposal §Explicit Membership Vs
  Effective Visibility, lines 166–179) and states "claimed does not mean
  cryptographically exclusive." This is the single largest visibility gap
  in the design, but it is a Discord platform constraint, not a fixable
  design defect. The research confirms this from both official Discord
  docs and discord.py docs.
- Recommendation: No action required in the module. Callers that need
  stronger isolation (e.g., confidential tickets) should be aware that
  `manage_threads` holders remain effective viewers. The proposal already
  mandates documenting this distinction in the module docstring.

### Finding 2: TOCTOU window between fetch and mutate
- Severity: LOW
- Description: Both coroutines fetch the current thread-member list via
  `fetch_members()` and then perform add/remove operations. Between the
  fetch and the mutations, another actor (bot, admin, or Discord itself)
  could add a user to the thread. This is a time-of-check-to-time-of-use
  gap. In practice, the window is milliseconds for a single async
  coroutine and the impact is that one extra member could remain after a
  claim. The result object's `member_ids_after` reflects what the
  coroutine computed, not a post-mutation re-fetch, so callers see the
  intended state rather than the true final state.
- Recommendation: Acceptable for v1. If claim precision becomes critical,
  a post-mutation `fetch_members()` re-check could be added later. The
  result object already has the shape to report this (`member_ids_after`
  vs a hypothetical `verified_ids_after`).

### Finding 3: Partial failure leaves thread in intermediate state
- Severity: LOW
- Description: The proposal lets discord.py operational errors
  (`Forbidden`, `HTTPException`, `NotFound`) surface directly without
  retry or rollback. If `remove_user` succeeds for three of five members
  and fails on the fourth, the thread is left in a partially narrowed
  state — some handlers removed, some still present. There is no
  transactional guarantee over multiple Discord API calls.
- Recommendation: Acceptable for v1. Discord API calls are inherently
  non-transactional. Callers can catch the exception and inspect the
  thread state to decide whether to retry or alert. Adding per-member
  error collection would increase complexity without clear v1 value.

### Finding 4: Unresolved members may include admins who get removed
- Severity: LOW
- Description: When `execute_claim_visibility` cannot resolve a
  thread-member ID back to a guild member (guild cache miss and
  `fetch_member` raises `NotFound`), the member is classified as
  unresolved and is removable unless they are the bot, requester, or
  claimer. If a legitimate admin left the guild or the cache/API call
  fails transiently, that admin loses explicit thread membership. The
  proposal tracks this in `unresolved_member_ids` for caller visibility.
- Recommendation: No action required. An admin who left the guild is no
  longer a guild member and should not be retained as one. Transient API
  failures are covered by Finding 3. The `unresolved_member_ids` field
  gives callers full audit visibility.

### Finding 5: fetch_member calls may hit rate limits on large threads
- Severity: LOW
- Description: `execute_claim_visibility` calls
  `guild.fetch_member(member_id)` for each thread member not resolvable
  from cache or supplied arguments. If a thread has many members with
  cold caches, this produces one HTTP request per unresolved member.
  Discord's per-route rate limits could slow or fail the operation. The
  proposal's three-step resolution order (reuse supplied objects → cache
  → fetch) mitigates this for the common case where requester/claimer
  are pre-supplied and most handlers are cached.
- Recommendation: Acceptable for v1. Handler threads in this design
  typically contain fewer than 20 explicit members (one role's worth),
  so the fetch count stays well within rate limits. If thread sizes
  grow, batch resolution could be added.

### Finding 6: No authorization in the module — caller must enforce
- Severity: LOW
- Description: The proposal explicitly places authorization ("who may
  press Claim") in anti-scope. This is architecturally correct — the
  helper is a membership primitive, not a policy engine. However, if a
  caller invokes `execute_claim_visibility` without first checking
  authorization, any user who can trigger the code path could narrow a
  thread. The design depends on `daemon/applications.py` and
  `daemon/tickets.py` implementing proper authorization before calling
  the helper.
- Recommendation: No action required in claim.py. The anti-scope
  section and caller-responsibilities lists are clear. Callers should
  validate that the acting user has the right to claim before invoking
  the helper.

### Finding 7: Bot self-removal protection is explicit
- Severity: LOW
- Description: The proposal mandates that the bot user is never removed
  from the thread. This prevents the bot from losing the ability to
  manage the thread post-claim. The design rule is stated in both the
  Design Rules section and the execute_claim_visibility responsibilities.
- Recommendation: No action required. The rule is unambiguous.

### Finding 8: ValueError for public threads is correct fail-fast
- Severity: LOW
- Description: Passing a public thread triggers a `ValueError`. This is
  a programmer-error guard, not a user-facing exception. Public threads
  have fundamentally different visibility semantics — they are visible to
  everyone with parent-channel access — so silently proceeding would be
  worse than failing. The research confirms that private-thread
  membership is the only valid claim primitive.
- Recommendation: No action required.

### Finding 9: Result object determinism supports auditability
- Severity: LOW
- Description: The `ClaimVisibilityResult` uses sorted tuples for all ID
  fields, making log output and test assertions deterministic. The
  `unresolved_member_ids` field provides explicit visibility into
  resolution failures. This supports both debugging and post-incident
  review.
- Recommendation: No action required. The design is audit-friendly.

### Finding 10: Idempotency claims are well-founded
- Severity: LOW
- Description: Pre-claim setup is additive (only adds, never removes)
  and idempotent (re-adding an existing member is a no-op in Discord).
  Claim execution is narrowing and idempotent (re-running on an
  already-claimed thread finds no extra members to remove). Both
  properties hold because the operations are based on set reconciliation
  against the current membership snapshot.
- Recommendation: No action required.
