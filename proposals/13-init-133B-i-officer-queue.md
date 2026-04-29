# Proposal 13 - INIT-133B-i / BL-019D-beta slice 1: officer queue

## 1. Goal

INIT-133B-i ships the first BL-019D-beta officer review surface: a Solid Router-backed `/applications/queue` page where an authenticated officer can see submitted/queued applications, page through the queue, and claim one application. This consumes the INIT-133A `ApplicationListRead` / `ApplicationRead` contracts and the existing application transition service; detail, transcript, messaging, and non-claim decisions remain in INIT-133B-ii / INIT-133B-iii.

## 2. Locked Decisions Q1..Q8

### Q1. SPA architecture: B, wire Solid Router as the real entry

Choose B: replace the live vanilla `main.tsx` bootstrap with `AppProviders + router`, migrate the current `/`, `/applications`, and `/admin/chapters` behavior into Solid routes, and add `/applications/queue` as a first-class route. `index.html` loads only `/src/main.tsx` today (`services/web/index.html:9-12`), while the live runtime is a pathname switch in `main.tsx` (`services/web/src/main.tsx:35-37`, `services/web/src/main.tsx:146-149`). The router/provider scaffold already exists but is not mounted (`services/web/src/app/router.tsx:48-76`, `services/web/src/app/providers.tsx:24-38`), so extending `main.tsx` or mounting the router beside it would preserve the dual-system state the project rules explicitly reject: AGENTS requires no compatibility shims or dual support (`AGENTS.md:564-575`) and says hookpoint research should prevent parallel systems (`AGENTS.md:76-78`). This choice is not justified by diff size; it is justified by removing the parallel runtime before 133B-ii and 133B-iii build on top of it.

### Q2. Officer identity surface: Pomerium gate plus Discord-member actor bridge

Call `/api/v1/me` once on route mount for the Pomerium principal, but do not call the core `/api/v1/applications` endpoint directly from the browser. The current web-admin endpoint pattern depends on Pomerium identity headers (`services/api/app/api/v1/endpoints/web.py:18-23`) and `/api/v1/me` returns a Pomerium principal (`services/api/app/api/v1/endpoints/me.py:18-40`). Application list and transition endpoints, however, require an `ActorIdentity` from `X-Actor-*` context (`services/api/app/core/actor.py:26-42`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:91-93`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:140-142`), and claim ownership converts the user actor id to a UUID (`services/api/app/services/applications.py:266-273`). Therefore this slice adds a web-officer API bridge under `/api/v1/web/officer/*`: it requires Pomerium officer identity, verifies the existing `applicant_receipt` Discord cookie with `verify_applicant_receipt` (`services/api/app/services/applicant_discord_auth.py:207-236`), resolves the Discord member UUID via `resolve_or_create_real_discord_member` (`services/api/app/services/members.py:192-268`), and then calls the existing application list/transition services with `ActorIdentity(actor_kind="user", actor_id=<member uuid>)`. This keeps the core API unchanged and avoids browser-supplied actor headers.

### Q3. Route path: `/applications/queue`

Use `/applications/queue` for the queue page and reserve `/applications/{id}` for INIT-133B-ii. The backlog split names 133B-i as queue only and 133B-ii as detail/transcript (`plans/SESSION_HANDOFF.md:72-75`), and BL-019D-beta is explicitly the SPA officer review surface that consumes 019B/019C/019D-alpha (`plans/BACKLOG.md:522-524`). `/applications` remains the applicant form. The implementation must add Pomerium protection for `/applications/queue` because the current local Pomerium config protects only `/admin` on the web host and leaves the catch-all route public (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-63`).

### Q4. Filter UX: state toggles only

Ship a compact state toggle row with default states `submitted,queued`. The backend list endpoint accepts `state`, `scope_kind`, `scope_id`, `owner_id`, `limit`, and `after_id` (`services/api/app/api/v1/endpoints/applications/lifecycle.py:83-105`), and the state enum is locked in the application contract (`services/api/app/contracts/applications.py:37-47`). Scope selector and owner filter are not in this slice because 133B-i is proving the queue and claim workflow; API-side authority remains authoritative through the existing list service (`services/api/app/services/applications.py:420-446`).

### Q5. Pagination UX: explicit Load More

Use a "Load more" button when `next_after_id` is present. `ApplicationListRead` returns `items` plus `next_after_id` (`services/api/app/contracts/applications.py:375-377`), and the repository orders by `submitted_at DESC, id ASC` with limit-plus-one paging (`services/api/app/repositories/applications.py:133-189`). No infinite scroll, prefetch, counts, or total pages are included.

### Q6. Claim button semantics: real transition, no optimistic-only action

Render a claim button only for rows in `submitted` or `queued`. The POST body must match the real contract, `{ "action": "claim" }`, not the problem-map placeholder `transition_type`; `ApplicationTransitionRequest` uses the `action` field (`services/api/app/contracts/applications.py:249-260`), and the endpoint is `POST /api/v1/applications/{application_id}/transitions` (`services/api/app/api/v1/endpoints/applications/lifecycle.py:134-155`). The web-officer bridge sends `If-Match: "<row.version>"`, because the endpoint requires a strong ETag (`services/api/app/api/v1/endpoints/applications/_shared.py:33-56`). On success, update the row from the returned `ApplicationRead` and refetch the queue once. On `409` or `412`, show a conflict message and refetch. On `403`, show forbidden state and disable claim controls.

### Q7. Test surface: new officer spec plus test 19 augmentation

Add `services/web/tests/officer-queue.spec.ts` rather than making `compat.spec.ts` carry both applicant compatibility and officer workflow coverage. `compat.spec.ts` already uses the shared contract fixture, Playwright route mocking, applicant receipt cookies, and inline risk annotations (`services/web/tests/compat.spec.ts:36-48`, `services/web/tests/compat.spec.ts:88-158`, `services/web/tests/compat.spec.ts:202-220`). Keep those patterns. Extend `infra/tests/e2e/tests/19-web-ui.sh` instead of adding a new e2e number because test 19 already validates the web image, Pomerium/admin route, applicant receipt submit, and persistence (`infra/tests/e2e/tests/19-web-ui.sh:50-53`).

### Q8. Anti-scope: queue and claim only

Out of scope: application detail page and transcript view (133B-ii), message thread and non-claim decision actions (133B-iii), applicant DM materialization (BL-020), Discord-visible channel/DM side effects (BL-009), bulk actions, search, sorting beyond existing backend order, officer scope selector, owner/mine filter, export, Storybook, and mobile polish beyond responsive non-overlap.

## 3. Scope

### New files

- `services/web/src/features/public/ApplicationFormRoute.tsx` - Solid route that mirrors the current receipt-gated applicant form behavior from `main.tsx`.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx` - officer queue route with state toggles, table/list rows, load-more, claim action, and status messages.
- `services/web/src/features/officer/officer.module.css` - route-local queue layout and row styling.
- `services/web/tests/officer-queue.spec.ts` - Playwright component tests for officer queue auth, list, filters, pagination, and claim.
- `services/api/tests/test_web_officer_applications.py` - API tests for the Pomerium + Discord receipt bridge, list, claim, and failure cases.

### Modified files

- `services/web/src/main.tsx` - replace vanilla DOM routing with Solid `render(() => <AppProviders router={router} />, root)` while preserving the same mounted `#root`.
- `services/web/src/app/router.tsx` - add `/applications` and `/applications/queue`; keep `/` and `/admin/chapters`; add queue nav only when the route has officer state.
- `services/web/src/app/providers.tsx` - remove the `any` router prop type and keep query/router providers as the only runtime wrapper.
- `services/web/src/api/client.ts` - add Zod schemas for `ApplicationScope`, `ApplicationRead`, `ApplicationListRead`, transition request/response, `CurrentPrincipal.groups`, applicant Discord identity, and web-officer client functions; switch browser-facing API URLs to `/api/...` so nginx maps them to API `/api/v1/...`.
- `services/web/src/features/public/HomeRoute.tsx` - replace demo preview behavior with a Solid mirror of the current public home route and link to `/applications`.
- `services/web/src/features/admin/AdminChaptersRoute.tsx` - preserve the current chapter table behavior while using the corrected browser-facing `/api/web/admin/chapters` client path.
- `services/api/app/contracts/web.py` - add `groups: list[str] = []` to `CurrentPrincipalRead` and add web-officer response/error helper types only if needed by endpoint tests.
- `services/api/app/api/v1/endpoints/me.py` - parse `x-pomerium-claim-groups` into `CurrentPrincipalRead.groups`.
- `services/api/app/api/v1/endpoints/web.py` - add `/officer/applications` list and `/officer/applications/{application_id}/claim` endpoints using Pomerium + applicant receipt identity.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` - protect `/applications/queue` and `/api/web/officer/` with Pomerium identity headers before the public catch-all route.
- `infra/tests/test_applicant_discord_pomerium.py` - assert the new protected officer route prefixes precede the public catch-all.
- `infra/tests/validate_web_ui_local.sh` - extend static checks for the officer queue fixture/spec and keep the existing web build/runtime proof.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` - after existing applicant submit, navigate to `/applications/queue`, wait for the queue, and record a claimed application id.
- `infra/tests/e2e/tests/19-web-ui.sh` - seed/read the officer queue assertion and verify the claimed application owner/state in Postgres.

### Deleted files

- `services/web/src/RuntimeApp.tsx` - delete the unmounted parallel runtime.
- `services/web/src/features/forms/DarkNemesisForm.tsx` - delete or replace with the real `ApplicationFormRoute`; do not keep a demo form parallel to the supported applicant form.
- `services/web/src/features/forms/schema.ts` - delete if no longer imported by the real applicant route.
- `services/web/src/features/forms/form.module.css` - delete if no longer imported.

### Tests

- `services/web/tests/compat.spec.ts` - update only as needed to keep the applicant route, receipt gating, UI-library smoke, and contract fixture behavior passing under Solid Router.
- `services/web/tests/officer-queue.spec.ts` - new officer route test file described above.
- `services/api/tests/test_web_officer_applications.py` - new API bridge tests.
- `infra/tests/test_applicant_discord_pomerium.py` - route-order/static Pomerium tests.
- `infra/tests/validate_web_ui_local.sh` - static coverage assertions.
- `infra/tests/e2e/tests/19-web-ui.sh` and `infra/tests/e2e/lib/playwright/browser-flow.mjs` - live local e2e queue proof.

### Fixtures

- `infra/tests/fixtures/web-ui/contract.json` - add `routes.officer_queue`, `auth.officer`, `applications.queue`, and `applications.claim` fixture data while preserving the existing applicant form fixture consumed by `compat.spec.ts` and test 19 (`infra/tests/fixtures/web-ui/contract.json:44-87`).

This is larger than a pure frontend slice because the existing backend/browser auth surfaces do not currently provide a safe officer member UUID for claim. Splitting the auth bridge into its own INIT is possible, but not recommended: the queue page plus claim button cannot be honestly tested without it.

## 4. API Surface Consumed

### GET `/api/v1/me`

Browser path: `/api/me` through the web nginx proxy. Request shape: no body; Pomerium supplies claim headers. Response shape: `{ subject: string, email: string | null, display_name: string | null, provider: "pomerium", groups: string[] }`. Auth: Pomerium identity required; the existing dependency returns `401 identity_missing` when headers are absent (`services/api/app/api/v1/endpoints/me.py:24-31`). UI handling: anonymous users should be redirected by Pomerium before the route renders; if the SPA sees `401`, show an auth-required panel and no queue controls. If groups do not include `officers`, show forbidden/non-officer state.

### GET `/auth/discord/me`

Request shape: no body; `applicant_receipt` cookie. Response shape: `{ discord_user_id: string }` (`services/api/app/api/v1/endpoints/auth_discord.py:88-105`). Auth: applicant Discord receipt cookie required. UI handling: if missing/expired, show a "Login with Discord" action that starts `/auth/discord/start?return_to=/applications/queue`; do not call queue endpoints until the receipt exists. This is the actor-member bridge, not the officer authorization gate.

### GET `/api/v1/web/officer/applications`

Browser path: `/api/web/officer/applications`. Query: `state?: string` comma list, `limit?: number`, `after_id?: uuid`; no `scope_kind`, `scope_id`, or `owner_id` UI in this slice. Response shape: exactly `ApplicationListRead`:

```json
{
  "items": [ApplicationRead],
  "next_after_id": "uuid or null"
}
```

`ApplicationRead` fields must match `services/api/app/contracts/applications.py:352-372`: ids, form metadata, `target_scope`, `responses`, `state`, `owner_id`, timestamps, and `version`. Auth: Pomerium principal must include officer group; applicant Discord receipt must resolve to a real Discord member; existing application authority must allow list. Failure modes handled: `401 identity_missing` or `applicant_receipt_required` shows auth/Discord login state; `403 officer_required` or `application_list_forbidden` shows forbidden state; `422 validation_error` shows filter error and resets to default states; network/5xx shows retry panel.

### POST `/api/v1/web/officer/applications/{application_id}/claim`

Browser path: `/api/web/officer/applications/{id}/claim`. Request shape:

```json
{
  "expected_version": 3
}
```

The bridge converts this to the core transition request `{ "action": "claim" }` with `If-Match: "\"3\""`. Response shape: `ApplicationRead`. Auth: same Pomerium officer + Discord member receipt + existing `application.claim` authority. Failure modes handled: `401` shows auth/Discord login state; `403` disables claim; `404` removes/refetches row; `409 application_already_claimed` or `409 invalid_application_transition` shows conflict and refetches; `412 stale_application_version` shows conflict and refetches; `422` shows validation error.

## 5. Component Contract Preview

### Route components

```ts
export type ApplicationQueueRouteProps = {
  readonly initialStates?: readonly ApplicationState[];
};

export function ApplicationQueueRoute(props: ApplicationQueueRouteProps): JSX.Element;

export function ApplicationFormRoute(): JSX.Element;
export function HomeRoute(): JSX.Element;
export function AdminChaptersRoute(): JSX.Element;
```

Router-owned route components should fetch through client functions directly; tests may render through the full router and mock network routes.

### Sub-components

```ts
export type QueueFilterBarProps = {
  readonly selectedStates: readonly ApplicationState[];
  readonly onChange: (states: readonly ApplicationState[]) => void;
  readonly disabled?: boolean;
};

export type ApplicationQueueListProps = {
  readonly applications: readonly ApplicationRead[];
  readonly currentOfficerMemberId?: string;
  readonly claimingId?: string;
  readonly onClaim: (application: ApplicationRead) => void;
};

export type ApplicationQueueRowProps = {
  readonly application: ApplicationRead;
  readonly canClaim: boolean;
  readonly isClaiming: boolean;
  readonly onClaim: () => void;
};
```

### API client functions

```ts
export const applicationStateSchema: z.ZodEnum<[...states]>;
export const applicationReadSchema: z.ZodType<ApplicationRead>;
export const applicationListReadSchema: z.ZodType<ApplicationListRead>;

export type CurrentPrincipal = z.infer<typeof principalSchema>;
export type ApplicantDiscordMe = z.infer<typeof applicantDiscordMeSchema>;
export type ApplicationRead = z.infer<typeof applicationReadSchema>;
export type ApplicationListRead = z.infer<typeof applicationListReadSchema>;

export function fetchCurrentPrincipal(): Promise<CurrentPrincipal>;
export function fetchApplicantDiscordIdentity(): Promise<ApplicantDiscordMe>;
export function fetchOfficerApplicationQueue(input: {
  readonly states: readonly ApplicationState[];
  readonly limit?: number;
  readonly afterId?: string;
}): Promise<ApplicationListRead>;
export function claimOfficerApplication(input: {
  readonly applicationId: string;
  readonly expectedVersion: number;
}): Promise<ApplicationRead>;
```

All client functions validate with Zod; no `any`. The current `AppProviders` `router: any` must be replaced (`services/web/src/app/providers.tsx:24-29`).

### Signals / stores

No global TanStack Store state is introduced. Route-local Solid signals:

- `selectedStates: Accessor<ApplicationState[]>`, default `["submitted", "queued"]`.
- `items: Accessor<ApplicationRead[]>`.
- `nextAfterId: Accessor<string | null>`.
- `claimingId: Accessor<string | null>`.
- `notice: Accessor<{ kind: "info" | "error" | "success"; message: string } | null>`.

TanStack Query may cache the principal and queue responses through `createQuery`; the durable UI store remains theme/navigation only (`services/web/src/app/store.ts:11-27`).

## 6. Authorization Model

Anonymous: Pomerium protects `/applications/queue`; unauthenticated browser navigation should redirect before the SPA route loads. If the SPA still receives `401 identity_missing` from `/api/me`, it shows an auth-required panel and no queue data. The current local Pomerium route must be extended because only `/admin` is protected today (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:48-53`).

Non-officer: `/api/me` succeeds but `groups` lacks `officers`; the route shows a forbidden panel. The web-officer API repeats this check server-side before resolving the Discord member. The UI cannot unlock itself by changing local state.

Officer without Discord receipt: `/api/me` succeeds and groups include `officers`, but `/auth/discord/me` or the web-officer API returns `applicant_receipt_required`. The page shows a Discord login action pointing to `/auth/discord/start?return_to=/applications/queue`. This is required because claim ownership must be a real member UUID, and the application service rejects non-UUID user actor ids for review actions (`services/api/app/services/applications.py:266-273`).

Officer with Discord receipt and authority: the web-officer API resolves the member UUID, calls existing list/transition services, and lets those services enforce `application.claim` / review authority (`services/api/app/services/applications.py:348-362`, `services/api/app/services/applications.py:393-446`). The client treats API `403` as authoritative even if `/api/me` says the user is in the officer group.

## 7. Test Plan

### Unit/component tests (Playwright)

- `officer queue redirects anonymous Pomerium user`: route `/applications/queue`, mock `/api/me` as 401, assert auth panel and no queue table. Risk annotation: `group=TG-133B-i; named_risk=anonymous_queue_access; level=component`.
- `officer queue blocks non-officer principal`: mock `/api/me` with no `officers` group, assert forbidden panel and no queue fetch. Risk annotation: `named_risk=non_officer_queue_access`.
- `officer queue asks officer for Discord receipt before data`: mock `/api/me` officer, `/auth/discord/me` 401, assert Discord login link uses `return_to=/applications/queue` and no list call. Risk annotation: `named_risk=claim_actor_member_missing`.
- `officer queue renders submitted and queued rows`: mock principal, Discord identity, and list response from `contract.json`; assert headings, state toggles, row fields, and claim buttons for `submitted|queued`.
- `officer queue filters by state`: click state toggles and assert query string sent to `/api/web/officer/applications?state=...`.
- `officer queue load more appends rows`: first response has `next_after_id`, second request includes `after_id`, UI appends without replacing earlier rows.
- `officer queue claim posts expected version`: click claim, assert request body `{ expected_version: row.version }`, assert returned row updates state/owner and a refetch occurs.
- `officer queue claim conflict refetches`: claim returns `409 application_already_claimed` or `412 stale_application_version`, assert conflict notice and refetch.
- Existing `compat.spec.ts` tests continue to cover public route, applicant receipt gate, submit payload, and UI library smoke. Its fixture-loading pattern must remain (`services/web/tests/compat.spec.ts:36-48`), and its applicant route tests must still pass (`services/web/tests/compat.spec.ts:202-291`).

### API tests

- `web officer list requires Pomerium identity`: no Pomerium headers -> 401.
- `web officer list requires officers group`: Pomerium principal without `officers` -> 403.
- `web officer list requires applicant receipt`: officer headers but no receipt -> 401 `applicant_receipt_required`.
- `web officer list returns ApplicationListRead`: officer + receipt + authority -> 200 matching `ApplicationListRead`.
- `web officer claim maps receipt to member actor`: claim succeeds, returned `ApplicationRead.owner_id` equals the resolved member UUID.
- `web officer claim stale version returns conflict/precondition failure`: stale `expected_version` maps to structured error without swallowing service errors.

### E2E

Extend `19-web-ui.sh` and `browser-flow.mjs`. After the existing public applicant submit persists a queued application with a real Discord member (`infra/tests/e2e/tests/19-web-ui.sh:8-37`), navigate as the authenticated Pomerium user to `/applications/queue`, inject or reuse a valid applicant receipt as test 19 already does (`infra/tests/e2e/lib/playwright/browser-flow.mjs:47-68`), assert the queued application appears, click claim, record the application id, and verify in Postgres that `state='claimed'` and `owner_id` is a non-synthetic Discord member. Keep the suite count at 19.

## 8. Anti-scope

- No application detail page; INIT-133B-ii owns `/applications/{id}` and full `GET /api/v1/applications/{id}` rendering.
- No transcript view; INIT-133B-ii owns `GET /api/v1/applications/{id}/transcript`.
- No message thread; INIT-133B-iii owns `GET/POST /api/v1/applications/{id}/messages`.
- No decisions beyond claim; INIT-133B-iii owns review, approve, deny, waitlist, request interview, reassign, reactivate, and withdraw controls.
- No Discord-visible writes, channel creation, DMs, or officer review embed; BL-009 and BL-020 own those.
- No scope selector, "mine" filter, search, export, or bulk actions.
- No schema migration and no new authority permission names.
- No browser-supplied `X-Actor-Kind` / `X-Actor-Id`; the web-officer API bridge constructs actor identity server-side.
- No feature flag, legacy vanilla route fallback, or retained `RuntimeApp` parallel entry.

## 9. Diff Budget

Estimated net: `+950 / -260` lines.

Breakdown: web Solid migration and queue `+520 / -220`; web tests `+220`; API web-officer bridge and API tests `+260`; fixture/e2e/Pomerium route assertions `+210 / -40`. If implementation exceeds `+1,250` net lines or touches unrelated backend services, the scope gate should fail and split the auth bridge from the queue route.

## 10. Risk Gates (Self-Review)

### Audit

Risk is the highest around replacing the SPA entry path because the live applicant flow is currently in `main.tsx` and handles receipt probing, draft preservation, submit, and redirect (`services/web/src/main.tsx:176-216`, `services/web/src/main.tsx:238-311`). The proposal preserves that behavior by making `/applications` a Solid route with the same `/auth/discord/me` probe, same `/api/public/applications` browser path, same no `X-Discord-User-Id` behavior already asserted in tests (`services/web/tests/compat.spec.ts:114-125`), and the same `#submit-status` e2e selector used by browser-flow (`infra/tests/e2e/lib/playwright/browser-flow.mjs:129`). Queue claim uses optimistic locking via `expected_version` and maps to the existing `If-Match` transition contract, so stale claims do not corrupt state. Conclusion: LOW.

### Scope

The slice includes a web-officer API bridge and Pomerium route updates because the existing core application endpoint requires an actor UUID, while Pomerium only supplies identity headers and the local web host currently leaves `/applications/*` public. Those are directly necessary for a real queue + claim surface. It does not add detail, transcript, messages, non-claim transitions, schema, new permissions, or Discord side effects. Conclusion: LOW.

### Shortcut

No `TODO`, no `any`, no feature flag, no old vanilla fallback, no browser actor headers, and no "UI-only" test skip. `AppProviders` must remove the existing `router: any` (`services/web/src/app/providers.tsx:24`). Zod schemas must mirror Pydantic contracts instead of parsing untyped JSON. Tests are separated for component, API, and e2e behavior. Conclusion: LOW.

### Supported-surface

Pomerium auth flow: add explicit protected routes for `/applications/queue` and `/api/web/officer/` before the public catch-all; keep `/auth/discord/` public and API-targeted as currently asserted (`infra/tests/test_applicant_discord_pomerium.py:58-67`). Applicant Discord OAuth flow: keep `/auth/discord/start`, `/auth/discord/callback`, `/auth/discord/me`, and the `applicant_receipt` cookie unchanged (`services/api/app/api/v1/endpoints/auth_discord.py:16-32`, `services/api/app/api/v1/endpoints/auth_discord.py:75-105`). Build pipeline: no changes to `Containerfile.web`; it still runs `npm run build` and copies `dist` into nginx (`containers/server-manager/Containerfile.web:10-24`). K3d image rollout: `validate_web_ui_local.sh` and test 19 still use `build-channel-image.sh` and the `server-manager-web` deployment (`infra/tests/validate_web_ui_local.sh:138-145`, `infra/tests/validate_web_ui_local.sh:159-172`). Existing e2e test 19 must still pass on humility-local and gains only an additional queue/claim assertion after the current applicant submit proof. Conclusion: LOW.

## 11. Hookpoint Preview

Reuse:

- `services/web/src/app/router.tsx`, `providers.tsx`, and `store.ts` as the real Solid runtime.
- Existing primitives/components where they serve real UI (`Button`, `Icon`, table/layout CSS patterns).
- Existing applicant receipt verifier and Discord member resolver for actor bridging.
- Existing application list and transition services/contracts; do not duplicate list/claim logic.
- Existing Playwright fixture/mocking style and test 19 browser flow.

Delete:

- `services/web/src/RuntimeApp.tsx`, because it is a second unmounted runtime.
- Demo-only form scaffolding if it is not transformed into the real applicant route.
- Vanilla DOM rendering in `main.tsx`; keep only Solid bootstrap.

Leave alone:

- Core `/api/v1/applications` endpoint semantics, including actor headers and `If-Match`.
- Public submit API and applicant Discord OAuth endpoints.
- Build image, nginx container, and deployment image tag mechanics.

Under this architecture, `features/{public,admin}/*Route.tsx` stop being parallel scaffolding: `HomeRoute` and `AdminChaptersRoute` become the actual routes mounted by `main.tsx`, while the applicant form and officer queue are added beside them as real Solid routes.
