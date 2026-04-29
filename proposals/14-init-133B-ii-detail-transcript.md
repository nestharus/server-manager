# Proposal 14 - INIT-133B-ii / BL-019D-beta slice 2: application detail + transcript

## 1. Goal

INIT-133B-ii ships BL-019D-beta's second officer review slice: a read-only `/applications/{id}` officer detail route that loads one `ApplicationRead`, renders its metadata/responses, and renders the chronological application transcript. It layers on the INIT-133B-i officer queue shipped at `b10bedf5fa66fbc0e6f60ce4bc14070c7f455a6b`, reuses the Pomerium/Discord officer bridge, and intentionally does not add messages, transition controls, or Discord-visible side effects; those remain in INIT-133B-iii / later BL items.

## 2. Locked Decisions Q1..Q7

### Q1. Route path: `/applications/{id}` with a protected `/applications/` prefix

Lock the browser route to `/applications/{id}`; in TanStack Solid Router this is implemented as a dynamic child such as `/applications/$applicationId`. The parent queue problem map reserved this shape for detail (`research/19-init-133B-problem-map.md:112-121`), and the beta-ii problem map locks it explicitly (`research/22-init-133B-ii-problem-map.md:76-95`).

Pomerium adds exactly one new web-host entry: `prefix: /applications/`. It must be placed after the existing `path: /applications/queue` and `prefix: /applications/queue/` entries, and before the public catch-all. Current route order has the queue entries at `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:67-78` and the public catch-all at `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:91-94`. This keeps bare `/applications` public through the catch-all, keeps `/applications/queue` on its dedicated queue route, and protects `/applications/<uuid>` plus any future nested detail-owned paths.

### Q2. Detail layout: two-column desktop, stacked mobile

Lock the route to a simple detail view: left side application metadata plus responses, right side transcript. On mobile the sections stack. Responses render as plain key-value rows from `ApplicationRead.responses`; field-definition-aware rendering is not in this slice. This follows the beta-ii problem map (`research/22-init-133B-ii-problem-map.md:97-108`) and the actual `ApplicationRead` fields (`services/api/app/contracts/applications.py:352-372`).

### Q3. Transcript rendering: actual `type` discriminator, chronological feed

Render transcript entries as the shipped discriminated union, not the draft `kind` spelling from the problem map. The actual contract uses `type: "state_change"` and `type: "message"` (`services/api/app/contracts/applications_transcript.py:16-45`). State-change rows show change type, from/to state, actor kind, truncated actor id, and timestamp. Message rows show visibility, author kind, truncated author id, timestamp, and body markdown as escaped text/plain rendering for this slice. The service already sorts the merged feed by `occurred_at` (`services/api/app/services/application_transcript.py:68-73`), so the SPA preserves server order.

### Q4. Authorization model: reuse beta-i officer actor, then delegate

Reuse `_build_officer_actor` exactly as the bridge identity boundary: Pomerium principal, exact `officers` group, Pomerium `discord_user_id`, real Discord member resolution, then `ActorIdentity(actor_kind="user", actor_id=<member uuid>)` (`services/api/app/api/v1/endpoints/web.py:67-116`). Detail GET calls `read_application` and then `require_application_read_authority`; the direct lifecycle endpoint already does that at `services/api/app/api/v1/endpoints/applications/lifecycle.py:109-122`, backed by the authority helper at `services/api/app/services/applications.py:365-390`. Transcript GET calls `read_application_transcript` with the same actor identity and lets `read_application_messages` enforce message visibility and `application.message` authority (`services/api/app/services/application_transcript.py:49-73`, `services/api/app/services/application_messages.py:160-202`).

### Q5. Component and client contracts: route-local, Zod-validated

Use the same route-local signal pattern as `ApplicationQueueRoute`, which already bootstraps principal state and data in `onMount` (`services/web/src/features/officer/ApplicationQueueRoute.tsx:41-78`, `services/web/src/features/officer/ApplicationQueueRoute.tsx:112-120`). No global store is added. The client extends the existing Zod/fetch pattern in `services/web/src/api/client.ts:100-149` with full detail fields and transcript schemas.

### Q6. Test plan: extend beta-i, do not create a new e2e number

Extend `services/api/tests/test_web_officer_applications.py`, add `services/web/tests/officer-detail.spec.ts`, and extend test 19 after the existing queue claim leg. This follows the beta-i pattern: API tests use Pomerium header helpers and grants (`services/api/tests/test_web_officer_applications.py:26-67`), Playwright uses fixture-driven route mocks (`services/web/tests/officer-queue.spec.ts:44-114`), and `19-web-ui.sh` already chains public submit plus officer claim in one flow (`infra/tests/e2e/tests/19-web-ui.sh:84-90`).

### Q7. Anti-scope: read-only detail only

No claim button, no message composer, no transition controls, no transcript filter UI, no actor display-name lookup, no optimistic-locking mutation path, no live updates, and no new identity/authority model. This matches the beta-ii anti-scope (`research/22-init-133B-ii-problem-map.md:66-73`, `research/22-init-133B-ii-problem-map.md:165-172`) and the project rules against compatibility shims or deferred stubs (`AGENTS.md:564-583`).

## 3. Scope

### New files

- `services/web/src/features/officer/ApplicationDetailRoute.tsx` - Solid route for `/applications/{id}`; owns auth bootstrap, detail fetch, transcript fetch, refresh/retry state, metadata/responses layout, and transcript rendering.
- `services/web/tests/officer-detail.spec.ts` - Playwright component tests for officer detail auth states, detail rendering, transcript rendering, and read-only failure handling.

### Modified files

- `services/web/src/app/router.tsx` - add the dynamic `/applications/$applicationId` route beside the existing `/applications` and `/applications/queue` routes (`services/web/src/app/router.tsx:66-82`, `services/web/src/app/router.tsx:93-98`).
- `services/web/src/api/client.ts` - expand `applicationReadSchema` to include every detail field consumed from `ApplicationRead`, add transcript entry/read schemas, and add `fetchOfficerApplication` / `fetchOfficerApplicationTranscript` using browser-facing `/api/...` paths (`services/web/src/api/client.ts:41-69`, `services/web/src/api/client.ts:100-149`).
- `services/web/src/features/officer/ApplicationQueueRoute.tsx` - make each row expose a detail navigation affordance to `/applications/{id}` and, after successful claim, allow the e2e flow to navigate to the claimed detail route. Keep claim behavior unchanged (`services/web/src/features/officer/ApplicationQueueRoute.tsx:91-110`, `services/web/src/features/officer/ApplicationQueueRoute.tsx:171-210`).
- `services/web/src/features/officer/officer.module.css` - add route-local detail and transcript layout styles using the existing officer CSS module; no global style system change.
- `services/api/app/api/v1/endpoints/web.py` - add `GET /officer/applications/{application_id}` and `GET /officer/applications/{application_id}/transcript`; both are read-only and call Python services directly, not HTTP self-calls. Reuse `_build_officer_actor` (`services/api/app/api/v1/endpoints/web.py:67-116`) and `_db` (`services/api/app/api/v1/endpoints/web.py:40-41`).
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` - add the protected `prefix: /applications/` route on the web host, after queue exact/prefix routes and before the public catch-all.
- `infra/tests/test_applicant_discord_pomerium.py` - extend route-order/collision tests so `/applications` remains public, `/applications/queue` resolves to the queue route, and `/applications/<uuid>` resolves to the new protected prefix.
- `infra/tests/fixtures/web-ui/contract.json` - add `routes.officer_detail`, `applications.detail.endpoint`, and `applications.transcript.endpoint` fixtures.
- `infra/tests/validate_web_ui_local.sh` - extend static client/fixture assertions for the two new browser API paths and the new Playwright spec.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` - after the existing claim succeeds, navigate to `/applications/{claimed_application_id}` and assert detail metadata plus a claim state-change transcript entry.
- `infra/tests/e2e/tests/19-web-ui.sh` - keep test number 19; add the post-claim detail/transcript verification and persistence checks.

### Tests

- `services/api/tests/test_web_officer_applications.py` - add bridge detail/transcript tests and expand the dependency-tree guard to the two new routes.
- `services/web/tests/officer-detail.spec.ts` - new component test surface.
- `infra/tests/test_applicant_discord_pomerium.py`, `infra/tests/validate_web_ui_local.sh`, `infra/tests/e2e/tests/19-web-ui.sh`, and `infra/tests/e2e/lib/playwright/browser-flow.mjs` - route protection, static contract, and live post-claim navigation coverage.

### Pomerium route shape

```yaml
- from: https://web.local.humility.local
  prefix: /applications/
  to: http://server-manager-web.web.svc.cluster.local:8080
  preserve_host_header: true
  pass_identity_headers: true
  allow_any_authenticated_user: true
```

Insertion position is locked: immediately after current `prefix: /applications/queue/` (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:73-78`) and before `prefix: /admin` / public catch-all (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:79-94`). This is the only architectural choice in the slice.

## 4. API Surface Consumed

### Browser SPA calls

- `GET /api/me` - unchanged beta-i principal probe. Non-2xx, redirects, opaque fetches, or network failures show the auth-required panel; missing `officers` shows forbidden; missing `discord_user_id` shows identity incomplete. Current client path is `/api/me` (`services/web/src/api/client.ts:118-120`), and current principal contract includes `groups` plus `discord_user_id` (`services/api/app/contracts/web.py:13-19`).
- `GET /api/web/officer/applications/{application_id}` - new detail bridge. Response is `ApplicationRead`; UI handles `401 identity_missing`, `401 officer_discord_identity_missing`, `401 officer_discord_identity_invalid`, `403 officer_required`, `403 authority_decision_denied`, `404 application_not_found`, `422 validation_error`, Zod parse failure, network failure, and 5xx.
- `GET /api/web/officer/applications/{application_id}/transcript` - new transcript bridge. Response is `ApplicationTranscriptRead`; UI handles the same identity failures, `403 application_transcript_forbidden`, `404 application_not_found`, Zod parse failure, network failure, and 5xx.

The SPA does not call `/api/v1/applications/{id}` or `/api/v1/applications/{id}/transcript` directly. Browser paths remain `/api/...` because the web nginx owns the `/api/` to API `/api/v1/` rewrite, as locked in beta-i (`research/21-init-133B-i-hookpoints.md:150-154`).

### Bridge service calls

- Detail bridge wraps `read_application(db, application_id=...)` (`services/api/app/services/applications.py:887-894`) and `require_application_read_authority(...)` (`services/api/app/services/applications.py:365-390`), then returns `ApplicationRead`. It maps known errors through `raise_known_application_error`, preserving direct endpoint codes including `application_not_found` and `authority_decision_denied` (`services/api/app/api/v1/endpoints/applications/_shared.py:64-182`).
- Transcript bridge wraps `read_application_transcript(db, application_id=..., viewer_actor_kind=actor.actor_kind, viewer_actor_id=actor.actor_id)` (`services/api/app/services/application_transcript.py:49-73`). Its mapper preserves direct transcript endpoint codes: `404 application_not_found` and `403 application_transcript_forbidden` (`services/api/app/api/v1/endpoints/applications/transcript.py:22-36`).

Both bridge endpoints are `async def` only because `_build_officer_actor` awaits member resolution. After the actor is built, the service reads are synchronous Python calls, matching the beta-i bridge pattern (`services/api/app/api/v1/endpoints/web.py:119-148`, `services/api/app/api/v1/endpoints/web.py:151-209`). No `If-Match` parsing, no mutation body, and no ETag requirement are introduced in this read-only slice.

## 5. Component Contract Preview

### Route components

```ts
export function ApplicationDetailRoute(): JSX.Element;
```

`ApplicationDetailRoute` reads the route param from TanStack Router, calls `/api/me`, then loads detail and transcript in parallel only after officer identity is verified. It renders no mutation controls.

### Sub-components

```ts
export type ApplicationMetadataPanelProps = {
  readonly application: ApplicationRead;
};

export type ApplicationResponsesPanelProps = {
  readonly responses: Readonly<Record<string, unknown>>;
  readonly formSnapshot: Readonly<Record<string, unknown>>;
};

export type ApplicationTranscriptListProps = {
  readonly entries: readonly TranscriptEntry[];
};
```

### API client functions and schemas

```ts
export const applicationReadSchema: z.ZodType<ApplicationRead>;
export const applicationTranscriptStateChangeEntrySchema: z.ZodType<TranscriptStateChangeEntry>;
export const applicationTranscriptMessageEntrySchema: z.ZodType<TranscriptMessageEntry>;
export const applicationTranscriptEntrySchema: z.ZodDiscriminatedUnion<"type", [...]>;
export const applicationTranscriptReadSchema: z.ZodType<ApplicationTranscriptRead>;

export type TranscriptStateChangeEntry = z.infer<typeof applicationTranscriptStateChangeEntrySchema>;
export type TranscriptMessageEntry = z.infer<typeof applicationTranscriptMessageEntrySchema>;
export type TranscriptEntry = z.infer<typeof applicationTranscriptEntrySchema>;
export type ApplicationTranscriptRead = z.infer<typeof applicationTranscriptReadSchema>;

export function fetchOfficerApplication(applicationId: string): Promise<ApplicationRead>;
export function fetchOfficerApplicationTranscript(applicationId: string): Promise<ApplicationTranscriptRead>;
```

`applicationReadSchema` must stop relying on `.passthrough()` for fields this route renders: include `form_definition_id`, `form_version`, `form_snapshot`, `responses`, `queued_at`, `claimed_at`, `review_started_at`, `decided_at`, `withdrawn_at`, `created_at`, and `updated_at` alongside the fields already present (`services/web/src/api/client.ts:41-51`). The transcript schemas mirror the actual Pydantic contract at `services/api/app/contracts/applications_transcript.py:16-45`.

### Signals / state

Route-local Solid signals only:

- Officer auth state: `loading | auth_error | non_officer | missing_discord_claim | ready`.
- `application: Accessor<ApplicationRead | null>`.
- `transcript: Accessor<ApplicationTranscriptRead | null>`.
- `loading: Accessor<boolean>`.
- `notice: Accessor<{ kind: "error" | "info"; message: string } | null>`.

TanStack Query may be used if it stays route-local and does not introduce a durable global detail store. The beta-i global store remains theme/navigation only.

## 6. Authorization Model

Trust chain:

1. Pomerium protects `/applications/{id}` via the new `prefix: /applications/` route and protects bridge calls through the existing `/api/web/officer/` prefix (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:61-66`).
2. The route probes `/api/me`; `get_pomerium_principal` reads Pomerium headers, parses groups, and exposes `discord_user_id` (`services/api/app/api/v1/endpoints/me.py:37-55`).
3. Both new bridge endpoints call `_build_officer_actor`, which requires the officer group, validates the Pomerium Discord snowflake, resolves/creates a real Discord member, and constructs `ActorIdentity(user, member_uuid)` (`services/api/app/api/v1/endpoints/web.py:67-116`).
4. Detail GET reads the application and requires application read authority. Read authority is applicant identity or any application review/decision permission on the target scope; officer-group membership alone is not sufficient (`services/api/app/services/applications.py:159-168`, `services/api/app/services/applications.py:365-390`).
5. Transcript GET does not add a separate read-authority gate. It delegates to `read_application_transcript`, which first calls `read_application_messages`; that path lets the applicant see applicant-visible messages, lets officers with `application.message` authority see both visibilities, and rejects strangers with `ApplicationMessageAppendForbiddenError` (`services/api/app/services/application_messages.py:175-202`).

The bridge still ignores applicant receipts and browser-supplied `X-Actor-*` headers, consistent with the existing guard test (`services/api/tests/test_web_officer_applications.py:660-758`). That guard must include all four officer bridge routes after this slice.

## 7. Test Plan

### API bridge tests

Extend `services/api/tests/test_web_officer_applications.py`:

- Detail GET requires Pomerium identity, officer group, Discord claim, and real Discord member. Risk annotation: `group=TG-1; named_risk=detail_actor_binding; level=api`.
- Detail GET ignores applicant receipt and `X-Actor-*`, returning data for the Pomerium-resolved member. Risk annotation: `group=TG-1; named_risk=detail_actor_spoofing`.
- Detail GET happy path returns `ApplicationRead` with responses, version, owner/state, and timestamps. Risk annotation: `group=TG-1; named_risk=detail_contract_shape`.
- Detail GET without application read authority returns `403 authority_decision_denied`; missing id returns `404 application_not_found`.
- Transcript GET happy path returns `ApplicationTranscriptRead` with both state-change and message entries for an officer with `application.message`. Risk annotation: `group=TG-2; named_risk=officer_transcript_visibility_regression`.
- Transcript GET without `application.message` returns `403 application_transcript_forbidden`; missing id returns `404 application_not_found`.
- Dependency-tree guard expected route set expands from list + claim to list + claim + detail + transcript, preserving the existing no `get_current_actor`, no `CURRENT_ACTOR.get`, no `verify_applicant_receipt`, no `applicant_receipt` source assertions (`services/api/tests/test_web_officer_applications.py:723-758`).

### Component tests

Add `services/web/tests/officer-detail.spec.ts`:

- Anonymous/redirect/fetch failure on `/api/me` shows auth-required and does not fetch detail/transcript. Risk annotation: `group=TG-3; named_risk=anonymous_detail_blocked; level=component`.
- Non-officer principal and officer missing Discord claim stop before detail fetch.
- Happy path renders application id, state, owner, version, target scope, submitted/updated timestamps, and response key-value rows.
- Transcript renders state-change and message entries in server order using the `type` discriminator.
- `403`, `404`, `422`, Zod parse failure, and network/5xx show stable read-only error panels.
- No button/form issues POST/PUT/PATCH/DELETE from the detail route. Risk annotation: `group=TG-5; named_risk=read_only_surface_regression`.

### E2E

Extend `infra/tests/e2e/tests/19-web-ui.sh` and `infra/tests/e2e/lib/playwright/browser-flow.mjs` after the existing queue claim leg (`infra/tests/e2e/lib/playwright/browser-flow.mjs:130-160`):

1. Navigate to `/applications/{claimed_application_id}`.
2. Assert detail metadata shows the claimed state, owner id prefix, version, and at least one response value from the submitted fixture.
3. Assert the transcript includes a state-change entry for the claim transition.
4. Write the detail assertion result into the existing session artifact or a sibling `web-ui-detail.json`.

Do not create a new e2e number; test 19 already owns the public submit -> officer queue flow (`infra/tests/e2e/tests/19-web-ui.sh:84-90`).

## 8. Anti-scope

- No message thread or `POST /messages`; INIT-133B-iii owns it.
- No review/approve/deny/waitlist/interview/reactivate/withdraw/reassign controls; INIT-133B-iii owns non-claim transitions.
- No claim button on the detail page; beta-i queue remains the claim surface.
- No transcript filtering, pagination, live updates, SSE, or WebSocket.
- No actor display-name/member lookup; show actor kind plus shortened actor id only.
- No field-definition renderer beyond plain key-value responses.
- No schema migration, new permissions, new actor kinds, `member_links`, applicant-receipt officer identity, browser actor headers, feature flags, compatibility shims, deprecated aliases, or placeholder stubs.
- No Discord-visible writes, DMs, channels, role changes, embeds, or moderation actions.

## 9. Diff Budget

Estimated net: `+430 / -20` lines.

Breakdown: API bridge + tests `+150`; SPA client/detail route/CSS `+190`; Playwright component tests `+110`; Pomerium/static/e2e fixture extensions `+70`; small queue navigation adjustment `+30 / -20`. If implementation exceeds `+600` net lines or touches application state machine, message append, database migrations, Authentik, or authority internals, the scope gate should fail and split the work.

## 10. Risk Gates (Self-Review)

### Audit

LOW. The proposal reuses beta-i officer actor construction, direct service reads, existing application read authority, and existing transcript visibility filtering. The only route-policy change is explicitly ordered and testable.

### Scope

LOW. The slice is read-only detail + transcript. It does not add actions, message append, new grants, new schema, new identity chain, or Discord-visible side effects.

### Shortcut

LOW. The SPA uses Zod schemas for the actual contracts, the bridge constructs actor identity server-side, and backend reads delegate to existing services rather than HTTP self-calls or duplicated repositories.

### Supported-surface

LOW. Public `/applications` remains public, `/applications/queue` remains on its beta-i protected route, `/api/web/officer/` remains the bridge API prefix, and the new `/applications/` prefix only protects detail-owned paths before the public catch-all.

## 11. Hookpoint Preview

Reuse:

- `services/api/app/api/v1/endpoints/web.py::_build_officer_actor` for officer identity (`services/api/app/api/v1/endpoints/web.py:67-116`).
- `raise_known_application_error` for detail read errors (`services/api/app/api/v1/endpoints/applications/_shared.py:64-182`).
- Direct lifecycle read shape: `read_application` plus `require_application_read_authority` (`services/api/app/api/v1/endpoints/applications/lifecycle.py:109-122`).
- Direct transcript service behavior and error codes (`services/api/app/api/v1/endpoints/applications/transcript.py:22-56`).
- Solid route shell in `services/web/src/app/router.tsx` and the beta-i `ApplicationQueueRoute` bootstrap pattern.
- `services/web/src/api/client.ts` `getJson` / `ApiError` pattern.
- Existing Playwright fixture/mocking style from `officer-queue.spec.ts` and compat risk annotations.

New:

- `ApplicationDetailRoute.tsx`.
- Transcript Zod schema using discriminator `type`.
- Two bridge endpoints: `GET /api/v1/web/officer/applications/{id}` and `GET /api/v1/web/officer/applications/{id}/transcript`.
- One Pomerium `prefix: /applications/` entry, ordered after queue routes and before the catch-all.
- One component spec file: `services/web/tests/officer-detail.spec.ts`.

Leave alone:

- Core `/api/v1/applications` direct endpoint behavior, actor-header behavior, transitions, and ETags.
- Application message append endpoints and services.
- Database schema, authority permission names, Authentik officer OAuth config, and member resolver internals.
- Public applicant route, applicant receipt machinery, and public submit behavior.
