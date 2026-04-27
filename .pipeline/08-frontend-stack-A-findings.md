# Sub-Question A — React fork findings

## Identified project (or "no single match found")

No single project satisfies all three constraints perfectly:

- "React fork" in the literal sense.
- Raw runtime performance marketing.
- Mostly drop-in compatibility with an existing React component tree.
- Active 2025-2026 discussion and maintenance.

Best match for the user's wording:

- **Million.js** if the phrase was remembered as "something that makes React way faster."
- Evidence: its README markets itself as an "optimizing compiler for React," claims React components can be up to 70% faster, says it works with React, and says it makes reconciliation faster.
- Limitation: it is not a React fork, and its npm package has not shipped since 2024-06-04.

Best current 2025-2026 explanation if the user was thinking of recent React performance news:

- **React Compiler** if the "way faster" part came from recent React Conf / React 19 discourse.
- Evidence: React Compiler 1.0 shipped on 2025-10-07, is stable, production-ready, and automatically optimizes React components and hooks.
- Limitation: it is upstream React, not a fork.

Best literal "React-compatible faster runtime" candidates:

- **Preact**: fast 3 kB React alternative, `preact/compat` alias lets many React components work.
- **Inferno**: actively maintained in 2026, "insanely fast, React-like," has `inferno-compat`.
- **Rari**: active 2026 React Server Components framework on a Rust runtime, but not a React fork and not drop-in for existing client-only React apps.

Recommendation:

- Name **Million.js** first when answering "what was the React thing that makes React faster?"
- Add that as of 2026 it is probably **stale**, and the currently relevant "React got faster" project is **React Compiler**.
- If the user insists "fork/runtime, not compiler," ask whether they meant **Preact** or **Inferno**.

## Candidate 1: Million.js

- Project URL + GitHub:
- Website/docs: https://million.dev and legacy/docs links at https://github.com/aidenybai/million
- GitHub: https://github.com/aidenybai/million
- npm: https://www.npmjs.com/package/million

- Current version + release date:
- npm `million` latest: **3.1.11**, published **2024-06-04T10:37:31Z**.
- GitHub latest release page shows **v3.1.0**, published **2024-05-21T14:33:22Z**.
- GitHub repo is not archived.
- GitHub API showed `pushed_at`: **2025-12-11T22:10:52Z**.
- The most recent commit visible through the GitHub API was a README update on **2025-12-04**, not an npm release.

- What it claims to make faster:
- The README says Million.js is an optimizing compiler for React.
- It claims components can be up to 70% faster.
- It says it works with React and makes reconciliation faster.
- It describes replacing React's diffing work with generated direct DOM updates for eligible components.
- It describes the goal as React components running at near raw JavaScript speed.

- Compatibility with upstream React:
- **Library/compiler layer, not a React fork.**
- It is intended to work with React projects.
- It has React integration packages/modules in the monorepo: `react`, `react-server`, and `compiler`.
- It is not a blanket "any existing React tree Just Works" runtime.
- It has eligibility constraints because the compiler optimizes components it can understand.

- Maintenance status (last 90-day activity):
- Weak.
- npm package has no release since **2024-06-04**.
- GitHub release has no release since **2024-05-21**.
- Repository is not archived.
- GitHub issue **#1181 "Is Million Abandoned?"** was opened **2025-07-24**, noting that the repo and blog appeared untouched for over a year.
- GitHub issue **#1184 "Million.js with React Compiler?"** was opened **2026-01-17**, so it is still being discussed by users.
- GitHub API showed open PR activity in January 2026, but no corresponding release.

- Likelihood this is what the user meant:
- **High** for the phrase "some kind of React fork that makes it way faster."
- It is the candidate with the closest exact marketing shape: React + faster reconciliation + "70% faster."
- The user's use of "fork" is likely colloquial here; Million.js is a performance layer/compiler, not a fork of React.
- The big caveat is currency: it does not look like the active 2025-2026 answer to choose for a new stack.

## Candidate 2: React Compiler / React Forget

- Project URL + GitHub:
- Official blog: https://react.dev/blog/2025/10/07/react-compiler-1
- Official docs: https://react.dev/learn/react-compiler
- React repo: https://github.com/facebook/react
- npm package: `babel-plugin-react-compiler`

- Current version + release date:
- `babel-plugin-react-compiler` latest stable: **1.0.0**, published **2025-10-07T19:19:01Z**.
- `react-compiler-runtime` latest stable: **1.0.0**, published **2025-10-07T19:19:07Z**.
- React package latest stable observed: **19.2.5**, published **2026-04-08T18:39:24Z**.
- The React repo is active; GitHub API showed `pushed_at`: **2026-04-24T23:27:40Z**.

- What it claims to make faster:
- React Compiler is a build-time optimizer.
- It automatically memoizes React components and hooks.
- The React team says it optimizes React apps without requiring rewrites.
- The React team cites production results: initial loads and cross-page navigations improved by up to 12%, and some interactions were more than 2.5x faster.
- It targets re-render / memoization overhead, not replacing React's reconciler with a different runtime.

- Compatibility with upstream React:
- **Upstream React, not a fork.**
- Works on React and React Native.
- Official blog says it is compatible with React 17 and up when configured with a minimum target and runtime dependency.
- It is explicitly designed for incremental adoption in existing applications.
- It is the most credible "React got faster" answer in 2025-2026.

- Maintenance status (last 90-day activity):
- Strong.
- Stable 1.0 released in October 2025.
- npm package metadata was modified in April 2026 due to ongoing React canary/experimental publication cadence.
- React 19.2.x stable patch releases continued into April 2026.

- Likelihood this is what the user meant:
- **Medium-high** if the user heard recent conversation around "React Forget" or "React Compiler makes React faster."
- **Low** if the user specifically remembers a third-party fork or runtime replacement.
- The "fork" word does not fit; the "way faster" press framing does.

## Candidate 3: Preact

- Project URL + GitHub:
- Website: https://preactjs.com/
- GitHub: https://github.com/preactjs/preact
- Compatibility docs: https://preactjs.com/guide/v10/getting-started/#aliasing-react-to-preact

- Current version + release date:
- npm `preact` latest stable: **10.29.1**, published **2026-04-03T10:43:57Z**.
- GitHub latest release API: **10.29.1**, published **2026-04-03T10:43:40Z**.
- GitHub repo is not archived.
- GitHub API showed `pushed_at`: **2026-04-08T06:05:26Z**.

- What it claims to make faster:
- Preact markets itself as a fast 3 kB alternative to React with the same modern API.
- It emphasizes smaller download, parse, and execution cost.
- It says it is one of the fastest Virtual DOM libraries because of a simple predictable diff implementation.
- It automatically batches updates and is tuned heavily for performance.

- Compatibility with upstream React:
- **React-compatible alternative, not a React fork.**
- `preact/compat` aliases `react`, `react-dom`, and `react/jsx-runtime` imports.
- Preact docs say React libraries and components can work through the compatibility layer.
- Compatibility is good but not perfect; projects with deep assumptions about React internals or newer React-only features can hit edges.

- Maintenance status (last 90-day activity):
- Strong.
- Stable release on **2026-04-03**.
- Repository pushed on **2026-04-08**.
- Preact v11 beta is also advertised on the site, showing ongoing forward work.

- Likelihood this is what the user meant:
- **Medium**.
- Preact is the classic answer to "faster React-compatible runtime."
- It is actively maintained and drop-in-ish.
- But it is old, well-known, and not normally described as a 2025 "some kind of React fork" discovery unless the user saw recent Remix v3 discourse.

## Candidate 4: Inferno

- Project URL + GitHub:
- Website: https://infernojs.org
- GitHub: https://github.com/infernojs/inferno
- Compat README: https://raw.githubusercontent.com/infernojs/inferno/master/packages/inferno-compat/README.md

- Current version + release date:
- npm `inferno` latest: **9.1.0**, published **2026-04-07T13:22:32Z**.
- GitHub latest release: **v9.1.0**, published **2026-04-07T13:27:30Z**.
- GitHub repo is not archived.
- GitHub API showed `pushed_at`: **2026-04-07T13:07:29Z**.

- What it claims to make faster:
- Inferno describes itself as an insanely fast, React-like library for high-performance user interfaces.
- Its README states the main objective is fastest possible runtime performance for web applications.
- It highlights compile-time JSX optimization, bitwise flags for diffing, conditional normalization, and other runtime micro-optimizations.
- It points to js-framework-benchmark and other benchmark suites.

- Compatibility with upstream React:
- **React-like runtime, not a React fork.**
- `inferno-compat` provides a compatibility layer exposing React and React DOM-like exports.
- The compat README says React-based modules can work with Inferno without code changes by aliasing `react` and `react-dom`.
- The same README warns compatibility adds overhead and native Inferno performance should not be expected.

- Maintenance status (last 90-day activity):
- Strong.
- Latest npm and GitHub release in April 2026.
- Repository is active with recent commits.

- Likelihood this is what the user meant:
- **Medium-low**.
- It fits "React-compatible runtime that is much faster" better than most candidates.
- It is less likely as the remembered project because Inferno is not new, and recent mainstream discussion is smaller than React Compiler / Preact / Million.js.

## Candidate 5: Rari

- Project URL + GitHub:
- Website: https://www.rari.build/
- GitHub: https://github.com/rari-build/rari
- npm package: `rari`

- Current version + release date:
- npm `rari` latest: **0.13.1**, published **2026-04-24T19:10:24Z**.
- GitHub API latest release: **rari@0.13.1**, published **2026-04-24T19:10:59Z**.
- GitHub repo is not archived.
- GitHub API showed `pushed_at`: **2026-04-24T22:02:21Z**.

- What it claims to make faster:
- Rari markets itself as a React Server Components framework powered by a Rust runtime.
- The README claims 9.8x faster average response times and 47.7x higher throughput than Next.js in its benchmark setup.
- It claims smaller client bundles and faster production builds.
- It attributes performance to running the HTTP server, RSC renderer, and router in Rust with embedded V8.

- Compatibility with upstream React:
- **React framework/runtime layer, not a React fork.**
- You write standard React and React Server Components semantics.
- It is compatible with the React app-router / RSC mental model.
- It is not a drop-in replacement for an arbitrary existing React component tree.
- It competes more with Next.js / RSC frameworks than with React itself.

- Maintenance status (last 90-day activity):
- Strong.
- npm and GitHub release on **2026-04-24**.
- Repository pushed on **2026-04-24**.
- Active enough to count as a 2025-2026 conversation.

- Likelihood this is what the user meant:
- **Medium-low**.
- It is very current and performance-forward.
- It does not fit "React fork"; it fits "faster React framework/server runtime."
- It is plausible if the user saw claims like "React Server Components with Rust, 12x faster than Next.js."

## Candidate 6: Remix 3 / fork of Preact / custom component model

- Project URL + GitHub:
- Official landing page: https://remix.run/
- Official post: https://remix.run/blog/wake-up-remix
- Background article: https://www.infoq.com/news/2025/08/remix-run-v3-drops-react/

- Current version + release date:
- No stable Remix 3 release identified.
- Official Remix landing page says Remix 3 is under active development.
- The May 2025 "Wake up, Remix!" post is the key source.

- What it claims to make faster:
- Remix 3 is positioned as lightweight, simpler, performance-focused, web-API-first, zero-dependency, and bundler-free.
- The current official wording emphasizes no critical dependencies, not even React.
- It says Remix 3 is being built for a development experience that feels lighter, faster, and more aligned with the web.

- Compatibility with upstream React:
- **Not React-compatible in the required sense.**
- Important correction: earlier reporting said Remix 3 would start with a fork of Preact.
- The official "Wake up, Remix!" post now shows that Preact-fork sentence struck through and says Remix is building its own component model.
- Existing React component trees will not "mostly Just Work."
- React-based Remix functionality moved into React Router v7.

- Maintenance status (last 90-day activity):
- Active project direction in 2025-2026.
- Official landing page says Remix 3 is under active development.
- But there is no stable package/release to evaluate as a runtime replacement.

- Likelihood this is what the user meant:
- **Medium** if the user heard "Remix is dropping React for a faster fork of Preact."
- **Low** if the user wants something to use as a drop-in React replacement.
- The current official position has moved away from "fork of Preact" toward a custom component model, so it should be treated as ruled out for this question.

## Candidate 7: react-strict-dom

- Project URL + GitHub:
- GitHub: https://github.com/facebook/react-strict-dom
- Docs: https://facebook.github.io/react-strict-dom/learn/
- Design goals: https://facebook.github.io/react-strict-dom/contribute/design-goals/

- Current version + release date:
- npm `react-strict-dom` latest: **0.0.55**, published **2026-01-09T22:23:53Z**.
- GitHub latest release page/API observed: **0.0.54**, published **2025-10-02T19:38:56Z**.
- GitHub repo is not archived.
- GitHub API showed `pushed_at`: **2026-04-01T20:44:04Z**.

- What it claims to make faster:
- It is not mainly a raw runtime speed project.
- It standardizes styled React components for web and native.
- It emphasizes engineering efficiency, portability, and platform alignment.
- On web, docs say it has no bundle size or runtime performance overhead relative to Meta's existing React DOM + StyleX code.
- It has a tiny runtime claim in docs: under 2 kB of runtime code for describing web components with encapsulated styles.

- Compatibility with upstream React:
- **Subset/library, not a React fork.**
- Defines a subset of React DOM and Web APIs.
- Requires using `html.*` elements and its `css` API.
- It is not a drop-in replacement for arbitrary React DOM trees.

- Maintenance status (last 90-day activity):
- Reasonably active.
- npm release in January 2026.
- Repository pushed in April 2026.

- Likelihood this is what the user meant:
- **Low**.
- It is "fork-shaped" only because it is Meta-owned and React DOM-adjacent.
- It does not market itself as "React but way faster."

## Candidate 8: One

- Project URL + GitHub:
- Website: https://onestack.dev/
- GitHub: https://github.com/onejs/one
- npm package: `one`

- Current version + release date:
- npm `one` latest: **1.16.2**, published **2026-04-25T08:11:37Z**.
- GitHub latest release: **v1.16.2**, published **2026-04-25T08:11:52Z**.
- GitHub repo is not archived.
- GitHub API showed `pushed_at`: **2026-04-25T08:11:42Z**.

- What it claims to make faster:
- One's homepage says it is the simplest, fastest, all-in-one React Native framework.
- It emphasizes Vite, web/native sharing, routing, render modes, loaders, middleware, and avoiding RSC complexity.
- It is more about cross-platform React app development than raw React runtime replacement.

- Compatibility with upstream React:
- **React framework, not React fork or runtime replacement.**
- Uses React and React Native.
- Existing React knowledge applies.
- It does not replace React's reconciler.

- Maintenance status (last 90-day activity):
- Strong.
- npm and GitHub release on **2026-04-25**.
- Active repo.

- Likelihood this is what the user meant:
- **Low**.
- It matches the "One React" query, but not the "React fork that makes it way faster" target.

## Candidates ruled out (one-line each)

- **Cloudflare vinext**: not React; it reimplements the Next.js API surface on Vite and still uses React/RSC.
- **Bun React optimizations**: Bun has JSX, HMR, React Fast Refresh, and runtime/build speed claims, but not a React fork or React-compatible UI runtime.
- **Vercel / Next.js experiments**: performance work is framework/tooling/RSC/Turbopack/React Compiler integration, not a React fork.
- **TanStack Start**: high-performance React/Solid meta-framework; not a React runtime replacement.
- **react-strict-dom**: React DOM subset + StyleX/cross-platform API; not a raw "faster React" fork.
- **One**: React/React Native meta-framework; not a React-compatible faster reconciler.
- **Remix 3 Preact fork**: current official post strikes through the Preact-fork plan and points to a custom component model; not drop-in React.
- **Solid / Qwik / Svelte**: fast alternatives, but not React-compatible enough for existing React trees.
- **Riot**: component framework, not a current React fork/drop-in runtime.
- **Refract**: unrelated current search results point to visual/3D tooling or older reactive side-effect libraries, not a React runtime.
- **Restle / Restyle**: REST/CSS-in-JS/React Native styling projects; not a React runtime fork.
- **Velvet / Svelvet / Velvette**: search results are unrelated or Svelte graph/UI tooling, not a React fork.
- **Vinxi**: full-stack JavaScript SDK used by frameworks; not a React runtime fork.
- **Wrap**: no credible current React-compatible faster runtime found under this name.

## Recommendation: which name best matches "react fork that makes it way faster"

Answer the user with this hierarchy:

1. **Million.js** is the closest match to the remembered phrase.
   It explicitly markets itself as making React components faster through an optimizing compiler and faster reconciliation.
   It is probably what someone would describe loosely as "a React fork that makes React way faster."

2. **React Compiler** is the current, production-ready React performance story.
   It is not a fork, but it is the 2025-2026 mainstream explanation for "React is faster now."
   If the user is choosing a stack today, this is more relevant than Million.js.

3. **Preact** and **Inferno** are the real React-compatible faster runtimes.
   Preact is the safer ecosystem answer.
   Inferno is the stronger "raw runtime performance" answer.
   Neither is new, and neither is literally a React fork.

4. **Rari** is the current "React but much faster server runtime" candidate.
   It is relevant only if the user was thinking about RSC / Next.js replacement performance rather than browser React reconciliation.

Bottom line:

- **Best name to identify:** Million.js.
- **Best current technology to recommend investigating:** React Compiler, then Preact/Inferno depending on whether they want upstream compatibility or a runtime swap.
- **Not the answer:** Cloudflare vinext, Remix 3, react-strict-dom, One, TanStack Start.

## Citations

- Million.js GitHub README: https://github.com/aidenybai/million
- Million.js npm package: https://www.npmjs.com/package/million
- Million.js latest GitHub release: https://github.com/aidenybai/million/releases
- Million.js "Is Million Abandoned?" issue: https://github.com/aidenybai/million/issues/1181
- Million.js "with React Compiler?" issue: https://github.com/aidenybai/million/issues/1184
- React Compiler v1.0 official post: https://react.dev/blog/2025/10/07/react-compiler-1
- React Compiler docs: https://react.dev/learn/react-compiler
- React Conf 2025 recap: https://react.dev/blog/2025/10/16/react-conf-2025-recap
- Preact homepage: https://preactjs.com/
- Preact React-alias docs: https://preactjs.com/guide/v10/getting-started/#aliasing-react-to-preact
- Preact GitHub: https://github.com/preactjs/preact
- Inferno GitHub README: https://github.com/infernojs/inferno
- Inferno compat README: https://raw.githubusercontent.com/infernojs/inferno/master/packages/inferno-compat/README.md
- Rari GitHub README: https://github.com/rari-build/rari
- React Strict DOM GitHub: https://github.com/facebook/react-strict-dom
- React Strict DOM introduction: https://facebook.github.io/react-strict-dom/learn/
- React Strict DOM design goals: https://facebook.github.io/react-strict-dom/contribute/design-goals/
- Remix landing page: https://remix.run/
- Remix "Wake up, Remix!" official post: https://remix.run/blog/wake-up-remix
- One GitHub: https://github.com/onejs/one
- One homepage: https://onestack.dev/
- TanStack Start v1 RC post: https://tanstack.com/blog/announcing-tanstack-start-v1
- TanStack Start 5x SSR throughput post: https://tanstack.com/blog/tanstack-start-5x-ssr-throughput
- vinext homepage: https://vinext.io/
