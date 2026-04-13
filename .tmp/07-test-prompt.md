# Test Agent: Roles Command

## Task

Write tests for the `fetch_roles` handler in `discord_cli.py`. Add
tests to the EXISTING file `tests/test_discord_cli.py`.

## Contract (from proposal)

The `fetch_roles` handler has this contract:

```python
async def fetch_roles(guild: discord.Guild, args: argparse.Namespace) -> dict:
    """Return role metadata for all guild roles."""
```

### Input
- `guild` — a discord.Guild object with `.roles` populated
- `args` — argparse.Namespace (no additional arguments for this command)

### Output Schema
```json
{
  "count": <int>,
  "roles": [
    {
      "id": <int>,
      "name": <str>,
      "color": <int>,
      "hoist": <bool>,
      "position": <int>,
      "permissions": <int>,
      "managed": <bool>,
      "mentionable": <bool>,
      "is_default": <bool>,
      "is_bot_managed": <bool>,
      "is_integration": <bool>,
      "is_premium_subscriber": <bool>,
      "created_at": <str ISO 8601>
    }
  ]
}
```

## What to Test

1. **Handler exists and is async**: Use the `require_public_handler`
   pattern from the existing tests.

2. **Returns correct count**: `count` should match `len(roles)`.

3. **Serializes role fields correctly**: Verify id, name, color, hoist,
   position, permissions, managed, mentionable are present and correctly
   typed.

4. **Boolean helpers**: Verify `is_default`, `is_bot_managed`,
   `is_integration`, `is_premium_subscriber` are present and boolean.

5. **created_at is ISO 8601**: Verify the datetime is serialized
   correctly.

6. **Parser recognizes roles subcommand**: Verify `build_parser()`
   accepts `roles`.

## Rules

- Read `tests/test_discord_cli.py` first to understand existing patterns
- Use the existing `guild_fixture` — add role objects to it if needed
- Do NOT read or reference implementation code — test from contract ONLY
- Follow the existing test naming pattern:
  `test_<handler>_<behavior>(guild_fixture)`
- Use `require_public_handler("roles")` to get the handler
- Use the `run()` helper for async execution
