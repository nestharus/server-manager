# BUG-10 — Supported-surface risk gate

**Verdict:** LOW

BUG-10 (officer detail route does not re-render the transcript after
`setTranscript(...)` because the unkeyed parent `<Show>` child callback
destructures `detail()` once, freezing `readTranscript.entries` against
the initial transcript object — RCA §1-§5) is repaired by replacing the
object-returning `<Show>` `when` with a plain truthy gate and threading
signal-backed accessor props (`() => ApplicationRead`,
`() => ApplicationTranscriptRead["entries"]`, `() => string`) into the
five detail children, so downstream JSX continues to read from the
`application()` / `transcript()` signals on every truthy-to-truthy
update (proposal §2 Q1-Q2, §3). The fix lives entirely under the
officer feature folder
(`services/web/src/features/officer/ApplicationDetailRoute.tsx`,
`ApplicationMessageComposer.tsx`,
`ApplicationTransitionActions.tsx`) plus one new Playwright spec at
`services/web/tests/ApplicationDetailRoute.spec.tsx` (proposal §3, §6).
No public API, no SPA route URL, no env var, no DB migration, no
GitOps manifest, and no Pomerium/Authentik resource is touched
(proposal §5 anti-scope explicitly forbids each of these, including
the Solid compat shim at `services/web/src/solid-compat/solid.ts`).

## Surfaces touched

### 1. Public/SPA route URLs — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Detail route path `/applications/$applicationId` (TanStack Solid Router `useParams({ from: "/applications/$applicationId" })` at `ApplicationDetailRoute.tsx:188`) | as today | unchanged — proposal §3 limits modified files to the three component sources; no router config edit | none |
| Queue route link `/applications/queue` (`ApplicationDetailRoute.tsx:279`) | as today | unchanged — proposal §6 anti-scope: no broad route rewrites | none |
| Bridge endpoints consumed by the route (`fetchOfficerApplication`, `fetchOfficerApplicationTranscript`, `fetchCurrentPrincipal`, `appendOfficerApplicationMessage`) | as today | unchanged — proposal §5: "Do NOT change the bridge endpoints"; proposal §6: API client changes "Not expected" | none |
| Backend route `GET /api/web/officer/applications/{id}/transcript` (RCA §1; `services/web/src/api/client.ts:388-392`) | already returns 200 with the appended message after `setTranscript(...)` (RCA "Symptom + state": "The transcript API returns 200 and includes the new message") | unchanged — fix is below the API boundary; the bug is purely client-side reactivity, not API persistence, authorization, or serialization (RCA §2 "isolates the failure to client reactivity after `setTranscript(...)`, not API persistence") | none |

Risk on §1: **none** — gate criterion 1 (no public/SPA route URL
changes) holds. The route URL, the query parameter shape, and the
backend bridge endpoints all remain byte-identical.

### 2. Environment variables — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `VITE_API_BASE_URL` and other Vite envs consumed by `services/web/src/api/client.ts` | as today | unchanged — no new env reads in any of the three modified files | none |
| Officer Discord identity envs (e.g., `E2E_OFFICER_DISCORD_USER_ID`) | already provided by the e2e harness | unchanged — the regression spec at `services/web/tests/ApplicationDetailRoute.spec.tsx` mocks `/api/me`, `/api/web/officer/applications/{id}`, and the transcript endpoint directly (proposal §4 TG-2), so it adds no new env requirement | none |
| Compat shim `services/web/src/solid-compat/solid.ts` | as today (RCA §6: `For` and `Show` are direct re-exports of installed Solid 2 beta) | unchanged — proposal §5: "Do NOT modify the compat shim `services/web/src/solid-compat/solid.ts`"; the bug is the route's destructure pattern, not the shim | none |

Risk on §2: **none** — gate criterion 2 (no env vars) holds. Proposal
§6 budget excludes "new frontend dependencies" and the modified file
list is narrow; no `import.meta.env` access is added.

### 3. Database migrations — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head (`migrations/versions/...`) | current head | unchanged — proposal §3 limits all modified files to the three component sources under `services/web/src/features/officer/`; no DDL or migration is introduced | none |
| Schemas of `application_messages`, transcript projections, or any backing table | as defined by prior migrations | unchanged — proposal §5: "Do NOT modify the API or transcripts service"; the fix does not run new SQL, change column shapes, or add indexes | none |

Risk on §3: **none** — gate criterion 3 (no DB migrations) holds.

### 4. GitOps / Pomerium / Authentik — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/applications/server-manager/**` | as today | unchanged — proposal §3 modifies only files under `services/web/src/features/officer/`; no Kustomization, Job, or Service manifest is touched | none |
| `gitops/channels/local/auth/pomerium/**` | as today | unchanged — proposal §5: "Do NOT change... authorization behavior"; the fix is below the auth boundary, and `/api/me` already returns 200 with the spoofed officer principal in the failing test (RCA §1) | none |
| `gitops/channels/local/auth/authentik/**` | as today | unchanged — no OAuth, claim mapping, or blueprint change | none |
| Pomerium claim headers / route allowlist | as today | unchanged — the bug reproduces under the existing officer principal mock (RCA §1, "Detail page renders `state=claimed`"), confirming auth configuration is not on the change surface | none |

Risk on §4: **none** — gate criterion 4 (no GitOps/Pomerium/Authentik
changes) holds.

### 5. Children's exported types — value → accessor (auditable in TypeScript)

The runtime API for the affected detail children changes from plain
value props to accessor functions, per proposal §2 Q2 and §3. This is
the only surface delta and is enforced by TypeScript at every call
site.

| Type / component | Pre (value prop) | Post (accessor prop) | Callers |
|---|---|---|---|
| `ApplicationMetadataPanelProps.application` (`ApplicationDetailRoute.tsx:21-23`) | `ApplicationRead` | `() => ApplicationRead` | one in-file site at `ApplicationDetailRoute.tsx:335` |
| `ApplicationResponsesPanelProps.application` (`ApplicationDetailRoute.tsx:25-27`) | `ApplicationRead` | `() => ApplicationRead` | one in-file site at `ApplicationDetailRoute.tsx:336` |
| `ApplicationTranscriptListProps.entries` (`ApplicationDetailRoute.tsx:29-31`) | `ApplicationTranscriptRead["entries"]` | `() => ApplicationTranscriptRead["entries"]` | one in-file site at `ApplicationDetailRoute.tsx:350` |
| `ApplicationMessageComposerProps.applicationId` (`ApplicationMessageComposer.tsx:13`) | `string` | `() => string` | one in-file site at `ApplicationDetailRoute.tsx:338` |
| `ApplicationTransitionActionsProps.application` (`ApplicationTransitionActions.tsx:18`) | `ApplicationRead` | `() => ApplicationRead` | one in-file site at `ApplicationDetailRoute.tsx:344` |

Caller audit (verified via `grep` over the repository):

- `ApplicationMetadataPanel`, `ApplicationResponsesPanel`, and
  `ApplicationTranscriptList` are defined in
  `ApplicationDetailRoute.tsx` and are imported by no other source
  file. Their three exported `*Props` type names appear only in
  `ApplicationDetailRoute.tsx` and in the historical proposal
  `proposals/14-init-133B-ii-detail-transcript.md` (documentation,
  not a runtime caller).
- `ApplicationMessageComposer` is imported only by
  `ApplicationDetailRoute.tsx` (sibling import at line 17).
- `ApplicationTransitionActions` is imported only by
  `ApplicationDetailRoute.tsx` (sibling import at line 18).

Result: every runtime caller of the changed prop types is the same
file that owns the change. There is no external consumer in
`services/web` or elsewhere in the repo, so no downstream package or
slice is affected by the value→accessor flip.

| Aspect | Pre | Post | Risk |
|---|---|---|---|
| Prop names (`application`, `entries`, `applicationId`) | as today | unchanged — only the prop *shape* changes from `T` to `() => T` (proposal §2 Q2) | none |
| Other props on the same components (`disabled`, `onMessageAppended`, `onTransitioned`, `onError`) | as today | unchanged — proposal §2 Q2: "`disabled`, callback props, and local component state do not need to be converted" | none |
| Component test ids (`application-transcript`, `application-detail-state`, `application-detail-version`) | as today | unchanged — proposal §3: "preserve current local state, submit/transition behavior, labels, test ids, and API client calls" | none |
| TypeScript compile-time enforcement | strict | strict — call-site mismatches surface as compile errors at the single in-file caller, which is updated in the same patch | none — auditable; no runtime-only surface |

Risk on §5: **none** — gate criterion 5 (the runtime API for the
children's exported types changes from value to accessor — auditable
in TypeScript callers) holds. The change is contained to one file's
call sites; TypeScript will block any out-of-date caller from
compiling.

### 6. Anti-scope items — explicitly held out

| Surface | Status | Source |
|---|---|---|
| `services/web/src/solid-compat/solid.ts` | not modified | proposal §5: "Do NOT modify the compat shim" |
| API service / transcripts service | not modified | proposal §5: "Do NOT modify the API or transcripts service" |
| Bridge endpoints | not modified | proposal §5: "Do NOT change the bridge endpoints" |
| Compatibility shims, feature flags, alternate component paths, test-only setters | not introduced | proposal §5: "Do NOT add compatibility shims, feature flags, alternate component paths, or test-only setters" |
| Transcript serialization, message append payloads, transition contracts, authorization behavior | not modified | proposal §5: "Do NOT change transcript serialization, message append payloads, transition contracts, or authorization behavior" |
| Test-only export of `setTranscript` | not introduced | proposal §2 Q3: "Do not add test-only exports or expose `setTranscript`. Fire the update through an existing user-visible route action" |
| CSS / layout, new frontend deps, broad route rewrites, API-client edits | not introduced | proposal §6 budget: "Not expected" list |

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public/SPA route URL changes | PASS |
| 2. No env vars | PASS |
| 3. No DB migrations | PASS |
| 4. No GitOps / Pomerium / Authentik changes | PASS |
| 5. Children's exported types change from value to accessor — auditable in TypeScript callers | PASS |

## Findings

1. **No public/SPA route URL change.** The route path
   `/applications/$applicationId`, the queue link
   `/applications/queue`, and every bridge endpoint
   (`fetchOfficerApplication`,
   `fetchOfficerApplicationTranscript`, `fetchCurrentPrincipal`,
   `appendOfficerApplicationMessage`) are byte-identical pre/post.
   Proposal §5 anti-scope forbids bridge or API-client edits;
   proposal §6 budget marks API-client changes as "Not expected".

2. **No env vars added.** The three modified component files do not
   read `import.meta.env`; the proposed regression spec mocks
   `/api/me`, the detail endpoint, and the transcript endpoint
   directly, so it introduces no new env requirement.

3. **No DB migrations.** Proposal §3 limits modified files to three
   component sources under `services/web/src/features/officer/`
   plus one new spec under `services/web/tests/`; no Alembic
   revision, no DDL, no SQL is added or executed.

4. **No GitOps / Pomerium / Authentik changes.** The fix is a
   client-side Solid reactivity correction. `/api/me` already
   returns 200 with the spoofed officer principal in the failing
   reproduction (RCA §1 "Symptom + state": "Officer queue renders
   the chapter-scoped application. Officer claim returns 200.
   Detail page renders `state=claimed`"), which is independent
   evidence that the auth surface is not on the change set.

5. **Runtime API change from value → accessor is fully
   TypeScript-auditable.** Five exported types
   (`ApplicationMetadataPanelProps.application`,
   `ApplicationResponsesPanelProps.application`,
   `ApplicationTranscriptListProps.entries`,
   `ApplicationMessageComposerProps.applicationId`,
   `ApplicationTransitionActionsProps.application`) flip from
   `T` to `() => T`. A repo-wide grep confirms each is consumed by
   exactly one caller — `ApplicationDetailRoute.tsx` — which is
   updated in the same patch. `ApplicationMetadataPanel`,
   `ApplicationResponsesPanel`, and `ApplicationTranscriptList`
   are defined in the same file and not exported to any other
   module; `ApplicationMessageComposer` and
   `ApplicationTransitionActions` are imported only from
   `ApplicationDetailRoute.tsx`. There is no external slice,
   package, or runtime consumer that can silently observe a
   stale signature, and TypeScript will refuse to compile any
   missed call site.

6. **Anti-scope held in full.** The Solid compat shim, API
   service, transcripts service, bridge endpoints, compatibility
   shims, feature flags, alternate component paths, test-only
   `setTranscript` exposure, transcript serialization, transition
   contracts, and authorization behavior are all explicitly out
   of scope per proposal §5 and §6, and the diff budget (three
   source files + one new spec, ~120-220 changed lines)
   structurally cannot reach those surfaces.

## Out-of-scope items intentionally not addressed

- The Solid 2 beta unkeyed `Show` semantics themselves (RCA §2,
  §6) — the fix works around the documented behavior by not
  destructuring at the boundary, rather than altering the shim or
  the upstream primitive.
- Other detail-route data flows that incidentally also stale-capture
  via the same `Show` (metadata, responses, transition action
  visibility) — proposal §1 and §2 Q2 fold these into the same
  accessor-prop change because they share the destructured `read`
  object; they are not a separate surface.
- The chapter fixture and officer authority seeding owned by
  BUG-5 / BUG-7 (`infra/tests/e2e/lib/seed-authority-grants.mjs`,
  `seed-chapter-fixture.mjs`) — not on this change surface.
- The compat shim's behavior around legacy effects, `createContext`,
  or direct `createSignal` re-export touched by BUG-1 (RCA §6) —
  explicitly out of scope per proposal §5.

## Verdict

**LOW** — the fix is a self-contained client-side reactivity
correction confined to three component files under
`services/web/src/features/officer/` plus one new Playwright
regression spec under `services/web/tests/`. It changes no public
API, no SPA route URL, no env var, no DB schema, no GitOps
manifest, and no auth resource. The only runtime API delta is the
value→accessor flip on five exported prop types, each of which has
exactly one in-repo caller (the same file owning the change), so
the surface is fully auditable at compile time and cannot leak to
external consumers.

SUPPORTED_SURFACE_DONE: plans/risk/bug-10-supported-surface.md
