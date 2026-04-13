# Notes

- Target guild: Humility (`900000000000000001`) per [AGENTS.md](/home/nes/discord/AGENTS.md).
- `discord_cli.py` is the reusable local CLI surface for Discord inspection and management work.
- Initial scaffold implements `overview` and reserves `bots`, `channels`, `find-channel`, `read`, and `integrations` as stubs.
- Research report for the Discord CLI problem space is in [research/05-discord-cli.md](/home/nes/discord/research/05-discord-cli.md).
- Local `uv` resolution currently exposes `discord.py` `2.7.1` even though `pyproject.toml` only requires `>=2.3`.
- Phase 6 added contract tests in [tests/test_discord_cli.py](/home/nes/discord/tests/test_discord_cli.py) based only on [proposals/05-discord-cli.md](/home/nes/discord/proposals/05-discord-cli.md) and [research/05-discord-cli-needs.md](/home/nes/discord/research/05-discord-cli-needs.md).
- Current implementation gaps exposed by that test suite:
  - `read` parser does not yet accept the required `channel` positional or optional `--limit`.
  - Only `fetch_overview` is publicly exposed; contract tests expect async per-command handlers for `bots`, `channels`, `find-channel`, `read`, and `integrations`.
  - `fetch_overview` does not yet match the proposed pure handler shape of `(guild, args)`.
- Key research findings:
  - `bots` depends on privileged member access (`Intents.members`) because it is a member-list problem.
  - `channels` and `overview` primarily depend on `Intents.guilds` and guild/cache state.
  - `read` centers on `abc.Messageable.history()` and documented channel permissions like `read_message_history`; the gathered docs did not establish `Intents.message_content` as a `history()` requirement.
  - `integrations` centers on `Guild.integrations()` plus `manage_guild`; `Intents.integrations` only affects integration gateway events.
  - Phase 7 roles research: `guild.roles` is populated from `GUILD_CREATE` under `Intents.guilds`; `Role.members` is cache-derived from `guild._members` and is incomplete without chunking or other member-cache population.
