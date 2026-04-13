# Phase 5: Hookpoint Research — Discord CLI Tool

## Objective
Map the approved proposal to existing code. Find what's reusable, what's parallel, what to delete. This informs the implementation agent.

## Input
Read these files:
- `proposals/05-discord-cli.md` — the approved proposal
- `discord_cli.py` — the existing code (if any)
- Any other Python files in the project

## Research Questions
1. Does `discord_cli.py` already exist? If so, what subcommands are implemented vs stubbed?
2. What patterns from the existing code should be preserved (e.g., gateway lifecycle, JSON output, argparse structure)?
3. What code can be reused vs what needs to be written fresh?
4. Are there any utility functions or patterns that could be shared across subcommands?
5. What's the current state of the `.env` loading and configuration?

## Deliverable
Write your findings to `research/05-hookpoints.md`. Structure as:
1. Existing code inventory (what's there, what works)
2. Reuse opportunities (code to keep)
3. Implementation gaps (what needs to be built)
4. Deletion candidates (dead code or stubs to replace)
5. Parallel opportunities (subcommands that can share patterns)

## Rules
- Do NOT implement anything
- Do NOT modify any files
- Focus on mapping the proposal to existing code
