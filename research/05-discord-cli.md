# Discord CLI Problem Research

Date: 2026-04-12

## Scope

This document describes the problem space for a one-shot Discord guild inspection CLI around `discord.py`. It does not propose an implementation. The focus is:

- which `discord.py` APIs exist for each requested subcommand
- which gateway intents and Discord permissions those APIs depend on
- which model objects those APIs return
- which documented failure modes matter
- what object/serialization constraints shape JSON output

## Evidence Baseline

- Project dependency target: `discord.py>=2.3` in `pyproject.toml`.
- Runtime API surface inspected via `uv run python` in this repo resolves `discord.py` `2.7.1`.
- Primary sources:
  - `discord.py` API reference: https://discordpy.readthedocs.io/en/latest/api.html
  - Discord Gateway docs: https://docs.discord.com/developers/events/gateway
  - Discord Gateway Events docs: https://docs.discord.com/developers/events/gateway-events
  - Discord rate limit docs: https://docs.discord.com/developers/topics/rate-limits
  - Discord status/error code docs: https://docs.discord.com/developers/topics/opcodes-and-status-codes

## Cross-Cutting Findings

### Lifecycle and one-shot session behavior

- `discord.Client.start(token, *, reconnect=True)` is documented as a shorthand for `login()` plus `connect()`.
- `discord.Client.connect(*, reconnect=True)` creates the websocket connection and runs the event system until the websocket terminates.
- `discord.Client.close()` closes the connection to Discord.
- `discord.Client.run(...)` is the blocking convenience entrypoint; the docs explicitly say to use `start()` or `connect()` plus `login()` instead when more event-loop control is needed.
- `on_ready()` is documented as:
  - called after the client has prepared data from Discord and `Client.guilds` is usually filled
  - not guaranteed to be the first event
  - not guaranteed to be called only once, because reconnect/resume failures can trigger it again

Research implication: any one-shot CLI pattern that performs work from `on_ready()` must treat it as a readiness signal with reconnect caveats, not as a guaranteed single-fire callback.

### Model objects are rich Python objects, not JSON

The relevant source objects are `discord.Guild`, `discord.Member`, `discord.Role`, `discord.Integration`, channel model classes such as `discord.TextChannel` and `discord.Thread`, and `discord.Message`.

These are not plain dicts. Their documented attributes include Python objects such as:

- aware `datetime` values like `Guild.created_at` and `Member.joined_at`
- nested model references like `Integration.user`, `Integration.account`, `Role.permissions`
- sequences of model objects like `Guild.channels`, `Guild.roles`, `Guild.members`

Research implication: downstream JSON cannot be a direct dump of returned `discord.py` models. The problem is a flattening/serialization problem before it is a CLI formatting problem.

### Intents vs HTTP/API calls

The docs distinguish between:

- cache- and event-shaping gateway intents such as `Intents.guilds`, `Intents.members`, `Intents.integrations`, and `Intents.message_content`
- HTTP/API coroutine calls such as `Guild.fetch_channels()`, `Guild.fetch_member()`, `Guild.integrations()`, and `abc.Messageable.history()`

Important documented split:

- `Intents.guilds` populates guild/channel/thread/role cache and guild-related events.
- `Intents.members` populates member-related cache and member events, and Discord treats it as a privileged intent.
- `Intents.integrations` controls integration-related gateway events only; the `Guild.integrations()` fetch method itself is documented in terms of permission (`manage_guild`), not intent.
- `Intents.message_content` affects what message content fields are present in gateway events such as `on_message()` and `on_message_edit()`. The `history()` docs only document `read_message_history` permission, not `message_content` intent.

Inference from paired docs: the gathered sources do not establish `Intents.message_content` as a requirement for `abc.Messageable.history()`. They do establish it for message-content-bearing gateway events.

### Common documented failure modes

`discord.py` exceptions:

- `discord.LoginFailure`: login failed because of bad credentials or another login failure.
- `discord.HTTPException`: HTTP request failed.
- `discord.Forbidden`: HTTP 403.
- `discord.NotFound`: HTTP 404.
- `discord.DiscordServerError`: HTTP 5xx.
- `discord.GatewayNotFound`: gateway could not be found.
- `discord.ConnectionClosed`: gateway closed for reasons the library could not handle internally.
- `discord.PrivilegedIntentsRequired`: privileged intents requested but not enabled in the Developer Portal.

Discord close/status/rate-limit docs:

- Gateway close `4004`: authentication failed.
- Gateway close `4008`: rate limited.
- Gateway close `4013`: invalid intent(s).
- Gateway close `4014`: disallowed intent(s).
- HTTP `401`: missing/invalid authorization.
- HTTP `403`: token lacks permission to the resource.
- HTTP `404`: resource does not exist.
- HTTP `429`: rate limited.
- HTTP `502`: gateway unavailable; retry later.
- Global bot HTTP rate limit: 50 requests per second.
- Invalid-request limit / temporary Cloudflare restriction: 10,000 invalid requests per 10 minutes, counting `401`, `403`, and `429`.

Discord resource-specific JSON error codes relevant here include:

- `10003` unknown channel
- `10004` unknown guild
- `10005` unknown integration
- `10007` unknown member
- `10008` unknown message

### Permission resolution

Channel visibility and message access are not implied by simply having a channel object:

- `abc.GuildChannel.permissions_for(member_or_role)` returns a `Permissions` object.
- The channel docs explicitly note that receiving an `abc.GuildChannel` does not mean the client can communicate in it.
- `Permissions.view_channel` is the alias for `read_messages`.
- `Permissions.read_message_history` indicates whether previous messages can be read.
- `Permissions.manage_guild` is the guild-level permission documented for listing integrations.

## Subcommand Research

## `overview`

### Relevant `discord.py` APIs

- `discord.Client.guilds` -> documented property of guilds the connected client belongs to.
- `discord.Client.get_guild(id)` -> cached lookup, returns a guild by ID.
- `discord.Guild` documented attributes directly relevant to overview:
  - `id`
  - `name`
  - `owner_id`
  - `channels`
  - `roles`
  - `member_count`
  - `created_at`
  - `unavailable`
- `discord.Guild.fetch_member(member_id)` -> documented HTTP/API coroutine returning `Member`.

Runtime signatures observed in this repo:

- `Guild.fetch_member(self, member_id: int, /) -> Member`

### Required intents and permissions

- `Intents.guilds`:
  - documented as the intent that fills `Client.guilds`, `Guild` objects, and guild channel/thread cache
  - effectively the base intent for cached guild overview data
- `Intents.members`:
  - not required just to have a `Guild`
  - documented as necessary for member cache features such as `Guild.members`, `Guild.get_member()`, and member attribute cache
  - `Guild.member_count` docs warn that keeping it accurate requires `Intents.members`

Research implication: an overview that depends on cached owner/member state or accurate live `member_count` inherits the `members` intent problem; a narrower overview using only guild metadata does not.

### Returned data structures

- `Guild` represents a Discord guild.
- `Guild.channels` -> `Sequence[abc.GuildChannel]`
- `Guild.roles` -> roles in hierarchy order
- `Guild.member_count` -> optional count, with documented accuracy caveat
- `Guild.fetch_member()` -> `Member`

### Error modes

- `Client.get_guild(id)` is cache-based and can return no guild if the guild is not present in cache yet.
- `Guild.unavailable == True` is documented to mean the reliability of most other attributes is slim and they may be `None`; the docs say it is best not to do anything with the guild if it is unavailable.
- `Guild.fetch_member()` raises:
  - `Forbidden`
  - `NotFound`
  - `HTTPException`

### JSON-shaping constraints

- The source object already separates stable identifiers from display fields:
  - guild: `id`, `name`
  - owner: `owner_id` or fetched `Member.id`
- Timestamps like `created_at` are `datetime`.
- Counts such as `member_count`, `len(channels)`, and `len(roles)` are scalar-friendly, but they summarize model sequences rather than replacing them.

## `bots`

### Relevant `discord.py` APIs

- `discord.Guild.members` -> `Sequence[Member]`
- `discord.Member.bot` -> documented property equivalent to `User.bot`
- `discord.Guild.fetch_members(*, limit=1000, after=...)` -> async iterator for guild members

Observed runtime signature:

- `Guild.fetch_members(...) -> AsyncIterator[Member]`

### Required intents and permissions

- `Intents.members` is the key documented dependency:
  - `Intents.members` corresponds to `Guild.members`, `Guild.fetch_members()`, `Guild.get_member()`, and member cache fields like `Member.roles` and `Member.nick`
  - Discord treats this as a privileged intent
- Discord gateway docs for Request Guild Members say `GUILD_MEMBERS` intent is required to request the entire member list.

Research implication: full bot enumeration is a member-list problem, not a guild-metadata problem.

### Returned data structures

- `Guild.members` -> `Sequence[Member]`
- `Member` attributes directly relevant to bot enumeration:
  - `bot`
  - `nick`
  - `joined_at`
  - `roles`
  - `guild_permissions`

### Error modes

- Without `Intents.members`, cached guild member data may be incomplete or unavailable.
- `Guild.fetch_members()` is documented as potentially slow when asked to retrieve all members.
- Discord gateway docs document rate limits for Request Guild Members and a `Rate Limited` gateway event for opcode 8.
- If privileged intents are requested but not enabled, `discord.py` can raise `PrivilegedIntentsRequired`, and Discord gateway close `4014` documents disallowed intents.

### JSON-shaping constraints

- The key discriminator for this subcommand already exists as `Member.bot`.
- Member objects contain nested and ordered structures (`roles`, permission objects), not just scalars.
- Names are not unique. `Member.id` is the stable identity field; `nick`, handle, and global name are presentation fields.

## `channels`

### Relevant `discord.py` APIs

- `discord.Guild.channels` -> `Sequence[abc.GuildChannel]`
- `discord.Guild.text_channels` -> `List[TextChannel]`
- `discord.Guild.voice_channels` -> `List[VoiceChannel]`
- `discord.Guild.categories` -> `List[CategoryChannel]`
- `discord.Guild.threads` -> list of viewable threads
- `discord.Guild.by_category()` -> `List[Tuple[Optional[CategoryChannel], List[abc.GuildChannel]]]`
- `discord.Guild.fetch_channels()` -> HTTP/API coroutine returning `Sequence[abc.GuildChannel]`
- `discord.Guild.active_threads()` -> HTTP/API coroutine returning `List[Thread]`

Observed runtime signatures:

- `Guild.fetch_channels(self) -> Sequence[GuildChannel]`
- `Guild.by_category(self) -> List[ByCategoryItem]`

### Required intents and permissions

- `Intents.guilds`:
  - documented as the intent covering guild/channel/thread events and guild cache
  - docs explicitly tie guild/channel/thread cache population to this intent
- Channel visibility still depends on channel permissions; the docs note that having a channel object does not itself guarantee communication or access.

### Returned data structures

- `Guild.channels` returns guild channels only.
- `Guild.threads` is separate and documented as threads the client has permission to view.
- `Guild.get_channel(channel_id)` is ID-based and explicitly does not search threads.
- `Guild.get_channel_or_thread(channel_id)` searches both channels and threads and returns `Optional[Union[Thread, abc.GuildChannel]]`.
- `Client.fetch_channel(channel_id)` can return `abc.GuildChannel`, `abc.PrivateChannel`, or `Thread`.

Research implication: “channels” and “threads” are separate first-class collections in `discord.py`.

### Error modes

- `Guild.fetch_channels()` raises:
  - `InvalidData` if Discord returns an unknown channel type
  - `HTTPException`
- `Guild.threads` is permission-filtered by viewability.
- `Guild.unavailable` makes other guild attributes unreliable, which includes channel access through the guild object.

### JSON-shaping constraints

- Channel output cannot be type-free if downstream consumers need to distinguish:
  - text channel
  - voice channel
  - category
  - thread
- Parent/ordering context exists in the source API:
  - `by_category()` groups by category
  - `threads` are not embedded in `channels`
- Permission context is external to the channel object shape and comes from `permissions_for(...)`.

## `find-channel`

### Relevant `discord.py` APIs

The gathered API surface exposes:

- collection properties:
  - `Guild.channels`
  - `Guild.text_channels`
  - `Guild.voice_channels`
  - `Guild.categories`
  - `Guild.threads`
- ID-based lookups:
  - `Guild.get_channel(channel_id)`
  - `Guild.get_channel_or_thread(channel_id)`
  - `Guild.fetch_channel(channel_id)`
  - `Client.fetch_channel(channel_id)`

There is no documented `Guild` helper in the gathered sources that looks up a channel by name directly.

Research implication: name-based discovery is a collection-inspection problem over cached/fetched channel and thread objects, not a dedicated single API call problem.

### Required intents and permissions

- `Intents.guilds` for cached channel/thread collections.
- No additional gateway intent is documented for channel metadata lookup itself.
- Visibility still depends on `view_channel`-resolved permissions.

### Returned data structures

- Cached lookup by ID:
  - `Guild.get_channel()` -> `Optional[abc.GuildChannel]`
  - `Guild.get_channel_or_thread()` -> `Optional[Union[Thread, abc.GuildChannel]]`
- HTTP lookup by ID:
  - `Guild.fetch_channel()` -> guild channel or thread
  - `Client.fetch_channel()` -> guild channel, private channel, or thread

### Error modes

- Name is not a documented unique key in the API surface.
- Threads live outside `Guild.channels`, so any name-based scan that only inspects `Guild.channels` would omit them.
- Permission-filtered visibility means a channel can exist in the guild but still be absent from the viewable set.
- ID-based HTTP fetches can raise `Forbidden`, `NotFound`, and `HTTPException` depending on route and resource visibility.

### JSON-shaping constraints

- A name-only result is ambiguous because names are not the stable identity in the API; IDs are.
- The source API naturally carries context needed to disambiguate:
  - type
  - category/parent grouping
  - thread vs non-thread

## `read`

### Relevant `discord.py` APIs

- `discord.abc.Messageable.history(*, limit=100, before=None, after=None, around=None, oldest_first=None)` -> async iterator of `Message`
- Channels/objects in the docs that implement `history()` include `TextChannel`, `Thread`, `VoiceChannel`, `StageChannel`, `DMChannel`, `GroupChannel`, `Member`, `User`, and `PartialMessageable`
- For guild inspection, channel resolution APIs relevant before calling `history()` are:
  - `Guild.get_channel_or_thread(channel_id)`
  - `Guild.fetch_channel(channel_id)`
  - `Client.fetch_channel(channel_id)`
- `abc.GuildChannel.permissions_for(member_or_role)` -> `Permissions`

Observed runtime signatures:

- `abc.Messageable.history(self, *, limit=100, before=None, after=None, around=None, oldest_first=None) -> AsyncIterator[Message]`
- `abc.GuildChannel.permissions_for(self, obj: Union[Member, Role], /) -> Permissions`

### Required intents and permissions

- Documented permission requirement for `history()`: `read_message_history`
- Related documented permission for visibility checks: `view_channel`
- `Intents.message_content`:
  - documented as affecting gateway event payload fields for `on_message`, `on_message_edit`, `on_message_delete`, and `on_raw_message_edit`
  - not documented in the gathered `history()` docs as a requirement for reading message history

Inference from docs: the official sources gathered define `history()` primarily as a permission-gated HTTP/API read of message history, not as a gateway message-event consumer.

### Returned data structures

- `history()` yields `Message`
- `Message` is a rich model object, not a dict
- Ordering and pagination are part of the API surface:
  - `limit`
  - `before`
  - `after`
  - `around`
  - `oldest_first`

Documented behavior details:

- `limit=None` retrieves every message and is documented as slow
- `around` has a maximum effective limit of 101
- naive datetimes are assumed to be local time

### Error modes

- `history()` raises:
  - `Forbidden` when the caller lacks permission to get message history
  - `HTTPException` when the request fails
- Missing channel/message resources can also surface as Discord HTTP `404` / JSON codes such as `10003` unknown channel and `10008` unknown message on related fetches.
- Permission problems are two-layered:
  - channel visibility (`view_channel`)
  - ability to read older messages (`read_message_history`)

### JSON-shaping constraints

- Output is inherently record-oriented because `history()` yields one `Message` at a time.
- The API surface already distinguishes pagination/window controls (`before`, `after`, `around`) from message payload fields; downstream consumers may need both the message list and the query window that produced it.
- Message objects contain nested objects and non-JSON-native values, so flattening is required before emission.

## `integrations`

### Relevant `discord.py` APIs

- `discord.Guild.integrations()` -> documented coroutine returning `List[Integration]`

Observed runtime signature:

- `Guild.integrations(self) -> List[Integration]`

### Required intents and permissions

- Documented permission requirement: `Permissions.manage_guild`
- `Intents.integrations` is documented for integration-related gateway events:
  - `on_guild_integrations_update`
  - `on_integration_create`
  - `on_integration_update`
  - `on_raw_integration_delete`

Research implication: the fetch problem and the event problem are distinct here. The docs tie `Guild.integrations()` to `manage_guild`, not to `Intents.integrations`.

### Returned data structures

- `Integration` represents a guild integration.
- Documented attributes directly relevant to inspection:
  - `type` -> integration type string
  - `enabled` -> boolean
  - `account` -> `IntegrationAccount`
  - `user` -> `User`
  - `guild` -> `Guild`

The gathered docs do not document a separate “broken integration” field on `discord.Integration`. The closest documented state field is `enabled`.

### Error modes

- `Guild.integrations()` raises:
  - `Forbidden` if the caller lacks permission
  - `HTTPException` if fetching fails
- Discord HTTP/JSON failures relevant here include:
  - `403`
  - `404`
  - JSON `10005` unknown integration

### JSON-shaping constraints

- Integrations are naturally nested objects:
  - integration identity/state
  - linked external account
  - creating/owning user if present
- The documented `enabled` field is an explicit state flag that downstream systems will likely need if the guild contains broken or disabled integrations.

## Subcommand-by-Subcommand JSON Constraints Summary

This is not a schema proposal. It is a summary of the source-object constraints that any downstream-friendly JSON will have to accommodate.

### `overview`

- stable guild ID and owner ID
- scalar counts derived from sequences
- UTC-aware timestamps
- guild availability state

### `bots`

- stable member ID
- explicit bot discriminator
- optional nickname/global-name presentation fields
- ordered role membership if included

### `channels`

- explicit channel/thread type discriminator
- stable channel ID
- category/parent context
- permission-derived visibility context if included

### `find-channel`

- IDs are necessary because names are not documented as unique
- multiple matches are possible in the source model
- threads require separate consideration from `Guild.channels`

### `read`

- record-oriented message list
- query-window controls (`limit`, `before`, `after`, `around`, `oldest_first`) are separate from message payload
- non-JSON-native nested message fields require flattening

### `integrations`

- integration state (`enabled`)
- integration type
- linked external account data
- creating/owning user data when present

## Bottom Line

The main research conclusions are:

- `overview` and `channels` are mostly guild-cache problems shaped by `Intents.guilds`.
- `bots` is fundamentally a privileged member-intent problem shaped by `Intents.members` and guild-member retrieval limits.
- `find-channel` is a collection-inspection problem because the gathered `discord.py` API surface is ID-oriented, not name-oriented.
- `read` is a permission-gated message-history problem centered on `abc.Messageable.history()`, with the gathered docs tying it to `read_message_history` rather than to `Intents.message_content`.
- `integrations` is a guild-permission problem centered on `Guild.integrations()` and `manage_guild`; integration gateway intent matters for events, not for the fetch itself.
- Across all subcommands, the source models are rich Python objects, so downstream JSON usefulness depends first on flattening, stable IDs, type discrimination, and timestamps.
