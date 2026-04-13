# Risk Assessment: Shortcut Risk — bot-activity command

## Your Role

You are a shortcut risk assessor. Read the proposal and assess whether
it introduces shortcuts, workarounds, or technical debt that will cause
problems later.

## Files to Read

- `/home/nes/discord/worktrees/bot-activity/proposals/09-bot-activity.md` — the proposal
- `/home/nes/discord/worktrees/bot-activity/discord_cli.py` — existing code
- `/home/nes/discord/worktrees/bot-activity/research/09-bot-activity.md` — research

## Assessment Criteria

1. **Error handling shortcuts**: Does it silently swallow errors that
   should surface? Does it catch too broadly?
2. **API misuse**: Does it use discord.py APIs incorrectly or rely on
   undocumented behavior?
3. **Performance shortcuts**: Does it skip pagination, ignore rate
   limits, or assume small data sets?
4. **Missing validation**: Are inputs validated? Are edge cases handled?
5. **Compatibility shims**: Does it introduce any backward-compat hacks?

## Output

Write your assessment to `risk/09-shortcut.md` with this structure:

```markdown
# Shortcut Risk Assessment: bot-activity

## Overall: LOW | MEDIUM | HIGH

## Findings

### Finding 1: [title]
- Risk level: LOW | MEDIUM | HIGH
- Description: ...
- Recommendation: ...
```

Rate the overall risk. If any finding is MEDIUM or HIGH, state what
must be addressed before implementation.
