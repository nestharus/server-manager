# Audit Risk Assessment: Roles Command

## Task

Assess the AUDIT risk of the proposal in `proposals/07-roles-command.md`.
Write your assessment to `risk/07-audit.md`.

## Context

Read these files:
- `proposals/07-roles-command.md` — the proposal to assess
- `research/07-roles-command.md` — background research
- `discord_cli.py` — current implementation
- `risk/05-audit.md` — reference for assessment format

## What to Assess

1. **Security**: Does the proposal expose sensitive data? Are permissions
   serialized safely?
2. **Data integrity**: Could the output be misleading or incomplete?
3. **Error handling**: Are failure modes covered?
4. **API contract**: Is the JSON output schema clean and consistent
   with existing commands?

## Output Format

```markdown
# Audit Risk Assessment: Roles Command

## Risk Level: LOW | MEDIUM | HIGH

## Findings

1. **Finding title** (severity)
   Description and evidence.

## Recommendation

Accept or revise.
```

Rate each finding as LOW, MEDIUM, or HIGH. The overall risk level
should be the maximum of all findings.
