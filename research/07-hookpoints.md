# Hookpoint Research: Roles Command

Date: 2026-04-12

## 1. Handler registration

The `roles` command fits the existing handler dispatch exactly.

- Add `fetch_roles` alongside the other async guild handlers near
  [discord_cli.py](/home/nes/discord/discord_cli.py:334).
- Register it in `command_specs()` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:417) by adding:
  - `"roles": fetch_roles`
- The command will then flow through the existing generic runner in
  `run_command()` at [discord_cli.py](/home/nes/discord/discord_cli.py:428),
  which already:
  - reads `args.command`
  - looks up the handler from `command_specs()`
  - runs it through `run_gateway_command()`
  - wraps the result with `success_payload()`

Hookpoint summary:

- `fetch_roles(guild, args)` plugs into the same pattern as
  `fetch_bots()` ([discord_cli.py](/home/nes/discord/discord_cli.py:353))
  and `fetch_integrations()`
  ([discord_cli.py](/home/nes/discord/discord_cli.py:409)).

## 2. Parser registration

`roles` should be added in the simple no-argument parser loop in
`build_parser()` at [discord_cli.py](/home/nes/discord/discord_cli.py:441).

The current loop at [discord_cli.py](/home/nes/discord/discord_cli.py:445)
already handles the no-argument inspection commands:

- `overview`
- `bots`
- `channels`
- `integrations`

The new hookpoint is to extend that tuple with:

- `("roles", "List guild roles")`

This is the right place because `roles` matches the same shape:

- no positional arguments
- no optional flags
- `set_defaults(func=run_command)` already provided by the loop at
  [discord_cli.py](/home/nes/discord/discord_cli.py:451)

It should not get its own dedicated parser block like `find-channel` or
`read`, because those exist only for commands with custom arguments at
[discord_cli.py](/home/nes/discord/discord_cli.py:454) and
[discord_cli.py](/home/nes/discord/discord_cli.py:458).

## 3. Serialization helpers

There is no existing role serializer yet, but the file already has the
helper pattern the new command should follow.

Reusable helpers:

- `iso_or_none()` at [discord_cli.py](/home/nes/discord/discord_cli.py:104)
  should be reused for `created_at`.
- `safe_str()` at [discord_cli.py](/home/nes/discord/discord_cli.py:108)
  exists for enum-like or object-ish values, but the approved proposal
  does not need it for any required role fields.

Existing serializer patterns to mirror:

- `serialize_bot_member()` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:122)
- `serialize_channel()` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:144)
- `serialize_message()` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:187)
- `serialize_integration()` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:203)

What is reusable from those patterns:

- flatten Discord objects into plain dicts with JSON-safe primitives
- call small shared helpers like `iso_or_none()` inside the serializer
- keep the async handler itself focused on collection and return shape

What likely gets added:

- a new `serialize_role(role: Any) -> dict[str, Any]` helper near the
  other serializers, probably in the same block around
  [discord_cli.py](/home/nes/discord/discord_cli.py:114)

Fields that need direct flattening rather than helper reuse:

- `role.color.value` for `color`
- `role.permissions.value` for `permissions`
- `role.is_default()`
- `role.is_bot_managed()`
- `role.is_integration()`
- `role.is_premium_subscriber()`

Parallel note:

- This serializer is independent of channel/message/integration helpers.
  It can be added without touching `resolve_channel()`,
  `combined_channels()`, or message serialization code.

## 4. Return shape

The proposed `{"count": N, "roles": [...]}` contract matches the
existing collection-command pattern.

Existing matches:

- `fetch_bots()` returns `{"count": len(bots), "bots": bots}` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:353)
- `fetch_integrations()` returns
  `{"count": len(integrations), "integrations": integrations}` at
  [discord_cli.py](/home/nes/discord/discord_cli.py:409)

That means `fetch_roles()` should follow the same handler shape:

- build a list from `guild.roles`
- preserve the existing order from `guild.roles`
- return:
  - `count`
  - `roles`

This also fits the outer command envelope already handled by
`success_payload()` at [discord_cli.py](/home/nes/discord/discord_cli.py:66)
and `run_command()` at [discord_cli.py](/home/nes/discord/discord_cli.py:428).

## 5. Test patterns

The existing tests establish the pattern the new command should follow.

Parser coverage to extend:

- `test_build_parser_recognizes_all_contract_subcommands`
  ([tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:290))
  should include `"roles"` in the expected subcommand set.

Public handler contract pattern to copy:

- `require_public_handler()` at
  [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:24)
  asserts that `fetch_<command>` exists and is async.
- Handler tests call the handler directly with a mocked guild plus
  `argparse.Namespace()`, for example:
  - `test_bots_handler_filters_members_by_bot_flag`
    ([tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:342))
  - `test_integrations_handler_returns_type_and_enabled_status`
    ([tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:413))

Recommended new test shape:

- Add a `test_roles_handler_returns_expected_contract_fields` using the
  same direct-handler pattern.
- Assert:
  - `result["count"] == len(guild.roles)`
  - `result["roles"]` preserves guild role order
  - each entry includes the approved flattened primitive fields

Fixture hookpoint:

- `guild_fixture()` at
  [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py:85)
  already provides `guild.roles`, but the current role mocks only have
  `id` and `name`.
- To support the proposed `roles` contract, those role mocks will need
  more attributes and methods:
  - `color.value`
  - `hoist`
  - `position`
  - `permissions.value`
  - `managed`
  - `mentionable`
  - `created_at`
  - `is_default()`
  - `is_bot_managed()`
  - `is_integration()`
  - `is_premium_subscriber()`

## 6. Parallel and reusable work

The `roles` command is mostly isolated and low-risk relative to the
other subcommands.

Reusable existing paths:

- handler dispatch in `command_specs()`
- generic execution in `run_command()`
- gateway lifecycle in `run_gateway_command()`
- outer JSON envelope via `success_payload()`
- timestamp serialization via `iso_or_none()`

Independent work units:

- adding `fetch_roles`
- adding `serialize_role`
- extending `command_specs()`
- extending the simple parser tuple in `build_parser()`
- adding handler and parser tests

No coupling points with existing read-path logic:

- `roles` does not depend on member chunking
- `roles` does not depend on `guild.members`
- `roles` does not depend on channel resolution or history reads
- `roles` does not depend on `guild.integrations()`

## Conclusion

The cleanest implementation path is:

1. Add `serialize_role()` near the existing serializers.
2. Add `fetch_roles()` near the existing async handlers.
3. Register `"roles"` in `command_specs()`.
4. Add `("roles", "List guild roles")` to the simple parser loop.
5. Extend the parser-subcommand test and add one direct handler test
   following the `bots` and `integrations` patterns.

No new runner, parser shape, or envelope machinery is needed. The
command fits the current architecture directly.
