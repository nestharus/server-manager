# BUG-1 — Shortcut risk gate (Solid compat shim)

**Verdict:** LOW

Source: `proposals/18-bug-1-solid-compat-shim.md`,
`research/30-bug-1-admin-route-rca.md`,
`services/web/src/solid-compat/solid.ts`.

## C1 — Real legacy-handler closure, not `() => {}` that loses threading

**Pass.**

The previous-result threading lives in the **runner closure**, not the
handler. The existing runner at `services/web/src/solid-compat/solid.ts:74-83`
already captures `previous`, `hasPrevious`, and `initial`, calls
`effect(hasPrevious ? previous : undefined)`, and reassigns `previous = result`
on each pass. The shim repair only changes the call site to pass that runner
plus a second argument to the native primitive.

The proposal Q1 (lines 33-37) preserves this exactly:

> The runner keeps the current legacy behavior: pass `undefined` to the
> first run when no initial value is supplied, pass the previous result on
> later runs, and store the latest result for the next run.

The "no-op handler" the proposal describes is the **second** argument
(Solid 2's effect-handler slot). In Solid 2, `createEffect(setup, handler)`
runs `setup` reactively and calls `handler` with the returned value. Legacy
semantics put the side effects inside the user's `effect(previous)` call,
which executes inside the runner — so the handler legitimately has nothing
to do, and a no-op handler does not strip threading.

This is the correct shape: real runner closure + benign handler stub. Not
the failure mode the check is guarding against (which would be a
`solid.createEffect(() => {}, () => {})` collapse that drops the runner).

## C2 — Uses `solid.createEffect(runner, handler)`, not a fake monkeypatch

**Pass.**

Q2 (lines 53-59) locks the native Solid 2 beta primitives:

> use Solid 2 beta's native effect primitives with the required handler;
> do not switch to `createReaction`. ... the legacy path should use
> `solid.createRenderEffect(runner, legacyEffectHandler)`.

Anti-scope (line 226) explicitly forbids monkeypatching:

> Do not monkeypatch `node_modules`, global Solid exports, or TanStack
> packages.

The fix is local to `services/web/src/solid-compat/solid.ts`. No global
mutation, no `Object.defineProperty` on imports, no patching of
`@solidjs/signals` or `@tanstack/solid-query`.

## C3 — Tests genuinely exercise the legacy one-arg path

**Pass.**

TG-1 (lines 159-181) names the one-arg cases explicitly:

- `createEffect(fn)` — exact failure path
- `createRenderEffect(fn)` — the TanStack Query call site that crashes
- `createComputed(fn)` — alias inheritance check
- `onMount(fn)` — indirect path through shim's `createEffect`
- `createResource(fetcher)` — internal raw `solid.createEffect(() => …)`
  at `services/web/src/solid-compat/solid.ts:151`

The two-arg paths are covered separately so the native-handler branch
doesn't regress: `createEffect(fn, initialValue)`, `createEffect(fn,
nativeHandler)`, `createRenderEffect(fn, initialValue)`,
`createRenderEffect(fn, nativeHandler)`.

Lines 184-185 explicitly bar import-only smoke:

> The assertions must check both "no throw" and an observable side effect.
> A test that only imports the module is insufficient because the failure
> occurs when the effect flushes.

This rules out a test that passes the type checker but never flushes the
effect. TG-2 adds a Playwright bootstrap spec that loads the built SPA and
asserts no `Cannot read properties of undefined (reading 'effect')` page
error and a non-empty `#root` — closes the loop with the actual cluster
failure mode in `research/30-bug-1-admin-route-rca.md:77`.

## C4 — Audit of other shim entry points isn't "trust me"

**Pass — actually traced.**

Q3 (lines 71-102) walks each export with a file:line citation.
Cross-checked against the actual file contents:

| Entry point | Audit claim | File evidence |
|---|---|---|
| `createEffect` | bug, routes through `createLegacyEffect` | solid.ts:99-111 ✓ |
| `createComputed` | alias of `createEffect` | solid.ts:113 ✓ |
| `createRenderEffect` | bug, observed crash site | solid.ts:115-127 ✓ |
| `onMount` | indirect via shim `createEffect` | solid.ts:68-71 ✓ |
| `createResource` | **internal** raw `solid.createEffect(() => …)` | solid.ts:151 ✓ |
| `createSignal` | safe — `@solidjs/signals` doesn't deref second arg | prod.js:1924-1926 ✓ |
| `Index` | delegates to `solid.For`, no raw effect | solid.ts:56-65 ✓ |
| `For`, `Show` | re-exports, not local wrappers | (re-exported via `export *`) ✓ |
| `batch`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `on` | no raw effect primitives | confirmed by reading lines 6-54, 129-144 ✓ |

The catch on `createResource` (line 91 of the proposal) is the meaningful
one — its raw `solid.createEffect(() => …)` at solid.ts:151 would crash the
same way the TanStack Query call did, and it would not be covered by
fixing only the explicit `createLegacyEffect` path. The proposal correctly
routes it through the fixed legacy helper.

## C5 — No "TODO: revisit when Solid 2 is stable" stubs

**Pass.**

Anti-scope explicitly forbids deferred stubs (lines 232-233):

> Do not create deferred stubs or TODO comments. The shim repair and tests
> are complete in the implementation phase.

The fix changes call signatures inside an existing helper; it doesn't
introduce parallel APIs, feature flags, or compatibility branches that
would need future cleanup. Anti-scope also bars adding "a parallel
`solid-js` API surface, new alias module, feature flag, compatibility mode
switch, deprecated export, or fallback branch" (line 228).

The Pomerium drift (section 6) is the only deferred item, and it is
explicitly scoped *out* of BUG-1 and recorded as a separate Bug #5 — that
is correct triage, not a TODO stub embedded in the fix.

## Findings worth carrying into implementation

These are not blockers — the shortcut review is LOW — but the
implementation phase should preserve them:

1. **Don't collapse the runner.** When the implementation lands, the
   runner closure inside `createLegacyEffect` must still capture `previous`
   and reassign it on each pass. A drive-by simplification of the form
   `solid.createEffect(() => effect(undefined), () => {})` would silently
   break legacy `createEffect(fn, initialValue)` previous-result threading.
   The TG-1 case `createEffect(fn, initialValue)` "preserves the previous
   result for later runs" guards this.

2. **`createResource` must route through the fixed helper, not the
   exported `createEffect`.** Either is technically OK (the exported
   `createEffect` is just `arguments.length === 1 → createLegacyEffect`),
   but the proposal specifies the fixed helper directly, which avoids
   re-entering arity dispatch from internal code.

3. **Don't pass `{}` as the handler.** Q1 calls this out explicitly: in
   Solid 2 beta, `@solidjs/signals` reads `t.effect || t`; `{}` would skip
   the immediate dereference but then become a non-callable handler that
   fails on flush. The handler must be a function.

## Verdict

LOW. No shortcuts. The proposal:

- preserves the runner closure that does the legacy threading
- uses native Solid 2 primitives with a handler argument, not a
  monkeypatch
- writes tests that flush effects and assert observable side effects, not
  just import smoke
- traces every other shim export against the file with line numbers, and
  catches the non-obvious internal `createResource` raw effect at
  solid.ts:151
- forbids deferred stubs / TODOs / feature flags in anti-scope

The fix is appropriately narrow (20-35 lines in solid.ts, ~90-140 lines of
new tests) and does not blur into the Pomerium drift, which is correctly
spun out as a separate bug.

SHORTCUT_DONE: plans/risk/bug-1-shortcut.md
