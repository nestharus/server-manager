# Shortcut Risk: Component Serialization

**Overall risk level: LOW**

The proposal closely tracks the research and explicitly acknowledges every
gap it introduces. The omitted cases (Components v2 deep serialization,
TextInput, `required` field) are documented in the anti-scope section with
clear rationale rather than silently dropped. The fallback path for
unrecognized components is minimal but intentional, and the tradeoffs
section honestly describes the consequences. There are no hidden shortcuts;
the few findings below are minor underspecifications rather than corners
cut for expedience.

## Findings

### 1. Enum-to-string mechanism unspecified (LOW)

The proposal says "string enum names" for `ComponentType`, `ButtonStyle`,
and `ChannelType` and shows bare values like `"primary"` and
`"action_row"` in the JSON examples. It does not specify whether the
implementation should use `.name`, `str()`, or the existing `safe_str()`
helper. In discord.py 2.x these currently produce identical results for
the relevant enums, but a future discord.py release could change `__str__`
behavior without changing `.name`.

**Severity:** LOW — the existing codebase uses `safe_str()` for the same
purpose and an implementer would likely follow that pattern.

**Recommendation:** Add one sentence to the Serialization Rules section
stating which mechanism to use (e.g., "use `safe_str()` consistent with
the existing embed and message type serialization").

### 2. TextInput in ActionRow children falls to fallback silently (LOW)

The research documents that `ActionRow.children` is typed as
`list[Button | SelectMenu | TextInput]`. The proposal dispatches Button
and SelectMenu to dedicated serializers and routes everything else —
including TextInput — through the minimal `{type, id}` fallback. TextInput
carries fields like `label`, `custom_id`, `placeholder`, `value`,
`required`, `min_length`, and `max_length` that would all be lost.

**Severity:** LOW — TextInput is modal-oriented and should not appear in
normal message ActionRows. The anti-scope section explicitly excludes it.

**Recommendation:** None required. If TextInput serialization is ever
needed, it can be added as a new dedicated serializer without changing the
dispatch structure.

### 3. Components v2 nested interactive components are invisible (LOW)

The research documents that `Message.components` in 2.7.x can contain
top-level `Container` or `SectionComponent` entries with nested ActionRows
and Buttons. The proposal's fallback emits only `{type, id}` for these,
meaning any interactive components nested inside v2 containers are silently
dropped from the output.

**Severity:** LOW — the current Humility server uses only the classic
ActionRow model, and the proposal acknowledges this tradeoff explicitly.

**Recommendation:** None required. The fallback prevents crashes without
pretending to support v2. Full v2 serialization is a separate future
effort.

### 4. No indication when fallback is used (LOW)

When an unrecognized component hits the fallback path, the output contains
only `{type, id}` with no marker distinguishing it from a component that
genuinely has only those two fields. A consumer cannot tell whether the
output is complete or truncated.

**Severity:** LOW — the `type` field itself reveals whether the component
is a recognized type (action_row, button, string_select, etc.) or an
unrecognized one (container, section, text_display, etc.), so a careful
consumer can infer which entries are fallbacks.

**Recommendation:** Consider adding a `"partial": true` flag to fallback
output to make truncation explicit, though this is optional given the low
likelihood of v2 components in the current use case.
