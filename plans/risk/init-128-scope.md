READ:
- proposals/09-receipt-required-submit.md
- research/15-receipt-required-submit-problem-map.md
- .tmp/rca/member-conversion-FINDINGS.md
- ~/ai/workflows/implementation-pipeline.md
- proposals/08-applicant-discord-oauth.md
- plans/risk/init-127-scope.md

# INIT-128 / BL-017 Phase 4 — Scope Risk

**Verdict:** LOW
**Supported-surface termination signal:** none observed in this dimension (handled by the supported-surface report)
**Re-runs against revisions:** none yet

This report evaluates only scope coherence. Audit checklist obligations, assumption-register evidence, and net-value/blast-radius are owned by the audit and supported-surface reports.

## 1. Scope ↔ Anti-scope coherence

| Scope item | Matched anti-scope guard | Coherent? |
|---|---|---|
| Widen `applicant_receipt` cookie path in `auth_discord.py` so browser sends it to both `/auth/discord/me` and `/api/public/applications` | "No authenticated officer route behavior change"; INIT-127 OAuth surface untouched | Yes — the change is path-only on the existing applicant cookie set in the INIT-127 callback (`proposals/09-receipt-required-submit.md:39`, `proposals/09-receipt-required-submit.md:75-79`); HttpOnly, Secure, SameSite=Lax, max-age semantics are preserved, and officer Pomerium auth is not touched. The cookie-path widening is the *bug fix* identified in the problem map (`research/15-receipt-required-submit-problem-map.md:101-106`) and is necessary for receipt-required submit to function in a real browser. |
| FastAPI dependency `verify_applicant_receipt(request) -> DiscordIdentity` returning structured `401` `applicant_receipt_required` | "No `X-Discord-User-Id` or other redundant identity header" | Yes — the receipt is the sole trust boundary; the dependency reads only the cookie and rejects all invalid receipt classes with one error code (`proposals/09-receipt-required-submit.md:81-101`). |
| Change `POST /api/v1/public/applications` to require receipt while retaining `Depends(authorize_public_intake)` | "No Cedar policy edits" | Yes — Cedar's `Public::"web-intake.<channel>"` route gate is preserved; receipt verification answers a different question ("which Discord user is submitting?") and stacks under the existing Cedar gate (`proposals/09-receipt-required-submit.md:108-114`, `.tmp/rca/member-conversion-FINDINGS.md:188-200`). |
| Replace anonymous public-submit service path with `submit_public_application_with_receipt(...)` calling `_submit_application_internal(..., _SubmissionAuthority.USER)` | "No retained anonymous submit path, including in the e2e suite" | Yes — the active endpoint stops calling `submit_public_application()` and never reaches `resolve_or_create_public_intake_member()` for new submits (`proposals/09-receipt-required-submit.md:104-114`, `proposals/09-receipt-required-submit.md:148-149`). The proposal explicitly retires the anonymous happy path. See §4 below for the convention check on the residual `submit_public_application()` symbol. |
| Add `resolve_or_create_real_discord_member(discord_user_id) -> Member` with `INSERT ... ON CONFLICT DO NOTHING` plus final `SELECT` | "No `members.kind` schema changes"; "No `member_links` table" | Yes — the helper uses the *existing* `members.discord_user_id` unique constraint (wu-011) and the *existing* `members.kind` constraint (wu-043) as the race boundary; no new table, no new column, no new enum value (`proposals/09-receipt-required-submit.md:117-130`). |
| Emit `application.public_submitted` notification event with payload `discord_user_id`, `applicant_member_id`, `application_id` | "No DM materialization or Discord send" | Yes — the proposal explicitly calls `notification_events.emit()` to insert one row plus a deferred `notifications_materialize` effect, and just as explicitly defers actual envelope/DM resolution to BL-020 because the current materializer does not handle "recipient comes from event payload" (`proposals/09-receipt-required-submit.md:152-165`). The event is an internal API/database effect, not a Discord-visible write. |
| SPA: re-fetch `/auth/discord/me` before submit; redirect to `/auth/discord/start?return_to=/applications` on 401; never send redundant identity headers | "No `X-Discord-User-Id` or other redundant identity header"; "No private review channel, transcript, or in-product chapter management work" | Yes — the SPA work is bounded to gating submit on the existing INIT-127 endpoint and never widens to chapter/review UI (`proposals/09-receipt-required-submit.md:168-178`). |
| Update `19-web-ui.sh` and `browser-flow.mjs` to seed a valid receipt before submit; suite stays at 19 specs | "No retained anonymous submit path, including in the e2e suite" | Yes — the existing INIT-120 anonymous-submit assertion (`infra/tests/e2e/tests/19-web-ui.sh` checking `discord_user_id` starts with `public:`) is replaced, not paired with a parallel anonymous spec (`proposals/09-receipt-required-submit.md:47`, `proposals/09-receipt-required-submit.md:243-245`). |

**No anti-scope item is contradicted by any scope item.**

## 2. Implementation choices inside scope

Each implementation decision in `proposals/09-receipt-required-submit.md:62-72` lives inside the declared scope:

- **Receipt-required submit (RCA Option B)** — within the "Change `POST /api/v1/public/applications` to require the receipt dependency" scope item; explicit RCA citation (`.tmp/rca/member-conversion-FINDINGS.md:107-119`) and matches the user-confirmed product direction.
- **Forward-path member binding using member UUID as actor id** — within the "Replace the active anonymous public-submit service path" scope item; correctly identifies the `_require_submit_authority()` self-submit invariant that requires `actor.actor_id == str(applicant_id)` (`proposals/09-receipt-required-submit.md:64-65`, `services/api/app/services/applications.py:298-307`). Using the Discord snowflake as the actor id would silently fall through to grant lookup and reject legitimate self-submits — the proposal catches this trap.
- **No `member_links` table** — anti-scope literal match; justification cites the absence of a durable applicant-controlled ownership proof for synthetic rows (`.tmp/rca/member-conversion-FINDINGS.md:121-170`).
- **Cookie path widened to `/`** — within the "Widen the applicant receipt cookie path" scope item; the security tradeoff is named and bounded (HttpOnly + Secure + SameSite=Lax + short TTL + HMAC-signed snowflake-only receipt), and the RCA-identified browser-vs-nginx path-rewrite issue is the load-bearing reason a narrower path will not work (`proposals/09-receipt-required-submit.md:75-79`, `.tmp/rca/member-conversion-FINDINGS.md:97-98`).
- **No `X-Discord-User-Id` redundancy** — anti-scope literal match; correctly identifies the HS256 receipt as the sole trust boundary.
- **Notification event in this slice, DM materialization deferred** — within the "Emit notification event" scope item and explicitly bounded against the "No DM materialization or Discord send" anti-scope; deferral is grounded in the existing materializer's static-recipient limitation (`proposals/09-receipt-required-submit.md:163-165`, BL-020 ownership).
- **E2E seeds a valid receipt rather than driving the live OAuth/Authentik dance** — within the "Update `19-web-ui.sh` and `browser-flow.mjs`" scope item; the chosen mechanism (test-helper endpoint or Playwright-injected cookie with test-mode HMAC key) keeps the suite at 19 specs and avoids brittle external-OAuth coupling. The RCA explicitly framed this as an open question and the proposal closed it (`.tmp/rca/member-conversion-FINDINGS.md:213-214`).
- **SPA receipt-state caching for the cookie TTL with a re-fetch on submit** — within the "Update the SPA" scope item; correctly notes that SPA state is advisory and the API remains authoritative.

No implementation decision pulls a non-scope file or surface into the slice.

## 3. Out-of-scope discipline

Each named anti-scope item has a corresponding implementation guard:

| Anti-scope item | Guarded by |
|---|---|
| No `member_links` table | Implementation decision (`proposals/09-receipt-required-submit.md:66`); resolver uses existing `members.discord_user_id` unique constraint as the race boundary, no new table is created. |
| No auto-conversion or application re-pointing for historical synthetics | Summary explicitly states "Synthetic `members.kind='public_intake'` rows that already exist remain historical orphans; this slice does not link, convert, or clean them" (`proposals/09-receipt-required-submit.md:29`). BL-018 owns cleanup. |
| No DM materialization or Discord send | Notification event emission is internal-only: `notification_events.emit()` writes one row and queues `notifications_materialize`, but the proposal explicitly says "Set recipient semantics in the event payload, not by sending a Discord DM" and defers DM resolution to BL-020 (`proposals/09-receipt-required-submit.md:163-165`). The TG-9 test asserts a deferred-effect queue entry, not a Discord-visible send. |
| No `members.kind` schema changes | Resolver consumes the existing `kind in ('discord','public_intake')` constraint from wu-043 without modification; corruption check on `kind != 'discord'` for an existing snowflake row is a *read-side* invariant, not a schema change (`proposals/09-receipt-required-submit.md:124-130`). |
| No Cedar policy edits | `Depends(authorize_public_intake)` is preserved unchanged on the public submit endpoint (`proposals/09-receipt-required-submit.md:108-114`); the receipt is layered on top of, not replacing, the route gate. |
| No chapter channel config | Notification event payload does not include a chapter or channel id; the in-product chapter management surface is anti-scope and explicitly deferred to BL-019 (`proposals/09-receipt-required-submit.md:60`, `proposals/09-receipt-required-submit.md:279`). |
| No `X-Discord-User-Id` or other redundant identity header | Implementation decision (`proposals/09-receipt-required-submit.md:68`); SPA scope item explicitly forbids redundant identity headers (`proposals/09-receipt-required-submit.md:175`); test TG-11 asserts headers exclude redundant identity. |
| No authenticated officer route behavior change | Scope is bounded to `/api/v1/public/applications`, `/auth/discord/*` cookie path, and `/applications` SPA. Supported-surface track explicitly states "Authenticated `POST /api/v1/applications` continues to require actor headers and use `AUTHENTICATED_SUBMIT_SURFACE`" (`proposals/09-receipt-required-submit.md:206`). |
| No retained anonymous submit path, including in the e2e suite | Endpoint dependency makes anonymous submit return `401`; e2e replaces the INIT-120 anonymous assertion rather than running it alongside a new spec; suite count stays at 19 (`proposals/09-receipt-required-submit.md:243-245`). |
| No private review channel, transcript, or in-product chapter management work | All deferred to BL-019 / BL-020 / BL-009 in §"Out of scope for follow-up" (`proposals/09-receipt-required-submit.md:276-281`). |

**No anti-scope item is silently violated.**

## 4. Convention compliance — no backwards-compat shim

The pipeline rule (`~/ai/workflows/implementation-pipeline.md:28`, `~/ai/conventions/no-backwards-compatibility.md`) forbids backwards-compat shims, including flag-gated dual paths.

The proposal removes the anonymous path cleanly:

- The active endpoint dependency `verify_applicant_receipt` is required, not flag-gated. Missing/invalid receipts return structured `401`; there is no environment variable or feature flag that re-enables anonymous behavior at runtime (`proposals/09-receipt-required-submit.md:104-114`).
- The SPA submit gate is unconditional. There is no client-side flag to bypass `/auth/discord/me` and POST anonymously (`proposals/09-receipt-required-submit.md:168-178`).
- The e2e suite removes the anonymous assertion outright; it is not "kept under a deprecated flag" (`proposals/09-receipt-required-submit.md:243-245`).
- The rollback path is a *git revert*, not a flag flip — "Revert SPA submit gating to the prior direct POST behavior. Remove the public endpoint receipt dependency..." (`proposals/09-receipt-required-submit.md:266-273`). This is the correct rollback shape under no-backwards-compat: the deployed system runs one path at a time.

**Watch signal (non-blocking) — soft retention of legacy symbols.**

The proposal says "The new service must not call `resolve_or_create_public_intake_member()` and must not derive a `public:<hash>` id. The old `submit_public_application()` can remain only if it is unreachable from active routes and explicitly treated as BL-018 legacy/e2e cleanup surface." (`proposals/09-receipt-required-submit.md:148-149`).

Strictly read, this allows three Python symbols (`submit_public_application`, `resolve_or_create_public_intake_member`, and the `_SubmissionAuthority.PUBLIC_INTAKE` value if it would otherwise become orphaned) to remain in the codebase as dead-on-the-active-path code. That is a borderline case under the no-backwards-compat convention:

- It is **not** a flag-gated dual path: there is no runtime branch that selects between receipt-required and anonymous behavior.
- It is **not** a deferred stub: the symbols already exist and have working bodies.
- It **is** unreferenced legacy code that the proposal expects BL-018 to delete.

The cleaner reading of the convention is that `submit_public_application()` and `resolve_or_create_public_intake_member()` should be deleted in this slice, since the `_SubmissionAuthority.PUBLIC_INTAKE` audit-actor and `members.kind='public_intake'` enum value remain available for BL-018's archival/cleanup tooling without needing the old write paths to keep compiling.

**Recommendation (non-blocking, does not fail the gate):** Phase 5 hookpoint research should explicitly decide whether `submit_public_application()` and `resolve_or_create_public_intake_member()` are deleted in this slice or retained for BL-018. Either decision is recordable; the watch signal is that "retain unreachable" is the weaker option and should be taken only if BL-018 has a concrete, near-term need that requires these symbols rather than reading their git history. The proposal's framing ("can remain only if … explicitly treated as BL-018 legacy/e2e cleanup surface") already gates this on Phase 5's choice and does not prescribe retention.

This watch signal does not block the gate because it is a Step 5 hookpoint decision the proposal correctly flagged as still open, and because nothing in the *active runtime path* of the slice depends on the legacy symbols.

## 5. Adjacent-path discipline

### 5.1 Officer flows

The supported-surface track explicitly bounds the cohort to "web applicants submitting through `/applications`" and excludes "officers, protected admin APIs, Pomerium officer auth, and authenticated officer review paths" (`proposals/09-receipt-required-submit.md:195`). Concrete check: the authenticated `POST /api/v1/applications` endpoint, its actor-header contract, and `AUTHENTICATED_SUBMIT_SURFACE` are not modified (`proposals/09-receipt-required-submit.md:206`). **Coherent.**

### 5.2 INIT-124 / 125A synthetic-member boundary guards

The proposal correctly identifies that `applicant_synthetic_not_allowed` continues to fire for non-`kind='discord'` applicants under USER authority and routes the new submit through that exact guard with a real `kind='discord'` member (`proposals/09-receipt-required-submit.md:200`). The `members.kind` discriminator added by INIT-125A is the load-bearing primitive the resolver depends on (`migrations/versions/wu-043_members_kind.py:15-31`). **Coherent — INIT-128 strengthens, not weakens, the INIT-124/125A guard set.**

### 5.3 INIT-127 OAuth surface

The proposal makes one change inside the INIT-127 surface: it widens the `applicant_receipt` cookie path from `"/applications"` to `"/"` in `discord_auth_callback()` (`proposals/09-receipt-required-submit.md:75-79`). All other INIT-127 surfaces — `/auth/discord/start`, `/auth/discord/callback` token-exchange/JWKS validation, `/auth/discord/me`, the receipt JWT claim contract, the Authentik blueprint, the Pomerium route — are explicitly unchanged (`proposals/09-receipt-required-submit.md:199`).

The cookie-path widening is properly scoped:

- It is a fix for a bug *already present* in INIT-127's shipped behavior, identified by the problem map (`research/15-receipt-required-submit-problem-map.md:101-106`) and the RCA (`.tmp/rca/member-conversion-FINDINGS.md:97-98`). INIT-127's tests do not catch the bug because they pass explicit `Cookie` headers.
- Without this fix, receipt-required submit cannot work in a real browser, so deferring the cookie-path fix to a hypothetical INIT-127 follow-up would create an artificial cross-slice dependency and ship a slice that fails its own e2e.
- The change is single-line, additive in surface area (more paths receive the cookie), and the existing security attributes (HttpOnly, Secure, SameSite=Lax, short TTL) bound the attack surface.

**Coherent — the INIT-127 reach-in is minimal, justified, and recorded as an explicit implementation decision.**

### 5.4 INIT-120 anonymous path

Anti-scope removes this path from the active route and from the e2e suite. The proposal does not retain a parallel anonymous spec or a flag-gated alternate route. The cleanup of historical `kind='public_intake'` rows is explicitly deferred to BL-018. **Coherent.**

### 5.5 Cedar policy

Cedar `Public::"web-intake.<channel>"` route gate is preserved; the receipt verification is *added* below the Cedar gate, not substituted for it. No new principal (e.g., `Applicant`, `User::<discord_user_id>`) is introduced. **Coherent with anti-scope.**

### 5.6 Notification substrate

Event emission is in scope; envelope materialization and Discord delivery are anti-scope and deferred to BL-020. The proposal correctly identifies that the current materializer (`services/api/app/services/notifications_materialize.py:77-122`) cannot resolve "recipient from event payload" and uses that limitation as the load-bearing reason for the deferral. **Coherent — internal-only event emission does not breach the "no DM materialization or Discord send" anti-scope.**

## 6. Decompose-trigger check

No scope-risk decompose trigger fires:

- The slice has one product surface (public web submit) with one cohort (web applicants).
- Adjacent-path reach-ins are bounded to one well-justified cookie-path fix on the INIT-127 surface.
- The work is decomposed across distinct artifacts (cookie path, dependency, resolver, service, event, SPA, e2e) but they are all required for a single coherent contract change. Splitting them across slices would require flag-gated dual paths (which the no-backwards-compat convention forbids) or ship a slice that fails its own e2e.

The proposal's "Suggested decomposition" in the RCA (`.tmp/rca/member-conversion-FINDINGS.md:225-231`) is a *Step 5 implementation ordering* recommendation, not a slice-split. The proposal correctly keeps it as one slice because each piece is load-bearing for the others.

## 7. Verdict

**LOW.**

- All scope items have matching anti-scope guards or are explicitly bounded.
- All anti-scope items are covered by named implementation guards.
- Adjacent-path reach-ins (cookie path widening on INIT-127) are minimal, justified, and required for the slice to function.
- The slice is convention-compliant on no-backwards-compat: the active runtime has no flag-gated dual path, and rollback is a git revert.

**Watch signals (non-blocking, hand to Step 5 hookpoint research):**

1. **W1 — Legacy symbol retention.** Phase 5 should explicitly decide whether `submit_public_application()` and `resolve_or_create_public_intake_member()` are deleted in this slice or retained for BL-018. "Retain unreachable" is the weaker option under no-backwards-compat; prefer deletion unless BL-018 has a near-term concrete need.
2. **W2 — Resolver implementation tension.** The scope locks `INSERT ... ON CONFLICT DO NOTHING + SELECT` as the race posture (`proposals/09-receipt-required-submit.md:43`) but also requires preserving the `aggregate_heads` + `mutate_entity()` audit invariants that the existing `create_or_get_member()` provides via unique-violation recovery (`proposals/09-receipt-required-submit.md:128`). Phase 5 must pick *one* implementation that satisfies both constraints — either extend `create_or_get_member()` to use `ON CONFLICT` directly while keeping its audit/aggregate hooks, or introduce a new helper that replicates the audit/aggregate side-effects under the locked race posture. This is an implementation-detail decision, not a scope explosion, but Phase 5 should not silently soften either constraint.
3. **W3 — Notification event without materialization rule.** Deferring DM materialization to BL-020 means production notification workers will see a new `event_type='application.public_submitted'` with no matching materialization rule for the dynamic recipient. Phase 5 / Phase 6 should confirm that the worker treats this as "no envelope to create" (no failed-event drift) rather than as a stuck or repeatedly-retried event. If the existing worker would treat a no-rule event as a failure, scope must absorb a small materializer guard or the event emission must be feature-gated until BL-020 lands. The proposal's A3 assumption claims this is non-blocking; Phase 5/Phase 6 should empirically confirm.

None of these watch signals require proposal revision. They are flagged for Step 5 hookpoint research to close.
