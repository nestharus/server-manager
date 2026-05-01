# CodeRabbit Solid 2 Beta False-Positive Baseline

Source RCA: `research/32-bug-3-coderabbit-foraccessor-rca.md`

This baseline records recurring CodeRabbit findings that are false positives
for the repo's pinned Solid 2 beta web package. It is for future review
comparison only; it is not a source-code suppression list.

## For Accessor

CodeRabbit repeatedly treated `<For>` callback parameters as raw values even
though `solid-js@2.0.0-beta.8` passes accessors.

Appeared in:

- beta-i r2, r3, r4, and r5 for `ApplicationQueueRoute.tsx` state filters and
  application rows.
- beta-ii r1, r3, r4, and r5 for queue rows, state filters, detail metadata
  rows, response tuples, and transcript entries.
- beta-iii r1 and r3 for transition action rows.
- BUG-1 r1 as a related test-shape concern around casting `solid.For(...)` to
  an accessor; the test concern was addressed, but it did not make `<For>`
  callback parameters raw values.

Canonical non-regression expectation: `item()`, `index()`, `state()`,
`application()`, `row()`, `entry()`, and `action()` are valid when they are
`<For>` callback parameters in `services/web/**`.

## Show Accessor

The RCA records `<Show>` as vulnerable to the same model error. Explicit
CodeRabbit comments mostly targeted `<For>`, but the installed Solid 2 beta
types and runtime pass the narrowed `<Show>` value as an accessor too.

Cataloged in:

- RCA Pattern 8, covering `ApplicationQueueRoute.tsx` and
  `ApplicationTransitionActions.tsx`.
- INIT-134 r1-r3 and INIT-135 r1-r8 were searched as negative evidence; the
  RCA found no explicit `For`/`Show` accessor findings in those rounds.

Canonical non-regression expectation: calling a `<Show>` callback parameter,
such as `message()` or `action()`, is valid in this Solid 2 beta.

## @solidjs/web Import

CodeRabbit repeatedly suggested replacing `@solidjs/web` with `solid-js/web`.
That is wrong for this repo's beta pin: `solid-js@2.0.0-beta.8` does not export
`./web`, while `@solidjs/web@2.0.0-beta.8` is the installed web helper package.

Appeared in:

- BUG-1 r2 for `services/web/tests/solid-compat.spec.ts`.
- BUG-1 r4 for `services/web/tests/solid-compat.spec.ts`.
- BUG-1 r6 for `services/web/tests/solid-compat.spec.ts`.

Canonical non-regression expectation: do not suggest changing
`renderToString` imports from `@solidjs/web` to `solid-js/web`.

## createContext

CodeRabbit inferred a Solid 1/stable `.Provider` shape for `createContext`.
That is wrong for this Solid 2 beta runtime, where `createContext` returns a
callable provider function with `id` and `defaultValue`. The local compat shim
may intentionally attach a Solid 1-style `.Provider` wrapper.

Appeared in:

- BUG-1 r2 for `services/web/src/solid-compat/solid.ts`.
- BUG-1 r3 for `services/web/src/solid-compat/solid.ts`.

Canonical non-regression expectation: do not require the local provider wrapper
to call `context.Provider` as if it were a native property on the returned
Solid 2 beta context.

## Effect Handler Arity

CodeRabbit treated the compat shim's legacy effect paths as invalid or as
ordinary Solid 1/stable overloads, instead of recognizing that native Solid 2
beta `createEffect` and `createRenderEffect` require a handler argument and
the shim intentionally supplies compatibility paths for legacy call sites.

Appeared in:

- beta-i r2 for `services/web/src/solid-js-compat.d.ts` and the legacy
  `createEffect` declaration.
- beta-i r3 for `services/web/src/solid-compat/solid.ts` legacy
  `createEffect` handling and two-callback route effects.
- beta-i r4 for `services/web/src/solid-compat/solid.ts` effect handler
  clarity.
- beta-ii r1 for `services/web/src/solid-js-compat.d.ts` and native handler
  detection.
- beta-ii r3 for `services/web/src/solid-compat/solid.ts` handler shape.
- beta-ii r5 for `services/web/src/solid-compat/solid.ts` legacy effect
  implementation details.

Canonical non-regression expectation: do not suggest deleting handler-supplying
compatibility paths or treating legacy `createEffect(fn)` /
`createRenderEffect(fn)` preservation as accidental.

## Version Pin

The shared root cause is CodeRabbit applying Solid 1/stable public
documentation over the repo's installed beta package versions:
`solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`, and
`@solidjs/signals@2.0.0-beta.8`.

Appeared as the common failed premise in:

- beta-i r2, r3, r4, and r5 through repeated `<For>` raw-value suggestions.
- beta-ii r1, r3, r4, and r5 through repeated `<For>` raw-value suggestions.
- beta-iii r1 and r3 through repeated transition-action raw-value suggestions.
- BUG-1 r2, r3, r4, and r6 through `@solidjs/web` and `createContext`
  Solid 1/stable assumptions.

Canonical non-regression expectation: when reviewing `services/web/**`, prefer
the installed beta package types, runtime files, and package exports over
public Solid 1/stable documentation.

## Regression Check

If a CodeRabbit r1+ review on services/web/** re-flags any of these patterns, .coderabbit.yaml is not being applied.
