# Scope Risk Assessment: discord_cli.py

## Risk Level: LOW

## Findings

1. **[LOW] Subcommand set maps 1:1 to stated needs.** The proposal implements exactly the 6 subcommands identified in the needs analysis (`overview`, `bots`, `channels`, `find-channel`, `read`, `integrations`). No extra subcommands were added.

2. **[LOW] Error taxonomy is detailed but not over-engineered.** The proposal specifies 11 error categories (the original 10 plus `timeout_error`). Each category maps to a real Discord failure mode or `asyncio` exception documented in the research. The 3-value exit code scheme (0/1/2) keeps the shell interface simple. Implementation is just a mapping dict — specification detail, not code bloat.

3. **[LOW] "Recommended additional fields" slightly exceed core requirements.** The `channels` spec adds `nsfw`, `topic`, and `parent_id` beyond the fields the user asked for. The `read` spec includes `tts`, `jump_url`, and embed summaries. These are single-attribute reads off existing model objects — they cost almost nothing to include and would cost more to add later (changing the output contract). Acceptable enrichment, not feature creep.

4. **[LOW] `message_content` intent is over-scoped by design.** The proposal enables `Intents.message_content` even though research confirms it is not required for `history()`. The proposal explicitly acknowledges this tradeoff and justifies it: the user already enabled the intent in the Developer Portal, and it avoids future surprises. The cost is a broader privileged scope with zero additional code complexity.

5. **[LOW] Channel resolution in `read` has 4-step fallback logic.** The resolver tries: integer ID, exact name, substring, fail with ambiguous error. This is the most complex logic in the proposal. However, the needs document specifically calls for name-based ergonomic resolution, and the research confirms Discord has no native name-lookup API. The ambiguity error path is a safety feature, not over-engineering.

6. **[LOW] Gateway timeout addition is minimal and proportionate.** The revised proposal adds `asyncio.wait_for()` with a 30-second default wrapping the gateway session, plus one `timeout_error` error category. This is the minimum viable fix for the previously identified hang risk (no connection timeout). It does not introduce retry logic, exponential backoff, configurable timeout flags, or any complexity beyond what was needed. One stdlib call and one error mapping entry — well within scope for a CLI that must always terminate cleanly.

7. **[NONE] Anti-scope section is strong and specific.** The proposal explicitly rules out: daemon mode, multi-guild support, general SDK wrapper, database-backed cache, REPL/TUI, job queue, moderation framework, write operations, and compatibility shims. This is an unusually thorough scope boundary for a proposal of this size.

8. **[NONE] Abstraction level matches a single-file tool.** Four layers (argparse, config/JSON utilities, one-shot session runner, per-subcommand handlers) are appropriate. No packages, no frameworks, no plugin systems.

9. **[NONE] Dependency scope is minimal.** The tool requires `discord.py` (already a project dependency) and standard library modules (`argparse`, `json`, `asyncio`). The `.env` loading implies `python-dotenv` or equivalent, which is already in the project. No new dependencies introduced.

10. **[NONE] Each subcommand does one thing.** No subcommand combines concerns. `overview` reads guild metadata, `bots` filters members, `channels` dumps structure, `find-channel` searches names, `read` fetches history, `integrations` lists integrations. The only secondary responsibility is channel resolution inside `read`, which is inherent to the "read by name" requirement.

## Recommendation

**Accept.** The proposal is well-scoped for a single-file CLI tool with 6 subcommands. The subcommand set matches the needs document exactly, the anti-scope boundaries are clear, and the timeout revision adds the minimum necessary complexity to address the previously identified shortcut risk without expanding scope. The few areas of additional specification (error taxonomy, recommended fields, `message_content` intent) are justified by the research and add negligible implementation cost. No changes needed.
