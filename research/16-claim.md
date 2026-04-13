# Research: `daemon/claim.py` Shared Claim-Visibility Helper

Date: 2026-04-13

## Scope

This note documents the current problem space for the planned
`daemon/claim.py` module.

It is limited to:

- what the repo currently says "claim" does for tickets and applications
- what `discord.py` exposes for thread member management and message edits
- how Discord private-thread visibility actually works
- what parent-channel permissions still matter after thread membership changes
- what admin and moderator detection surfaces exist in `discord.py`

It does not propose an implementation.

## Local Baseline

- The daemon design names [daemon/claim.py](/home/nes/discord/docs/DAEMON_DESIGN.md:14)
  as the shared home for "claim-visibility logic".
- The design is built around private threads off queue messages, with
  "private-thread membership" called out as the claim primitive
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:25)).
- The per-item flow is shared by tickets and applications:
  create queue message, create private thread, add requester plus handler
  members, then claim by removing everyone except claimer, requester, and
  admins while also marking the queue message as claimed
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:41)).
- The design also has a special moderator-ticket rule where `Trial Mod`
  is intended to be read-only on those private threads
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:54)).
- The SQLite schema already reserves the persistent state needed for a
  claim flow:
  - `submissions.status`, `submissions.thread_id`,
    `submissions.queue_message_id`, and `submissions.claimer_id`
    ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:121),
    [daemon/db.py](/home/nes/discord/daemon/db.py:29))
  - `tickets.status`, `tickets.thread_id`, `tickets.queue_message_id`,
    and `tickets.claimer_id`
    ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:135),
    [daemon/db.py](/home/nes/discord/daemon/db.py:46))
- Existing daemon modules use explicit typing, small helper functions,
  frozen dataclasses where they fit, and direct stdlib/library APIs
  rather than heavy framework abstractions
  ([daemon/config.py](/home/nes/discord/daemon/config.py:48),
  [daemon/db.py](/home/nes/discord/daemon/db.py:74)).
- The local environment currently resolves `discord.py 2.7.1`, while the
  project dependency floor is `discord.py>=2.3`
  ([pyproject.toml](/home/nes/discord/pyproject.toml:6)).

## Primary Sources

- Local repo files:
  - [AGENTS.md](/home/nes/discord/AGENTS.md:1)
  - [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:1)
  - [daemon/__init__.py](/home/nes/discord/daemon/__init__.py:1)
  - [daemon/config.py](/home/nes/discord/daemon/config.py:1)
  - [daemon/db.py](/home/nes/discord/daemon/db.py:1)
- Official `discord.py` docs:
  - https://discordpy.readthedocs.io/en/latest/api.html
  - https://discordpy.readthedocs.io/en/latest/migrating.html
- Official Discord docs:
  - https://docs.discord.com/developers/topics/threads
  - https://docs.discord.com/developers/topics/permissions
- Local runtime inspection:
  - `uv run python` with `discord.py 2.7.1`
  - `inspect.signature()` / `inspect.getdoc()` on
    `discord.Thread.add_user`, `discord.Thread.remove_user`,
    `discord.Thread.permissions_for`, `discord.Thread.fetch_members`,
    `discord.Thread.is_private`, `discord.Member.guild_permissions`,
    and `discord.Message.edit`

## 1. What "claim" means in the current repo

The daemon design defines claim as a shared workflow across both queue
types, not as a tickets-only feature:

- queue item is created
- private thread is created from the queue message
- requester and handler-role members are added to that thread
- a Claim button exists on the queue message
- pressing Claim changes who can see the thread
- pressing Claim also changes what the queue message says

From the local design and schema, claim has at least three distinct
effects:

1. a thread-membership effect
2. a queue-message presentation effect
3. a persistent state effect

The thread-membership effect is explicit in the design step that says
claim removes everyone except the claimer, requester, and admins from
the thread ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:49)).

The queue-message effect is also explicit: the queue message is marked
"Claimed by @X"
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:49)).

The persistent-state effect is implied by the schema already carrying
`status` and `claimer_id` for both `submissions` and `tickets`
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:121),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:135)).

## 2. Discord private-thread visibility is membership plus moderator bypass

Discord’s thread docs and `discord.py` agree on the core model:

- threads inherit most permissions from their parent channel
- private threads are not generally visible just because the parent
  channel is visible
- a private thread is visible to users who were added to it
- a private thread is also visible to moderators with
  `MANAGE_THREADS`

Discord’s official thread docs describe private threads as guild-local
group-DM-like spaces and say a user must be invited to the thread to
view or participate in it, unless they are a moderator with
`MANAGE_THREADS`
(https://docs.discord.com/developers/topics/threads).

`discord.py` exposes the same rule on `Thread.is_private`: a private
thread is only viewable by users explicitly invited or by users with
`Permissions.manage_threads`
(https://discordpy.readthedocs.io/en/latest/api.html#discord.Thread.is_private).

The important consequence for this repo’s claim flow is that removing a
user from a private thread only removes ordinary explicit membership.
It does not, by itself, hide the thread from anyone who still has
effective `manage_threads` on the parent channel.

This makes "visible only to claimer + requester + admins" a compound
visibility statement, not merely "membership list equals those users".

## 3. Parent-channel permissions still control thread behavior

Discord’s permission docs say threads do not have their own overwrite
system; they inherit from the parent channel, with some thread-specific
rules layered on top
(https://docs.discord.com/developers/topics/permissions,
https://docs.discord.com/developers/topics/threads).

`discord.py` exposes that model directly through
`Thread.permissions_for(obj)`, whose docs say thread permissions are
"mostly" inherited from the parent channel, with implicit changes
(https://discordpy.readthedocs.io/en/latest/api.html#discord.Thread.permissions_for).

Relevant thread-specific permission facts from the official docs:

- `CREATE_PUBLIC_THREADS`, `CREATE_PRIVATE_THREADS`, and
  `SEND_MESSAGES_IN_THREADS` are thread-specific permission bits.
- `SEND_MESSAGES` does not control the ability to talk in a thread.
- `SEND_MESSAGES_IN_THREADS` is the permission that controls thread
  posting.
- `MANAGE_THREADS` allows deleting and archiving threads, and viewing
  all private threads.

The migration note in `discord.py` v2 also states that a guild member
can send messages in a private thread only when all of the following are
true:

- they have `send_messages_in_threads` in the parent channel
- they are already a member of the thread or have `manage_threads` in
  the parent channel
- the thread is not locked

This matters directly to the design’s Trial Mod note. The current design
describes Trial Mod read-only behavior in terms of denying
`SEND_MESSAGES` on the parent channel
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:56)).
The official Discord and `discord.py` docs instead describe thread
posting in terms of `SEND_MESSAGES_IN_THREADS`, not `SEND_MESSAGES`.

That is a factual constraint in the current problem statement.

## 4. `discord.py` thread member management API surface

The main `discord.py` APIs relevant to claim visibility are:

- `discord.Thread.add_user(user)`
- `discord.Thread.remove_user(user)`
- `discord.Thread.fetch_members()`
- `discord.Thread.members`

### `Thread.add_user`

In `discord.py 2.7.1`, `Thread.add_user(user)` is a coroutine that adds a
user to the thread.

Its docs say:

- `send_messages_in_threads` is required to add a user
- if the thread is private and `invitable` is `False`,
  `manage_messages` is additionally required
- it raises `Forbidden` on missing permission
- it raises `HTTPException` on request failure

The `invitable` flag is only meaningful for private threads.
`discord.py` documents it as whether non-moderators can add other
non-moderators to that private thread
(https://discordpy.readthedocs.io/en/latest/api.html#discord.Thread.invitable).

### `Thread.remove_user`

In `discord.py 2.7.1`, `Thread.remove_user(user)` is a coroutine that
removes a user from the thread.

Its docs say:

- `manage_threads` or thread ownership is required
- it raises `Forbidden` on missing permission
- it raises `HTTPException` on request failure

This permission requirement is different from `add_user`.

### Inspecting thread members

`Thread.members` and `Thread.fetch_members()` are not equivalent.

`discord.py` documents that:

- `Thread.members` depends on `Intents.members`
- most of the time the gateway does not fully provide this member list
- `fetch_members()` is often needed to retrieve the actual thread-member
  list
- `fetch_members()` needs `Intents.members` to get data about members
  other than the current bot user

This matters because the claim problem is not just mutation. It also
includes knowing who is presently in the thread before and after the
claim transition.

## 5. Message editing is part of claim, not a side detail

The design says the queue message itself changes on claim
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:49)).

In `discord.py`, `Message.edit(...)` is the concrete edit surface for
that operation. In the installed `2.7.1` runtime:

- it is a coroutine
- it edits message content, embed(s), attachments, and/or view
- it returns the edited `Message`

Since the queue message also carries buttons
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:48)),
claim is not only a thread-member update. It is also a queue-message
state update on a message that may have content, embeds, and a view.

## 6. Admin detection in `discord.py`: guild-level and channel-level surfaces differ

There are at least three relevant permission surfaces in `discord.py`:

- `member.guild_permissions`
- `role.permissions`
- `thread.permissions_for(member)` or `parent.permissions_for(member)`

`Member.guild_permissions`:

- returns guild-level permissions
- includes guild ownership
- includes administrator implication
- does not include channel overwrites

`Permissions.administrator` is documented as bypassing all
channel-specific overrides.

`Role.permissions` exposes the permissions granted by that role, so
`role.permissions.administrator` is the role-level way to detect whether
a role itself confers administrator.

This creates an important distinction inside the claim problem:

- "administrator" is one Discord permission bit
- "can still see a private thread after removal" also includes members
  with effective `manage_threads`

Those are not identical sets.

## 7. Gateway and sync behavior relevant to claim visibility

Discord’s thread docs include a few gateway facts that matter to any
shared claim helper:

- the gateway only syncs active threads the current user can view
- adding a user to a private thread sends a `THREAD_CREATE` event so the
  client gains that thread in memory
- thread membership is tracked explicitly in thread-member objects
- `THREAD_MEMBERS_UPDATE` is the gateway event for users being added to
  or removed from a thread
- seeing other users’ thread-member updates requires the
  `GUILD_MEMBERS` intent at the Discord API level; `discord.py` maps
  that to `Intents.members`

Related `discord.py` event surfaces exist as:

- `on_thread_member_join`
- `on_thread_member_remove`
- `on_raw_thread_member_remove`

and those docs also require `Intents.members`.

This means claim visibility is partly a REST-mutation problem and partly
an in-memory/cache-accuracy problem.

## 8. Problem-space summary specific to `claim.py`

From the sources above, the shared claim helper sits at the intersection
of five concrete concerns:

1. Thread membership mutation for ordinary users via
   `Thread.add_user` / `Thread.remove_user`.
2. Effective visibility rules for private threads, which depend on both
   membership and parent-channel moderator permissions.
3. Effective write/read capability in the claimed thread, which still
   depends on parent-channel permissions such as
   `send_messages_in_threads` and `manage_threads`.
4. Queue-message mutation via `Message.edit(...)`, because claim changes
   the visible queue state as well as the thread state.
5. Persistent ticket/submission state, because both schema tables
   already model a claimed state and store `claimer_id`.

The current design also carries two source-backed tensions that are part
of the problem space:

- membership removal alone does not hide a private thread from users who
  retain effective `manage_threads`
- the Trial Mod read-only note currently talks about `SEND_MESSAGES`,
  while the official thread docs say thread posting is controlled by
  `SEND_MESSAGES_IN_THREADS`

Those are constraints to account for when reasoning about
`daemon/claim.py`; they are not implementation proposals.
