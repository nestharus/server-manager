# BUG-10 Proposal: Detail route transcript reactivity

## 1. Problem statement

Root cause: `ApplicationDetailRoute` captures `readTranscript` from an
unkeyed `Show` child callback once and passes `readTranscript.entries` to
the transcript list from that stale captured object.

Precise location:

- `services/web/src/features/officer/ApplicationDetailRoute.tsx:318-325`
  computes a truthy object from `application()` and `transcript()`.
- `services/web/src/features/officer/ApplicationDetailRoute.tsx:327-328`
  invokes the `Show` child callback and destructures `detail()` into
  plain constants.
- `services/web/src/features/officer/ApplicationDetailRoute.tsx:350`
  passes `readTranscript.entries` from the captured initial transcript to
  `ApplicationTranscriptList`.

Solid pattern:

Unkeyed `Show` tracks only truthiness for child execution. It supplies an
accessor to the latest `when` value, but child callback execution is not
itself a reactive computation for truthy-to-truthy object changes. Values
read and destructured from that accessor at child creation time become
ordinary stale references unless downstream JSX bindings continue reading
from the accessor or another signal.

After message append, `setTranscript(nextTranscript)` changes the signal,
but the already-mounted detail subtree still points at the first
`readTranscript`. The compiled parent prop getter is
`get entries(){ return n.entries }`, where `n` is the initial transcript,
so the child `<For>` never receives the new entries array.

The bug affects every detail-route update where the outer detail `Show`
stays truthy:

- Message append transcript refresh:
  `handleMessageAppended(...) -> loadTranscript(...) -> setTranscript(...)`.
- Transition transcript refresh:
  `handleTransitioned(...) -> setApplication(nextApplication) -> loadTranscript(...)`.
- Manual detail refresh while already loaded:
  Refresh button -> `loadDetail(...) -> setApplication(...)` and
  `setTranscript(...)`.
- Conflict/stale recovery that calls `loadDetail(..., { preserveNotice: true })`
  after status 409, 412, or 428.

The same stale-capture pattern also freezes other props derived from
`read`, including metadata, responses, and transition action visibility,
because those components receive the initially captured `read` object.

Unaffected:

- Initial detail load from null to truthy.
- API append persistence.
- API transcript read authorization and serialization.
- `ApplicationMessageComposer` submit/clear behavior.
- `ApplicationTranscriptList` and Solid `For` behavior when given a
  genuinely reactive `entries` source.

## 2. Decisions

### Q1. How to wire reactivity?

Pick: **Option a, replace the `Show` destructure with direct
`application()` / `transcript()` reads through accessor props.**

The outer `Show` should remain only a visibility gate:

```tsx
<Show when={canReview() && application() !== null && transcript() !== null}>
  <div class={styles.detailLayout} data-application-id={application()!.id}>
    ...
  </div>
</Show>
```

Inside that gated subtree, do not destructure a `detail()` object into
plain constants. Pass signal-backed accessors to children:

```tsx
const read = () => application()!;
const readTranscript = () => transcript()!;

<ApplicationMetadataPanel application={read} />
<ApplicationResponsesPanel application={read} />
<ApplicationMessageComposer applicationId={() => read().id} ... />
<ApplicationTransitionActions application={read} ... />
<ApplicationTranscriptList entries={() => readTranscript().entries} />
```

The important constraint is that downstream JSX bindings and child
components must call the accessor at render/update time. They must not
convert it back into a local object snapshot at the `Show` boundary.

Rejected:

- Option b, replacing `<Show>` with `<Switch><Match>`: this changes the
  control-flow primitive but still risks relying on truthy control-flow
  semantics instead of fixing the stale data boundary.
- Option c, derived `createMemo` accessors: this would work, but it adds
  an extra abstraction over signals that already exist. The bug is not
  expensive recomputation; it is premature snapshotting.
- Option d, separate `<Show>` wrappers per child: this fragments the
  detail layout and makes each child own the same loaded/reviewable gate.
  It also does not scale if more detail children are added.

### Q2. Children's prop signature change?

Yes. Change the child props that carry application or transcript data to
accessor props.

Required prop changes:

- `ApplicationMetadataPanel`: `application: () => ApplicationRead`
- `ApplicationResponsesPanel`: `application: () => ApplicationRead`
- `ApplicationTranscriptList`: `entries: () => ApplicationTranscriptRead["entries"]`
- `ApplicationMessageComposer`: `applicationId: () => string`
- `ApplicationTransitionActions`: `application: () => ApplicationRead`

Child internals must read through those accessors wherever they currently
read plain props:

- metadata rows use `props.application().state`, `props.application().version`,
  and related fields;
- responses use `Object.entries(props.application().responses)`;
- transcript list uses `<For each={props.entries()}>`;
- composer posts with `applicationId: props.applicationId()`;
- transition actions compute valid actions, application id, and expected
  version from `props.application()`.

`disabled`, callback props, and local component state do not need to be
converted unless the implementation naturally benefits from doing so.
The stale object defect is specifically the application/transcript data
captured by the parent `Show`.

### Q3. Are unit tests needed beyond e2e?

Yes. Add a focused web test in addition to rerunning e2e test 19.

The existing e2e flow proves the full browser path, but the regression is
a local Solid reactivity pattern. A route-level Playwright spec gives a
cleaner gate because it can mock the detail and transcript endpoints,
trigger the route path that calls `setTranscript(...)`, and assert that
the already-mounted transcript DOM updates.

Do not add test-only exports or expose `setTranscript`. Fire the update
through an existing user-visible route action such as message append or
refresh, with the second mocked transcript response containing the new
entry.

## 3. Substrate

### Modified files

- `services/web/src/features/officer/ApplicationDetailRoute.tsx`
- `services/web/src/features/officer/ApplicationMessageComposer.tsx`
- `services/web/src/features/officer/ApplicationTransitionActions.tsx`

### New test file

- `services/web/tests/ApplicationDetailRoute.spec.tsx`

### Implementation shape

In `ApplicationDetailRoute.tsx`:

- remove the object-returning `Show when={... ? { read, readTranscript } : null}`;
- use the `Show` only for `canReview() && application() !== null && transcript() !== null`;
- define `read` and `readTranscript` as local accessor functions in the
  detail route component, or inline equivalent accessor lambdas at each child;
- pass accessors to metadata, responses, transcript, composer, and transition
  children;
- ensure `data-application-id` reads `application()!.id` from a reactive JSX
  binding, not from a destructured snapshot.

In child components:

- update TypeScript prop types from plain data to accessor functions;
- replace reads of `props.application` with `props.application()`;
- replace reads of `props.entries` with `props.entries()`;
- replace reads of `props.applicationId` with `props.applicationId()`;
- preserve current local state, submit/transition behavior, labels,
  test ids, and API client calls.

No compatibility shim changes are part of this proposal.

## 4. Test plan

### TG-1. E2E test 19 reaches the transcript assertion

Run:

```bash
infra/tests/e2e/tests/19-web-ui.sh
```

Expected result: the officer flow now passes through the message append
step, the transcript refresh returns the appended message, and the
message text becomes visible under `data-testid="application-transcript"`.

### TG-2. Focused route reactivity regression

Add `services/web/tests/ApplicationDetailRoute.spec.tsx`.

The spec should:

- mock `/api/me` with an officer principal that has `discord_user_id`;
- mock the application detail endpoint with an initial loaded application;
- mock the transcript endpoint with two responses: first an initial
  state-change-only transcript, then a transcript that includes a new
  message entry;
- mount/navigate to the application detail route;
- assert the initial transcript renders;
- trigger the route code path that calls `setTranscript(...)` by submitting
  a mocked message append or clicking refresh against the second mocked
  transcript response;
- assert the new transcript entry renders inside
  `data-testid="application-transcript"`;
- optionally assert that metadata or transition action visibility updates
  when the second mocked application changes state/version.

This should fail on the stale `Show` destructure and pass after the
accessor-prop change.

## 5. Anti-scope

Do NOT modify the compat shim
`services/web/src/solid-compat/solid.ts`.

Do NOT modify the API or transcripts service.

Do NOT change the bridge endpoints.

Do NOT add compatibility shims, feature flags, alternate component paths,
or test-only setters.

Do NOT change transcript serialization, message append payloads, transition
contracts, or authorization behavior.

## 6. Diff budget

Expected implementation budget: three source files and one new test file,
roughly 120-220 changed lines total.

Allowed changes:

- narrow prop type updates for the five affected detail children;
- replacing the stale `Show` object/destructure with signal-backed accessors;
- internal child read-site updates from plain props to accessor calls;
- one focused Playwright regression spec for route reactivity.

Not expected:

- modifications to `services/web/src/solid-compat/solid.ts`;
- API client changes;
- service/repository changes;
- bridge endpoint changes;
- broad route rewrites;
- CSS or layout changes;
- new frontend dependencies.

PROPOSAL_DONE: proposals/23-bug-10-transcript-reactivity.md
