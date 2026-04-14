# Shortcut risk assessment — Chapter contracts

YOU are the shortcut assessor. Assess shortcut risk for the proposal.

## Input files
- `proposals/26-chapters-contract.md` — proposal
- `research/26-chapters-contract.md` — research

## Assessment criteria
1. Any compatibility shims or backward-compat patterns?
2. Any hardcoded values that should be configurable?
3. Any duplicated logic from existing code?
4. Any deferred TODOs instead of resolved decisions?
5. Any unvalidated assumptions about Discord types?
6. Any shortcuts in the VersionedMixin integration?

## Output
Write assessment to `risk/26-shortcut.md` with verdict, findings, recs.

## Rules
- Only modify `risk/26-shortcut.md`
- No code, no server inspection
