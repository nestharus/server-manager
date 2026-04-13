# Shortcut Risk Assessment: Roles Command

## Risk Level: LOW

## Findings

1. **Snowflake IDs as JSON integers — inherited** (LOW)
   Same issue as finding #3 in risk/05. Role IDs are Discord snowflakes
   and can exceed `2^53`. The proposal specifies `id` as `int`, which is
   correct and lossless for Python-to-Python consumption. If the output
   were piped to a JavaScript consumer, IDs would silently lose
   precision. Acceptable for the current scope — flagged for continuity
   with the existing assessment.

2. **All intents enabled for a cache-only command — inherited** (LOW)
   Same issue as finding #4 in risk/05. The `roles` command reads only
   `guild.roles`, which requires `Intents.guilds` alone. The shared
   `build_intents()` also requests `members` and `message_content`. No
   practical cost for a single-guild admin tool, but the roles command
   would be the clearest candidate for intent narrowing if that were
   ever pursued.

3. **`created_at` is never None but `iso_or_none()` is suggested** (LOW)
   The proposal recommends using `role.created_at.isoformat()` or the
   existing `iso_or_none()` helper. Per the research, `created_at` is
   derived from the snowflake ID and is always a `datetime` — it cannot
   be `None`. Using `iso_or_none()` is harmless but subtly implies the
   value might be absent, which could mislead a future reader. Either
   approach produces correct output. Not worth blocking on.

4. **No error paths needed — and none are missing** (NONE)
   The command iterates `guild.roles`, which is populated from
   `GUILD_CREATE` before `on_ready` fires. Every guild has at least the
   `@everyone` role, so an empty collection is not a realistic scenario.
   The tag-derived booleans (`is_bot_managed()`, `is_integration()`,
   `is_premium_subscriber()`) are `Role`-level methods that handle
   `None` tags internally. There are no API calls, no user-supplied
   selectors, and no permission-gated data. The absence of error
   handling is correct, not a shortcut.

5. **`is_assignable()` omitted without explicit rationale** (LOW)
   The research identifies `is_assignable()` as available on `Role` but
   notes it depends on `guild.me` and role hierarchy — it is not pure
   payload metadata. The proposal omits it, consistent with the "pure
   metadata export" goal, but does not call it out in the anti-scope
   list. A future contributor might add it without understanding the
   `guild.me` dependency. Minor documentation gap, not a design
   shortcut.

## Recommendation

**Accept.** The proposal is conservative, well-scoped, and introduces no
new shortcuts. All findings are LOW or inherited from the existing
codebase. None require changes before implementation.
