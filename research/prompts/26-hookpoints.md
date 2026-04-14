# Hookpoint research — Chapter contracts

YOU are the researcher. Do the research yourself. Do NOT delegate.

## Task
Map the validated proposal for `services/api/app/contracts/chapters.py`
to the existing codebase.

## Input files
- `proposals/26-chapters-contract.md` — validated proposal
- `services/api/app/contracts/base.py` — VersionedMixin
- `services/api/app/contracts/__init__.py` — package init
- `services/api/tests/test_contracts_base.py` — existing tests

## Questions
1. Does `contracts/chapters.py` already exist?
2. Does `VersionedMixin` need changes to support the proposed contracts?
3. Does `contracts/__init__.py` need updating to re-export chapter types?
4. What test patterns exist in `test_contracts_base.py` to follow?
5. Any conflicts with existing code?

## Output
Write to `research/26-hookpoints.md`:
- Existing code inventory
- Reusable components
- New components needed
- Test infrastructure notes
- Conflicts or surprises

## Rules
- Only modify `research/26-hookpoints.md`
- No code, no server inspection
