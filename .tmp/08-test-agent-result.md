## Verification Result

No new tests are needed for this pass.

The existing test `test_bots_handler_filters_members_by_bot_flag` in
`tests/test_discord_cli.py:426` adequately covers the requested
`fetch_bots()` contract in `discord_cli.py:371`.

Why the current test is sufficient for this verification target:

- It exercises `fetch_bots()` through the public async handler.
- The fixture guild supplies mixed cached members via `guild.members`
  (`owner`, one human, and two bot members), so the test verifies bot
  filtering from cached members rather than from any fetch or chunk
  path.
- It asserts `result["count"] == len(expected_bots)`, which covers the
  returned count.
- It asserts on `result["bots"]` by comparing returned entry ids to the
  expected bot ids, which covers that the payload includes a `bots`
  list containing only bot members.
- It explicitly checks that the human member id is absent from the
  returned `bots` list.

Scope note:

- The existing test does not cover the empty-cache `CLIError` branch,
  but that branch is outside the requested verification scope here. For
  the stated contract of cached-member bot filtering plus `{count,
  bots}` return format, current coverage is adequate.
