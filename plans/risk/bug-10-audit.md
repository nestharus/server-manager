# Risk audit — BUG-10 detail route transcript reactivity

Inputs:
- Proposal: `proposals/23-bug-10-transcript-reactivity.md`
- RCA: `research/36-bug-10-transcript-reactivity-rca.md`
- Substrate:
  - `services/web/src/features/officer/ApplicationDetailRoute.tsx`
    (stale `Show` destructure at lines 318-354; in-file children
    `ApplicationMetadataPanel` lines 110-142,
    `ApplicationResponsesPanel` lines 144-165,
    `ApplicationTranscriptList` lines 167-185).
  - `services/web/src/features/officer/ApplicationMessageComposer.tsx`
    (reads `props.applicationId` at line 54).
  - `services/web/src/features/officer/ApplicationTransitionActions.tsx`
    (reads `props.application.state/id/version` at lines 81-82, 103).
  - New test file: `services/web/tests/ApplicationDetailRoute.spec.tsx`.

## Verdict

**Risk level: LOW.** APPROVED — proceed to implementation.

The proposal directly attacks the RCA's named root cause. The RCA
(lines 209-223) identifies that `ApplicationDetailRoute` returns a
fresh `{ read, readTranscript }` object from an unkeyed `<Show>`
predicate, which re-renders only on truthy/falsy flip (Solid 2 beta
unkeyed `Show` uses `equals: (a, b) => !a === !b`,
`services/web/node_modules/solid-js/dist/solid.js:771-788`,
RCA §2 lines 84-91), then destructures `detail()` into plain `read`
and `readTranscript` constants and passes `readTranscript.entries`
through a getter that closes over the stale object (RCA §3-§4
lines 99-145; compiled `get entries(){ return n.entries }` proves
the closure). The proposal's Q1 (lines 64-94) replaces the
object-returning `when` with a pure boolean visibility gate
(`canReview() && application() !== null && transcript() !== null`)
and replaces the destructured plain values with signal-backed
accessor functions (`read = () => application()!`,
`readTranscript = () => transcript()!`) that downstream JSX
bindings call at render time. Q2 (lines 109-136) propagates that
accessor discipline into the five affected child components with
matching prop signature changes and explicit internal read-site
updates, so no subtree path remains on the stale-destructure
pattern. Q3 (lines 138-150) adds a focused Playwright regression
without test-only setters or shim changes. §5 anti-scope (lines
228-240) correctly forbids touching the compat shim, API service,
transcript serialization, bridge endpoints, or alternate component
paths — all of which the RCA already cleared as not load-bearing.

## Findings

### F-1 Fix targets the RCA's exact root cause — PASS

RCA §"Root cause" (lines 209-223) names three lines as the failure
locus:
- `ApplicationDetailRoute.tsx:318-325` (object-returning `when`),
- `ApplicationDetailRoute.tsx:327-328` (destructure of `detail()`
  into plain `read` / `readTranscript`),
- `ApplicationDetailRoute.tsx:350` (`entries={readTranscript.entries}`
  passing a getter that closes over the stale object).

I confirmed those three locations are present in the current
substrate at exactly those line numbers (see source file dump).

Proposal §Q1 (lines 70-94) eliminates all three:
1. The object-returning `when` is replaced with the pure boolean
   `canReview() && application() !== null && transcript() !== null`,
   so there is no transient object whose identity is being elided
   by `Show`'s `!a === !b` equality.
2. The destructure is removed; `read` and `readTranscript` are
   accessor functions defined in the route component scope, not
   plain constants destructured inside the `Show` child callback.
3. `<ApplicationTranscriptList entries={() => readTranscript().entries} />`
   replaces `entries={readTranscript.entries}`. Solid compiles the
   inline arrow JSX prop into a getter that calls
   `readTranscript()` at read time, which re-reads `transcript()`
   reactively, so the prop getter no longer closes over a stale
   `n` object. The "compiled getter closes over `n`" defect
   diagnosed in RCA §4 lines 119-133 is removed at the source.

Q1's rejection list (lines 96-106) is well-reasoned: switching to
`<Switch><Match>` would still depend on truthy control-flow
semantics (rejection b); `createMemo` adds an unnecessary layer
when the issue is premature snapshotting, not recomputation cost
(rejection c); per-child `<Show>` wrappers fragment the layout and
each child re-implements the same gate (rejection d). Option a is
the minimum surface that severs the stale-capture path. PASS.

### F-2 Replaces destructured plain values with accessors throughout subtree — PASS

The proposal §1 final paragraph (lines 49-51) explicitly notes
that the same stale-capture freezes metadata, responses, and
transition action visibility, so a fix that converts only
`entries` would leave correctness gaps for transition state
changes, version-bumped optimistic concurrency assertions, and
metadata refresh. §Q1 (lines 84-89) and §3 implementation shape
(lines 168-184) cover every subtree binding:

| Subtree binding | Pre-fix (stale) | Post-fix (accessor) |
|---|---|---|
| `data-application-id` | `read.id` (line 332) | `application()!.id` from reactive JSX binding (§3 line 175) |
| `ApplicationMetadataPanel.application` | `read` (line 335) | `read` accessor (§Q1 line 85) |
| `ApplicationResponsesPanel.application` | `read` (line 336) | `read` accessor (§Q1 line 86) |
| `ApplicationMessageComposer.applicationId` | `read.id` (line 338) | `() => read().id` accessor (§Q1 line 87) |
| `ApplicationTransitionActions.application` | `read` (line 344) | `read` accessor (§Q1 line 88) |
| `ApplicationTranscriptList.entries` | `readTranscript.entries` (line 350) | `() => readTranscript().entries` accessor (§Q1 line 89) |

All six subtree bindings — five children plus the
`data-application-id` data attribute — switch to accessor-backed
JSX bindings. No subtree binding remains on the destructured
snapshot. PASS.

### F-3 Children's prop type changes are consistent (no half-converted) — PASS

§Q2 (lines 109-136) lists every child prop type change with the
exact accessor signature and pairs each with the corresponding
internal read-site update:

- `ApplicationMetadataPanel.application: () => ApplicationRead`
  → metadata rows read `props.application().state`,
  `.version`, etc. The existing `rows` (substrate lines 111-120)
  reads `props.application.state`/etc.; converting to
  `props.application().state` keeps the closure inside `() =>
  [...]` and stays reactive because the array literal is read
  inside `<For each={rows()}>` (substrate line 129).
- `ApplicationResponsesPanel.application: () => ApplicationRead`
  → `Object.entries(props.application().responses)`. Same shape
  as above; the existing `responses = () =>
  Object.entries(props.application.responses)` (substrate line
  145) becomes `responses = () =>
  Object.entries(props.application().responses)`.
- `ApplicationTranscriptList.entries: () => ApplicationTranscriptRead["entries"]`
  → `<For each={props.entries()}>`. Solid compiles the
  `props.entries()` prop expression into a getter that re-reads
  the accessor at each `mapArray` tick (`solid-js/dist/solid.js:
  755-763` per RCA §5 line 161). Reactive.
- `ApplicationMessageComposer.applicationId: () => string` →
  `props.applicationId()` is read inside `submit()` (substrate
  lines 53-58); the read happens at click time, so it picks up
  the latest value. No reactive scope is needed because the
  read is event-driven, not subscription-driven.
- `ApplicationTransitionActions.application: () => ApplicationRead`
  → `validOfficerTransitionActions(props.application().state)`
  inside `<For each=...>` (substrate line 103) is a JSX getter
  context, so the `props.application()` call is reactively
  tracked. The `props.application().id` and `.version` reads
  inside `submit()` (substrate lines 81-82) happen at click time
  on the latest value. Both call sites correct.

§Q2's explicit non-conversions are correct: `disabled?: boolean`,
the four callback props (`onMessageAppended`, `onError`,
`onTransitioned`), and per-component local state (`bodyMarkdown`,
`visibility`, `clientMessageId`, `submitting`, `activeAction`,
`fieldValue`, `forbiddenActions`) are not subject to the stale
`Show`-destructure pathology. They are either invariant
references (callbacks come from `ApplicationDetailRoute`'s scope
and capture signals via closure) or owned by the child's own
`createSignal` calls. Converting them adds churn without fixing
anything. PASS.

A consistency note (non-blocking): for the message-composer
`applicationId` and the transition-actions callsite, ensure the
implementer changes BOTH the prop signature AND every read site
in the same patch. Half-converting (e.g. updating the type
annotation but leaving `props.applicationId` un-called) would
type-check the wrong way and silently regress the stale capture
in a different shape. §Q2 lines 122-130 is explicit about every
read site, so the proposal already pre-empts this.

### F-4 Initial null→truthy load still works — PASS

`Show when={canReview() && application() !== null && transcript() !== null}`
evaluates to `false` until both signals become non-null. The
substrate's existing `loadDetail` path (lines 202-219) sets both
signals via `Promise.all([fetchOfficerApplication(id),
fetchOfficerApplicationTranscript(id)])` then synchronously calls
`setApplication(nextApplication)` and `setTranscript(nextTranscript)`
back-to-back inside the same microtask. Solid 2 beta will batch
these signal writes, so the boolean predicate flips from `false` to
`true` exactly once per load. Unkeyed `Show` re-runs the child
callback on `false`→`true` (`!false === !true` is false, so the
equality breaks). The new accessor-defining setup
(`const read = () => application()!`, `const readTranscript = () =>
transcript()!`) runs once at mount; both accessors return non-null
because the `Show` gate ensures it.

The non-null assertion (`!`) on `application()!` and `transcript()!`
inside the accessors is safe because the `Show` predicate already
ruled out null. If a future signal update transiently sets either
to null, `Show` flips to false and the subtree unmounts before any
accessor read can observe the null — Solid renders flow-control
boundary changes synchronously relative to signal updates, so the
unmount precedes any descendant rerun.

The principal-loading branches (substrate lines 293-304) are
separate `<Show>` blocks gated on `principalStatus()` and
`principal()?.groups`/`discord_user_id`. They remain unchanged.
The `notice` and `loading` `<Show>` gates (substrate lines 306-316)
also remain unchanged. None of them participate in the
stale-destructure pattern. PASS.

### F-5 Conflict/stale recovery via loadDetail/preserveNotice paths still re-render — PASS

Three update paths must still produce a re-render after the fix:

**Path 1 — message append** (substrate lines 229-232):
`handleMessageAppended` → `loadTranscript(applicationId())` →
`setTranscript(...)`. Only `transcript()` updates;
`application()` stays the same. `Show` stays truthy across the
update. With the fix, `<ApplicationTranscriptList entries={() =>
readTranscript().entries} />` re-reads `transcript()` via the
getter and `mapArray` diffs against the new entries array. The
new message renders. The existing failing
`test_message_composer_appends_visible_message` /
`test_message_composer_appends_officer_only_message` tests
(`services/web/tests/officer-actions.spec.ts:336-337`, RCA §1
lines 21-32) become the regression gate.

**Path 2 — transitioned** (substrate lines 234-238):
`handleTransitioned` → `setApplication(nextApplication)` then
`loadTranscript()` → `setTranscript(...)`. Both signals update.
`Show` stays truthy. Metadata, responses, transition actions, and
transcript all re-read their accessor props. State, version, and
valid-action set update reactively.

**Path 3 — manual refresh** (substrate lines 282-289 + 202-219):
Refresh button → `loadDetail(applicationId())`. On success,
`setApplication` + `setTranscript` both fire. `Show` stays truthy
unless the load fails. Subtree DOM updates via accessor reads.

**Path 4 — conflict/stale recovery** (substrate lines 240-245 +
202-219):
`handleActionError(message, 409|412|428)` → `loadDetail(...,
{ preserveNotice: true })`. On success, both signals update;
`Show` stays truthy; subtree re-reads accessor props. The
`preserveNotice` flag only suppresses the `setNotice(null)` at
line 204 so the user-visible notice persists across the recovery
load — it has no interaction with the accessor pattern. On error
inside the recovery `loadDetail`, the catch (substrate lines
212-215) sets both signals to null, `Show` flips to false, the
subtree unmounts, and the notice persists. When a subsequent
successful load runs, the subtree remounts cleanly via Path 3
semantics.

All four paths yield a fresh DOM render. The proposal §1 lines
35-46 already enumerates these four paths as the affected scope,
and the fix structure resolves all four uniformly through accessor
re-reads. PASS.

## Observations (non-blocking)

1. **`data-application-id` syntax landmine.** Implementer must
   write `data-application-id={read().id}` (or
   `data-application-id={application()!.id}`), NOT
   `data-application-id={read.id}`. Because `read` is now a
   function, `read.id` would render the function object's `.id`
   property (undefined), silently breaking the e2e selector
   `[data-application-id="<id>"]` that BUG-7's queue and detail
   paths rely on. §3 line 175 captures the requirement as "from a
   reactive JSX binding, not from a destructured snapshot," but
   does not show the literal syntax. Calling this out explicitly
   for implementer hygiene.

2. **Avoid recreating accessor lambdas inside the `Show` child
   callback.** §Q1 lines 83-89 defines `read` and `readTranscript`
   inside the `Show` child or in the route scope. Either is
   correct. Defining them at route scope is slightly cleaner
   because the `Show` child callback now contains only JSX. An
   in-line arrow created on each child invocation
   (`<ApplicationMessageComposer applicationId={() => read().id}
   ... />`) is fine — the arrow's stable identity inside the
   subtree's lifetime is irrelevant since Solid only tracks the
   prop's getter, not the arrow's identity.

3. **Solid 2 beta `mapArray` tracking.** RCA §5 line 161
   references `mapArray(() => props.each, props.children, options)`
   as the reactive list iterator. The post-fix
   `<For each={props.entries()}>` compiles to a JSX prop getter
   that calls the accessor once per `mapArray` tick. This is the
   standard Solid pattern and is exercised elsewhere in this
   codebase (`ApplicationMetadataPanel.rows`,
   `ApplicationResponsesPanel.responses`,
   `ApplicationTransitionActions.validOfficerTransitionActions`).
   No new reactive primitive is being introduced.

4. **`!` non-null assertions are constrained by the `Show` gate.**
   `application()!` and `transcript()!` inside `read` and
   `readTranscript` accessors are sound because the `Show`
   predicate gates the subtree on both being non-null. If the
   implementer prefers to avoid `!`, an early-return pattern at
   the accessor level
   (`const read = () => { const a = application(); if (a === null)
   throw new Error("read called outside Show gate"); return a; }`)
   is unnecessary noise — the `Show` boundary is the right place
   for the invariant.

5. **Transition actions: state-driven `<For>` reactivity is
   already correct.** Substrate line 103
   (`<For each={validOfficerTransitionActions(props.application.state)}>`)
   reads `props.application.state` inside a JSX prop expression,
   which Solid compiles into a getter. Today, that getter still
   closes over the stale destructured `read.state`. Post-fix, it
   reads `props.application().state`, which tracks the
   route-level `application()` signal through the accessor chain.
   No change to `For` semantics; only the source of `.state`
   changes from a stale snapshot to a live accessor.

6. **Test substrate alignment.** The new
   `services/web/tests/ApplicationDetailRoute.spec.tsx` (§Q3
   lines 138-150, §4 TG-2 lines 204-225) mirrors the existing
   `services/web/tests/officer-actions.spec.ts` shape that already
   contains the failing component tests
   (RCA §1 lines 21-32). The proposal's discipline against
   test-only setters and `setTranscript` exposure (§Q3 line 147)
   is correct: firing the second transcript fetch through message
   append or refresh exercises the same route code path that
   production uses, so the regression gate is faithful to the
   real path.

7. **Diff budget realism.** §6 budget of 120-220 lines across
   three source files plus one new test file is consistent with
   the change shape: three children's prop signatures change with
   matching internal read-site rewrites (~10-30 lines each), the
   route's `<Show>` block rewrites (~15-30 lines), and a focused
   Playwright spec (~50-80 lines). No surprises.

## Acceptance check (proposed)

When implementation lands, all of the following must hold:

- `services/web/src/features/officer/ApplicationDetailRoute.tsx`
  no longer returns an object from the `<Show when=...>`
  predicate; the predicate is a pure boolean
  `canReview() && application() !== null && transcript() !== null`.
- The detail subtree's `data-application-id`,
  `ApplicationMetadataPanel.application`,
  `ApplicationResponsesPanel.application`,
  `ApplicationMessageComposer.applicationId`,
  `ApplicationTransitionActions.application`, and
  `ApplicationTranscriptList.entries` bindings all read from
  accessor functions, not destructured plain values.
- `ApplicationMetadataPanel.application`,
  `ApplicationResponsesPanel.application`, and
  `ApplicationTranscriptList.entries` prop signatures change to
  `() => ApplicationRead` / `() => ApplicationTranscriptRead["entries"]`,
  with every internal read site updated to call the accessor.
- `ApplicationMessageComposer.applicationId` prop signature changes
  to `() => string`, with the `submit` handler updated to call
  `props.applicationId()`.
- `ApplicationTransitionActions.application` prop signature
  changes to `() => ApplicationRead`, with all reads
  (`<For each=...>` predicate, `submit` `id`/`version`) updated
  to call `props.application()`.
- No edits in `services/web/src/solid-compat/solid.ts`,
  `services/api/`, the bridge endpoints, transcript
  serialization, message-append payloads, transition contracts,
  or authorization paths.
- No test-only exports from `ApplicationDetailRoute.tsx` and no
  exposure of `setTranscript`/`setApplication`.
- `services/web/tests/ApplicationDetailRoute.spec.tsx` exists and
  asserts that after a route-driven second transcript fetch
  (message append or refresh), the new transcript entry renders
  inside `data-testid="application-transcript"`. The test
  must fail on the pre-fix substrate and pass post-fix.
- TG-1: `infra/tests/e2e/tests/19-web-ui.sh` passes through the
  message-append assertion, with the appended message text
  visible under `data-testid="application-transcript"`.
- TG-2: `services/web/tests/ApplicationDetailRoute.spec.tsx`
  passes locally (`cd services/web && npm test --
  --grep "ApplicationDetailRoute"` or equivalent project-scoped
  invocation).
- The previously failing focused tests
  (`test_message_composer_appends_visible_message`,
  `test_message_composer_appends_officer_only_message`) at
  `services/web/tests/officer-actions.spec.ts:336-337` now pass
  without modification, confirming the regression contract is
  fulfilled by the route-level fix.
- Diff stays within §6 budget (~120-220 lines across three
  source files plus one new test file).

AUDIT_DONE: plans/risk/bug-10-audit.md
