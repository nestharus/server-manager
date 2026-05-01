# BUG-1 hookpoints

## Summary

BUG-1 repairs the Solid 2 beta compat shim's legacy effect path so the
one-argument `createRenderEffect((unmount) => …)` call from
`@tanstack/solid-query` no longer aborts SPA bootstrap with
`TypeError: Cannot read properties of undefined (reading 'effect')`
(`research/30-bug-1-admin-route-rca.md` §7).

The fix is confined to one source file
(`services/web/src/solid-compat/solid.ts`) plus net-new test files
under `services/web/tests/`. The implementation extends the existing
`createLegacyEffect` helper to accept the native primitive
(`solid.createEffect` or `solid.createRenderEffect`) and always supply
a no-op `legacyEffectHandler`, then re-routes the five effect entry
points (`createEffect`, `createComputed`, `createRenderEffect`,
`onMount`, `createResource`) through that fixed helper.

The Playwright runner at `services/web/playwright.config.ts` is the
sole test harness — no Vitest is configured, and proposal §4 forbids
adding a new framework. TG-1 lands as a new Playwright spec that
exercises the shim's runtime behavior; TG-2 lands as a narrow
bootstrap smoke that loads the built SPA via Vite preview; TG-3 is
the deferred re-run of `infra/tests/e2e/tests/19-web-ui.sh` against
the live cluster.

## Reuse (call directly)

Line numbers are approximate against the post-fix file; symbol names are authoritative.

### Shim internals

- `services/web/src/solid-compat/solid.ts:2` — `import * as solid from
  "../../node_modules/solid-js/dist/solid.js"`. The module-level
  binding stays the call surface for both
  `solid.createEffect(runner, legacyEffectHandler)` and
  `solid.createRenderEffect(runner, legacyEffectHandler)`. Reuse, do
  not re-import.
- `services/web/src/solid-compat/solid.ts:87-95` — `isNativeEffectHandler`.
  Already discriminates Solid 2 native two-arg callers from legacy
  initial-value callers. Reuse verbatim from the fixed
  `createEffect` and `createRenderEffect` dispatchers; do not
  duplicate the function-or-`{effect|error}` predicate.
- `services/web/src/solid-compat/solid.ts:74-82` — the existing
  `createLegacyEffect` runner closure (`hasPrevious`, `previous`,
  `effect(hasPrevious ? previous : undefined)`, reassign on each
  pass). Reuse the closure pattern; only the call site at line 77
  changes from `solid.createEffect(...)` (one-arg) to
  `nativeCreateEffect(runner, legacyEffectHandler)` (two-arg via the
  new parameter).
- `services/web/src/solid-compat/solid.ts:147-149, 162-170` —
  `createResource`'s `solid.createSignal` triple
  (`value`/`loading`/`error`) and the returned tuple
  `[Object.assign(value, { loading, error }), { refetch }]`. Reuse
  unchanged; only the internal `solid.createEffect(() => …)` block at
  lines 151-160 reroutes through the fixed legacy helper.
- `services/web/src/solid-compat/solid.ts:68-72` — `onMount(callback)`
  body `return createEffect(() => { callback(); });`. Reuse verbatim;
  it inherits the fix transitively because it calls the shim's
  exported `createEffect`.
- `services/web/src/solid-compat/solid.ts:113` — `export const
  createComputed = createEffect`. Reuse the alias verbatim; it
  inherits the fix automatically.

### Test infrastructure

- `services/web/playwright.config.ts` — the configured Playwright
  runner (`testDir: "./tests"`, `baseURL: "http://127.0.0.1:4173"`,
  `webServer: "npm run build && npm run preview --host 127.0.0.1"`).
  Reuse for both TG-1 and TG-2; proposal §4 forbids adding a new
  framework.
- `services/web/package.json:13-16` — existing `npm run test` and
  `npm run test:compat` scripts. The new spec at
  `services/web/tests/solid-compat.spec.ts` will be picked up by
  `npm run test`. No script change required.
- `services/web/tests/compat.spec.ts:1-3` — the existing
  `import { expect, test } from "@playwright/test"` pattern. Reuse
  the import shape; both TG-1 and TG-2 are Playwright `test(...)`
  files in the same directory.
- `services/web/tests/compat.spec.ts:71-89` — the existing
  `page.route("**/...", ...)` mocking pattern for unauthenticated
  API stubs. TG-2 reuses this idiom to stub the admin bootstrap APIs
  (`/api/me`, `/api/web/admin/chapters`) so the smoke test does not
  depend on a live cluster.
- `services/web/vite.config.ts:11-25` — the Vite alias chain that
  routes `solid-js`, `solid-js/web`, and `solid-js/store` through the
  shim. Reuse unchanged; the shim repair stays inside the existing
  alias destination.
- `infra/tests/e2e/tests/19-web-ui.sh` and
  `infra/tests/e2e/lib/playwright/browser-flow.mjs:84` — the existing
  e2e harness for TG-3. Reuse verbatim; the acceptance check is that
  `getByRole("heading", { name: "Chapter administration" })` becomes
  visible inside the 30s timeout once the bootstrap crash is removed.

## New (write fresh)

### Tests

- TG-1: shim unit tests — `services/web/tests/solid-compat.spec.ts`
  (new). Test names (one Playwright `test(...)` block per case so
  failures isolate per surface):
  - `"createEffect(fn) does not throw and runs the effect"` — exact
    arity-1 failure path; assert no throw + observable side effect
    (e.g., a counter incremented inside `fn`).
  - `"createEffect(fn, initialValue) passes initial then previous"` —
    asserts `fn` receives `initialValue` on the first run and the
    prior result on later runs.
  - `"createEffect(fn, nativeHandler) takes the native path"` —
    asserts the supplied handler is invoked with the runner's return
    value (proves `isNativeEffectHandler` discrimination is intact).
  - `"createRenderEffect(fn) does not throw and runs the effect"` —
    the TanStack Query call site at
    `services/web/node_modules/@tanstack/solid-query/build/index.js:20`.
  - `"createRenderEffect(fn, initialValue) preserves previous-value
    semantics"`.
  - `"createRenderEffect(fn, nativeHandler) takes the native path"`.
  - `"createComputed(fn) inherits the fixed createEffect path"` —
    asserts the alias at solid.ts:113 routes through the fix.
  - `"onMount(fn) runs the callback once via the fixed path"` —
    transitive coverage of solid.ts:68-72.
  - `"createResource(fetcher) updates loading, value, and error
    accessors"` — covers the internal effect at solid.ts:151 with a
    resolving fetcher; asserts `loading` flips true→false and
    `value()` returns the resolved payload.
  - `"createResource(fetcher) sets error accessor on rejection"` —
    same path with a rejecting fetcher.
  - `"createSignal smoke: get and set"` — proves the un-fixed entry
    point still works (negative-space lock).
  - `"For smoke: renders each item"` and `"Show smoke: renders when
    when-true"` — negative-space locks for the re-exported
    components.

  Spec must run inside the shim's actual reactive context — wrap
  effect calls in `solid.createRoot(() => …)` (imported from
  `services/web/src/solid-compat/solid.ts`) so flushes occur and
  cleanup is bounded. Proposal §4 explicitly bars import-only smoke:
  the failure manifests at flush time.

- TG-2: bootstrap smoke test —
  `services/web/tests/router-bootstrap.spec.tsx` (new, optional per
  proposal §4 / §7; may be folded into the same
  `solid-compat.spec.ts` file if the spec stays under the diff
  budget). Test name:
  - `"admin chapters route mounts under QueryClientProvider"` —
    `page.goto("/admin/chapters")`; mock `**/api/me` and
    `**/api/v1/web/admin/chapters` via the existing `page.route`
    idiom from `tests/compat.spec.ts:71-89`; collect `pageerror`
    events through `page.on("pageerror", …)`; assert:
    - no page error message contains `Cannot read properties of
      undefined (reading 'effect')`,
    - `page.locator("#root")` is non-empty
      (`expect(...).not.toBeEmpty()` or innerHTML length > 0),
    - `page.getByRole("heading", { name: "Chapter administration" })`
      is visible (the same accessible-name contract as
      `browser-flow.mjs:84`).

  This spec runs against the Vite preview server already wired by
  `playwright.config.ts:webServer`, so no extra infra is required.

- TG-3: e2e — extension point in test 19.
  - Re-run `infra/tests/e2e/tests/19-web-ui.sh` against the local
    humility cluster (no script edits). The acceptance check is the
    existing `browser-flow.mjs:84` `getByRole("heading", { name:
    "Chapter administration" })` visibility within 30 s; it currently
    times out due to the bootstrap crash (RCA §7).
  - No new assertion is added to test 19. The shim repair makes the
    existing assertion pass; the Pomerium drift recorded in proposal
    §6 / RCA §3 is carved out as Bug #5 and may still cause later
    `/api/me` and `/api/web/admin/chapters` failures after bootstrap
    succeeds. If that drift surfaces a new failure in test 19 after
    the shim fix lands, log it against Bug #5; do not bundle it into
    BUG-1.
  - Proposal §4 explicitly defers TG-3 to phase 6c.

## Modify in place

Line numbers are approximate against the post-fix file; symbol names are authoritative.

### Shim

`services/web/src/solid-compat/solid.ts` — only file edited for the
fix. Modified line ranges (current line numbers; the diff will shift
lines slightly):

- **Lines 74-83 — `createLegacyEffect`.** Extend the signature to
  accept the native primitive:
  `function createLegacyEffect<T>(nativeCreateEffect, effect, initial?)`.
  Preserve the closure body verbatim (`hasPrevious`, `previous`,
  reassignment) — proposal §2 Q1 and audit F-3 require the
  previous-result threading to live in the runner closure. Replace
  the line 77 call from `solid.createEffect(() => { … })` to
  `nativeCreateEffect(() => { … }, legacyEffectHandler)`. Add (above
  or beside this function) the new no-op
  `function legacyEffectHandler(_value: unknown) { /* no-op */ }`.
  Diff target ~10-15 lines.
- **Lines 99-111 — `createEffect`.** Keep the public signature
  `(effect, initialOrEffect?, options?)`. Keep the
  `arguments.length === 1` branch (line 104) but route through
  `createLegacyEffect(solid.createEffect, effect)`. Keep the
  `!isNativeEffectHandler(initialOrEffect)` branch (lines 107-109)
  but route through
  `createLegacyEffect(solid.createEffect, effect, initialOrEffect as T)`.
  Keep the native-handler return at line 110
  (`solid.createEffect(effect, initialOrEffect, options)`) verbatim
  (audit F-2; required by Q2 last paragraph). Diff target ~3-5
  lines.
- **Line 113 — `createComputed`.** No edit. The
  `export const createComputed = createEffect` alias inherits the
  fix automatically (audit F-4).
- **Lines 115-127 — `createRenderEffect`.** Same shape as the
  `createEffect` edit, but route through
  `createLegacyEffect(solid.createRenderEffect, effect)` and
  `createLegacyEffect(solid.createRenderEffect, effect, initialOrEffect as T)`.
  Keep the native-handler return at line 126
  (`solid.createRenderEffect(effect, initialOrEffect, options)`)
  verbatim. Q2 explicitly locks render-effect scheduling to the
  native render-effect primitive. Diff target ~3-5 lines.
- **Lines 146-171 — `createResource`.** Replace the raw
  `solid.createEffect(() => { … })` block at lines 151-160 with
  `createLegacyEffect(solid.createEffect, () => { … })`. Preserve
  `setLoading(true)`, the `fetcher().then(...).catch(...).finally(...)`
  chain, and the returned tuple shape verbatim (audit F-4 and
  shortcut-gate finding 2). Diff target ~1-3 lines.

Total expected shim diff: ~20-35 changed lines, matching proposal
§7's budget.

### Functions that stay verbatim

- Lines 6-66 — `batch`, `equalFn`, `Suspense`, `ErrorBoundary`,
  `startTransition`, `useTransition`, `mergeProps`, `splitProps`,
  `Index`. Audit F-5 confirms none of these touch raw effect
  primitives; do not edit.
- Lines 68-72 — `onMount`. Inherits the fix transitively through the
  shim's exported `createEffect`. Do not edit.
- Lines 87-95 — `isNativeEffectHandler`. The existing predicate is
  the dispatch contract for the native-handler branches; do not
  edit.
- Lines 129-144 — `on`. Pure JS composition helper; no raw effect
  primitive. Do not edit.
- Lines 1-4 — module-level imports and the `export *` re-export from
  `solid-js/dist/solid.js`. Do not edit; the re-export keeps
  `createSignal`, `For`, `Show`, etc. flowing through unchanged
  (audit F-5).

## Anti-scope

The following are out of scope for BUG-1 (proposal §5; cross-checked
against `plans/risk/bug-1-{audit,scope,shortcut,supported-surface}.md`):

- **No second source file.** Do not edit
  `services/web/src/app/providers.tsx`,
  `services/web/src/app/router.tsx`,
  `services/web/src/features/admin/AdminChaptersRoute.tsx`,
  `services/web/src/features/public/ApplicationFormRoute.tsx`, or any
  other shim consumer. Existing imports from `solid-js`,
  `solid-js/web`, and `solid-js/store` continue to resolve through
  the Vite alias.
- **No package version bumps.** Do not bump `solid-js`,
  `@solidjs/signals`, `@tanstack/solid-query`,
  `@tanstack/solid-router`, Vite, `vite-plugin-solid`,
  `@playwright/test`, or any other package. Do not touch
  `services/web/package.json` dependency entries or any lockfile.
- **No `node_modules` patching.** Do not monkeypatch
  `services/web/node_modules/@solidjs/signals`,
  `services/web/node_modules/solid-js`,
  `services/web/node_modules/@tanstack/solid-query`, or any other
  upstream package. Do not register a `patch-package`-style overlay.
- **No new abstractions beyond `legacyEffectHandler` + the extended
  `createLegacyEffect` parameter.** Do not add a parallel `solid-js`
  API surface, a new alias module, a feature flag, a compatibility
  mode switch, a deprecated export, a fallback branch, or a
  `try/catch` wrapper. Do not introduce a sentinel `{}` argument
  (proposal §2 Q1 explicitly bans this — it only delays the
  failure). Do not switch to `createReaction` (Q2).
- **No top-level arity fork as the fix.** Do not branch in
  `createEffect` / `createRenderEffect` themselves; the bug is in
  the shared legacy helper, and the fix must repair the shared
  helper.
- **No new test framework.** Do not add Vitest, Jest, or any other
  unit-test runner. The Playwright config at
  `services/web/playwright.config.ts` is the sole harness. Do not
  add a separate `vitest.config.ts`, `jest.config.js`, or
  equivalent.
- **No deferred stubs or TODO comments.** Proposal §5 explicitly
  bans these; the shim repair and tests are complete in the
  implementation phase.
- **No TG-3 e2e edits.** Do not modify `infra/tests/e2e/tests/19-web-ui.sh`,
  `infra/tests/e2e/lib/playwright/browser-flow.mjs`, or any e2e
  harness file. Re-running test 19 is the acceptance check, not new
  test infrastructure.
- **No Pomerium / Authentik / GitOps / API / Discord / migration
  changes.** The live-cluster Pomerium drift (RCA §3, proposal §6 —
  missing `/api/me`, `/api/web/admin/`, `/api/web/officer/`, and
  `discord_user_id` claim-header routes) is recorded as separate
  follow-up Bug #5. Do not bundle it into BUG-1.
- **No shim API redesign.** Exported names
  (`batch`, `equalFn`, `Suspense`, `ErrorBoundary`, `startTransition`,
  `useTransition`, `mergeProps`, `splitProps`, `Index`, `onMount`,
  `createEffect`, `createComputed`, `createRenderEffect`, `on`,
  `createResource`, plus the `export *` re-exports) keep their
  signatures and observable runtime contracts. The supported-surface
  gate enumerates this; do not rename, remove, or re-type.
- **No diff growth past ~145-235 lines** (~20-35 in the shim,
  ~90-140 in the unit spec, ~35-60 optional in the bootstrap spec).
  An implementation materially larger than that should be re-checked
  against this anti-scope list before landing.

HOOKPOINTS_DONE: research/31-bug-1-hookpoints.md
