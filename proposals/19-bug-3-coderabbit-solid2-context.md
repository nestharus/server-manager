# Proposal 19 - BUG-3: CodeRabbit Solid 2 beta review context

## 1. Problem statement

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

## 2. Decisions

### Q1. Where does the Solid 2 beta context live?

Lock: add a repository-root `.coderabbit.yaml`.

The Solid 2 beta context should live in CodeRabbit's own repository
configuration, at the same repository-root level as `AGENTS.md`, rather than
as another section in `AGENTS.md`. CodeRabbit's docs identify
`.coderabbit.yaml` as the repository-root customization file, and
`reviews.path_instructions` is the direct mechanism for telling CodeRabbit how
to review specific paths. `AGENTS.md` remains process guidance for coding
agents and is already large; adding tool-specific Solid semantics there would
mix review-runtime configuration with human/agent workflow policy.

### Q2. Path scope: global or only `services/web/**`?

Lock: scope the instruction to `services/web/**`.

The false positives are specific to the Solid web application and its tests.
The API service, Discord daemon, migrations, infrastructure plans, and product
strategy documents should not inherit Solid-specific review assumptions.
CodeRabbit's path instructions support glob-scoped review guidance, so the
proposal should use one `reviews.path_instructions` entry for
`services/web/**`.

Do not use `reviews.path_filters` for this bug. The goal is to keep
CodeRabbit reviewing the affected web files with correct framework context,
not to exclude them from review.

### Q3. Format: markdown vs YAML inline strings?

Lock: use markdown bullets inside a YAML block scalar.

The config should be YAML because `.coderabbit.yaml` is the substrate, but the
`reviews.path_instructions[].instructions` value should be free-form markdown
text using a `|` block scalar. CodeRabbit's configuration reference defines
`instructions` as a string with additional review guidance, and the path
instructions examples show multi-line free-form text under that field.
Markdown bullets keep the Solid 2 facts readable and diffable without forcing
long escaped YAML strings.

### Q4. What specific patterns are called out?

Lock this exact instruction bullet list for `services/web/**`:

- This package intentionally uses `solid-js@2.0.0-beta.8`,
  `@solidjs/web@2.0.0-beta.8`, and `@solidjs/signals@2.0.0-beta.8`.
  Prefer the installed beta package types, runtime files, and package exports
  over public Solid 1/stable documentation when reviewing `services/web/**`.
- In this Solid 2 beta, `<For>` child callbacks receive accessors:
  `(item: Accessor<T>, index: Accessor<number>) => U`. Calling `item()` and
  `index()` is correct; do not suggest raw item property access such as
  `item.id` for `<For>` callback parameters.
- In this Solid 2 beta, `<Show>` callback children receive an accessor for the
  narrowed `when` value. Calling the callback parameter, such as `value()`, is
  correct.
- SSR/web helpers are imported from `@solidjs/web` in this beta. Do not suggest
  changing `renderToString` imports to `solid-js/web`; `solid-js/web` is not
  exported by the installed `solid-js@2.0.0-beta.8` package.
- In this Solid 2 beta, `createContext` returns a callable provider function
  with `id` and `defaultValue`; it does not return an object with a native
  `.Provider` property. The local compat shim may intentionally attach a
  Solid 1-style `.Provider` wrapper.
- Solid 2 beta native `createEffect` and `createRenderEffect` require an
  effect handler argument. The local compat shim intentionally preserves
  legacy `createEffect(fn)` / `createRenderEffect(fn)` call sites by routing
  them through handler-supplying compatibility paths.

### Q5. Use `@coderabbitai ignore` comments inline, or rely on path instructions?

Lock: rely solely on `reviews.path_instructions`; do not add
`@coderabbitai ignore` to source call sites.

The official `@coderabbitai ignore` command is a PR-description control that
permanently disables automatic reviews for that PR. It is not a documented
inline source-code suppression for individual call sites, and disabling review
would hide real bugs in the same files. Ordinary source comments already
failed to stop recurring false positives for `@solidjs/web`, so scattering
more comments through the code is not the durable mechanism.

### Q6. Knowledge base: persistent "always-true" facts?

Lock: CodeRabbit does support persistent learnings, but this proposal should
not seed them as part of the repository change.

CodeRabbit's Knowledge Base docs describe learnings as persistent
natural-language review preferences that can apply to particular files, an
entire repository, or an organization. That satisfies the capability question:
project-level facts can persist across PRs. However, learnings live outside the
source-controlled diff and can be edited or scoped through the CodeRabbit
service. For this bug, the primary fix should be auditable repository config:
`.coderabbit.yaml` with `reviews.path_instructions`.

If TG-1 still shows canonical Solid 2 beta false positives after the config
lands, a later operational follow-up may add CodeRabbit learnings through a PR
comment or the CodeRabbit UI. That is not part of the locked implementation
scope for BUG-3.

## 3. Substrate

### New files

- `.coderabbit.yaml`
  - Repository-root CodeRabbit config.
  - Skeleton:

    ```yaml
    # yaml-language-server: $schema=https://coderabbit.ai/integrations/schema.v2.json
    reviews:
      path_instructions:
        - path: "services/web/**"
          instructions: |
            [Solid 2 beta review instructions from Q4]
    ```

- `docs/coderabbit-solid2-false-positive-baseline.md`
  - Tracked baseline of recurring CodeRabbit false positives from the RCA, used
    by future review runs to detect regressions in review context.
  - Skeleton:

    ```markdown
    # CodeRabbit Solid 2 Beta False-Positive Baseline

    Source RCA: research/32-bug-3-coderabbit-foraccessor-rca.md

    ## Canonical Patterns

    1. For accessor callback parameters
    2. Show accessor callback parameters
    3. @solidjs/web renderToString import
    4. createContext callable provider return shape
    5. Legacy effect handler arity in the compat shim

    ## Historical Evidence

    [Condensed log references from the RCA symptom catalog]

    ## Regression Check

    [Checklist used after future CodeRabbit runs]
    ```

### Modified files

None.

Do not modify Solid source, tests, package versions, AGENTS.md, or the
CodeRabbit review loop in this phase. The eventual implementation should only
add the two files above unless hookpoint research finds an already-existing
repository-level CodeRabbit config in another branch that must be merged.

## 4. Test plan

### TG-1: representative CodeRabbit rerun

After `.coderabbit.yaml` lands, re-run CodeRabbit on a representative
BUG-1-ish PR or local branch that touches the Solid compat shim and web route
surfaces:

```bash
coderabbit review --plain --base main --cwd <project-dir>
```

Acceptance:

- CodeRabbit still reviews `services/web/**` files.
- It does not re-emit the canonical Solid 2 beta false positives:
  `<For>` callback parameters treated as raw values, `<Show>` callback
  parameters treated as raw values, `renderToString` import changed to
  `solid-js/web`, `createContext` assumed to have native `.Provider`, or legacy
  compat effect arity treated as a mistake.
- Any remaining findings are reviewed on their own merits instead of being
  dismissed as part of the BUG-3 false-positive family.

### TG-2: baseline snapshot

Create `docs/coderabbit-solid2-false-positive-baseline.md` from the RCA's
symptom catalog before rerunning reviews.

Acceptance:

- The baseline records the five canonical pattern families and representative
  historical log references.
- TG-1 results are compared against the baseline.
- If a future CodeRabbit run repeats one of the baseline patterns, the
  regression is visible without rereading every historical `.tmp/**/coderabbit`
  log.

## 5. Anti-scope

- Do not add `@coderabbitai ignore` scattered through source code.
- Do not add `@coderabbitai ignore` to PR descriptions as the BUG-3 fix.
- Do not bump CodeRabbit CLI or service configuration versions.
- Do not add lint rules, AST-grep instructions, or custom pre-merge checks.
- Do not change Solid package versions.
- Do not change `services/web/src/solid-compat/solid.ts`.
- Do not change web route code to satisfy Solid 1/stable assumptions.
- Do not edit `AGENTS.md` for Solid 2 beta context in this proposal.

## 6. Diff budget

Estimated implementation diff: 2 new files, no modified code files.

- `.coderabbit.yaml`: about 25-45 lines.
- `docs/coderabbit-solid2-false-positive-baseline.md`: about 70-120 lines.

Total budget: about 95-165 added lines. No runtime code, test code, dependency
lockfiles, migrations, or live Discord-visible changes.
