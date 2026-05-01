# BUG-10 — Shortcut risk gate (detail route transcript reactivity)

**Verdict:** LOW

Source: `proposals/23-bug-10-transcript-reactivity.md`,
`research/36-bug-10-transcript-reactivity-rca.md`,
`services/web/src/features/officer/ApplicationDetailRoute.tsx`,
`services/web/src/features/officer/ApplicationMessageComposer.tsx`,
`services/web/src/features/officer/ApplicationTransitionActions.tsx`.

## C1 — Real signal accessors, not local clone-copies

**Pass.**

Q1 (proposal lines 64-95) keeps the `Show` as a pure visibility gate over
`canReview() && application() !== null && transcript() !== null` and then
defines the child-facing values as functions that close over the route's
own signal getters:

```tsx
const read = () => application()!;
const readTranscript = () => transcript()!;
```

These are not snapshots. Each invocation re-enters `application()` /
`transcript()`, which Solid tracks as live signal reads. When child JSX
bindings or memos call `read()` or `readTranscript()`, the call chain ends
at the same `createSignal` accessors instantiated at
`ApplicationDetailRoute.tsx:193-194`, so a `setTranscript(next)` from
`loadTranscript` (`ApplicationDetailRoute.tsx:221-227`) propagates through
to the JSX binding the same way the *initial* truthy transition does.

The proposal makes the no-snapshot rule explicit at lines 92-95:

> The important constraint is that downstream JSX bindings and child
> components must call the accessor at render/update time. They must not
> convert it back into a local object snapshot at the `Show` boundary.

The same paragraph also rules out the obvious "shortcut" variants:

- Option b (`<Switch><Match>`) is rejected because it changes the
  control-flow primitive without fixing the stale-data boundary
  (lines 96-101).
- Option c (`createMemo`) is rejected because the bug is premature
  snapshotting, not expensive recomputation, so wrapping in a memo would
  be ceremony (lines 102-105).
- Option d (per-child `Show`) is rejected because it fragments the gate
  and forces every new child to own the loaded/reviewable check
  (lines 106-108).

Anti-scope (lines 232-244) reinforces by explicitly forbidding feature
flags, alternate component paths, test-only setters, and compat-shim
edits — none of those would be necessary here, and listing them as
out-of-scope removes the "I'll patch around it" escape hatch.

The data-attribute binding is also pinned to a reactive read at
lines 174-176:

> ensure `data-application-id` reads `application()!.id` from a reactive
> JSX binding, not from a destructured snapshot.

That matters because the current bundle compiles
`data-application-id={read.id}` against the captured `read`
(`ApplicationDetailRoute.tsx:328-333`), which is precisely the same
stale-snapshot pattern at the root of the bug. The proposal's wording
forces the binding to be `application()!.id`, not a reused local.

The pattern here is structurally the same one that `ApplicationTranscriptList`
already proves works when fed by a reactive source: its compiled form
`A(Mr,{get each(){return e.entries}, ...})` (RCA section 4) preserves the
boundary as a getter, so once the *parent* prop is an accessor the chain
is reactive end-to-end. The fix is the minimum change to restore that
reactivity, not an alternate rendering path.

## C2 — Children's prop signatures genuinely become accessor types in TypeScript

**Pass.**

Q2 (proposal lines 110-120) lists explicit TypeScript prop-type rewrites
for every affected child:

> - `ApplicationMetadataPanel`: `application: () => ApplicationRead`
> - `ApplicationResponsesPanel`: `application: () => ApplicationRead`
> - `ApplicationTranscriptList`: `entries: () => ApplicationTranscriptRead["entries"]`
> - `ApplicationMessageComposer`: `applicationId: () => string`
> - `ApplicationTransitionActions`: `application: () => ApplicationRead`

These are real type contract flips, verified against the current
declarations:

- `ApplicationDetailRoute.tsx:21-31` declares
  `ApplicationMetadataPanelProps.application: ApplicationRead`,
  `ApplicationResponsesPanelProps.application: ApplicationRead`, and
  `ApplicationTranscriptListProps.entries: ApplicationTranscriptRead["entries"]`
  as plain data — flipping them to `() => …` changes the contract the TS
  compiler enforces at every call site.
- `ApplicationMessageComposer.tsx:13-18` declares
  `applicationId: string` — flipping to `() => string` likewise becomes a
  compiler-checked contract.
- `ApplicationTransitionActions.tsx:18-23` declares
  `application: ApplicationRead` — same.

A "shortcut" version of this fix could have left the prop types as plain
data and only changed the *callers* to pass an accessor that the children
silently treat as data — that would compile only because TS is structural
and `() => ApplicationRead` is not assignable to `ApplicationRead` (so it
would actually fail; but a sloppier shortcut would have widened the prop
to `ApplicationRead | (() => ApplicationRead)` and added a runtime
discriminator). The proposal does neither. It commits to the accessor
type at the prop boundary, which makes the read-site changes
(`props.application()`, `props.entries()`, `props.applicationId()`) a TS
requirement, not a discipline issue.

Substrate (lines 178-184) re-states the read-site changes per child:

> - replace reads of `props.application` with `props.application()`;
> - replace reads of `props.entries` with `props.entries()`;
> - replace reads of `props.applicationId` with `props.applicationId()`;

Those reads exist today at concrete sites:
- `ApplicationDetailRoute.tsx:112-119` (metadata `rows()`),
- `ApplicationDetailRoute.tsx:126` (`Version {props.application.version}`),
- `ApplicationDetailRoute.tsx:145` (`Object.entries(props.application.responses)`),
- `ApplicationDetailRoute.tsx:177` (`<For each={props.entries}>`),
- `ApplicationMessageComposer.tsx:54` (`applicationId: props.applicationId`),
- `ApplicationTransitionActions.tsx:81-82` (`props.application.id`,
  `props.application.version`),
- `ApplicationTransitionActions.tsx:103` (`validOfficerTransitionActions(props.application.state)`).

Each of those is a TS-checked read against the new accessor type, so
none of them can survive a clean `tsc` after the prop signature change
without being rewritten to call the function. That makes C2 not just a
style preference but mechanically enforced.

The proposal also draws a tight perimeter on what does *not* flip:

> `disabled`, callback props, and local component state do not need to be
> converted unless the implementation naturally benefits from doing so.

That is the right bound. `disabled` is already a primitive prop that
Solid tracks reactively at the JSX boundary, and callback props
(`onMessageAppended`, `onTransitioned`, `onError`) are stable function
references whose identity does not encode stale data. Flipping them to
accessor form would be cargo-culted; not doing so is not a shortcut.

## C3 — TG-2 spec genuinely fires a `setTranscript` update and asserts re-render

**Pass.**

TG-2 (proposal lines 200-225) is structured as a route-level Playwright
spec that:

1. Mocks `/api/me` with an officer principal that has `discord_user_id`
   (matches the gate at `ApplicationDetailRoute.tsx:266-269`).
2. Mocks the application detail endpoint with an initial loaded
   application.
3. Mocks the transcript endpoint with **two** responses: first the
   initial state-change-only transcript, then a transcript that includes
   a new message entry.
4. Mounts/navigates to the application detail route.
5. Asserts the initial transcript renders.
6. **Triggers the route code path that calls `setTranscript(...)`** by
   submitting a mocked message append (which routes through
   `handleMessageAppended` → `loadTranscript` → `setTranscript` per
   `ApplicationDetailRoute.tsx:229-232` and `:221-227`) or clicking
   Refresh against the second mocked transcript response (which routes
   through `loadDetail` → `setTranscript` per
   `ApplicationDetailRoute.tsx:202-219` and the Refresh button at
   `:282-289`).
7. Asserts the new transcript entry renders inside
   `data-testid="application-transcript"` (the testid is fixed at
   `ApplicationDetailRoute.tsx:172`).

That is the actual "fires `setTranscript` and asserts the rendered DOM
updates" shape, not a synthetic mount-twice or a `getByText` against a
fresh render. The trigger goes through the same user-visible action that
e2e test 19 exercises, which is also the trigger that the existing
failing component tests at `services/web/tests/officer-actions.spec.ts:151-166`
and `:336-337` already use (per RCA section "Symptom + state"). So TG-2
encodes the same contract those tests were trying to enforce; it should
fail today on the captured `readTranscript` and pass after the accessor
flip.

Q3 (lines 138-151) explicitly forecloses two shortcut variants for the
test:

> Do not add test-only exports or expose `setTranscript`. Fire the
> update through an existing user-visible route action such as message
> append or refresh, with the second mocked transcript response
> containing the new entry.

That blocks:

- "Export `setTranscript` from the route module so the test can poke it
  directly" — that would assert reactivity of a signal that isn't the one
  the production code paths actually mutate, and would pass even if the
  prop boundary were still snapshotted (since calling `setTranscript`
  from outside the component skips the message-append code path entirely,
  but the *captured* readTranscript inside `Show` would still be
  refreshed because the test would be running before the snapshot was
  taken — so it would never fail on the bug at all).
- "Mount the route, swap the mock, force a re-mount" — that would test
  the null→truthy transition (which is already working per RCA's
  "Unaffected" list, line 261) instead of the truthy→truthy transition
  that is the actual defect.

The proposal's variant routes through real append/refresh handlers, so
the `Show` body stays mounted across the truthy→truthy transition that is
the bug surface.

The optional second assertion (lines 220-222: "optionally assert that
metadata or transition action visibility updates when the second mocked
application changes state/version") is a bonus regression — it covers
the broader "stale-capture pattern also freezes other props" claim from
the RCA (lines 256-258 and proposal lines 50-53). Treating it as
optional rather than required is reasonable; the transcript assertion
alone is sufficient to gate the specific reactivity defect, and the
metadata/transition assertion is a coverage extension, not a substitute.

## C4 — No "TODO: refactor children later" stubs

**Pass.**

The proposal lands all five child component updates in the same scope:

- Modified files (lines 156-159) names three TSX files:
  - `ApplicationDetailRoute.tsx` — which co-locates
    `ApplicationMetadataPanel`, `ApplicationResponsesPanel`, and
    `ApplicationTranscriptList` (verified at lines 110-185 of the route
    source), so all three of those children are touched in this file.
  - `ApplicationMessageComposer.tsx`.
  - `ApplicationTransitionActions.tsx`.
- Substrate (lines 178-184) names every read-site change required.
- Q2 (lines 122-130) enumerates the specific call sites per child:

  > - metadata rows use `props.application().state`,
  >   `props.application().version`, and related fields;
  > - responses use `Object.entries(props.application().responses)`;
  > - transcript list uses `<For each={props.entries()}>`;
  > - composer posts with `applicationId: props.applicationId()`;
  > - transition actions compute valid actions, application id, and
  >   expected version from `props.application()`.

Cross-checked against current sources:

- `ApplicationDetailRoute.tsx:111-120` (metadata `rows()` lambda) reads
  `props.application.state`, `.owner_id`, `.applicant_id`,
  `.target_scope`, `.submitted_at`, `.queued_at`, `.claimed_at`,
  `.updated_at` — all flipping to `props.application().…`.
- `ApplicationDetailRoute.tsx:126` reads `props.application.version` —
  flipping to `props.application().version`.
- `ApplicationDetailRoute.tsx:145` calls
  `Object.entries(props.application.responses)` — flipping to
  `Object.entries(props.application().responses)`.
- `ApplicationDetailRoute.tsx:177` uses `<For each={props.entries}>` —
  flipping to `<For each={props.entries()}>`.
- `ApplicationMessageComposer.tsx:54` reads `props.applicationId` in the
  POST payload — flipping to `props.applicationId()`.
- `ApplicationTransitionActions.tsx:81-82` reads `props.application.id`
  and `props.application.version` for `transitionOfficerApplication(...)`
  — flipping to `props.application().id`, `props.application().version`.
- `ApplicationTransitionActions.tsx:103` reads
  `props.application.state` for `validOfficerTransitionActions(...)` —
  flipping to `props.application().state`.

Every read site that the type flip would break is named in the proposal,
so there is no hidden "I'll fix this child in a follow-up" stub. The
implementer cannot ship the prop type change without also fixing the
read sites because TS will fail; and the proposal's enumeration matches
what TS would surface.

Anti-scope (lines 232-244) is *bounding*, not *deferring*:

> Do NOT modify the compat shim `services/web/src/solid-compat/solid.ts`.
> Do NOT modify the API or transcripts service.
> Do NOT change the bridge endpoints.
> Do NOT add compatibility shims, feature flags, alternate component
> paths, or test-only setters.
> Do NOT change transcript serialization, message append payloads,
> transition contracts, or authorization behavior.

Those rule out widening the fix into the API, bridge, or compat shim —
not parking child internals. The compat-shim exclusion is consistent
with RCA section 6 (`research/36-bug-10-transcript-reactivity-rca.md`
lines 173-189), which proves the shim is a direct alias of Solid's `For`
and `Show` and is not implicated.

Diff budget (lines 246-254) is:

> three source files and one new test file, roughly 120-220 changed
> lines total

Across three TSX files (route + composer + transition), 120-220 lines
covers prop type rewrites, the route-level `Show` boundary fix, and the
five children's read-site updates — that is consistent with all of the
work being in one bundle. A budget that left children for later would
be much smaller (just the route + the prop type + maybe one child) and
would call out a follow-up file; this one does not.

The proposal's own framing in section 1 ("The same stale-capture pattern
also freezes other props derived from `read`, including metadata,
responses, and transition action visibility, because those components
receive the initially captured `read` object" — lines 49-53) makes
clear that the four non-transcript children are part of the same defect
class, so addressing them now (rather than as a follow-up) is the
correct scope: the optional metadata/transition assertion in TG-2 even
*tests* this directly.

## Findings worth carrying into implementation

Not blockers — verdict is LOW — but the implementation phase should
preserve:

1. **Both signals must be co-gated by one `Show`, not two.** The Q1
   pattern at lines 70-73 keeps the gate on
   `canReview() && application() !== null && transcript() !== null`.
   A subtle shortcut would be splitting into nested `Show`s
   (`<Show when={application()}>{<Show when={transcript()}>...`),
   which seems equivalent but would let the inner subtree render with a
   stale `transcript()` momentarily during a refresh that nulls and
   re-sets transcript while application stays truthy. The current
   `loadDetail` at `ApplicationDetailRoute.tsx:202-219` does
   `setApplication(null); setTranscript(null);` inside the catch path —
   if the gate were split, an error followed by a successful retry
   could briefly mount the subtree with the *old* transcript while the
   new application is truthy. Keep the gate as one composite predicate.

2. **`responses()` memo must wrap the accessor read, not be replaced
   by a one-shot.** `ApplicationResponsesPanel` currently has
   `const responses = () => Object.entries(props.application.responses)`
   at `ApplicationDetailRoute.tsx:145`. After the type flip this must
   become `const responses = () => Object.entries(props.application().responses)`
   — keep the lambda. A shortcut `const responses = Object.entries(props.application().responses);`
   at the top of the component would re-introduce the same one-time
   snapshot pattern at the child level.

3. **`metadata.rows()` lambda likewise must keep its `() => […]`
   wrapper.** `ApplicationDetailRoute.tsx:111-120` builds the row array
   inside an accessor function. After the flip, every row entry that
   reads `props.application.…` becomes `props.application().…` — but
   the outer `const rows = () => […]` lambda must stay. Hoisting it to
   `const rows = […]` (computed once at component setup) would
   reintroduce the bug.

4. **`<For each={props.entries()}>` — call the accessor inside the JSX
   binding, do not double-wrap.** Solid's `For` accepts both an array
   and a function; with `props.entries: () => Entry[]`, the binding
   `<For each={props.entries()}>` reads the entries inside the JSX
   getter that Solid tracks per-render. A shortcut
   `<For each={() => props.entries()}>` (extra wrapping) would still
   work but is confusing and signals that the implementer didn't fully
   internalize the boundary; a worse shortcut
   `const entries = props.entries(); <For each={entries}>` would
   re-introduce the defect at the local scope.

5. **`data-application-id={application()!.id}`, not a captured local.**
   Lines 174-176 of the proposal pin this. The current code at
   `ApplicationDetailRoute.tsx:332` reads `data-application-id={read.id}`
   where `read` is the destructured stale snapshot. After the fix this
   must read directly through the signal, not through `read().id`
   captured into a local at the top of the gated `<div>`.

6. **TG-2 should run under the chromium project the existing officer
   tests already use.** The RCA at lines 24-26 invokes
   `npm test -- --grep "test_message_composer_appends_visible_message" --project=chromium`,
   so the new spec must live in `services/web/tests/` (matching the
   existing officer-actions.spec.ts location) and run under the same
   Playwright config so it surfaces in the same e2e gate. Putting it
   under a different config would let the bug regress in CI while the
   new test passes locally.

7. **`ApplicationMessageComposer.applicationId` accessor flip must be
   propagated to `appendOfficerApplicationMessage` payload, not just
   the prop type.** `ApplicationMessageComposer.tsx:54` builds
   `{ applicationId: props.applicationId, ... }` — after the flip this
   must be `{ applicationId: props.applicationId(), ... }`. The TS
   compiler will flag it (because `string` is not assignable to
   `() => string` on the API client side), but the implementer must
   call the accessor, not type-cast around it.

8. **The optional metadata/transition assertion in TG-2 is a useful
   regression boundary; consider promoting it from optional to
   required.** Section 1 (lines 49-53) and "Affected paths" in the
   RCA (lines 240-258) both note that the same stale-capture pattern
   affects metadata/responses/transitions. If the test stays
   transcript-only and a future regression flips back to capturing
   `read` but not `readTranscript`, the gate would miss it. Asserting
   that metadata or transition button visibility also updates after
   `setApplication(...)` adds a cheap bound on the broader defect class
   for the same mocked second response. This is a *strengthening*
   note, not a blocker.

## Verdict

LOW. No shortcuts. The proposal:

- Replaces the stale `Show` destructure with real signal-backed
  accessor lambdas (`() => application()!`, `() => transcript()!`)
  that close over the route's own `createSignal` getters, not local
  snapshots, and explicitly forbids re-snapshotting at any downstream
  boundary.
- Flips the TypeScript prop contracts of all five affected children to
  accessor types (`() => ApplicationRead`, `() => string`,
  `() => ApplicationTranscriptRead["entries"]`), making the read-site
  updates a compiler-enforced obligation rather than a style choice,
  and enumerates every concrete read-site that needs to flip.
- Adds a route-level Playwright spec that triggers `setTranscript` via
  user-visible message-append or refresh handlers (the same paths e2e
  test 19 hits), uses two mocked transcript responses, and asserts the
  rendered DOM under `data-testid="application-transcript"` updates —
  not a synthetic remount, not a test-only `setTranscript` export.
- Bundles all five children's prop type and read-site updates in the
  same proposal, in three named TSX files, with no "fix later" deferral
  and an anti-scope that bounds the perimeter (no API/bridge/compat-shim
  changes) without parking work.

SHORTCUT_DONE: plans/risk/bug-10-shortcut.md
