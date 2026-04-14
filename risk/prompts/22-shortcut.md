# Risk Assessment: Shortcut Risk — VersionedMixin (contracts/base.py)

## Your Role

You are a shortcut risk assessor. Evaluate whether the proposal in
`proposals/22-contracts-base.md` introduces its own shortcuts — places
where the design takes an easy path that creates problems later.

## Context

- Research: `research/22-contracts-base.md`
- Synthesis: `research/22-contracts-base-needs.md`
- Proposal: `proposals/22-contracts-base.md`

## Evaluation Criteria

1. **Deferred complexity**: Does the proposal push complexity to
   consumers instead of solving it? E.g., making every concrete
   schema handle version semantics differently.
2. **Undocumented assumptions**: Does the proposal rely on behavior
   that isn't documented in Pydantic v2? The research flagged that
   plain-class mixin field contribution is observed but not documented.
3. **Missing validation**: Should the version field have validators
   that the proposal doesn't include?
4. **Anti-patterns**: Does the proposal introduce patterns that
   conflict with project rules (no backwards compatibility, no
   deferred stubs)?

## Output

Write your assessment to `risk/22-shortcut.md` with this structure:

```markdown
# Shortcut Risk Assessment: VersionedMixin

## Overall: LOW | MEDIUM | HIGH

## Findings

### Finding 1: [title]
- Severity: LOW | MEDIUM | HIGH
- Description: ...
- Recommendation: ...
```

If overall risk is MEDIUM or HIGH, explain what shortcut must be
addressed before implementation can proceed.
