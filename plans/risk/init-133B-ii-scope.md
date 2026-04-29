# INIT-133B-ii — Scope risk gate

**Verdict:** LOW

## In scope (justified)

- **Two new bridge GETs: `GET /api/v1/web/officer/applications/{application_id}` and `GET /api/v1/web/officer/applications/{application_id}/transcript`** in `services/api/app/api/v1/endpoints/web.py`. Both reuse `_build_officer_actor` (verified at `services/api/app/api/v1/endpoints/web.py:67-116`) and `_db` (verified at `:40-41`). No edits to `_build_officer_actor` itself. Both endpoints are read-only — no `If-Match`, no `set_etag`, no mutation body. Each delegates to existing services (`read_application` + `require_application_read_authority`, `read_application_transcript`) and routes errors through the existing `raise_known_application_error` mapper. Load-bearing because the SPA cannot supply trusted `X-Actor-*` headers.
- **`ApplicationDetailRoute.tsx` (new) at `services/web/src/features/officer/`.** Owns auth bootstrap (mirroring β-i's `ApplicationQueueRoute` pattern verified at `services/web/src/features/officer/ApplicationQueueRoute.tsx:67-78`), parallel detail/transcript fetch, metadata/responses layout, and transcript rendering. Route-local Solid signals only — no global store added.
- **`services/web/src/api/client.ts` expansion**: add transcript Zod schemas (state-change + message + discriminated union + read), add `fetchOfficerApplication` / `fetchOfficerApplicationTranscript`, and expand `applicationReadSchema` to include detail-only fields (`form_definition_id`, `form_version`, `form_snapshot`, `responses`, plus all timestamp fields). Schema expansion is additive — existing β-i `fetchOfficerApplicationQueue` / `claimOfficerApplication` callers remain valid because those fields were carried via passthrough.
- **`services/web/src/app/router.tsx`**: add the dynamic `/applications/$applicationId` route alongside existing `/applications` and `/applications/queue` routes. Single route addition.
- **`services/web/src/features/officer/officer.module.css`**: add detail + transcript layout styles using the existing officer CSS module. No global style system change.
- **One new Pomerium route entry** in `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`: `prefix: /applications/`, inserted after the existing `prefix: /applications/queue/` entry (verified at `:73-78`) and before the public catch-all (verified at `:91-94`). β-i exact `path: /applications/queue` and `prefix: /applications/queue/` entries are unchanged. First-match-wins ordering preserves the bare `/applications` public route.
- **Queue row navigation affordance + post-claim navigation in `ApplicationQueueRoute.tsx`** (small edit). Connects β-i queue rows to β-ii detail surface and lets the e2e flow navigate post-claim. Claim behavior, filter state, principal probe, and bootstrap order remain unchanged. Load-bearing connective tissue — without it, β-ii ships a route with no in-app way to reach it from β-i.
- **API tests in `services/api/tests/test_web_officer_applications.py`**: extend with detail + transcript happy paths, identity failures, authority denied, 404, and expand the dependency-tree guard from list+claim to list+claim+detail+transcript routes. Keeps the locked-actor / no-receipt / no-`X-Actor-*` source assertions in place.
- **Component tests in `services/web/tests/officer-detail.spec.ts`** (new): auth states, detail render, transcript render with `type` discriminator, 403/404/422/Zod/network/5xx error panels, and a regression assertion that no detail-route control issues POST/PUT/PATCH/DELETE.
- **Test 19 e2e + browser-flow extension**: after the existing claim leg navigate to `/applications/{claimed_id}` and assert detail metadata + claim state-change transcript entry. Test number stays 19 (β-i flow already owns this number).
- **`infra/tests/test_applicant_discord_pomerium.py`**: extend route-order/collision assertions for the new `/applications/` prefix vs bare `/applications` (public) and `/applications/queue` (β-i).
- **`infra/tests/fixtures/web-ui/contract.json`** + **`infra/tests/validate_web_ui_local.sh`**: add fixtures and static checks for the two new browser API paths and the new spec.

## Out of scope (deferred)

- Message thread / `POST /messages` — INIT-133B-iii (proposal §8).
- Non-claim transitions (review/approve/deny/waitlist/interview/reactivate/withdraw/reassign) — INIT-133B-iii.
- Claim button on the detail page — beta-i queue remains the claim surface.
- Transcript filter UI, pagination, live updates, SSE, WebSocket — explicitly anti-scope.
- Actor display-name / member lookup; show actor kind + truncated id only.
- Field-definition-aware response rendering; plain key-value rows only.
- Schema migration, new permission, new actor kind, `member_links`, applicant-receipt officer identity, browser actor headers, feature flags, compatibility shims, deprecated aliases, placeholder stubs (proposal §8).
- Discord-visible writes, DMs, channel creation, role changes, embeds, moderation actions.
- Touching `services/applications.py`, `contracts/applications.py`, `repositories/applications.py`, application state machine, message append, database migrations, Authentik blueprints, authority internals, member-resolver internals.
- Touching the applicant form route, public submit endpoints, admin chapters route, applicant-receipt machinery, or any pre-existing β-i Pomerium route entry.

## Risk surface

| Area | Pre (post-β-i) | Post (β-ii) | Justification |
|---|---|---|---|
| Officer bridge surface | 2 endpoints: `GET /web/officer/applications`, `POST /web/officer/applications/{id}/claim` | + `GET /web/officer/applications/{id}`, + `GET /web/officer/applications/{id}/transcript` | Two read-only adds; reuse `_build_officer_actor`, `_db`, and `raise_known_application_error` verbatim |
| `_build_officer_actor` | Single helper, 50 lines | Identical | No edits; both new endpoints call it as-is |
| SPA routes | `/`, `/applications`, `/applications/queue`, `/admin/chapters` | + `/applications/$applicationId` | Single route addition |
| `ApplicationQueueRoute.tsx` | β-i claim + filter behavior | Same + per-row detail navigation affordance + post-claim navigate | Behavioral surface preserved (claim, filters, principal probe, bootstrap unchanged); only navigation glue added |
| `client.ts` | β-i fetchers + narrow `applicationReadSchema` (passthrough) | + transcript schemas, + 2 fetchers, + explicit detail fields on `applicationReadSchema` | Additive; existing β-i callers continue to work because the new fields were already carried via passthrough |
| Pomerium routes | β-i officer/admin/queue routes + applicant-form public catch-all | + one `prefix: /applications/` between queue prefix and catch-all | First-match-wins preserves `/applications` public + `/applications/queue` β-i |
| Identity / authority | Pomerium → officer group → discord_user_id → real Discord member → `ActorIdentity(user, member uuid)` | Identical | No new claim, no new group, no new actor kind |
| Backend services touched | None (β-i added bridge only; service layer untouched) | None — read paths delegate to `read_application`, `require_application_read_authority`, `read_application_transcript`, `read_application_messages` | Reuses INIT-132 transcript service and INIT-133A read authority unchanged |
| Database / schema | Unchanged | Unchanged | No migration, no new column, no new table |
| Authentik | β-i officer Discord OAuth source + officers group | Unchanged | No new app, source, scope, or group |
| `applicant_receipt` cookie | Untouched by bridge | Untouched | Bridge ignores receipts and `X-Actor-*` for all four officer routes; guard test extended to cover new routes |
| Test surface | β-i officer queue + claim tests + dependency-tree guard | + detail/transcript bridge tests, + officer-detail spec, + e2e post-claim leg, + Pomerium route-order assertion for new prefix | Each test covers code shipped here; dependency-tree guard scaled to 4 routes |

## Splittable concerns

- **Detail GET vs transcript GET could in principle land separately.** They do not depend on each other at the bridge layer. The proposal bundles them because (a) the detail route is the only browser surface that calls either, (b) the e2e leg verifies metadata + transcript together (the claim transition is the natural transcript proof), and (c) the diff budget (~+430 net) is well under β-i's +1,060 — splitting would double the route-policy/Pomerium-static-test/fixture overhead for negligible benefit.
- **The Pomerium `prefix: /applications/` entry is NOT separately splittable.** It only gates the new detail route; landing it ahead would gate a path that doesn't yet exist.
- **The queue-route navigation affordance is NOT separately splittable.** Without it β-ii ships an unreachable route from inside the SPA. The edit is the smallest possible change consistent with letting officers reach detail from queue and letting the e2e flow continue post-claim.

## Verdict reasoning

LOW. The slice is read-only and additive across every surface:

1. **Bridge** — Two GETs reusing `_build_officer_actor` verbatim (verified `web.py:67-116`); no helper edits, no new identity logic, no `If-Match` or ETag complexity. Error mapping reuses `raise_known_application_error` already in `_shared.py`.
2. **SPA** — One new route, one new spec, additive client schemas. The queue-route edit is a small navigation affordance with claim/filter/principal behavior preserved (verified against `ApplicationQueueRoute.tsx:41-220`).
3. **Pomerium** — Exactly one new prefix entry inserted at the locked position (after `:73-78` queue-prefix, before `:91-94` catch-all); β-i entries unchanged.
4. **No schema, no new permission, no new actor kind, no new identity claim** — anti-scope §8 is explicit and the proposal §6 trust chain reuses `read_application`, `require_application_read_authority`, `read_application_transcript`, `read_application_messages`, all pre-existing.
5. **No applicant-flow, public-submit, admin-chapter, or Discord-visible surface is touched.** Bare `/applications` stays public via catch-all; submit and admin endpoints are not in §3's modified-file list.
6. **Diff budget** is `+430 / -20` with a documented fail-condition at `+600` net or any state-machine / message-append / migration / Authentik / authority touch.

The two judgment calls worth naming explicitly — both LOW-risk:

- The queue route IS edited (navigation glue) despite the user's "untouched" check. This is load-bearing connective tissue for letting officers reach detail from queue and for the e2e flow to navigate post-claim. Not feature creep.
- The β-i `applicationReadSchema` is expanded with explicit detail fields. Existing β-i callers remain valid because the fields were already carried via passthrough; this tightens the contract rather than changing it.

No "while we're at it" cleanups, no audits of pre-existing systems, no scope leakage outside the officer surface.

SCOPE_DONE: plans/risk/init-133B-ii-scope.md
