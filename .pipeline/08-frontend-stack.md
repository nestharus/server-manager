# Frontend Stack — Research Synthesis v2

## Question

Which frontend stack should `server-manager` use for the Phase 6 web UI, after
correcting the first research round's premises?

Corrected premises:

- The "Cloudflare React fork" described in the first round does not exist as
  described. The second-round question is whether there is some other React
  fork, compiler, runtime, or framework that plausibly matches "React but way
  faster."
- Tailwind is rejected for this project by user preference and team direction.
  The second-round evidence question is narrower: whether primary sources
  support "everyone is using vanilla CSS over Tailwind," and whether modern
  vanilla CSS is technically strong enough for Humility.
- Solid 2 is in scope as a promising option, but TanStack Router is not.
- TanStack remains in scope for non-router packages.
- Tooling preferences are Oxfmt, Oxlint, `tsgo`, and possibly
  `@nkzw/oxlint-config`.
- React Compiler and "Async React" are in scope for the React candidate.
- Styling should be vanilla CSS: CSS Modules, native CSS features, layers,
  custom-property tokens, and small local utilities rather than Tailwind.

This synthesis uses the four second-round findings as binding evidence:

- `.tmp/08-frontend-stack-A-findings.md` - React fork identification.
- `.tmp/08-frontend-stack-B-findings.md` - Solid 2 and non-TanStack Solid router.
- `.tmp/08-frontend-stack-C-findings.md` - Oxc, Oxfmt, Oxlint, `tsgo`, React
  Compiler, and Async React.
- `.tmp/08-frontend-stack-D-findings.md` - Modern vanilla CSS.

`research/07-frontend-stack.md` is background only.

## Evidence-vs-premise gaps

- **"React fork that makes it way faster": not found as stated.** Researcher A
  found no single project that is literally a React fork, performance-marketed,
  mostly drop-in compatible, and actively maintained in 2025-2026. The closest
  remembered name is probably Million.js, but it is an optimizing compiler layer,
  not a React fork, and its npm package has not shipped since 2024-06-04.
  The current production-ready React performance story is upstream React
  Compiler 1.0, not a fork. Citation: `.tmp/08-frontend-stack-A-findings.md`,
  sections "Identified project", "Candidate 1: Million.js", and "Candidate 2:
  React Compiler / React Forget".

- **"Everyone using vanilla CSS over Tailwind": not proven by primary sources.**
  Researcher D found strong technical evidence that browser-native CSS is now
  capable enough for an evergreen SPA, but did not find primary-source evidence
  for a broad industry migration away from Tailwind. Vercel has Geist and also
  publishes Tailwind templates; Solid docs list CSS Modules and Tailwind among
  supported choices. Citation: `.tmp/08-frontend-stack-D-findings.md`, sections
  "Real-world SPA examples that ship without Tailwind in 2026" and "'Everyone is
  doing this' sanity check".

- **Solid 2 is not production-stable yet.** Solid 2 exists only on prerelease
  tracks in the evidence: `solid-js@2.0.0-beta.8` on `next`, with no RC or GA
  release as of 2026-04-26. The official `latest` line remains
  `solid-js@1.9.12`. Citation: `.tmp/08-frontend-stack-B-findings.md`, sections
  "Solid 2 readiness summary" and "Adapter readiness matrix".

- **TanStack without Router is coherent, but weaker on route typing.**
  `@solidjs/router` is the official Solid router and the right non-TanStack
  Solid answer. The tradeoff is that TanStack Router is stronger for typed route
  params, typed search params, route trees, and devtools. Citation:
  `.tmp/08-frontend-stack-B-findings.md`, section "Canonical Solid router
  (non-TanStack)".

- **`@nkzw/oxlint-config` is React-shaped.** It is real and current, but its
  rule set includes React, React Hooks, and React Compiler-oriented hooks rules.
  Researcher C calls out that it is not a clean Solid-only preset without
  overrides. Citation: `.tmp/08-frontend-stack-C-findings.md`, sections
  "@nkzw/oxlint-config" and "How they wire together for a Solid SPA project".

- **`tsgo` and Oxfmt are still beta/non-GA in strict terms.** They are real and
  credible, but Oxfmt is beta and `tsgo` is TypeScript 7.0 beta/native preview.
  The safer posture is to pin them and keep TypeScript 6 available where tools
  import the TypeScript JS API. Citation: `.tmp/08-frontend-stack-C-findings.md`,
  sections "Oxfmt" and "tsgo".

## Stack candidates

### Candidate 1: Solid 2 + TanStack (ex-Router) + @solidjs/router + Vanilla CSS + Oxc/tsgo

Components:

| Layer | Pick |
| --- | --- |
| Framework | `solid-js@2.0.0-beta.8` on `next` |
| Router | `@solidjs/router@0.17.0-next.3` for Solid 2 beta |
| Data | `@tanstack/solid-query@6.0.0-beta.4` for explicit Solid 2 beta support |
| Forms | `@tanstack/solid-form@1.29.1`, with compatibility validation against Solid 2 |
| State | Solid signals/stores; TanStack Store only indirectly or if a package needs it |
| Components | Prefer Ark UI over Kobalte if Solid 2 beta is chosen; validate before production |
| Styling | CSS Modules, cascade layers, custom-property tokens, size container queries, `:has()`, OKLCH, subgrid |
| Build | Vite plus `vite-plugin-solid@3.0.0-next.5` for Solid 2 testing |
| Format | `oxfmt@0.46.0` |
| Lint | `oxlint@1.61.0`; avoid unmodified `@nkzw/oxlint-config` unless React rules are disabled |
| Type-check | Pinned `@typescript/native-preview@7.0.0-dev.20260426.1` / `tsgo`, with TS 6 retained initially |

Versions and release dates from the findings:

- `solid-js@1.9.12` stable/latest, published 2026-03-24.
- `solid-js@2.0.0-beta.8` next, published 2026-04-22.
- Solid 2 beta milestone `v2.0.0-beta.0`, released 2026-03-03 as a prerelease.
- `vite-plugin-solid@2.11.12` latest, published 2026-04-05;
  `3.0.0-next.5`, published 2026-04-18.
- `@solidjs/router@0.16.1` latest, published 2026-03-17;
  `0.17.0-next.3`, published 2026-04-26.
- `@tanstack/solid-query@5.100.5` latest, published 2026-04-25;
  `6.0.0-beta.4`, published 2026-04-22, with Solid 2 beta peer range.
- `@tanstack/solid-form@1.29.1`, published 2026-04-21.
- `@tanstack/solid-table@8.21.3` latest, with `9.0.0-alpha.37` alpha modified
  / published 2026-04-26.
- `@tanstack/solid-virtual@3.13.24`, published 2026-04-17.
- `@ark-ui/solid@5.36.2`, published 2026-04-22.
- `@kobalte/core@0.13.11`, published 2025-07-26, with Solid 1 peer range.
- `oxfmt@0.46.0`, published 2026-04-20.
- `oxlint@1.61.0`, published 2026-04-20.
- `@typescript/native-preview@7.0.0-dev.20260426.1`, observed as current on
  2026-04-26.

Pros under the user's constraints:

- Best alignment with the user's stated interest in Solid 2 and rejection of
  TanStack Router.
- `@solidjs/router` is the official Solid router and the canonical
  non-TanStack router.
- TanStack remains usable where it matters for an API-backed dashboard:
  Query, Form, Table, Virtual, and possibly Store.
- Modern vanilla CSS works equally well for Solid 1 and Solid 2 because the
  strategy is Vite/CSS-based, not tied to a runtime styling library.
- Oxc/Oxlint/Oxfmt and `tsgo` are framework-agnostic enough for Solid TSX.

Cons / risks:

- This is not the conservative production default today. Solid 2, the Solid 2
  router track, the Solid 2 Vite plugin track, and TanStack Query's Solid 2
  support are all prerelease.
- Several useful form/component packages do not advertise Solid 2 stable support
  in the findings: Kobalte, Modular Forms, and Felte are on older Solid 1 peer
  ranges or stale release lines.
- TanStack Router's rejection gives up stronger route-level typing, search-param
  schemas, generated route trees, and router devtools.
- The project would need explicit compatibility testing for Ark UI and
  TanStack Form under Solid 2 before proposal work can treat them as safe.
- `@nkzw/oxlint-config` needs adaptation because it includes React-specific
  rules.

Citations to subtopic findings:

- Solid 2 readiness and adapter state: `.tmp/08-frontend-stack-B-findings.md`,
  sections "Solid 2 readiness summary" and "Adapter readiness matrix".
- Solid router: `.tmp/08-frontend-stack-B-findings.md`, section "Canonical
  Solid router (non-TanStack)".
- TanStack Solid packages: `.tmp/08-frontend-stack-B-findings.md`, section
  "TanStack scope (Solid adapters, ex-Router)".
- Oxc/Oxfmt/Oxlint/tsgo: `.tmp/08-frontend-stack-C-findings.md`, sections
  "Oxlint", "Oxfmt", "tsgo", and "How they wire together for a Solid SPA
  project".
- Vanilla CSS: `.tmp/08-frontend-stack-D-findings.md`, sections
  "Browser-native CSS feature matrix (2026 Q2)", "CSS Modules in 2026", and
  "Recommended pattern for a Solid 2 + Vite SPA".

### Candidate 2: React + React Compiler + Async React + TanStack (ex-Router) + (router?) + Vanilla CSS + Oxc/tsgo

Candidate 2 stays on upstream React. The evidence does not support choosing a
third-party "React fork" as the React candidate.

Components:

| Layer | Pick |
| --- | --- |
| Framework | Upstream `react@19.2.5` / `react-dom@19.2.5` |
| Performance | `babel-plugin-react-compiler@1.0.0` plus compiler lint rules in `eslint-plugin-react-hooks@7.1.1` |
| Async UI | Stable React 19 APIs where applicable: Suspense, `use()`, Actions/transitions, `cache()`, `cacheSignal()`, and `<Activity>` |
| Router | Unresolved in this round; must be non-TanStack if the router ban applies equally to React |
| Data | TanStack Query is presumed in-scope by "TanStack ex-Router", but React package versions were not researched in the second round |
| Forms | TanStack Form is presumed in-scope by "TanStack ex-Router", but React package versions were not researched in the second round |
| State | React state plus TanStack package state as needed |
| Components | Accessible primitive/library choice unresolved by second-round React evidence |
| Styling | Same vanilla CSS strategy: CSS Modules, layers, tokens, container queries, `:has()`, OKLCH, subgrid |
| Build | Vite 8 with React plugin; React Compiler wiring uses `@rolldown/plugin-babel` plus `reactCompilerPreset()` |
| Format | `oxfmt@0.46.0` |
| Lint | `oxlint@1.61.0`; `@nkzw/oxlint-config@1.1.1` fits this candidate better than Solid |
| Type-check | Pinned `@typescript/native-preview@7.0.0-dev.20260426.1` / `tsgo`, with TS 6 retained initially |

Versions and release dates from the findings:

- `react@19.2.5` and `react-dom@19.2.5` observed as current stable.
- `babel-plugin-react-compiler@1.0.0`, published 2025-10-07; React Compiler
  1.0 is described as stable and production-ready in the findings.
- `react-compiler-runtime@1.0.0`, published 2025-10-07, for older React targets.
- `eslint-plugin-react-hooks@7.1.1` observed current.
- React canary observed as `19.3.0-canary-561ed529-20260423`; this matters only
  for canary-only APIs such as `<ViewTransition>`.
- `vite@8.0.10`, `@vitejs/plugin-react@6.0.1`, and
  `@vitejs/plugin-react-swc@4.3.0` observed current.
- `@nkzw/oxlint-config@1.1.1`, published 2026-04-20.
- `oxfmt@0.46.0`, published 2026-04-20.
- `oxlint@1.61.0`, published 2026-04-20.
- `@typescript/native-preview@7.0.0-dev.20260426.1`, observed as current on
  2026-04-26.

Pros under the user's constraints:

- It keeps the project on upstream React rather than betting on an unverified or
  stale "React fork."
- React Compiler is the strongest current evidence-backed answer for "React got
  faster"; it is GA and production-ready in the findings.
- Async React is a real 2026 API cluster, but the stable pieces can be used
  selectively without adopting canary-only `<ViewTransition>`.
- `@nkzw/oxlint-config` aligns naturally with React because it includes React
  Hooks and React Compiler-oriented lint coverage.
- React avoids Solid 2 beta ecosystem churn.
- Vanilla CSS strategy is framework-independent and does not require Tailwind.

Cons / risks:

- The router is not resolved by the second-round evidence. If TanStack Router is
  banned for React too, Phase 4 must pick a router before proposal work.
- React Query/Form package versions and React-specific form-renderer choices
  were not part of the binding second-round findings. The old 07 synthesis can
  inform context, but this v2 decision should not pretend that evidence was
  refreshed.
- React Compiler optimizes re-render/memoization behavior; it does not replace
  React's reconciler, a bundler, or general performance work.
- React Compiler still requires lint discipline and test coverage because
  memoization can expose latent Rules of React violations.
- `<ViewTransition>` remains canary-only and should not be part of a production
  Phase 6 baseline.

Citations to subtopic findings:

- React fork identification: `.tmp/08-frontend-stack-A-findings.md`, sections
  "Identified project" and "Recommendation: which name best matches 'react fork
  that makes it way faster'".
- React Compiler and Async React: `.tmp/08-frontend-stack-C-findings.md`,
  sections "React Compiler (current GA state)" and "Async React (what it
  actually means in 2026)".
- Oxc/Oxfmt/Oxlint/tsgo and React wiring: `.tmp/08-frontend-stack-C-findings.md`,
  sections "Oxlint", "Oxfmt", "tsgo", "@nkzw/oxlint-config", and "How they wire
  together for a Solid SPA project".
- Vanilla CSS: `.tmp/08-frontend-stack-D-findings.md`, sections
  "Browser-native CSS feature matrix (2026 Q2)", "CSS Modules in 2026", and
  "Recommended pattern for a Solid 2 + Vite SPA".

## Tradeoff matrix

| Axis | Candidate 1 (Solid 2) | Candidate 2 (React + Compiler) |
| --- | --- | --- |
| Production-readiness today | Medium-low for Phase 6 production because Solid 2 and several adapters are beta/next. Solid 1.9 would be the conservative Solid line, but that is not this candidate. | High for the framework/compiler core: React 19 stable and React Compiler 1.0 GA. Router/forms/component choices still need a Phase 4 pick. |
| Form-renderer fitness for YAML schemas | Good if Humility owns a renderer on TanStack Solid Form, but Solid 2 compatibility needs validation. Off-the-shelf Solid form/component evidence is thinner. | Likely strong by ecosystem breadth, but not proven by this second round. TanStack React Form package versions and schema renderer options need refresh before proposal. |
| Maintenance momentum | Strong but prerelease-heavy: Solid 2 beta, router next, Vite plugin next, Query v6 beta. | Strong in core React and React Compiler. Toolchain pieces are current. React-specific TanStack package evidence was not refreshed in this round. |
| Auth-via-Pomerium fit | Not directly researched. As a browser SPA talking to the Python API, no stack-specific blocker appears in the findings. | Not directly researched. As a browser SPA talking to the Python API, no stack-specific blocker appears in the findings. |
| Risk in 12 months | Medium-high: Solid 2 could settle cleanly, but beta adapter churn may consume Phase 6 time. | Medium: less framework churn, but router/form/component choices are unresolved and React Compiler requires lint/test discipline. |
| User's stated premise alignment | High on Solid 2, non-TanStack Router, TanStack ex-Router, and vanilla CSS. Low on production conservatism unless beta risk is accepted. | High on React Compiler, Async React, upstream React, Oxc/tsgo, and vanilla CSS. Low if the user specifically wanted a non-React framework or an actual React fork. |

## Recommendation

Recommend **Candidate 2: upstream React 19 + React Compiler + stable Async React
APIs + TanStack excluding Router + vanilla CSS + Oxc/Oxfmt/Oxlint/tsgo** for
Phase 6 production proposal work.

Rationale tied to user constraints:

- The React-fork premise did not survive the evidence. The current credible
  performance path is upstream React Compiler, not Million.js, Preact, Inferno,
  Rari, Remix 3, or vinext.
- Solid 2 matches the user's interest, but the binding evidence says it is beta,
  not GA, with prerelease router/build/query tracks. That is acceptable only if
  Phase 6 is allowed to absorb framework and adapter churn.
- Vanilla CSS is a sound project choice, but the defensible reason is technical:
  CSS Modules plus layers, custom properties, container queries, `:has()`, OKLCH,
  and subgrid now cover the app's needs. The claim "Tailwind is dead" should not
  be used as a formal premise.
- The Oxc family and `tsgo` are credible, but `tsgo` and Oxfmt should be pinned
  and adopted with fallback lanes because both are still beta/non-GA in strict
  terms.

If the user explicitly accepts Solid 2 beta risk, Candidate 1 becomes a coherent
forward-looking stack. Without that acceptance, Candidate 2 is the safer
production stack.

## Open questions for user (Phase 4 decision)

1. If you disagree with Researcher A, what is the actual React fork/runtime name
   you had in mind? The closest evidence-backed guesses are Million.js,
   Preact, Inferno, Rari, or a misremembered React Compiler story.
2. Is Solid 2 beta production-readiness acceptable for Phase 6, including
   prerelease router/build/query tracks and explicit compatibility testing?
3. If Candidate 1 is chosen, is `@solidjs/router` confirmed as the Solid router?
4. If Candidate 2 is chosen, does the TanStack Router ban also apply to React,
   and what router should replace it?
5. Which vanilla-CSS-accessible primitive path should proposal work assume:
   Ark UI, Kobalte, pure HTML5 + ARIA, or a React-specific primitive library if
   Candidate 2 wins?
6. Should `@nkzw/oxlint-config` be mandatory only for React packages, or should
   the Solid path use a custom Oxlint config without React rules?

## Draft current problem map

- Build one browser SPA for public applicant flows and authenticated
  officer/admin workflows.
- Keep `services/api/` as the structured mutation/query boundary.
- Treat Pomerium/Authentik as edge auth unless later research shows a
  frontend-specific integration requirement.
- Render existing YAML forms through a project-owned renderer, with per-form
  polish where user-facing quality matters.
- Use a modern CSS architecture that is readable in browser devtools and does
  not depend on Tailwind.
- Keep the stack current without choosing prerelease framework infrastructure
  by accident.

## Draft assumption register

- Phase 6 is production-oriented, not a disposable prototype.
- "TanStack but not TanStack Router" means Query/Form/Table/Virtual remain
  eligible.
- React candidate means upstream React, not a fork.
- React Compiler is additive and lint-gated; it is not a substitute for
  framework/router/form decisions.
- Solid 2 is allowed only if the user explicitly accepts beta risk.
- Vanilla CSS means CSS Modules plus native CSS features, not classless CSS and
  not a no-build styling strategy.
- `tsgo` starts as a pinned fast lane with TS 6 retained for tooling that still
  imports TypeScript's JS API.

## Citations

- https://bun.com/docs/bundler/css
- https://caniuse.com/css-anchor-positioning
- https://caniuse.com/css-cascade-layers
- https://caniuse.com/css-cascade-scope
- https://caniuse.com/css-color-function
- https://caniuse.com/css-container-queries
- https://caniuse.com/css-container-queries-style
- https://caniuse.com/css-has
- https://caniuse.com/css-lch-lab
- https://caniuse.com/css-nesting
- https://caniuse.com/css-subgrid
- https://caniuse.com/css-variables
- https://caniuse.com/mdn-css_types_color_oklch
- https://caniuse.com/view-transitions
- https://caniuse.com/wf-color-mix
- https://caniuse.com/wf-light-dark
- https://caniuse.com/wf-registered-custom-properties
- https://devblogs.microsoft.com/typescript/announcing-typescript-7-0-beta/
- https://devblogs.microsoft.com/typescript/announcing-typescript-native-previews/
- https://docs.solidjs.com/guides/routing-and-navigation
- https://docs.solidjs.com/guides/styling-components/css-modules
- https://docs.solidjs.com/guides/styling-your-components
- https://docs.solidjs.com/solid-router
- https://docs.solidjs.com/solid-router/advanced-concepts/preloading
- https://docs.solidjs.com/solid-start/building-your-application/css-and-styling
- https://docs.solidjs.com/solid-start/building-your-application/routing
- https://facebook.github.io/react-strict-dom/contribute/design-goals/
- https://facebook.github.io/react-strict-dom/learn/
- https://github.com/aidenybai/million
- https://github.com/aidenybai/million/issues/1181
- https://github.com/aidenybai/million/issues/1184
- https://github.com/aidenybai/million/releases
- https://github.com/css-modules/css-modules
- https://github.com/css-modules/css-modules/blob/master/docs/composition.md
- https://github.com/facebook/react
- https://github.com/facebook/react-strict-dom
- https://github.com/infernojs/inferno
- https://github.com/microsoft/typescript-go
- https://github.com/onejs/one
- https://github.com/oxc-project/oxc-resolver
- https://github.com/preactjs/preact
- https://github.com/rari-build/rari
- https://github.com/solidjs/solid-router
- https://github.com/solidjs/solid/releases
- https://github.com/solidjs/solid/releases/tag/v2.0.0-beta.0
- https://github.com/vitejs/vite-plugin-react/releases
- https://infernojs.org
- https://million.dev
- https://newreleases.io/project/github/TanStack/query/release/release-2026-04-22-2157
- https://onestack.dev/
- https://open-props.style/
- https://oxc.rs/
- https://oxc.rs/blog/2026-02-24-oxfmt-beta
- https://oxc.rs/docs/guide/usage/formatter.html
- https://oxc.rs/docs/guide/usage/formatter/config.html
- https://oxc.rs/docs/guide/usage/formatter/migrate-from-prettier
- https://oxc.rs/docs/guide/usage/linter.html
- https://oxc.rs/docs/guide/usage/linter/editors
- https://oxc.rs/docs/guide/usage/linter/js-plugins
- https://oxc.rs/docs/guide/usage/linter/migrate-from-eslint
- https://oxc.rs/docs/guide/usage/linter/multi-file-analysis
- https://oxc.rs/docs/guide/usage/linter/plugins.html
- https://oxc.rs/docs/guide/usage/linter/type-aware
- https://oxc.rs/docs/guide/usage/transformer.html
- https://picocss.com/
- https://preactjs.com/
- https://preactjs.com/guide/v10/getting-started/#aliasing-react-to-preact
- https://raw.githubusercontent.com/infernojs/inferno/master/packages/inferno-compat/README.md
- https://react.dev/blog/2024/12/05/react-19
- https://react.dev/blog/2025/04/23/react-labs-view-transitions-activity-and-more
- https://react.dev/blog/2025/10/01/react-19-2
- https://react.dev/blog/2025/10/07/react-compiler-1
- https://react.dev/blog/2025/10/16/react-conf-2025-recap
- https://react.dev/learn/react-compiler
- https://react.dev/learn/react-compiler/installation
- https://react.dev/reference/react-compiler/compiling-libraries
- https://react.dev/reference/react-compiler/configuration
- https://react.dev/reference/react-compiler/directives/use-no-memo
- https://react.dev/reference/react/Activity
- https://react.dev/reference/react/Suspense
- https://react.dev/reference/react/ViewTransition
- https://react.dev/reference/react/cache
- https://react.dev/reference/react/cacheSignal
- https://react.dev/reference/react/use
- https://registry.npmjs.org/@ark-ui/solid
- https://registry.npmjs.org/@felte/solid
- https://registry.npmjs.org/@kobalte/core
- https://registry.npmjs.org/@modular-forms/solid
- https://registry.npmjs.org/@nkzw/oxlint-config
- https://registry.npmjs.org/@solidjs/router
- https://registry.npmjs.org/@solidjs/start
- https://registry.npmjs.org/@tanstack/solid-db
- https://registry.npmjs.org/@tanstack/solid-form
- https://registry.npmjs.org/@tanstack/solid-pacer
- https://registry.npmjs.org/@tanstack/solid-query
- https://registry.npmjs.org/@tanstack/solid-store
- https://registry.npmjs.org/@tanstack/solid-table
- https://registry.npmjs.org/@tanstack/solid-virtual
- https://registry.npmjs.org/@typescript/native-preview
- https://registry.npmjs.org/@vitejs/plugin-react
- https://registry.npmjs.org/babel-plugin-react-compiler
- https://registry.npmjs.org/eslint-plugin-react-hooks
- https://registry.npmjs.org/oxfmt
- https://registry.npmjs.org/oxlint
- https://registry.npmjs.org/oxlint-tsgolint
- https://registry.npmjs.org/react
- https://registry.npmjs.org/react-compiler-runtime
- https://registry.npmjs.org/solid-js
- https://registry.npmjs.org/vite
- https://registry.npmjs.org/vite-plugin-solid
- https://remix.run/
- https://remix.run/blog/wake-up-remix
- https://rsbuild.dev/guide/styling/css-modules
- https://rsbuild.rs/config/output/css-modules
- https://styledictionary.com/info/tokens/
- https://styledictionary.com/reference/hooks/formats/
- https://tanstack.com/blog/announcing-tanstack-start-v1
- https://tanstack.com/blog/tanstack-start-5x-ssr-throughput
- https://tanstack.com/db/latest/docs/framework/solid/overview
- https://tanstack.com/form/latest/docs/framework/solid/examples/standard-schema
- https://tanstack.com/form/latest/docs/framework/solid/guides/validation
- https://tanstack.com/query/latest/docs/framework/solid
- https://tanstack.com/query/latest/docs/framework/solid/installation
- https://tanstack.com/table/latest/docs/framework/solid
- https://tanstack.com/virtual/latest/docs
- https://tanstack.dev/pacer/latest/docs/installation
- https://tanstack.dev/store/latest/docs/overview
- https://vanilla-extract.style/
- https://vercel.com/geist/introduction
- https://vercel.com/templates/tailwind
- https://vinext.io/
- https://vite.dev/guide/features.html#css-modules
- https://www.cssscript.com/open-props-ui/
- https://www.infoq.com/news/2025/08/remix-run-v3-drops-react/
- https://www.npmjs.com/package/million
- https://www.rari.build/
- https://www.w3.org/TR/css-2026/
- https://www.w3.org/TR/css-anchor-position-1/
- https://www.w3.org/TR/css-cascade-5/
- https://www.w3.org/TR/css-cascade-6/
- https://www.w3.org/TR/css-color-4/
- https://www.w3.org/TR/css-color-5/
- https://www.w3.org/TR/css-contain-3/
- https://www.w3.org/TR/css-grid-2/
- https://www.w3.org/TR/css-nesting-1/
- https://www.w3.org/TR/css-properties-values-api-1/
- https://www.w3.org/TR/css-variables-1/
- https://www.w3.org/TR/css-view-transitions-1/
- https://www.w3.org/TR/selectors-4/
