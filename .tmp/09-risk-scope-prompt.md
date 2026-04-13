# Risk Assessment: Scope Risk — bot-activity command

## Your Role

You are a scope risk assessor. Read the proposal and assess whether it
introduces scope creep, unnecessary complexity, or features beyond what
was requested.

## Files to Read

- `/home/nes/discord/worktrees/bot-activity/proposals/09-bot-activity.md` — the proposal
- `/home/nes/discord/worktrees/bot-activity/research/09-bot-activity-needs.md` — needs synthesis
- `/home/nes/discord/worktrees/bot-activity/discord_cli.py` — existing code

## Assessment Criteria

1. **Scope alignment**: Does the proposal match the stated need (bot
   footprint audit for consolidation)?
2. **Unnecessary features**: Does it add capabilities beyond the request?
3. **Complexity**: Is the design proportionate to the problem?
4. **Consistency**: Does it follow existing CLI patterns or introduce
   new patterns unnecessarily?

## Output

Write your assessment to `risk/09-scope.md` with this structure:

```markdown
# Scope Risk Assessment: bot-activity

## Overall: LOW | MEDIUM | HIGH

## Findings

### Finding 1: [title]
- Risk level: LOW | MEDIUM | HIGH
- Description: ...
- Recommendation: ...
```

Rate the overall risk. If any finding is MEDIUM or HIGH, state what
must be addressed before implementation.
