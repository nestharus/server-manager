# Proposal 15 - INIT-133B-iii / BL-019D-beta slice 3: messages + transitions

## 1. Goal

INIT-133B-iii ships BL-019D-beta's final officer review slice: the existing `/applications/{id}` officer detail route gains an application message composer and non-claim transition controls so officers can append applicant-visible or officer-only messages, move a claimed application into review, request interview, waitlist, approve, deny, reactivate, or withdraw it, and see each result reflected in the transcript. This builds on INIT-133B-i's Pomerium-bound officer bridge and claim flow plus INIT-133B-ii's read-only detail/transcript route, and closes BL-019D-beta as the web officer review substrate needed before BL-009 Discord-visible side effects and BL-020 DM materialization (`plans/BACKLOG.md:613-647`).

## 2. Locked Decisions Q1..Q8

### Q1. Transition bridge shape: single `POST /transitions`

Lock one bridge endpoint: `POST /api/v1/web/officer/applications/{application_id}/transitions`. The browser path is `/api/web/officer/applications/{id}/transitions`, and the body mirrors `ApplicationTransitionRequest` (`services/api/app/contracts/applications.py:249-260`). This matches the direct lifecycle endpoint's single transition route and `If-Match` flow (`services/api/app/api/v1/endpoints/applications/lifecycle.py:125-146`) instead of creating per-action bridge endpoints.

### Q2. Transition action set: service-supported non-claim review actions

Expose `review`, `request_interview`, `waitlist`, `approve`, `deny`, `reactivate`, and `withdraw`. Do not expose `claim`, because INIT-133B-i owns the queue claim endpoint and UI (`services/api/app/api/v1/endpoints/web.py:195-255`, `services/web/src/features/officer/ApplicationQueueRoute.tsx:96-115`). Do not expose `reassign`, because it needs an owner picker and is explicitly out of scope in the problem map (`research/24-init-133B-iii-problem-map.md:93-94`).

Do not expose `route` in this slice. The problem map marks route as only relevant if officers author queue-routing decisions (`research/24-init-133B-iii-problem-map.md:15-17`), and the current service rejects `route` before state-machine execution (`services/api/app/services/applications.py:1068-1074`). Public submit is already queued in the e2e persistence assertion (`infra/tests/e2e/tests/19-web-ui.sh:23-33`), so adding a route button now would be a deferred stub.

### Q3. Action visibility: local helper mirrors `VALID_TRANSITIONS`

Render transition controls only when `application.state` allows the action in `VALID_TRANSITIONS` (`services/api/app/services/applications.py:65-89`). The helper excludes `claim`, `route`, and `reassign`; for the exposed actions it maps: `claimed -> review, withdraw`; `in_review -> request_interview, waitlist, approve, deny, withdraw`; `interview -> waitlist, approve, deny, withdraw`; `waitlisted -> reactivate, withdraw`; terminal states show no controls.

### Q4. Message composer: textarea, visibility, idempotency

Ship a plain message composer in the detail route: required textarea, visibility segmented control for `applicant_visible` / `officer_only`, and Send button. The bridge request body contains only `body_markdown`, `visibility`, and `client_message_id`; the bridge fills author fields from `_build_officer_actor` because the direct append request requires author fields (`services/api/app/contracts/application_messages.py:19-24`) and browser-supplied author identity is not trusted. After success, clear the textarea, generate a fresh UUIDv4 `client_message_id`, and refetch transcript so the returned `ApplicationMessageRead` is visible inline. If the same compose is retried with the same `client_message_id`, preserve direct endpoint idempotency: created returns 201 and duplicate returns 200 (`services/api/app/api/v1/endpoints/applications/messages.py:49-76`, `services/api/app/services/application_messages.py:93-100`).

### Q5. Optimistic locking: browser `If-Match` like claim

Transitions require `If-Match: "<version>"` derived from the current `ApplicationRead.version`. The bridge calls `parse_if_match_strong(request)` and forwards `expected_version` into `transition_application`, then sets the returned ETag with `set_etag(response, result.etag)`, matching the direct endpoint (`services/api/app/api/v1/endpoints/applications/lifecycle.py:134-146`) and the existing claim client pattern (`services/web/src/api/client.ts:280-303`). On success, replace the route's application with the response, then refetch detail and transcript. On `412 stale_application_version` or `428 if_match_required`, show a stale/precondition notice and refetch. On `409` transition conflicts, show the specific notice and refetch.

### Q6. Authorization: bridge builds actor, services decide permissions

Reuse `_build_officer_actor` for Pomerium identity, officer group membership, Pomerium `discord_user_id`, real Discord member resolution, and `ActorIdentity(user, member_uuid)` construction (`services/api/app/api/v1/endpoints/web.py:75-129`). Message append delegates to `append_application_message`, which requires `application.message` for non-applicant authors (`services/api/app/services/application_messages.py:52-82`, `services/api/app/services/application_messages.py:121-125`). Transitions delegate to `transition_application`, which calls `require_transition_authority` unless skipped (`services/api/app/services/applications.py:1075-1084`).

The permission mapping follows the actual helper, not the problem-map guess: `require_transition_authority` maps every action except `reassign` to `application.{action}` (`services/api/app/services/applications.py:348-362`). Therefore `request_interview` requires `application.request_interview`, and `withdraw` requires `application.withdraw`.

### Q7. Pomerium and browser routing: no new protected prefixes

No new Pomerium routes. INIT-133B-i already protects `/api/web/officer/` and INIT-133B-ii already protects `/applications/` detail paths (`plans/BACKLOG.md:564-570`, `plans/BACKLOG.md:624-625`). The SPA keeps using browser `/api/...` paths through the web nginx rewrite, as the current client already does for queue, detail, transcript, and claim (`services/web/src/api/client.ts:251-303`).

### Q8. Anti-scope: no Discord-visible or owner-picker work

Out of scope: route, reassign, owner picker, bulk actions, search/sort/filter expansion, message editing/deletion/threading, attachments, real-time updates, Discord DMs/channels/embeds/role changes, applicant DM materialization, schema migrations, new permissions, new actor kinds, compatibility shims, feature flags, deprecated aliases, or placeholder stubs. BL-009 owns Discord-visible rollout and BL-020 owns DM materialization (`plans/BACKLOG.md:646-647`).

## 3. Scope

### New files

- `services/web/src/features/officer/applicationStateMachine.ts` - route-local helper that maps `ApplicationState` to exposed transition actions and required input metadata, derived from `VALID_TRANSITIONS`.
- `services/web/src/features/officer/ApplicationMessageComposer.tsx` - message composer with visibility control, submit state, idempotency token ownership, and validation.
- `services/web/src/features/officer/ApplicationTransitionActions.tsx` - action button group plus inline fields for notes/reasons/decision reason/thread id where required by `ApplicationTransitionRequest`.
- `services/web/tests/officer-actions.spec.ts` - Playwright component tests for message append and transition controls. This may be folded into `officer-detail.spec.ts` if the implementation stays small, but the proposal budgets a separate spec to keep read-only beta-ii coverage clear.

### Modified files

- `services/api/app/contracts/web.py` - add `OfficerApplicationMessageAppendRequest` with `body_markdown`, `visibility`, and `client_message_id`; do not expose author fields to the browser (`services/api/app/contracts/web.py:9-19`).
- `services/api/app/api/v1/endpoints/web.py` - add `POST /officer/applications/{application_id}/messages` and `POST /officer/applications/{application_id}/transitions`; reuse `_build_officer_actor`, `parse_if_match_strong`, `raise_known_application_error`, `set_etag`, `append_application_message`, and `transition_application` (`services/api/app/api/v1/endpoints/web.py:8-12`, `services/api/app/api/v1/endpoints/web.py:75-129`, `services/api/app/api/v1/endpoints/web.py:195-255`).
- `services/web/src/api/client.ts` - add Zod schemas for message append/read and full transition requests, widen `applicationTransitionRequestSchema` beyond claim, and add `appendOfficerApplicationMessage` / `transitionOfficerApplication` using the existing `ApiError` and fetch patterns (`services/web/src/api/client.ts:80-84`, `services/web/src/api/client.ts:126-180`, `services/web/src/api/client.ts:280-303`).
- `services/web/src/features/officer/ApplicationDetailRoute.tsx` - mount composer and transition action group below metadata/transcript, own refetch-after-mutation, conflict notices, and stale-version recovery (`services/web/src/features/officer/ApplicationDetailRoute.tsx:184-315`).
- `services/web/src/features/officer/officer.module.css` - add compact detail action styles; no global style system change.
- `services/api/tests/test_web_officer_applications.py` - extend bridge tests from list/claim/detail/transcript to messages/transitions using existing Pomerium header, grant, and dependency guard patterns (`services/api/tests/test_web_officer_applications.py:26-88`, `services/api/tests/test_web_officer_applications.py:170-181`).
- `infra/tests/fixtures/web-ui/contract.json` - add message and transition endpoint fixture paths, action names, and expected success statuses.
- `infra/tests/validate_web_ui_local.sh` - extend static assertions for new browser API paths and absence of `/api/v1/` literals in SPA source.
- `infra/tests/e2e/lib/playwright/browser-flow.mjs` - after the current claim/detail proof, run `review` then `approve` through the detail route and record returned states (`infra/tests/e2e/lib/playwright/browser-flow.mjs:130-184`).
- `infra/tests/e2e/tests/19-web-ui.sh` - seed the required transition grants, assert claim -> review -> approve states in Postgres, and keep the existing message-authority grant path (`infra/tests/e2e/tests/19-web-ui.sh:95-140`, `infra/tests/e2e/tests/19-web-ui.sh:173-181`).

### Tests

- `services/api/tests/test_web_officer_applications.py` - API bridge coverage for message append, idempotency, transition `If-Match`, authority, service error mapping, and actor-spoofing guards.
- `services/web/tests/officer-actions.spec.ts` or extended `services/web/tests/officer-detail.spec.ts` - component coverage for valid action visibility, required fields, stale/conflict handling, successful transcript refresh, and message composer behavior.
- `infra/tests/e2e/tests/19-web-ui.sh` plus `infra/tests/e2e/lib/playwright/browser-flow.mjs` - live path `submit -> claim -> review -> approve`, with Postgres assertions after each mutation.

### Bridge endpoint shapes

```http
POST /api/v1/web/officer/applications/{application_id}/messages
Content-Type: application/json

{
  "body_markdown": "string",
  "visibility": "applicant_visible" | "officer_only",
  "client_message_id": "string | null"
}

201 Created | 200 OK
ApplicationMessageRead
```

```http
POST /api/v1/web/officer/applications/{application_id}/transitions
If-Match: "<version>"
Content-Type: application/json

ApplicationTransitionRequest

200 OK
ApplicationRead
etag: "<new-version>"
```

The transition bridge accepts only the beta-iii action set: `review`, `request_interview`, `waitlist`, `approve`, `deny`, `reactivate`, and `withdraw`. `claim` stays on `/claim`; `route` and `reassign` return `422 validation_error` from bridge validation rather than rendering unusable controls.

## 4. API Surface Consumed

### Browser SPA calls

- `GET /api/me` - unchanged principal probe. UI handles non-2xx/redirect/opaque/network as auth-required, missing `officers` as forbidden, and missing `discord_user_id` as identity incomplete (`services/web/src/api/client.ts:218-220`, `services/web/src/features/officer/ApplicationDetailRoute.tsx:218-240`).
- `GET /api/web/officer/applications/{application_id}` - existing detail bridge returning `ApplicationRead`. UI handles `401 identity_missing`, `401 officer_discord_identity_missing`, `401 officer_discord_identity_invalid`, `403 officer_required`, `403 authority_decision_denied`, `404 application_not_found`, `422 validation_error`, Zod parse failure, network failure, and 5xx (`services/api/app/api/v1/endpoints/web.py:179-193`, `services/web/src/features/officer/ApplicationDetailRoute.tsx:46-54`).
- `GET /api/web/officer/applications/{application_id}/transcript` - existing transcript bridge returning `ApplicationTranscriptRead`. UI handles the same identity failures, `403 application_transcript_forbidden`, `404 application_not_found`, Zod parse failure, network failure, and 5xx (`services/api/app/api/v1/endpoints/web.py:258-284`).
- `POST /api/web/officer/applications/{application_id}/messages` - new message bridge. UI handles `200/201` success, `401`, `403 officer_required`, `403 application_message_forbidden`, `404 application_not_found`, `422 applicant_visibility_required` / `validation_error`, Zod parse failure, network failure, and 5xx.
- `POST /api/web/officer/applications/{application_id}/transitions` - new transition bridge. UI handles `200` success with ETag, `401`, `403 officer_required`, `403 authority_decision_denied`, `404 application_not_found`, `409 invalid_application_transition`, `409 application_not_owner`, `409 application_decision_reason_required`, `409 application_review_notes_required`, `409 application_waitlist_reason_required`, `409 application_reactivate_owner_required`, `412 stale_application_version`, `428 if_match_required`, `422 validation_error`, Zod parse failure, network failure, and 5xx (`services/api/app/api/v1/endpoints/applications/_shared.py:79-201`).

### Bridge service calls and direct endpoints wrapped

- Message bridge wraps the direct API shape at `POST /api/v1/applications/{application_id}/messages` (`services/api/app/api/v1/endpoints/applications/messages.py:49-76`) by constructing an `ApplicationMessageAppendRequest` with server-side author fields and calling `append_application_message` (`services/api/app/services/application_messages.py:85-158`).
- Transition bridge wraps the direct API shape at `POST /api/v1/applications/{application_id}/transitions` (`services/api/app/api/v1/endpoints/applications/lifecycle.py:125-146`) by parsing `If-Match`, calling `transition_application`, forwarding known application errors through `raise_known_application_error`, and setting the returned ETag.
- The SPA does not call `/api/v1/...` directly. Browser paths remain `/api/...` through the web nginx rewrite, following the existing client paths (`services/web/src/api/client.ts:263-303`).

## 5. Component Contract Preview

### Message composer component

```ts
export type ApplicationMessageComposerProps = {
  readonly applicationId: string;
  readonly disabled?: boolean;
  readonly onMessageAppended: (message: ApplicationMessageRead) => Promise<void> | void;
  readonly onError: (notice: OfficerActionNotice) => void;
};

export function ApplicationMessageComposer(props: ApplicationMessageComposerProps): JSX.Element;
```

The component owns `bodyMarkdown`, `visibility`, `clientMessageId`, and `submitting` signals. Empty or whitespace-only body disables Send. Successful append clears body, keeps the selected visibility, rotates the idempotency UUID, and asks the route to refetch transcript.

### Transition action button group component

```ts
export type ApplicationTransitionActionsProps = {
  readonly application: ApplicationRead;
  readonly disabled?: boolean;
  readonly onTransitioned: (application: ApplicationRead) => Promise<void> | void;
  readonly onError: (notice: OfficerActionNotice) => void;
};

export function ApplicationTransitionActions(props: ApplicationTransitionActionsProps): JSX.Element;
```

The group renders one compact control per valid action. Required fields follow service validation: `review` requires `notes`; `waitlist` requires `reason`; `approve` and `deny` require `decision_reason`; `request_interview` may send `thread_id` and `reason`; `reactivate` may send `reason`; `withdraw` may send `notes` (`services/api/app/services/applications.py:585-620`). Submission sends `expectedVersion: application.version`.

### State machine helper

```ts
export const OFFICER_TRANSITION_ACTIONS = [
  "review",
  "request_interview",
  "waitlist",
  "approve",
  "deny",
  "reactivate",
  "withdraw",
] as const;

export type OfficerTransitionAction = (typeof OFFICER_TRANSITION_ACTIONS)[number];

export function validOfficerTransitionActions(state: ApplicationState): readonly OfficerTransitionAction[];
export function transitionActionInput(action: OfficerTransitionAction): TransitionInputContract;
```

The helper is intentionally small and table-driven. It mirrors only the beta-iii exposed subset of `VALID_TRANSITIONS`; direct API and service validation remain authoritative.

### API client functions and schemas

```ts
export const applicationMessageVisibilitySchema: z.ZodEnum<[
  "applicant_visible",
  "officer_only",
]>;
export const applicationMessageAppendRequestSchema: z.ZodType<ApplicationMessageAppendRequest>;
export const applicationMessageReadSchema: z.ZodType<ApplicationMessageRead>;
export const applicationTransitionActionSchema: z.ZodEnum<[...]>;
export const applicationTransitionRequestSchema: z.ZodType<ApplicationTransitionRequest>;

export type ApplicationMessageAppendRequest = {
  body_markdown: string;
  visibility: "applicant_visible" | "officer_only";
  client_message_id?: string | null;
};
export type ApplicationMessageRead = z.infer<typeof applicationMessageReadSchema>;
export type ApplicationTransitionRequest = z.infer<typeof applicationTransitionRequestSchema>;

export function appendOfficerApplicationMessage(input: {
  applicationId: string;
  bodyMarkdown: string;
  visibility: "applicant_visible" | "officer_only";
  clientMessageId: string;
}): Promise<ApplicationMessageRead>;

export function transitionOfficerApplication(input: {
  applicationId: string;
  expectedVersion: number;
  body: ApplicationTransitionRequest;
}): Promise<ApplicationRead>;
```

The transition schema includes the direct request fields (`notes`, `decision_reason`, `thread_id`, `reason`, `new_owner_id`) but its action enum is the beta-iii exposed subset, not `claim`, `route`, or `reassign`.

## 6. Authorization Model

Trust chain:

1. Pomerium protects `/applications/{id}` and `/api/web/officer/` before the public catch-all (`plans/BACKLOG.md:564-570`, `plans/BACKLOG.md:624-625`).
2. The detail route probes `/api/me`; the current principal includes groups and `discord_user_id` (`services/api/app/contracts/web.py:13-19`).
3. Both new bridge endpoints call `_build_officer_actor`, which requires the `officers` group, validates the Pomerium Discord snowflake, resolves/creates a real Discord member, and returns `ActorIdentity(actor_kind="user", actor_id=<member uuid>)` (`services/api/app/api/v1/endpoints/web.py:75-129`).
4. Message append constructs server-side author fields and delegates to `append_application_message`; officers need `application.message` at the application target scope (`services/api/app/contracts/application_messages.py:10-12`, `services/api/app/services/application_messages.py:52-82`).
5. Transitions delegate to `transition_application`; the service checks `require_transition_authority` and owner constraints (`services/api/app/services/applications.py:348-362`, `services/api/app/services/applications.py:1075-1093`).

Permission mapping:

| Action | Permission | Notes |
| --- | --- | --- |
| message append | `application.message` | Required for officer-authored messages and officer-only reads. |
| review | `application.review` | Also requires current owner equals officer. |
| request_interview | `application.request_interview` | Also requires current owner equals officer. |
| waitlist | `application.waitlist` | Also requires current owner equals officer. |
| approve | `application.approve` | Also requires current owner equals officer. |
| deny | `application.deny` | Also requires current owner equals officer. |
| reactivate | `application.reactivate` | Owner fallback must exist or `new_owner_id` must be supplied by future owner-picker work. |
| withdraw | `application.withdraw` | User actor reviewer id is recorded by `_reviewer_id` (`services/api/app/services/applications.py:266-273`). |

`route` would map to `application.route` under the helper, but is not exposed because the service rejects it before transition (`services/api/app/services/applications.py:1068-1074`). `reassign` maps internally to `application.review`, but remains out of scope because it requires owner selection.

## 7. Test Plan

### API bridge tests

Extend `services/api/tests/test_web_officer_applications.py`:

- Message append requires Pomerium identity, officer group, Discord claim, real Discord member, and `application.message`. Risk annotation: `group=TG-1; named_risk=message_actor_binding; level=api`.
- Message append ignores applicant receipt and `X-Actor-*`, recording author fields from the Pomerium-resolved officer. Risk annotation: `group=TG-1; named_risk=message_actor_spoofing`.
- Message append happy path returns `ApplicationMessageRead`, appears in transcript, preserves `visibility`, and uses 201 for created / 200 for duplicate `client_message_id`. Risk annotation: `group=TG-2; named_risk=message_idempotency`.
- Transition bridge requires `If-Match`; missing header returns 428 and malformed/stale returns 412 via `parse_if_match_strong`. Risk annotation: `group=TG-3; named_risk=transition_optimistic_locking`.
- Transition bridge happy paths cover `review` and `approve`, assert version increments and ETag is set.
- Transition bridge permission matrix tests at least one denied action, expecting `403 authority_decision_denied`.
- Transition bridge owner constraint test expects `409 application_not_owner` for a non-owner reviewer on `approve`.
- Required-field tests cover `review` missing notes, `approve` missing decision reason, and `waitlist` missing reason using shared mapper codes.
- Dependency-tree guard expands to include the two POST routes while preserving no `get_current_actor`, no `CURRENT_ACTOR.get`, no `verify_applicant_receipt`, and no `applicant_receipt` source assertions (`services/api/tests/test_web_officer_applications.py:170-177` and the existing guard section).

### Component tests

Add `services/web/tests/officer-actions.spec.ts` or extend `services/web/tests/officer-detail.spec.ts`:

- Composer renders only after officer auth and successful detail load. Risk annotation: `group=TG-4; named_risk=unauthorized_actions_hidden; level=component`.
- Composer sends body, visibility, and client message id to `/api/web/officer/applications/{id}/messages`; it does not send author fields.
- Composer success refetches transcript and clears textarea.
- `claimed` shows `review` and `withdraw`; `in_review` shows `request_interview`, `waitlist`, `approve`, `deny`, `withdraw`; `approved`, `denied`, and `withdrawn` show no transition controls. Risk annotation: `group=TG-4; named_risk=state_machine_visibility`.
- Required fields disable or block submit until present for `review`, `waitlist`, `approve`, and `deny`.
- Transition success sends `If-Match`, replaces application state/version, and refetches transcript.
- `409`, `412`, `428`, `403`, Zod parse failure, and network/5xx show stable notices and do not leave controls stuck disabled.

### E2E

Extend `infra/tests/e2e/tests/19-web-ui.sh` and `infra/tests/e2e/lib/playwright/browser-flow.mjs` after the existing detail assertion (`infra/tests/e2e/lib/playwright/browser-flow.mjs:160-184`):

1. Seed `application.message`, `application.review`, and `application.approve` for the officer. The current script already seeds message authority separately and review/claim through the grant helper (`infra/tests/e2e/tests/19-web-ui.sh:95-140`, `infra/tests/e2e/tests/19-web-ui.sh:173-177`); extend that grant set to include approve.
2. From the claimed detail page, append an officer-only message and assert it appears in the transcript.
3. Submit `review` with notes; assert the UI state becomes `in_review`, then query Postgres and assert `applications.state = 'in_review'` and an `application.review` audit row has request surface `/api/v1/web/officer/applications/{id}/transitions`.
4. Submit `approve` with decision reason; assert the UI state becomes `approved`, then query Postgres and assert `applications.state = 'approved'`, `decision_reason` is set, and action type is `application.decision`.
5. Record the transition proof in a sibling session artifact such as `web-ui-actions.json`.

Risk annotations:

- `TG-1 actor_binding`: bridge actor remains Pomerium-bound, not browser/cookie-bound.
- `TG-2 message_visibility`: officer-only messages require `application.message` and appear only through transcript authorization.
- `TG-3 optimistic_locking`: stale writes do not silently use the live version.
- `TG-4 state_machine`: UI action visibility stays aligned with service transitions.
- `TG-5 e2e_persistence`: live web path mutates persisted state and audit request surfaces.

## 8. Anti-scope

- No `route` UI or bridge support until the service supports officer-authored routing; current `transition_application` rejects route (`services/api/app/services/applications.py:1068-1074`).
- No `reassign` UI, owner picker, owner search, or member lookup. A future BL item should own owner selection.
- No claim changes; INIT-133B-i queue remains the claim surface.
- No Discord-visible sends, channels, embeds, roles, moderation, or side effects. BL-009 owns Discord-side rollout (`plans/BACKLOG.md:260`, `plans/BACKLOG.md:646-647`).
- No applicant DM materialization; BL-020 owns that downstream surface (`plans/BACKLOG.md:646-647`).
- No message editing, deletion, replies/threading, attachments, markdown rendering beyond escaped text, pagination, transcript filters, SSE, WebSocket, or polling.
- No new permissions, actor kinds, schema migrations, Authentik/Pomerium routes, applicant receipt use, browser actor headers, feature flags, backwards-compatibility shims, deprecated aliases, or deferred stubs (`AGENTS.md:564-583`).

## 9. Diff Budget

Estimated net: `+720 / -30` lines.

Breakdown: API bridge + contract + tests `+230`; SPA client/components/helper/styles `+300 / -30`; Playwright component tests `+130`; e2e/static fixture extensions `+90`. If implementation exceeds `+900` net lines, adds new permissions/schema, touches Authentik/Pomerium route policy, or implements `route`/`reassign`, the scope gate should fail and split the work.

## 10. Risk Gates (Self-Review)

### Audit

LOW. The proposal reuses the beta-i officer actor bridge, server-side author construction, shared error mapper, existing message service, existing transition service, and existing optimistic-locking helpers. It explicitly avoids browser-supplied actor fields.

### Scope

LOW. The slice is constrained to detail-page messages plus supported non-claim transitions. It does not add Discord-visible effects, owner selection, schema changes, new grants, new identity chains, or routing policy.

### Shortcut

LOW. The bridge calls Python services directly instead of HTTP self-calls, the SPA uses Zod schemas for all new request/response shapes, and action visibility is table-driven rather than hard-coded into scattered JSX conditionals.

### Supported-surface

LOW. Browser paths stay under existing `/api/web/officer/` and `/applications/` protected surfaces. The transition endpoint shape mirrors the direct API while constraining unsupported beta-iii actions so the UI cannot ship broken controls.

## 11. Hookpoint Preview

Reuse:

- `_build_officer_actor` / `get_officer_actor` for officer identity (`services/api/app/api/v1/endpoints/web.py:75-143`).
- `raise_known_application_error` for application/message/transition mapper codes (`services/api/app/api/v1/endpoints/applications/_shared.py:68-202`).
- `parse_if_match_strong` and `set_etag` for transition optimistic locking (`services/api/app/api/v1/endpoints/applications/_shared.py:38-65`).
- `transition_application`, `VALID_TRANSITIONS`, `require_transition_authority`, and `_reviewer_id` for all transition semantics (`services/api/app/services/applications.py:65-89`, `services/api/app/services/applications.py:266-273`, `services/api/app/services/applications.py:348-362`, `services/api/app/services/applications.py:1059-1142`).
- `append_application_message` and message visibility/authority substrate (`services/api/app/services/application_messages.py:52-82`, `services/api/app/services/application_messages.py:85-158`).
- Existing detail route bootstrap, metadata/transcript rendering, and refresh pattern (`services/web/src/features/officer/ApplicationDetailRoute.tsx:184-315`).
- Queue claim API client error/ETag pattern (`services/web/src/api/client.ts:280-303`) and queue claim UI mutation pattern (`services/web/src/features/officer/ApplicationQueueRoute.tsx:96-115`).
- Existing Playwright detail fixture style and transcript assertions (`services/web/tests/officer-detail.spec.ts:164-202`, `services/web/tests/officer-detail.spec.ts:286-350`).

New:

- Two POST bridge endpoints: `/api/v1/web/officer/applications/{id}/messages` and `/api/v1/web/officer/applications/{id}/transitions`.
- `OfficerApplicationMessageAppendRequest` bridge contract in `services/api/app/contracts/web.py`.
- Message composer component.
- Transition action button group component.
- State machine helper for exposed officer transition actions.
- Client Zod schemas/functions for messages and non-claim transitions.
- Component and e2e tests proving message append plus claim -> review -> approve.

Leave alone:

- Direct `/api/v1/applications/{id}/messages` and `/api/v1/applications/{id}/transitions` endpoint behavior.
- Queue claim endpoint and UI.
- Pomerium/Authentik configuration.
- Discord-visible side-effect emitters, DM materialization, and owner reassign workflows.
