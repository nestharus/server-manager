# Synthesis: Message Component Serialization Needs

## Source

Research: `research/12-read-components.md`

## Humility-Specific Context

The Humility Discord server has exactly one interactive panel that matters
right now: the `#support` channel contains a `HumilityTicketBot#7529`
message (ID `900000000000000003`, posted `2023-12-22`) with an embed
titled "Click to open a ticket" and a description "Click on the button
corresponding to the type of ticket you wish to open." The `#panels`
channel has a similar "General Support" panel from `2022-04-04`.

These panels use buttons to open tickets. The current `serialize_message()`
function serializes embeds but not the `components` field, so we cannot
see the button metadata (custom_id, label, style) needed to diagnose
why ticket interactions are failing after the ticketsbot.net shutdown
and whitelabel migration.

## Mapping Research to Needs

### What we need (scoped)

1. **Serialize `message.components` in `serialize_message()`** — add a
   `"components"` key to the output dict that captures the interactive
   components attached to each message.

2. **ActionRow → Button serialization** — this is the primary use case.
   The ticket panel buttons are in ActionRows. Each button needs:
   `custom_id`, `label`, `style` (as string name), `emoji`, `disabled`,
   `url`, `sku_id`.

3. **ActionRow → SelectMenu serialization** — secondary but should be
   included for completeness since the CLI is a general inspection tool.
   Each select needs: `type` (as string name), `custom_id`, `placeholder`,
   `min_values`, `max_values`, `disabled`, `options` (with label/value/
   description/emoji/default), `channel_types`, `default_values`.

4. **Handle empty components** — when `message.components` is empty (most
   messages), emit `"components": []` rather than omitting the key.

### What we do NOT need (anti-scope)

- **Components v2 deep serialization** — Container, SectionComponent,
  TextDisplay, etc. These are new and not used by any current Humility
  panel. A generic fallback (type + id only) is sufficient for now.
- **TextInput serialization** — modal-only, not present in message
  components for ticket panels.
- **Recursive component tree walking** — the classic ActionRow model is
  flat (one level of nesting). We don't need recursive traversal for the
  current panels.
- **Mutable `discord.ui` conversion** — we're read-only inspection, not
  interaction handling.

### Gaps / risks identified

1. **Emoji serialization** — buttons and select options can have
   `PartialEmoji`. Need a serializer for emoji (name, id, animated).
   Check if the existing codebase already has one.

2. **Style enum to string** — `ButtonStyle` and `ComponentType` are enums.
   The existing `safe_str()` helper likely handles this, but verify.

3. **Components v2 fallback** — if a message somehow has a Container or
   SectionComponent, the serializer should not crash. A minimal fallback
   that emits `{"type": "...", "id": ...}` for unrecognized component
   types is sufficient.

## Conclusion

The scope is narrow: add a `"components"` list to `serialize_message()`
that serializes ActionRow children (buttons and select menus) with their
full metadata. This directly enables the ticket-panel inspection that
motivated the change. The fallback for newer component types prevents
crashes without requiring full Components v2 support.
