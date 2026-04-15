# Hookpoint Research: Component Serialization

Date: 2026-04-13

## Scope

This note maps `proposals/12-read-components.md` onto the current
implementation in `discord_cli.py` and `tests/test_discord_cli.py`. It
is hookpoint-only research: no implementation, no parser changes, no
dispatch changes.

## 1. `serialize_message()` hookpoint

`serialize_message()` lives at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:187).

Current returned keys, from lines 188-199:

- `id`
- `created_at`
- `edited_at`
- `author`
- `content`
- `attachments`
- `embeds`
- `pinned`
- `tts`
- `type`
- `jump_url`

It currently does not return `components`.

Only two live call sites consume this serializer:

- `fetch_read()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:428), where `"messages"` is built from `serialize_message(message)` on line 442.
- `fetch_bot_activity()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:446), where `"samples"` is built from `serialize_message(message)` on line 499.

That means the proposed change stays local to the serializer layer and
automatically reaches both `read` output and `bot-activity` samples.

## 2. Helper insertion point

To match the existing ordering convention, the new component helpers
should be inserted between:

- `serialize_embed()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:179)
- `serialize_message()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:187)

Exact insertion window: after line 184 and before line 187.

Why this is the right spot:

- `serialize_author()`, `serialize_attachment()`, and `serialize_embed()`
  are leaf serializers that appear before the aggregate
  `serialize_message()`.
- The component serializers are the same kind of message-local leaf/helper
  stack and should sit beside attachments/embeds rather than below
  `serialize_message()`.
- No later serializer depends on components directly.

Recommended block placement:

1. New component leaf/helpers
2. `serialize_component(...)` dispatcher
3. `serialize_message(...)`

The exact internal order of the new helpers is flexible, but the whole
block belongs above `serialize_message()`.

## 3. Reusable helpers and existing patterns

### Reusable helpers

- `safe_str()` already exists at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:108).
- `iso_or_none()` already exists at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:104).

`iso_or_none()` is not directly needed for the proposal as written, but
`safe_str()` is the obvious existing helper to review for enum/string
normalization.

### `safe_str()` correctness

`safe_str()` currently does only this:

```python
if value is None:
    return None
return str(value)
```

In the repo's `discord.py` 2.7.1 virtualenv, that is not uniformly
correct for the proposal's enum requirements:

- `ChannelType` is fine because it overrides `__str__` to return
  `self.name` at
  `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/enums.py`
  lines 230-231.
- `ButtonStyle` is not fine: it has no `__str__` override at the class
  definition on lines 706-723, so `str(discord.ButtonStyle.primary)`
  yields `ButtonStyle.primary`, not `primary`.
- `ComponentType` is not fine: it has no `__str__` override at the class
  definition on lines 678-703, so `str(discord.ComponentType.action_row)`
  yields `ComponentType.action_row`, not `action_row`.

Conclusion: `safe_str()` exists, but it does not by itself satisfy the
proposal's bare-name requirement for `ButtonStyle` and `ComponentType`.
It is only correct for `ChannelType` among the three enums called out in
the proposal.

Adjacent note: `SelectDefaultValue.type` uses `SelectDefaultValueType`,
which also has no `__str__` override in this environment, so the same
issue applies there.

### Existing serializer patterns to follow

The current serializer style is consistent across:

- `serialize_author()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:135)
- `serialize_attachment()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:169)
- `serialize_embed()` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:179)

Patterns worth following:

- Return a plain dict literal, not a custom object.
- Use direct attribute access for required fields like `id`.
- Use `getattr(..., None)` for optional fields.
- Normalize booleans with `bool(...)` where the output contract wants a
  strict JSON boolean.
- Normalize special values through a tiny helper (`safe_str`,
  `iso_or_none`) instead of inline branching.
- Aggregate nested values with list comprehensions inside the parent
  serializer, e.g. `attachments` and `embeds` inside `serialize_message()`.

The component helper stack should follow the same pattern: one helper per
shape, small dict literals, and list comprehensions at the parent level.

## 4. Existing emoji/component overlap

There is no existing component serializer in `discord_cli.py`.

Search results found no implementation references in `discord_cli.py` to:

- `emoji`
- `PartialEmoji`
- `ActionRow`
- `Button`
- `SelectMenu`
- `SelectOption`
- `SelectDefaultValue`
- `ComponentType`

There is also no existing `serialize_partial_emoji()` or similar helper.

So emoji serialization is net-new and has no overlap with an existing
helper in this file.

## 5. Required imports

No new explicit imports are required in `discord_cli.py` if the
implementation follows the repo's current style.

Reasons:

- The file already uses module-qualified Discord types everywhere via
  `import discord` at [discord_cli.py](/home/nes/discord/worktrees/feat-components/discord_cli.py:14).
- Existing annotations already use `discord.Guild`,
  `discord.TextChannel`, `discord.Thread`, etc. without any direct
  `from discord import ...` imports.
- In the repo's virtualenv, `discord.py` re-exports component classes at
  `/home/nes/discord/.venv/lib/python3.14/site-packages/discord/__init__.py`
  line 69 via `from .components import *`.
- `pyproject.toml` declares `discord.py>=2.3` at
  [pyproject.toml](/home/nes/discord/worktrees/feat-components/pyproject.toml:7),
  and the linked virtualenv is on 2.7.1.

So `discord.ActionRow`, `discord.Button`, `discord.SelectMenu`,
`discord.SelectOption`, `discord.SelectDefaultValue`,
`discord.PartialEmoji`, `discord.ButtonStyle`, `discord.ComponentType`,
and `discord.ChannelType` can all be referenced without adding import
statements.

The same applies in tests: `tests/test_discord_cli.py` already imports
`discord_cli`, so tests can reference `discord_cli.discord.<Type>` if
they need concrete specs or enum values.

## 6. Test hookpoints

The best insertion point for new component-serialization tests is in the
existing `read` section, between:

- `test_read_handler_returns_message_content_with_author_info()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:533)
- `test_integrations_handler_returns_type_and_enabled_status()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:553)

That keeps the new tests beside the feature they extend instead of
placing them down in the generic utility or gateway sections.

### Existing test patterns

Patterns already used in this file:

- Handler-level tests call `require_public_handler(...)` and execute the
  coroutine through `run(...)`.
- Fixtures provide a mocked guild graph through `guild_fixture`.
- Mock objects are built with `Mock`, `MagicMock`, and `AsyncMock`.
- Async history streams use `async_iter(...)`.
- Output assertions usually check exact fields on returned dicts, not raw
  JSON strings.

### Existing helpers available

Available helpers near the top of the file:

- `run()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:12)
- `async_iter()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:16)
- `require_public_handler()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:24)
- `make_member()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:34)
- `make_activity_author()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:80)
- `make_activity_message()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:90)
- `guild_fixture()` at [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:156)

What is missing:

- There is no existing component-specific mock builder.
- There are no direct serializer unit tests for `serialize_author`,
  `serialize_attachment`, `serialize_embed`, or `serialize_message`.

So the component tests will likely be the first serializer-focused tests
in this file. If a reusable component mock helper is added later, it
should live with the other test builders in the top helper block
(roughly lines 34-148).

### Existing test overlap

Two existing test groups already depend indirectly on `serialize_message()`:

- `bot-activity` sample assertions at
  [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:730)
  and [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:856)
- `read` handler output at
  [tests/test_discord_cli.py](/home/nes/discord/worktrees/feat-components/tests/test_discord_cli.py:533)

Because the current implementation uses `getattr(message, "components", [])`,
existing tests that build message mocks without a `components` attribute
should continue to work once the new key is added.

## 7. Conflicts, overlap, and deletions

Conflicts/overlap to account for:

- `safe_str()` overlaps with the proposal's enum-string need, but is not
  sufficient for `ButtonStyle` and `ComponentType`.
- `serialize_message()` is the only serializer hookpoint that must grow;
  `fetch_read()` and `fetch_bot_activity()` should remain unchanged.
- No existing emoji/component helper conflicts with the proposed
  `serialize_partial_emoji()` or component serializers.

What to delete:

- Nothing. There is no obsolete component serializer, no parser wiring to
  remove, and no command registration to replace.

What stays parallel/local:

- Implementation work is confined to the serializer block in
  `discord_cli.py`.
- Test work is confined to new cases in the `read` section of
  `tests/test_discord_cli.py`.
- Parser, command specs, and gateway dispatch are out of scope.
