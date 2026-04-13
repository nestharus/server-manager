# Scope Risk: daemon/claim.py

**Overall risk level: LOW**

The proposal defines `daemon/claim.py` as a thin async helper with
exactly two public coroutines — one additive (pre-claim) and one
narrowing (claim execution) — both operating exclusively on private-
thread membership. The boundary is well-drawn: all workflow-specific
logic (queue-message edits, SQLite mutations, authorization checks,
approval/denial/interview flows) is explicitly deferred to callers in
`daemon/applications.py` and `daemon/tickets.py`. The anti-scope
section is comprehensive and directly addresses every adjacent concern
that could tempt scope creep: role lookup, thread creation, embed
construction, database writes, channel overwrites, and policy engines.
The data model is a single immutable result object with deterministic
sorted tuples — proportionate to the problem and no more.

## Findings

### 1. Proposal correctly excludes parent-channel overwrite management

**Severity: INFO**

The research documents that private-thread visibility is a compound
property: explicit membership plus `manage_threads` bypass. The
proposal explicitly states that `daemon/claim.py` only controls explicit
membership and does not attempt to manage channel overwrites or model
the full visibility surface. The Trial Mod read-only concern is
correctly identified as a channel-provisioning problem, not a
claim-module problem. This is the right boundary.

### 2. Admin preservation scope is intentionally narrow

**Severity: INFO**

The proposal preserves only members with the guild-level `administrator`
permission bit, not every user with effective `manage_threads`. The
research confirms these are different sets. The proposal acknowledges
this distinction and documents it as a behavioral constraint rather than
trying to model the full moderator-visibility surface. This is a
deliberate, justified scoping decision — widening to `manage_threads`
would pull in channel-overwrite inspection, which belongs elsewhere.

### 3. Membership resolution adds a fetch fallback

**Severity: LOW**

`execute_claim_visibility` may call `guild.fetch_member(member_id)` for
cache misses during admin detection. This is a network call per
unresolved member. The resolution order (reuse caller objects → cache
lookup → fetch) is reasonable and minimizes API calls. For typical
thread sizes (under 20 explicit members), this is unlikely to hit rate
limits. The `unresolved_member_ids` field in the result object
correctly accounts for fetch failures without silently promoting
unknown users to admin status.

**Recommendation:** No change required. If thread sizes grow
unexpectedly large in practice, batch resolution could be considered
as a future optimization — but that is an implementation concern, not
a scope concern.

### 4. No custom exception hierarchy is the right v1 call

**Severity: INFO**

The proposal lets `discord.py` exceptions (`Forbidden`,
`HTTPException`, `NotFound`) propagate directly and uses `ValueError`
for programmer errors (e.g., passing a public thread). This avoids
premature abstraction and matches the existing codebase style in
`daemon/config.py` and `daemon/db.py`. Custom exceptions can be added
later if error-handling patterns emerge during integration.

### 5. Two-function API is proportionate to the problem

**Severity: INFO**

The research identifies two distinct membership transitions: additive
setup (pre-claim) and narrowing (claim). The proposal maps these 1:1
to two public coroutines. Combining them into one function with mode
flags would be less clear; splitting further would be premature. The
function count matches the problem shape exactly.

### 6. Design-only proposal does not specify tests

**Severity: LOW**

The proposal is explicitly design-only and does not include test
expectations. This is consistent with the proposal format used
elsewhere in the repo. Implementation should include tests for both
coroutines, particularly for idempotency guarantees, admin
preservation, bot self-preservation, and the unresolved-member path.
This is a normal implementation concern, not a scope risk.
