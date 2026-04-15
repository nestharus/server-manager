# Research: Message Component Serialization in `discord.py` 2.7.x

## Scope

This note documents what `discord.py` 2.7.x exposes on
`discord.Message.components` and which fields are available for
serialization. It is a facts-only research pass focused on the
read-only component objects returned by message reads.

Primary references used here:

- `discord.py` tag `v2.7.1` source:
  - [`discord/message.py`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/message.py)
  - [`discord/components.py`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py)
  - [`discord/ui/view.py`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/ui/view.py)
  - [`discord/enums.py`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/enums.py)
- Official docs:
  - [`Message`](https://discordpy.readthedocs.io/en/v2.7.1/api.html#discord.Message)
  - [`discord.ui.View.from_message`](https://discordpy.readthedocs.io/en/v2.7.1/interactions/api.html#discord.ui.View.from_message)
  - [`discord.ui.LayoutView.from_message`](https://discordpy.readthedocs.io/en/v2.7.1/interactions/api.html#discord.ui.LayoutView.from_message)

Version notes:

- `Message.components` exists in `discord.py` 2.x and is documented as
  version-added in `2.0`.
- Discord "Components v2" support was added in `2.6.0`.
- New modal component classes such as `RadioGroupComponent` and
  `CheckboxGroupComponent` were added in `2.7.0`.

## 1. What `message.components` is

In `discord.py` 2.7.x, `Message.components` is a read-only list of
component objects parsed from the message payload.

Relevant source:

- `Message` docs and attribute comment:
  [`discord/message.py#L2098-L2103`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/message.py#L2098-L2103)
- Message payload parsing:
  [`discord/message.py#L533-L537`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/message.py#L533-L537)

Small source excerpt:

```python
self.components: List[MessageComponentType] = []
for component_data in data.get('components', []):
    component = _component_factory(component_data, state)
```

Observed behavior from the source/docs:

- The attribute is always initialized as a list.
- If the message payload has no `components` key, the list stays empty.
- The docs explicitly say it is "a list of components in the message."
- The docs also note that if `Intents.message_content` is not enabled,
  `Message.components` will be empty unless the bot is mentioned or the
  message is a DM.
- The objects in this list are not `discord.ui.*` items. They are the
  read-only component classes from `discord.components`, re-exported at
  top-level as `discord.ActionRow`, `discord.Button`, etc.

`discord.ui.View.from_message()` states the same distinction directly:
message components are read-only and separate from the editable
`discord.ui` classes.

## 2. Component types and available metadata

### 2.1 Base hierarchy

All concrete message component classes inherit directly from
`discord.Component`.

Relevant source:

- Base class and exported names:
  [`discord/components.py#L103-L181`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L103-L181)
- Top-level re-export:
  [`discord/__init__.py#L69`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/__init__.py#L69)

Important hierarchy facts:

- `discord.Component` is abstract.
- `discord.ActionRow` is a container, not a base class for buttons.
- `discord.Button`, `discord.SelectMenu`, `discord.TextInput`,
  `discord.SectionComponent`, `discord.Container`, etc. all inherit
  directly from `discord.Component`.
- `discord.SelectOption` is not a `Component`; it is option data used by
  `SelectMenu`.
- `discord.SelectDefaultValue` is also not a `Component`; it is helper
  data for entity selects.

### 2.2 Type mapping

`discord.py` parses raw component payloads through `_component_factory`.

Relevant source:

- Factory mapping:
  [`discord/components.py#L1750-L1782`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L1750-L1782)
- Component type enum:
  [`discord/enums.py#L678-L700`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/enums.py#L678-L700)

The factory maps Discord numeric component types to these classes:

| Raw type | `ComponentType` | `discord.py` class |
| --- | --- | --- |
| `1` | `action_row` | `ActionRow` |
| `2` | `button` | `Button` |
| `3` | `select` / `string_select` | `SelectMenu` |
| `4` | `text_input` | `TextInput` |
| `5` | `user_select` | `SelectMenu` |
| `6` | `role_select` | `SelectMenu` |
| `7` | `mentionable_select` | `SelectMenu` |
| `8` | `channel_select` | `SelectMenu` |
| `9` | `section` | `SectionComponent` |
| `10` | `text_display` | `TextDisplay` |
| `11` | `thumbnail` | `ThumbnailComponent` |
| `12` | `media_gallery` | `MediaGalleryComponent` |
| `13` | `file` | `FileComponent` |
| `14` | `separator` | `SeparatorComponent` |
| `17` | `container` | `Container` |
| `18` | `label` | `LabelComponent` |
| `19` | `file_upload` | `FileUploadComponent` |
| `21` | `radio_group` | `RadioGroupComponent` |
| `22` | `checkbox_group` | `CheckboxGroupComponent` |
| `23` | `checkbox` | `CheckboxComponent` |

Two practical implications:

- All select-menu variants collapse into the single `SelectMenu` class.
- You must inspect `component.type` to tell string/user/role/mentionable/channel
  selects apart.

### 2.3 Classic message-panel classes

These are the classes most relevant to ticket panels and other ordinary
interactive message rows.

#### `ActionRow`

Relevant source:

- [`discord/components.py#L249-L294`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L249-L294)

Available attributes:

- `children: list[Button | SelectMenu | TextInput]`
- `id: int | None`
- `type == ComponentType.action_row`

Notable fact:

- The docstring says an action row holds "up to 5 children components in
  a row."

#### `Button`

Relevant source:

- [`discord/components.py#L297-L396`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L297-L396)
- Button styles:
  [`discord/enums.py#L706-L720`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/enums.py#L706-L720)

Available attributes:

- `style: ButtonStyle`
- `custom_id: str | None`
- `url: str | None`
- `disabled: bool`
- `label: str | None`
- `emoji: PartialEmoji | None`
- `sku_id: int | None`
- `id: int | None`
- `type == ComponentType.button`

Useful enum values for `style`:

- `primary`
- `secondary`
- `success`
- `danger`
- `link`
- `premium`

Important edge-case facts from the docs/source:

- Link buttons use `style == ButtonStyle.link`.
- For a URL button, `custom_id` is absent and `url` is populated.
- Premium buttons can carry `sku_id`.

#### `SelectMenu`

Relevant source:

- [`discord/components.py#L398-L492`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L398-L492)
- Typed payload variants:
  [`discord/types/components.py#L73-L129`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/types/components.py#L73-L129)

Available attributes:

- `type: ComponentType`
- `custom_id: str`
- `placeholder: str | None`
- `min_values: int`
- `max_values: int`
- `options: list[SelectOption]`
- `disabled: bool`
- `channel_types: list[ChannelType]`
- `default_values: list[SelectDefaultValue]`
- `required: bool`
- `id: int | None`

Important edge-case facts:

- String selects use `type == ComponentType.string_select` and may have
  `options`.
- User/role/mentionable/channel selects also use `SelectMenu`, but are
  distinguished only by `type`.
- Channel selects can carry `channel_types`.
- User/role/mentionable/channel selects can carry `default_values`.
- The typed payload comment says `required` is only for string selects in
  modals.

#### `SelectOption`

Relevant source:

- [`discord/components.py#L495-L597`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L495-L597)

Available attributes:

- `label: str`
- `value: str`
- `description: str | None`
- `emoji: PartialEmoji | None`
- `default: bool`

For serialization, this is the useful option-level metadata exposed on a
string select.

#### `TextInput`

Relevant source:

- [`discord/components.py#L600-L690`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L600-L690)

Available attributes:

- `style: TextStyle`
- `label: str | None`
- `custom_id: str`
- `placeholder: str | None`
- `value: str | None`
- `required: bool`
- `min_length: int | None`
- `max_length: int | None`
- `id: int | None`
- `type == ComponentType.text_input`

This class exists in the same read-only component model, but it is a
modal-oriented component rather than a normal ticket-panel button row.

### 2.4 Components v2 and newer classes

`discord.py` 2.6 added Components v2 support and `2.7` added additional
modal component classes.

Relevant source:

- `2.6.0` changelog:
  [`docs/whats_new.rst#L158-L170`](https://github.com/Rapptz/discord.py/blob/v2.7.1/docs/whats_new.rst#L158-L170)
- `2.7.0` changelog:
  [`docs/whats_new.rst#L34-L45`](https://github.com/Rapptz/discord.py/blob/v2.7.1/docs/whats_new.rst#L34-L45)

Message-facing v2 component classes present in `2.7.x`:

- `SectionComponent`
  - `children`
  - `accessory`
  - `id`
- `TextDisplay`
  - `content`
  - `id`
- `ThumbnailComponent`
  - `media`
  - `description`
  - `spoiler`
  - `id`
- `MediaGalleryComponent`
  - `items`
  - `id`
- `FileComponent`
  - `media`
  - `spoiler`
  - `name`
  - `size`
  - `id`
- `SeparatorComponent`
  - `spacing`
  - `visible`
  - `id`
- `Container`
  - `children`
  - `spoiler`
  - `accent_colour`
  - `id`
- `LabelComponent`
  - `label`
  - `description`
  - `component`
  - `id`

2.7 modal component classes in the same module:

- `FileUploadComponent`
- `RadioGroupComponent`
- `CheckboxGroupComponent`
- `CheckboxComponent`

For the current ticket-panel inspection use case, the classic
`ActionRow`/`Button`/`SelectMenu` objects are the important ones, but
`Message.components` in 2.7.x is broader than that.

## 3. How components are nested

### 3.1 Classic nesting

For ordinary message buttons/selects, the classic structure is:

`Message.components -> ActionRow -> Button/SelectMenu`

Relevant source:

- Type alias:
  [`discord/components.py#L87-L99`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L87-L99)
- `ActionRow.children`:
  [`discord/components.py#L260-L280`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L260-L280)

This is the shape most likely to appear on ticket panels.

### 3.2 It is not always only ActionRow -> children

In 2.7.x, messages can also contain Components v2, and those can nest
more deeply than a single action row.

Relevant source:

- Recursive traversal in `discord.ui.view._walk_all_components()`:
  [`discord/ui/view.py#L101-L111`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/ui/view.py#L101-L111)

The traversal logic explicitly handles:

- `ActionRow` by iterating `children`
- `Container` by recursively walking its `children`
- `SectionComponent` by walking its `children` and its `accessory`

So the answer to "is it always ActionRow -> children?" is no for
`discord.py` 2.7.x as a whole.

Examples of valid higher-level nesting shapes visible in the source:

- `Message.components -> Container -> ActionRow -> Button`
- `Message.components -> Container -> SectionComponent -> accessory Button`
- `Message.components -> SectionComponent -> TextDisplay + accessory`

For ticket-panel serialization, the common case is still the classic row
model.

## 4. `Component` vs `ActionRow` hierarchy

Relevant source:

- Base class:
  [`discord/components.py#L131-L181`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L131-L181)
- `ActionRow`:
  [`discord/components.py#L249-L294`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L249-L294)
- `Button`:
  [`discord/components.py#L297-L396`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L297-L396)
- `SelectMenu`:
  [`discord/components.py#L398-L492`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/components.py#L398-L492)

The hierarchy is flat under `Component`:

- `Component`
  - `ActionRow`
  - `Button`
  - `SelectMenu`
  - `TextInput`
  - `SectionComponent`
  - `TextDisplay`
  - `ThumbnailComponent`
  - `MediaGalleryComponent`
  - `FileComponent`
  - `SeparatorComponent`
  - `Container`
  - `LabelComponent`
  - `FileUploadComponent`
  - `RadioGroupComponent`
  - `CheckboxGroupComponent`
  - `CheckboxComponent`

Important consequences:

- `ActionRow` is not a superclass of `Button` or `SelectMenu`.
- Nesting is represented by attributes like `children`, `accessory`, or
  `component`, not by class inheritance.
- `discord.ui.View.from_message()` converts these read-only component
  objects into separate mutable `discord.ui` items.

Relevant docs/source for the conversion step:

- [`discord/ui/view.py#L386-L445`](https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/ui/view.py#L386-L445)

Small source excerpt:

```python
for component in message.components:
    if not view._is_layout() and isinstance(component, ActionRowComponent):
```

## 5. Metadata most useful for ticket-panel inspection

For a ticket panel button, the fields that identify the button in a
serialization are:

- `custom_id`
  - Usually the most important identifier for non-link interactive
    buttons.
- `label`
  - What users see on the button.
- `style`
  - Distinguishes primary/success/danger/link/etc.
- `emoji`
  - Often part of the user-visible identity.
- `disabled`
  - Important if the panel shows inactive controls.
- `url`
  - Required for link buttons, which do not have `custom_id`.
- `id`
  - Component ID added in 2.6; not usually the logical interaction
    identifier, but still exposed.
- Row and child order
  - `Message.components` preserves top-level order, and `ActionRow.children`
    preserves in-row order.

For select menus, the useful inspection metadata is:

- `type`
- `custom_id`
- `placeholder`
- `min_values`
- `max_values`
- `disabled`
- `options[]`
  - `label`
  - `value`
  - `description`
  - `emoji`
  - `default`
- `channel_types`
- `default_values`

## 6. Edge cases and serialization-relevant notes

### 6.1 No components

- Messages without interactive components expose `message.components` as
  an empty list, not `None`.

### 6.2 Missing `message_content` intent

- The docs state `Message.components` will be empty when
  `Intents.message_content` is unavailable, except for mentions and DMs.

### 6.3 Link buttons

- A link button has `style == ButtonStyle.link`.
- It carries `url`.
- It does not carry `custom_id`.

### 6.4 Premium buttons

- Premium buttons may expose `sku_id`.

### 6.5 Disabled state

- `Button.disabled` and `SelectMenu.disabled` are both surfaced directly
  on the read-only message component objects.

### 6.6 Select variants share one class

- `string_select`, `user_select`, `role_select`, `mentionable_select`,
  and `channel_select` are all represented by `discord.SelectMenu`.
- The discriminator is `component.type`, not the Python class.

### 6.7 Options vs default values

- String selects expose `options`.
- Entity selects expose `default_values`.
- Channel selects may also expose `channel_types`.

### 6.8 Components v2 on messages

- In 2.7.x, `Message.components` can contain top-level v2 components such
  as `SectionComponent` or `Container`, not only `ActionRow`.
- `discord.ui.View.from_message()` documents that v2 component messages
  require `LayoutView` for conversion.

### 6.9 Text inputs and newer modal components

- `TextInput`, `FileUploadComponent`, `RadioGroupComponent`,
  `CheckboxGroupComponent`, and `CheckboxComponent` exist in the same
  read-only component model.
- These are modal-oriented rather than the usual ticket-panel message
  controls, but they are still part of the `discord.py` 2.7.x component
  type system.

## Conclusion

For `discord.py` 2.7.x, `Message.components` is a list of read-only
`discord.Component` subclass instances parsed from the message payload.
For the panel-inspection use case, the main serialization targets are:

- top-level row order
- `ActionRow.children`
- per-button fields:
  `custom_id`, `label`, `style`, `emoji`, `disabled`, `url`
- per-select fields:
  `type`, `custom_id`, `placeholder`, `min_values`, `max_values`,
  `disabled`, `options`, `channel_types`, `default_values`

The broad version-specific caveat is that `2.7.x` is not limited to the
classic ActionRow model: Components v2 and newer modal component classes
also exist in the same message component parsing layer.
