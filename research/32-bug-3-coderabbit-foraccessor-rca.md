# RCA: CodeRabbit Solid 2 beta For/Show accessor false positives

Date: 2026-04-30

Scope: RCA only. This document does not propose or select a fix.

## Summary

CodeRabbit repeatedly applies Solid 1 / stable-doc assumptions to this repo's
Solid 2 beta install. The project pins `solid-js@2.0.0-beta.8`,
`@solidjs/web@2.0.0-beta.8`, and `@solidjs/signals@2.0.0-beta.8`
(`services/web/package.json:23`, `services/web/package.json:33`;
package metadata confirms the same versions in
`services/web/node_modules/*/package.json`). In this beta:

- `For` children receive accessors, not raw values:
  `children: (item: Accessor<T[number]>, index: Accessor<number>) => U`
  (`services/web/node_modules/solid-js/types/client/flow.d.ts:19-23`,
  same in server types).
- `Show` callback children receive an accessor for the narrowed `when` value:
  `ConditionalRenderCallback<T> = (item: Accessor<NonNullable<T>>) => JSX.Element`
  (`services/web/node_modules/solid-js/types/client/flow.d.ts:4-6`,
  `:47-52`).
- `createContext` returns a callable provider function with `id` and
  `defaultValue`, not an object with a native `.Provider` property
  (`services/web/node_modules/solid-js/dist/solid.js:6-17`).
- `solid-js` does not export `./web`; the web package exists as
  `@solidjs/web` (`services/web/node_modules/solid-js/package.json:25-115`,
  `services/web/node_modules/@solidjs/web/package.json:31-116`, and
  `services/web/node_modules/solid-js/web` is absent).

The recurrence is not caused by one bad local code pattern. It is caused by
review context missing the repo's actual framework version semantics, combined
with CodeRabbit's generic Solid knowledge matching Solid 1/stable behavior.

## Required Reading Completed

- `AGENTS.md`: only CodeRabbit guidance is the review loop and "rerun until
  clean"; no Solid-specific CodeRabbit instructions are present
  (`AGENTS.md:155-171`).
- `coderabbit --help`: CLI supports `review`, `stats`, `feedback`, `update`,
  with review modes `--plain`, `--agent`, `--interactive`.
- `coderabbit review --help`: review supports `--files`, `--dir`, `--config`,
  `--base`, `--base-commit`, `--type`, `--prompt-only`.
- `.tmp/init-133B-*`, `.tmp/init-134`, `.tmp/init-135`, and
  `.tmp/bug-1-admin-timeout/phase7` CodeRabbit logs were searched. There are
  no matching `coderabbit*.log` files under `.tmp/init-131` or `.tmp/init-132`.
- CodeRabbit docs were reachable at `https://docs.coderabbit.ai/`.

## Symptom Catalog

### Pattern 1: `For` state filter accessors flagged as raw strings

Affected source: `services/web/src/features/officer/ApplicationQueueRoute.tsx`
currently uses:

- `state()` in filter class, `aria-pressed`, click handler, and label
  (`services/web/src/features/officer/ApplicationQueueRoute.tsx:154-165`).

CodeRabbit said:

- beta-i r2: "In SolidJS, `<For>` passes the item directly, not as a signal
  accessor. Calling `state()` will throw" for
  `ApplicationQueueRoute.tsx` lines 145-156
  (`.tmp/init-133B-i/phase7/coderabbit-r2.log:106-127`).
- beta-i r3: same claim for lines 145-156
  (`.tmp/init-133B-i/phase7/coderabbit-r3.log:162-183`).
- beta-i r4: "state is not an accessor in Solid's For loop" for lines 150-161
  (`.tmp/init-133B-i/phase7/coderabbit-r4.log:201-224`).
- beta-i r5: "state from `<For>` callback is not a signal" for lines 149-160
  (`.tmp/init-133B-i/phase7/coderabbit-r5.log:160-185`).
- beta-ii r1: same claim for lines 150-161
  (`.tmp/init-133B-ii/coderabbit-r1.log:257-280`).
- beta-ii r3: same claim for lines 150-161
  (`.tmp/init-133B-ii/coderabbit-r3.log:156-179`).
- beta-ii r4: same claim for lines 154-165
  (`.tmp/init-133B-ii/coderabbit-r4.log:231-254`).
- beta-ii r5: same claim for lines 154-165
  (`.tmp/init-133B-ii/coderabbit-r5.log:211-234`).

Actual Solid 2 beta semantic: `For` child `state` is an `Accessor<T[number]>`;
calling `state()` is required.

### Pattern 2: `For` application row accessors flagged as raw objects

Affected source: `services/web/src/features/officer/ApplicationQueueRoute.tsx`
currently uses `application().id`, `application().state`, and passes
`application()` to `claim` (`:185-221`).

CodeRabbit said:

- beta-i r2: "`application` parameter from `<For>` is the item object, not a
  signal accessor" for lines 176-205
  (`.tmp/init-133B-i/phase7/coderabbit-r2.log:163-198`).
- beta-i r3: "application is the item value, not a signal accessor" for lines
  177-205 (`.tmp/init-133B-i/phase7/coderabbit-r3.log:85-120`).
- beta-i r4: "application is not an accessor in Solid's For loop" for lines
  181-210 (`.tmp/init-133B-i/phase7/coderabbit-r4.log:259-296`).
- beta-i r5: "application from `<For>` is not a signal" for lines 180-209
  (`.tmp/init-133B-i/phase7/coderabbit-r5.log:94-131`).
- beta-ii r1: same claim for lines 181-217
  (`.tmp/init-133B-ii/coderabbit-r1.log:318-356`).
- beta-ii r3: same claim for lines 181-217
  (`.tmp/init-133B-ii/coderabbit-r3.log:187-227`).
- beta-ii r4: same claim for lines 185-221
  (`.tmp/init-133B-ii/coderabbit-r4.log:183-223`).
- beta-ii r5: same claim for lines 185-221
  (`.tmp/init-133B-ii/coderabbit-r5.log:131-171`).

Actual Solid 2 beta semantic: `application` is an accessor for the array item.
The correct property access is `application().id`, not `application.id`.

### Pattern 3: `For` tuple/object rows in detail panels flagged as raw values

Affected source:

- `ApplicationDetailRoute.tsx` metadata rows use `row()[0]` and `row()[1]`
  (`services/web/src/features/officer/ApplicationDetailRoute.tsx:129-138`).
- response tuples use `entry()[0]` and `entry()[1]` (`:151-160`).
- transcript entries pass `entry()` (`:176-181`).

CodeRabbit said:

- beta-ii r1: row, response, and transcript callbacks are "not accessors"
  (`.tmp/init-133B-ii/coderabbit-r1.log:104-161`,
  `.tmp/init-133B-ii/coderabbit-r1.log:169-194`).
- beta-ii r3: repeats `entry()` and row claims
  (`.tmp/init-133B-ii/coderabbit-r3.log:125-148`,
  `.tmp/init-133B-ii/coderabbit-r3.log:259-280`).
- beta-ii r5: repeats application, responses, transcript, row claims
  (`.tmp/init-133B-ii/coderabbit-r5.log:180-203`,
  `.tmp/init-133B-ii/coderabbit-r5.log:242-276`).

Actual Solid 2 beta semantic: these callback parameters are accessors, even
when the array element itself is a tuple or object.

### Pattern 4: `For` transition actions flagged as raw strings

Affected source: `ApplicationTransitionActions.tsx` uses `action()` for button
variant, test id, forbidden check, click handler, and label
(`services/web/src/features/officer/ApplicationTransitionActions.tsx:103-119`).

CodeRabbit said:

- beta-iii r1: "`action` parameter should be referenced as a value, not called
  as a function" for lines 103-119
  (`.tmp/init-133B-iii/coderabbit-r1.log:63-82`).
- beta-iii r3: repeats the same claim for lines 103-119
  (`.tmp/init-133B-iii/coderabbit-r3.log:72-91`).

Actual Solid 2 beta semantic: `action` is an accessor for the item. `action()`
is correct.

### Pattern 5: `For` test accessor cast called fragile

BUG-1 r1 flagged a test that cast `solid.For(...)` to `solid.Accessor`
(`.tmp/bug-1-admin-timeout/phase7/coderabbit-r1.log:53-76`). The local follow-up
removed that cast and moved the assertion to rendered SSR output
(`.tmp/bug-1-admin-timeout/phase7/STEP7_R1_DONE.md:6-7`). This was a real test
shape concern, but it became part of the broader pattern because subsequent
rounds still treated Solid 2 beta control-flow return/callback behavior as
stable Solid 1 behavior.

Actual Solid 2 beta semantic: relying on rendered output was the safer test
contract; this does not imply that `For` child parameters are raw values.

### Pattern 6: `@solidjs/web` import flagged as nonstandard or internal

Affected source: `services/web/tests/solid-compat.spec.ts` imports
`renderToString` from `@solidjs/web` and now includes a comment warning that
`solid-js/web` does not exist for this beta (`:1-4`).

CodeRabbit said:

- BUG-1 r2: "Change import path to `solid-js/web`"
  (`.tmp/bug-1-admin-timeout/phase7/coderabbit-r2.log:111-121`).
- BUG-1 r4: "Use the standard import path `solid-js/web` instead of
  `@solidjs/web`" (`.tmp/bug-1-admin-timeout/phase7/coderabbit-r4.log:38-47`).
- BUG-1 r6: "`@solidjs/web` package is internal and not intended for direct
  imports" (`.tmp/bug-1-admin-timeout/phase7/coderabbit-r6.log:19-26`).

Actual Solid 2 beta semantic: `solid-js@2.0.0-beta.8` has no `./web` export and
no `services/web/node_modules/solid-js/web` directory. `@solidjs/web` is the
installed package that exports SSR/web helpers for this beta.

### Pattern 7: `createContext` `.Provider` shape inferred from Solid 1/stable

Affected source: the compatibility wrapper creates a Solid 1-style `.Provider`
wrapper around Solid 2 beta's callable context provider
(`services/web/src/solid-compat/solid.ts:16-20`).

CodeRabbit said:

- BUG-1 r2: "Remove the incorrect Provider assignment from createContext"
  because Solid supposedly already provides `.Provider`
  (`.tmp/bug-1-admin-timeout/phase7/coderabbit-r2.log:129-138`).
- BUG-1 r3: "Use `context.Provider` instead of `context` when creating the
  Provider component" (`.tmp/bug-1-admin-timeout/phase7/coderabbit-r3.log:91-109`).

Actual Solid 2 beta semantic: runtime `createContext` defines `function
provider(props)`, attaches `id` and `defaultValue`, and returns the function.
There is no native `.Provider` property in the runtime object returned from
`solid.createContext` (`services/web/node_modules/solid-js/dist/solid.js:6-17`).

### Pattern 8: `Show` child accessors were vulnerable to the same model error

Affected source: `Show` callback children call the narrowed value as an
accessor, for example `message()` in
`ApplicationQueueRoute.tsx:168-173` and `action` in
`ApplicationTransitionActions.tsx:121-124`.

Observed log evidence is lighter than the `For` findings: most explicit
CodeRabbit comments targeted `For`, but the symptom family includes the same
underlying mismatch. The installed Solid 2 beta type explicitly defines `Show`
callback children as accessors (`flow.d.ts:4-6`, `:47-52`), and the runtime
passes `child(() => conditionValue())` (`solid.js:771-786`).

### Negative evidence: INIT-134 and INIT-135 logs

The requested INIT-134 and INIT-135 logs were searched. I found no explicit
`For`/`Show` accessor, `@solidjs/web`, or `createContext.Provider` findings in
INIT-134 r1-r3 or INIT-135 r1-r8. Those rounds contain other CodeRabbit
findings, some of them debatable, but not the canonical Solid 2 beta accessor
false positives cataloged above.

## CodeRabbit Config Audit

### Current repository state

- No root `.coderabbit.yaml`, `.coderabbit.yml`, `coderabbit.yaml`, or
  `coderabbit.yml` exists.
- No `services/web/.coderabbit.yaml` exists.
- No `.github` CodeRabbit config or GitHub Copilot instruction file exists in
  this checkout.
- `AGENTS.md` is present and contains the CodeRabbit review-loop requirement,
  but it does not mention Solid 2 beta, `For` accessors, `Show` accessors,
  `@solidjs/web`, or `createContext` semantics.

### CLI surface

`coderabbit review --help` shows local scoping and instruction options:

- `--files <files...>`: review only specified files.
- `--dir <path>`: review only git changes inside a directory.
- `--config <files...>`: pass additional instructions for CodeRabbit AI.
- `--prompt-only`: print the agent prompts.
- `--type`, `--base`, `--base-commit`: control the diff under review.

These are invocation-time controls. The current AGENTS loop uses
`coderabbit review --plain --base main --cwd <project-dir>` and does not pass
extra Solid-specific config.

### Repository YAML surface

CodeRabbit docs state that behavior can be customized via a repository-root
`.coderabbit.yaml` file:
<https://docs.coderabbit.ai/reference/configuration>.

Relevant documented knobs:

- `reviews.path_filters`: include or exclude paths using glob patterns.
  Excludes start with `!`; includes can override default excludes.
  Docs: <https://docs.coderabbit.ai/configuration/path-instructions>.
- `reviews.path_instructions`: add review guidance scoped to globbed paths.
  The docs explicitly position this for recurring path-specific review gaps.
- `knowledge_base.code_guidelines`: CodeRabbit can scan guideline files such as
  `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, and
  `.github/copilot-instructions.md`; defaults include `**/AGENTS.md`.
  Docs: <https://docs.coderabbit.ai/knowledge-base> and configuration lines for
  `filePatterns` in <https://docs.coderabbit.ai/reference/configuration>.
- `knowledge_base.web_search.enabled`: web search is configurable and defaults
  to enabled per docs.
- `reviews.auto_review.labels`, `ignore_title_keywords`, `ignore_usernames`,
  `drafts`, `base_branches`, and `description_keyword`: PR-level automatic
  review eligibility controls. Docs:
  <https://docs.coderabbit.ai/configuration/auto-review>.
- `reviews.tools.ast-grep`: AST-based instructions can add structural rules
  for automated review context. Docs:
  <https://docs.coderabbit.ai/configuration/ast-grep-instructions>.
- `reviews.pre_merge_checks.custom_checks`: natural-language pass/fail checks
  in the walkthrough, but docs say these cannot modify review comments and
  should use path instructions for review behavior. Docs:
  <https://docs.coderabbit.ai/pr-reviews/custom-checks>.

### Per-file directives

I found no official CodeRabbit source-code directive comparable to
`// coderabbit:ignore-next-line` in the docs search. Documented controls are PR
commands, YAML config, path filters, path instructions, code guidelines,
knowledge-base learnings, and CLI `--config`/`--files`/`--dir`.

There is a plain source comment in `services/web/tests/solid-compat.spec.ts:2-3`
explaining the `@solidjs/web` import. BUG-1 r6 still flagged that import after
similar evidence existed in previous rounds, so ordinary in-code comments are
not reliable as a suppression mechanism.

### Per-PR commands and labels

Documented per-PR commands include:

- `@coderabbitai pause`
- `@coderabbitai resume`
- `@coderabbitai ignore` in the PR description
- `@coderabbitai review`
- `@coderabbitai full review`
- `@coderabbitai resolve`
- `@coderabbitai configuration`

Docs: <https://docs.coderabbit.ai/reference/review-commands>.

Labels can control whether a PR is reviewed, including negative labels like
`!wip`, through `reviews.auto_review.labels`. I found no documented mechanism
for a label to make a PR "Solid-aware" or to alter framework semantics other
than by coupling labels with broader review eligibility.

## Root Cause

The root cause is a framework-version context mismatch in CodeRabbit reviews.
CodeRabbit's review model repeatedly assumes stable Solid 1 semantics:

- `For` child argument is a raw item.
- `Show` follows stable callback assumptions unless otherwise typed.
- `solid-js/web` is the canonical web import.
- `createContext` returns a context object with `.Provider`.

This repo is intentionally on Solid 2 beta. In the installed beta packages,
those assumptions are wrong for the affected surfaces. The local source and
tests are using the installed package contract, but CodeRabbit does not appear
to consult or correctly weight the repo's installed `node_modules` types,
package exports, or local compatibility-wrapper evidence when producing these
findings.

Contributing factors:

- No `.coderabbit.yaml` exists to put Solid 2 beta instructions in front of the
  reviewer.
- `AGENTS.md` is auto-detectable as a code-guidelines file, but it contains
  CodeRabbit process instructions only, not the Solid 2 beta contract.
- CodeRabbit can use web search by default, which likely reinforces stable
  public Solid docs over beta package-local semantics.
- The affected code looks unusual to a Solid 1 reviewer because accessors are
  called in places where Solid 1 examples use raw item values.
- Some compatibility files intentionally bridge Solid 1-style consumers onto
  Solid 2 beta runtime packages, which makes the code look like a shim unless
  the reviewer understands the beta package split.

## Affected Surfaces

Most affected files and patterns:

- `services/web/src/features/officer/ApplicationQueueRoute.tsx`
  - `For each={ALL_STATES}` state accessor usage.
  - `For each={items()}` application accessor usage.
  - Nested `Show` callback values.
- `services/web/src/features/officer/ApplicationDetailRoute.tsx`
  - `For` over metadata rows, response tuples, and transcript entries.
- `services/web/src/features/officer/ApplicationTransitionActions.tsx`
  - `For` over valid officer transition actions.
  - `Show` over the active action.
- `services/web/src/solid-compat/solid.ts`
  - `createContext` wrapper and Solid 1-style `.Provider` compatibility.
  - Direct runtime import from `solid-js/dist/solid.js`.
- `services/web/tests/solid-compat.spec.ts`
  - `@solidjs/web` `renderToString` import.
  - SSR smoke tests for `For`, `Show`, and `createContext`.
- `services/web/tsconfig.json` and `services/web/vite.config.ts`
  - compatibility aliases for `solid-js`, `solid-js/web`, and `solid-js/store`.

## Candidate Intervention Points, Not a Fix Proposal

These are possible places the project could intervene. This RCA does not choose
between them.

- Repository `.coderabbit.yaml` with `reviews.path_instructions` for
  `services/web/src/**` and `services/web/tests/**` explaining the Solid 2 beta
  contract.
- Repository `.coderabbit.yaml` with `reviews.path_filters` if a narrow compat
  shim path should be excluded from review.
- Code-guideline context in `AGENTS.md`, `CLAUDE.md`, or
  `.github/copilot-instructions.md`, since CodeRabbit docs say those files are
  scanned as code guidelines by default.
- CLI `coderabbit review --config <file>` in the project review loop, if the
  team wants invocation-time Solid 2 beta instructions without repository YAML.
- Knowledge-base learnings through CodeRabbit chat/review interactions, if the
  service retains and applies those preferences for future reviews.
- AST-based review instructions, if the team wants structural recognition of
  `For`/`Show` callback shapes.
- PR-level controls such as `@coderabbitai pause`, `@coderabbitai ignore`, or
  auto-review labels to reduce review churn on known-problem PRs. These control
  whether/when review runs, not the Solid semantic model itself.

## Conclusion

The recurring findings are false positives rooted in CodeRabbit reviewing a
Solid 2 beta codebase with Solid 1/stable assumptions. The evidence is strongest
for `For` callback accessors, `@solidjs/web`, and `createContext` shape, and the
same installed type/runtime evidence covers `Show` callback accessors. The
repository currently gives CodeRabbit no durable Solid 2 beta context beyond
ordinary code and scattered comments, so the model falls back to public/stable
framework expectations and repeats the same incorrect comments across rounds.
