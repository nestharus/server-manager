READ:
- proposals/05-synthetic-member-guard.md
- research/08-synthetic-member-guard-problem-map.md
- .tmp/rca/synthetic-public-member-pollution-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- services/api/app/services/members.py
- services/api/app/services/applications.py
- services/api/app/services/authority.py
- services/api/app/services/roster.py
- services/api/app/repositories/members.py

# INIT-124 Phase 4 — Supported-Surface Risk

## Inputs read

- `proposals/05-synthetic-member-guard.md` — full proposal, including supported-surface track (lines 209-248), net-value statement (lines 37-41), assumption register A1–A3 (lines 250-254), test-intent track (lines 256-310), and the eight named guard sites with their expected error codes.
- `research/08-synthetic-member-guard-problem-map.md` — approved Phase 2.5 problem map covering the touched surface, current supported paths, brittle behavior already present, blast-radius adjacents, deployment cohort, and open questions for proposal.
- `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md` — RCA enumerating the production sites that read `members` (or pretend to read `members`) without a real-Discord-member predicate, plus the `public:` prefix contract verified against Discord's snowflake spec (`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:111-117`).
- Phase pipeline conventions: `~/ai/workflows/implementation-pipeline.md`.
- Cited source artifacts for assumption verification and adjacent-path checks: `services/api/app/services/members.py:103-193`, `services/api/app/services/applications.py:572-769`, `services/api/app/services/applications.py:822-856`, `services/api/app/services/authority.py:131-179`, `services/api/app/services/roster.py:117-145`, `services/api/app/repositories/members.py:25-53`, `services/discord/app/handlers/application_submission.py:29-93`, `services/discord/app/handlers/onboarding.py:54-99`, `services/discord/app/handlers/roster.py:53-206`.

## Termination evaluation

Per `implementation-pipeline.md:106`, evaluate orthogonal termination signals before the LOW/MEDIUM/HIGH verdict. Order: invalidated assumption first, then non-positive value.

### Invalidated assumption check

I cross-checked each assumption in the proposal's register against current source. Detail in `## Assumption register cross-check`. Summary: cited evidence resolves at the named locations for A1, A2, and A3; each has an observable invalidation condition. No assumption is contradicted by current source. The `public:` prefix discriminator survives both the local helper at `services/api/app/services/members.py:175` and the Discord snowflake contract verified in the RCA.

**No INVALIDATED_ASSUMPTION signal.**

### Non-positive value check

Existing-state risk on the supported surface is concrete and present today. Eight officer-reachable write boundaries currently accept a synthetic `members` row as a fully real Discord member, and BL-005 explicitly tracks the resulting roster, trust, owner, and aggregate-count contamination (`plans/BACKLOG.md:144`). The named risky surfaces are:

- Authenticated submit applicant (`services/api/app/services/applications.py:594-595`) accepts any UUID that resolves through `fetch_member_by_id`, including synthetic ones.
- Application owner reassign and reactivate (`services/api/app/services/applications.py:847-855`) accept any UUID that exists in `members`.
- Application claim sets `updated["owner_id"] = reviewer_id` (`services/api/app/services/applications.py:831-832`) without a real-member check on the actor-derived owner.
- Trust signal create, compute, and recompute (`services/api/app/services/trust.py:302`, `:375`, `:462`) validate only existence in `members`.
- Leadership alias expansion (`services/api/app/services/authority.py:142-163`) reads `member_row["discord_user_id"]` and adds `public:<hash>` directly into the alias set used by grants/applications/tickets.
- Roster entry create (`services/api/app/services/roster.py:117-145`) inserts `request.member_id` without any `members` lookup at all; `roster_entries.member_id` is unconstrained `TEXT` (`migrations/versions/wu-007c_roster_foundation.py:21`).
- Member status mutation (`services/api/app/services/members.py:216-227`) locks any UUID by `_fetch_member_by_id_for_update` and transitions status with no synthetic check.

Added blast radius is bounded:

- One helper (`is_synthetic_member`) and one typed exception (`SyntheticMemberNotAllowedError`) in existing modules.
- Eight service-layer guard branches that emit six stable error codes (`applicant_synthetic_not_allowed`, `application_owner_synthetic_not_allowed`, `trust_member_synthetic_not_allowed`, `leadership_member_synthetic_not_allowed`, `roster_member_synthetic_not_allowed`, `member_status_synthetic_not_allowed`).
- An `_shared.py` exception-to-detail mapping branch that already maps generic `ValueError` to `validation_error` (`services/api/app/api/v1/endpoints/applications/_shared.py:171`).
- One `synthetic_policy: Literal["reject","omit"]` parameter on `_collect_member_aliases()` for the leadership/succession split.
- Zero schema, migration, Authentik, Pomerium, Cedar, Discord-handler, web-UI, GitOps, or channel-template edits.

Migration is code-only with code-only rollback (`proposals/05-synthetic-member-guard.md:316-332`); no synthetic rows, applications, audit rows, trust rows, or roster rows are deleted under any branch. The reduction in concrete current-state risk (eight officer-facing write paths now reject synthetic UUIDs at typed errors with stable codes) clearly outweighs the additive blast radius (six new 422 responses and one alias-policy parameter) plus the migration cost (zero schema, code-only revert).

**No NON_POSITIVE_VALUE signal.**

## Existing-state risk reduction

The proposal closes the named write boundaries flagged in both the RCA enumeration table and the problem map's "known risky or brittle behavior already present" section. The reduction is structural rather than cosmetic for several reasons:

- The single helper `is_synthetic_member()` keeps the `public:` prefix check in one module (`services/api/app/services/members.py`) that already owns the synthetic creation point at `services/api/app/services/members.py:175`. Future refactors (e.g., replacing the prefix with a `members.kind` discriminator under BL-008) need to change one helper and one constant. The proposal's Q1 and Q2 commitments lock this single source of truth.
- The typed exception `SyntheticMemberNotAllowedError` carries `code`, `field`, and `member_id` so endpoint mapping in `services/api/app/api/v1/endpoints/applications/_shared.py` and equivalents emits a stable code rather than the current `validation_error` fallback. This converts an unobservable failure ("submit returned a 422 with no specific code") into a discoverable observability signal.
- The split between `synthetic_policy="reject"` for direct leadership context and `synthetic_policy="omit"` for succession-plan alias expansion is the right asymmetry: a direct read of `/leadership-context/{synthetic_uuid}` is always wrong, while a succession plan that includes one polluted historical roster row should not lose the rest of the chapter's plan over a single synthetic holder. The proposal locks both behaviors with explicit error codes for the reject path and a documented "no `public:` text alias and no synthetic UUID owner alias contributed to grant/application/ticket lookups" contract for the omit path (`proposals/05-synthetic-member-guard.md:188`).
- The roster entry guard parses `RosterEntryCreate.member_id` as a UUID before reading `members` and rejects synthetic rows with a specific code. Today, `services/api/app/services/roster.py:117-145` does not fetch `members` at all and `roster_entries.member_id` is `TEXT`. The guard is the first layer that actually validates roster member identity, which is the most leveraged improvement in the slice because all roster-derived aggregates (compliance, archive counts, succession, leadership) read from `roster_entries`.
- Authenticated submit's split-by-authority approach (`_SubmissionAuthority.PUBLIC_INTAKE` vs `_SubmissionAuthority.USER`) is preserved verbatim from the existing internal helper signature at `services/api/app/services/applications.py:572-588`; the proposal introduces no new dispatch dimension.

The proposal explicitly defers read-side hardening for `roster_entries`, compliance, archive counts, trust profile reads, and owner workload queries to BL-008 (`proposals/05-synthetic-member-guard.md:206-207`). The fragility shifts from "any officer surface that fetches a member-by-UUID can write a synthetic row into operational state" to "pre-existing already-polluted operational rows still surface in reads until BL-008." That is a smaller, observable, and explicitly residual surface.

Residual concern (not a verdict-blocker): the proposal's posture on application owner workload queries (`list_open_applications_for_owner_ids()` at `services/api/app/repositories/applications.py:207`) is "guard owner assignment instead." Existing already-polluted owner rows continue to appear in workload aggregates. The residual artifact records this. If pre-existing pollution is widespread (assumption A3 below), reads may understate the change. The proposal's residual artifact reference at `proposals/05-synthetic-member-guard.md:312-314` is the right place for that residual.

## Adjacent-path blast-radius bounding

Adjacent paths I checked:

- **INIT-120 public submit (`POST /api/v1/public/applications`, `POST /api/public/applications`)**: this is the single sanctioned synthetic-creation surface. Verified at `services/api/app/services/applications.py:737-769`: `submit_public_application()` resolves or creates the synthetic member through `resolve_or_create_public_intake_member()` (`services/api/app/services/members.py:167-193`) and submits with `_SubmissionAuthority.PUBLIC_INTAKE`. The proposal's authenticated-submit guard at `services/api/app/services/applications.py:594-595` is gated on `submission_authority != _SubmissionAuthority.PUBLIC_INTAKE`, so the public path is preserved. T-public-submit-positive-path (`proposals/05-synthetic-member-guard.md:264-268`) is the contractually correct gate.

- **INIT-120 e2e probes**: `services/api/tests/test_public_intake_submit.py` and `services/api/tests/test_public_intake_synthetic_member.py` both assert `members.discord_user_id LIKE 'public:%'` after public submit. The proposal's positive test reuses these existing expectations (`proposals/05-synthetic-member-guard.md:267`). Adjacent INIT-120 e2e remains intact.

- **Authenticated `POST /api/v1/applications`**: this is in the rejection cohort. Existing chapter-scope authenticated submit tests must still pass because they pass real-member UUIDs; only callers who supply a synthetic UUID see new 422s. Not a regression.

- **Discord submission service**: `services/discord/app/handlers/application_submission.py:29-93` resolves the interaction actor through `/api/v1/members/by-discord/{discord_user_id}` with a numeric Discord snowflake, then submits authenticated `/api/v1/applications` with that resolved member as `applicant_id`. By construction the actor and applicant are real Discord members; the proposal does not change `/by-discord/{discord_user_id}` semantics. Adjacent path stays green.

- **Discord onboarding (`services/discord/app/handlers/onboarding.py:54-99`)**: handler reads `discord_user_id` from a `discord.Member` join event (numeric), creates or resolves that real member, then calls trust compute. No change in behavior because the `member_id` resolved from a real Discord ID is not synthetic. Adjacent path stays green.

- **Discord roster sync (`services/discord/app/handlers/roster.py:53-206`)**: handler converts `event.member_discord_user_id` with `int(user_id)` during guild member resolution. A synthetic `public:<hash>` would have crashed at `int(...)` today; the proposal stops synthetic rows at roster write time before they can ever generate a sync event. The proposal explicitly chooses this upstream-stop posture rather than handling synthetics in Discord mutation code (`proposals/05-synthetic-member-guard.md:227`). Bounded.

- **Audit substrate**: public intake keeps `actor_kind="service"` and `actor_id="public-intake"`; synthetic members remain application subjects, never actors. Verified against the proposal's restatement of the INIT-120 audit invariant (`proposals/05-synthetic-member-guard.md:104`, `proposals/05-synthetic-member-guard.md:228`) and the migration text-actor schema in `migrations/versions/wu-002_activity_substrate.py`. Anti-scope respected.

- **Members exact reads (`/api/v1/members/{member_id}`, `/api/v1/members/by-discord/{discord_user_id}`)**: kept unfiltered by design, because public intake idempotency depends on `fetch_member_by_discord_id()` finding `public:<hash>` rows (`services/api/app/repositories/members.py:36-42`). Authorized callers can still observe synthetic rows. The proposal flags this as intentional (`proposals/05-synthetic-member-guard.md:234`). Acceptable for a write-boundary slice.

- **Trust profile reads, active-signal lists**: no join to `members` today; the proposal explicitly defers read-side hardening to BL-008. Pre-existing synthetic profiles or signals remain readable. Anti-scope, with the residual logged.

- **Cedar policy, Pomerium, Authentik**: not touched. Anti-scope respected.

- **Channel-template surfaces (`gitops/channels/<channel>/applications/server-manager/`)**: not touched; this is API-service behavior, not a GitOps Job, ConfigMap, or channel-conditional renderer change. The proposal's "no code path may branch on channel" rule (`proposals/05-synthetic-member-guard.md:215`) is consistent with INIT-120's local-IS-a-deployment-target framing.

Adjacent-path coverage gap (notable observation): the test-intent track does not enumerate a regression check that succession plans for chapters with **no** pre-existing synthetic roster holders return identical alias sets after the `synthetic_policy="omit"` change. Because the omit path filters silently, a regression that drops *real* members would be invisible without a positive-control test. Step 6a/6b should add or document non-applicability.

## Migration and rollback realism

Migration is code-only and follows the order documented at `proposals/05-synthetic-member-guard.md:316-324`:

1. Tests encoded against the contract (Step 6b).
2. Helper plus typed error.
3. Service guard call sites at the eight named boundaries.
4. Endpoint error mappings (the `_shared.py` branch and any equivalents in trust/roster/members endpoint shared handlers).
5. Focused API test suite run.

Verified preconditions for the implementation path:

- The helper site is `services/api/app/services/members.py`, which already imports `_fetch_member_by_id_for_update`, `fetch_member_by_discord_id`, and `fetch_member_by_id` (`services/api/app/services/members.py:22-26`). Adding `SYNTHETIC_MEMBER_DISCORD_ID_PREFIX` and `is_synthetic_member` next to the synthetic creation point is the smallest change.
- The exception lives in `services/api/app/contracts/members.py` per the proposal. The endpoint mapping at `services/api/app/api/v1/endpoints/applications/_shared.py:171` already has a generic `ValueError` branch; adding a specific `SyntheticMemberNotAllowedError` branch above it is structurally consistent.
- The `_collect_member_aliases()` API change adds one keyword-only parameter `synthetic_policy: Literal["reject","omit"]`. Two call sites consume it: `read_leadership_context()` (`services/api/app/services/read_models.py:232-247`) and `compute_succession_plan()` (`services/api/app/services/authority.py:493-527`). No other callers exist, so the signature change is bounded.
- Roster entry creation requires a UUID parse before `fetch_member_by_id()` because `RosterEntryCreate.member_id` is non-empty text today (`services/api/app/contracts/roster.py:29-31`). The proposal acknowledges that non-UUID and missing-member errors use existing handling with different codes (`proposals/05-synthetic-member-guard.md:195`), so this is not a contract widening.

Rollback (`proposals/05-synthetic-member-guard.md:326-332`):

1. Revert the guard call sites and error mappings.
2. Keep synthetic member rows, applications, audit rows, trust rows, and roster rows intact. **Critical**: the rollback path must not delete dependent rows; `applications.applicant_id` is `NOT NULL` and FK to `members.id`, so deleting a synthetic member would cascade-violate (or, depending on FK shape, leave dangling applications). The proposal's "no data deletion under rollback" stance is the correct failure mode.
3. Re-evaluation: if rollback is triggered because a real caller depended on synthetic writes, that caller belongs in BL-008 linking — not in INIT-124.

Notable observation: rollback re-introduces the eight named contamination surfaces. The slice intentionally does not provide a "safe undo" because the original state is the contaminated state. This matches `implementation-pipeline.md:235`-style decision-recording for accepted residual risk.

The proposal does not promise to clean up already-polluted data and explicitly defers that to a separate cleanup slice (`proposals/05-synthetic-member-guard.md:336-337`). For a guard-only slice on a known-broken existing state, this is the appropriate posture.

## Observability

The proposal's observability story is six stable error codes plus existing access logs:

- `applicant_synthetic_not_allowed` for authenticated submit.
- `application_owner_synthetic_not_allowed` for claim, reassign, reactivate.
- `trust_member_synthetic_not_allowed` for trust signal create, compute, recompute.
- `leadership_member_synthetic_not_allowed` for direct `/leadership-context/{member_id}`.
- `roster_member_synthetic_not_allowed` for `POST /api/v1/roster-entries`.
- `member_status_synthetic_not_allowed` for `PATCH /api/v1/members/{member_id}/status`.

This is proportional to the slice scope. The codes are observable through API response bodies and existing structured access logs. The proposal explicitly defers a metric/alert subsystem (`proposals/05-synthetic-member-guard.md:247`).

Residual observability concerns (non-blocking):

- **Silent succession omit.** When `compute_succession_plan()` calls `_collect_member_aliases(..., synthetic_policy="omit")`, a pre-existing synthetic roster holder is silently dropped from alias expansion. There is no log signal, no error code, and no warning. If a chapter relies on the broken succession view to surface the pollution, that signal disappears with the proposal. The residual artifact at `plans/risk/init-124-test-residuals.md` should record this. Not a verdict-blocker because the alternative (rejecting the entire succession plan because one historical roster row is synthetic) is worse for officer workflow.
- **No log signal for the omit path.** Step 6a/6c discretion: a single structured-log line at the omit decision (e.g., `synthetic_role_holder_omitted` with `chapter_id` and the synthetic member UUID) would close this without breaking the slice's "no telemetry subsystem" rule. The proposal does not commit to this; consider it a Step 6 follow-up.
- **Endpoint mapping completeness.** The proposal calls out the authenticated-applications shared handler (`services/api/app/api/v1/endpoints/applications/_shared.py:171`) but does not explicitly enumerate the equivalent handlers for trust, roster, members, and authority. Step 6a should produce the full handler list so each emits the typed code rather than the generic `validation_error` fallback. If any endpoint surface drops the typed code, the observability claim degrades silently for that surface.
- **Existing 422 vs 404.** The roster entry guard "Expected API result for non-UUID or missing member: HTTP 422 or 404 per implementation convention, but not the synthetic code" (`proposals/05-synthetic-member-guard.md:195`). Step 6a should lock the convention so test contracts at the component level are unambiguous.

## Channel-template parity

The proposal stays channel-agnostic by design. Quoted from the supported-surface track (`proposals/05-synthetic-member-guard.md:213-215`): "Apply in all channels because this is API service behavior, not a local-only route condition" and "No code path may branch on channel."

Parity-relevant checks:

- The eight guarded sites are pure service logic in `services/api/app/`. No GitOps manifest, channel-conditional renderer, channel-template, or `gitops/sources/<scope>/<channel>/` resource is touched.
- INIT-120's local-IS-a-deployment-target framing (`proposals/02-public-application-intake.md:141-145`) holds: local receives concrete manifests, remote carries the same logical contract. The synthetic-member guard is a logical-contract change, not a manifest change.
- INIT-120 public intake is the supported surface that exists in local today (`research/08-synthetic-member-guard-problem-map.md:267-280`). Validation in local first is the right cohort posture; remote channels inherit the same logical contract once they are materialized under BL-013.
- No `dev`-channel-only or `local`-channel-only conditional branch is introduced into shared API code.

Local-first deployment with same-logical-contract for remote is the appropriate channel-template posture for a service-layer guard slice.

## Assumption register cross-check

For each assumption: I check (a) the cited evidence exists at the cited location and supports the claim, and (b) the invalidation condition is observable.

**A1.** "`public:` prefix is a stable identifier for synthetic members."
- Cited at `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:111-117` and `services/api/app/services/members.py:173-175`. Verified `members.py:173`: `digest = hashlib.sha256(...).hexdigest()`; `members.py:175`: `discord_user_id=f"public:{digest[:32]}"`. The RCA confirms Discord snowflakes are decimal numeric strings per Discord's developer docs (`.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:113-115`), so a real Discord ID cannot collide with `public:[0-9a-f]{32}`. Local test evidence at `services/api/tests/test_public_intake_synthetic_member.py:43` asserts `public:[0-9a-f]{32}` shape.
- Invalidation condition: a Discord-origin member row whose `discord_user_id` starts with literal `public:`, observable through `SELECT id, discord_user_id FROM members WHERE discord_user_id LIKE 'public:%'` plus source tracing showing the row came from Discord join/import rather than `resolve_or_create_public_intake_member()`. ✓

**A2.** "No production code creates members with `public:` prefix other than the INIT-120 public-intake helper."
- Cited at `services/api/app/services/members.py:175` and `services/api/app/services/applications.py:744`. Verified by repository grep: the only `public:` prefix in production member writes is `members.py:175`; the `applications.py:744` occurrence is `client_application_id = f"public:{public_submission_id}"`, which is an application identifier, not a member ID. No other production write site assigns `members.discord_user_id` with the `public:` prefix.
- Invalidation condition: any production member-write path outside `resolve_or_create_public_intake_member()` that assigns `members.discord_user_id` with the `public:` prefix, observable through repository search or write-path tracing. ✓

**A3.** "Roster entries written before INIT-120 do not contain synthetic UUIDs."
- Cited at `migrations/versions/wu-007c_roster_foundation.py:17-21` (roster foundation predates synthetic member creation, stores `member_id` as `TEXT`) and `proposals/02-public-application-intake.md:65-70` (INIT-120 introduced synthetic public-intake members later). The proposal explicitly states that if A3 is false, the pre-existing-pollution sweep handles it outside INIT-124 (`proposals/05-synthetic-member-guard.md:254`).
- Invalidation condition: a `roster_entries.member_id` value that resolves to a synthetic `members.id` row created before this slice landed. Observable through `SELECT re.id FROM roster_entries re JOIN members m ON re.member_id::uuid = m.id WHERE m.discord_user_id LIKE 'public:%'`. ✓ (Invalidation degrades the slice's reduction of read-side pollution but does not invalidate the write-boundary guard. Non-blocking.)

All three assumptions resolve at their cited locations and have observable invalidation conditions. No assumption is contradicted by current source.

## Notable observations

These are observations and watch signals, not verdict-blockers.

1. **Helper signature footgun.** `is_synthetic_member(member_or_discord_user_id: object | str) -> bool` uses `getattr(..., "discord_user_id")` for the non-`str` branch. Repository rows are `dict` (psycopg DictRow), and dicts do not expose attribute access for keys, so passing a row dict directly raises `AttributeError`. The proposal's convention "Repository rows should call the helper with `row['discord_user_id']`, not rely on dict handling" (`proposals/05-synthetic-member-guard.md:78`) is the correct discipline. Step 6a should restate this in the contract and Step 6b should add a unit test that asserts `is_synthetic_member({"discord_user_id": "public:x"})` raises (or, alternatively, narrows the type hint to `MemberRead | str` to make the constraint compile-time visible).

2. **Reviewer-id shape for application claim.** The claim guard validates `reviewer_id = _reviewer_id(actor, action)` (derived in `_transition_application_locked()` at `services/api/app/services/applications.py:811`) by `fetch_member_by_id()` and rejects synthetic. For service-actor claims (e.g., automation), `reviewer_id` may not be a member UUID. The existing claim contract already assumes `reviewer_id` is a member UUID because `updated["owner_id"] = reviewer_id` and `applications.owner_id` references `members.id`; if a service actor today crashes the existing flow, the guard does not change that. But Step 6a should make the test contract explicit so `application_owner_synthetic_not_allowed` only fires when `reviewer_id` resolves to a synthetic member, not when it fails to resolve at all.

3. **Owner workload aggregates.** `list_open_applications_for_owner_ids()` at `services/api/app/repositories/applications.py:207` is **out of scope** for the slice (`proposals/05-synthetic-member-guard.md:104`, `proposals/05-synthetic-member-guard.md:206-207`). Existing already-polluted owner UUIDs continue to surface in workload counts after the slice lands. The residual artifact must record this; a chapter that has been running since INIT-120 may see the workload aggregate diverge from the ground-truth set of officer-claimable applications until BL-008 hardens the read side.

4. **Silent omit at succession.** Discussed under `## Observability`. The omit path silently drops synthetic role holders. If pre-existing pollution exists, the change makes the symptom invisible from succession output. The omit policy is the right tradeoff for officer workflow, but the residual artifact must record that the omit is silent and that any operator who relied on succession to surface the pollution loses that signal.

5. **Pre-existing synthetic trust profiles and signals.** The proposal explicitly defers read-side hardening to BL-008 (`proposals/05-synthetic-member-guard.md:206-207`). After this slice, `GET /api/v1/trust/{synthetic_member_id}` still returns a synthetic profile if one was created before the guard landed; only **new** profile/signal creation is blocked. Step 6a/6b should make sure component tests that assert "no `trust_profiles` insert" use a fresh synthetic member rather than one that may already have a profile.

6. **Endpoint handler list completeness.** The proposal anchors the typed-error mapping at `services/api/app/api/v1/endpoints/applications/_shared.py:171`. Trust, roster, members, and authority endpoints have their own shared/error handlers that must be updated to emit the typed code. Step 6a should produce the full list; if any handler drops the typed code to `validation_error`, that surface loses the observability promise. Not a proposal-design defect, but Step 6a/6b/6c discretion.

7. **`_collect_member_aliases` API consumers.** The new `synthetic_policy: Literal["reject","omit"]` keyword-only parameter has exactly two call sites today (`read_leadership_context()` and `compute_succession_plan()`). Step 6c must ensure no third caller is added without choosing a policy, or default the parameter to `"reject"` so a forgotten caller fails closed at the leadership/succession level rather than silently leaking `public:<hash>` aliases. Default-to-reject is the safer posture for the helper signature; the proposal does not specify a default. Step 6a should lock it.

8. **Non-UUID roster `member_id`.** Roster entry create currently accepts any non-empty text in `RosterEntryCreate.member_id` (`services/api/app/contracts/roster.py:29-31`). The proposal's guard parses `request.member_id` as a UUID before `fetch_member_by_id()`. Existing callers that wrote Discord-ID-shaped (`"123456789"` numeric string) values into `roster_entries.member_id` would start failing validation. The problem map flagged this as an open question (`research/08-synthetic-member-guard-problem-map.md:304-307`). The proposal's posture is "Missing/non-UUID can use existing validation handling; synthetic uses the specific code" (`proposals/05-synthetic-member-guard.md:194-195`). If callers exist today who pass non-UUID `member_id` values for legitimate roster entries, this is a contract widening rather than a synthetic-only guard. Step 6a should confirm by repository search that all current callers pass UUIDs; if not, the slice expands beyond synthetic-only.

## Verdict

The proposal targets eight named officer-reachable write boundaries that currently accept synthetic `members` rows, locks the discriminator at the single helper `is_synthetic_member()` and the single creation site at `services/api/app/services/members.py:175`, preserves the public-intake exception verbatim through `_SubmissionAuthority.PUBLIC_INTAKE`, and emits six stable error codes that the existing endpoint shared handlers can map without contract churn. The assumption register is verifiable against current source (A1 helper site, A2 single write path, A3 falsifiable but residual-only). The supported-surface track is honest about deferred read-side hardening for trust profiles, owner workload aggregates, roster reads, compliance, archive counts, and pre-existing pollution; those are explicitly assigned to BL-008 or a dedicated cleanup slice. The blast radius is bounded to one helper, one typed exception, eight service guard branches, an `_shared.py` mapping branch, and one keyword-only parameter on `_collect_member_aliases()`. Migration is code-only with code-only rollback that intentionally does not delete dependent rows. The main residuals (helper signature footgun, claim reviewer-id shape, silent succession omit, pre-existing trust profile reads, endpoint handler list completeness, `_collect_member_aliases` default policy, non-UUID roster `member_id` callers) are Step 6a/6b/6c obligations rather than proposal defects. INIT-120 e2e remains green by design.

```
SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
```
