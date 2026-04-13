# Research: `daemon/applications.py` Applications Subsystem

Date: 2026-04-13

## Scope

This note documents the current problem space for the planned
`daemon/applications.py` module.

It is limited to:

- what the local repo already says the applications subsystem must do
- what `discord.py 2.7.1` exposes for slash commands, modals, views,
  selects, and threads
- what the Discord platform docs say about interaction timing, modal
  limits, followup messages, and thread creation
- where the current local design and the current platform/library
  documentation materially disagree

It does not propose an implementation.

## Local Baseline

- The daemon design gives `daemon/applications.py` ownership of form
  rendering, modal handling, and submission flow
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:15)).
- The intended application flow is:
  `/apply <chapter>` -> modal -> queue message -> private review thread
  -> Claim/Interview/Approve/Deny actions
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:41)).
- The design explicitly says blacklisted users are blocked at the top of
  `/apply` with an ephemeral denial
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:77)).
- The config loader already models application forms as immutable
  dataclasses with question types `short`, `long`, `number`, `select`,
  and `multi_select`
  ([daemon/config.py](/home/nes/discord/daemon/config.py:69),
  [daemon/config.py](/home/nes/discord/daemon/config.py:78),
  [daemon/config.py](/home/nes/discord/daemon/config.py:307)).
- The config loader also precomputes form steps, but the current step
  planner groups all text/number questions into `modal` steps first and
  all select questions into `followup_selects` steps afterward. It does
  not preserve source order and does not encode an alternating sequence
  such as `modal -> followup -> modal`
  ([daemon/config.py](/home/nes/discord/daemon/config.py:89),
  [daemon/config.py](/home/nes/discord/daemon/config.py:514)).
- The local validation rules already enforce two Discord-facing limits:
  text/number `max_length <= 4000` and select-option count `<= 25`
  ([daemon/config.py](/home/nes/discord/daemon/config.py:470),
  [daemon/config.py](/home/nes/discord/daemon/config.py:480)).
- The DB layer already exposes the persistence and lookup primitives the
  subsystem would need:
  `create_submission(...)`, `get_submission_by_id(...)`, and
  `get_blacklist_entry(...)`
  ([daemon/db.py](/home/nes/discord/daemon/db.py:178),
  [daemon/db.py](/home/nes/discord/daemon/db.py:245),
  [daemon/db.py](/home/nes/discord/daemon/db.py:344)).
- The claim helper already assumes a private-thread review surface and
  uses `thread.fetch_members()`, `thread.add_user()`, and
  `thread.remove_user()`
  ([daemon/claim.py](/home/nes/discord/daemon/claim.py:40),
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:74)).
- The current daemon entry point already uses a `commands.Bot`,
  guild-scoped slash-command registration, and `tree.sync(guild=...)`
  ([daemon.py](/home/nes/discord/daemon.py:66),
  [daemon.py](/home/nes/discord/daemon.py:82)).
- The current example form has 7 questions: 5 text/number questions and
  2 select questions, matching the design doc’s stated split pressure
  ([forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:7)).

## Primary Sources

- Local repo files:
  - [AGENTS.md](/home/nes/discord/AGENTS.md:1)
  - [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:1)
  - [daemon/config.py](/home/nes/discord/daemon/config.py:1)
  - [daemon/db.py](/home/nes/discord/daemon/db.py:1)
  - [daemon/claim.py](/home/nes/discord/daemon/claim.py:1)
  - [daemon.py](/home/nes/discord/daemon.py:1)
  - [forms/dark-nemesis.yaml](/home/nes/discord/forms/dark-nemesis.yaml:1)
- Official `discord.py` docs:
  - https://discordpy.readthedocs.io/en/latest/interactions/api.html
  - https://discordpy.readthedocs.io/en/latest/api.html
  - https://discordpy.readthedocs.io/en/latest/ext/commands/api.html
- Official Discord docs:
  - https://docs.discord.com/developers/interactions/application-commands
  - https://docs.discord.com/developers/interactions/overview
  - https://docs.discord.com/developers/interactions/receiving-and-responding
  - https://docs.discord.com/developers/components/reference
  - https://docs.discord.com/developers/components/using-modal-components
  - https://docs.discord.com/developers/resources/channel
- Local runtime inspection on 2026-04-13:
  - `uv run python` resolved `discord.py 2.7.1`
  - installed source inspection in `.venv/site-packages` for
    `discord.ui.Modal`, `discord.ui.View`, `discord.ui.Select`,
    `discord.Interaction`, `discord.InteractionResponse`,
    `discord.Client.add_view`, `discord.TextChannel.create_thread`, and
    `discord.Message.create_thread`

## 1. Guild-Scoped Slash Commands

The current local daemon already uses the exact `discord.py` surfaces
relevant to `/apply <chapter>`:

- `commands.Bot` for the long-running client
- `@app_commands.guilds(guild)` for guild scoping
- `self.tree.command(...)` for slash-command registration
- `self.tree.sync(guild=guild)` for publishing the command to Discord

That is visible in
[daemon.py](/home/nes/discord/daemon.py:82).

`discord.py`’s application-command docs say:

- `app_commands.guilds(...)` associates a command with specific guilds
  instead of making it global
- `CommandTree.sync(...)` must be called for commands to appear

Discord’s application-command docs add the platform-level scope facts:

- commands can be global or guild-specific
- guild commands are only available in the specified guild
- guild commands are not available in DMs
- guild commands update instantly
- global command registration is slower, while guild commands are the
  recommended quick-testing path
- command names must be unique within scope
- Discord applies a rate limit of 200 application-command creates per
  day, per guild

Evidence:

- current local usage:
  [daemon.py](/home/nes/discord/daemon.py:82)
- `discord.py` docs for guild association and sync:
  https://discordpy.readthedocs.io/en/latest/interactions/api.html
- Discord command scope docs:
  https://docs.discord.com/developers/interactions/application-commands

## 2. Modals in `discord.py 2.7.1`

### Library surface

Local `discord.py 2.7.1` inspection shows:

- `discord.ui.Modal` title is limited to 45 characters
- `discord.ui.Modal` `custom_id` is limited to 100 characters
- `Modal.add_item(...)` raises once the modal has 5 children
- `InteractionResponse.send_modal(...)` is the interaction response API
  used to open a modal

Evidence:

- [.venv/lib/python3.14/site-packages/discord/ui/modal.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/modal.py:62>)
- [.venv/lib/python3.14/site-packages/discord/interactions.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/interactions.py:1266>)

### Platform limits

Discord’s receiving/responding docs say a modal response payload has:

- `custom_id`: 1-100 characters
- `title`: max 45 characters
- `components`: between 1 and 5 inclusive

Discord’s components reference and modal guide additionally show:

- text inputs in modals can set `max_length` up to 4000
- modal examples now include components wrapped in `Label`
- current docs show String Select and other select types inside modals,
  not only text inputs

Evidence:

- modal payload limits:
  https://docs.discord.com/developers/interactions/receiving-and-responding
- modal-components example:
  https://docs.discord.com/developers/components/using-modal-components
- component usage matrix:
  https://docs.discord.com/developers/components/reference

### Important documentation drift

Discord’s official docs are internally inconsistent on what modals can
contain:

- Interactions Overview still says the only interactive component in a
  modal is a text input
- Components Reference says String Select, User Select, Role Select,
  Mentionable Select, and Channel Select are valid in modals
- Using Modal Components includes a concrete example of a modal with a
  String Select and a Text Input
- local `discord.py 2.7.1` source also supports select components in
  modals: `Modal.to_components()` explicitly accepts `BaseSelect` and
  `TextInput`, and `discord.ui.Select.required` is documented as only
  applicable within modals

Evidence:

- outdated overview wording:
  https://docs.discord.com/developers/interactions/overview
- newer components docs:
  https://docs.discord.com/developers/components/reference
- modal example with select:
  https://docs.discord.com/developers/components/using-modal-components
- installed `discord.py` source:
  [.venv/lib/python3.14/site-packages/discord/ui/modal.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/modal.py:224>)
  and
  [.venv/lib/python3.14/site-packages/discord/ui/select.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/select.py:418>)

This matters because the local design doc still treats
`select`/`multi_select` as impossible inside modals
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:84)).

## 3. Select Menus in Views

For message-based UI, `discord.py` 2.7.1 exposes `discord.ui.Select`
inside `discord.ui.View`.

Relevant limits from the installed docs/source:

- `custom_id`: up to 100 characters
- `placeholder`: up to 150 characters
- `min_values`: 0 to 25
- `max_values`: 1 to 25
- `options`: up to 25
- `row`: 0 through 4
- `Select.values` returns the selected values

Evidence:

- [.venv/lib/python3.14/site-packages/discord/ui/select.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/select.py:418>)

Relevant `View` limits from the installed source:

- a `View` can have at most 25 children
- a `View` is arranged across 5 rows
- row width is enforced; a select consumes full width

Evidence:

- [.venv/lib/python3.14/site-packages/discord/ui/view.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/view.py:724>)

The local config loader already matches part of this platform surface:
`_require_options(...)` rejects option lists longer than 25
([daemon/config.py](/home/nes/discord/daemon/config.py:480)).

## 4. Interaction Timing, Followups, and Ephemeral UI

Discord’s interaction model imposes the main timing rules for any
application form flow:

- the initial response must be sent within 3 seconds
- the interaction token remains valid for 15 minutes
- a modal submission is its own interaction (`MODAL_SUBMIT`)
- an interaction gets only one initial response
- secondary messages use followup webhook endpoints

Evidence:

- platform interaction timing and followups:
  https://docs.discord.com/developers/interactions/receiving-and-responding
- local `discord.py` interaction docs/source:
  [.venv/lib/python3.14/site-packages/discord/interactions.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/interactions.py:398>)
  and
  [.venv/lib/python3.14/site-packages/discord/interactions.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/interactions.py:139>)

For ephemeral followups after a modal:

- Discord’s followup endpoint supports the `EPHEMERAL` message flag
- `discord.py` exposes the followup webhook as `interaction.followup`
- `discord.py`’s interaction response docs say that if an ephemeral
  message is sent with a view and the view timeout is unset, the timeout
  is forced to 15 minutes
- Discord’s followup docs say an existing message’s ephemeral state
  cannot be changed later

Evidence:

- Discord followup rules:
  https://docs.discord.com/developers/interactions/receiving-and-responding
- `discord.py` followup property and ephemeral-view timeout:
  [.venv/lib/python3.14/site-packages/discord/interactions.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/interactions.py:407>)
  and
  [.venv/lib/python3.14/site-packages/discord/interactions.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/interactions.py:1015>)

## 5. Multi-Step Flow Constraints

The design doc says forms larger than one modal can be split across
`modal -> select menus -> modal -> etc.`
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:94)).

The official interaction callback rules narrow what is actually possible:

- `MODAL` callback type is valid for command/component interactions
- `MODAL` callback type is explicitly not available for
  `MODAL_SUBMIT`
- `UPDATE_MESSAGE` and `DEFERRED_UPDATE_MESSAGE` are only valid for
  component-based interactions
- the modal submit payload only includes a `message` when the modal was
  triggered from a component

That means the documented platform behavior distinguishes between:

- `slash command -> modal`
- `modal submit -> message or defer`
- `component interaction -> modal`

It does not document `modal submit -> modal` as a valid callback.

Evidence:

- callback-type table and modal-submit payload:
  https://docs.discord.com/developers/interactions/receiving-and-responding

This is a direct factual constraint on the local design language around
`modal -> modal` chaining.

## 6. Private Threads and Review Surfaces

### Thread creation model

Discord’s channels docs say:

- starting a thread from an existing message creates a `PUBLIC_THREAD`
  or `ANNOUNCEMENT_THREAD`
- starting a thread without a message is the route for private threads

Local `discord.py 2.7.1` matches that exactly:

- `Message.create_thread(...)` says it creates a public thread from a
  message
- `TextChannel.create_thread(message=None, ...)` says `None` creates a
  private thread
- if `message` is passed to `TextChannel.create_thread(...)`, the type
  is ignored and the created thread is always public

Evidence:

- Discord channels docs:
  https://docs.discord.com/developers/resources/channel
- installed `discord.py` source:
  [.venv/lib/python3.14/site-packages/discord/message.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/message.py:1639>)
  and
  [.venv/lib/python3.14/site-packages/discord/channel.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/channel.py:916>)

This is a material mismatch with the design doc’s phrase
"private thread off that message"
([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:46)).

### Thread limits and membership rules

Discord’s channels docs and the installed `discord.py` docs/source give
the relevant thread constraints:

- thread name: 1-100 characters
- auto-archive duration: `60`, `1440`, `4320`, or `10080`
- slowmode: `0` to `21600`
- `invitable` applies only to private threads
- adding another member requires the ability to send messages in the
  thread
- removing another member requires `MANAGE_THREADS`, or thread creator
  for private threads
- listing thread members is paginated and restricted by the
  `GUILD_MEMBERS` privileged intent

Evidence:

- Discord channels docs:
  https://docs.discord.com/developers/resources/channel
- installed `discord.py` thread docs:
  [.venv/lib/python3.14/site-packages/discord/channel.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/channel.py:922>)
  and existing local usage in
  [daemon/claim.py](/home/nes/discord/daemon/claim.py:48)

## 7. Persistent Views and Review Buttons

`discord.py` documents restart-persistent component handling for views:

- `Client.add_view(view, message_id=...)` registers a view for
  persistent listening
- a persistent view must have `timeout=None`
- every dispatchable component in that view must have an explicit
  `custom_id`
- `message_id` is optional and is only used for state refresh during
  message-update events

Evidence:

- [.venv/lib/python3.14/site-packages/discord/client.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/client.py:3166>)
- [.venv/lib/python3.14/site-packages/discord/ui/view.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/view.py:678>)

Discord’s component docs add the payload-level limit that `custom_id` is
1-100 characters
(https://docs.discord.com/developers/components/reference).

That is the documented persistence surface for review buttons such as:

- `app:claim:<id>`
- `app:interview:<id>`
- `app:approve:<id>`
- `app:deny:<id>`

I did not find an equivalent documented restart-persistent registration
API for modals. The installed `discord.py` source shows
`send_modal(...)` storing the modal in the client state when sent, which
is evidence of in-process dispatch, not a documented restart-persistent
surface
([.venv/lib/python3.14/site-packages/discord/interactions.py](/home/nes/discord/.venv/lib/python3.14/site-packages/discord/interactions.py:1308)).

That last sentence is an inference from the documented/public API
surface plus the installed source.

## 8. Hard Limits Relevant to This Subsystem

- Interaction initial response deadline: 3 seconds
- Interaction token lifetime: 15 minutes
- Modal title: 45 characters
- Modal `custom_id`: 1-100 characters
- Modal component count: 1-5
- Text input max length: 4000
- Button label: 80 characters
- Button `custom_id`: 1-100 characters
- Select placeholder: 150 characters
- Select `custom_id`: 1-100 characters
- Select `min_values`: 0-25
- Select `max_values`: 1-25
- Select option count: 25
- Message-view child count: 25
- View rows: 5
- Thread name: 1-100 characters
- Thread auto-archive values: `60`, `1440`, `4320`, `10080`
- Thread slowmode max: `21600`

Evidence:

- Discord interaction docs:
  https://docs.discord.com/developers/interactions/receiving-and-responding
- Discord component docs:
  https://docs.discord.com/developers/components/reference
- Discord channels docs:
  https://docs.discord.com/developers/resources/channel
- installed `discord.py` source:
  [.venv/lib/python3.14/site-packages/discord/ui/modal.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/modal.py:84>),
  [.venv/lib/python3.14/site-packages/discord/ui/select.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/select.py:424>),
  [.venv/lib/python3.14/site-packages/discord/ui/view.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/ui/view.py:745>),
  [.venv/lib/python3.14/site-packages/discord/message.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/message.py:1658>),
  and
  [.venv/lib/python3.14/site-packages/discord/channel.py](</home/nes/discord/.venv/lib/python3.14/site-packages/discord/channel.py:922>)

## 9. Evidence-Backed Mismatches in the Current Problem Statement

These are not implementation recommendations. They are factual places
where the current local statement of the problem and the current
platform/library docs do not line up.

1. The design doc says modals are text-only and selects must be handled
   as follow-up messages
   ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:86)).
   Current Discord component docs and installed `discord.py 2.7.1`
   source both document select components in modals.

2. The design doc says forms can be split across
   `modal -> select menus -> modal -> etc.`
   ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:94)).
   Discord’s interaction callback table says `MODAL` is not available
   for `MODAL_SUBMIT`, so a modal cannot directly answer a prior modal
   submission with another modal.

3. The design doc says the subsystem creates a private thread off the
   queue message
   ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:46)).
   Discord’s channels docs and `discord.py` both say message-attached
   thread creation is public; private threads are created without a
   source message.

4. The current config step planner does not represent the ordered,
   alternating multi-step flow described in the design doc; it groups
   all modal-compatible questions first and all select questions second
   ([daemon/config.py](/home/nes/discord/daemon/config.py:514)).
