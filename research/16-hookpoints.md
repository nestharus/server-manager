# Hookpoint Research: `daemon/claim.py`

Date: 2026-04-13

## Scope

This note maps [proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:1)
onto the current repository.

It is hookpoint-only research for `daemon/claim.py`:

- what already exists and is reusable
- where the first real insertion points are
- what can proceed in parallel
- what current boundaries should not be collapsed

This document does not include implementation code.

## 1. What already exists and is reusable

### Existing package slot and import shape

The package/layout decision is already made:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:10)
  already reserves `daemon/claim.py` in the daemon file layout.
- [daemon/__init__.py](/home/nes/discord/daemon/__init__.py:7)
  already lists `claim` as a planned daemon submodule.
- [tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:7)
  already treats `"claim"` as one of the expected daemon submodule
  names.

That is reusable directly. `daemon/claim.py` does not need a packaging
change, a new top-level location, or any package-root re-export.
[tests/test_daemon_init.py](/home/nes/discord/tests/test_daemon_init.py:59)
already establishes that `daemon.__init__` should not become a public
API surface.

### The design doc already splits claim into setup and narrowing

The current daemon design already contains the two workflow moments that
the proposal turns into the public API:

- queue setup adds the requester plus every handler-role member to the
  private thread
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:46),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:47))
- claim removes everyone except the claimer, requester, and admins from
  that same private thread
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:48),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:49))

That maps cleanly onto the proposal's two coroutines:

- `ensure_preclaim_visibility(...)`
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:85))
- `execute_claim_visibility(...)`
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:109))

This is the strongest existing reuse point. The repo already describes
one shared claim lifecycle for both applications and tickets; the
proposal is extracting the membership part of that lifecycle into a
single helper boundary.

### The database already models the state that callers own

The proposal says `daemon/claim.py` must not write SQLite state and that
callers own `status` and `claimer_id`
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:25),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:129),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:229)).

That fits the current schema directly. Both workflow tables already
carry the queue/thread/claimer fields that surround a claim transition:

- `submissions.status`, `queue_message_id`, `queue_channel_id`,
  `thread_id`, `claimer_id`
  ([daemon/db.py](/home/nes/discord/daemon/db.py:29),
  [daemon/db.py](/home/nes/discord/daemon/db.py:39))
- `tickets.status`, `queue_message_id`, `queue_channel_id`, `thread_id`,
  `claimer_id`
  ([daemon/db.py](/home/nes/discord/daemon/db.py:46),
  [daemon/db.py](/home/nes/discord/daemon/db.py:56))

This is reusable because it confirms the separation of concerns:

- `claim.py` reconciles explicit thread membership
- `applications.py` and `tickets.py` persist claimed state around it

`claim.py` does not need to know table names or SQL details.

### The config model already holds the inputs that claim.py should not derive

[daemon/config.py](/home/nes/discord/daemon/config.py:54) already
defines `ChapterConfig` with the queue-channel and role IDs that future
callers will use to decide who the handlers are:

- `officer_role_id`
- `applications_channel_id`
- `tickets_channel_id`
- `incidents_channel_id`

The proposal explicitly says the claim helper should accept explicit
participants from the caller rather than deriving them from roles,
ticket types, or chapter config
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:46),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:99),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:226)).

That means the reuse boundary is already visible:

- config and workflow code decide which members belong in the thread
- `claim.py` receives concrete snowflakes and a `discord.Thread`

### Existing daemon support modules provide a style baseline

The strongest local module-style references are
[daemon/config.py](/home/nes/discord/daemon/config.py:1) and
[daemon/db.py](/home/nes/discord/daemon/db.py:1):

- module docstring first, then `from __future__ import annotations`
- frozen dataclasses for typed return/config objects
  ([daemon/config.py](/home/nes/discord/daemon/config.py:48),
  [daemon/db.py](/home/nes/discord/daemon/db.py:74))
- explicit function entry points with explicit arguments rather than a
  hidden singleton runtime
  ([daemon/config.py](/home/nes/discord/daemon/config.py:117),
  [daemon/db.py](/home/nes/discord/daemon/db.py:79))

That is reusable for the proposal's `ClaimVisibilityResult`
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:59)).
The local pattern supports a small typed helper module with one result
dataclass and a few focused functions.

## 2. Existing boundaries `claim.py` must fit

### The daemon owns claim workflow; the CLI does not

The current architecture already puts claim behavior on the daemon side:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:193)
  says `discord_cli.py` remains the one-shot inspection/admin
  interface.
- The same section says the daemon handles interactions while the CLI
  handles administrative one-shots
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:194),
  [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:196)).

The live CLI implementation matches that split:

- command dispatch is currently a map of guild-read handlers
  ([discord_cli.py](/home/nes/discord/discord_cli.py:629))
- every command runs through the one-shot gateway path
  ([discord_cli.py](/home/nes/discord/discord_cli.py:642),
  [discord_cli.py](/home/nes/discord/discord_cli.py:650))
- parser wiring only builds inspection commands today
  ([discord_cli.py](/home/nes/discord/discord_cli.py:655))

So the real consumers of `claim.py` are future daemon modules, not
`discord_cli.py`.

### The proposal intentionally narrows the older "threads + channels" wording

There is one documented wording mismatch that matters:

- [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:14)
  describes `claim.py` as "shared claim-visibility logic (threads +
  channels)"
- the proposal narrows v1 to private-thread membership only and pushes
  channel overwrites, queue-message edits, and policy lookup out of
  scope
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:31),
  [proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:136),
  [proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:186),
  [proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:224))

The proposal should be treated as the more precise contract. It matches
the design's own statement that Trial Mod read-only is a parent-channel
concern, not a thread-membership concern
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:54),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:181)).

### Claim.py sits between Discord thread objects and caller-owned policy/state

The proposal's anti-scope is already consistent with the current repo:

- callers provide an already-created `discord.Thread`
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:42))
- callers decide authorization and queue-message edits
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:127))
- callers write SQLite state
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:129))

That keeps three layers separate:

- config chooses channels and roles
- workflow modules choose whether a claim is allowed and what state
  transitions happen
- `claim.py` only reconciles explicit private-thread membership

This boundary should not be collapsed.

## 3. First concrete insertion points

### Pre-claim setup belongs immediately after thread creation

The first concrete hookpoint is the moment after a queue item exists and
its private thread has been created:

1. create queue message
2. create private thread
3. resolve handler members from config/roles
4. call `ensure_preclaim_visibility(...)`

That is exactly the handoff between the design's step 4 and step 5
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:46),
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:47)).

The future callers are already named by the proposal:

- `daemon/applications.py`
- `daemon/tickets.py`
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:17))

### Claim execution belongs after authorization and before state mutation

The second concrete hookpoint is the moment when a handler presses
Claim:

1. workflow code verifies the acting user may claim
2. workflow code resolves the requester and claimer objects/IDs
3. workflow code calls `execute_claim_visibility(...)`
4. only after success does workflow code edit the queue message and
   persist `status`/`claimer_id`

That ordering is already implied by the proposal's caller
responsibilities
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:125)).
It is also the cleanest fit with the existing DB schema, where claimed
state is stored outside the helper
([daemon/db.py](/home/nes/discord/daemon/db.py:35),
[daemon/db.py](/home/nes/discord/daemon/db.py:52)).

### The membership-resolution work lives entirely inside claim.py

There is no existing local helper for "thread member IDs to guild
members". The proposal's resolution order is therefore a real module
responsibility, not a reusable helper from elsewhere:

- reuse supplied `discord.Member` requester/claimer objects when
  possible
- check `thread.guild.get_member(...)`
- fall back to `await thread.guild.fetch_member(...)`
  ([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:146))

That logic belongs inside `claim.py` because it is part of the helper's
admin-preservation contract, not part of config or DB.

### Daemon startup must honor the proposal's `Intents.members` prerequisite

The proposal assumes `Intents.members`
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:209)).
There is no live daemon entry point yet, but the current CLI already has
the nearest local analogue:

- [discord_cli.py](/home/nes/discord/discord_cli.py:67) enables
  `guilds`, `members`, and `message_content`

That is not a direct code hookpoint for `claim.py`, but it is an
existing pattern that future `daemon.py` startup must preserve. The
prerequisite belongs in daemon boot/runtime wiring, not inside the claim
helper.

## 4. Reusable patterns to carry forward

### Keep the public API explicit and keyword-oriented

`daemon/db.py` uses explicit helper signatures with keyword-only
workflow inputs
([daemon/db.py](/home/nes/discord/daemon/db.py:111),
[daemon/db.py](/home/nes/discord/daemon/db.py:178),
[daemon/db.py](/home/nes/discord/daemon/db.py:249)).

The proposal follows the same shape for `requester`, `handler_members`,
and `claimer`
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:85),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:109)).

That is the right local pattern. `claim.py` should take the exact
thread and participants it needs, not a larger workflow context object.

### Prefer a typed immutable result instead of ad-hoc dicts

The existing daemon support modules already use frozen dataclasses for
stable typed objects
([daemon/config.py](/home/nes/discord/daemon/config.py:48),
[daemon/db.py](/home/nes/discord/daemon/db.py:74)).

That makes `ClaimVisibilityResult` the natural local pattern, especially
because the proposal wants deterministic sorted tuples for logging and
tests
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:71)).

### Reuse fail-fast validation, but not the CLI exception model

Local code already favors explicit guard clauses and early validation:

- config validation fails as soon as an input contract is violated
  ([daemon/config.py](/home/nes/discord/daemon/config.py:130))
- CLI handlers reject bad arguments before doing work
  ([discord_cli.py](/home/nes/discord/discord_cli.py:538),
  [discord_cli.py](/home/nes/discord/discord_cli.py:556))

That is reusable for checks like "thread must be private". But the
proposal explicitly rejects a custom exception hierarchy for
`claim.py` and says `discord.py` operational errors should surface
directly while programmer misuse should fail with `ValueError`
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:194)).

So the reusable part is the guard-clause style, not the CLI's
`CLIError` wrapper.

## 5. Parallel work boundaries

### Claim.py can be implemented in parallel with workflow modules

The proposal is deliberately narrow enough that `claim.py` can be built
independently of the rest of the daemon, as long as the signatures and
result object stay fixed:

- `claim.py` needs a `discord.Thread` and explicit participants
- it does not need config lookup
- it does not need SQLite writes
- it does not need queue-message edit logic

That is exactly the separation stated in the proposal
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:36),
[proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:237)).

### DB claim transitions are separate work

Current `daemon/db.py` has creation and lookup helpers, but no helper
yet for transitioning `submissions` or `tickets` into a claimed state
([daemon/db.py](/home/nes/discord/daemon/db.py:178),
[daemon/db.py](/home/nes/discord/daemon/db.py:245),
[daemon/db.py](/home/nes/discord/daemon/db.py:249),
[daemon/db.py](/home/nes/discord/daemon/db.py:316)).

That means claim-related DB update helpers can proceed in parallel.
`claim.py` does not need to wait for them because its contract stops at
membership reconciliation.

### Handler-member selection is separate work

Because the proposal forbids role/config lookup inside the helper
([proposals/16-claim.md](/home/nes/discord/proposals/16-claim.md:46)),
the caller-side work of mapping queue type or chapter config to
`handler_members` can also proceed independently inside
`applications.py` and `tickets.py`.

## 6. Current gaps and tensions to keep visible

### The hookpoints are architectural today, not call sites in live workflow code

There is still no live `daemon/applications.py` or `daemon/tickets.py`
implementation in the repo. So the main hookpoints identified here are
documented architecture seams, not existing call sites ready for a
one-line patch.

That is normal at this stage, but it means the proposal is defining the
contract before the consumers exist.

### The design doc wording should not pull channel-policy work back into claim.py

The main risk in the current docs is the broader `claim.py` wording in
[docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:14).
If that wording is followed literally, the helper could drift into
channel overwrite policy, queue-message editing, or other workflow
logic.

The proposal's narrower contract is better aligned with the current
config, DB, and daemon/CLI split. That narrower boundary should be kept.
