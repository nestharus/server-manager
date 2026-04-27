# Sub-Question B — Solid 2 + router findings

As-of date: 2026-04-26.

Evidence boundary:

- Primary sources used: Solid GitHub releases, Solid official docs, Solid Router docs, TanStack docs, npm registry metadata.
- Social posts were not used as evidence.
- npm registry metadata was used for current package versions, dist-tags, publish timestamps, and peer dependency ranges.
- "Production-safe" below means "reasonable default for a new production Humility SPA", not "impossible to ship".

## Solid 2 readiness summary

- Current stable Solid package: `solid-js@1.9.12`.
- Stable package publish date: 2026-03-24.
- Current Solid 2 package on the `next` dist-tag: `solid-js@2.0.0-beta.8`.
- Solid 2 beta.8 package publish date: 2026-04-22.
- npm dist-tags observed:
- `latest`: `1.9.12`.
- `next`: `2.0.0-beta.8`.
- `beta`: `1.10.0-beta.0`.
- GitHub release milestone: `v2.0.0-beta.0`, released by `ryansolid` on 2026-03-03.
- GitHub release status: pre-release.
- Maintainer release language: Solid 2 "enters the beta stage".
- Maintainer release language: "There will be bugs and rough edges" in the ecosystem.
- Maintainer release language: focus is documentation, migration strategy, and extending 2.0 into the wider ecosystem.
- No Solid 2 RC or GA release was found as of 2026-04-26.
- No official statement was found saying Solid 2 is the default production line for SPAs.
- Official npm posture still points new unqualified installs at Solid 1.9.12 through `latest`.
- Solid 2 is viable for beta-tolerant greenfield exploration.
- Solid 2 is not the conservative production default for Humility as of 2026-04-26.
- Qualified verdict: use Solid 2 only if the project explicitly accepts beta framework and adapter churn.
- Humility verdict: do not treat Solid 2 as production-safe yet; reconsider once Solid 2 is RC/GA and stable adapters move off prerelease tags.

Production-readiness notes for SPA-only use:

- The Solid 2 beta release includes CSR and SSR StackBlitz templates.
- The beta release says missing pieces do not block "core mechanics".
- That is evidence that core SPA mechanics are testable.
- It is not evidence that the broader production ecosystem is stable.
- The risk for a Humility SPA is mostly adapter/library churn, not SSR/RSC.
- The router, Vite plugin, and query adapters all have prerelease Solid 2 tracks.
- Several form/component packages still publish only Solid 1 peer ranges or old release lines.

Solid 2 breaking-change surface called out in the beta release:

- Async is first-class in the reactive graph.
- `<Loading>` is the initial-readiness primitive.
- `isPending(() => expr)` reports background pending work.
- `action(...)` plus optimistic primitives become the mutation story.
- Derived state gets function forms such as `createSignal(fn)` and `createStore(fn)`.
- Updates are microtask-batched.
- Reads do not update until the batch flushes.
- `flush()` is the explicit settle-now escape hatch.
- Dev guardrails warn on top-level reads in components.
- Dev guardrails warn on writes in reactive scopes.
- `use:` directives are removed.
- `ref` directive factories replace `use:` directives.
- `classList` is folded into `class`.
- `Index` is replaced by `<For keyed={false}>`.
- `<For>` children receive accessors such as `item()` and `i()`.
- `createEffect` is split into compute/apply phases.
- `onMount` is replaced by `onSettled`.
- Store setters are draft-first by default.
- `storePath(...)` is the opt-in helper for old path-style store ergonomics.

Migration cost from Solid 1.9 to Solid 2:

- Low-to-medium for a small SPA using mostly signals, memos, simple JSX, and plain Vite.
- Medium for a real admin SPA with forms, tables, router data, component primitives, and third-party libraries.
- High if the codebase uses many `use:` directives, `classList`, `Index`, old store path setters, mount/effect assumptions, or third-party libraries without Solid 2 beta support.
- Migration requires API edits, not just dependency bumps.
- Migration requires retesting async UI timing because batching and reads change.
- Migration requires retesting route/data preloading because router and query support are on prerelease tracks.
- Migration requires retesting UI primitives because Ark/Kobalte/Felte/Modular Forms do not all publish explicit Solid 2 stable support.

Adapter readiness matrix:

| Adapter / library | Current observed package | Release date | Solid 2 status | Production interpretation |
| --- | ---: | --- | --- | --- |
| `solid-js` | `1.9.12` latest / `2.0.0-beta.8` next | 2026-03-24 / 2026-04-22 | Solid 2 is beta-only | Solid 1 remains default production line |
| `vite-plugin-solid` | `2.11.12` latest / `3.0.0-next.5` next | 2026-04-05 / 2026-04-18 | Solid 2 support is on `next` | Good signal, but prerelease for Solid 2 |
| `@solidjs/router` | `0.16.1` latest / `0.17.0-next.3` next | 2026-03-17 / 2026-04-26 | Stable peer `solid-js:^1.8.6`; next peer `solid-js >=2.0.0-beta.7 <2.0.0-experimental.0` | Official router has active Solid 2 next track, not stable |
| `@solidjs/start` | `1.3.2` latest / `2.0.0-alpha.2` alpha | 2026-02-24 / 2026-02-20 | Start v2 is alpha | Not needed for SPA; avoid as production dependency |
| `@tanstack/solid-query` | `5.100.5` latest / `6.0.0-beta.4` beta | 2026-04-25 / 2026-04-22 | v5 peer `solid-js:^1.6.0`; v6 beta peer `>=2.0.0-beta.0 <3.0.0` | Strong adapter; Solid 2 support is beta |
| `@tanstack/solid-form` | `1.29.1` | 2026-04-21 | Peer `solid-js >=1.9.9`; no separate Solid 2 prerelease found | Active and likely testable, but no explicit Solid 2 beta line found |
| `@ark-ui/solid` | `5.36.2` | 2026-04-22 | Peer `solid-js >=1.6.0`; no explicit Solid 2 statement found in registry | Active; validate against Solid 2 before production |
| `@kobalte/core` | `0.13.11` | 2025-07-26 | Peer `solid-js ^1.8.15` | Not Solid 2-ready by peer range |
| `@modular-forms/solid` | `0.25.1` | 2025-03-01 | Peer `solid-js ^1.3.1` | Not Solid 2-ready by peer range; stale release cadence |
| `@felte/solid` | `1.2.14` | 2024-10-29 | Peer `solid-js ^1.2.0` | Not Solid 2-ready by peer range; stale release cadence |

## Canonical Solid router (non-TanStack)

- Canonical non-TanStack router: `@solidjs/router`.
- Project URL: https://github.com/solidjs/solid-router
- Official docs URL: https://docs.solidjs.com/solid-router
- Current stable npm version: `0.16.1`.
- Stable publish date: 2026-03-17.
- Current `next` npm version: `0.17.0-next.3`.
- `next` publish date: 2026-04-26.
- Stable peer range: `solid-js:^1.8.6`.
- Solid 2 `next` peer range: `solid-js >=2.0.0-beta.7 <2.0.0-experimental.0`.
- Official docs describe Solid Router as the universal router for Solid.
- Official docs say it works for client and server rendering.
- Official docs describe it as inspired by React Router and Ember Router.
- Official routing guide installs and imports from `@solidjs/router`.
- Official routing guide shows `<Router>`, `<Route>`, `<A>`, lazy route components, dynamic route params, match filters, optional params, wildcards, and nested routes.
- Official SolidStart routing uses `<FileRoutes />` from `@solidjs/start/router`.
- SolidStart docs say `<FileRoutes />` generates route config from the file system.
- SolidStart docs show `<FileRoutes />` used inside `Router` from `@solidjs/router`.
- SolidStart file routes are therefore a SolidStart feature layered over Solid Router, not a separate canonical SPA router.

What real Solid users ship with for new SPAs:

- Primary-source answer: the official path for a plain Solid SPA is `@solidjs/router`.
- Primary-source answer: the official path for a SolidStart app is file-based routes through `<FileRoutes />`, backed by `@solidjs/router`.
- No primary source found that makes Rouage, solid-named-router, Solid Aria, or a Vinxi-only router the canonical Solid SPA router.
- `solid-aria-router` was not found as a canonical or current Solid router package.
- Rouage exists as an alternative framework/router, but it is not the Solid official router.
- TanStack Router remains a strong typed-router option, but it is explicitly rejected for this question.
- For a new Humility SPA that rejects TanStack Router, use `@solidjs/router`.

Feature comparison vs TanStack Router on Humility-relevant dimensions:

| Dimension | `@solidjs/router` | TanStack Router | Humility implication |
| --- | --- | --- | --- |
| Official Solid status | Official Solid router | Third-party TanStack router with Solid adapter | Official path favors `@solidjs/router` |
| SPA routing | Yes | Yes | Both viable |
| SSR-capable | Yes | Yes | Not decisive for Humility SPA |
| Solid 2 support | `0.17.0-next.3` targets Solid 2 beta.7+ | Active Solid 2 work in TanStack Router/Start/Query release train | Both are prerelease for Solid 2 |
| File-based routes | Plain router: no canonical file route generator; SolidStart `<FileRoutes />` provides file routes | Preferred and recommended in TanStack Router docs | Solid Router is less feature-rich for file routing in plain SPA |
| Code/config routes | JSX routes and object/config routes | Code routes and generated route tree | Both support code routes |
| Type-safe route params | TypeScript types exist; docs show `useParams` and `MatchFilters` | Strong route-level type inference and typed hooks | TanStack is stronger |
| Param validation | `MatchFilters` for path matching | Typed params plus validation patterns | TanStack is stronger for app-wide type safety |
| Search-param schemas | `useSearchParams`; no official schema validation layer found in Solid Router docs | `validateSearch`, schema adapters, typed search hooks | TanStack is much stronger |
| Route loaders / preload | `preload`, `query`, `createAsync`, revalidation docs | Loader APIs, preloading, pending/error APIs | Both have data APIs; TanStack is more integrated with route types |
| Route trees | Nested `<Route>` structure; SolidStart file routes generate config | Explicit route tree is central concept | Both support nesting; TanStack has stronger generated route tree tooling |
| Devtools | No Solid Router devtools found in official docs | TanStack Router docs include Devtools | TanStack is stronger |
| API-backed dashboard fit | Sufficient with TanStack Query or Solid Router data APIs | Strong, but rejected | `@solidjs/router` is enough if Query handles server state |

Router recommendation:

- Use `@solidjs/router` for the non-TanStack router decision.
- Use `@solidjs/router@0.16.1` with Solid 1.9.x for production today.
- Use `@solidjs/router@0.17.0-next.3` only when deliberately testing Solid 2 beta.
- Do not use SolidStart solely to get file-based routing for a Pomerium-protected API-backed SPA.
- Do not introduce TanStack Router through another package if the user rejection is firm.

## TanStack scope (Solid adapters, ex-Router)

| Package | Solid version | Release date | Solid 2 compat | Recommended? |
| --- | ---: | --- | --- | --- |
| `@tanstack/solid-query` | `5.100.5` latest | 2026-04-25 | Stable v5 peer `solid-js:^1.6.0`; Solid 2 support exists as `6.0.0-beta.4` with peer `>=2.0.0-beta.0 <3.0.0` | Yes for Solid 1 production; for Solid 2 only as beta |
| `@tanstack/solid-form` | `1.29.1` | 2026-04-21 | Peer `solid-js >=1.9.9`; no explicit Solid 2 prerelease tag found | Yes, but validate on Solid 2 before committing |
| `@tanstack/solid-table` | `8.21.3` latest; `9.0.0-alpha.37` alpha | 2025-04-14 latest; 2026-04-26 alpha | Latest peer `solid-js >=1.3`; alpha peer also `>=1.3`; no explicit Solid 2 beta tag found | Yes for tables on Solid 1; Solid 2 needs compatibility testing |
| `@tanstack/solid-virtual` | `3.13.24` | 2026-04-17 | Peer `solid-js:^1.3.0`; no Solid 2 peer range | Yes for Solid 1; not confirmed for Solid 2 beta |
| `@tanstack/solid-store` | `0.11.0` | 2026-04-17 | Peer `solid-js:^1.6.0`; no Solid 2 peer range | Yes indirectly; useful when TanStack packages need it |
| `@tanstack/solid-pacer` | `0.21.0` | 2026-04-17 | Peer `solid-js >=1.9.5`; docs say compatible with Solid v1.9.5+ | Optional; use only for timing/rate-control needs |
| `@tanstack/solid-db` | `0.2.19` | 2026-04-14 | Peer `solid-js >=1.9.0`; docs include Solid adapter and `useLiveQuery`; no explicit Solid 2 beta tag found | Not a default for Humility; consider only if local live-query/client DB becomes a requirement |

TanStack package notes:

- `@tanstack/solid-query` is the strongest in-scope TanStack package for Humility.
- Query has active stable releases and a separate Solid 2 beta line.
- Query v6 beta.4 release notes include "upgrade to solid v2 beta 7".
- `@tanstack/solid-form` is active and directly relevant to Humility's YAML-driven forms.
- TanStack Form Solid docs show Standard Schema support with Zod, Valibot, ArkType, and Effect Schema.
- `@tanstack/solid-table` is relevant for admin/operator tables.
- Table latest v8 is older than other TanStack packages, but npm metadata shows a v9 alpha line was modified/published on 2026-04-26.
- `@tanstack/solid-virtual` is relevant for large member/application/ticket lists.
- `@tanstack/solid-store` is a low-level store, often used internally by TanStack packages.
- TanStack Store docs say it ships framework adapters for React, Solid, Vue, Angular, and Svelte.
- `@tanstack/solid-pacer` exists.
- TanStack Pacer docs list `@tanstack/solid-pacer` and say it is compatible with Solid v1.9.5+.
- `@tanstack/solid-db` exists.
- TanStack DB Solid docs include `useLiveQuery` and explain Solid signal tracking inside query functions.
- TanStack DB should not be in the default Humility stack unless the frontend needs local collections, optimistic transactions, or sync-style live queries.

Recommended TanStack scope if router is rejected:

- Keep: `@tanstack/solid-query`.
- Keep: `@tanstack/solid-form`.
- Keep when needed: `@tanstack/solid-table`.
- Keep when needed: `@tanstack/solid-virtual`.
- Allow indirectly: `@tanstack/solid-store`.
- Optional/niche: `@tanstack/solid-pacer`.
- Defer: `@tanstack/solid-db`.
- Exclude: `@tanstack/solid-router`.
- Exclude: TanStack Start if the rejection of TanStack Router is firm, because TanStack Start is built on TanStack Router.

Bottom-line stack implication:

- Solid 2 is promising, but still beta as of 2026-04-26.
- The safest production stack remains Solid 1.9.x plus `@solidjs/router@0.16.1`.
- The forward-looking test stack is Solid 2 beta plus `@solidjs/router@0.17.0-next.3` plus TanStack Query v6 beta.
- For Humility, choose the production stack unless the user explicitly wants to spend Phase 6 absorbing Solid 2 beta migration risk.

## Citations

- Solid 2 beta release: https://github.com/solidjs/solid/releases/tag/v2.0.0-beta.0
- Solid releases: https://github.com/solidjs/solid/releases
- Solid npm registry metadata: https://registry.npmjs.org/solid-js
- Vite Plugin Solid npm registry metadata: https://registry.npmjs.org/vite-plugin-solid
- Solid Router docs overview: https://docs.solidjs.com/solid-router
- Solid routing guide: https://docs.solidjs.com/guides/routing-and-navigation
- Solid Router preloading docs: https://docs.solidjs.com/solid-router/advanced-concepts/preloading
- SolidStart routing docs: https://docs.solidjs.com/solid-start/building-your-application/routing
- Solid Router GitHub repo: https://github.com/solidjs/solid-router
- Solid Router npm registry metadata: https://registry.npmjs.org/@solidjs/router
- SolidStart npm registry metadata: https://registry.npmjs.org/@solidjs/start
- TanStack Query Solid docs: https://tanstack.com/query/latest/docs/framework/solid
- TanStack Query Solid installation: https://tanstack.com/query/latest/docs/framework/solid/installation
- TanStack Query Solid 2 beta release mirror: https://newreleases.io/project/github/TanStack/query/release/release-2026-04-22-2157
- TanStack Query npm registry metadata: https://registry.npmjs.org/@tanstack/solid-query
- TanStack Form Solid validation docs: https://tanstack.com/form/latest/docs/framework/solid/guides/validation
- TanStack Form Solid Standard Schema example: https://tanstack.com/form/latest/docs/framework/solid/examples/standard-schema
- TanStack Form npm registry metadata: https://registry.npmjs.org/@tanstack/solid-form
- TanStack Table Solid docs: https://tanstack.com/table/latest/docs/framework/solid
- TanStack Table npm registry metadata: https://registry.npmjs.org/@tanstack/solid-table
- TanStack Virtual docs: https://tanstack.com/virtual/latest/docs
- TanStack Virtual npm registry metadata: https://registry.npmjs.org/@tanstack/solid-virtual
- TanStack Store docs: https://tanstack.dev/store/latest/docs/overview
- TanStack Store npm registry metadata: https://registry.npmjs.org/@tanstack/solid-store
- TanStack Pacer installation docs: https://tanstack.dev/pacer/latest/docs/installation
- TanStack Pacer npm registry metadata: https://registry.npmjs.org/@tanstack/solid-pacer
- TanStack DB Solid docs: https://tanstack.com/db/latest/docs/framework/solid/overview
- TanStack DB npm registry metadata: https://registry.npmjs.org/@tanstack/solid-db
- Ark UI Solid npm registry metadata: https://registry.npmjs.org/@ark-ui/solid
- Kobalte npm registry metadata: https://registry.npmjs.org/@kobalte/core
- Modular Forms Solid npm registry metadata: https://registry.npmjs.org/@modular-forms/solid
- Felte Solid npm registry metadata: https://registry.npmjs.org/@felte/solid
