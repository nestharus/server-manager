# Scope Risk: Component Serialization

**Overall risk level: LOW**

The proposal stays tightly within its stated boundaries. It adds one key
to `serialize_message()` and introduces a small stack of read-only
serializer helpers that follow the identical pattern already established
for attachments and embeds. The anti-scope is explicit and
well-calibrated: it excludes Components v2 deep serialization, modals,
`TextInput`, mutations, parser changes, and `discord.ui` conversion.
Nothing in the proposed change touches command wiring, dispatch, or
Discord write paths. The seven new helpers (`serialize_component`,
`serialize_action_row`, `serialize_button`, `serialize_select_menu`,
`serialize_select_option`, `serialize_select_default_value`,
`serialize_partial_emoji`, `serialize_component_fallback`) are
proportionate to the three component classes being covered and do not
introduce abstractions beyond what the data shapes require.

## Findings

### 1. SelectMenu `required` field exclusion is appropriate but implicit

**Severity: INFO**

The anti-scope lists `required` on `SelectMenu` as excluded, and the
research confirms it is only meaningful for string selects in modals.
This is the correct call. No action needed — noting for completeness
that the exclusion is deliberate and justified.

### 2. Dependency pin is loose: `discord.py>=2.3`

**Severity: LOW**

`pyproject.toml` pins `discord.py>=2.3`. The proposal targets 2.7.x
APIs (`id` on components, `SelectDefaultValue`, `sku_id` on Button).
These attributes exist from 2.6+. A runtime on 2.3-2.5 would hit
missing attributes, but `getattr` with defaults (the pattern used
throughout the existing serializers) would degrade gracefully to `null`.
The proposal's fallback path already handles unrecognized types.
This is a pre-existing condition, not new coupling introduced by
this proposal.

**Recommendation:** No change required for this proposal. A future
housekeeping pass could bump the floor to `>=2.6` to match the actual
API surface in use.

### 3. Helper count is proportionate

**Severity: INFO**

Eight new functions may seem like a lot for "add one key to a dict," but
each maps 1:1 to a distinct discord.py data class. The alternative —
inlining everything — would produce a single unreadable function. The
count matches the established codebase pattern (separate helpers for
author, channel, attachment, embed, integration, role, member). No
over-engineering detected.

### 4. Fallback boundary is correctly drawn

**Severity: INFO**

The fallback emits `{type, id}` for any unrecognized component and
explicitly does not recurse into Components v2 children. This prevents
the serializer from crashing on newer payloads while keeping scope
narrow. The anti-scope correctly lists every Components v2 class that
the fallback will catch. No accidental scope leakage here.

### 5. No test or validation surface added

**Severity: LOW**

The proposal is design-only and does not specify test expectations.
This is acceptable for a proposal document, but implementation should
include tests for the new helpers. This is not a scope risk — it is a
normal implementation concern that does not need to gate the proposal.
