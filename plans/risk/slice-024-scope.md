# SLICE-024 Scope Risk: **LOW**

Rating: **LOW** — every step in the proposal maps to one of WU-044A / WU-044B / WU-045A-applications / WU-045A-tickets / WU-045B; no Alembic migration ships; succession never auto-triggers; transfer has no rollback path; no Discord surface is added; exactly four new authority permission names are introduced; the code footprint stays inside the `endpoints/authority/` subpackage plus the new handoff services plus the permitted `reassign` extensions in `services/applications.py` and `services/tickets.py`; no scope kinds and no service actors are added. PR seams are clean — every WU's file additions land in the PR the synthesis assigns them to. Three observations are recorded below that are not gate-failing: (1) the mechanical move of `endpoints/authority.py` into `endpoints/authority/lifecycle.py`, (2) repository helpers added to `chapter_roles.py` / `roster.py` / `applications.py` / `tickets.py` (SELECT-only, no writes), and (3) the `reassign` action being reachable through the general transition endpoints without `leadership_handoff.execute`. Each is spelled out below.

## SLICE-024 ACs (ticket)

1. A succession-triggering departure produces a queryable plan even when no successor is designated, and no automatic authority transfer occurs without that designation.
2. Authority transfer creates a new grant linked to the predecessor and reuses the existing grant lifecycle path instead of bypassing audit.
3. Application and ticket handoff executions are idempotent and write one causal chain linking departure, grant transfer, and each handoff action.
4. The leadership-context view reads from projection state and surfaces missing handoff state as an explicit stale-context signal rather than empty output.

---

## Findings per focus item

### Focus 1 — Every step maps to WU-044A / WU-044B / WU-045A-applications / WU-045A-tickets / WU-045B

**Verdict: PASS.**

| Proposal step | WU |
|---|---|
| §1 AC1 block — `SuccessionPlanRead` contract, plan service, `GET /chapters/{chapter_id}/succession-plan`, `test_succession_plan.py` | WU-044A |
| §1 AC2 block — `AuthorityGrantTransferRequest`, `transfer_authority_grant`, `find_successor_grant`, `POST /authority-grants/{grant_id}/transfer`, `test_authority_transfer.py` | WU-044B |
| §1 AC3 applications half — `reassign` action on applications, `leadership_handoff_applications.execute_handoff`, `POST …/handoff/applications`, `test_leadership_handoff_applications.py` | WU-045A-applications |
| §1 AC3 tickets half — `reassign` action on tickets, `leadership_handoff_tickets.execute_handoff`, `POST …/handoff/tickets`, `test_leadership_handoff_tickets.py` | WU-045A-tickets |
| §1 AC4 block — `LeadershipContextRead`, `read_leadership_context`, `GET /members/{member_id}/leadership-context`, `test_leadership_context.py` | WU-045B |

No step in §1–§8 (AC mapping, schema, contracts, repository, service, lifecycle extension, endpoints, tests) falls outside the five WUs. §11 PR decomposition collapses the five WUs into three PRs (A = WU-044A + WU-044B, B = WU-045A-applications + WU-045A-tickets, C = WU-045B) without adding new work.

### Focus 2 — No new schema migrations (D2)

**Verdict: PASS.**

- Proposal §2: "Per D2, SLICE-024 ships **zero** Alembic migrations. … Migration head remains `wu_038`."
- `AuthorityGrant.predecessor_grant_id`, `revoked_at`, `revoked_by`, `revocation_reason`, and `chapter_roles.triggers_succession` are confirmed present since earlier slices — no column additions required.
- Authority permission names are opaque service-layer strings; no registry table is introduced.
- Proposal §2 explicitly states that any Alembic file for this slice fails review, and an implementation-discovered need escalates to synthesis rather than silently adding a migration. Matches synthesis D2 exactly.

### Focus 3 — No auto-triggering succession (D15)

**Verdict: PASS.**

- Proposal §10 item 1: "Automatic succession triggering on role removal (roster hook, scheduled worker, Discord notification)." — explicitly out of scope.
- Plan endpoint is `GET`, computed live on request; no event hook fires transfer or handoff.
- Proposal §10 item 10: "`succession-worker` or other dedicated service actor." — out of scope (also covered by Focus 12).
- Proposal §10 item 5: "Persisted successor designation (`successor_designated` is always `False` this slice)." — reinforces that no mechanism exists in this slice to designate, schedule, or fire a transfer automatically.

### Focus 4 — No rollback of transfer (D15)

**Verdict: PASS.**

- Proposal §10 item 4: "Transfer rollback endpoint." — explicitly deferred.
- No inverse endpoint, service function, or request contract in §1/§3/§5/§7 reverses a completed transfer. Reversal would require a separate operator action path (re-grant + re-revoke) that the proposal does not provide.

### Focus 5 — No Discord interactions (ticket)

**Verdict: PASS.**

- Ticket Technical Specification: "Discord interactions: — none directly in this slice."
- Proposal §10 item 8: "Discord messages/embeds for succession events." — out of scope.
- No `services/discord/` path appears anywhere in §3–§8. All endpoints are in `services/api/app/api/v1/endpoints/authority/`.

### Focus 6 — Exactly 4 new authority permissions (D4)

**Verdict: PASS.**

Proposal §9 constants table and §1/§5 authority checks enumerate exactly four new permission strings:

1. `succession_plan.read` — gates `compute_succession_plan` at chapter scope (§1 AC1 block, §5).
2. `authority_grant.transfer` — gates `transfer_authority_grant` at the predecessor grant's scope (§1 AC2 block, §5).
3. `leadership_handoff.execute` — gates both `execute_handoff` services (applications and tickets) at the grant's scope (§1 AC3 block, §5).
4. `leadership_context.read` — gates `read_leadership_context` at global scope (§1 AC4 block, §5).

No fifth permission is introduced. No wildcard or hierarchy is added. No registry migration is proposed. Proposal §9's "no cross-slice permission registry is created" line aligns with synthesis D4's "names-only, no seeding."

### Focus 7 — Code boundaries: `endpoints/authority/` subpackage + new services + `reassign` extension in apps/tickets services; no writes to chapters or roster services

**Verdict: PASS.**

- `endpoints/authority/` subpackage (§7 package layout):
  - `__init__.py` (aggregator router)
  - `_shared.py` (moved helpers from the old single-file module)
  - `lifecycle.py` (moved verbatim from existing `endpoints/authority.py`)
  - `succession_plan.py`, `transfer.py`, `handoff_applications.py`, `handoff_tickets.py`, `leadership_context.py` (the five new endpoints)
- New services (per §5): `services/leadership_handoff_applications.py`, `services/leadership_handoff_tickets.py` (new modules), plus additive functions in `services/authority.py` (`compute_succession_plan`, `transfer_authority_grant`) and `services/read_models.py` (`read_leadership_context`).
- `reassign` extension in apps/tickets services (§6): `services/applications.py` gains the `reassign` action in its registry + `VALID_TRANSITIONS`; `services/tickets.py` gains the `reassign` action that bypasses category state-machine edge validation. Both are scoped to ownership-only mutation; no state change.
- **No writes to `services/chapters.py` or `services/roster.py`.** §4 adds read-only helpers to `repositories/chapter_roles.py` (`list_succession_triggering_roles`) and `repositories/roster.py` (`list_holders_for_roles`), explicitly annotated "All repository helpers are single-query and SELECT-only. Mutations flow only through service-layer `mutate_entity` calls." Chapter and roster service layers are untouched.

Observation (not gate-failing): the ticket's Work Units table lists a narrower Code Boundary per WU (contracts + dedicated service + endpoint + test). The proposal correctly expands this with repository helpers and the `reassign` extension in the existing services. This is the minimum infra glue required by the binding synthesis decisions (D5, D7, D8, D10, D12), parallel to the SLICE-021 scope precedent, and Focus 7 itself authorizes the `reassign` extension.

### Focus 8 — Migration chain stays `wu_038` (no new migration)

**Verdict: PASS.**

- Proposal §2: "Migration head remains `wu_038`."
- "Migration chain" subsection: "Current head: `wu_038` (SLICE-020 temporary permission lifecycle). SLICE-024 does not advance the head (D2). If implementation discovers an unavoidable migration, revisit synthesis before adding it; the candidate name would be `wu_044_leadership_succession`."
- No revision import of a new migration module appears in §2 or §5.

### Focus 9 — PR decomposition seams clean; flag if any single WU's changes cross the seam

**Verdict: PASS.**

Seam map:

| File | WU-044A | WU-044B | WU-045A-apps | WU-045A-tickets | WU-045B |
|---|---|---|---|---|---|
| `contracts/authority.py` | `SuccessionPlanRead`, `DepartingRoleEntry`, `PendingApplicationRef`, `PendingTicketRef` | `AuthorityGrantTransferRequest`, `SUCCESSION_TRANSFER_REVOCATION_REASON`, `GrantAlreadyTransferredError`, `NonBlankReasonRequiredError` | `ApplicationHandoffRequest`, `ApplicationHandoffResult` | `TicketHandoffRequest`, `TicketHandoffResult` | — |
| `contracts/applications.py` | — | — | reassign constants | — | — |
| `contracts/tickets.py` | — | — | — | reassign constants | — |
| `contracts/read_models.py` | — | — | — | — | `InheritedFromEntry`, `StaleHandoffEntry`, `LeadershipContextRead` |
| `repositories/authority.py` | `list_active_grants_for_members` | `find_successor_grant` | — | — | `list_active_grants_for_member`, `fetch_predecessor_grants` |
| `repositories/chapter_roles.py` | `list_succession_triggering_roles` | — | — | — | — |
| `repositories/roster.py` | `list_holders_for_roles` | — | — | — | — |
| `repositories/applications.py` | `list_open_applications_for_owners_in_scope` (also reused by 045A-apps, 045B) | — | (reuses A) | — | (reuses A) |
| `repositories/tickets.py` | `list_open_tickets_for_owners_in_scope` (also reused by 045A-tickets, 045B) | — | — | (reuses A) | (reuses A) |
| `services/authority.py` | `compute_succession_plan` | `transfer_authority_grant` | — | — | — |
| `services/applications.py` | — | — | `reassign` action | — | — |
| `services/tickets.py` | — | — | — | `reassign` action | — |
| `services/leadership_handoff_applications.py` | — | — | **new module** | — | — |
| `services/leadership_handoff_tickets.py` | — | — | — | **new module** | — |
| `services/read_models.py` | — | — | — | — | `read_leadership_context` |
| `endpoints/authority/succession_plan.py` | **new** | — | — | — | — |
| `endpoints/authority/transfer.py` | — | **new** | — | — | — |
| `endpoints/authority/handoff_applications.py` | — | — | **new** | — | — |
| `endpoints/authority/handoff_tickets.py` | — | — | — | **new** | — |
| `endpoints/authority/leadership_context.py` | — | — | — | — | **new** |

Cross-WU sharing all lands on additive-only surfaces:
- `contracts/authority.py` — each WU adds different symbols; no collision, no redefinition.
- `repositories/authority.py` — WU-044A, WU-044B, WU-045B each add disjoint helpers.
- `repositories/applications.py` / `repositories/tickets.py` — WU-044A introduces the helpers; WU-045A-* and WU-045B reuse them (no duplication, no redefinition).

PR seam map (per proposal §11):
- **PR A** (WU-044A + WU-044B): contained within `endpoints/authority/*`, `services/authority.py`, `contracts/authority.py`, `repositories/authority.py`, `repositories/chapter_roles.py`, `repositories/roster.py`, `repositories/applications.py`, `repositories/tickets.py`. Includes the mechanical move of the existing single-file `endpoints/authority.py` into `endpoints/authority/lifecycle.py` plus subpackage `__init__.py` / `_shared.py`.
- **PR B** (WU-045A-applications + WU-045A-tickets): bundles apps and tickets handoff because they share `leadership_handoff.execute` and the handoff service pattern. Each half stays inside its own subsystem (apps reaches only into `services/applications.py` + `services/leadership_handoff_applications.py` + `endpoints/authority/handoff_applications.py`; tickets the same on the ticket side). No file is written by both halves.
- **PR C** (WU-045B): contained within `services/read_models.py`, `contracts/read_models.py`, `repositories/authority.py` (new functions only), `endpoints/authority/leadership_context.py`. Depends on PR B's `reassign` landing for the `is_stale → False` test to be meaningful.

No single WU writes into a seam that another WU owns. The one reused-cross-WU surface (`repositories/applications.py` / `tickets.py` helpers) is additive and shared by clean import, not modification.

**Observation 1 (LOW)** — Mechanical subpackage move. Proposal §7 notes that since Python cannot have a module and a subpackage with the same name, converting `endpoints/authority.py` → `endpoints/authority/` requires moving the existing create/list/revoke handlers verbatim into `endpoints/authority/lifecycle.py` and extracting shared helpers (`_parse_if_match`, `_error_body`, `_db`) into `endpoints/authority/_shared.py`. This move is additive-and-mechanical (the proposal explicitly says "not a rewrite" and D13 forbids rewriting the lifecycle handlers). It is bundled into PR A. It is outside WU-044A's enumerated Code Boundary in the ticket's Work Units table but is a structural precondition for every endpoint under Focus 7. Not a scope violation; noting it because a reviewer reading only the ticket table may flinch at the diff size in PR A.

### Focus 10 — `reassign` action added to applications + tickets `VALID_TRANSITIONS`; no other state machine changes

**Verdict: PASS.**

- Applications (§6, synthesis D12): `reassign` is added to the action registry and to `VALID_TRANSITIONS` with source state == destination state for each of the six open states (`submitted`, `queued`, `claimed`, `in_review`, `interview`, `waitlisted`). Payload allowlist is `{"new_owner_id"}`. No existing edge is altered, no new state is added, and terminal-state reassignment is rejected by the existing `VALID_TRANSITIONS` check.
- Tickets (§6, synthesis D8/D12): `reassign` is added to the ticket action registry. Its validity rule is `terminal_at IS NULL`, and it deliberately bypasses the per-category `category_state_machine` edge lookup. `owner_id` is updated, `state`, `category_id`, and `category_snapshot` are all left unchanged. One `ticket_transitions` row is written per call with `from_state == to_state`.
- No changes to any other application or ticket action, edge, state enum value, or payload allowlist.

One construction detail: for tickets, `VALID_TRANSITIONS` in the existing code is a per-category concept (category_state_machine), not a single global table. The proposal's bypass matches synthesis D12's instruction: "Tickets: reassign is valid from any non-terminal state (terminal_at IS NULL); destination state equals source state." The binding language is "no other state machine changes," which holds — no category-state-machine edges are added, modified, or removed.

### Focus 11 — No new scope kinds

**Verdict: PASS.**

All authority checks in §1/§5 use existing scope kinds only:
- `succession_plan.read` → `scope_kind="chapter"` (existing).
- `authority_grant.transfer` → `scope_kind=predecessor.scope_kind` (derived from the existing grant; always a shipped scope kind).
- `leadership_handoff.execute` → `scope_kind=grant.scope_kind` (same derivation).
- `leadership_context.read` → `scope_kind="global"` (existing).

Scope kinds stored on the item itself (applications' `form_snapshot.target_scope_kind`, tickets' `category_snapshot.routing_scope_kind`) are filtered against but never invented. No `Literal[...]` union on scope_kind fields is extended anywhere in §3 contracts.

### Focus 12 — No service actors

**Verdict: PASS.**

- Proposal §10 item 10: "`succession-worker` or other dedicated service actor." — explicitly out of scope.
- Proposal §2: "No new … service-actor seeds are introduced."
- §5/§7 all endpoint + service entries derive actor from `Depends(get_current_actor)` → `ActorIdentity` threaded into the existing ambient audit context. No `SERVICE_ACTOR_ID` constant appears in §9.
- Synthesis D15 item 10 anchors this: "Transfer/handoff are operator-triggered; no `succession-worker` actor is seeded."

---

## Observations (non-gating)

1. **Mechanical subpackage move bundled into PR A** — already covered under Focus 9 Observation 1. Worth flagging for the PR reviewer but does not alter the slice's scope.

2. **Repository helpers added outside the ticket's per-WU Code Boundary column** — `repositories/chapter_roles.py`, `repositories/roster.py`, `repositories/applications.py`, and `repositories/tickets.py` each gain SELECT-only helpers in §4. These files are not listed in the ticket Work Units table's Code Boundary cells but are the minimum data-access surface required by synthesis D5, D7, D8, D10. No writes against roster, chapters, or the mutable aggregates originate from these helpers. Same pattern as SLICE-021 scope report §3 ("minimum infra glue with D-backing"). Not a gate fail.

3. **`reassign` action reachable through the general transition endpoints** — Proposal §6 discloses: "The action is still reachable via the general `POST /api/v1/applications/{id}/transition` and `POST /api/v1/tickets/{id}/transition` endpoints if a caller names the action explicitly; gating those broader endpoints on `leadership_handoff.execute` authority is out of scope for this slice. The handoff endpoints gate authority, and no other shipped caller invokes `reassign` today." This is an audit-surface concern (the Audit risk agent's territory) rather than a scope concern, because within SLICE-024 the only shipped caller is the handoff service, which is authority-gated. The disclosure is explicit and the proposal does not lean on it silently. Recording it so the audit reviewer sees it surfaced here as well.

4. **Authority gating mechanics land at the service layer, not via `RequireAuthority(...)` FastAPI dependency** — Synthesis D4 language ("Each new endpoint wires `RequireAuthority("<permission>", scope=...)` via the existing dependency pattern") and proposal §7 language ("no endpoint here uses a FastAPI-level `RequireAuthority(...)` dependency … services call `_require_scoped_authority` internally per D4") diverge on mechanism but converge on outcome: every endpoint is authority-gated. Proposal §7 justifies the divergence against research §3 (existing authority endpoints do not declare a `RequireAuthority` dep) and the SLICE-017 precedent. Synthesis D4's binding content is the *four permission names + the scope each is checked at*, which the proposal honors. Mechanics of where the gate is enforced is permitted to vary per synthesis preamble ("Mechanics may vary inside those boundaries; scope and shape may not.").

5. **Handoff endpoints omit `If-Match`** — Proposal §7 "Per-item error model" explains that handoff batches do not take a request-level `If-Match`; per-item OCC runs without caller-supplied `expected_version`. A stale-item failure surfaces as a batch 409 with partial-progress accounting. This is a deliberate design (otherwise the batch cannot be retried cleanly) and matches synthesis D7/D9 idempotency semantics. Not a scope issue; noting it so the audit and shortcut reviewers can corroborate.

---

## Summary

| Focus | Verdict |
|---|---|
| 1. Every step maps to the five WUs | PASS |
| 2. No new schema migrations | PASS |
| 3. No auto-triggering succession | PASS |
| 4. No rollback of transfer | PASS |
| 5. No Discord interactions | PASS |
| 6. Exactly 4 new authority permissions | PASS |
| 7. Code boundaries (subpackage + new services + reassign extension; no chapter/roster writes) | PASS |
| 8. Migration chain stays `wu_038` | PASS |
| 9. PR decomposition seams clean | PASS |
| 10. `reassign` in VALID_TRANSITIONS; no other state-machine changes | PASS |
| 11. No new scope kinds | PASS |
| 12. No service actors | PASS |

**Scope risk: LOW.** Proposal is shippable as-is from a scope perspective. Observations 1–5 are recorded so they surface at PR-review time; they do not warrant a synthesis revision.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
