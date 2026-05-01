# BUG-1 — Scope risk gate

**Verdict:** LOW

BUG-1 fixes the Solid 2 beta compat shim's legacy effect path so the
one-argument `createRenderEffect((unmount) => ...)` call from
`@tanstack/solid-query` no longer aborts SPA bootstrap with
`TypeError: Cannot read properties of undefined (reading 'effect')`
(`research/30-bug-1-admin-route-rca.md` §7,
`services/web/src/solid-compat/solid.ts:74-82, 115-126`). The proposal
locks one mechanism (`createLegacyEffect` always supplies a no-op
`legacyEffectHandler` to the native Solid 2 effect primitive) and
limits substrate to a single file plus shim-focused tests
(`proposals/18-bug-1-solid-compat-shim.md` §2 Q1, §3, §5). Diff
budget 145-235 lines (20-35 shim, 90-140 tests, 35-60 optional
bootstrap spec) is far below any single-PR threshold (§7).

## Gate checks

### 1. Only the shim file changes for the fix

**PASS.** §3 ("Modified files") enumerates exactly one source file:
`services/web/src/solid-compat/solid.ts`, lines 74-82, 99-110, 113,
115-126, 146-160. All five modification blocks target the same file.

The five blocks are coherent applications of the same fix:

- 74-82: replace `createLegacyEffect`'s raw one-argument
  `solid.createEffect(...)` with a shared helper that accepts the
  native primitive and always supplies the no-op handler.
- 99-110: route `createEffect`'s one-argument and legacy-initial
  paths through the fixed legacy helper using `solid.createEffect`;
  preserve the native-handler branch for two-argument Solid 2 callers.
- 113: keep `createComputed = createEffect` alias wired to the fixed
  path (no separate code path).
- 115-126: route `createRenderEffect`'s one-argument and
  legacy-initial paths through the fixed legacy helper using
  `solid.createRenderEffect`; preserve the native-handler branch.
- 146-160: change `createResource`'s internal effect from raw
  `solid.createEffect(...)` to the shim's fixed legacy effect path.

`onMount` (lines 68-71) is fixed transitively because it calls the
shim's exported `createEffect(fn)`. No second source file is touched.
`gitops/`, `services/api/`, the Discord daemon, Alembic migrations,
Pomerium templates, and Authentik blueprints are all untouched
(§3 "No API, Discord daemon, GitOps, migration, or live
Discord-visible changes"). ✅

### 2. No version bumps to solid-js, @solidjs/signals, or @tanstack/solid-query

**PASS.** §5 anti-scope: "Do not bump `@solidjs/signals`, `solid-js`,
Vite, TanStack Query, TanStack Router, or any other package version."
This forecloses the alternative fix path of upgrading
`@tanstack/solid-query` to a Solid 2-aware release. §3 also bans
`node_modules` patching: "Do not monkeypatch `node_modules`, global
Solid exports, or TanStack packages."

The fix sits entirely in the local compat layer
(`services/web/src/solid-compat/solid.ts`), which is the version
boundary the project owns. `services/web/package.json` versions of
`solid-js`, `@solidjs/signals`, `@tanstack/solid-query`, and
`@tanstack/solid-router` are unchanged. No `package-lock.json` /
lockfile churn from this fix. ✅

### 3. No refactor of consumers (queue route, detail route, application form, etc.)

**PASS.** §5 anti-scope: "Do not refactor consumers of the shim.
Existing imports from `solid-js`, `solid-js/web`, and
`solid-js/store` remain routed by Vite aliases."

The shim already absorbs the API gap behind the existing alias,
so consumers only need their existing imports to keep resolving. §3
explicitly notes one example consumer that benefits without being
edited: `services/web/src/features/public/ApplicationFormRoute.tsx:414-425`
contains one-argument `createEffect` usage that should be covered by
the same shim tests, "even though the RCA's first observed crash is
TanStack Query." That phrasing names the consumer as test-coverage
target, not edit target.

The proposal also does not edit `services/web/src/app/providers.tsx`
(the `QueryClientProvider` site that triggers the crash) or
`services/web/src/app/router.tsx` (the route registration). The
crash boundary is fixed inside the shim, leaving routing /
provider composition unchanged. ✅

### 4. No new abstractions beyond the `legacyEffectHandler` helper inside the shim

**PASS — minimal helper accepted by the gate criteria.** §2 Q1
locks one new symbol: `legacyEffectHandler`, a no-op Solid 2
effect handler that takes `(value, previous?) => void` and returns
nothing. This is the one helper named in the gate criteria.

§3 (lines 109-112) describes a "shared helper that accepts the
native primitive (`solid.createEffect` or `solid.createRenderEffect`)
and always supplies a no-op handler for legacy calls". This is not
a separate new abstraction — it is the existing `createLegacyEffect`
extended to take the native primitive as a parameter so both the
`createEffect` legacy path and the `createRenderEffect` legacy path
share the no-op handler call. Without this single parameter the fix
cannot be applied uniformly to both paths without duplicating the
no-op handler call site, which would be strictly worse.

§2 Q1 explicitly bans the alternative abstractions:

- "Do not pass `{}` as the second argument" (rules out a sentinel
  object pattern that would still fail at flush time).
- "Do not add a new top-level arity fork as the fix" (rules out
  branching in `createEffect` / `createRenderEffect` themselves
  rather than fixing the shared legacy path).

§5 anti-scope adds:

- "Do not add a parallel `solid-js` API surface, new alias module,
  feature flag, compatibility mode switch, deprecated export, or
  fallback branch."
- "Do not create deferred stubs or TODO comments."

So the shim gains exactly one new symbol (`legacyEffectHandler`)
and one extended parameter on the existing `createLegacyEffect`.
No new modules, no parallel API, no feature flag, no deprecated
exports. ✅

### 5. Tests added are focused on the shim's behavior (not full SPA refactor)

**PASS.** §4 enumerates three test groups, all narrowly scoped:

**TG-1 (unit, shim entry points).** Cases listed in §4 cover
exclusively the shim's exported surface area:

- `createEffect(fn)`, `createEffect(fn, initialValue)`,
  `createEffect(fn, nativeHandler)` — three arity branches.
- `createRenderEffect(fn)`, `createRenderEffect(fn, initialValue)`,
  `createRenderEffect(fn, nativeHandler)` — three arity branches.
- `createComputed(fn)` — alias inheritance check.
- `onMount(fn)` — transitive fix path.
- `createResource(fetcher)` — internal effect path; observable
  `loading`/`value`/`error` accessors.
- Smoke coverage for `createSignal`, `For`, `Show` to prove they
  are not changed by the effect fix.

§4 explicitly requires both "no throw" and an observable side
effect, "because the failure occurs when the effect flushes". A
test that only imports the module is named insufficient. This is
shim-behavior-focused, not consumer-behavior-focused.

**TG-2 (integration, SPA bootstrap chain).** §4 calls this a "small
Playwright smoke test", narrow by intent: "It exists to catch the
exact startup failure before the full local e2e flow spends 30
seconds waiting for the admin heading." Assertions are limited to
(a) no `Cannot read properties of undefined (reading 'effect')`
page error, (b) `#root` non-empty, (c) the app shell or admin
heading renders. This is the minimum boundary that proves
`AppProviders -> QueryClientProvider -> RouterProvider` did not
abort. It does not test queue, detail, application-form, or
chapter-selector routes.

**TG-3 (e2e).** Explicitly deferred to 6c: "This TG remains
deferred to 6c because the current proposal stage is not an
implementation stage". Re-running `infra/tests/e2e/tests/19-web-ui.sh`
is named as the post-fix acceptance check, not part of this
proposal's test additions.

§4 also names the harness constraint: "Use Playwright's configured
test runner... There is no Vitest setup... do not add a new test
framework for this bug." This forecloses scope creep into a new
unit-test framework. ✅

## In scope (justified)

- **`legacyEffectHandler` no-op handler** in the shim — required
  by Solid 2 beta's `createEffect(e, t, n)` and
  `createRenderEffect(e, t, n)` signatures, which dereference
  `t.effect || t` (`@solidjs/signals/dist/prod.js:1931-1935`).
  Passing the no-op handler matches the native signature without
  changing legacy-runner semantics.
- **Extending `createLegacyEffect` to accept the native primitive
  parameter.** The shared helper is the natural seam to apply the
  no-op handler uniformly to `createEffect`-legacy and
  `createRenderEffect`-legacy paths. Splitting render-effect
  scheduling from regular-effect scheduling is required (§2 Q2:
  "the legacy path should use `solid.createRenderEffect(runner,
  legacyEffectHandler)` so render-effect scheduling remains tied
  to the native render-effect primitive").
- **Routing `createResource`'s internal effect through the fixed
  legacy path.** §2 Q3 audit names this as another arity-bug site
  (line 151 currently calls raw `solid.createEffect(() => ...)`
  with one argument). Fixing it inside this proposal is correct
  because the same root cause applies; deferring it would leave
  a known-broken caller in the same module being modified.
- **Audit confirmation that `createSignal`, `For`, `Show`,
  `Index`, `batch`, `Suspense`, `ErrorBoundary`, `startTransition`,
  `useTransition`, `mergeProps`, `splitProps`, `on` do NOT have
  the same arity bug.** §2 Q3 enumerates each; smoke tests in
  TG-1 lock this in without modifying those entry points.
- **TG-1 unit coverage** of shim entry points using the configured
  Playwright test runner (no new framework introduced).
- **TG-2 narrow bootstrap smoke** asserting `#root` non-empty and
  no `'effect'` page error after `QueryClientProvider` mounts.

## Out of scope (deferred / explicit anti-scope §5)

- **SPA rewrite to Solid 2 beta directly** — explicitly banned.
- **Version bumps** of `@solidjs/signals`, `solid-js`, Vite,
  `@tanstack/solid-query`, `@tanstack/solid-router`, or any other
  package — explicitly banned.
- **`node_modules` patching, global Solid mutation, TanStack
  package monkeypatching** — explicitly banned.
- **Parallel `solid-js` API surface, new alias module, feature
  flag, compatibility mode switch, deprecated export, fallback
  branch** — explicitly banned.
- **Consumer refactors** in queue, detail, application-form,
  chapter-selector, providers, or router files — explicitly
  banned. Existing imports continue to resolve through the Vite
  alias.
- **Pomerium / Authentik / Discord daemon / API / GitOps /
  migration changes** — explicitly out of scope. The §6
  Pomerium drift (live local cluster missing `/api/me`,
  `/api/web/admin/`, `/api/web/officer/`, and the
  `discord_user_id` claim-header route) is recorded as
  follow-up Bug #5 (gitops state drift), NOT bundled into
  BUG-1.
- **Deferred stubs / TODO comments** — explicitly banned.
- **TG-3 e2e re-run of `19-web-ui.sh`** — deferred to phase 6c;
  acceptance check not test addition.
- **A new test framework (Vitest, Jest, etc.)** — explicitly
  banned; Playwright's configured runner is reused.

## Risk surface

| Area | Pre | Post (BUG-1) | Justification |
|---|---|---|---|
| Modified source files | — | `services/web/src/solid-compat/solid.ts` only | §3 enumerates one source file with five line-block edits |
| New source files | — | None | Test-only additions live under `services/web/tests/` |
| Modified test files | — | `services/web/tests/solid-compat.spec.ts` (new); optional `services/web/tests/router-bootstrap.spec.tsx` (new) | §4 TG-1 + TG-2 |
| Package versions | `solid-js`, `@solidjs/signals`, `@tanstack/solid-query`, `@tanstack/solid-router`, Vite | Identical | §5 explicitly bans bumps |
| `node_modules` content | upstream releases | Identical (no patching) | §5 explicitly bans monkeypatching |
| Vite alias surface | Existing aliases route consumer imports through the shim | Identical | §5 "Existing imports from `solid-js`, `solid-js/web`, and `solid-js/store` remain routed by Vite aliases" |
| Shim exported symbols | `batch`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `Index`, `onMount`, `createEffect`, `createComputed`, `createRenderEffect`, `on`, `createResource`, plus re-exports | Same set; one new internal `legacyEffectHandler` (not exported in the public sense — internal helper) | §2 Q1 names `legacyEffectHandler` as the one new helper |
| `createEffect(fn)` semantics | Throws `TypeError` at flush via `t.effect` deref | Runs `fn`; previous-value chain preserved | §2 Q1 + §4 TG-1 |
| `createEffect(fn, initialValue)` semantics | Throws `TypeError` at flush | First run gets `initialValue`; later runs get prior result | §4 TG-1 |
| `createEffect(fn, nativeHandler [, options])` semantics | Native Solid 2 path | Identical native path | §2 Q1 "Two-argument native Solid 2 callers must continue to use the current native path"; preserved by `isNativeEffectHandler` (lines 87-95) |
| `createRenderEffect(fn)` semantics | Throws `TypeError` at flush | Runs `fn` via `solid.createRenderEffect` with no-op handler; render-effect scheduling preserved | §2 Q2 |
| `createComputed(fn)` semantics | Throws (alias of broken `createEffect`) | Inherits fixed `createEffect` | Line 113 alias unchanged |
| `onMount(fn)` semantics | Throws (calls broken `createEffect(fn)`) | Runs callback through fixed path | Lines 68-71 unchanged; transitive fix |
| `createResource(fetcher)` semantics | Throws (calls raw `solid.createEffect(() => ...)`) | Internal effect routed through fixed legacy path; `loading`/`value`/`error` accessors observable | §3 lines 146-160 |
| `createSignal`, `For`, `Show`, `Index`, `batch`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `on` | Functional today | Identical | §2 Q3 audit + TG-1 smoke locks |
| `AppProviders` / `QueryClientProvider` / `RouterProvider` chain (`services/web/src/app/providers.tsx:26-37`) | Aborts at first `createRenderEffect` flush | Bootstraps; `RouterProvider` mounts | §1 root cause closure |
| Admin heading at `/admin/chapters` (`services/web/src/features/admin/AdminChaptersRoute.tsx:65`) | Never mounts; body length 0 | Mounts after OAuth | RCA §1, §5 |
| Pomerium policy / template | Live drift at `/api/me`, `/api/web/admin/`, `/api/web/officer/`, `discord_user_id` claim-header route | Identical (deferred to Bug #5 §6) | §5 anti-scope: "Do not change... Pomerium... behavior in this fix" |
| Authentik blueprint | Includes `pomerium` app/provider + `discord_user_id` scope mapping | Identical | Not in §3 modified files |
| API behavior | Healthy when identity headers present | Identical | RCA §6 |
| Discord daemon / Discord-visible writes | INIT-134 surface | Identical | §3 explicit |
| Alembic migrations | Current head | Identical (no migration) | §5 anti-scope |
| Test harness | Playwright via `services/web/playwright.config.ts` | Same harness; new spec(s) reuse it | §4 "do not add a new test framework for this bug" |
| Diff budget | — | 145-235 lines (20-35 shim, 90-140 spec, 35-60 optional bootstrap spec) | §7 self-policed; flag any larger diff as scope drift |

## Splittable concerns

- **The five line-block edits in `services/web/src/solid-compat/solid.ts`
  are not splittable.** They share one root cause (Solid 2 beta
  effect primitives require a handler argument) and one mechanism
  (`legacyEffectHandler` applied through the shared
  `createLegacyEffect`). Splitting `createEffect` from
  `createRenderEffect` from `createResource` would leave known-broken
  arity-bug sites in the same module post-merge, which §5 anti-scope
  forbids ("Do not create deferred stubs or TODO comments").
- **TG-1 unit spec and TG-2 bootstrap smoke can be one spec file or
  split between `services/web/tests/solid-compat.spec.ts` and
  `services/web/tests/router-bootstrap.spec.tsx`** (§4 leaves this
  choice to implementation). Either layout stays inside the
  diff budget; no scope difference.
- **§6 Pomerium drift secondary finding is the right boundary to
  split.** Bug #5 (gitops state drift) is the correct next
  follow-up because the live Pomerium config lacks the checked-in
  identity-header routes, and that drift would surface only after
  the SPA mounts (admin/officer API calls). Bundling it into
  BUG-1 would cross the proposal's §3 "no API, Discord daemon,
  GitOps, migration, or live Discord-visible changes" boundary.
- **TG-3 e2e re-run of `19-web-ui.sh`** is correctly deferred to
  phase 6c, not split into a separate proposal — it is a
  validation step against the running cluster, not new
  implementation surface.

## Verdict reasoning

LOW. Every gate check passes:

1. **Only the shim file changes for the fix.** §3 enumerates a
   single source file (`services/web/src/solid-compat/solid.ts`)
   with five tightly co-located line-block edits, all expressing
   the same fix. No second file is touched. ✅ check 1.
2. **No version bumps.** §5 anti-scope explicitly bans
   `@solidjs/signals`, `solid-js`, `@tanstack/solid-query`,
   `@tanstack/solid-router`, Vite, and "any other package" bumps.
   The fix sits in the local version boundary the project owns. ✅
   check 2.
3. **No consumer refactors.** §5 anti-scope explicitly bans
   refactoring shim consumers. Existing imports continue to
   resolve through the Vite alias. The proposal references
   `ApplicationFormRoute.tsx` only as a test-coverage target, not
   an edit target. ✅ check 3.
4. **No new abstractions beyond `legacyEffectHandler`.** The
   proposal introduces exactly one new symbol
   (`legacyEffectHandler`) and one extended parameter on the
   existing `createLegacyEffect`. §2 Q1 explicitly bans the
   alternative abstractions (`{}` sentinel, top-level arity fork,
   parallel API surface, alias module, feature flag, compatibility
   mode switch, deprecated export, fallback branch, deferred stubs,
   TODO comments). ✅ check 4.
5. **Tests focused on shim behavior, not full SPA refactor.**
   TG-1 covers shim entry points only; TG-2 is a narrow
   `#root`-non-empty + no-`'effect'`-pageerror smoke; TG-3 is
   deferred. The Playwright harness is reused; no new framework. ✅
   check 5.

Three judgment calls worth naming explicitly — all LOW-risk:

- **Extending `createLegacyEffect` to accept the native primitive
  parameter** is an extension of the existing helper, not a new
  abstraction. It is required to apply the no-op handler uniformly
  to both `createEffect`-legacy and `createRenderEffect`-legacy
  paths without duplicating the call site. Without this single
  parameter the fix would either fork into duplicate code or
  reintroduce the top-level arity-fork pattern §2 Q1 explicitly
  bans.
- **Routing `createResource`'s internal effect through the fixed
  legacy path** widens the touched surface within the same file
  by one block (lines 146-160). It is correct because §2 Q3 audit
  identified `createResource` as having the same arity bug
  (currently calling raw `solid.createEffect(() => ...)` with one
  argument). Leaving it broken in the same module being modified
  would be a deferred-stub pattern §5 explicitly bans, and any
  consumer that calls `createResource` would still crash on flush.
- **Recording §6 Pomerium drift as follow-up Bug #5 rather than
  bundling it** keeps BUG-1 tightly scoped to the SPA bootstrap
  crash and respects §5 anti-scope's API/GitOps/Pomerium ban. The
  RCA correctly identifies the drift as a secondary affected
  surface that surfaces only after the bootstrap crash is fixed,
  so sequencing BUG-1 first and Bug #5 next is the right ordering;
  bundling would cross test, deployment, and review boundaries.

No "while we're at it" cleanups, no upstream package upgrades,
no shim API redesign, no consumer refactors, no Pomerium /
Authentik / API / Discord / migration scope leakage, no new
test framework, no deferred stubs or TODO comments.

SCOPE_DONE: plans/risk/bug-1-scope.md
