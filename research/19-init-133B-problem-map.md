# INIT-133B problem map — SPA officer review surface

Source: BL-019D-β in `plans/BACKLOG.md`. Greenfield SPA work; folded
problem-map into a single artifact (no Phase 0 RCA — feature, not bug).

## What we're building

A web surface where an officer (Pomerium-authenticated) can:

1. See a queue of applications (filterable by state + chapter scope).
2. Open one application to see details + transcript + message thread.
3. Take action: claim, message the applicant, transition state
   (queued → claimed → in_review → approved | denied | …).

Backend prerequisites are already in place:

- `GET /api/v1/applications` — INIT-133A list endpoint (paged, scoped).
- `GET /api/v1/applications/{id}` — single-application read.
- `GET /api/v1/applications/{id}/transcript` — INIT-132 chronological merge.
- `GET/POST /api/v1/applications/{id}/messages` — INIT-131 substrate
  (visibility = `applicant_visible | officer_only`, idempotent on
  `client_message_id`).
- `POST /api/v1/applications/{id}/transitions` — existing transition surface.

## The decomposition (per handoff)

- **133B-i** — queue page only (list + claim button). **This slice.**
- **133B-ii** — detail page + transcript view (read-only).
- **133B-iii** — message thread + decision actions.

133B-i is the foundation: it forces us to resolve the SPA architecture
question below, settles auth wiring, settles route patterns, and lets
133B-ii/iii layer on without re-litigating those choices.

## Substrate audit — current SPA state

`services/web/` is in a **dual-system limbo**:

- **Live entry** (loaded by `index.html`): `src/main.tsx`, 314 lines of
  vanilla DOM via `innerHTML` strings. Handles three pseudo-routes
  (`/`, `/applications`, `/admin/chapters`) by checking
  `window.location.pathname`. The applicant Discord OAuth flow,
  receipt-required submit, and admin-chapters placeholder all live here.
- **Parallel scaffolding** (NOT loaded by anything): TanStack Solid
  Router setup at `src/app/router.tsx`, `src/app/providers.tsx`,
  `src/RuntimeApp.tsx`, plus Solid components at
  `src/features/{public,admin}/*Route.tsx`. Imports `@tanstack/solid-router`,
  `@tanstack/solid-router-devtools`, Ark UI primitives, `solid-js`.
  None of it is mounted today.

The `compat.spec.ts` Playwright suite exercises `main.tsx` only. The
"tanstack" / "ark" / "fontawesome" library names in
`infra/tests/fixtures/web-ui/contract.json` describe vanilla HTML
elements (an `<a>` tag, a `<button role="tab">`, a `<span data-testid>`)
— the contract uses those library names as labels, but the production
runtime doesn't actually render any framework component.

This is the central technical question for 133B-i: **do we extend
`main.tsx` (more vanilla DOM) or wire up the existing Solid Router
scaffolding as the real entry?**

## Open questions for the proposal

### Q1. SPA architecture (load-bearing)

Three candidates:

- **A. Extend `main.tsx`.** Add officer queue route (path-checked) into
  the same vanilla file. Pros: zero infrastructure churn, fastest path
  to a working slice. Cons: `main.tsx` already at 314 lines with three
  routes — adding a queue + (later) detail + thread + actions makes it
  unmaintainable. Defers the migration question to 133B-ii or 133B-iii
  where it'll be even harder.

- **B. Wire up the Solid Router as the entry.** Replace `main.tsx`'s
  vanilla bootstrap with `AppProviders + router`. Migrate
  `/`, `/applications`, `/admin/chapters` into Solid routes that mirror
  current vanilla behavior. Add `/applications/queue` as a new Solid
  route. Pros: decisively resolves the parallel-systems problem;
  133B-ii/iii build on a real router; lines up with the pre-scaffolded
  infra; matches AGENTS.md "no parallel systems / no compatibility shims".
  Cons: bigger diff for this slice; risk of regressing the existing
  applicant flow if the migration isn't a strict behavioral mirror.

- **C. Mount queue route via Solid Router beside `main.tsx`'s vanilla
  rendering.** `main.tsx` keeps the existing public/applications/admin
  routes; queue routes mount through the router only. Pros: smaller
  diff than B. Cons: locks in the dual-system limbo permanently —
  exactly the parallel-systems pattern AGENTS.md prohibits.

Recommended: **B**. Resolves parallel infra, aligns with AGENTS.md,
unblocks 133B-ii/iii cleanly. Carries the regression risk that the
audit/scope/shortcut/supported-surface gates must catch. C is the
explicit anti-pattern; A is short-term speed at the cost of
133B-ii/iii.

### Q2. Officer identity surface

Today: `services/api/app/api/v1/endpoints/web_admin.py` (or wherever
`/api/v1/web/admin/chapters` lives) reads Pomerium claim headers.
`/api/v1/me` returns the principal. Officer auth = Pomerium identity
with `groups=officers` (per `infra/tests/fixtures/web-ui/contract.json`).

Question: does the queue page call `/api/v1/me` itself or rely on the
list endpoint's 401/403 to drive an unauthenticated state? Lock for the
proposal: **call `/api/v1/me` once on route mount, gate the queue UI on
the response, and rely on `/api/v1/applications` to enforce
authorization at the data layer.** A 401/403 on the list call shows an
empty/forbidden message; the page doesn't try to "log in" — Pomerium
handles redirect.

### Q3. Route path

Candidates: `/admin/applications`, `/applications/queue`,
`/officer/applications`. The handoff suggested `/applications/queue` +
`/applications/{id}` — keeps "applications" as the surface noun and
keeps the queue/detail relationship obvious. Lock: **`/applications/queue`
for the list page, `/applications/{id}` later for detail.** This forces
us to keep applicant `/applications` (the form) and officer
`/applications/queue` distinct in routing logic — easy with the router
in option B, awkward in vanilla.

### Q4. Filter UX

Filters available from the list endpoint:
- `state` (`submitted | queued | claimed | in_review | interview |
  waitlisted | approved | denied | withdrawn`) — comma list.
- `scope_kind` + `scope_id` — typically chapter-bounded.
- `owner_id` — for "mine".

For 133B-i, lock the slice to:
- A state filter as a row of toggle buttons (default `queued,
  submitted` — anything actively needing attention).
- No scope filter UI yet — slice infers scope from the API's auth
  resolution (caller's chapter authority). Scope-selector is a
  follow-up if/when an officer holds authority over multiple chapters.
- No owner filter UI yet.

### Q5. Pagination UX

`GET /api/v1/applications` returns `{ items, next_after_id }`. Lock:
**simple "Load more" button** that appends to the same list when
`next_after_id` is non-null. No infinite scroll, no pre-fetch.
50/page is the API default.

### Q6. Claim button semantics

Claim → `POST /api/v1/applications/{id}/transitions` with body
`{ transition_type: "claim", ... }`. Authorization is enforced by the
endpoint (`application.claim` permission). Lock for 133B-i:
- Button is visible only when the application is in
  `submitted | queued` state (states from which `claim` is valid).
- On success, optimistically updates the row in place to show the
  caller as `owner_id` and state `claimed`; refetches the list once on
  success to confirm.
- 409 (state conflict) shows a toast/message and refetches.
- 403 hides the button on the next render.

### Q7. Test surface

Two layers:
- **Component tests**: probably a new spec file rather than extending
  `compat.spec.ts` (which is the public/applicant flow). Suggest
  `services/web/tests/officer-queue.spec.ts`.
- **E2E**: extend `infra/tests/e2e/tests/19-web-ui.sh` or add a new
  test (e.g., `21-officer-queue.sh`) that seeds an officer identity +
  a queued application and exercises the queue + claim flow against
  `humility-local`.

Lock: **new spec file** + **extend test 19-web-ui** with a single
queue assertion (officer login → queue visible → at least one item).
A dedicated `21-officer-queue.sh` is overkill for the slice.

### Q8. Anti-scope (explicit)

Out of scope for 133B-i, deferred to 133B-ii/iii:
- Application detail page (133B-ii).
- Transcript rendering (133B-ii).
- Message thread (133B-iii).
- Transitions other than `claim` (133B-iii).
- Sorting, bulk actions, export, search.
- Mobile / tablet layout polish — stick to `compat.spec.ts`'s
  desktop-first conventions.
- Storybook / component library work — out of scope.

## What the proposal must lock

1. SPA architecture (Q1) — pick A/B/C with justification.
2. Officer identity wiring (Q2) — what's the auth probe + failure UX.
3. Routes + nav surface (Q3) — exact paths + how the top-nav exposes
   the queue link, and how that's gated on officer-ness.
4. Filter + pagination + claim UX (Q4–Q6) — exact components.
5. Test plan (Q7) — spec file path + e2e changes.
6. Anti-scope (Q8) — make it explicit so risk-scope gate has something
   to check.
7. Diff budget — orient the gates and the build cookbook.

## Dependencies + sequencing

133B-i locks the architecture; 133B-ii layers detail+transcript;
133B-iii layers messaging+transitions. Do not pick up 133B-ii before
133B-i lands and the SPA architecture choice is durable.
