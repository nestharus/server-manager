# INIT-133B-ii problem map — officer detail page + transcript

Source: BL-019D-β-ii in `plans/BACKLOG.md`. Greenfield SPA work
on top of β-i.

## What we're building

After β-i landed (officer queue page + claim), the next slice
adds the **application detail surface**: a route at
`/applications/{id}` where an officer can:

1. See the full application (applicant, scope, responses,
   state, owner, version, timestamps).
2. See the chronological transcript (INIT-132 endpoint merging
   activity_state_changes + application_messages with
   visibility filtering).
3. Read-only — NO actions in this slice. Claim is on the queue
   page (β-i). Other transitions and message append are β-iii.

## Backend prerequisites

All in place:

- `GET /api/v1/applications/{id}` — existing single-application
  read endpoint at
  `services/api/app/api/v1/endpoints/applications/lifecycle.py`.
  Returns `ApplicationRead`. Authorization reuses
  `require_application_read_authority`.
- `GET /api/v1/applications/{id}/transcript` — INIT-132
  endpoint at
  `services/api/app/api/v1/endpoints/applications/transcript.py`
  returns `ApplicationTranscriptRead` (discriminated union of
  state-change + message entries).

## Officer bridge prerequisites

β-i added `/api/v1/web/officer/applications` (list) and
`/api/v1/web/officer/applications/{id}/claim` (claim). β-ii
needs **two new bridge endpoints**:

- `GET /api/v1/web/officer/applications/{id}` — bridge to single-
  application read; reuses `_build_officer_actor`.
- `GET /api/v1/web/officer/applications/{id}/transcript` —
  bridge to transcript; reuses `_build_officer_actor`.

Both are read-only; no `If-Match`, no `set_etag` complexity.

## SPA prerequisites

β-i landed:
- TanStack Solid Router as the SPA entry.
- `ApplicationQueueRoute` at `/applications/queue`.
- `client.ts` with `ApiError`, `getJson`, Zod schemas for
  `ApplicationRead`, `ApplicationListRead`,
  `applicationTransitionResponseSchema`.

β-ii needs:
- Solid route at `/applications/{id}` →
  `ApplicationDetailRoute` (officer-gated).
- API client: `fetchOfficerApplication(id)` and
  `fetchOfficerApplicationTranscript(id)` with Zod schemas.
- Zod schemas for `ApplicationTranscriptRead` (discriminated
  union of `activity_state_change` + `application_message`
  entries).

## Anti-scope

Out of scope for β-ii, deferred to β-iii:
- Message thread (POST `/messages`).
- Non-claim transitions (review/approve/deny/waitlist/...).
- "Back to queue" navigation polish — basic Link is fine.
- Pagination on transcript (transcripts are bounded).

## Open questions for the proposal

### Q1. Route path

Lock: `/applications/{id}` (per β-i contract preview).
Pomerium needs to add `prefix:/applications/` (or a more
specific shape) to gate this route. β-i only gates the bare
`/applications/queue` path. The `/applications/{id}` path
falls under the catch-all today (public).

This is a real Pomerium decision. The applicant form is at
`/applications` (bare) and is public. So the gating shape:
- `path:/applications` — public (applicant form).
- `path:/applications/queue` — auth-gated officer queue.
- `prefix:/applications/` — auth-gated officer detail (matches
  `/applications/<uuid>` and any nested path).

Wait, `prefix:/applications/` matches `/applications/queue`
too — collision. Resolution: keep `path:/applications/queue`
ahead of `prefix:/applications/`; first-match-wins so
`/applications/queue` resolves to its dedicated path entry,
and `/applications/<uuid>` falls to the prefix.

### Q2. Detail page layout

Two columns (desktop) / stacked (mobile):
- Left: application metadata (state, owner, applicant,
  scope, version, submitted_at) + responses (fields rendered
  based on form definition's field types — but for v1, treat
  responses as plain key-value pairs from `ApplicationRead.responses`).
- Right: transcript (chronological feed of state changes +
  messages, scrolling).

Lock: simple two-column for v1; mobile responsiveness follows
the existing CSS module pattern from β-i.

### Q3. Transcript rendering

Each entry is a discriminated union:
- `activity_state_change`: `{kind: "state_change", from_state,
  to_state, action, actor_kind, actor_id, occurred_at}`.
- `application_message`: `{kind: "message", id, body, visibility,
  author_member_id, created_at}` (visibility-filtered server-side).

Render entries chronologically with type-distinct styling. Show
actor display name where available — but actor lookup is out of
scope for v1; show actor_kind + truncated actor_id.

### Q4. Authorization model

Same as β-i: officer group + Pomerium Discord identity →
member UUID → application authority. The detail bridge calls
the existing `read_application` service with the resolved
`ActorIdentity`, and the existing `require_application_read_authority`
gate decides 200 vs 403.

If officer has no read authority on this application's scope
→ 403 `application_read_forbidden`. Map via
`raise_known_application_error`.

### Q5. Component contracts

```ts
export function ApplicationDetailRoute(): JSX.Element;
export function ApplicationTranscriptList(props: {
  entries: readonly TranscriptEntry[];
}): JSX.Element;

export function fetchOfficerApplication(applicationId: string):
  Promise<ApplicationRead>;
export function fetchOfficerApplicationTranscript(applicationId: string):
  Promise<ApplicationTranscriptRead>;
```

Route reads `useParams()` for the id; bootstrap pattern same
as β-i (`onMount` with bootstrap async function).

### Q6. Test plan

- API tests:
  `services/api/tests/test_web_officer_applications.py`
  extension — bridge GET single + GET transcript happy paths,
  identity failures (re-uses `_build_officer_actor`), authority
  denied, 404 on non-existent id.
- Component tests:
  `services/web/tests/officer-detail.spec.ts` — auth states,
  detail render, transcript render, 404 handling.
- E2e: extend `19-web-ui.sh` after the queue/claim leg to
  navigate to the just-claimed application's detail page,
  verify metadata + transcript include the claim event.

### Q7. Anti-scope

- No actions on detail page (no claim button, no transitions,
  no message append).
- No actor display-name lookup (just kind + truncated id).
- No transcript filtering UI (visibility decision is server-side).
- No optimistic locking / If-Match (read-only).
- No live updates (refetch on user action, no SSE/WebSocket).

## What the proposal must lock

1. Q1 Pomerium routing for `/applications/{id}`.
2. Q2 detail page layout and responses rendering.
3. Q3 transcript entry rendering shape + styling.
4. Q4 authorization mapping (re-use `_build_officer_actor`).
5. Q5 component + client function signatures (Zod schemas
   matching `ApplicationTranscriptRead`).
6. Q6 test plan.
7. Q7 anti-scope.

## Dependencies + sequencing

- β-i is the prerequisite (Solid Router entry + bridge actor
  helper + identity binding chain). Done.
- β-ii lands as a standalone slice on the same branch.
- β-iii follows with messaging + transitions.

## Diff budget

Estimate ~+450 / -50 net lines (smaller than β-i because most
infra exists):
- Bridge: ~+60 (two thin GET endpoints).
- SPA: ~+250 (route + transcript component + Zod schemas).
- Pomerium config: ~+10.
- Tests: ~+150 (API + component + e2e).
