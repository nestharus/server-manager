# Proposal 18 - BUG-1: Solid compat shim legacy effect crash

## 1. Problem statement

The root cause is the local Solid 2 compatibility wrapper's legacy effect
path, not route registration, heading text, OAuth timing, or API health.

Specifically:

1. `AppProviders` renders `QueryClientProvider`
   (`services/web/src/app/providers.tsx:26`).
2. `@tanstack/solid-query` calls `createRenderEffect((unmount) => ...)`
   with one argument (`services/web/node_modules/@tanstack/solid-query/build/index.js:20`).
3. The alias routes that call through `services/web/src/solid-compat/solid.ts`.
4. The one-argument `createRenderEffect` path calls `createLegacyEffect`
   (`services/web/src/solid-compat/solid.ts:120-121`).
5. `createLegacyEffect` calls the raw Solid 2 beta `solid.createEffect(...)`
   with one argument (`services/web/src/solid-compat/solid.ts:77`).
6. Solid 2 beta's underlying `@solidjs/signals` implementation dereferences
   the missing second argument as `t.effect`
   (`services/web/node_modules/@solidjs/signals/dist/prod.js:1931-1932`).
7. The thrown `TypeError` aborts SPA bootstrap, leaving `<body>` empty and
   causing `browser-flow.mjs:84` to wait until timeout.

## 2. Decisions

### Q1. Pass an empty options object, pass a no-op handler, or add an `if/else` fork by arity?

Lock: pass a no-op Solid 2 effect handler from the legacy path.

`createLegacyEffect` must never call the raw Solid 2 beta effect primitive with
only the effect function. It should call the selected native effect primitive as
`nativeCreateEffect(runner, legacyEffectHandler)`, where
`legacyEffectHandler` intentionally accepts the computed value and returns
nothing. The runner keeps the current legacy behavior: pass `undefined` to the
first run when no initial value is supplied, pass the previous result on later
runs, and store the latest result for the next run.

Do not pass `{}` as the second argument. In Solid 2 beta,
`@solidjs/signals` reads `t.effect || t`; `{}` avoids the immediate
`t.effect` dereference but then becomes a non-callable handler, which can fail
when the effect is flushed.

Do not add a new top-level arity fork as the fix. The shim already dispatches
one-argument and legacy-initial-value calls into `createLegacyEffect`; the bug
is inside that shared legacy path. Fix that shared path so all legacy effect
wrappers inherit the same behavior.

### Q2. Use Solid 2 beta's new effect API or a different primitive such as `createReaction`?

Lock: use Solid 2 beta's native effect primitives with the required handler;
do not switch to `createReaction`.

For `createEffect`, `createComputed`, `onMount`, and the shim's internal
resource tracking, the legacy path should use Solid 2 beta's
`solid.createEffect(runner, legacyEffectHandler)`. For `createRenderEffect`,
the legacy path should use `solid.createRenderEffect(runner,
legacyEffectHandler)` so render-effect scheduling remains tied to the native
render-effect primitive.

`createReaction` is not a substitute. It returns a trigger function and defers
work until the trigger is called. That would change the semantics of
`createEffect(fn)`, `createRenderEffect(fn)`, and TanStack Query's provider
bootstrap path.

Two-argument native Solid 2 callers must continue to use the current native
path: `solid.createEffect(effect, effectHandler, options)` and
`solid.createRenderEffect(effect, effectHandler, options)` when
`isNativeEffectHandler(initialOrEffect)` identifies a handler.

### Q3. Do other shim entry points have the same arity bug?

Audit result:

- `createEffect`: yes. One-argument calls and legacy
  `createEffect(fn, initialValue)` both route through `createLegacyEffect`,
  which currently calls raw `solid.createEffect` with no handler
  (`services/web/src/solid-compat/solid.ts:74-110`).
- `createComputed`: yes by alias. `export const createComputed =
  createEffect` inherits the same legacy path
  (`services/web/src/solid-compat/solid.ts:113`).
- `createRenderEffect`: yes. One-argument and legacy-initial-value calls route
  through `createLegacyEffect`; the TanStack Query caller at
  `@tanstack/solid-query/build/index.js:20` is the observed crash
  (`services/web/src/solid-compat/solid.ts:115-126`).
- `onMount`: yes indirectly. It calls the shim's exported `createEffect(fn)`,
  so it is fixed by the shared legacy effect repair
  (`services/web/src/solid-compat/solid.ts:68-71`).
- `createResource`: yes internally. It calls raw `solid.createEffect(() => ...)`
  with one argument and must be routed through the fixed legacy helper or the
  shim's exported `createEffect` (`services/web/src/solid-compat/solid.ts:146-160`).
- `createSignal`: no same arity bug. Solid 2 beta's `createSignal(e, t)` accepts
  an omitted second argument and does not dereference `t.effect`
  (`@solidjs/signals/dist/prod.js:1924-1926`).
- `For` and `Show`: no same shim arity bug. They are re-exported Solid
  components, not local wrappers that call the raw effect API with a missing
  handler.
- `Index`: no same arity bug. It delegates to `solid.For` and does not call a
  raw effect primitive (`services/web/src/solid-compat/solid.ts:56-65`).
- `batch`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`,
  `mergeProps`, `splitProps`, and `on`: no same arity bug. They do not call raw
  Solid 2 effect primitives.

## 3. Substrate

### Modified files

- `services/web/src/solid-compat/solid.ts`
  - Lines 74-82: replace `createLegacyEffect`'s direct one-argument
    `solid.createEffect(...)` call with a shared helper that accepts the native
    primitive (`solid.createEffect` or `solid.createRenderEffect`) and always
    supplies a no-op handler for legacy calls.
  - Lines 99-110: keep `createEffect`'s native-handler branch intact, but route
    one-argument and legacy-initial-value calls through the fixed legacy helper
    using `solid.createEffect`.
  - Line 113: keep `createComputed` wired to the fixed `createEffect` path.
  - Lines 115-126: route one-argument and legacy-initial-value
    `createRenderEffect` calls through the fixed legacy helper using
    `solid.createRenderEffect`; preserve the native-handler branch for
    two-argument Solid 2 callers.
  - Lines 146-160: change `createResource`'s internal tracking from raw
    one-argument `solid.createEffect` to the shim's fixed legacy effect path.

### Callers and evidence

- `services/web/node_modules/@tanstack/solid-query/build/index.js:20` calls
  `createRenderEffect((unmount) => { ... })` with one argument. This must no
  longer throw and must still execute the mount/unmount side effect.
- `services/web/node_modules/solid-js/dist/solid.js:589-590` forwards
  `createRenderEffect` and `createEffect` calls to the underlying Solid 2 beta
  primitives.
- `services/web/node_modules/@solidjs/signals/dist/prod.js:1931-1935` shows the
  native signatures: `createEffect(e, t, n)` dereferences `t.effect`, and
  `createRenderEffect(e, t, n)` passes `t` as the handler.
- `services/web/src/app/providers.tsx:26-37` wraps the whole router in
  `QueryClientProvider`, so this crash aborts the entire SPA before
  `RouterProvider` can mount.
- `services/web/src/features/public/ApplicationFormRoute.tsx:414-425` contains
  one-argument `createEffect` usage that should be covered by the same shim
  tests, even though the RCA's first observed crash is TanStack Query.

### New or modified tests

- Add `services/web/tests/solid-compat.spec.ts` using the configured Playwright
  test runner. There is no Vitest setup in `services/web/package.json` or
  `services/web/playwright.config.ts`; do not add a new test framework for this
  bug.
- Add a small Playwright bootstrap spec, either in
  `services/web/tests/solid-compat.spec.ts` or a focused
  `services/web/tests/router-bootstrap.spec.tsx`, that loads the built SPA
  through Vite preview and asserts the router root renders.

No API, Discord daemon, GitOps, migration, or live Discord-visible changes are
part of this proposal. This is a local web runtime shim change only, so it is
Tier 2 under the Live Server Principle.

## 4. Test plan

### TG-1 unit tests: shim entry points

Use Playwright's configured test runner as the unit-test harness for
`services/web/src/solid-compat/solid.ts`.

Cover these cases:

- `createEffect(fn)` does not throw, runs `fn`, and records the side effect.
- `createEffect(fn, initialValue)` does not throw, passes the initial value to
  the first run, and preserves the previous result for later runs.
- `createEffect(fn, nativeHandler)` still takes the Solid 2 native-handler path
  and calls the supplied handler.
- `createRenderEffect(fn)` does not throw, runs `fn`, and returns through the
  native render-effect primitive with a handler supplied.
- `createRenderEffect(fn, initialValue)` preserves legacy previous-value
  behavior.
- `createRenderEffect(fn, nativeHandler)` still takes the native Solid 2 path.
- `createComputed(fn)` inherits the fixed `createEffect(fn)` behavior.
- `onMount(fn)` does not throw and runs the callback through the fixed path.
- `createResource(fetcher)` does not throw from its internal effect and updates
  `loading`, `value`, and `error` accessors for a resolving fetcher.
- `createSignal(initial)`, `For`, and `Show` get smoke coverage to prove they
  are not changed by the effect fix.

The assertions must check both "no throw" and an observable side effect. A test
that only imports the module is insufficient because the failure occurs when the
effect flushes.

### TG-2 integration: SPA bootstrap chain

Add a small Playwright smoke test that loads the built SPA through the existing
`services/web/playwright.config.ts` web server, mocks the admin bootstrap APIs,
and navigates to `/admin/chapters`.

Assertions:

- No page error containing `Cannot read properties of undefined (reading
  'effect')`.
- `#root` is non-empty.
- The app shell or admin route heading renders, proving
  `AppProviders -> QueryClientProvider -> RouterProvider` bootstrapped.

This test should be narrow. It exists to catch the exact startup failure before
the full local e2e flow spends 30 seconds waiting for the admin heading.

### TG-3 e2e: deferred to 6c

Re-run test 19's Playwright admin step in the local cluster:

```bash
infra/tests/e2e/tests/19-web-ui.sh
```

The acceptance check for BUG-1 is that the browser flow reaches
`https://web.local.humility.local/admin/chapters` and the accessible heading
`Chapter administration` renders within 30 seconds.

This TG remains deferred to 6c because the current proposal stage is not an
implementation stage, and because the RCA identified a separate Pomerium drift
that may affect later API calls after the bootstrap crash is fixed.

## 5. Anti-scope

- Do not rewrite the SPA to use Solid 2 beta directly.
- Do not bump `@solidjs/signals`, `solid-js`, Vite, TanStack Query, TanStack
  Router, or any other package version.
- Do not monkeypatch `node_modules`, global Solid exports, or TanStack packages.
- Do not add a parallel `solid-js` API surface, new alias module, feature flag,
  compatibility mode switch, deprecated export, or fallback branch.
- Do not refactor consumers of the shim. Existing imports from `solid-js`,
  `solid-js/web`, and `solid-js/store` remain routed by Vite aliases.
- Do not change API, GitOps, Pomerium, Authentik, Discord daemon, or database
  behavior in this fix.
- Do not create deferred stubs or TODO comments. The shim repair and tests are
  complete in the implementation phase.

## 6. Pomerium drift secondary finding

Record the RCA's Pomerium/Auth drift as follow-up Bug #5: gitops state drift.

The checked-in local Pomerium template includes browser API identity-header
routes and the `discord_user_id` claim mapping, but the live local cluster's
rendered Pomerium config lacks `/api/me`, `/api/web/admin/`,
`/api/web/officer/`, and the `discord_user_id` claim-header route. That drift
would break admin/officer API calls through the browser after the SPA mounts,
but it is not the first failure boundary for BUG-1.

This proposal does not change Pomerium. BUG-1 is limited to the Solid compat
shim crash that aborts SPA bootstrap.

## 7. Diff budget

Estimated implementation diff:

- `services/web/src/solid-compat/solid.ts`: 20-35 changed lines.
- `services/web/tests/solid-compat.spec.ts`: 90-140 new lines.
- Optional focused bootstrap spec if kept separate from the unit spec:
  35-60 new lines.

Total expected budget: 145-235 lines. Any implementation materially larger
than that should be treated as scope drift and rechecked against this proposal's
anti-scope.
