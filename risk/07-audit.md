# Audit Risk Assessment: Roles Command

## Risk Level: LOW

## Findings

1. **Permissions bitfield exposes full guild role configuration (severity: low, by design)**
   The proposal serializes `role.permissions.value` as a raw integer. This encodes every permission flag (administrator, manage guild, ban members, etc.) for each role. However, this is guild-level administrative metadata that the bot operator already has access to via the Discord Developer Portal and guild settings. The operator is explicitly requesting this data. Exposing it in stdout is equivalent to any read-only CLI that surfaces API data the caller is authorized to see. No escalation vector exists: the data describes what permissions a role *grants*, not what actions the bot can perform.

2. **No member data leakage through role metadata (severity: none)**
   The proposal explicitly excludes `Role.members`, `guild.chunk()`, and per-role member counts from scope. The anti-scope section enumerates these exclusions. The serialized fields are pure role metadata from the guild payload — no member PII (names, IDs, join dates) can appear in the output. This is the correct boundary: the research establishes that `Role.members` depends on the member cache and would be incomplete or empty without chunking.

3. **Object-valued fields are safely flattened to JSON primitives (severity: none)**
   Three `discord.py` fields require explicit conversion:
   - `role.color` → `role.color.value` (int)
   - `role.permissions` → `role.permissions.value` (int)
   - `role.created_at` → `role.created_at.isoformat()` (str)

   The proposal specifies all three conversions explicitly and notes the existing `iso_or_none()` helper as an option for `created_at`. No `discord.py` library objects are passed through to `json.dumps()` unconverted. The existing `json_default` fallback in `discord_cli.py` would catch `datetime` but not `Permissions` or `Colour` — so the explicit `.value` calls are load-bearing. If an implementer omits them, `json.dumps()` will raise `TypeError`, failing safe rather than leaking malformed data.

4. **`RoleTags`-derived booleans handle `None` gracefully (severity: none)**
   The proposal includes `is_bot_managed`, `is_integration`, and `is_premium_subscriber` — all of which delegate to `RoleTags` methods. The research confirms these are called on `Role`, not on `RoleTags` directly. The `Role` methods guard against `tags is None` (returning `False` when no tags are present), so no `AttributeError` can occur. These booleans are stable, JSON-safe, and cannot produce misleading output.

5. **No new API calls or network surface (severity: none)**
   The command reads only from `guild.roles`, which is populated from the `GUILD_CREATE` gateway event before the handler runs. No additional HTTP requests (e.g., `guild.fetch_roles()`, `guild.chunk()`) are made. This means:
   - No new rate-limit exposure beyond the single gateway connection.
   - No new network error paths beyond what `run_gateway_command` already handles.
   - No increase in the authenticated session window.

6. **Output schema is consistent with existing commands (severity: none)**
   The proposed `{count, roles}` shape matches the established pattern used by `fetch_bots` (`{count, bots}`) and `fetch_integrations` (`{count, integrations}`). The envelope wrapping (`ok`, `command`, `guild_id`, `data`) is inherited from `success_payload()`. No schema divergence is introduced.

7. **No write operations (severity: none)**
   The command is read-only. The anti-scope section explicitly excludes "any write or mutation behavior." The handler signature returns `dict` and has no side effects. Consistent with all existing commands.

8. **`created_at` is derived from snowflake ID, not a stored timestamp (severity: informational)**
   `Role.created_at` is computed from the Discord snowflake, not from a payload field. This is deterministic and cannot drift or be inconsistent with the role's actual creation time. However, consumers should be aware this is a derived value — it reflects when Discord allocated the snowflake, which is effectively the creation time. No data integrity concern.

## Recommendation

**Accept.** The proposal adds a pure read of cached guild-level role metadata with no new API calls, no member data exposure, no write operations, and explicit serialization rules for all non-primitive fields. The output schema is consistent with existing commands. The only non-trivial data exposed — the permissions bitfield — is administrative metadata the operator already has access to. No findings rise above low severity.

One implementation note carries forward from the prior assessment:

- The `json_default` fallback in `discord_cli.py` handles `datetime` but not `Permissions` or `Colour`. The explicit `.value` conversions specified in the proposal are required — omitting them will cause a `TypeError` at serialization time, which fails safe.
