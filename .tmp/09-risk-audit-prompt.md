# Risk Assessment: Audit Risk — bot-activity command

## Your Role

You are an audit risk assessor. Read the proposal and assess whether it
introduces security, data-integrity, or operational risks.

## Files to Read

- `/home/nes/discord/worktrees/bot-activity/proposals/09-bot-activity.md` — the proposal
- `/home/nes/discord/worktrees/bot-activity/discord_cli.py` — existing code
- `/home/nes/discord/worktrees/bot-activity/research/09-bot-activity.md` — research

## Assessment Criteria

1. **Security**: Does the command expose sensitive data? Can the bot_id
   argument be abused? Are there injection vectors?
2. **Data integrity**: Can this command corrupt or modify any state?
3. **Operational safety**: Can scanning many channels cause rate limiting,
   timeouts, or resource exhaustion?
4. **Permission model**: Does it respect the CLI's tier system?

## Output

Write your assessment to `risk/09-audit.md` with this structure:

```markdown
# Audit Risk Assessment: bot-activity

## Overall: LOW | MEDIUM | HIGH

## Findings

### Finding 1: [title]
- Risk level: LOW | MEDIUM | HIGH
- Description: ...
- Recommendation: ...

[repeat for each finding]
```

Rate the overall risk. If any finding is MEDIUM or HIGH, state what
must be addressed before implementation.
