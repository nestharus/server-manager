# Risk audit — BUG-1 Solid compat shim legacy effect crash

Inputs:
- Proposal: `proposals/18-bug-1-solid-compat-shim.md`
- RCA: `research/30-bug-1-admin-route-rca.md`
- Code under repair: `services/web/src/solid-compat/solid.ts`

## Verdict

APPROVED — proceed to implementation.

The proposal addresses the named root cause, preserves the surviving native
two-argument paths, and does not introduce surprising reactive-graph side
effects. Two minor clarifications and one observation are recorded below; none
block implementation.

## Findings

### F-1 Root-cause coverage — PASS

The RCA names the root cause as `createLegacyEffect` calling raw
`solid.createEffect` with one argument
(`services/web/src/solid-compat/solid.ts:77`), which then crashes inside
`@solidjs/signals/dist/prod.js:1932` at `effect(e, t.effect || t, t.error, ...)`
because `t` is `undefined`.

The proposal's Q1 lock matches this directly: `createLegacyEffect` will call
`nativeCreateEffect(runner, legacyEffectHandler)` with a function-typed handler.
A function `t` makes `t.effect` resolve to `undefined`, then the `||` falls back
to `t` itself, satisfying the `effect(e, t.effect || t, t.error, ...)` contract.
Confirmed against the live signals source at
`services/web/node_modules/@solidjs/signals/dist/prod.js:1931-1932`.

### F-2 Two-argument shim callers — PASS

Search of `services/web/src` for two-argument `createEffect(...)` /
`createRenderEffect(...)` calls turns up only the shim's internal native
forwarding lines (`solid-compat/solid.ts:110, 126`); no project-side caller
uses the two-argument forms. The TanStack Solid Query bundles
(`@tanstack/solid-query/build/index.js`) call all of `createRenderEffect`,
`createComputed`, and `createEffect` with a single function argument
(`build/index.js:20, 215, 231, 256, 307, 310, 358, 410, 424, 444, 500`) and
never pass a second argument.

The proposal preserves the native-handler branch verbatim:
`isNativeEffectHandler(initialOrEffect)` discriminates, falls to
`solid.createEffect(effect, initialOrEffect, options)` and
`solid.createRenderEffect(effect, initialOrEffect, options)` for native
two/three-arg calls. No regression risk on those paths.

Note on the audit-prompt phrasing: the "6+ existing two-argument shim callers"
appears to refer to the six shim entry points enumerated in proposal Q3
(`createEffect`, `createComputed`, `createRenderEffect`, `onMount`,
`createResource`, `createSignal`), not to project-side two-argument call
sites. No such call sites exist today.

### F-3 Legacy "previous result" semantics — PASS, with clarification

The audit-prompt phrasing "the `legacyEffectHandler` accepts the computed value
AND stores it for the next run" does not literally match the proposal's design.
The proposal stores in the **runner closure**, not in the handler:

- `legacyEffectHandler` "intentionally accepts the computed value and returns
  nothing."
- The runner "passes `undefined` to the first run when no initial value is
  supplied, passes the previous result on later runs, and stores the latest
  result for the next run" — this is the existing closure pattern at
  `solid-compat/solid.ts:74-82` (`previous = result; hasPrevious = true;`).

This is correct. Solid 2 beta's effect model is `runner(prev) → newValue` then
`handler(newValue)`; legacy "previous" semantics are preserved by the runner's
closure regardless of what the handler does. The handler does not need to
store. The audit-prompt phrasing should be read as "previous-result semantics
are preserved across the runner+handler pair" rather than "the handler itself
performs storage."

### F-4 Coverage of createComputed / createRenderEffect / createResource / onMount — PASS

- `createComputed`: aliased via `export const createComputed = createEffect`
  (`solid-compat/solid.ts:113`) — inherits the fix automatically.
- `createRenderEffect`: proposal explicitly routes one-argument and
  legacy-initial-value calls through the fixed legacy helper, parameterized
  with `solid.createRenderEffect` so render-effect scheduling stays bound to
  the native render-effect primitive (Q2 lock). Two-argument native callers
  keep the existing `solid.createRenderEffect(effect, initialOrEffect, options)`
  delegation.
- `createResource`: proposal changes the internal raw
  `solid.createEffect(() => { ... })` at `solid-compat/solid.ts:151` to route
  through the fixed legacy helper — this is necessary because that internal
  effect is a one-arg call and would otherwise still crash.
- `onMount`: implemented as `createEffect(() => { callback(); })` at
  `solid-compat/solid.ts:68-71`, calling the *shim's* exported `createEffect`
  rather than `solid.createEffect`, so it inherits the fix transitively.

All four legacy effect surfaces pass through the fixed path.

### F-5 Negative-space audit (unaffected APIs) — PASS

Spot-checked against the live signals source:

- `createSignal`: signals/dist/prod.js:1918-1925 implements
  `createSignal(e, t)` as either `computed(e, t)` (when `e` is a function) or
  `signal(e, t)`. Neither call dereferences `t.effect`. Safe with omitted
  second argument. Proposal correctly excludes from the fix.
- `For`, `Show`: re-exported from `solid-js/dist/solid.js` via
  `export * from "../../node_modules/solid-js/dist/solid.js"` at
  `solid-compat/solid.ts:4`. Not local wrappers; no shim arity bug.
- `Index`: delegates to `solid.createComponent(solid.For, ...)` at
  `solid-compat/solid.ts:60-65`. No raw effect call.
- `batch`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`,
  `mergeProps`, `splitProps`, `on`: inspection of
  `solid-compat/solid.ts:6-54, 129-144` confirms none of these call raw Solid
  effect primitives. They are pure JS composition helpers or component shims.

The proposal's Q3 audit list is accurate. No spurious changes proposed for
these surfaces.

### F-6 SPA bootstrap chain — DESIGN PASS, runtime verification deferred

The crash chain in the RCA is:
`AppProviders` (`services/web/src/app/providers.tsx:26`) →
`QueryClientProvider` →
`@tanstack/solid-query/build/index.js:20` (`createRenderEffect((unmount) => …)`) →
shim `createRenderEffect` one-arg branch (`solid-compat/solid.ts:120-121`) →
`createLegacyEffect` (`solid-compat/solid.ts:77`) →
raw one-arg `solid.createEffect` →
`@solidjs/signals/dist/prod.js:1932` `t.effect || t` throw.

After the fix, the legacy helper supplies a function-typed handler, so
`t.effect || t` resolves to the handler function and `effect(...)` is invoked
without a TypeError. Bootstrap can proceed past `QueryClientProvider` into
`ThemeRuntime` and `RouterProvider`.

Runtime confirmation is deferred to the proposal's TG-2 (Playwright SPA smoke)
and TG-3 (`infra/tests/e2e/tests/19-web-ui.sh`) test groups, which is correct
for the proposal stage. The Pomerium drift recorded in RCA section 3 and
proposal section 6 remains a separate Bug #5 and is correctly not bundled
into this fix.

### F-7 Reactive-graph side effects — PASS

The handler is described as a function that "accepts the computed value and
returns nothing." It does not:

- Read or subscribe to signals (no implicit reactive subscription).
- Write to signals (no triggered updates).
- Mutate any module-level state.
- Throw, since it has no body that can throw.

In Solid 2 beta, the handler is the "success" arm of the effect's commit
phase (`createEffect(e, t, n)` → `effect(e, t.effect || t, t.error, …)`). A
no-op handler simply discards the runner's return value. The runner itself
remains the source of all reactive reads, so the dependency graph is
identical to today's behavior.

For `createRenderEffect`, signals/dist/prod.js:1934-1935 shows
`effect(e, t, undefined, n)` — `t` is passed straight through. The Q2 lock to
use `solid.createRenderEffect` (rather than `solid.createEffect`) for render
effects keeps render-effect scheduling tied to the native render-effect
primitive, avoiding an accidental phase change for TanStack Query's
`createRenderEffect((unmount) => …)` mount path.

No surprising reactive-graph mutation introduced by the handler.

## Observations (non-blocking)

1. **createEffect's `prev` parameter from Solid 2 beta is ignored.** The
   runner uses closure-based `previous` and ignores whatever Solid 2 passes as
   the runner's argument. This is intentional and matches the existing legacy
   runner; no change needed. Future maintainers should not "simplify" the
   runner to use Solid 2's `prev` argument without verifying Solid 2's exact
   semantics for the first call (where Solid 2 may pass `undefined` while
   legacy expects the configured `initial`).

2. **Diff budget.** Proposal estimates 145–235 lines total (20–35 in
   `solid.ts`, 90–140 in the new spec, optional 35–60 for a separate
   bootstrap spec). Implementation materially larger should re-check
   anti-scope, particularly the prohibitions on bumping package versions,
   monkey-patching node_modules, or adding parallel API surfaces.

3. **Pomerium drift (RCA §3, proposal §6).** Out of scope for BUG-1 and
   correctly carved out as Bug #5. Audit does not assess that drift here.

## Acceptance check (proposed)

When implementation lands, the following must all hold:

- `services/web/src/solid-compat/solid.ts` no longer contains a one-argument
  `solid.createEffect(...)` call (line 77 today, line 151 today).
- `createLegacyEffect` accepts a `nativeCreateEffect` parameter (or equivalent
  internal dispatch) so render effects route through `solid.createRenderEffect`
  and non-render effects route through `solid.createEffect`.
- The native-handler branches at lines 110 and 126 remain untouched.
- TG-1 unit tests assert both "no throw" and an observable side effect for
  every fixed surface.
- TG-2 Playwright smoke renders `#root` non-empty with no
  `Cannot read properties of undefined (reading 'effect')` page error.

AUDIT_DONE: plans/risk/bug-1-audit.md
