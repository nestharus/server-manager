# SLICE-016 Scope Risk: **LOW**

Rating: **LOW** — the proposal ships exactly the two WU-030A/030B endpoints against AC1–AC4, every deviation from the ticket's Code Boundary list is driven by a binding synthesis decision (D9 migration split; package layout implied by `trust/signals.py` + `trust/recompute.py`), no deferred items (signal revocation, signal listing, automated Discord sources, trust profile history, new service actor) are pulled forward, and the legacy `policy_type="trust"` rename is executed as a no-shim data migration per D9.

## SLICE-016 ACs (ticket)

1. Creating a trust signal persists type, scope, value, and optional expiry without mutating the current trust profile immediately.
2. Recompute pins the current trust policy/config version when producing the new profile.
3. Recompute is deterministic for the same signal set and policy version.
4. Trust writes remain audit-safe and do not accept Discord-local ad hoc overrides.

## Findings

### 1. AC trace is complete and testable

| AC | Named tests | Source |
|---|---|---|
| AC1 | `test_create_signal_persists_fields_without_mutating_profile`; `test_create_signal_rejects_invalid_scope_shape`; `test_create_signal_with_expires_at_persists_correctly`; DB constraint tests. | proposal §11 WU-030A tests, §12 AC1. |
| AC2 | `test_recompute_pins_current_policy_version`; updated `test_trust.py` policy seed assertions (`config_version` on `TrustProfileRead`). | proposal §11 WU-030B + §11 `test_trust.py` updates, §12 AC2. |
| AC3 | `test_recompute_deterministic_for_same_inputs`; `test_recompute_honors_expired_signals_by_ignoring_them`. | proposal §11 WU-030B tests, §12 AC3. |
| AC4 | `test_create_signal_requires_authority_at_scope`; `test_recompute_audit_records_correct_diff`; `test_no_trust_signal_bypass_remains`. | proposal §11 WU-030B + audit invariant, §12 AC4. |
| Invariants | `test_recompute_produces_new_profile_version`; `test_recompute_returns_409_on_stale_conflict_after_retry`. | proposal §11 concurrency tests (D12). |

Every AC has a direct named test. AC1 and AC4 get additional coverage (scope validation, authority denial, bypass grep) because each spans multiple invariants; that traces to D3/D5/D7/D13 not scope inflation.

### 2. Anti-scope items from synthesis / ticket are absent

| Anti-scope item | Proposal coverage |
|---|---|
| Signal revocation endpoint, `trust_signal.revoke` action, `revoked_at` column (D11) | Not present. §12 "Out of scope" explicit. §4 `list_active_signals_for_member` notes "No `revoked_at` predicate exists in SLICE-016 because D11 excludes revocation." Research §3.1 suggested `revoked_at` — synthesis D11 rejected it and the proposal honors D11 over research. |
| Automated signal sources / Discord event producers (D13) | Not present. Ticket line 30–31 says "none in this slice." §12 out of scope for Discord handlers. `test_no_trust_signal_bypass_remains` (§11) greps for `INSERT INTO trust_signals` outside the allowed service/repository pair, enforcing AC4 at the test layer. |
| Signal listing / operator viewing API | Not present. Only `POST /api/v1/trust/signals` and `POST /api/v1/trust/recompute/{member_id}` are added (§6). No `GET /api/v1/trust/signals` or `GET /api/v1/trust/signals/{id}`. |
| Trust profile history table (`trust_profile_versions`) | Not present. D4 binds "Extend `trust_profiles` in place. Do not create a parallel `trust_profile_versions` table." §2 migration only `ADD COLUMN config_version BIGINT` and `computed_at TIMESTAMPTZ` on existing `trust_profiles`. |
| `trust_computation_configs` table | Not present. D2 binds TrustComputationConfig → `policy_versions.content`. §3 and §5 read `policy_type="trust_computation"` from existing policies substrate. |
| New trust service actor (D7) | Not present. §7 explicit: "Do not seed any new service actor grants. Do not broaden the existing `member-onboarder` grant." No seed INSERT in migration §2. |
| Dual support for old `policy_type="trust"` reads / old `rules` content shape | Not present. §2 migration does a forward-only `UPDATE policy_versions SET policy_type = 'trust_computation'` with a symmetric downgrade; §3 explicit: "Do not support both old `rules` and new content shapes." §11 tests updated to the new shape, no alias fallback. Matches AGENTS.md "No Backwards Compatibility". |
| `signal_revision_at` on `trust_profiles` (D4) | Not present. §8 explicit: "`signal_revision_at` must not be added in SLICE-016 per D4. Staleness UI and profile-listing semantics belong to a later slice." Research §3.6 had suggested this as "optional" — proposal correctly drops it. |
| Scoped trust profiles / `(member_id, scope_kind, scope_id)` profile key | Not present. D6 binds "Profile scope remains global for SLICE-016" and §5 uses `fetch_latest_version(connection, "trust_computation", "global", None)`. No schema change to `trust_profiles` primary key. |
| `computed_at` exposed on `TrustProfileRead` | Not present. D4 binds "`TrustProfileRead` adds `config_version` but does not add `computed_at`." §3 contract only adds `config_version: int = Field(ge=1)`. §8 reinforces: "`computed_at` is persisted for audit/operator context, but `TrustProfileRead` does not expose it." |
| Discord handlers / Discord-side trust writes | Not present. Ticket §"Discord interactions: none in this slice." D13 binds "no Discord interaction and no Discord-side direct database writes." §9 has no Discord-side audit, §11 `test_no_trust_signal_bypass_remains` enforces at test layer. |

### 3. Deviations from the ticket Code Boundary list are explicit and binding-driven

The ticket enumerates 2 endpoints and roughly 10 code-boundary files. The proposal touches the following files beyond the ticket's enumeration. Each is driven by a synthesis binding decision or is a direct consequence of one.

| Added file / deviation | Backing | Verdict |
|---|---|---|
| `migrations/versions/wu-030a_trust_signals.py` instead of ticket's `wu-030_trust_signals.py` | **D9 BINDING** — "Use two migrations: `wu-030a_trust_signals.py` ... `wu-030b_trust_profile_recompute_metadata.py`." | Binding-driven rename; no net scope add. |
| `migrations/versions/wu-030b_trust_profile_recompute_metadata.py` (new file) | **D9 BINDING** — second migration is required to carry the `trust_profiles` column add + backfill + policy type rename. WU-030B's ticket code boundary does not list a migration, but the backfill has no other home (parallels SLICE-015's WU-029A bundling `notification_envelopes` because WU-029B owns no migration). | Binding-driven. Not creep. |
| `services/api/app/api/v1/endpoints/trust/__init__.py` (new) | Consequence of the ticket's own code boundary which specifies `services/api/app/api/v1/endpoints/trust/signals.py` and `services/api/app/api/v1/endpoints/trust/recompute.py` — package layout requires `__init__.py`. §6 explicit: "Convert `services/api/app/api/v1/endpoints/trust.py` into a package." | Forced by ticket-listed paths. |
| `services/api/app/api/v1/endpoints/trust/profiles.py` (new, relocation only) | Same package conversion. Moves existing `GET /{member_id}` and `POST /compute/{member_id}` from the current `trust.py` module. §6 explicit: "Preserve existing path behavior except for the required `trust_computation` policy rename and `config_version` field in responses." | Relocation, not new routes. No new public surface. |
| `services/api/tests/conftest.py` — add `trust_signals` to `GOVERNANCE_TABLES` | §2 explicit: "Implementation note: add `trust_signals` to `GOVERNANCE_TABLES` in `services/api/tests/conftest.py` so tests isolate rows." | Test-isolation plumbing for the new table; unavoidable. |
| `services/api/tests/test_trust.py` edits (policy type rename, `config_version` assertions, new content shape in seeds) | **D2/D9 BINDING** no-shim rename from `policy_type="trust"` to `"trust_computation"`; **D4** adds `config_version` to `TrustProfileRead`; old SLICE-007 tests must update in the same slice per AGENTS.md "No Backwards Compatibility". | Required migration fallout. |
| `services/api/app/services/trust.py` existing `compute_trust()` update (§5 last subsection) | D2/D9 rename fallout: onboarding compute must read `policy_type="trust_computation"` and write `config_version`/`computed_at` on new rows. §5 explicit: "Keep `POST /api/v1/trust/compute/{member_id}` as the SLICE-007 onboarding path, but it must not read or write `trust_signals`." | Same-slice rename propagation; does not add a new write path. |
| `TrustRecomputeRequest` contract defined but unused (§3) | §3 explicit: "`TrustRecomputeRequest` is not accepted by `POST /trust/recompute/{member_id}` in this slice because D6 binds the endpoint to no request body. If the class is added for generated contract completeness, it remains unused until a later slice changes the API." | Minor additive — see §6 Minor observations. |

The four endpoint-package files (`__init__.py`, `profiles.py`, `signals.py`, `recompute.py`) correspond one-to-one to: router glue, existing routes relocated, WU-030A route, WU-030B route. No fifth module, no cross-slice helper, no generic `trust/signals_list.py`, no `trust/revocation.py`.

### 4. WU boundary coverage: every Code Boundary file in the ticket is touched

| WU | Ticket Code Boundary file | Proposal coverage |
|---|---|---|
| WU-030A | `migrations/versions/wu-030_trust_signals.py` | §2 `wu-030a_trust_signals.py` (D9 rename) ✔ |
| WU-030A | `services/api/app/contracts/trust.py` | §3 adds `TrustSignalScope`, `TrustSignalCreate`, `TrustSignalRead`, `TrustProfileRead.config_version`, exceptions ✔ |
| WU-030A | `services/api/app/repositories/trust.py` | §4 `insert_trust_signal`, `list_active_signals_for_member`, split profile helpers ✔ |
| WU-030A | `services/api/app/services/trust.py` | §5 `create_trust_signal`, `validate_trust_signal_scope` ✔ |
| WU-030A | `services/api/app/api/v1/endpoints/trust/signals.py` | §6 `signals.py` with manual-authority pattern, `POST ""` returning 201 ✔ |
| WU-030A | `services/api/tests/test_trust_signals.py` | §11 four named tests covering persistence, authority, scope validation, expiry validation ✔ |
| WU-030B | `services/api/app/contracts/trust.py` | §3 `TrustProfileRead.config_version`, `TrustRecomputeRequest` (declared unused per D6), `TrustRecomputeConflictError` ✔ |
| WU-030B | `services/api/app/services/trust.py` | §5 `recompute_trust_profile`, `compute_score`, constants (`TRUST_POLICY_TYPE`, aggregate types) ✔ |
| WU-030B | `services/api/app/api/v1/endpoints/trust/recompute.py` | §6 `recompute.py` with static `RequireAuthority("trust.recompute", "global")`, no body, no If-Match ✔ |
| WU-030B | `services/api/tests/test_trust_recompute.py` | §11 six named tests covering pin, determinism, version bump, OCC retry, expiry, audit diff ✔ |

Every ticket-listed file is touched. No listed file is silently skipped. The additional files are the strictly necessary consequences of the ticket's own package-path choice and D9's migration split.

### 5. Legacy removal: no daemon trust code bypass shims

| Legacy concern | Proposal coverage |
|---|---|
| `policy_type="trust"` kept as alias or dual-read fallback | **Not present.** §2 migration does a forward-only `UPDATE policy_versions SET policy_type = 'trust_computation' WHERE policy_type = 'trust' AND id IN (SELECT policy_version_id FROM trust_profiles)`. §3 explicit: "Do not support both old `rules` and new content shapes." §11 `test_trust.py` is updated in the same slice. Matches AGENTS.md §"No Backwards Compatibility". |
| Old `rules` content shape kept alongside new `signal_weights`/`decay_rules`/`level_thresholds` | **Not present.** §5 `compute_score` validates only the D2 content shape (`schema_version == 1`, numeric `score_floor`/`score_ceiling`/`default_score`, object `signal_weights`, object `decay_rules`, nonempty ordered `level_thresholds`). |
| Daemon / Discord-side `trust_signals` or `trust_profiles` writer | **Not present.** §11 `test_no_trust_signal_bypass_remains` greps all Python files outside `services/api/app/services/trust.py` and `services/api/app/repositories/trust.py` for `INSERT INTO trust_signals`, `UPDATE trust_profiles`, and `INSERT INTO trust_profiles`; allows migrations and tests only. Enforces D13 at CI time. |
| `_insert_trust_profile()` left as a dead path alongside new recompute helper | **Not present.** §4 explicit: "Replace `_insert_trust_profile()` with explicit profile helpers: `insert_trust_profile`, `update_trust_profile`, `upsert_trust_profile_for_recompute`." Clean replacement, no deprecated wrapper. |
| `/api/v1/trust/compute/{member_id}` kept as a parallel advanced write path | **Not present.** §5 explicit: "Keep `POST /api/v1/trust/compute/{member_id}` as the SLICE-007 onboarding path, but it must not read or write `trust_signals`." §12 out-of-scope list reiterates "backwards-compatible `policy_type="trust"` reads." D13 explicit that the onboarding path "must not accept operator-managed TrustSignal evidence or bypass the new signal/recompute flow." |

### 6. Authority grants: minimal new permissions, no new service actor

| Permission change | Proposal coverage | Backing |
|---|---|---|
| New permission `trust.signal.create` evaluated at body-driven scope | §7 + §6 signals.py manual authority pattern (mirrors `roster.py`) | D7 BINDING |
| New permission `trust.recompute` evaluated at global scope | §7 + §6 recompute.py static `RequireAuthority("trust.recompute", "global")` | D7 BINDING, D6 (profile scope stays global) |
| New trust service actor seeded | **Not added.** §7 explicit: "Do not seed any new service actor grants." §2 migration has no guarded-insert seed block (contrast with `wu-029a_notifications.py` seeding `notification-dispatcher`). | D7 BINDING |
| Existing `member-onboarder` grant broadened to cover advanced signals/recompute | **Not added.** §7 explicit: "Do not broaden the existing `member-onboarder` grant. Operators or services that need these permissions must receive normal authority grants outside this slice." | D7 BINDING |
| `trust.read` / `trust.write` semantics changed | **Not changed.** `GET /{member_id}` and `POST /compute/{member_id}` (relocated to `profiles.py`) preserve their existing `RequireAuthority` bindings (§6 "Preserve existing path behavior"). Research §3.3 explicitly declined to split trust read permissions. | Research §3.3 |

Exactly two new permission names, zero new actors, zero broadenings. Matches the AC4 + D7 invariant.

### 7. No Discord handlers

| Ticket line | Proposal coverage |
|---|---|
| "Discord interactions: none in this slice" (ticket §Technical Specification) | **Observed.** §6 endpoint files are all HTTP API (`services/api/app/api/v1/endpoints/trust/*`); no `services/discord/app/` additions. §9 audit section has no Discord-side actor or surface. §11 test file list has no `services/discord/tests/...`. §12 "Out of scope for SLICE-016: ... Discord handlers ...". |
| D13 "No Discord bypass or alternate write path" | **Enforced at test time** by `test_no_trust_signal_bypass_remains` (§11). Grep predicate covers `INSERT INTO trust_signals`, `UPDATE trust_profiles`, and `INSERT INTO trust_profiles` in Python files outside the two allowed modules; allows migrations and tests. This catches any accidental daemon or task-side write. |

### 8. In-scope extensions beyond the ticket literal text, each with binding backing

| Feature | Status | Backing |
|---|---|---|
| `trust_signal` aggregate type in `aggregate_heads` | In scope | D8 BINDING (`aggregate_type="trust_signal"`, `aggregate_id=str(signal_id)`, `expected_version=0`). Required so signal creates produce uniform action/state-change/audit rows. |
| `TrustSignalScope` Pydantic model + structured scope persistence | In scope | D3 BINDING (clients submit `scope_kind` + `scope_id`, server builds `scope` JSON). |
| `source_actor_kind` / `source_actor_id` derived from `ActorIdentity`, not request body | In scope | D5 BINDING ("Clients must not submit source actor fields"). `InvalidTrustSignalActorError` when `actor.actor_kind == "system"` enforces the D1 check constraint `source_actor_kind IN ('user','service')` at service layer. |
| 5 indexes on `trust_signals`, including GIN on `value` and `(member_id, expires_at)` | In scope | D1 BINDING — exact index list. No additional indexes proposed. |
| `value.schema_version` must be numeric, `expires_at > observed_at` check | In scope | D1 BINDING check constraints; Pydantic `validate_value` and `validate_expiry` mirror DB checks. |
| Deterministic canonical ordering `(observed_at ASC, created_at ASC, id ASC)` + exact-retry dedupe | In scope | D10 BINDING for AC3 determinism. |
| Expiry filtering outside evaluator with a single captured `as_of` | In scope | D10 BINDING ("Expiry filtering happens outside the evaluator by capturing one `as_of` time"). §8 explicit that `as_of` is not a score input. |
| OCC retry-once then `TrustRecomputeConflictError` → 409 | In scope | D12 BINDING ("If the retry also sees a stale version, return HTTP 409 Conflict with a trust-specific error code such as `trust_recompute_conflict`."). |
| `policy_type="trust"` → `"trust_computation"` rename folded into `wu-030b` backfill | In scope | D9 BINDING ("`wu-030b` also performs the no-shim data rename"). |
| `config_version BIGINT NOT NULL` on `trust_profiles` with backfill from `policy_versions.version_number` | In scope | D4 BINDING. |
| `computed_at` column persisted but not exposed on `TrustProfileRead` | In scope | D4 BINDING (persist but do not expose). |

Each extension traces to a named D-binding. No silently-added field, column, index, constraint, or permission.

### 9. No scope leakage into downstream slices

| Downstream concern | Would require | Present in proposal? |
|---|---|---|
| Signal revocation slice | `revoked_at` column, `POST /signals/{id}/revoke`, `trust.signal.revoke` permission | **No.** D11 + §12 explicit. |
| Signal listing / operator UI slice | `GET /api/v1/trust/signals`, pagination contracts, `trust.signal.read` permission | **No.** Only `POST /signals` + `POST /recompute/{member_id}` ship. |
| Trust profile history slice | `trust_profile_versions` table, history endpoint | **No.** D4 explicit extend-in-place. |
| Scoped trust profiles slice | `(member_id, scope_kind, scope_id)` key on `trust_profiles`, scoped recompute endpoint | **No.** D6 fixes profile scope to global in SLICE-016. `RequireAuthority("trust.recompute", "global")` static guard. |
| Automated Discord-event signal producer | Discord daemon handlers writing signals, service-actor grant | **No.** Ticket + D13 explicit; `test_no_trust_signal_bypass_remains` enforces. |
| Profile staleness / signal-revision UI | `signal_revision_at` column, stale indicator on `TrustProfileRead` | **No.** D4 + §8 explicit. |
| Preview/confirm on trust computation policy | Policy preview/confirm wiring specifically for `trust_computation` | **No.** D2 reuses generic `policy_versions` substrate; no specialized preview route. |
| Dual `policy_type="trust"` backwards compatibility slice | Read-side alias, dual-seed fixture | **No.** AGENTS.md "No Backwards Compatibility" applied at D9 migration level. |

### 10. Minor observations (not severity escalations)

| Observation | Verdict |
|---|---|
| `TrustRecomputeRequest` class is defined in §3 but noted as unused in SLICE-016 because D6 binds "no request body." | **Soft add.** Proposal itself says "If the class is added for generated contract completeness, it remains unused until a later slice changes the API." Preferred: drop the class entirely until the later slice actually needs it — an unused contract is mild scope creep and risks later confusion. Not severity-escalating because it is explicitly flagged as unused and never imported by `recompute.py` (§6 shows no request body parameter). Implementation should omit it; worst case it can be deleted trivially at review. |
| `wu-030b` migration bundles both (a) `trust_profiles` column add + backfill and (b) policy-type rename. | **Acceptable bundling.** D9 binding explicitly folds the rename into `wu-030b`. Both changes are in the same data domain and must be atomic with `config_version` backfill (which reads the renamed `policy_type`). Parallels SLICE-015's bundling of `notification_envelopes` into the WU-029A migration. |
| Package conversion of `endpoints/trust.py` → `endpoints/trust/` touches existing routes (`GET /{member_id}`, `POST /compute/{member_id}`) even though those are not in SLICE-016 ACs. | **Forced by ticket.** Ticket code boundaries specify `services/api/app/api/v1/endpoints/trust/signals.py` and `services/api/app/api/v1/endpoints/trust/recompute.py`, which is a package layout. The module-to-package conversion necessarily moves the existing routes. §6 constrains the move to behavior-preserving relocation plus the required `trust_computation` policy rename and `config_version` response field. No new public paths or changed response status codes. |
| Three new exception types introduced (`InvalidTrustSignalScopeError`, `InvalidTrustSignalActorError`, `TrustRecomputeConflictError`). | **Minimal and each mapped.** Each maps to a specific HTTP response: 422 for scope shape, 422 for actor kind, 409 for OCC retry exhaustion. Each traces to D1 constraint, D1 `source_actor_kind` literal, and D12 respectively. |
| `TRUST_SIGNAL_AGGREGATE_TYPE` and `TRUST_PROFILE_AGGREGATE_TYPE` constants introduced alongside `TRUST_POLICY_TYPE`. | **Standard**. Matches existing service-layer constant pattern (e.g., `tickets.py` uses aggregate-type constants). Not a new surface. |
| Proposal §11 adds migration tests asserting `trust_signals` constraints ("where cheap"). | **Defensive but in-scope.** Constraint coverage supports AC1 persistence semantics and D1 binding. Not new features. |
| Pydantic `validate_value` and `validate_expiry` duplicate DB check constraints (`value ? 'schema_version'`, `expires_at > observed_at`). | **Redundant by design.** Validation at both layers is consistent with other governed contracts (e.g., `TicketCategoryCreate`). Gives 422 with meaningful error before DB round-trip. Not a scope risk. |

## Summary table

| Risk category | Severity | Notes |
|---|---|---|
| New endpoints beyond WU-030A/030B | None | Only `POST /api/v1/trust/signals` and `POST /api/v1/trust/recompute/{member_id}` added. `profiles.py` relocates existing `GET /{member_id}` + `POST /compute/{member_id}` with preserved behavior (package conversion forced by ticket code boundary naming). |
| New tables beyond `trust_signals` | None | `trust_profiles` extended in place per D4; no history table, no `trust_computation_configs` table, no scoped-profile key change. |
| Deferred items pulled forward (signal revocation, listing, automated sources, profile history) | None | All excluded per D11/D13/D4/§12 with explicit references in body and out-of-scope list. Grep invariant test enforces D13. |
| AC coverage gaps | None | Each AC1–AC4 has direct named tests (§11, §12 trace table); concurrency and version-bump invariants also covered. |
| WU Code Boundary files not touched | None | All 10 listed files touched. Added files (`wu-030a/b.py` split, `endpoints/trust/__init__.py`, `endpoints/trust/profiles.py`, `tests/conftest.py` `GOVERNANCE_TABLES`) are each binding-driven (D9) or directly forced by ticket-listed paths. |
| Legacy bypass shims or alias paths | None | Forward-only rename in `wu-030b`, no `policy_type="trust"` alias, no `rules`-shape fallback, no old `_insert_trust_profile()` wrapper, no daemon-side trust writer (grep invariant). |
| New permissions / actors | None | Two permissions (`trust.signal.create`, `trust.recompute`); zero new service actors; existing `member-onboarder` not broadened (D7). |
| Discord handler scope | None | Zero Discord-side files; D13 enforced by `test_no_trust_signal_bypass_remains`. |
| `TrustRecomputeRequest` defined but unused | Low | Proposal flags it as unused; should be omitted entirely. Trivial to drop; not a gate concern. |

## What LOW requires (already met)

1. Each AC has at least one direct test — **yes** (§11 + §12 trace table).
2. Deferred items (revocation, listing, automated producers, history, staleness, scoped profiles) are absent — **yes** (D11/D13/D4/§12).
3. Any deviation from the ticket's endpoint list or code-boundary files is explicit and binding-driven — **yes** (D9 migration split; package conversion forced by ticket path naming; rename fallout in `test_trust.py` and `compute_trust()` required by D2/D9).
4. Legacy `policy_type="trust"` is renamed, not aliased, per AGENTS.md §"No Backwards Compatibility" — **yes** (§2 migration forward-only update; §3 and §11 forbid dual support).
5. Minimal authority surface: two new permissions, no new service actor, no broadened grant — **yes** (§7 + D7).
6. No Discord handlers ship; bypass paths are grep-enforced — **yes** (D13 + §11 `test_no_trust_signal_bypass_remains`).
7. `trust_profiles` extended in place, not versioned table — **yes** (D4 + §2 migration).
8. Recompute is deterministic and expiry filtering is outside the evaluator — **yes** (D10 + §8).

No scope reductions or additions are required. The proposal is right-sized for WU-030A/WU-030B against AC1–AC4, every expansion beyond the ticket's literal file list maps to a synthesis binding, and every deferred concern from the ticket and synthesis remains explicitly out of scope.
