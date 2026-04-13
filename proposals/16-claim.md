# Proposal: `daemon/claim.py`

Date: 2026-04-13

## Goal

Define the design for `daemon/claim.py` as the shared claim-visibility
helper for the Humility Discord daemon.

This proposal is design only. It does not include implementation code.

## Summary

`daemon/claim.py` should be a small, async helper module focused on one
job: reconciling explicit membership on private queue threads.

It should support two shared operations used by both
`daemon/applications.py` and `daemon/tickets.py`:

- pre-claim setup: ensure the requester and the current handler set are
  members of the private thread
- claim execution: narrow explicit thread membership down to claimer +
  requester + explicitly present admins

The module should not own ticket/application workflow logic. Callers
should decide which handler members apply, when a claim is allowed, how
the queue message is edited, and how SQLite state is updated.

In v1, the helper should stay intentionally narrow:

- async coroutine API only
- private-thread membership only
- explicit admin preservation using
  `member.guild_permissions.administrator`
- deterministic result objects for logging and tests
- no policy lookup, no config lookup, and no database writes

## Design Rules

The helper should follow these rules.

- It operates on `discord.Thread` objects that are already created.
- It is valid only for private threads; public threads are out of scope.
- It should use `Thread.fetch_members()` as the authoritative source of
  explicit thread membership rather than `Thread.members`.
- It should accept explicit participants from the caller rather than
  deriving them from roles, ticket types, or chapter config.
- Pre-claim setup should be additive and idempotent.
- Claim execution should be narrowing and idempotent.
- Admin preservation should mean the Discord `administrator`
  permission bit, not every member who can still view the thread via
  `manage_threads`.
- The bot user should never remove itself from the thread.

## Data Model

The module should expose one small immutable result object.

### `ClaimVisibilityResult`

Fields:

- `thread_id: int`
- `member_ids_before: tuple[int, ...]`
- `member_ids_after: tuple[int, ...]`
- `added_member_ids: tuple[int, ...]`
- `removed_member_ids: tuple[int, ...]`
- `preserved_admin_ids: tuple[int, ...]`
- `unresolved_member_ids: tuple[int, ...]`

Design notes:

- the tuple contents should be sorted for deterministic logging and test
  assertions
- `unresolved_member_ids` exists because `fetch_members()` returns
  `ThreadMember` objects, so admin detection requires resolving IDs back
  to guild members
- unresolved users should still be removable unless they are the bot,
  requester, or claimer

## Public API

`daemon/claim.py` should expose exactly two public coroutines in v1.

### `async ensure_preclaim_visibility(thread: discord.Thread, *, requester: discord.abc.Snowflake, handler_members: Collection[discord.abc.Snowflake]) -> ClaimVisibilityResult`

Responsibilities:

- verify the thread is private
- fetch the current explicit thread-member IDs
- add the requester if not already present
- add each handler member if not already present
- deduplicate all inputs by user ID
- perform no removals
- return a structured diff describing what changed

Caller responsibilities:

- decide which handler members belong in the pre-claim thread
- supply those members from role/config logic
- update any queue message or database state outside this helper

Design intent:

- this is the shared setup primitive for both applications and tickets
- it remains safe to call more than once
- it does not try to prune stale members during setup

### `async execute_claim_visibility(thread: discord.Thread, *, requester: discord.abc.Snowflake, claimer: discord.abc.Snowflake) -> ClaimVisibilityResult`

Responsibilities:

- verify the thread is private
- fetch the current explicit thread-member IDs
- ensure the requester is an explicit member
- ensure the claimer is an explicit member
- resolve current explicit member IDs back to guild members when
  possible
- preserve any explicitly present members whose
  `guild_permissions.administrator` flag is true
- preserve the bot user
- remove every other explicit member from the thread
- return a structured diff describing the final member set

Caller responsibilities:

- decide whether the acting user is allowed to claim
- edit the queue message to show claimed state
- persist `status` and `claimer_id` in SQLite
- trigger any follow-on workflow such as interview, approve, deny, or
  close

Design intent:

- this is the shared claim primitive for both applications and tickets
- it narrows explicit membership only; it does not redefine parent
  channel permissions

## Membership Resolution Rules

`fetch_members()` returns `ThreadMember` entries, not full guild-member
objects. Since admin preservation depends on
`member.guild_permissions.administrator`, `execute_claim_visibility()`
should resolve each explicit thread-member ID back to a guild member.

The resolution order should be:

1. when the supplied requester or claimer object is already a
   `discord.Member`, reuse it when the ID matches
2. use `thread.guild.get_member(member_id)` for cache hits
3. fall back to `await thread.guild.fetch_member(member_id)` when needed

If a member cannot be resolved as a guild member:

- record the ID in `unresolved_member_ids`
- do not treat that user as an admin
- keep them only if they are the bot, requester, or claimer

This keeps admin preservation accurate without making the caller pass
the full current thread roster in.

## Behavioral Constraints

The helper should make these semantics explicit.

### Explicit Membership Vs Effective Visibility

`daemon/claim.py` only controls explicit private-thread membership.

That means:

- it can add or remove ordinary thread members
- it can preserve explicit admin members already in the thread
- it cannot hide the thread from users who still have effective
  `manage_threads` on the parent channel

This distinction should be documented in the module because "claimed"
does not mean "cryptographically exclusive"; it means explicit thread
membership was narrowed correctly.

### Trial Mod Read-Only

The `Trial Mod` read-only rule belongs to parent-channel overwrites on
`#mod-tickets`, not to thread membership reconciliation.

`daemon/claim.py` should not attempt to:

- inspect or edit channel overwrites
- translate `SEND_MESSAGES` vs `SEND_MESSAGES_IN_THREADS`
- implement moderator-ticket permission policy

That remains a channel provisioning concern elsewhere in the daemon.

### Error Surface

In v1, the helper should not define a custom exception hierarchy.

It should allow `discord.py` operational errors to surface directly,
including:

- `discord.Forbidden`
- `discord.HTTPException`
- `discord.NotFound`

For programmer errors such as a public thread being passed in, the
helper should fail fast with a regular `ValueError` rather than silently
trying to continue.

## Operational Assumptions

The helper assumes:

- `Intents.members` is enabled so thread-member inspection is usable
- the daemon bot has the Discord permissions required to add and remove
  users from the target private thread
- the caller already has a `discord.Thread` and the relevant user
  objects or IDs

These are runtime prerequisites, not work this module should discover or
repair for the caller.

## Anti-scope

`daemon/claim.py` should not contain:

- role lookup from chapter config, ticket type, or queue channel
- thread creation or archive/close logic
- queue-message embed, content, or button-view construction
- SQLite reads or writes for `status`, `claimer_id`, or queue refs
- authorization checks for who may press Claim
- application approval, denial, or interview workflow logic
- ticket closing or logging workflow logic
- parent-channel overwrite management
- a complete visibility policy engine for every user who can see a
  thread via moderator permissions

In particular, the overall claim flow still spans multiple modules:

- `daemon/claim.py` narrows explicit thread membership
- `daemon/applications.py` and `daemon/tickets.py` own their queue
  message edits and database mutations
- channel provisioning code owns parent-channel permission rules

## Decision

Design `daemon/claim.py` as a thin async membership-reconciliation
boundary with two public coroutines: one additive setup helper and one
narrowing claim helper. Keep it reusable across applications and
tickets, preserve explicit admins by the guild-level `administrator`
bit, and keep workflow-specific message, database, and policy logic out
of the module.
