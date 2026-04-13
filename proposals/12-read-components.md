# Proposal: Read Command Component Serialization

Date: 2026-04-13

## Goal

Extend `serialize_message()` in `discord_cli.py` so the `read` command
includes message components alongside the existing content, attachment,
and embed serialization.

This proposal is design only. It does not include implementation code.

## Summary

The change should stay entirely inside the existing serialization layer:

- add a `"components"` key to `serialize_message()`
- preserve top-level component order from `message.components`
- serialize `ActionRow` containers with a `"children"` list
- fully serialize `Button` and `SelectMenu` children
- serialize `PartialEmoji` helper objects
- use a minimal fallback for all other component classes
- emit `"components": []` when a message has no components

No command wiring, parser changes, or Discord mutation behavior is
needed.

## Architecture

### `serialize_message()`

Extend the existing helper:

```python
def serialize_message(message: Any) -> dict[str, Any]:
    ...
```

New behavior:

- add `"components"` to the returned payload
- source data from `getattr(message, "components", [])`
- always emit a list, never omit the key

Recommended addition inside the returned dict:

```python
"components": [serialize_component(item) for item in getattr(message, "components", [])],
```

### New helper functions

Add a small serializer stack beside the existing message/embed helpers.

Primary dispatcher:

```python
def serialize_component(component: Any) -> dict[str, Any]:
    ...
```

Recommended dispatch behavior:

- `discord.ActionRow` -> `serialize_action_row`
- `discord.Button` -> `serialize_button`
- `discord.SelectMenu` -> `serialize_select_menu`
- anything else -> `serialize_component_fallback`

Concrete helpers:

```python
def serialize_action_row(component: discord.ActionRow) -> dict[str, Any]:
    ...

def serialize_button(component: discord.Button) -> dict[str, Any]:
    ...

def serialize_select_menu(component: discord.SelectMenu) -> dict[str, Any]:
    ...

def serialize_select_option(option: discord.SelectOption) -> dict[str, Any]:
    ...

def serialize_select_default_value(value: discord.SelectDefaultValue) -> dict[str, Any]:
    ...

def serialize_partial_emoji(emoji: discord.PartialEmoji | None) -> dict[str, Any] | None:
    ...

def serialize_component_fallback(component: Any) -> dict[str, Any]:
    ...
```

### Data flow

The serializer path should be:

1. `serialize_message()` reads `message.components`
2. each top-level entry is passed to `serialize_component()`
3. `ActionRow` entries serialize their `children` with the same dispatcher
4. `Button` and `SelectMenu` emit full structured payloads
5. unsupported component classes emit a minimal fallback payload

This keeps the change local to read-message serialization and reuses the
same helper-oriented pattern already used for attachments and embeds.

## Serialization Schema

### Top-level message shape

`serialize_message()` should gain one new key:

```json
{
  "id": 123,
  "created_at": "2026-04-13T01:02:03+00:00",
  "edited_at": null,
  "author": {},
  "content": "hello",
  "attachments": [],
  "embeds": [],
  "components": [],
  "pinned": false,
  "tts": false,
  "type": "default",
  "jump_url": "https://discord.com/channels/..."
}
```

When a message has no components, `"components"` must be `[]`.

### ActionRow

Exact shape:

```json
{
  "type": "action_row",
  "id": 111,
  "children": []
}
```

Field rules:

- `type`: string name from `component.type`, expected `"action_row"`
- `id`: integer or `null`
- `children`: ordered list of serialized child components

Use `"children"` rather than `"components"` inside rows so the payload
matches the read-only `discord.py` object model and does not collide
with the top-level message key.

### Button

Exact shape:

```json
{
  "type": "button",
  "id": 222,
  "custom_id": "ticket:create_general",
  "label": "General Support",
  "style": "primary",
  "emoji": {
    "name": "🎫",
    "id": null,
    "animated": false
  },
  "disabled": false,
  "url": null,
  "sku_id": null
}
```

Field rules:

- `type`: string name from `component.type`, always `"button"`
- `id`: integer or `null`
- `custom_id`: string or `null`
- `label`: string or `null`
- `style`: string enum name from `component.style`
- `emoji`: serialized `PartialEmoji` object or `null`
- `disabled`: boolean
- `url`: string or `null`
- `sku_id`: integer or `null`

Link buttons should have `style: "link"` and typically `custom_id: null`
with `url` populated.

Premium buttons should surface `sku_id` when present.

### SelectMenu

Exact shape:

```json
{
  "type": "string_select",
  "id": 333,
  "custom_id": "ticket:type",
  "placeholder": "Choose a ticket type",
  "min_values": 1,
  "max_values": 1,
  "disabled": false,
  "options": [],
  "channel_types": [],
  "default_values": []
}
```

Field rules:

- `type`: string name from `component.type`
- `id`: integer or `null`
- `custom_id`: string
- `placeholder`: string or `null`
- `min_values`: integer
- `max_values`: integer
- `disabled`: boolean
- `options`: ordered list of serialized select options
- `channel_types`: list of string enum names
- `default_values`: ordered list of serialized select default values

Expected `type` values include:

- `"string_select"`
- `"user_select"`
- `"role_select"`
- `"mentionable_select"`
- `"channel_select"`

`options` should be present for all selects and default to `[]`.
`channel_types` and `default_values` should also always be present and
default to `[]`.

### SelectOption

Exact shape:

```json
{
  "label": "General Support",
  "value": "general",
  "description": "Questions and troubleshooting",
  "emoji": {
    "name": "🎫",
    "id": null,
    "animated": false
  },
  "default": false
}
```

Field rules:

- `label`: string
- `value`: string
- `description`: string or `null`
- `emoji`: serialized `PartialEmoji` object or `null`
- `default`: boolean

### SelectDefaultValue

Exact shape:

```json
{
  "id": 900000000000000001,
  "type": "channel"
}
```

Field rules:

- `id`: integer
- `type`: string enum value from `SelectDefaultValue.type`

Expected `type` values:

- `"user"`
- `"role"`
- `"channel"`

### PartialEmoji

Exact shape:

```json
{
  "name": "ticket",
  "id": 123456789012345678,
  "animated": false
}
```

Field rules:

- `name`: string or `null`
- `id`: integer or `null`
- `animated`: boolean

Return `null` when the source emoji is `None`.

### Fallback for unrecognized components

Exact shape:

```json
{
  "type": "container",
  "id": 444
}
```

Field rules:

- `type`: string name from `component.type` when available, otherwise
  `safe_str(type(component).__name__)`
- `id`: integer or `null`

This fallback applies to unsupported top-level components and
unsupported `ActionRow.children` entries. It must not recurse into
Components v2 internals.

## Serialization Rules

- Preserve the order of `message.components` exactly as received.
- Preserve the order of `ActionRow.children` exactly as received.
- Preserve the order of `SelectMenu.options` and `default_values`.
- Emit JSON-safe primitives only.
- Use string enum names for `ComponentType`, `ButtonStyle`, and
  `ChannelType`.
- Emit declared keys consistently, using `null` or `[]` instead of
  omitting keys for optional structured fields.

## Anti-scope

This proposal explicitly does not include:

- any implementation changes outside the serializer helpers
- any parser, dispatch, or command registration changes
- any write or mutation behavior against Discord
- full Components v2 serialization for `Container`,
  `SectionComponent`, `TextDisplay`, `ThumbnailComponent`,
  `MediaGalleryComponent`, `FileComponent`, `SeparatorComponent`, or
  `LabelComponent`
- recursive traversal beyond the classic `ActionRow -> children` shape
- `TextInput` serialization
- modal-oriented component serialization
- the `required` field on `SelectMenu`
- conversion to `discord.ui.View` or `LayoutView`
- any backwards-compatibility shim layer

## Tradeoffs

- String enum names are more readable than raw numeric values, but they
  tie the JSON contract to discord.py's enum naming.
- Including `id` on recognized components slightly widens the payload,
  but it keeps the schema consistent with the fallback path and preserves
  useful 2.6+ metadata.
- Always emitting `options`, `channel_types`, and `default_values`
  makes consumers simpler, but it produces some empty arrays on component
  types where those fields are not meaningfully used.
- A minimal fallback avoids crashes on Components v2 payloads, but it
  intentionally drops nested structure and display metadata for those
  newer component classes.

## Decision

Proceed with a serializer-only change centered on `serialize_message()`
plus a small component helper stack. The output contract should add a
stable `"components"` list, fully cover `ActionRow`, `Button`, and
`SelectMenu`, and degrade safely to `{type, id}` for unsupported
component classes.
