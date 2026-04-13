# Shortcut Risk Assessment: Roles Command

## Task

Assess the SHORTCUT risk of the proposal in `proposals/07-roles-command.md`.
Write your assessment to `risk/07-shortcut.md`.

## Context

Read these files:
- `proposals/07-roles-command.md` — the proposal to assess
- `research/07-roles-command.md` — background research
- `discord_cli.py` — current implementation
- `risk/05-shortcut.md` — reference for assessment format

## What to Assess

1. **Shortcuts in the proposal itself**: Does the proposal introduce
   shortcuts that will cause problems later?
2. **Missing error handling**: Are there error scenarios that should be
   handled but aren't?
3. **Implicit assumptions**: Does the proposal rely on assumptions that
   might not hold?
4. **Technical debt**: Does the proposal create technical debt that
   isn't acknowledged?

## Output Format

```markdown
# Shortcut Risk Assessment: Roles Command

## Risk Level: LOW | MEDIUM | HIGH

## Findings

1. **Finding title** (severity)
   Description and evidence.

## Recommendation

Accept or revise.
```
