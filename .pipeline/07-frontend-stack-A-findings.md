# Sub-Question A - Cloudflare React fork findings

Investigated date: 2026-04-26 America/Los_Angeles.

Primary identification:

- The project appears to be `vinext`.
- Cloudflare does not describe `vinext` as a React fork.
- Cloudflare describes it as a drop-in replacement for Next.js.
- More precisely, Cloudflare describes it as a reimplementation of the Next.js API surface on Vite.
- The project README says it is not a fork of Next.js.
- The README says it imports some Next.js types and utilities, but the core is written from scratch.
- Evidence source: Cloudflare launch post, 2026-02-24.
- Evidence source: `cloudflare/vinext` README, observed 2026-04-26.

## Project name + official URL

- Project name: `vinext`.
- Pronunciation in launch post: "vee-next".
- Official repository: https://github.com/cloudflare/vinext
- Official project site: https://vinext.io/
- Official Cloudflare launch post: https://blog.cloudflare.com/vinext/
- Launch post title: "How we rebuilt Next.js with AI in one week".
- Launch post date: 2026-02-24.
- Repository owner: `cloudflare`.
- GitHub repository description, via GitHub API: "Vite plugin that reimplements the Next.js API surface - deploy anywhere".
- Repository created_at, via GitHub API: 2026-02-24T05:07:41Z.
- Repository license, via GitHub API: MIT.
- Official project site footer says: "Built by Cloudflare with AI".
- Official project site footer says: "Not affiliated with Vercel or the Next.js team".
- Official project site footer says: "Experimental software, use at your own risk".
- Official project site top-level positioning: "The Next.js API surface, reimplemented on Vite."
- Official project site says existing `app/`, `pages/`, and `next.config.js` work as-is.

## Status (version, release stage, date)

- Launch status on 2026-02-24: experimental.
- Launch post status section title: "Status: Experimental".
- Launch post says vinext was "not even one week old" at launch.
- Launch post says it had not been "battle-tested with any meaningful traffic at scale" at launch.
- Launch post also says Cloudflare already had customers running it in production at launch.
- Launch post names National Design Studio and CIO.gov as production usage examples.
- Official README warning says the project is experimental and under heavy development.
- README warning says most code, tests, and docs were written by AI.
- README warning says humans direct architecture, priorities, and design decisions.
- README warning says humans have not reviewed most code line-by-line.
- README warning says to expect bugs, rough edges, and things that do not work.
- Latest npm version observed with `npm view vinext version time --json`: `0.0.44`.
- Latest npm publish timestamp observed: 2026-04-24T20:39:04.102Z.
- Latest GitHub release shown on releases page: `v0.0.44`.
- `v0.0.44` GitHub release timestamp shown: 2026-04-24 20:39.
- `v0.0.44` release notes include bug fixes and one new feature.
- `v0.0.44` release notes include support for rendering intercept route layouts inside App Router slots.
- `v0.0.44` release notes include fixes for protocol-relative URL handling.
- `v0.0.44` release notes include fixes for `usePathname` hydration snapshots.
- `v0.0.44` release notes include fixes for RSC non-ok responses during hard navigation.
- `v0.0.44` release notes include fixes for `isPending` across RSC-level redirects.
- Public npm versioning remains `0.0.x`.
- No explicit stable SemVer compatibility policy was found in the official README or visible release notes.
- No explicit breaking-change policy was found in the official README or visible release notes.
- Evidence-bound status conclusion: experimental, active, not GA.

## Why it exists vs upstream React

- Strictly, vinext does not exist to replace upstream React.
- vinext depends on React and React Server Components infrastructure.
- The README peer dependencies include React, React DOM, `react-server-dom-webpack`, Vite, `@vitejs/plugin-react`, and `@vitejs/plugin-rsc`.
- The README says App Router users install `@vitejs/plugin-rsc` and `react-server-dom-webpack`.
- The project site says React Server Components are supported via `@vitejs/plugin-rsc`.
- The project site says `"use client"` and `"use server"` directives work across dev and production builds.
- The launch post says `@vitejs/plugin-rsc` gave RSC support without Cloudflare building RSC from scratch.
- The problem Cloudflare identifies is not React itself.
- The problem Cloudflare identifies is Next.js deployment in the broader serverless ecosystem.
- The launch post says Next.js tooling is "entirely bespoke".
- The launch post says deploying Next.js to Cloudflare, Netlify, or AWS Lambda requires reshaping Next.js build output into something the target platform can run.
- The launch post says OpenNext solves this by adapting `next build` output.
- The launch post says that approach has limits because it reverse-engineers Next.js build output.
- The launch post says unpredictable Next.js build-output changes require ongoing correction.
- The launch post says Next.js adapters were still early as of 2026-02-24.
- The launch post says adapters only cover build and deploy.
- The launch post says `next dev` runs exclusively in Node.js.
- The launch post says this prevents plugging in a different runtime for development.
- The launch post says platform APIs such as Durable Objects, KV, or AI bindings cannot be tested in `next dev` without workarounds.
- vinext's technical answer is to reimplement the Next.js API surface directly on Vite.
- The launch post says this is "not a wrapper around Next.js and Turbopack output".
- The launch post says it is an alternative implementation of routing, server rendering, React Server Components, server actions, caching, and middleware.
- The launch post says it is built on Vite as a plugin.
- The launch post says Vite output runs on any platform through the Vite Environment API.
- README design principle: deploy anywhere.
- README design principle: pragmatic compatibility, not bug-for-bug parity.
- README design principle: latest Next.js only.
- README design principle: incremental adoption.
- README says vinext targets Next.js 16.x.
- README says deprecated APIs from older Next.js versions are not supported.
- README says about 94% of the Next.js 16 API surface works.

## SPA stack ecosystem

- Router:
- vinext's native router story is Next.js-compatible routing.
- README says vinext scans `pages/` and `app/` directories.
- README says it builds a file-system router matching Next.js conventions.
- README lists full or partial support for both Pages Router and App Router.
- README lists full support for `next/link`.
- README lists full support for `next/router`.
- README lists full support for `next/navigation`.
- README lists App Router pages, routes, layouts, templates, loading, error, not-found, forbidden, and unauthorized support.
- README lists dynamic routes, catch-all routes, optional catch-all routes, route groups, parallel routes, and intercepting routes.
- Official vinext sources reviewed do not document TanStack Router as a native vinext target.
- Cloudflare's Workers Vite plugin documentation separately lists official support for TanStack Start.
- Cloudflare's Workers Vite plugin documentation separately lists official support for React Router v7 with SSR.
- Cloudflare's React + Vite Workers guide describes a React SPA with a Workers API and Cloudflare Vite plugin.
- Cloudflare's SPA routing docs describe SPA static asset routing through `assets.not_found_handling = "single-page-application"`.
- Evidence-bound router conclusion: vinext itself targets Next.js App Router and Pages Router compatibility, not TanStack Router.

- Data:
- vinext supports Next.js caching APIs through `next/cache`.
- README lists `next/cache` support.
- README lists `revalidateTag`, `revalidatePath`, `unstable_cache`, pluggable `CacheHandler`, `"use cache"`, `cacheLife()`, and `cacheTag()`.
- README says ISR supports stale-while-revalidate and a pluggable `CacheHandler`.
- README includes `KVCacheHandler` from `vinext/cloudflare` for production ISR caching on Cloudflare KV.
- README says the cache is pluggable.
- README says the default `MemoryCacheHandler` works out of the box.
- README says users can swap in Redis, DynamoDB, or another backend.
- Project site says ISR uses Cloudflare KV through a pluggable CacheHandler.
- Project site says Durable Objects, AI bindings, KV, and R2 work without workarounds.
- README shows D1 access from a server component through `import { env } from "cloudflare:workers"`.
- Official vinext sources reviewed do not document TanStack Query as a native data layer.
- Evidence-bound data conclusion: vinext's documented data/cache layer is Next-compatible server APIs plus pluggable cache handlers.

- Forms:
- README lists `next/form` support.
- README says `next/form` supports GET form interception and POST server action delegation.
- README lists Server Actions support.
- README says Server Actions include action execution, FormData, re-render after mutation, and `redirect()` in actions.
- Project site says Server Actions support form submissions, mutations, `redirect()` inside actions, re-render after mutation, and full FormData support.
- Official vinext sources reviewed do not document TanStack Form as a native vinext target.
- Evidence-bound forms conclusion: vinext's documented form path is Next-compatible `next/form` plus Server Actions.

- Components:
- Official vinext sources reviewed do not identify a Cloudflare-blessed component primitives library.
- Official vinext sources reviewed do not identify Kobalte, Ark, or Radix as the preferred primitive layer.
- README does mention package import optimization defaults for ecosystem packages.
- README lists examples including `lucide-react`, `date-fns`, `radix-ui`, `antd`, and MUI under `experimental.optimizePackageImports`.
- This is optimization support, not a component-library recommendation.
- Cloudflare's separate `react-router-hono-fullstack-template` describes shadcn/ui in its repository description.
- That template is separate from vinext.
- Evidence-bound components conclusion: no vinext-native component primitive stack was found in primary sources.

- Build:
- vinext is documented as a Vite plugin.
- README says `vinext dev` starts a dev server with HMR.
- README says `vinext build` performs a production build.
- README says App Router builds are multi-environment: RSC, SSR, and client.
- README says `vinext deploy` builds and deploys to Cloudflare Workers.
- README says no `vite.config.ts` is required for basic usage.
- README says custom Vite config can be added when needed.
- README says App Router Cloudflare Workers deployment with RSC needs explicit plugin configuration when customizing.
- README example uses `vinext()`, `@vitejs/plugin-rsc`, and `@cloudflare/vite-plugin`.
- Cloudflare Workers Vite plugin docs say the plugin integrates Vite with the Workers runtime.
- Cloudflare Workers Vite plugin docs say Worker code runs inside `workerd`.
- Cloudflare Workers Vite plugin docs say this matches production behavior as closely as possible.
- Launch post benchmarks compare Next.js 16.1.6 with vinext on Vite 7/Rollup and Vite 8/Rolldown.
- Launch post says benchmarks are directional, not definitive.
- Evidence-bound build conclusion: Vite is the build foundation; Cloudflare Workers integration uses `@cloudflare/vite-plugin`; RSC uses `@vitejs/plugin-rsc`.

## Cloudflare integration

- Cloudflare Workers is the first native deployment target.
- Launch post says vinext deploys to Cloudflare Workers with one command.
- README says Cloudflare Workers deployment uses `vinext deploy`.
- README says native Workers integration includes `@cloudflare/vite-plugin`.
- README says native Workers integration includes bindings access through `cloudflare:workers`.
- README says native Workers integration includes KV caching.
- README says native Workers integration includes image optimization.
- README says `vinext deploy` can auto-generate `vite.config.ts`, `wrangler.jsonc`, and `worker/index.ts`.
- README says App Router and Pages Router work on Workers with full client-side hydration.
- README says `cloudflare:workers` can be imported in server components, route handlers, and server actions.
- README says no custom Worker entry is required for bindings access.
- README says all binding types are supported.
- README lists D1, R2, KV, Durable Objects, AI, Queues, Vectorize, and Browser Rendering.
- README says the `cloudflare:workers` import works because `@cloudflare/vite-plugin` runs the RSC environment in `workerd`.
- README says production builds externalize the import so `workerd` resolves it at runtime.
- README says Wrangler types provide TypeScript types for bindings.
- README says `getPlatformProxy()` is not needed.
- Launch post says a Cloudflare Agents example runs without `getPlatformProxy`.
- Launch post says the whole app runs in `workerd` during both dev and deploy phases.
- README includes Cloudflare KV-backed `KVCacheHandler` for ISR.
- Launch post says KV is a default caching option for most applications.
- Launch post says R2 may fit apps with large cached payloads or different access patterns.
- README documents Traffic-aware Pre-Rendering as experimental.
- README says Traffic-aware Pre-Rendering queries Cloudflare zone analytics at deploy time.
- README says it pre-renders pages that actually receive traffic.
- README says it uploads those pre-rendered results to KV cache.
- README says TPR requires a custom domain because zone analytics are unavailable on `*.workers.dev`.
- README says TPR requires `CLOUDFLARE_API_TOKEN` with Zone.Analytics read permission.
- Project site says all live examples are deployed to Cloudflare Workers and updated on every push to main.
- Project site lists a D1-backed benchmarks dashboard.

Cloudflare integration without hosting lock-in:

- README says vinext can be deployed to Vercel, Netlify, AWS, Deno Deploy, and more through the Nitro Vite plugin.
- README says native adapters for more platforms are planned.
- README says Cloudflare Workers is the first natively supported target.
- README says Cloudflare Workers native integration gives the smoothest experience.
- README documents Nitro deployment examples for Vercel, Netlify, AWS Amplify, Deno Deploy, and Node.js server.
- README says `output: "standalone"` generates `dist/standalone` with `server.js`, build artifacts, and runtime dependencies.
- README says static export with `output: "export"` generates static HTML/JSON for all routes.
- Project site says static export has no server requirement.
- Evidence-bound portability conclusion: Cloudflare has the deepest first-party integration, but official docs state non-Cloudflare targets through Nitro and static export.

## Limitations vs upstream React

- vinext is not an upstream React fork.
- No evidence was found that vinext changes React semantics.
- vinext uses React and React Server Components packages as dependencies or peer dependencies.
- Therefore, "limitations vs upstream React" is not the clearest comparison from primary evidence.
- The documented limitations are limitations vs Next.js API compatibility and deployment parity.

Documented limitations vs Next.js / Next-compatible behavior:

- README says vinext targets pragmatic compatibility, not bug-for-bug parity.
- README says undocumented Vercel behavior is intentionally not replicated.
- README says only latest Next.js is targeted.
- README says deprecated APIs from older Next.js versions are unsupported.
- README says OpenNext is safer when a mature, proven way to run Next.js outside Vercel is required.
- README says OpenNext covers more of the Next.js API surface because it builds on Next.js output.
- README says vinext has faster builds and smaller bundles, but less long-tail coverage.
- README says about 94% of the Next.js 16 API surface has full or partial support.
- README says remaining gaps include intentional stubs for deprecated features.
- README says Partial Prerendering is not supported as PPR.
- README says Next.js 16 reworked PPR into `"use cache"`, and that directive is supported.
- README says Vercel-specific features are not supported.
- README lists unsupported Vercel Analytics integration.
- README lists unsupported Vercel KV, Blob, and Postgres bindings.
- README says users should use platform equivalents.
- README says AMP is deprecated and `useAmp()` returns false.
- README says legacy `next export` is unsupported; use `output: "export"`.
- README says Turbopack and webpack configuration are unsupported.
- README says Vite plugins should be used instead of webpack loaders/plugins.
- README says `next/jest` is unsupported; use Vitest.
- README says `create-next-app` scaffolding is not a goal.
- README says image optimization does not happen at build time.
- README says remote images work through `@unpic/react`.
- README says local images route through `/_vinext/image` for Cloudflare Workers production resizing/transcoding through Images binding.
- README says local images do not have build-time optimization or static resizing.
- README says Google Fonts are loaded from CDN, not self-hosted.
- README says Google Fonts lack `size-adjust` fallback font metrics.
- README says local fonts work but `@font-face` CSS is injected at runtime, not extracted at build time.
- README says route segment config fields `runtime` and `preferredRegion` are ignored.
- README says everything runs in the same environment.
- README says Node.js production server through `vinext start` works for testing.
- README says Node.js production server is less complete than Workers deployment.
- README says Cloudflare Workers is the primary target.
- README says native Node modules can crash Vite's RSC dev environment.
- README lists `sharp`, `resvg`, `satori`, `lightningcss`, and `@napi-rs/canvas` as examples.
- README says dynamic OG image/icon routes using those modules work in production builds but not dev mode.
- README says those modules are auto-stubbed during `vinext deploy`.
- Launch post says static pre-rendering at build time was not supported at launch.
- Launch post says if a site is 100% prebuilt static HTML, it may not see much benefit from vinext at launch.
- Current README/project site now document static export support.
- Evidence-bound change note: static export appears to have changed after launch.

## Migration story from upstream React

- Official migration docs are framed around Next.js applications, not generic React SPAs.
- README quick start says to install `vinext`, Vite, and `@vitejs/plugin-react`.
- README says App Router users also install `@vitejs/plugin-rsc` and `react-server-dom-webpack`.
- README says to replace `next` with `vinext` in package scripts.
- README says existing `pages/`, `app/`, `next.config.js`, and `public/` directories work as-is.
- README says `vinext check` scans for known compatibility issues before migration.
- README says `vinext init` automates migration.
- README says `vinext init` runs `vinext check`.
- README says `vinext init` installs required dependencies.
- README says `vinext init` handles config generation and dev server startup.
- Launch post says vinext includes an Agent Skill for migration.
- Launch post says the Agent Skill handles compatibility checking, dependency installation, config generation, and dev server startup.
- Launch post says the manual path is `npx vinext init`, `npx vinext dev`, and `npx vinext deploy`.
- Project site says the recommended Agent Skill works with Cursor, Claude Code, Codex, and OpenCode.
- Project site says the CLI migration is `npx vinext init`.
- Project site says manual migration is installing vinext and replacing `next` with `vinext` in scripts.
- Project site says migration is non-destructive.
- Project site says an existing Next.js setup keeps working alongside vinext.
- Official sources reviewed do not provide a direct migration path from a plain React SPA to vinext.
- Cloudflare's React + Vite Workers guide remains the official React SPA path for Workers.
- Cloudflare's SPA docs say SPAs are client-side rendered and typically fetch data from APIs with client-side requests.
- Evidence-bound migration conclusion: Next.js migration is first-class; generic React SPA migration is not documented as a vinext path.

## Recent activity (last 60 days)

Window used: 2026-02-26 through 2026-04-26 America/Los_Angeles.

- npm package `vinext` has active publishing inside the window.
- npm observed versions from `0.0.10` on 2026-02-26 through `0.0.44` on 2026-04-24.
- That is 35 observed npm version publishes from `0.0.10` through `0.0.44`, inclusive.
- Latest observed npm version: `0.0.44`.
- Latest observed npm modified timestamp: 2026-04-24T20:39:04.410Z.
- GitHub releases page shows `v0.0.40` on 2026-04-07.
- GitHub releases page shows `v0.0.41` on 2026-04-09.
- GitHub releases page shows `v0.0.42` on 2026-04-21.
- GitHub releases page shows `v0.0.43` on 2026-04-22.
- GitHub releases page shows `v0.0.44` on 2026-04-24.
- GitHub API observed `pushed_at`: 2026-04-26T21:38:33Z.
- GitHub API observed `updated_at`: 2026-04-27T01:45:25Z.
- GitHub API observed open issues count: 103.
- GitHub API observed stargazers count: 7,915.
- GitHub API observed forks count: 317.
- GitHub commits API with `since=2026-02-26T00:00:00Z&per_page=1` returned a `Link` header with `rel="last"` page 517.
- Evidence-bound inference: at least 517 commits were reachable through that API query window, because each page contained one commit.
- Official Cloudflare launch blog is dated 2026-02-24.
- The launch blog is just outside a strict 60-day window ending 2026-04-26, but it is the official announcement that launched the project.
- No newer Cloudflare blog post about vinext was found in the official Cloudflare blog search results reviewed for this report.
- Official project site and GitHub releases show continuing activity after the launch post.

## Citations

- Cloudflare launch announcement, "How we rebuilt Next.js with AI in one week", 2026-02-24: https://blog.cloudflare.com/vinext/
- Cloudflare launch announcement lines for launch identity, motivation, benchmarks, Workers deployment, experimental status, production examples, and migration commands, accessed 2026-04-26: https://blog.cloudflare.com/vinext/
- Official repository README, `cloudflare/vinext`, accessed 2026-04-26: https://github.com/cloudflare/vinext
- Official repository releases page, latest release `v0.0.44` dated 2026-04-24, accessed 2026-04-26: https://github.com/cloudflare/vinext/releases
- Official project site, accessed 2026-04-26: https://vinext.io/
- GitHub repository API metadata, accessed 2026-04-26: https://api.github.com/repos/cloudflare/vinext
- GitHub commits API query for recent activity since 2026-02-26, accessed 2026-04-26: https://api.github.com/repos/cloudflare/vinext/commits?since=2026-02-26T00:00:00Z&per_page=1
- npm package metadata for `vinext`, observed with `npm view vinext version time --json` on 2026-04-26: https://www.npmjs.com/package/vinext
- Cloudflare Workers Vite plugin docs, last updated 2026-04-23, accessed 2026-04-26: https://developers.cloudflare.com/workers/vite-plugin/
- Cloudflare React + Vite Workers guide, accessed 2026-04-26: https://developers.cloudflare.com/workers/framework-guides/web-apps/react/
- Cloudflare Workers SPA routing docs, accessed 2026-04-26: https://developers.cloudflare.com/workers/static-assets/routing/single-page-application/
- Cloudflare `react-router-hono-fullstack-template` repository, accessed 2026-04-26: https://github.com/cloudflare/react-router-hono-fullstack-template
