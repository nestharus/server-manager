# SLICE-014 Justification Review

**Verdict: LOW_CONCERN**

Every implementation decision in PR #60 traces to a binding input (AC1–4,
D1–D15, shortcut F1/F4/F5 resolutions, or a shipped prior-slice precedent).
Two minor deviations are called out below:

- **M1** — `_build_drift_rows` adds `kind` as the primary sort key, whereas
  synthesis D8 step 7 binds `(role_id, channel_id or "")`. This was already
  flagged as shortcut F3 (LOW, discretionary polish). Determinism is
  preserved, but the binding prose is not honored verbatim.
- **L1** — `_record_drift_created` still uses the inline literals
  `"permission_drift.create"` / `"permission_drift.created"`. This was
  acknowledged by both audit Finding 1 and shortcut F1 as LOW (matches the
  shipped single-use-create precedent at
  `services/api/app/services/permissions.py:140, 227-239`); the class of
  bug the dispatch dicts forbid (f-string generation) cannot occur at a
  single-action site.

No other implementation choice lacks justification. Each migration file,
state-machine edge, service-layer gate, return-shape choice, replay
behavior, actor spoof rule, constants dispatch, non-goal, scope
discipline, grant, aggregate strategy, and mask type traces directly to a
binding input.

---

## Findings

### 1 — Migration design (three separate migrations, pre-narrow guard, two partial unique indexes)

- **Severity.** LOW
- **Decisions referenced.**
  - `migrations/versions/wu-027_permission_intents_refinements.py:14-45`
    (scope-narrow guard + CHECK swap)
  - `migrations/versions/wu-028a_permission_drift_widening.py:16-32`
    (pre-widening orphan guard), `:34-155` (column/constraint/index adds)
  - `migrations/versions/wu-028b_permission_reconciliation_runs.py:25-121`
    (run table + FK + two partial unique indexes)
- **Expected justification.**
  - **Three separate migrations**: synthesis D14 binds
    `wu_027 → wu_028a → wu_028b` chained from `wu_035_application_interview`
    with rollback granularity per WU boundary (`synthesis.md:806-845`).
  - **Pre-narrow guard for `scope_kind='member'`**: D1 binding implications
    verbatim (`synthesis.md:86-103`) — "migration refuses to run instead"
    of trying to migrate hypothetical member rows.
  - **Partial unique indexes (2 not 1)**: D3 explicitly calls out the
    Postgres NULL-equality caveat (`synthesis.md:214-223`); two disjoint
    partial indexes are required because `channel_id` may be NULL for
    guild-role drift and Postgres treats two NULL values as distinct.
- **Actual justification in the diff.**
  - wu-027 upgrade body matches D1 verbatim including the exception
    message text (`synthesis.md:92-98` vs migration :17-28).
  - wu-028a upgrade body matches D2 orphan guard verbatim
    (`synthesis.md:180-193` vs migration :17-32).
  - wu-028b creates the two partial unique indexes with the exact
    predicate shapes D3 binds (`WHERE reconciliation_run_id IS NOT NULL
    AND channel_id IS [NOT] NULL`, migration :106-121 vs
    `synthesis.md:208-223`).
  - Chain: wu-027 down_revision = `wu_035_application_interview`
    (migration :9), wu-028a → wu-027 (:11), wu-028b → wu-028a (:11).
    Linear per D14.
  - Every `downgrade()` is a no-op with a Live-Server-Principle comment
    (wu-027:48-53, wu-028a:158-161, wu-028b:162-166) per D14 binding.
- **Action.** None.

---

### 2 — State machine extensions (VALID_DRIFT_TRANSITIONS + VALID_RUN_TRANSITIONS edges)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/services/permissions.py:56-62`
    (`VALID_DRIFT_TRANSITIONS`)
  - `services/api/app/services/permission_reconciliation.py:25-30`
    (`VALID_RUN_TRANSITIONS`)
  - `services/api/app/services/permissions.py:64`
    (`DRIFT_TERMINAL_STATUSES`)
  - `services/api/app/services/permission_reconciliation.py:32`
    (`RUN_TERMINAL_STATUSES`)
- **Expected justification.**
  - **Drift edges**: D5 binds `detected → {acknowledged, reconciled,
    accepted}` and `acknowledged → {reconciled, accepted}`; terminals
    `reconciled` and `accepted` (`synthesis.md:329-346`).
  - **Run edges**: D4 binds `requested → snapshot_submitted`,
    `snapshot_submitted → reconciled|failed`, and the reserved
    `requested → failed` edge for operator/system cancellation
    (`synthesis.md:297-304`). Terminals: `reconciled`, `failed`.
- **Actual justification in the diff.**
  - `VALID_DRIFT_TRANSITIONS` maps exactly the five D5 edges, keyed by
    `(from_state, action)` so that `action` maps through
    `DRIFT_RESOLUTION_TARGET_STATUS` (D6, `synthesis.md:385-393`).
  - `VALID_RUN_TRANSITIONS` maps exactly the four D4 edges. The
    `("requested", "fail")` entry is reserved per D4 binding and is
    currently only exercised by `_advance_run_failed` when the original
    transaction aborts before `submit_snapshot` has advanced the run (a
    `requested → failed` direct edge); the synthesis explicitly permits
    this as "operator/system cancellation only" and the proposal wires
    it through the same `_advance_run_failed` helper used post-submit.
  - `DRIFT_TERMINAL_STATUSES = frozenset({"reconciled", "accepted"})`
    matches D5 terminal set.
  - `RUN_TERMINAL_STATUSES = frozenset({"reconciled", "failed"})`
    matches D4 terminal set.
- **Action.** None.

---

### 3 — Service-layer authority (shortcut F5 resolution)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/services/permissions.py:125-144`
    (`_require_scoped_authority` helper)
  - Service call sites:
    `services/api/app/services/permissions.py:181-187` (create),
    `:246-252` (update), `:322-328` (list intents),
    `:365-371` (list drift), `:406-412` (resolve drift)
  - `services/api/app/services/permission_reconciliation.py:142-148`
    (create run), `:647-653` (submit snapshot)
  - Endpoints additionally short-circuit via `require_scoped` (e.g.
    `services/api/app/api/v1/endpoints/permissions/intents.py:54-57`).
- **Expected justification.** Shortcut F5 (MEDIUM, resolved) required
  authority move from endpoint-only to service-level so non-HTTP callers
  (background jobs, CLI) hit the same gate — resolution R5 at
  `slice-014-shortcut.md:170-177` / `slice-014-audit.md:16` (Focus 4).
  SLICE-023 precedent (applications) establishes the pattern.
- **Actual justification in the diff.** Every service entry point calls
  `_require_scoped_authority(permission, scope_kind, scope_id, actor=,
  db=)` BEFORE any `mutate_entity()` or read-side aggregation. Endpoints
  retain `require_scoped` as a 403 short-circuit but are no longer the
  sole gate.
- **Action.** None.

---

### 4 — Drift batch return shape (shortcut F4 resolution)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/repositories/permissions.py:317-348`
    (`insert_permission_drift_batch`)
  - Consumer:
    `services/api/app/services/permission_reconciliation.py:683-692`
    (iterates `new_drift_ids` only)
- **Expected justification.** Shortcut F4 (MEDIUM, resolved) required the
  repo primitive to return only *newly-inserted* ids so that
  `_record_drift_created` can use `expected_version=0` safely without
  colliding with an existing aggregate head on retry
  (`slice-014-shortcut.md:165-171` R4).
- **Actual justification in the diff.** The repository uses
  `INSERT ... ON CONFLICT DO NOTHING RETURNING id` per-row and appends
  only the non-None result, so conflict rows are silently dropped from
  the return list. The service loops `new_drift_ids` through
  `_record_drift_created(..., expected_version=0, ...)` (hard-coded inside
  `_record_drift_created` at `permission_reconciliation.py:623-624`), so
  the `expected_version=0` invariant holds for every id returned. The
  run's final drift set is read back via `list_drift_ids_by_run`
  (`:693-695`), decoupling the audit loop from the final read set.
- **Action.** None.

---

### 5 — Terminal replay returns cached drift list without re-diff (AC4)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/services/permission_reconciliation.py:655-664`
    (terminal early-return)
  - `:200-211` (`read_reconciliation_run` populates `drift_ids`)
- **Expected justification.** AC4 mandates snapshot adapter reuses the
  API run id as the idempotency key; D8 step 2
  (`synthesis.md:505-511`) binds idempotent replay for a retried POST by
  returning the cached drift list. Proposal §5.3 confirms no
  recomputation or re-insert on replay; shortcut Focus 15
  (`slice-014-shortcut.md:38`) pins the behaviour.
- **Actual justification in the diff.** For `status == "reconciled"`, the
  function early-returns the `existing` read (which already carries
  `drift_ids`) wrapped in a fresh `MutationResult(head_version, etag)` —
  no call to `_build_drift_rows`, `insert_permission_drift_batch`, or any
  `mutate_entity`. For `status == "failed"`, a
  `ReconciliationRunConflictError` is raised (409) matching D8 step 2's
  "propagate the original failure reason" rule. The pre-check is *above*
  the `with db.transaction()` block, so no new action or state-change
  rows are written on replay.
- **Action.** None.

---

### 6 — Spoof-proof originating actor (SLICE-021 precedent)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/services/permissions.py:385-393`
    (`_drift_originating_actor`)
  - `services/api/app/services/permission_reconciliation.py:92-102`
    (`_requested_by`)
  - `services/api/app/contracts/permissions.py:249-269`
    (`PermissionDriftResolutionRequest` incl. both-or-neither validator)
- **Expected justification.** D6 binds the SLICE-021 applications pattern
  (`services/api/app/services/applications.py:189-195`): when
  authenticated actor is `service`, honour body `resolved_by_*`;
  otherwise override with authenticated identity
  (`synthesis.md:394-409`). Both-or-neither validator added by R8(a)
  (`slice-014-shortcut.md:178-179`).
- **Actual justification in the diff.**
  - `_drift_originating_actor` matches D6 exactly: service actors may
    provide spoofed `resolved_by_*`; user actors collapse to
    authenticated identity.
  - `_requested_by` applies the same rule for run creation
    (`originating_actor_*` honoured only for service actors), matching
    D4 spoof-proofing called out in audit Focus 7
    (`slice-014-audit.md:32`).
  - `PermissionDriftResolutionRequest.validate_resolved_by_pair` enforces
    both-or-neither (R8a).
- **Action.** None.

---

### 7 — Constants dispatch over f-strings (shortcut F1 HIGH resolution)

- **Severity.** LOW (with acknowledged exception L1)
- **Decisions referenced.**
  - `services/api/app/services/permissions.py:72-81`
    (`DRIFT_RESOLUTION_ACTION_TYPE` / `DRIFT_RESOLUTION_CHANGE_TYPE`)
  - `services/api/app/services/permission_reconciliation.py:47-59`
    (`RUN_ACTION_TYPE` / `RUN_CHANGE_TYPE`)
  - Call sites:
    `permissions.py:444-445` (resolve drift),
    `permission_reconciliation.py:185, 252, 301, 354` (run advances)
  - **L1 — residual inline literals**:
    `permission_reconciliation.py:628` (`"permission_drift.create"`),
    `:607` (`"permission_drift.created"`);
    `services/api/app/services/permissions.py:518, 505` (the
    `create_permission_drift` helper — also inline).
- **Expected justification.** Shortcut F1 HIGH was the `.acceptd` typo
  from an f-string (`permission_drift.{action}d`); resolution R1
  required dispatch dicts (`slice-014-shortcut.md:153-156`). Proposal
  Revision 1 §10.1 / §10.2 add `DRIFT_RESOLUTION_*`, `RUN_*` dispatch
  dicts. Audit Finding 1 (`slice-014-audit.md:41-71`) acknowledges
  `_record_drift_created` retains the inline literal as an accepted
  single-action-site pattern matching shipped precedent
  (`services/api/app/services/permissions.py:140, 227-239`).
- **Actual justification in the diff.** All variable-action sites
  (`acknowledge`/`reconcile`/`accept`; `create`/`submit_snapshot`/
  `reconcile`/`fail`) dispatch through constant maps. The drift-create
  path uses inline literals exactly as the audit Finding 1
  precedent/acknowledgement permits — no f-string class of bug is
  possible because there is no variable substitution.
- **Action.** None required (audit / shortcut already accepted L1 as
  discretionary polish).

---

### 8 — Authority denial audit non-goal

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/services/permissions.py:143-144`
    (`raise PermissionError` without audit row)
  - `services/api/app/api/v1/endpoints/permissions/_shared.py`
    (endpoint `require_scoped` 403 short-circuit — no audit row)
  - Proposal §11 non-goal bullet (R9) — denial auditing deferred.
- **Expected justification.** Audit Focus 10
  (`slice-014-audit.md:35`): "authority-denial audit row (SLICE-008
  precedent)" was explicitly disambiguated by R9 — the shipped
  `RequireAuthority` precedent
  (`services/api/app/services/audit_overrides.py:13-56`) logs
  *overrides* but not plain denials. SLICE-014 inherits this. Any
  symmetric `record_authority_denial` would be a separate future slice.
- **Actual justification in the diff.** `_require_scoped_authority`
  raises `PermissionError("authority requirement denied")` with no call
  to `record_authority_override` or any audit helper. Endpoint
  `require_scoped` does the same. Behaviour matches the shipped
  `RequireAuthority` precedent — denials produce 403, no audit row.
- **Action.** None.

---

### 9 — Discord adapter scope discipline (D13)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/discord/app/handlers/permissions.py:47-62`
    (`_channels_for_scope`)
  - `:65-82` (`_guild_role_entries`)
  - `:85-109` (`_channel_role_entries`)
  - `:112-119` (`_build_snapshot`)
- **Expected justification.** D13 binds:
  - **chapter scope**: walk chapter channels only
    (`synthesis.md:774-781`); chapter-to-channel resolution matches
    existing chapter helper conventions.
  - **global scope**: roles only; do NOT walk per-channel overwrites
    (`synthesis.md:782-783`).
  - Cache-only (`guild.roles`, `guild.channels`,
    `channel.overwrites`) — no `fetch_*` (`synthesis.md:762-767`).
- **Actual justification in the diff.**
  - `_channels_for_scope` returns `[]` unconditionally when
    `scope_kind != "chapter"` (line 52-53) — global scope therefore
    never enumerates channels.
  - `_build_snapshot` unconditionally calls `_guild_role_entries` (D13
    permits this for both scopes) and then chains
    `_channel_role_entries`, which is gated by `_channels_for_scope`'s
    empty-return for non-chapter scope.
  - All reads go through attribute access (`getattr(guild, "roles",
    [])`, `getattr(channel, "overwrites", None)`, etc.); no
    `fetch_channel` / `fetch_member` calls appear.
  - Member-target overwrites are `continue`-skipped (`:94-95`); this is
    shortcut F2 (LOW, silent filter — scope is documented, no
    correctness impact for role targets) and acknowledged as
    discretionary polish.
- **Action.** None.

---

### 10 — Service actor grant (global-scope single grant covers chapter)

- **Severity.** LOW
- **Decisions referenced.**
  - `migrations/versions/wu-028b_permission_reconciliation_runs.py:16-21,
    123-159` (grant seed with exact `@>/<@` containment)
  - `services/discord/app/infrastructure/permission_client.py:18,
    80-84` (service-actor header injection)
- **Expected justification.** D9 binds a `permission-reconciler` grant
  with `scope_kind='global', scope_id=NULL` and the four permissions
  (`permission_intent.read`, `permission_drift.read`,
  `permission_drift.write`, `permission_reconciliation_run.write`).
  SLICE-008's authority-scope hierarchy means a global grant covers
  chapter-scoped operations (`synthesis.md:609-612`: "central reconciler
  is global-scoped; chapter-scoped authority is granted to operators
  through the existing authority API"). Exact bidirectional containment
  (`@>` AND `<@`) prevents collision with an operator-created identical
  grant (`synthesis.md:567-589`, matches WU-037 / WU-033 precedent).
- **Actual justification in the diff.**
  - Migration inserts the grant at `(scope_kind='global',
    scope_id=NULL)` with the exact four-permission JSONB array
    (`:16-21` constant, `:142` insert, `:153-154` existence guard).
  - Guard uses `@>` AND `<@` plus active-grant (`revoked_at IS NULL AND
    (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)`) —
    idempotent per D9.
  - `downgrade()` is a no-op with Live-Server-Principle comment
    (`:162-166`), matching D9 non-goal.
  - Discord client authenticates as `permission-reconciler` via
    `X-Actor-Kind: service` / `X-Actor-Id:` headers.
- **Action.** None.

---

### 11 — Per-drift aggregate vs run-scoped findings (D3)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/services/permissions.py:472-488`
    (`resolve_permission_drift` uses `aggregate_type="permission_drift",
    aggregate_id=str(drift_id)`)
  - `services/api/app/services/permission_reconciliation.py:619-635`
    (`_record_drift_created` — one `mutate_entity` per drift id)
  - Partial unique indexes: `wu-028b_permission_reconciliation_runs.py:
    106-121`.
  - No `permission_drift_findings` child table exists.
- **Expected justification.** D3 binds per-row drift aggregates with
  per-drift OCC (`synthesis.md:199-249`); routing resolution through a
  run aggregate would couple unrelated drift mutations. Run-scoped
  uniqueness expressed as partial unique indexes on
  `(reconciliation_run_id, role_id, kind, channel_id)` — two indexes
  for the Postgres NULL-equality caveat (covered under Finding 1).
- **Actual justification in the diff.**
  - `resolve_permission_drift` calls `mutate_entity` with
    `aggregate_type="permission_drift"` and `aggregate_id=str(drift_id)`
    — per-row aggregate per D3.
  - `_record_drift_created` issues one `mutate_entity` per newly-inserted
    drift id, each keyed by its own aggregate id — matches D3 "Per-drift
    aggregates" with `expected_version=0`.
  - Idempotency is expressed only via partial unique indexes; no
    `permission_drift_findings` table was introduced (scope Focus 12,
    `slice-014-scope.md:24`).
  - `fetch_permission_drift` + `update_permission_drift_resolution`
    operate per-row; no run-aggregate fallback.
- **Action.** None.

---

### 12 — Decimal-string mask preservation (D7)

- **Severity.** LOW
- **Decisions referenced.**
  - `services/api/app/contracts/permissions.py:18-28`
    (`_validate_decimal_bit_string`, `DecimalBitString`)
  - Intent + drift + snapshot contracts use `DecimalBitString` throughout
    (`:86, 92-93, 146, 152-153, 187-192, 308, 314-315`)
  - Service cleared-state literals:
    `services/api/app/services/permission_reconciliation.py:397-408`
    (`_cleared_actual_masks`: `"0"` for guild_role, `"0"`/`"0"` for
    channel_role)
  - Repository normalization:
    `services/api/app/repositories/permissions.py:13-48`
    (`db_value_to_bit_str`, `_normalize_permission_intent_row`,
    `_normalize_permission_drift_row`)
  - Discord adapter:
    `services/discord/app/handlers/permissions.py:20-23`
    (`_decimal_bits` int → str gateway)
- **Expected justification.** D7 binds decimal-bitset round-trip over
  `NUMERIC(39,0)` columns (`synthesis.md:461-471`): variant-shape
  contracts mirror WU-006a; Discord snapshots must encode decimal
  strings, not raw ints or hex. Cleared-state literals preserve the
  canonical `"0"` form.
- **Actual justification in the diff.**
  - Every mask field on contracts (intent create/read, drift read,
    snapshot entries) is typed `DecimalBitString`; the validator rejects
    empty string, non-digit, and leading-zero forms.
  - `_cleared_actual_masks` returns the exact cleared-state literals D8
    step 7 binds.
  - Repository converts `NUMERIC` back to decimal via
    `db_value_to_bit_str`, preserving canonical form without ever
    leaking ints through the contract boundary.
  - Discord int → string gateway `_decimal_bits(value)` calls
    `str(int(value))`, producing canonical decimals; all snapshot
    entries are populated through this helper.
- **Action.** None.

---

## Deviations (called out but not blocking)

### M1 — Sort key divergence in `_build_drift_rows`

- **Severity.** LOW
- **Location.**
  `services/api/app/services/permission_reconciliation.py:478-481`.
- **Expected justification.** Synthesis D8 step 7
  (`synthesis.md:518-520`) binds the sort key
  `sorted(union(intent_keys, snapshot_keys), key=(role_id, channel_id
  or ""))`.
- **Actual in the diff.** The code sorts by
  `key=lambda k: (k[0], k[1], k[2] or "")` where `k = (kind, role_id,
  channel_id)` — i.e. adds `kind` as the *primary* sort key, then
  `role_id`, then `channel_id or ""`.
- **Why it doesn't break any AC.** The ordering is still fully
  deterministic and stable. The two keys share a 1:1 mapping to
  `(kind, role_id, channel_id)` tuples (a key can only represent one
  kind), so `drift.id` allocation is reproducible across replays within
  a single environment. AC4 idempotent replay is unaffected (it short-
  circuits before the sort anyway). Shortcut F3
  (`slice-014-shortcut.md:117-142`) flagged this class of issue as LOW
  / discretionary: "D8 binds and is unambiguous; test fixtures can pin
  order with one explicit assertion. Missing prose is a
  spec-completeness gap, not a correctness defect."
- **Action.** Either (a) tighten the lambda to match D8 verbatim
  (`key=lambda k: (k[1], k[2] or "")` — drop `k[0]`), or (b) file a
  synthesis-amendment note that D8 step 7 accepts `(kind, role_id,
  channel_id or "")` as an equivalent stable order and move on. Current
  behaviour does not block the gate.

### L1 — Residual inline literal on drift-create audit path

- **Severity.** LOW
- **Location.**
  `services/api/app/services/permission_reconciliation.py:607, 628`
  (`"permission_drift.created"`, `"permission_drift.create"`);
  `services/api/app/services/permissions.py:505, 518-520`
  (the `create_permission_drift` helper — likewise inline).
- **Expected justification.** Audit Finding 1
  (`slice-014-audit.md:41-71`) and shortcut F1
  (`slice-014-shortcut.md:44-81`) both explicitly classify this as LOW
  / discretionary. The class of bug the dispatch dicts forbid (f-string
  generation of `.acceptd`) cannot occur at a single-action site. The
  shipped `create_permission_intent`
  (`services/api/app/services/permissions.py:140, 227-239`) uses the
  same inline pattern.
- **Action.** None required. Optional polish: promote the two strings
  to `DRIFT_CREATE_ACTION_TYPE` / `DRIFT_CREATE_CHANGE_TYPE` constants
  in §10 of the proposal.

---

## Summary

Every one of the twelve focus areas has a direct binding input; the
diff honours each one. The only two gaps are the pre-identified
LOW/discretionary items called out as audit Finding 1 / shortcut F1
(inline drift-create literals) and shortcut F3 (sort-key prose vs code
divergence), neither of which blocks the gate.

**Verdict: LOW_CONCERN.** PR #60 is justified against AC1–4,
D1–D15, shortcut F1/F4/F5 resolutions, and the cited SLICE-008 /
SLICE-021 / WU-037 / WU-033 precedents. No new concerns beyond those
already accepted by the audit and shortcut reviewers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
