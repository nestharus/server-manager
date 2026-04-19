# AI Roadmap — Decomposition Risk Assessment

**Rating: LOW**

The AI roadmap decomposes the engineering roadmap into 78 work units with concrete Pydantic/endpoint contracts, directory-scoped test boundaries that reference only `contracts/` files, and code boundaries that contain the implementation surface needed to make those tests pass. Each work unit maps to a single PR. Cases where one WU covers multiple actions on a single aggregate are accompanied by explicit decomposition notes grounding the bundling in the "one versioned aggregate, one transition endpoint" rule that AGENTS.md's PR review would accept as non-splittable.

Findings below are observational (INFO) — they call out two cases that bundle submission and transition mutations on the same aggregate without a decomposition note, plus one WU that combines run creation with snapshot submission. None rise to MEDIUM because contracts remain concrete, test/code separation holds, and the bundled concerns in each case share a single versioned aggregate surface consistent with the justified pattern used elsewhere in the roadmap.

## Findings

### F-1. Single-concern test — bundled transitions are explicitly justified

**Severity: NONE**

Every work unit that combines creation and transitions on one aggregate carries a `Decomposition note` citing the shared versioned-aggregate boundary as the reason:

- WU-011 Member Aggregate And Status API — "same versioned member aggregate boundary" (`ai roadmap.md:481`)
- WU-012 Trust Profile And Initial Computation API — "single trust-profile capability with one contract surface" (`ai roadmap.md:501`)
- WU-022 Application Submission And Reviewer Ownership API — "same application aggregate and versioned lifecycle contract" (`ai roadmap.md:748`)
- WU-026 Discord Ticket Interaction Flow — "same thread-bootstrap, transcript-correlation, and command-routing surface" (`ai roadmap.md:902`)
- WU-028A Permission Drift Read And Resolution API — "read and mutation surface of the same drift resource" (`ai roadmap.md:944`)
- WU-035 Application Interview And Waitlist API — "same application state machine and versioned transition contract" (`ai roadmap.md:1207`)
- WU-037 Ticket SLA Evaluator And Escalation Worker — "one scheduled enforcement loop over the same ticket threshold contract" (`ai roadmap.md:1267`)

Each of these maps to the "single versioned aggregate, single transition endpoint" pattern. Under the AGENTS.md multi-concern PR review rule (`AGENTS.md:183`), splitting a versioned-transition endpoint by action does not produce independent concerns because the shared aggregate state, version check, and contract file would be co-modified by every split PR.

**Recommendation:** no action required.

---

### F-2. Contract concreteness — no prose contracts detected

**Severity: NONE**

Every work unit's `Contract:` block is a concrete listing of Pydantic model names (e.g., `MemberRead(id, discord_user_id, joined_at, status in ["active", "suspended", "departed"], version)` at `ai roadmap.md:470`), endpoint path+method signatures (e.g., `POST /api/v1/authority-grants -> AuthorityGrantRead` at `ai roadmap.md:534`), or typed handler signatures (e.g., `handler provision_chapter(command) -> ChapterProvisionResult` at `ai roadmap.md:697`). State-machine enums inline the allowed value set. No contract degrades to prose of the form "implement the trust system."

**Recommendation:** no action required.

---

### F-3. Test/code boundary separation is directory-scoped and clean

**Severity: NONE**

The roadmap's test boundary rule (`ai roadmap.md:21-26`) is enforced per WU: test boundaries list only files under `services/api/app/contracts/` or `services/discord/app/contracts/`. Code boundaries carry the migrations, repositories, services, endpoint, and test files needed to satisfy the contracts. Spot checks across phases:

- WU-015A Authority Enforcement Guard: test boundary `contracts/authority.py`, `contracts/audit.py`; code boundary adds `core/dependencies.py`, `services/authority.py`, `tests/test_authority_enforcement.py` (`ai roadmap.md:555-556`).
- WU-025A-events Ticket Initial Message Event Persistence: test boundary `contracts/ticket_messages.py`, `contracts/base.py`; code boundary adds `repositories/ticket_messages.py`, `services/ticket_messages.py` (`ai roadmap.md:841-842`).
- WU-028B-discord Discord Permission Snapshot Adapter: test boundary references only API and Discord `contracts/permissions.py`; code boundary adds `infrastructure/permission_client.py`, `handlers/permissions.py` (`ai roadmap.md:982-983`).

No test boundary references `services/`, `repositories/`, `infrastructure/`, or endpoint implementations. The test agent can author tests from the contract surface alone, satisfying AGENTS.md `111-140` and the Step 2 rule that test agents see contracts only.

**Recommendation:** no action required.

---

### F-4. Two WUs bundle aggregate creation and transitions without a decomposition note

**Severity: INFO**

WU-033 Roster Lifecycle API (`ai roadmap.md:1149-1168`) combines `POST /api/v1/roster-entries` (creation) and `POST /api/v1/roster-entries/{roster_entry_id}/transitions` (lifecycle mutation) into one unit, mirroring WU-011's structure but without an accompanying `Decomposition note`. WU-028B-api Permission Reconciliation Run API (`ai roadmap.md:949-969`) combines run creation and snapshot submission endpoints without a note.

Both match the same "single versioned aggregate, co-modified contract file" pattern the noted WUs rely on, so the underlying decomposition is consistent. The gap is documentary, not structural: a reader cross-referencing AGENTS.md's multi-concern PR rule against these two WUs has to re-derive the justification rather than read it inline.

**Recommendation:** add a `Decomposition note` to WU-033 and WU-028B-api pointing at the shared versioned-aggregate boundary, matching the style of WU-011 and WU-028A. Not a rating blocker — the structural decomposition already matches the justified pattern.

---

### F-5. Each work unit maps to a single PR under AGENTS.md's multi-concern rule

**Severity: NONE**

AGENTS.md PR review rule (`AGENTS.md:183-193`) mandates that any PR touching N independent concerns be split into N PRs, where independence is judged against the diff. A WU's diff scope is bounded by its code boundary. For every WU, the code boundary is a contiguous slice of one subsystem: one migration (where applicable), one contracts module, one repository, one service, one endpoint module, and one test file — or the Discord analog. No code boundary spans unrelated subsystems, and no WU's contract surface exposes concerns from two different aggregates without a dependency relationship. The multi-action transition endpoints flagged in F-1 remain single-concern at PR-review time because splitting them would co-modify the same contract, repository, and service files.

**Recommendation:** no action required.

---

## Summary table

| ID | Finding | Severity |
|----|---------|----------|
| F-1 | Bundled transitions carry explicit decomposition notes citing shared versioned aggregate | NONE |
| F-2 | All contracts are concrete Pydantic/endpoint/handler signatures; no prose contracts | NONE |
| F-3 | Test boundaries reference only `contracts/` directories; code boundaries contain implementation | NONE |
| F-4 | WU-033 and WU-028B-api bundle aggregate concerns without a decomposition note (documentary gap) | INFO |
| F-5 | Each WU maps to a single PR; code boundaries do not span unrelated subsystems | NONE |

## What LOW requires

- Every bundled-action WU continues to mutate a single versioned aggregate via a single contract file, so splitting would co-modify the same repository, service, and endpoint modules.
- Contracts remain stated as concrete Pydantic model names, endpoint path+method signatures, or typed handler signatures — no drift toward prose descriptions.
- Test boundaries remain restricted to files under `services/api/app/contracts/` or `services/discord/app/contracts/`. No WU adds `services/`, `repositories/`, `infrastructure/`, or endpoint implementation paths to its test boundary.
- Each WU's code boundary remains a contiguous slice of one subsystem (one contracts module + one repository + one service + one endpoint module, or the Discord analog), so the AGENTS.md multi-concern PR review would accept it as non-splittable.
- WU-033 and WU-028B-api are either split, or receive decomposition notes matching the style of WU-011 and WU-028A, before they enter the implementation pipeline.
