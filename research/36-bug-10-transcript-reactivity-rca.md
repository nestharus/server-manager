# BUG-10 RCA - Transcript does not re-render after officer message append

## Symptom + state

E2E test 19 now reaches the officer detail flow through message append:

- Public chapter dropdown fetch, select, and submit succeed.
- Officer queue renders the chapter-scoped application.
- Officer claim returns 200.
- Detail page renders `state=claimed`.
- First transcript fetch returns 200.
- Officer sends an `officer_only` message and the POST returns 201.
- The SPA calls `loadTranscript()`.
- The transcript API returns 200 and includes the new message.

The failing assertion waits for the new message text under
`data-testid="application-transcript"` and times out. The DOM remains at
the first loaded transcript.

I reproduced the same failure in the focused mocked component tests:

```bash
cd services/web
npm test -- --grep "test_message_composer_appends_visible_message" --project=chromium
npm test -- --grep "test_message_composer_appends_officer_only_message" --project=chromium
```

Both fail after the mocked second transcript response is available. The
visible-message test proves `transcriptCalls() === 2` before the DOM
assertion fails at `services/web/tests/officer-actions.spec.ts:336-337`.
The DOM still contains only the initial state-change entry.

## Investigation findings

### 1. Route mutation path reaches `setTranscript(...)`

`ApplicationMessageComposer` calls the bridge append endpoint and then
awaits the route callback:

- `services/web/src/features/officer/ApplicationMessageComposer.tsx:53-61`
  posts via `appendOfficerApplicationMessage(...)`, clears local composer
  state, rotates `clientMessageId`, and awaits `props.onMessageAppended`.
- `services/web/src/features/officer/ApplicationDetailRoute.tsx:229-232`
  handles that callback by clearing `notice` and awaiting
  `loadTranscript(applicationId())`.
- `services/web/src/features/officer/ApplicationDetailRoute.tsx:221-224`
  fetches `fetchOfficerApplicationTranscript(id)` and calls
  `setTranscript(...)`.
- `services/web/src/api/client.ts:388-392` fetches
  `/api/web/officer/applications/{id}/transcript`.

The local component test supplies a second transcript object with a new
`entries` array at `services/web/tests/officer-actions.spec.ts:151-166`
and verifies two transcript calls before the rendered text assertion.
That isolates the failure to client reactivity after `setTranscript(...)`,
not API persistence, authorization, or message append.

### 2. Parent `<Show>` does not re-run its child callback on truthy-to-truthy updates

The detail body is gated by this unkeyed `Show`:

`services/web/src/features/officer/ApplicationDetailRoute.tsx:318-354`

```tsx
<Show
  when={(() => {
    const read = application();
    const readTranscript = transcript();
    return canReview() && read !== null && readTranscript !== null
      ? { read, readTranscript }
      : null;
  })()}
>
  {(detail) => {
    const { read, readTranscript } = detail();
    return (
      ...
      <ApplicationTranscriptList entries={readTranscript.entries} />
    );
  }}
</Show>
```

Solid 2 beta's installed `Show` implementation confirms this behavior:

- `services/web/node_modules/solid-js/dist/solid.js:771-788` creates
  `conditionValue = createMemo(() => props.when, undefined)`.
- For unkeyed `Show`, it wraps that in `condition = createMemo(conditionValue, { equals: (a, b) => !a === !b })`.
- That equality intentionally treats all truthy values as equivalent for
  control-flow re-execution.
- The child function is invoked inside `untrack(...)` only when the
  boolean condition changes.

Therefore returning a fresh object from `when` does not cause the child
callback to re-run while the route remains reviewable and both
`application()` and `transcript()` remain non-null. The new object
reference is ignored for the unkeyed control-flow decision.

### 3. The destructure captures stale values

Inside the `Show` child callback,
`const { read, readTranscript } = detail();` at
`services/web/src/features/officer/ApplicationDetailRoute.tsx:328`
captures the current values once, at the null-to-truthy transition.

Solid passes `detail` as an accessor to the latest `conditionValue`, but
this route does not call `detail()` from a reactive binding. It
immediately destructures into plain constants. When `setTranscript(...)`
later stores a new transcript object, those constants still point at the
initial `ApplicationRead` and initial `ApplicationTranscriptRead`.

A minimal Solid 2 beta reproduction showed the same behavior: a child
callback under unkeyed `Show` ran once, and an inner closure that captured
`const { readTranscript } = detail()` continued to read the initial
entries after the transcript signal changed.

### 4. The transcript list receives a getter, but the getter closes over the stale object

The compiled bundle confirms the stale capture:

```js
children:e=>{
  let{read:t,readTranscript:n}=e();
  ...
  L(e,A(ET,{get entries(){return n.entries}}),null)
}
```

Here `n` is the initial `readTranscript`. The prop passed to
`ApplicationTranscriptList` is syntactically a getter, but it reads
`n.entries` from a plain captured object, not from `transcript()`.

`ApplicationTranscriptList` itself compiles to:

```js
function ET(e){
  ...
  A(Mr,{get each(){return e.entries}, ...})
}
```

That preserves a reactive prop boundary if the parent getter reads a
reactive source. In this case it does not, so the child cannot observe the
new transcript.

### 5. `<For each={props.entries}>` is not the primary defect

The source list is:

`services/web/src/features/officer/ApplicationDetailRoute.tsx:167-181`

```tsx
<For each={props.entries} fallback={...}>
  {(entry) => <TranscriptEntryView entry={entry()} />}
</For>
```

Solid's `For` implementation is:

- `services/web/node_modules/solid-js/dist/solid.js:755-763`
  returns `mapArray(() => props.each, props.children, options)`.
- `services/web/node_modules/@solidjs/signals/dist/types/map.d.ts:3-14`
  documents `mapArray` as reactively tracking changes to the list
  accessor.

The child list would re-iterate if `props.entries` changed through a
reactive getter. It does not re-iterate here because the parent passes a
getter over the stale captured `readTranscript`, so `props.entries`
continues returning the first array.

### 6. The compatibility shim did not change `For`/`Show` semantics

The current shim aliases `solid-js` to
`services/web/src/solid-compat/solid.ts` via
`services/web/vite.config.ts:11-24`.

The relevant shim exports are direct runtime exports:

- `services/web/src/solid-compat/solid.ts:13` exports
  `For = solid.For`.
- `services/web/src/solid-compat/solid.ts:14` exports
  `Show = solid.Show`.

BUG-1 changed the compat shim around Solid 2 beta legacy effects,
`createContext`, and direct `createSignal` export, but `For` and `Show`
remain direct aliases of the installed Solid implementation. The shim is
not the root cause of the stale transcript. It matters only because the
runtime behavior is the Solid 2 beta unkeyed `Show` behavior described
above.

### 7. Past slice comparison

`INIT-133B-iii` introduced the current route shape. The historical source
at commit `78e6d63` has the same `Show` block and the same destructure at
the same logical lines:

- `git show 78e6d63:services/web/src/features/officer/ApplicationDetailRoute.tsx`
  shows the unkeyed `Show` at lines 318-354.
- The same commit added `services/web/tests/officer-actions.spec.ts`.

The route-level stale capture was therefore present in the slice source.
I did not find a later change to `ApplicationDetailRoute.tsx` that
introduced this exact pattern after BL-019D-beta-iii. If a past e2e run
appeared green for this flow, the difference was not in this route source;
the likely difference was the built artifact/runtime being tested or the
assertion path exercised during that run.

## Root cause

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

## Affected paths

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

## Intervention candidates, not fixes

This RCA is not proposing a fix. Candidate intervention classes for a
separate proposal/code phase:

- Keep the detail subtree mounted but make transcript/application props
  read from reactive accessors rather than destructured one-time values.
- Change the control-flow boundary so truthy-to-truthy detail changes
  recreate or update the subtree intentionally.
- Split the authorization/load gate from the mutable application and
  transcript values so the gate controls visibility while child props
  remain signal-backed.
- Add a component-level regression that asserts transcript DOM updates
  after the second transcript fetch; the existing visible/officer-only
  mocked tests already encode this contract and currently fail.
