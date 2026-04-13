# Hookpoint Research: Bots No-Chunking Verification

## Context
Read `proposals/08-bots-nochunk.md`. The proposal is a verification-only pass confirming that `fetch_bots()` already satisfies the no-chunking goal. No code changes are proposed.

## Task
Since no code changes are proposed, this hookpoint research confirms what exists and maps the current implementation to the proposal's verification findings.

Write `research/08-hookpoints.md` documenting:
1. The current `fetch_bots()` function location and signature
2. The serialization helper it uses (`serialize_bot_member`)
3. The registration in `command_specs()` and `build_parser()`
4. The test coverage in `tests/test_discord_cli.py`
5. Confirmation that no new hookpoints are needed since no changes are proposed
