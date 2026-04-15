# Audit Risk Assessment: Component Serialization

## Overall: LOW

The proposal adds read-only serialization helpers that convert existing
discord.py component objects into JSON-safe dictionaries. The change is
confined to the serializer layer, introduces no mutation or write
behavior, accepts no external user input beyond what discord.py already
parses, and degrades safely on unrecognized component types. All
identified findings are low severity.

## Findings

### Finding 1: Enum `.name` access on unexpected values

- Severity: LOW
- Description: The proposal uses string enum names via `component.type`,
  `component.style`, and `channel_types` entries. In discord.py, these
  are `enum.Enum` subclasses and `.name` is always a string. However, if
  Discord adds a new enum value before discord.py updates its enum
  definitions, the library may return a raw `int` instead of an enum
  member. Calling `.name` on an int raises `AttributeError`. The proposal
  uses `safe_str()` as the existing fallback pattern, but does not
  explicitly mandate its use for `style` or `channel_types` enum
  serialization.
- Recommendation: Ensure `safe_str()` is used when serializing
  `component.style` and `channel_types` entries, consistent with how the
  codebase already serializes `message.type`. This is defensive, not
  blocking.

### Finding 2: `getattr` guards against missing attributes

- Severity: LOW
- Description: The proposal sources data via `getattr(message,
  "components", [])`, which is consistent with the existing serializer
  pattern. The component objects themselves are constructed by discord.py
  from validated payloads, so attribute access on `Button`, `SelectMenu`,
  and `ActionRow` is safe. The `id` attribute (added in discord.py 2.6)
  is always present in 2.7.x.
- Recommendation: No action required.

### Finding 3: No data leakage risk

- Severity: LOW
- Description: The serializer only reads public attributes already
  exposed by discord.py's read-only component model. No tokens, secrets,
  internal state, or raw HTTP payloads are accessed. The `url` field on
  link buttons is a Discord-provided URL, not user-controlled input to
  the CLI.
- Recommendation: No action required.

### Finding 4: Fallback does not recurse into Components v2

- Severity: LOW
- Description: The proposal explicitly limits the fallback to
  `{type, id}` for unrecognized component classes and states it must not
  recurse into Components v2 internals. This prevents unbounded recursion
  on deeply nested v2 structures (e.g., `Container -> SectionComponent ->
  accessory`). The anti-scope section confirms this boundary.
- Recommendation: No action required. The explicit anti-recursion rule is
  the correct choice.

### Finding 5: `ActionRow.children` may contain `TextInput`

- Severity: LOW
- Description: The research documents that `ActionRow.children` is typed
  as `list[Button | SelectMenu | TextInput]`. The proposal dispatches
  `Button` and `SelectMenu` but routes `TextInput` through the fallback.
  This is correct behavior — `TextInput` is modal-only and explicitly
  out of scope — but the fallback will emit `{type: "text_input", id:
  ...}` rather than silently dropping it.
- Recommendation: No action required. The fallback behavior is
  intentional and documented in the anti-scope section.

### Finding 6: Contract stability of `"children"` key name

- Severity: LOW
- Description: The proposal uses `"children"` inside `ActionRow` instead
  of `"components"` (which is the Discord API's raw payload key name).
  The justification — avoiding collision with the top-level message
  `"components"` key and matching discord.py's object model — is
  reasonable. However, consumers expecting the raw Discord API shape will
  need to know about this divergence.
- Recommendation: No action required. The choice is explicitly documented
  in the proposal with rationale. Consumers already depend on the CLI's
  serialization schema, not the raw Discord API.

### Finding 7: Empty arrays are always emitted

- Severity: LOW
- Description: The proposal mandates `options: []`, `channel_types: []`,
  and `default_values: []` on all select menu types, even when those
  fields are semantically meaningless (e.g., `options` on a
  `user_select`). This slightly widens payloads but keeps the contract
  uniform and prevents consumers from needing null checks.
- Recommendation: No action required. This is an intentional tradeoff
  documented in the proposal.

### Finding 8: No crash path from `None` components list

- Severity: LOW
- Description: `message.components` is always initialized as a list in
  discord.py (never `None`), and the proposal additionally guards with
  `getattr(message, "components", [])`. There is no path where the
  serializer receives `None` and attempts to iterate it.
- Recommendation: No action required.
