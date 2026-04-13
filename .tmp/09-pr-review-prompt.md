# PR Review: bot-activity command

## Your Role

You are a PR reviewer performing two checks:
1. **Multi-concern check**: Can this PR be decomposed into smaller PRs?
2. **Justification check**: What deserves to be in this PR? What doesn't?

## Files to Review

Read the diff in the worktree:
```bash
cd /home/nes/discord/worktrees/bot-activity && git diff master...HEAD
```

Also read the implementation:
- `/home/nes/discord/worktrees/bot-activity/discord_cli.py`
- `/home/nes/discord/worktrees/bot-activity/tests/test_discord_cli.py`

## Rules

- A PR that touches N independent concerns should be split into N PRs
- Dependency order matters
- A large deletion is its own PR
- If you conclude "cannot decompose further", the PR is ready to merge

## Output

Write your review to `risk/09-pr-review.md` with:

```markdown
# PR Review: bot-activity

## Multi-concern check
[Can this be decomposed? If so, into what?]

## Justification check
[What belongs? What doesn't?]

## Verdict
[Ready to merge / needs decomposition]
```
