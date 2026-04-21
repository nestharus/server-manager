# SLICE-007 Phase 8 — Opus Justification Review (PR #46)

Reviewed: 2026-04-21
PR: `feat/slice-007-member-onboarding` (#46)
Branch head: `e42f073` (against `origin/main` = `331da66`)
Inputs: `.pipeline/proposal.md` (Revision 1), `.pipeline/synthesis.md` (D1–D12),
`.pipeline/implementation.md`, `product-strategy/tickets/SLICE-007.md`
(AC1–AC4), `plans/risk/slice-007-audit.md`, `plans/risk/slice-007-scope.md`,
`plans/risk/slice-007-shortcut.md`, `gh pr diff 46`.

## 1. Verdict

**`LOW_CONCERN`** — no HIGH findings, no MEDIUM findings. Every non-trivial
file traces to an AC / D-decision / ticket surface / revision rationale.

- **Scope creep**: none. Endpoint surface (`POST /members`,
  `GET /members/{id}`, `GET /members/by-discord/{id}`,
  `PATCH /members/{id}/status`, `POST /trust/compute/{id}`,
  `GET /trust/{id}`, plus the Discord `handle_member_join` handler) matches
  the ticket (`product-strategy/tickets/SLICE-007.md:27-33`) verbatim. No
  extra endpoints, no extra handlers, no hidden CLI surfaces. D12 anti-scope
  restated and honored: no recompute, no signal-extensibility, no
  merge/split, no export, no compliance statuses, no per-chapter visibility,
  no age/phone verification.
- **Deferred stubs**: none. Grepped production code for
  `TODO|NotImplementedError|FIXME|XXX|HACK|pass  #` → no matches in
  `services/` or the new migrations. The only `NotImplementedError` in the
  tree is pre-existing `migrations/versions/wu-003a_widen_aggregate_id.py:44`
  (unchanged by this PR). D10 roster FK deferral is a legitimate cross-slice
  boundary (shortcut §3), not a stub.
- **Backwards-compat shims**: none. Members/trust aggregates are net-new;
  no parallel tables, dual-write paths, or feature flags. `roster_entries.
  member_id` is intentionally left as `TEXT` per D10 and is not read or
  written by this PR.
- **Magic values**: all accounted for. Status literals
  (`active|suspended|departed`) from D1/D2. Score range 0–100 from proposal
  line 192. `"member-onboarder"` service actor id from D9. Tier literal
  `"low"` → `intake_required=True` from proposal §Tradeoffs line 332 /
  Discord handler line 103.

The six LOW findings below are hygiene items: two unused evaluator
branches (F1, F2), one unjustified row lock (F3), two AC-trace-table
omissions (F4), one invariant-test rename (F5), and one dead test helper
(F6). None block merge.

## 2. Findings

| # | Severity | File:Line | Description | Proposed fix / justification |
|---|---|---|---|---|
| F1 | LOW | `services/api/app/services/trust.py:94-126` `_tier_for_score` | Supports **two** tier shapes: (a) `Sequence` of `{"name": str, "max_score": number}` objects and (b) `Mapping` of `name -> minimum threshold`. Every test and fixture exercises only the sequence form (`services/api/tests/test_trust.py:147-152` `_valid_trust_policy_rules`). The mapping branch (`trust.py:111-126`) has **0 callers** and **0 tests** in this slice. `.pipeline/implementation.md:41-42` discloses the dual-form as a deliberate extension ("accepts both tier mapping rules and the list form used by the contract tests"), but the proposal's Policy content contract (`.pipeline/proposal.md:270-278`) lists `rules.tiers` without pinning which shape, and no AC or D-decision requires both. This is the "<2 callers, <1 test" premature-abstraction pattern AGENTS.md §Quality warns against. | Delete the `Mapping` branch of `_tier_for_score` and keep only the `Sequence` form that `_valid_trust_policy_rules` exercises. If future policy shapes need a mapping form, add it with its own test in the slice that introduces the use case. **Not merge-blocking** — sequence-form correctness is verified by `test_compute_trust_creates_profile_with_current_policy_version` + determinism/replay tests. |
| F2 | LOW | `services/api/app/services/trust.py:83-91` `_age_weight` | Accepts either a `Mapping` with `per_day`/`max` keys or a scalar number. `_valid_trust_policy_rules` (`test_trust.py:141-145`) only provides the scalar form (`"discord_account_age_days": 2`). The mapping branch (capped age score via `"max"`) has **0 tests**. Same category as F1. Proposal §Policy content contract line 275 lists `rules.weights.discord_account_age_days` without sub-shape. | Same treatment as F1: collapse to the tested scalar form, or add a test that exercises the `{"per_day": n, "max": m}` mapping. **Not merge-blocking.** |
| F3 | LOW | `services/api/app/repositories/members.py:47-55` `_fetch_member_by_id_for_update`, called at `services/api/app/services/members.py:177` | Repository helper takes `FOR UPDATE OF m` on `members` inside `patch_member_status.mutate_projection`. Proposal §Repository lines 128-139 names `_insert_member` and `_update_member_status` only — no `_fetch_*_for_update` helper is mentioned. Audit §5 (`plans/risk/slice-007-audit.md:97-110`) concluded the state-machine validation "runs **inside** `mutate_projection`, which means the head lock is held when the transition check runs, so two concurrent transitions for the same member are serialized" — i.e., the `aggregate_heads` row lock is already sufficient. The additional row-level lock on `members` is defense-in-depth but is not traced to an AC, D-decision, or audit recommendation. | Either drop the helper and read the row inside the projection with a plain select (the head lock already serializes), or pin the extra lock as an explicit defense-in-depth choice in proposal §Tradeoffs. **Not merge-blocking** — behavior is correct, lock is brief. |
| F4 | LOW | `services/api/tests/test_members.py:361-391` `test_create_member_preserves_originating_user_in_audit`; `services/api/tests/test_trust.py:184-214` `test_compute_trust_requires_trust_write_permission` | Two tests exist in the PR that are not listed in `.pipeline/proposal.md:397-430` §AC Trace or §Invariants. Both are justified: the audit test covers **D8** (originating-Discord-user carried in audit payload) and parallels `test_handle_member_join_records_originating_user_in_audit` at the API layer; the authority test covers **D9** `trust.write` gating and parallels `test_create_member_requires_member_write_permission`. Neither is scope creep — they exercise in-scope decisions — but §AC Trace should mention them so reviewers can correlate tests → ACs without spelunking. | Add both tests to proposal §AC Trace (D8 → AC3 or new "Audit invariant" line; D9 → AC2). **Not merge-blocking.** |
| F5 | LOW | `services/api/tests/test_trust.py:572` `test_member_onboarder_service_actor_grants_seeded` | Proposal §Invariants line 428 names the test `test_member_onboarder_service_actor_has_read_and_write_grants_after_migration`; committed code uses the shorter `test_member_onboarder_service_actor_grants_seeded`. Assertions at lines 585-595 verify the exact `{member.read, member.write, trust.read, trust.write}` permission set per D9, so semantic content matches. | Rename to match the proposal (or update the proposal to match the implementation); either is fine. **Not merge-blocking.** |
| F6 | LOW | `services/api/tests/test_trust.py:179-180` `_trust_create_payload` | Identity wrapper: `def _trust_create_payload(signals): return signals`. Called from four test sites (`test_trust.py:208, 255, 471, 512`) but does no transformation. AGENTS.md §Simplicity ("three similar lines is better than a premature abstraction") applies. | Inline the four call sites and delete the helper. **Not merge-blocking.** |

No MEDIUM or HIGH findings.

## 3. Trace matrix

Every non-trivial file → AC / D-decision / ticket surface / Revision-1
rationale. Rows marked with "⚠" reference a finding from §2.

### Migrations

| File | Justification |
|---|---|
| `migrations/versions/wu-011_members.py` | `down_revision = "wu_033_roster"` — stacks on SLICE-018. Columns (`id UUID PK`, `discord_user_id TEXT`, `joined_at TIMESTAMPTZ`, `status TEXT`, timestamps) match **D1** (synthesis.md:10-18). `UNIQUE(discord_user_id)` + status `CHECK` — **D1** + **D2** (synthesis.md:20-26). No `version` column — **D1**. No `member_transitions` table — **D2**. No `roster_entries` mutation — **D10**. |
| `migrations/versions/wu-012_trust.py` | `trust_profiles.member_id UUID PRIMARY KEY REFERENCES members(id) ON DELETE RESTRICT` — **D3**. `score INT CHECK 0..100` — proposal §Migration line 192. `signals JSONB` — **D5**. `policy_version_id UUID REFERENCES policy_versions(id) ON DELETE RESTRICT` — **D4** (replay/audit), audit §3 (policy-version race mitigation). `ix_trust_profiles__policy_version_id` index — proposal line 204-205 (replay reads). `member-onboarder` global grant seed with `NOT EXISTS` guard — **D9** (synthesis.md:71-75). Downgrade removes only the grant row plus table/index — proposal line 204. |

### API contracts

| File | Justification |
|---|---|
| `services/api/app/contracts/members.py` `MemberStatus`, `OriginatingActorKind` | **D1** status literals + **D8** originating-actor kind. |
| `MemberCreate` (`discord_user_id`, `joined_at`, `originating_actor_*`) | **D1** shape + **D8** originating fields; proposal §Contracts lines 106-114. `extra="forbid"` — contract discipline from SLICE-010/013. |
| `MemberRead` (adds `version: int >= 1`) | **D1** — version from `aggregate_heads` join; proposal §Contracts lines 115-122. |
| `MemberStatusPatch` (`status`, `reason`, `originating_actor_*`) | **D2** transition matrix input + **D8**; proposal §Contracts lines 123-127. |
| `MemberNotFoundError`, `InvalidMemberStatusTransitionError` | **D2** + typed-error discipline (SLICE-010/013 precedent); proposal §Contracts line 128. |
| `services/api/app/contracts/trust.py` `TrustSignalsInput` | **D5** (fixed 4 fields) + **D8** originating fields; proposal §Contracts lines 210-217. |
| `TrustProfileRead` | **D3** (member_id key), **D4** (policy_version_id), **D1** (version via aggregate_heads); proposal §Contracts lines 218-224. |
| `TrustProfileNotFoundError`, `NoTrustPolicyConfiguredError`, `InvalidTrustPolicyError` | **D4** + Revision 1 typed errors; proposal §Contracts line 225. |

### API repositories

| File | Justification |
|---|---|
| `services/api/app/repositories/members.py` `_MEMBER_SELECT` (join `aggregate_heads` on `aggregate_type='member'`) | **D1** projection-plus-head pattern; mirrors `services/api/app/repositories/roster.py:11` per proposal line 133-136. |
| `fetch_member_by_id`, `fetch_member_by_discord_id` | **D1** + **D11** (discord_user_id lookup for get-or-create); proposal §Repository lines 134-136. |
| `_insert_member`, `_update_member_status` | Underscore-prefixed per proposal §Repository lines 137-139 — service owns mutation boundary. |
| `_fetch_member_by_id_for_update` ⚠ | **F3** — not traced; defense-in-depth row lock over what the head lock already serializes (audit §5). |
| `services/api/app/repositories/trust.py` `_TRUST_PROFILE_SELECT` (join `aggregate_heads` on `aggregate_type='trust_profile'`) | **D3** + proposal §Repository lines 229-230. |
| `fetch_trust_profile_by_member_id`, `_insert_trust_profile` | **D3** idempotency read path + proposal §Repository lines 230-231. `Jsonb(row["signals"])` — **D5** JSONB storage. |

### API services

| File | Justification |
|---|---|
| `services/api/app/services/members.py` `VALID_TRANSITIONS` | **D2** exact matrix (synthesis.md:20-26); mirrors `services/api/app/services/roster.py` VALID_TRANSITIONS pattern. |
| `_make_request`, `_member_from_row`, `_fetch_member_row`, `_fetch_member_row_by_discord_id` | Private helpers — service composition; no scope implication. |
| `create_or_get_member` | **D11** get-or-create by `discord_user_id`: existing → `(read, None, False)` → 200; absent → `mutate_entity(aggregate_type="member", expected_version=0, scope_kind="global")`. **UniqueViolation** re-read-and-return — proposal lines 150-151, audit §1. **D1** + **D8** — stores `originating_actor_*` in `StateChangeDraft.payload_json`. `payload_allowlist=set(request.model_dump().keys())` — audit §7 allowlist parity. |
| `get_member_by_id`, `get_member_by_discord_id` | Ticket §Technical Specification + **D1** version-in-ETag. |
| `patch_member_status(..., expected_version)` | **D2** state machine enforced inside `mutate_projection` (transition check is load-bearing): rejects same-status and unsupported transitions with `InvalidMemberStatusTransitionError` → 409 per endpoint. **AC4** — `mutate_entity` produces `StaleMutationError` → 412. **D8** `originating_actor_*` in payload_json. |
| `services/api/app/services/trust.py` `_make_request`, `_profile_from_row`, `_fetch_profile_row` | Private helpers. |
| `_as_mapping`, `_as_number`, `_required_number` | **D6** strict policy shape validation; **Revision 1** `InvalidTrustPolicyError` (proposal lines 278-280). Every missing/malformed rule raises rather than silently defaulting — shortcut §5. |
| `_age_weight` ⚠ | **F2** — dual-form with untested mapping branch. |
| `_tier_for_score` ⚠ | **F1** — dual-form with untested mapping branch. |
| `evaluate_trust` | **D6** pure-function evaluator over `(TrustSignalsInput, policy.rules)`. No clock, random, external state. `bounded = int(round(max(floor, min(ceiling, score))))` — proposal §Policy content contract lines 270-278. |
| `compute_trust` | Full compliance with **D3/D4/D6/D11**: (1) member existence check → `MemberNotFoundError`; (2) existing-profile → `(read, None, False)` — **D3** idempotency, no recompute (**D12**); (3) `fetch_latest_version("trust", "global", None)` — **D4**; (4) `NoTrustPolicyConfiguredError` on missing policy (synthesis.md:36-42) / `InvalidTrustPolicyError` on malformed rules (Revision 1); (5) `signal_payload = signals.model_dump(exclude={"originating_actor_*"})` — closes the audit §"Non-Blocking Observation" that originating-actor fields would otherwise bleed into `trust_profiles.signals` JSONB; (6) `mutate_entity(aggregate_type="trust_profile", aggregate_id=str(member_id), expected_version=0)` — **D3** + proposal line 250; (7) `except (StaleMutationError, errors.UniqueViolation): reread_existing()` — **Revision 1** pinned recovery (proposal lines 252-261). Re-raise on unexpectedly absent re-read — proposal line 253-255. |
| `get_trust_profile` | Ticket §Technical Specification + **D3** read path. |

### API endpoints

| File | Justification |
|---|---|
| `services/api/app/api/v1/endpoints/members.py` `_parse_if_match`, `_set_etag` | Mirrors `services/api/app/api/v1/endpoints/roster.py`/`chapters.py` precedent; **AC4** requires `If-Match`. |
| `_raise_for_member_error` | **D1** `MemberNotFoundError|MissingAggregateError` → 404; **AC4** `StaleMutationError` → 412; **D2** `InvalidMemberStatusTransitionError` → 409 with `from_status`/`to_status`. |
| `POST /api/v1/members` | Ticket §Technical Specification + **D9** `RequireAuthority("member.write", "global")` + **D11** 201 vs 200 from `created` flag + **D1** ETag. |
| `GET /api/v1/members/by-discord/{discord_user_id}` | Ticket + **D9** `member.read` + proposal line 176-177 (404 `member_not_found`). |
| `GET /api/v1/members/{member_id}` | Ticket + **D9** `member.read`. |
| `PATCH /api/v1/members/{member_id}/status` | Ticket + **D9** `member.write` + **AC4** If-Match requirement + **D2** transition enforcement. |
| `services/api/app/api/v1/endpoints/trust.py` `_raise_for_trust_error` | **D4** `NoTrustPolicyConfiguredError` → 409 `no_trust_policy_configured`; **Revision 1** `InvalidTrustPolicyError` → 409 `invalid_trust_policy`; **D3** `TrustProfileNotFoundError` → 404. |
| `POST /api/v1/trust/compute/{member_id}` | Ticket + **D9** `trust.write` + **D11** 201 vs 200 from `created` + **D3** idempotency. |
| `GET /api/v1/trust/{member_id}` | Ticket + **D9** `trust.read`. |
| `services/api/app/api/v1/router.py` (+members, +trust) | Required by ticket §Technical Specification; proposal lines 183, 295. |
| `services/api/tests/conftest.py` (+`trust_profiles`, +`members` in `GOVERNANCE_TABLES`) | Required by wu-011/wu-012 migrations so per-test truncation keeps governance tables isolated. |

### Discord

| File | Justification |
|---|---|
| `services/discord/app/contracts/onboarding.py` `MemberJoinSignals` (D5 fields only) | **D5** fixed shape (no originating fields — those live at the event envelope per proposal lines 304-306). |
| `MemberJoinEvent` | **D7** event shape + **D8** `originating_actor_kind="user"` literal and `originating_actor_id`. |
| `MemberJoinOutcomeRead` (`member`, `trust`, `intake_required`) | **D7** return shape (synthesis.md:56-64). |
| `services/discord/app/handlers/onboarding.py` `SERVICE_ACTOR_HEADERS = {"X-Actor-Kind":"service","X-Actor-Id":"member-onboarder"}` | **D8** header literal (synthesis.md:66-69); mirrors `services/discord/app/handlers/chapters.py:12` precedent. |
| `MemberOnboardingError(step, status, body)` | Typed failure propagation — proposal line 341-342 ("API errors propagate as onboarding failures"). |
| `_api_call`, `_originating_body`, `_signals_body` | Private helpers for the three API calls; `_signals_body` attaches `originating_actor_*` at the body layer per **D8**. |
| `handle_member_join` | **D7** flow verbatim: (1) `GET /members/by-discord/{id}`; (2) 404 → `POST /members`; (3) `POST /trust/compute/{id}`; (4) `intake_required = trust.tier == "low"` (proposal lines 331-332, §Tradeoffs). |
| `services/discord/app/core/bot.py` `on_member_join(discord.Member)` | Proposal §WU-013 line 336 — bot wiring converts `discord.Member` → `MemberJoinEvent`. `account_age_days = max((joined_at - created_at).days, 0)` and `has_verified_badge=False`/`account_flags=[]` are D5-shape placeholders sourced from `discord.Member` attributes; `originating_actor_id=str(member.id)` per **D8**. |

### Tests

| File | Justification |
|---|---|
| `services/api/tests/test_members.py::test_create_member_returns_active_with_uuid_id` | **AC1** direct (proposal line 399). |
| `::test_create_member_idempotent_on_duplicate_discord_user_id` | **AC1** + **D11** (proposal line 400). |
| `::test_create_member_requires_member_write_permission` | **AC1** + **D9** (proposal line 401). |
| `::test_get_member_by_id_returns_current_state` | **AC1** read-back (proposal line 402). |
| `::test_get_member_by_discord_id_404_when_absent` | **AC1** 404 path (proposal line 403). |
| `::test_patch_member_status_with_current_version_succeeds_and_advances_version` | **AC4** (proposal line 422). |
| `::test_patch_member_status_returns_412_on_stale_version` | **AC4** stale-412 (proposal line 423). |
| `::test_create_member_preserves_originating_user_in_audit` ⚠ | **F4** — covers **D8** but not enumerated in proposal §AC Trace. |
| `::test_no_hardcoded_system_actor_in_members_service` | Invariant (proposal line 429). |
| `::test_unique_discord_user_id_enforced` | Invariant (proposal line 430). |
| `services/api/tests/test_trust.py::test_compute_trust_creates_profile_with_current_policy_version` | **AC2** direct (proposal line 406). |
| `::test_compute_trust_is_deterministic_given_same_signals_and_policy` | **AC2** + **D6** (proposal line 407). |
| `::test_compute_trust_returns_existing_profile_on_retry` | **AC2** + **D3** (proposal line 408). |
| `::test_compute_trust_concurrent_same_member_returns_same_profile_to_both` | **AC2** + **D11** race recovery (proposal line 409). |
| `::test_compute_trust_returns_409_when_no_trust_policy` | **AC2** + **D4** (proposal line 410). |
| `::test_compute_trust_returns_409_when_policy_shape_invalid` | **AC2** + **Revision 1** `InvalidTrustPolicyError` (proposal line 411). |
| `::test_trust_profile_stores_policy_version_id_for_replay` | **AC2** + **D4** persistence (proposal line 412). |
| `::test_compute_trust_requires_trust_write_permission` ⚠ | **F4** — covers **D9** but not enumerated in proposal §AC Trace. |
| `::test_member_onboarder_service_actor_grants_seeded` ⚠ | **F5** — rename drift vs. proposal line 428 invariant. |
| `services/discord/tests/test_onboarding.py::test_handle_member_join_creates_member_when_absent` | **AC3** direct (proposal line 415). |
| `::test_handle_member_join_reuses_member_when_present` | **AC3** + **D11** (proposal line 416). |
| `::test_handle_member_join_computes_trust_and_derives_intake_required` | **AC3** + **D7** `intake_required` (proposal line 417). |
| `::test_handle_member_join_records_originating_user_in_audit` | **AC3** + **D8** (proposal line 418). |

### Anti-scope confirmation (D12)

Spot-checked against scope-risk §D12 table (`plans/risk/slice-007-scope.md:82-101`):

- **Trust recomputation**: `compute_trust` returns `(read, None, False)` when `fetch_trust_profile_by_member_id` finds a row (`services/api/app/services/trust.py:175-177`). No `/trust/recompute` endpoint; only `POST /trust/compute/{member_id}` which is idempotent. **Preserved.**
- **Trust signal extensibility**: `TrustSignalsInput` declares exactly the D5 four fields plus originating pair, `model_config = ConfigDict(extra="forbid")` (`contracts/trust.py:13, 16-23`). No plugin/extension hook, no signal-table. **Preserved.**
- **Member merge/split, export, compliance statuses, per-chapter visibility, age/phone verification**: no such endpoints, services, columns, or authority scopes. All member/trust endpoints require `scope_kind="global"` only. **Preserved.**
- **Roster FK deferral (D10)**: `wu-011_members.py` does not touch `roster_entries`. `roster_entries.member_id` remains `TEXT` and is not read or written by any SLICE-007 code. **Preserved.**

## 4. Sanity probes for "deferred stubs"

Grepped production + migration code for `TODO|FIXME|XXX|HACK|NotImplementedError|pass  #`:

- `services/**/*.py` in this PR's footprint — **no matches**.
- `migrations/versions/wu-011_members.py`, `migrations/versions/wu-012_trust.py` — **no matches**.
- The single `raise NotImplementedError` elsewhere in the tree
  (`migrations/versions/wu-003a_widen_aggregate_id.py:44`) is untouched by
  this PR (`git diff main -- migrations/versions/wu-003a_widen_aggregate_id.py`
  reports no changes).

No ellipsis-only bodies, no placeholder returns, no "will wire later"
comments. D10 roster-FK deferral is a ticketed cross-slice scope boundary,
not a stub.

## 5. "Non-trivial file" coverage checklist

| File in diff | Traced? |
|---|---|
| `migrations/versions/wu-011_members.py` | yes |
| `migrations/versions/wu-012_trust.py` | yes |
| `services/api/app/contracts/members.py` | yes |
| `services/api/app/contracts/trust.py` | yes |
| `services/api/app/repositories/members.py` | yes (F3 for `_fetch_member_by_id_for_update`) |
| `services/api/app/repositories/trust.py` | yes |
| `services/api/app/services/members.py` | yes |
| `services/api/app/services/trust.py` | yes (F1 tier dual-form, F2 age dual-form) |
| `services/api/app/api/v1/endpoints/members.py` | yes |
| `services/api/app/api/v1/endpoints/trust.py` | yes |
| `services/api/app/api/v1/router.py` | yes |
| `services/api/tests/conftest.py` | yes |
| `services/api/tests/test_members.py` | yes (F4) |
| `services/api/tests/test_trust.py` | yes (F4, F5, F6) |
| `services/discord/app/contracts/onboarding.py` | yes |
| `services/discord/app/handlers/onboarding.py` | yes |
| `services/discord/app/core/bot.py` | yes |
| `services/discord/tests/test_onboarding.py` | yes |
| `.pipeline/*`, `plans/risk/slice-007-*.md` | Planspace — informational, not production code. |

## 6. Merge recommendation

**Merge allowed under `LOW_CONCERN`.**

Non-blocking polish to absorb before SLICE-016 (recompute) opens, since that
slice will revisit the trust evaluator:

1. **F1** — Delete the `Mapping` branch of `_tier_for_score` (keep the
   sequence form the tests exercise). If SLICE-016 needs a mapping shape,
   introduce it with its own test.
2. **F2** — Collapse `_age_weight` to the scalar form or add a test for the
   `{per_day, max}` mapping form.
3. **F3** — Either drop `_fetch_member_by_id_for_update` (the head lock
   already serializes transitions) or pin the defense-in-depth row lock in
   proposal §Tradeoffs for future reviewers.
4. **F4** — Add `test_create_member_preserves_originating_user_in_audit`
   and `test_compute_trust_requires_trust_write_permission` to proposal
   §AC Trace (D8/AC3 and D9/AC2 respectively).
5. **F5** — Rename `test_member_onboarder_service_actor_grants_seeded` →
   `test_member_onboarder_service_actor_has_read_and_write_grants_after_migration`
   to match proposal line 428, or update the proposal.
6. **F6** — Inline the identity helper `_trust_create_payload`.

No HIGH or MEDIUM findings. No merge block.
