# SLICE-007 Scope Risk Assessment (Revision 1)

## Severity: LOW

The proposal delivers exactly the ticket's four ACs, matches the ticket's
endpoint list verbatim, restates the D12 anti-scope list, and traces each
AC to at least one direct test. No over-scope, no under-scope.

Note on prompt premise: the scope review prompt says "3 ACs", but
`product-strategy/tickets/SLICE-007.md:58-61` actually lists four. The
proposal correctly traces all four (AC4 covered by Revision 1).

## Endpoint / Handler Surface vs Ticket

Ticket (`product-strategy/tickets/SLICE-007.md:27-33`) vs proposal:

| Ticket surface | Proposal surface | Match |
|---|---|---|
| `POST /api/v1/members` | `.pipeline/proposal.md:167-173` | yes |
| `GET /api/v1/members/{member_id}` | `.pipeline/proposal.md:174-175` | yes |
| `GET /api/v1/members/by-discord/{discord_user_id}` | `.pipeline/proposal.md:176-177` | yes |
| `PATCH /api/v1/members/{member_id}/status` | `.pipeline/proposal.md:178-182` | yes |
| `POST /api/v1/trust/compute/{member_id}` | `.pipeline/proposal.md:284-291` | yes |
| `GET /api/v1/trust/{member_id}` | `.pipeline/proposal.md:292-294` | yes |
| `handle_member_join(MemberJoinEvent) -> MemberJoinOutcomeRead` | `.pipeline/proposal.md:314-336` | yes |

No extra endpoints. No extra handlers. No hidden CLI surfaces.

## Migrations / Schema Surface

- `wu-011_members.py` creates `members` per D1 shape only
  (`.pipeline/proposal.md:91-103`). No `version` column, no
  `member_transitions` projection (D2), no `roster_entries` mutation (D10).
- `wu-012_trust.py` creates `trust_profiles` per D3/D4/D5
  (`.pipeline/proposal.md:188-205`) and idempotently seeds only the
  `member-onboarder` global grant set required by D9. One optional
  replay-read index (`ix_trust_profiles__policy_version_id`) is noted;
  not a scope concern.

No new aggregate types, no new projections, no separate `trust_signals`
table (D5), no age-verification columns, no compliance-status columns.

## AC Trace — Direct Tests

All four ACs have at least one dedicated test in the proposal's AC
Trace section.

### AC1 — "active record with server-assigned id"
`.pipeline/proposal.md:397-402`
- `test_create_member_returns_active_with_uuid_id` — direct
- `test_create_member_idempotent_on_duplicate_discord_user_id` — D11 path
- `test_create_member_requires_member_write_permission` — D9 gating
- `test_get_member_by_id_returns_current_state` — read-back surface
- `test_get_member_by_discord_id_404_when_absent` — `by-discord` 404

### AC2 — "deterministic trust profile using current policy version"
`.pipeline/proposal.md:405-412`
- `test_compute_trust_creates_profile_with_current_policy_version` — direct
- `test_compute_trust_is_deterministic_given_same_signals_and_policy` — D6
- `test_compute_trust_returns_existing_profile_on_retry` — D3 idempotency
- `test_compute_trust_concurrent_same_member_returns_same_profile_to_both`
  — D11 race recovery
- `test_compute_trust_returns_409_when_no_trust_policy` — D4 typed error
- `test_compute_trust_returns_409_when_policy_shape_invalid` — typed
  error for deterministic scoring boundary
- `test_trust_profile_stores_policy_version_id_for_replay` — D4 persistence

### AC3 — "Discord join uses API, not local logic"
`.pipeline/proposal.md:415-418`
- `test_handle_member_join_creates_member_when_absent` — direct
- `test_handle_member_join_reuses_member_when_present` — D11 handler path
- `test_handle_member_join_computes_trust_and_derives_intake_required`
  — D7 `intake_required` derivation
- `test_handle_member_join_records_originating_user_in_audit` — D8

### AC4 — "stale N returns 412"
`.pipeline/proposal.md:421-424`
- `test_patch_member_status_with_current_version_succeeds_and_advances_version`
  — current-version success leg
- `test_patch_member_status_returns_412_on_stale_version` — stale-412 leg

## D12 Anti-Scope — Honored

The D12 exclusion list (`.pipeline/synthesis.md:89-103`) is restated
verbatim at `.pipeline/proposal.md:72-85`, and every exclusion is
confirmed against the body of the proposal:

| D12 exclusion | Check |
|---|---|
| Trust recomputation | `compute_trust()` returns existing profile without recomputing (`.pipeline/proposal.md:240-241`); no `/trust/recompute` endpoint. |
| Trust signal extensibility | `TrustSignalsInput` pins exactly the four D5 fields (`.pipeline/proposal.md:210-215`); no plugin/extension hook. |
| Member merge/split | No merge or split endpoints or services. |
| Member data export | No export endpoint. |
| Compliance-driven status changes | Status transitions restricted to the D2 matrix (`.pipeline/proposal.md:156-159`); no compliance status. |
| Per-chapter member visibility | All member/trust endpoints require global scope only (`.pipeline/proposal.md:168-180`, `.pipeline/proposal.md:285-293`). |
| Age verification | No age signal, no verification surface. |
| Phone verification | No phone signal, no verification surface. |

The D10 roster-FK deferral is also restated
(`.pipeline/proposal.md:84-85`); `wu-011_members.py` does not alter
`roster_entries`.

## Revision 1 Additions — Verified Non-Scope-Expanding

Revision 1 added four items (`.pipeline/proposal.md:435-439`). All four
are verification / closure of already-binding decisions, not new scope:

1. **Pinned `StaleMutationError | UniqueViolation` recovery**
   (`.pipeline/proposal.md:252-261`). Implementation of D3/D11
   idempotency, not a new capability.
2. **AC4 stale-version PATCH tests**
   (`.pipeline/proposal.md:421-424`). Adds the missing direct test for
   the ticket AC4 wording; closes prior round's MEDIUM. No endpoint
   added.
3. **`member-onboarder` service actor grants = read + write on both
   member and trust** (`.pipeline/proposal.md:200-203`). Verbatim D9
   (`.pipeline/synthesis.md:71-75`). Minimum needed for the already-
   in-scope handler flow plus read-after-write recovery; no new
   operator-visible surface.
4. **Typed `InvalidTrustPolicyError -> 409`**
   (`.pipeline/proposal.md:278-280`, `.pipeline/proposal.md:290-291`).
   A typed failure mode on the existing compute endpoint, paralleling
   the already-in-scope `no_trust_policy_configured` 409. Required for
   D6 determinism to be testable.

## Invariant Tests

Three additional invariant tests at `.pipeline/proposal.md:428-430`
(`test_member_onboarder_service_actor_has_read_and_write_grants_after_migration`,
`test_no_hardcoded_system_actor_in_members_service`,
`test_unique_discord_user_id_enforced`). These guard D9/D11 and are
properly labeled as invariants rather than AC coverage — they do not
inflate the AC Trace surface.

## Recommendation

**Accept.** The proposal delivers exactly the ticket's four ACs and
six-endpoint-plus-handler surface, honors the D12 anti-scope list, and
every Revision 1 addition is a close-out of a prior risk finding rather
than new scope. No scope changes required.
