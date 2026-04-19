# AI — Dependency Risk Assessment

**Rating: LOW**

## Findings

### F-1. Dependency graph is acyclic and topologically consistent with declared cohorts

**Severity: NONE**

I extracted the dependency edges for all 78 work units in `product-strategy/ai roadmap.md` and performed a topological walk. The declared cohort ordering in the Dependency Graph section is internally consistent:

- Phase 0 cohorts (`[WU-001 + WU-009A + WU-009B]` → `[WU-002 + WU-010A + WU-010B]` → `[WU-003 + WU-010C]` → `[WU-003B + WU-004 + WU-005 + WU-006A + WU-007A + WU-007B + WU-008A + WU-009C + WU-009D + WU-010D + WU-010E]` → `[WU-006B + WU-007C + WU-008B]`) respect every per-unit `Dependencies:` clause.
- Phase 1 cohorts: WU-011/WU-014 depend only on Phase 0 items; WU-012/WU-015A depend on WU-011/WU-014 respectively; WU-013 depends on WU-011 + WU-012 (prior cohort); WU-015B and WU-016A depend on WU-015A (prior cohort); WU-016B and WU-017 depend on WU-016A (prior cohort).
- Phase 2 cohorts: all six cohort-2 units (`WU-019, WU-022, WU-025A-create, WU-028A, WU-029B-materialize, WU-030B`) declare only cohort-1 or earlier Phase 0/1 dependencies. `WU-028B-api` correctly sits alone in cohort 3 because it depends on cohort-2 `WU-028A`. Cohort-4 and cohort-5 units similarly point back, not sideways.
- Phase 3 and Phase 4 cohorts follow the same pattern. `WU-041B`, `WU-045A-applications`, `WU-045A-tickets` all point at cohort-3 Phase-4 items and no further forward. `WU-045B` terminates the graph.

No work unit transitively depends on itself. The critical path claim of 19 units (`WU-001 → WU-002 → WU-003 → WU-008A → WU-008B → WU-014 → WU-015A → WU-016A → WU-017 → WU-024 → WU-025A-create → WU-025B → WU-025C → WU-033 → WU-034 → WU-039 → WU-040A → WU-041A → WU-041B`) is the longest gated chain when phase-boundary gates (`Phase N must complete before Phase N+1`, declared in the engineering roadmap) are treated as edges. Three transitions in that chain (`WU-008B → WU-014`, `WU-025C → WU-033`, `WU-034 → WU-039`) are phase-boundary edges rather than declared per-unit dependencies — which is correct because the AI roadmap inherits the engineering roadmap's phase-boundary gating.

**Recommendation:** No action required.

---

### F-2. Contracts match across declared dependency edges

**Severity: NONE**

Spot-checking each load-bearing edge, the upstream work unit's declared contract output matches what the downstream work unit consumes:

- `WU-002` outputs `VersionedRead`, `MutationRequest`, `MutationResult`; every API unit that cites it for "version base" reuses `expected_version` / `version` fields and returns `412 Precondition Failed`, which matches the `MutationRequest` contract shape.
- `WU-003` outputs `CorrelationHeadersRead`, `AuditContextRead`, `AuditEntryRead`; `WU-003B` reuses `correlation_id` / `causation_id` on `NotificationEventRead`; `WU-016A` returns `list[AuditEntryRead]` and `AuditEntryRead`; `WU-009C` and `WU-009D` thread `correlation_id` through their interaction / transport envelopes.
- `WU-004` outputs `AuthorityGrantRead`, `AuthorityRequirement`; `WU-014` returns `AuthorityGrantRead` from `POST /api/v1/authority-grants` and `/revoke`; `WU-015A` emits `AuthorityDecisionRead`; `WU-044B` references the same `AuthorityGrantRead` shape for transfer.
- `WU-005` outputs `PolicyPreviewRequest`, `PolicyPreviewRead`, `PolicyVersionRead`; `WU-017` consumes and returns those exact models via `POST /api/v1/policies/preview` and `/confirm`. Downstream policy consumers (`WU-018, WU-021, WU-024, WU-029A, WU-039`) explicitly flag their WU-017 dependency as "runtime dependency… does not consume policy contract types," which correctly models a behavioral rather than type-level coupling.
- `WU-006A` outputs `PermissionIntentRead`; `WU-027` returns it, `WU-038A` renews it, `WU-028A` ties drift back to intent IDs.
- `WU-006B` outputs `PermissionDriftRead`; `WU-028A` returns it from `GET /api/v1/permission-drift` and resolves it with `DriftResolutionRequest`.
- `WU-007A/B/C` outputs (`ChapterTemplateRead`, `ChapterRoleRead`, `RosterEntryRead`) are consumed by `WU-018`, `WU-020` and `WU-033` respectively, with matching field sets (channel/role structure, ordinal + succession flag, chapter/member/role/status).
- `WU-008A` `ScheduledJobRead` is consumed by every scheduled-handler unit (`WU-029B-deliver, WU-031, WU-037, WU-038B, WU-041B`). `WU-008B` `DeferredEffectRead` / `DegradedStateSummaryRead` is consumed by `WU-020, WU-032, WU-034, WU-043A, WU-043B`.
- `WU-028B-api` consumes `PermissionScopeSnapshotWrite`; `WU-028B-discord` produces `PermissionScopeSnapshotRead` and submits it through the API contract. The Write/Read pair shares the same `scope_kind, scope_id?, role_permissions, channel_permissions` field set — compatible at the JSON wire level.
- `WU-029B-materialize` consumes `NotificationEventRead` (WU-003B output) and emits `NotificationEnvelopeRead`, which `WU-029B-deliver` (and via `WU-029C`) forwards without shape change.
- `WU-044A` / `WU-044B` / `WU-045A-*` / `WU-045B` align on `predecessor_grant_id`, `AuthorityGrantRead`, and `application_ids` / `ticket_ids` across the succession chain.

No contract mismatch would cause a runtime failure across a declared edge.

**Recommendation:** No action required.

---

### F-3. Parallelization claims hold under dependency-edge and file-overlap checks

**Severity: NONE**

For every cohort I confirmed: (a) no declared dependency edge crosses between two units listed as parallel, (b) code-boundary file sets do not overlap within a cohort, (c) migration-writing units are reconciled by the explicit Alembic merge rule called out in the Parallelization Map.

Concrete spot checks:

- Phase 0 cohort 4 (11 units): `WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-008A` each write a distinct contracts file (`notifications.py`, `authority.py`, `policies.py`, `permissions.py`, `chapter_templates.py`, `chapter_roles.py`, `scheduler.py`); `WU-009C, WU-009D, WU-010D, WU-010E` write distinct Discord / runtime files. No overlap with each other or with cohort 3's `WU-003` (audit) / `WU-010C` (runtime factory).
- Phase 0 cohort 5: `WU-006B` writes back into `permissions.py`, `WU-007C` into `roster.py`, `WU-008B` into `scheduler.py` — all sequential-after-cohort-4 rewrites of the same files are fine because cohort 5 starts after cohort 4 closes.
- Phase 2 cohort 4 (8 units): `WU-020, WU-023a, WU-023b, WU-028B-discord` each write distinct Discord handler files; `WU-025A-events, WU-025B, WU-029B-deliver, WU-032` write distinct API service files (`ticket_messages.py` / `tickets.py` / `notifications*.py` / `read_models.py`). No shared mutable file within the cohort.
- Phase 3 cohort 2: `WU-034` (roster sync, Discord), `WU-036a` (interview thread), `WU-036b` (waitlist), `WU-038B` (permission expiry worker in API) — four disjoint file sets.
- Phase 4 cohort 3: `WU-040B-extract` (`compliance_extraction.py`), `WU-040B-correct` (`compliance_corrections.py`), `WU-041A` (`compliance.py`, `compliance_review.py`), `WU-043B` (`chapters.py`, `archive.py`), `WU-044B` (`authority.py`, `authority/transfer.py`) — disjoint.

Test fixtures come from two harness units (`WU-009A` API, `WU-009B` Discord) that each publish contract-only fixture interfaces; per-unit test files live in a per-unit module (`tests/test_*.py`), so no shared mutable fixture file exists within any cohort.

**Recommendation:** No action required.

---

### F-4. AI decomposition structure is consistent with engineering roadmap

**Severity: NONE**

Phase-level structure matches exactly: AI Phase 0 ↔ engineering Phase 0 Foundations; AI Phase 1 ↔ engineering Phase 1 (VS-001..VS-004); AI Phase 2 ↔ engineering Phase 2 (VS-005, 006, 007, 008, 009, 010, 015); AI Phase 3 ↔ engineering Phase 3 (VS-011..VS-014); AI Phase 4 ↔ engineering Phase 4 (VS-016..VS-018). All 18 value slices are present and each has at least one work unit under it. The `Phase N must complete before Phase N+1` gate from engineering is honored by the cohort ordering.

Internal cohort dependencies introduced by the AI decomposition (e.g. `WU-028B-api` sitting alone between two Phase-2 cohorts; `WU-025C` / `WU-026` / `WU-029C` being held to a final Phase-2 cohort 5 because they depend on message-event substrate and notification-delivery worker) do not contradict the engineering roadmap's cross-slice ordering — they're within-phase and respect the acknowledged strategic bottleneck slices (`VS-002`, `VS-008`, `VS-016`) noted in the engineering critical path summary.

**Recommendation:** No action required.

---

### F-5. API→Discord delivery dispatch path is implicit, not a dependency defect

**Severity: INFO**

`WU-029C` (Discord notification delivery adapter) declares a dependency on `WU-029B-deliver` (API scheduled delivery worker). The API worker iterates envelopes and the Discord adapter consumes them, but the wire mechanism (pull, queue, HTTP push) is not fixed at this roadmap layer. This is a design question the `WU-029C` proposal phase will resolve via AGENTS.md research → proposal. It is not a contract mismatch or missing edge at the dependency-graph layer: both units share the `NotificationEnvelopeRead` contract as the canonical handoff type and the declared edge correctly orders them.

**Recommendation:** No action required at this layer. Flagged for the `WU-029C` implementation-phase proposal to select an explicit transport.

---

## Summary table

| ID | Finding | Severity |
|----|---------|----------|
| F-1 | Graph acyclic; cohort topological order valid; 19-unit critical path correct including phase-boundary edges | NONE |
| F-2 | Contract types match across every declared dependency edge | NONE |
| F-3 | Parallelization claims have no dependency-edge or shared-mutable-file conflicts | NONE |
| F-4 | AI phase / cohort structure consistent with engineering roadmap | NONE |
| F-5 | `WU-029C` API→Discord dispatch path is a proposal-phase design question, not a dependency defect | INFO |

## What LOW requires

- Every declared `Dependencies:` clause in `ai roadmap.md` points backward to a work unit in an earlier cohort (or earlier phase).
- No cycle exists in the dependency graph.
- For every dependency edge `A → B`, `A`'s declared `Contract:` output includes the type(s) `B`'s `Contract:` references as input.
- For every cohort, no two units in the cohort have a direct or transitive dependency edge between them.
- For every cohort, no two units write to the same file in their `Code boundary:` list.
- Migration-writing units within a cohort are reconciled by the Alembic merge rule stated in the Parallelization Map.
- All 18 engineering value slices appear in the AI work unit inventory and the AI phase assignments match engineering phase assignments.
- Within-phase dependencies introduced by the AI decomposition do not contradict the engineering roadmap's cross-slice strategic bottlenecks (`VS-002`, `VS-008`, `VS-016`).
