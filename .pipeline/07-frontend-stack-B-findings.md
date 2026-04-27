# Sub-Question B - Solid ecosystem findings

As-of date: 2026-04-26.

Evidence scope:

- Primary sources only, except package-registry version checks where GitHub releases do not expose current dist-tags.
- Official docs and GitHub releases were treated as stronger evidence than community commentary.
- "Canonical" below means "best April 2026 default choice for a new shipped SPA given current official posture", not a claim of broad market share.

## Solid core (version, release date, posture)

Canonical April 2026 choice:

- Use Solid 1.x stable for production work today.
- Current stable package line observed: `solid-js@1.9.12`.
- Package registry dist-tags observed on 2026-04-26: `latest: 1.9.12`, `next: 2.0.0-beta.8`, `beta: 1.10.0-beta.0`.
- Latest stable 1.x package publish date observed: `1.9.12` on 2026-03-24.
- Official GitHub release posture is more important than the registry version: the Solid repo's current headline release is `v2.0.0-beta.0`, published 2026-03-03, and marked pre-release.
- Solid 2.0 is not the production default yet.
- Solid 2.0 is active beta work.
- Solid 2.0 beta release text explicitly says "There will be bugs and rough edges" and frames the focus as docs, migration, and extending 2.0 into the wider ecosystem.
- Therefore: new production SPA should start on Solid 1.9.x unless the project intentionally wants to absorb Solid 2 migration churn.

Solid 2.0 beta evidence:

- `v2.0.0-beta.0` was published on 2026-03-03.
- The beta release states that the project "enters the beta stage".
- The beta release identifies ecosystem extension and migration strategy as current work.
- The release links seven 2.0 migration/RFC documents.
- The release states that Vite Plugin Solid was updated under the `next` tag.

Breaking changes from Solid 1.x to Solid 2.0 beta:

- Async is first-class in the reactive graph.
- `<Loading>` becomes the initial-readiness primitive for async UI.
- `isPending(() => expr)` expresses pending work for background refresh.
- `action(...)` and optimistic primitives become the mutation story.
- Derived state gets explicit function forms such as `createSignal(fn)` and `createStore(fn)`.
- Scheduling becomes microtask-batched.
- Reads do not update until batch flush; `flush()` is the explicit settle-now escape hatch.
- Dev warnings catch top-level reads in components and writes in reactive scopes.
- DOM model cleanup replaces `use:` directives with `ref` directive factories.
- `classList` is folded into `class`.
- List rendering changes: `Index` is replaced by `<For keyed={false}>`.
- `For` children receive accessors such as `item()` and `i()`.
- Effects/lifecycle changes: `createEffect` is split into compute/apply phases.
- `onMount` is replaced by `onSettled`.
- Store setters become draft-first by default.
- `storePath(...)` exists as the opt-in helper for old path-style ergonomics.

Runners-up / alternatives:

- Solid 2.0 beta for greenfield prototypes that can track ecosystem churn.
- Solid 1.10 beta only if a specific 1.x beta fix is required.
- Do not start production on 2.0 beta unless the team has explicit capacity for migration breakage across router, Start, query, primitives, and component libraries.

## Solid Start status

Canonical April 2026 choice:

- SolidStart v1 is the current stable Solid meta-framework line.
- Current stable release observed: `@solidjs/start@1.3.2`, published 2026-02-24.
- `@solidjs/start@1.3.2` is not marked pre-release in GitHub releases.
- `@solidjs/start@2.0.0-alpha.2`, published 2026-02-20, is marked pre-release.
- Therefore: SolidStart v1 is the production-ready line; SolidStart v2 is alpha/experimental.

Official docs posture:

- Solid docs present SolidStart as the easiest way to get started with a Solid app when choosing the full-stack starter.
- The official quick start uses `create-solid` and asks whether the project is a SolidStart project.
- SolidStart docs say the app runs locally on port 3000 after scaffold/install.
- SolidStart docs say SolidStart uses Vinxi for dev/build, with Vite and Nitro under it.
- SolidStart docs present standard project files: `src/routes`, `entry-client.tsx`, `entry-server.tsx`, and `app.tsx`.

Runners-up / alternatives:

- Plain Solid + Vite for a browser-only SPA or API-backed frontend.
- TanStack Start Solid for teams intentionally adopting the TanStack routing/start stack; the TanStack Start Solid docs call it a release candidate, not a final stable framework.
- SolidStart v2 alpha only for prototype/research work.

## Router (canonical + runners-up)

Canonical April 2026 choice for official Solid:

- Plain SPA canonical: `@solidjs/router`.
- Current observed package line: `@solidjs/router@0.16.1`.
- Official Solid docs' routing guide installs/imports `@solidjs/router`.
- Official docs describe Solid Router as the package for route navigation, nested routes, lazy loading, dynamic params, match filters, and preload functions.
- Solid Router is not included by default in a bare Solid app; docs tell users to install it.
- SolidStart canonical routing is file-based routes generated through `<FileRoutes />` from `@solidjs/start/router`.
- SolidStart routing docs state that `<FileRoutes />` generates the route config from the file system.
- SolidStart docs also say this config can be used with the router of your choice.

Canonical April 2026 choice for a TanStack-oriented SPA:

- `@tanstack/solid-router` is an active, viable choice.
- Current release observed: `@tanstack/solid-router@1.168.24`, published in TanStack Router release `2026-04-26 02:58`.
- The 2026-04-26 TanStack Router release includes a Solid-specific fix: hydration mismatch for `ssr="data-only"` with `pendingComponent`.
- TanStack's same release also includes `@tanstack/solid-start@1.167.47`, `@tanstack/solid-start-client@1.166.41`, and `@tanstack/solid-start-server@1.166.42`.
- This is evidence of current maintenance, not evidence that TanStack Router has displaced Solid Router in official Solid docs.

Recommendation:

- If the project wants the official Solid path: use `@solidjs/router`.
- If the project wants TanStack's typed route/data ecosystem: `@tanstack/solid-router` is the best runner-up and can be the project-local canonical choice.
- For this specific Humility web app, TanStack Router remains defensible because the user has already expressed interest in TanStack + SolidJS and the adapter has current April 2026 releases.
- Do not describe TanStack Router as "the Solid canonical router" without qualifying the choice.

Runners-up:

- SolidStart file-based routing for full-stack SolidStart apps.
- TanStack Start Solid for full-stack TanStack apps.
- Vite plugin pages style file-routing exists in official templates but is not the docs' canonical router path.

## Data / cache

Canonical April 2026 choice:

- For simple local async reads in Solid: `createResource`.
- For SolidStart route/server data: Solid Router/SolidStart data APIs (`query`, `action`, preload, server functions) are the official path.
- For API-backed SPA server-state cache/invalidation: `@tanstack/solid-query` remains the strongest canonical choice.

Official Solid evidence:

- SolidStart data-loading docs say Solid provides `createResource` for loading data from data sources.
- Those docs say `createResource` integrates with `Suspense` and `ErrorBoundary`.
- Those docs warn about waterfalls when fetching inside components.
- Those docs recommend hoisting data fetching or, in SolidStart, using the server to fetch in a non-blocking way.
- Solid Router docs show `query(...)` used from `@solidjs/router` to prevent a fetch from happening more than once and to trigger refetch.
- SolidStart mutation docs build on actions from `@solidjs/router`.

TanStack Query evidence:

- Current observed release: `@tanstack/solid-query@5.100.5`, published in TanStack Query release `2026-04-25 17:32`.
- Same release also includes `@tanstack/solid-query-devtools@5.100.5`.
- Same release also includes `@tanstack/solid-query-persist-client@5.100.5`.
- Separate beta line observed for Solid 2 support: `@tanstack/solid-query@6.0.0-beta.4` in 2026-04-22 release notes, with change "upgrade to solid v2 beta 7".
- This indicates the TanStack Query Solid adapter is active on both the stable Solid 1.x path and the Solid 2 beta path.

Recommendation:

- For a Humility dashboard that talks to FastAPI endpoints, use TanStack Query for server-state cache, mutations, invalidation, retries, persistence if needed, and devtools.
- Use Solid `createResource` for small component-local async state where a full cache is unnecessary.
- Use Solid Router/SolidStart `query`/`action` if the app is built as a SolidStart route/server app.
- Do not claim `createResource` has displaced TanStack Query for cache-heavy SPAs; official docs present `createResource` as a primitive, not a complete cache product.

Runners-up:

- `createResource` + `query` from `@solidjs/router` for official Solid/SolidStart idioms.
- Custom signal/store cache for narrow local needs.
- TanStack Query v6 beta only for Solid 2 beta projects.

## Forms

Canonical April 2026 choice:

- There is no single Solid-wide form canonical equivalent to React Hook Form.
- For a TanStack stack: `@tanstack/solid-form` is the most active April 2026 choice.
- Current observed release: `@tanstack/solid-form@1.29.1`, published 2026-04-21.
- Same release updates `@tanstack/form-core@1.29.1`.
- If the project already chooses TanStack Router/Query, TanStack Form is the most coherent default.

Modular Forms evidence:

- Current Solid package observed in repo manifest: `@modular-forms/solid@0.25.1`.
- Latest Solid-specific GitHub release observed: `v0.25.1-solid`, published 2025-03-01.
- Modular Forms docs market the library as modular, type-safe, small, headless, and signal-based.
- Modular Forms docs advertise bundle size starting at 3 KB.
- Modular Forms docs say Solid enhanced forms/actions page is currently exclusively for Qwik and will be updated once SolidJS actions are implemented.
- This makes Modular Forms a strong Solid-native runner-up for client forms, but less clearly current for SolidStart action integration.

Felte evidence:

- Current observed repo manifest package: `@felte/solid@1.2.14`.
- Felte repo describes it as an extensible form library for Svelte, Solid, and React.
- The Felte Solid package depends on `@felte/core`.
- GitHub releases API returned no releases for the repo in this check.
- This makes Felte a legacy/stable runner-up, not the April 2026 momentum leader.

Recommendation:

- Use `@tanstack/solid-form` if the project uses TanStack Query/Router and wants one cross-framework mental model.
- Use Modular Forms if the priority is a Solid-native, small, headless API for client-side forms.
- Avoid treating Felte as the default for new work unless the team already knows it or needs its particular API.
- For high-value application/admin workflows, tests should target form behavior through the app/API contracts rather than library internals.

## Component primitives

Canonical April 2026 choice:

- Ark UI Solid is the strongest maintained component-primitive choice in April 2026.
- Current observed Ark UI docs version: `v5.36.2`.
- Ark UI changelog date for `5.36.2`: 2026-04-22.
- Ark UI docs expose Solid as a first-class framework option alongside React, Vue, and Svelte.
- Ark UI docs list a broad primitive/component surface: Accordion, Avatar, Carousel, Checkbox, Combobox, Date Picker, Dialog, File Upload, Menu, Number Input, Pagination, Popover, Select, Slider, Tabs, Toast, Tooltip, Tour, Tree View preview, and more.
- Ark UI GitHub repo description: build scalable design systems with React, Vue, Solid, and Svelte.
- Ark UI April 2026 changelog includes new features and fixes across components, showing active maintenance.

Kobalte status:

- Kobalte remains important and established in Solid.
- Current observed latest release: `@kobalte/core@0.13.11`, published 2025-07-26.
- Kobalte repo stars observed through GitHub page: about 1.8k.
- Kobalte describes itself as a UI toolkit for accessible web apps and design systems with SolidJS.
- Kobalte is still pre-1.0.
- Kobalte's latest observed release is about nine months old as of 2026-04-26.
- Kobalte should be treated as established but no longer the obvious April 2026 momentum leader.

Corvu status:

- Corvu is a Solid-specific unstyled primitive library.
- Current repo stars observed: about 699.
- Corvu repo describes itself as open-source UI primitives for SolidJS, unstyled, accessible, customizable, good docs, and SSR support.
- Corvu repo lists primitives including Accordion, Calendar, Dialog, Disclosure, Drawer, OTP Field, Popover, Resizable, and Tooltip.
- Latest GitHub release observed: `@corvu/resizable@0.2.5`, published 2025-05-04.
- Corvu is useful where its primitives fit, but the component surface is smaller than Ark UI's.

Other/new libraries:

- Shadcn-style Solid ports exist and depend on Kobalte/Ark/Corvu/cmdk-style primitives.
- The existence of those ports is evidence that primitives are composable, not evidence that a single styled component kit has become canonical.
- From primary sources available here, no new post-2025 Solid component primitive has displaced Ark UI as the maintained default.

Recommendation:

- Default to Ark UI Solid for accessible primitives in a new production admin SPA.
- Use Kobalte where a specific primitive or existing ecosystem component depends on it.
- Use Corvu for specific primitives or shadcn-style Solid ecosystems that already select it.
- Avoid betting the design system on a lightly maintained styled component kit unless its maintenance status is verified per package.

## Build tooling

Canonical April 2026 choice:

- Plain SPA: Vite + `vite-plugin-solid`.
- Current observed `vite-plugin-solid` package line: `2.11.12`.
- Observed `vite-plugin-solid` next line: `3.0.0-next.5` for Solid 2 work.
- Official Solid templates repo is named "Vite + solid templates".
- The templates README says official starter templates are for Vite.
- The templates README says they provide HMR, minimal bundle size, and all Vite features.
- Official quick start uses `create-solid`, asks whether the app is SolidStart, and presents TS/JS template choices.

SolidStart build setup:

- SolidStart uses Vinxi.
- SolidStart docs say Vinxi starts the dev server with Vite.
- SolidStart docs say Vinxi builds and starts a production server with Nitro.
- SolidStart docs say `vinxi dev` runs under the hood.
- SolidStart config docs say `defineConfig` accepts settings for SolidStart, Vite, and Nitro.
- SolidStart can deploy to Nitro-supported platforms.

TanStack Start Solid build setup:

- TanStack Start Solid uses TanStack's Start tooling and Vite plugin.
- TanStack Start Solid docs call TanStack Start "Release Candidate".
- Treat it as a strong runner-up for TanStack shops, not the official Solid default.

Rsbuild:

- No primary Solid docs evidence found that Rsbuild has displaced Vite as the canonical Solid build setup.
- Therefore Rsbuild is not the April 2026 canonical choice for this question.

Recommendation:

- For a single-page Humility web app: use Vite + `vite-plugin-solid`.
- Add TanStack Router/Query/Form as libraries rather than choosing a full-stack meta-framework by default.
- Use SolidStart only if SSR/server functions/file routes are in scope.
- Use TanStack Start only if the project intentionally wants the TanStack full-stack route/data framework.

## Momentum signals (last 90 days)

Positive signals:

- Solid core repo observed stars: 35,463.
- Solid core repo observed pushed_at: 2026-04-25.
- Solid 2.0 beta release published 2026-03-03.
- Solid 2.0 beta package line observed through `next` dist-tag up to `2.0.0-beta.8` by 2026-04-22.
- SolidStart stable line released `@solidjs/start@1.3.2` on 2026-02-24.
- SolidStart v2 alpha released `@solidjs/start@2.0.0-alpha.2` on 2026-02-20.
- TanStack Router released Solid packages on 2026-04-26.
- TanStack Query released `@tanstack/solid-query@5.100.5` on 2026-04-25.
- TanStack Query also has Solid 2 beta support work, including `@tanstack/solid-query@6.0.0-beta.4` in an April 2026 release.
- TanStack Form released `@tanstack/solid-form@1.29.1` on 2026-04-21.
- Ark UI shipped April 2026 releases and maintains a first-class Solid adapter.
- Official docs are current enough to include SolidStart v2 serialization docs and Solid Router data APIs.

Mixed or negative signals:

- Solid 2.0 is still beta as of the as-of date.
- The Solid 2.0 release itself warns of bugs and ecosystem rough edges.
- SolidStart v2 is alpha, not stable.
- Kobalte's latest observed release is 2025-07-26.
- Corvu's latest observed release is 2025-05-04.
- Modular Forms Solid's latest observed Solid-specific release is 2025-03-01.
- Felte has no GitHub releases returned by the GitHub releases API in this check.
- Solid has an active core and strong TanStack/Ark support, but the Solid-specific component/form ecosystem is still smaller and less uniformly active than React's.

Funding / sponsorship signals:

- SolidStart Fund Open Collective page observed on 2026-04-26 shows current budget and transactions.
- The page lists a 2026-02-08 credit from SolidJS to SolidStart Fund.
- The page lists total raised around USD 30,627 and total disbursed around USD 30,582.
- The page lists an estimated annual budget around USD 400 and two contributors.
- This is evidence of some transparent funding, not evidence of large ecosystem funding.

Conference/talk signals:

- No primary last-90-days project-maintainer conference post was found in the allowed source set.
- A GitNation page for Ryan Carniato's "Beyond Signals" exists, but the search result is older than 90 days and appears tied to JSNation 2026 marketing rather than a new April 2026 project release.
- Do not use conference activity as a positive last-90-days momentum claim for this report.

Bottom-line viability:

- Solid is still viable for new SPAs in April 2026.
- The safest production posture is Solid 1.9.x plus Vite.
- TanStack + Solid is current, not stale: Router, Query, and Form adapters all have April 2026 releases.
- The main risk is not core framework abandonment.
- The main risk is ecosystem breadth and Solid 2 transition churn.
- For Humility's API-first admin web app, Solid + Vite + TanStack Router/Query/Form + Ark UI is a coherent April 2026 stack.
- For a server-rendered app, SolidStart v1 is the stable official choice, while TanStack Start Solid is a release-candidate runner-up.

## Citations

[C1] Solid 2.0 beta GitHub release, published 2026-03-03: https://github.com/solidjs/solid/releases/tag/v2.0.0-beta.0
[C2] Solid GitHub repo metadata, observed 2026-04-26/27: https://github.com/solidjs/solid
[C3] Solid docs home, crawled current in search results: https://docs.solidjs.com/
[C4] Solid quick start docs, observed 2026-04-26: https://docs.solidjs.com/quick-start
[C5] SolidStart docs overview, observed 2026-04-26: https://docs.solidjs.com/solid-start
[C6] SolidStart getting-started docs, observed 2026-04-26: https://docs.solidjs.com/solid-start/getting-started
[C7] SolidStart routing docs, observed 2026-04-26: https://docs.solidjs.com/solid-start/building-your-application/routing
[C8] SolidStart data-loading docs, observed 2026-04-26: https://docs.solidjs.com/solid-start/building-your-application/data-loading
[C9] SolidStart data-mutation docs, observed 2026-04-26: https://docs.solidjs.com/solid-start/building-your-application/data-mutation
[C10] SolidStart config docs, observed 2026-04-26: https://docs.solidjs.com/solid-start/reference/config/define-config
[C11] SolidStart GitHub releases, latest stable `@solidjs/start@1.3.2`, published 2026-02-24: https://github.com/solidjs/solid-start/releases
[C12] SolidStart v2 alpha release, published 2026-02-20: https://github.com/solidjs/solid-start/releases/tag/@solidjs/start@2.0.0-alpha.2
[C13] Solid Router docs, observed 2026-04-26: https://docs.solidjs.com/solid-router
[C14] Solid routing and navigation guide, observed 2026-04-26: https://docs.solidjs.com/guides/routing-and-navigation
[C15] Solid Router repo/package manifest, observed version `0.16.1`: https://github.com/solidjs/solid-router
[C16] TanStack Router release `2026-04-26 02:58`, including `@tanstack/solid-router@1.168.24`: https://github.com/TanStack/router/releases/tag/release-2026-04-26-0258
[C17] TanStack Query release `2026-04-25 17:32`, including `@tanstack/solid-query@5.100.5`: https://github.com/TanStack/query/releases/tag/release-2026-04-25-1732
[C18] TanStack Query latest Solid docs: https://tanstack.com/query/latest/docs/solid/overview
[C19] TanStack Query April 2026 beta Solid 2 support release evidence: https://github.com/TanStack/query/releases
[C20] TanStack Form release `@tanstack/solid-form@1.29.1`, published 2026-04-21: https://github.com/TanStack/form/releases/tag/@tanstack/solid-form@1.29.1
[C21] Modular Forms docs, observed 2026-04-26: https://modularforms.dev/
[C22] Modular Forms Solid release `v0.25.1-solid`, published 2025-03-01: https://github.com/fabian-hiller/modular-forms/releases/tag/v0.25.1-solid
[C23] Modular Forms enhanced forms docs, Solid actions not implemented on that page: https://modularforms.dev/solid/guides/enhanced-forms
[C24] Felte repo and package manifest, observed `@felte/solid@1.2.14`: https://github.com/pablo-abc/felte
[C25] Ark UI changelog, `v5.36.2`, dated 2026-04-22: https://ark-ui.com/docs/overview/changelog
[C26] Ark UI repo: https://github.com/chakra-ui/ark
[C27] Kobalte repo/releases, latest observed `@kobalte/core@0.13.11`, published 2025-07-26: https://github.com/kobaltedev/kobalte/releases
[C28] Kobalte docs: https://kobalte.dev/
[C29] Corvu repo, observed stars/primitives/release link: https://github.com/corvudev/corvu
[C30] Corvu docs: https://corvu.dev/
[C31] Corvu release `@corvu/resizable@0.2.5`, published 2025-05-04: https://github.com/corvudev/corvu/releases/tag/@corvu/resizable@0.2.5
[C32] Solid templates repo, Vite templates: https://github.com/solidjs/templates
[C33] Vite Plugin Solid repo: https://github.com/solidjs/vite-plugin-solid
[C34] TanStack Start Solid docs, release-candidate status: https://tanstack.dev/start/latest/docs/framework/solid/overview
[C35] SolidStart Fund Open Collective, observed 2026-04-26: https://opencollective.com/solid/projects/solidstart-fund
[C36] Package registry checks run locally on 2026-04-26 for dist-tags/current package versions: `npm view solid-js`, `npm view @solidjs/start`, `npm view @solidjs/router`, `npm view vite-plugin-solid`.
