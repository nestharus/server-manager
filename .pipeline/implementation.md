# SLICE-018 Phase 5+6 Implementation

## Summary

Implemented both work units from final proposal revision 1:

- WU-033: roster lifecycle API with chapter-scoped user authority, service-only sync-failure reporting, OCC via `If-Match`, roster transition projection rows, partial current-entry uniqueness, and atomic deferred-effect enqueue.
- WU-034: Discord roster role sync handler with name/ID role resolution, idempotent add/remove behavior, deferred acknowledgement support, and API-backed sync-failure reporting as `roster-syncer`.

## Files Touched

### CREATE

- `migrations/versions/wu-033_roster.py`
- `services/api/app/api/v1/endpoints/roster.py`
- `services/api/tests/test_roster.py`
- `services/discord/app/contracts/roster.py`
- `services/discord/app/handlers/roster.py`
- `services/discord/tests/test_roster_sync.py`

### MODIFY

- `.pipeline/implementation.md`
- `services/api/app/api/v1/router.py`
- `services/api/app/contracts/roster.py`
- `services/api/app/repositories/roster.py`
- `services/api/app/services/roster.py`
- `services/api/tests/conftest.py`

### DELETE

- `services/api/tests/test_roster_foundation.py`

## Test Results

- `cd /home/nes/projects/server-manager/worktrees/slice-018/services/api && uv run pytest tests/ -q`
  - `354 passed, 1 warning`
- `cd /home/nes/projects/server-manager/worktrees/slice-018/services/discord && uv run pytest tests/ -q`
  - `59 passed, 20 warnings`

## Grep Invariants

Verified zero matches in implementation files:

```bash
rg -n "def insert_roster_entry\(|def fetch_roster_entry\(|def update_roster_status\(|def read_roster_entry\(|def transition_roster_status\(|roster-service|system/roster-service" services/api/app services/discord/app migrations -g '!**/.venv/**'
```

Result: no matches.

## Deviations

- Added optional `ack_deferred` to `RosterSyncEvent` so `sync_roster` can satisfy the explicit phase constraint that deferred acknowledgement happens before API/Discord work. This is additive to the proposal contract and does not change API persistence behavior.
- No intentional deviations from the revision 1 authority split, OCC requirements, state machine, transition projection, partial unique index, service actor identity, or deferred-effect enqueue semantics.

## Notes

- `.pipeline/proposal.md`, `.pipeline/synthesis.md`, `.pipeline/research.md`, and `plans/risk/slice-018-*.md` were treated as inputs. Existing unstaged input-file changes were left intact.
