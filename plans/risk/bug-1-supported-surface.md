# BUG-1 — Supported-surface risk gate

**Verdict:** LOW

BUG-1 (Solid compat shim legacy effect crash) repairs the local Solid 2
compatibility wrapper at `services/web/src/solid-compat/solid.ts`. The
change is confined to the internal `createLegacyEffect` helper and the
five effect entry points (`createEffect`, `createComputed`,
`createRenderEffect`, `onMount`, `createResource`); their exported
signatures, runtime semantics, and the Vite alias chain that routes
`solid-js` imports through the shim remain unchanged. The fix passes a
no-op handler to the underlying Solid 2 beta `solid.createEffect` /
`solid.createRenderEffect` primitives so that `@tanstack/solid-query`'s
one-argument `createRenderEffect((unmount) => …)` call no longer
dereferences `t.effect` on `undefined`. No public API, no new
dependency, no env var, no migration, no GitOps, and no
Pomerium/Authentik change is part of this fix; the RCA's secondary
Pomerium drift is recorded as separate follow-up Bug #5.

## Surfaces touched

### 1. Web public API surface (shim exports)

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/web/src/solid-compat/solid.ts` exports | `batch`, `equalFn`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `Index`, `onMount`, `createEffect`, `createComputed`, `createRenderEffect`, `on`, `createResource` plus `export *` re-exports from `solid-js/dist/solid.js` (`services/web/src/solid-compat/solid.ts:1-171`) | identical names, identical signatures; only the internal `createLegacyEffect` body and the call inside `createResource`'s effect block change (proposal §3 / §5) | none — additive on the implementation side; no exported name added, removed, renamed, or re-typed |
| `createEffect(fn)` arity-1 contract | runs `fn(undefined)` once, stores result, runs `fn(previous)` on later flushes; currently throws `TypeError: Cannot read properties of undefined (reading 'effect')` (proposal §1 step 5; `services/web/src/solid-compat/solid.ts:74-83`) | runs `fn(undefined)` once, stores result, runs `fn(previous)` on later flushes; no longer throws | none — observable runner contract preserved; "throws on bootstrap" is the bug being fixed, not a contract |
| `createEffect(fn, initialValue)` arity-2 legacy contract | first run receives `initialValue`, later runs receive previous result (`services/web/src/solid-compat/solid.ts:99-110`) | unchanged runner contract; only the underlying `nativeCreateEffect(runner, legacyEffectHandler)` call adds a no-op handler (proposal §2 Q1) | none |
| `createEffect(fn, nativeHandler[, options])` Solid 2 native path | dispatched via `isNativeEffectHandler` to `solid.createEffect(effect, handler, options)` (`services/web/src/solid-compat/solid.ts:107-110`) | unchanged — native two-argument callers continue to take the native path verbatim (proposal §2 Q2 last paragraph) | none |
| `createComputed` | `export const createComputed = createEffect` (`services/web/src/solid-compat/solid.ts:113`) | unchanged alias; inherits the fixed `createEffect` path (proposal §3 Q3 audit) | none |
| `createRenderEffect(fn)` arity-1 contract | currently routes through `createLegacyEffect`, which throws against Solid 2 beta (proposal §1 step 4) | routes through fixed legacy helper invoking `solid.createRenderEffect(runner, legacyEffectHandler)`; render-effect scheduling stays bound to the native render-effect primitive (proposal §2 Q2) | none — semantics preserved; the existing one-argument `@tanstack/solid-query` caller (`services/web/node_modules/@tanstack/solid-query/build/index.js:20`) and `services/web/src/features/public/ApplicationFormRoute.tsx:414-425` continue to receive an unmount-style render effect |
| `createRenderEffect(fn, initialValue)` and `createRenderEffect(fn, nativeHandler[, options])` | dispatched by `arguments.length` and `isNativeEffectHandler` (`services/web/src/solid-compat/solid.ts:115-127`) | unchanged dispatch; legacy 2-arg routes through fixed helper, native handler routes through `solid.createRenderEffect` directly (proposal §3) | none |
| `onMount(fn)` | wraps the shim's `createEffect(() => fn())` (`services/web/src/solid-compat/solid.ts:68-72`) | unchanged source; inherits the fixed `createEffect` path | none |
| `createResource(fetcher)` | returns `[Object.assign(value, { loading, error }), { refetch }]`; internally calls raw one-argument `solid.createEffect` (`services/web/src/solid-compat/solid.ts:146-171`) | identical return shape and accessor semantics; internal effect routes through the fixed legacy path (proposal §3) | none — return tuple shape, accessor `loading`/`error` properties, and `refetch` API preserved |
| `createSignal`, `For`, `Show`, `Index`, `batch`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `on` | exported as today (`services/web/src/solid-compat/solid.ts:6-66`, `129-144`, plus `export *`) | unchanged — proposal §2 Q3 audit confirms none of them call the raw effect primitive with a missing handler | none |

Risk on §1: **none** — gate criterion 1 (no public API change) holds.
Every exported identifier in the shim keeps its name, its declared
arity, and its observable runtime contract; the only differences are
inside `createLegacyEffect` (internal helper, not exported) and the
internal effect block of `createResource`.

### 2. Dependency surface — none added, none bumped

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/web/package.json` | declared `solid-js`, `@solidjs/signals`, `@tanstack/solid-query`, `@tanstack/solid-router`, `vite`, `vite-plugin-solid`, `@playwright/test` (existing pinned versions) | unchanged — anti-scope §5 forbids bumping `@solidjs/signals`, `solid-js`, Vite, TanStack Query, TanStack Router, or any other package; no new test framework is added (proposal §4 TG-1) | none |
| `services/web/node_modules` | as installed | not patched; anti-scope §5 forbids monkey-patching `node_modules`, global Solid exports, or TanStack packages | none |
| Test runner | Playwright (`services/web/playwright.config.ts`) | reused for both unit-style shim coverage (`services/web/tests/solid-compat.spec.ts`) and the bootstrap smoke test (proposal §4 TG-1 / TG-2) | none — Playwright is already a dependency |

Risk on §2: **none** — gate criterion 2 holds.

### 3. Backwards-compat shim layering — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Compat shim count | one shim at `services/web/src/solid-compat/solid.ts` aliased by `vite.config.ts:11-25` | unchanged — fix lives inside that single shim; anti-scope §5 forbids "a parallel `solid-js` API surface, new alias module, feature flag, compatibility mode switch, deprecated export, or fallback branch" (proposal §5) | none |
| Vite alias chain | `solid-js` → `src/solid-compat/solid.ts`, `solid-js/web` → `src/solid-compat/web.ts`, `solid-js/store` → `src/solid-compat/store.ts` (`services/web/vite.config.ts:11-25`) | unchanged | none |
| Companion shims (`web.ts`, `store.ts`) | not part of the BUG-1 fix scope | untouched (proposal §3 modified-files list) | none |

Risk on §3: **none** — gate criterion 3 (no shim-on-shim) holds. The
fix repairs the existing legacy path; it does not add a wrapper
around the wrapper, a feature toggle, or a deprecated alternate
export.

### 4. Environment variables — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/web` env vars (`VITE_API_BASE_URL`, build-time flags) | as defined in `vite.config.ts:5-7` | unchanged | none |
| Runtime web `ConfigMap` / `Secret` references | unchanged | unchanged | none |

Risk on §4: **none** — gate criterion 4 holds. Proposal §3 and the
anti-scope make no env-var change; the fix is a pure source edit.

### 5. Database migrations — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head | current head (`migrations/versions/...`) | unchanged — anti-scope §5 forbids changing database behavior; proposal §3 explicitly limits changes to `services/web/src/solid-compat/solid.ts` and `services/web/tests/...` | none |
| Web service ↔ DB | web is a static SPA; no direct DB connection | unchanged | none |

Risk on §5: **none** — gate criterion 5 holds.

### 6. GitOps surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/**` | as checked in | unchanged — anti-scope §5 explicitly forbids GitOps changes (proposal §5) | none |
| `gitops/channels/local/auth/pomerium/**` rendered config drift | drift recorded in RCA §3 (`research/30-bug-1-admin-route-rca.md:171-203`) | not addressed in this fix; proposal §6 records it as separate follow-up Bug #5 — explicitly out of scope for BUG-1 | none on the BUG-1 surface; the drift is a *secondary* effect that surfaces only after this bootstrap crash is fixed |
| Web container image / build pipeline | Vite production build via existing pipeline | unchanged build target; only `services/web/src/solid-compat/solid.ts` source bytes change, plus net-new test files under `services/web/tests/` (proposal §3, §7) | none |

Risk on §6: **none** — gate criterion 6 holds.

### 7. Pomerium / Authentik surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Pomerium routes (`gitops/channels/local/auth/pomerium/...`) | as checked in (and live drift documented in RCA) | unchanged — anti-scope §5 forbids Pomerium changes; proposal §6 explicitly carves out the live-cluster Pomerium drift as Bug #5 | none |
| Authentik blueprint (`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`) | unchanged | unchanged | none |
| OAuth round-trip behavior | already completes (RCA §2) | unchanged | none |

Risk on §7: **none** — gate criterion 7 holds. The RCA confirmed OAuth
completes before the timeout; Pomerium live drift is not a BUG-1
concern.

### 8. Runtime API of `createEffect`, `createRenderEffect`, etc. as called by existing SPA code

The shim is consumed by every SPA module that imports from
`solid-js`, `solid-js/web`, or `solid-js/store` — this includes
`services/web/src/app/providers.tsx`, `services/web/src/app/router.tsx`,
`services/web/src/features/admin/AdminChaptersRoute.tsx`,
`services/web/src/features/public/ApplicationFormRoute.tsx`, the
TanStack Solid packages (`@tanstack/solid-query`, `@tanstack/solid-router`),
and the Solid library itself. The supported behavioral contract for
existing callers is:

| Call shape (existing SPA usage) | Pre (broken) | Post (fixed) | Behavior delta |
|---|---|---|---|
| `createRenderEffect((unmount) => …)` from `@tanstack/solid-query/build/index.js:20` | throws `TypeError: Cannot read properties of undefined (reading 'effect')` (RCA §7) | runs the effect; native `solid.createRenderEffect` schedules it with a no-op handler that accepts the computed value (proposal §2 Q2) | the effect now runs as Solid 1.x callers expect — no change to the *intended* contract; only the bug is removed |
| `createEffect(fn)` (one-arg legacy) | currently broken on the same path | runs `fn(undefined)` once, then `fn(previous)` on each subsequent flush; the previous result is captured by the runner closure (proposal §2 Q1) | identical to the documented Solid 1.x legacy contract |
| `createEffect(fn, initialValue)` (two-arg legacy) | `arguments.length === 2` → routes through `createLegacyEffect` with `initial`; currently broken because the helper called raw `solid.createEffect` without a handler | identical runner closure now invokes `solid.createEffect(runner, legacyEffectHandler)`; first run sees `initialValue`, later runs see previous result (proposal §2 Q1) | unchanged contract |
| `createEffect(fn, handler[, options])` (Solid 2 native) | `isNativeEffectHandler(handler)` → routes to `solid.createEffect(fn, handler, options)` (`services/web/src/solid-compat/solid.ts:107-110`) | unchanged — native handler is forwarded verbatim with `options` (proposal §2 Q2 last paragraph) | none |
| `createComputed(fn[, initial])` | `export const createComputed = createEffect` (`services/web/src/solid-compat/solid.ts:113`) inherits the bug today | inherits the fix; same arity dispatch as `createEffect` (proposal §2 Q3) | none |
| `createRenderEffect(fn, initialValue)` and `createRenderEffect(fn, handler[, options])` | dispatch unchanged by arity / `isNativeEffectHandler` (`services/web/src/solid-compat/solid.ts:115-127`) | dispatch unchanged; legacy path now safe; native path still uses `solid.createRenderEffect` directly | none |
| `onMount(callback)` | implemented as `createEffect(() => callback())` (`services/web/src/solid-compat/solid.ts:68-72`); broken by transitive bug | implemented identically; inherits the fix | none |
| `createResource(fetcher)` | exported tuple `[Object.assign(value, { loading, error }), { refetch }]` (`services/web/src/solid-compat/solid.ts:146-171`) — the internal `solid.createEffect(() => …)` call would also throw if it ever flushed | identical return shape and accessor semantics; the internal effect routes through the fixed legacy helper so internal scheduling is safe (proposal §3) | none on the public tuple/accessors |
| `createSignal(initial)` | not affected by the bug — Solid 2 beta `createSignal(e, t)` does not dereference `t.effect` (proposal §2 Q3) | unchanged | none |
| `For`, `Show`, `Index`, `Suspense`, `ErrorBoundary`, `batch`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `on` | not affected by the bug (proposal §2 Q3) | unchanged | none |

`legacyEffectHandler` is the proposal's required no-op `(value) => {}`
that satisfies the Solid 2 beta `effect(e, t.effect || t, t.error,
{ user: true, ...n })` contract at
`services/web/node_modules/@solidjs/signals/dist/prod.js:1931-1935`
without changing the runner's caller-visible inputs. The proposal
explicitly forbids passing `{}` (which would only delay the failure)
and explicitly forbids using `createReaction` (which would change
scheduling semantics). Two-argument native Solid 2 callers continue to
take the native dispatch path verbatim (proposal §2 Q2).

Risk on §8: **none** — gate criterion 8 (runtime API of effect
primitives unchanged for existing SPA callers) holds. The only
behavioral delta is "previously crashed, now does what the contract
says" — that is the bug fix, not a contract change.

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change — exported names stay identical | PASS |
| 2. No new dependencies | PASS |
| 3. No backwards-compat shim layered on top of the shim | PASS |
| 4. No env vars | PASS |
| 5. No DB migrations | PASS |
| 6. No GitOps changes | PASS |
| 7. No Pomerium/Authentik changes | PASS |
| 8. Runtime API of `createEffect`, `createRenderEffect`, etc. as called by existing SPA code remains identical | PASS |

## Out-of-scope items intentionally not addressed

- Live-cluster Pomerium config drift recorded in
  `research/30-bug-1-admin-route-rca.md:171-203` (missing `/api/me`,
  `/api/web/admin/`, `/api/web/officer/`, and `discord_user_id`
  claim-header routes). Proposal §6 carves this out as separate
  follow-up Bug #5; addressing it inside BUG-1 would violate gate
  criteria 6 and 7.
- TG-3 e2e re-run of `infra/tests/e2e/tests/19-web-ui.sh` is deferred
  to phase 6c (proposal §4 TG-3); the current proposal stage adds shim
  unit coverage and a Vite-preview bootstrap smoke test only.

## Verdict

**LOW** — the fix is a localized internal repair of one shim helper,
preserves every supported entry point and runtime contract, and adds
no new surface across packages, env, schema, GitOps, or auth.

SUPPORTED_SURFACE_DONE: plans/risk/bug-1-supported-surface.md
