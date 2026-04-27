# Sub-Question C — Styling findings

## Tailwind v4 actual status (and what came after)

1. As of 2026-04-26, Tailwind CSS has not been superseded by Tailwind v5 or v6.
2. The current official docs banner reads `v 4.2`.
3. The latest GitHub release is `v4.2.4`, published 2026-04-21.
4. npm package metadata reports `tailwindcss@4.2.4`, published 2026-04-21T13:15:55Z.
5. The official Tailwind Plus docs also say Tailwind Plus components target "the latest version of Tailwind CSS, which is currently Tailwind CSS v4.2."
6. Tailwind v4.0 was released 2025-01-22.
7. Tailwind v4.0 was a ground-up rewrite, not an incremental v3 update.
8. Tailwind v4.0 introduced a new high-performance engine, CSS-first config, automatic content detection, built-in import support, first-party Vite support, CSS theme variables, P3/OKLCH colors, first-class container queries, 3D transforms, expanded gradients, `@starting-style`, and `not-*`.
9. Tailwind v4.0 leaned heavily on modern CSS primitives: cascade layers, `@property`, `color-mix()`, logical properties, native variables, and modern nesting/import processing via Lightning CSS.
10. Tailwind's official compatibility page still says v4.0 is designed for modern browsers.
11. Tailwind's official browser floor is Chrome 111, Safari 16.4, and Firefox 128.
12. Tailwind v4.1, released 2025-04-03, added text shadows, mask utilities, colored drop shadows, pointer/any-pointer variants, last-baseline alignment, safe alignment, `@source not`, and `@source inline(...)`.
13. Tailwind v4.1 specifically addressed v4.0's weak older-browser degradation.
14. The v4.1 blog says Tailwind v4.0 went "all-in on modern platform features" and that some of those features degraded poorly in older browsers, especially older Safari.
15. The v4.1 blog says v4.1 added framework-specific fallbacks for older browsers while still targeting modern browsers.
16. That older-browser compatibility episode is the strongest primary-source explanation for why a user might call "Tailwind v4" dated or suspect: v4.0 carried a modern-browser bet that v4.1 had to soften.
17. The stronger evidence, however, is that Tailwind v4 is not deprecated, not superseded, and still actively maintained.
18. Tailwind's 2026 posture is "CSS build tool + utility authoring" rather than just "utility class library."
19. Tailwind's docs explicitly tell users not to pair Tailwind with Sass/Less/Stylus, because Tailwind now performs build-time imports, nesting transforms, variables, and prefixing.
20. Tailwind's docs also say native CSS nesting support is good enough that teams often do not need a preprocessor even without Tailwind.
21. Conclusion: "Tailwind v4 is dated" is not a factual version-status claim.
22. It is more plausibly a taste/architecture claim: in 2026, the newer story is open-code components, AI-readable component registries, headless primitives, and compile-time/type-safe styling.
23. What came after Tailwind v4 is not Tailwind v5; it is a split market:
24. Tailwind + shadcn/open-code remains the mainstream default.
25. Ark UI + Panda CSS is the canonical replacement path for teams leaving Park UI or wanting typed, build-time design-system styling.
26. Mantine v9 and Chakra UI v3 are current full component-library choices.
27. Native CSS + CSS Modules is increasingly credible for small-to-medium SPAs and for teams that want no styling DSL.

## Utility-first alternatives (current state)

1. UnoCSS remains the most credible atomic/utility-first alternative.
2. Current version: `unocss@66.6.8`, published 2026-04-08.
3. GitHub release: `v66.6.8`, published 2026-04-08.
4. Maintenance status: active.
5. Official docs describe UnoCSS as "the instant on-demand atomic CSS engine."
6. UnoCSS positions itself as the spiritual successor to Windi CSS.
7. UnoCSS docs say Windi CSS is no longer actively maintained as of March 2023.
8. UnoCSS differs from Tailwind by being an isomorphic atomic CSS engine with first-class integrations, optional features, and custom presets.
9. UnoCSS includes a Wind4 preset, which is an explicit Tailwind v4 compatibility signal.
10. UnoCSS is a finalist only when the team wants atomic CSS but more engine-level control and extensibility than Tailwind.
11. UnoCSS is not a market-wide Tailwind replacement in the primary-source data.
12. State of CSS 2025 ranked Tailwind CSS first among CSS frameworks with 2,041 responses and UnoCSS tenth with 154 responses.
13. Master CSS is still present, but it does not look like the canonical 2026 SPA choice.
14. Current package state: `@master/css@1.37.8`, last modified 2025-06-26.
15. Master CSS release state is weaker than UnoCSS: GitHub latest release shown by `gh release view` is `v1.37.7`, published 2022-11-11, while npm has later packages and 2.0.0 release candidates.
16. Master CSS official docs describe it as a "Virtual CSS language with enhanced syntax."
17. Master CSS emphasizes HTML-only styling, shorthand syntax, responsive suffixes, selectors in class attributes, hybrid rendering, AOT/JIT, and on-demand injection.
18. Master CSS is a niche finalist for teams that like its terse virtual-CSS syntax.
19. It is not evidenced as the displaced canonical replacement for Tailwind.
20. Other atomic/utility-first options found in primary sources:
21. Open Props appears in State of CSS 2025 CSS-framework results at rank 9 with 170 responses.
22. Atomizer appears in State of CSS 2025 utilities at rank 12 with 10 matching responses.
23. These are not evidenced as canonical SPA defaults for 2026 Q2.

## Compile-time CSS solutions (current state)

1. Panda CSS is the strongest compile-time design-system contender.
2. Current version: `@pandacss/dev@1.10.0`, published 2026-04-18.
3. GitHub release family: `@pandacss/core@1.10.0`, published 2026-04-18.
4. Maintenance status: active; recent release within the last 10 days of the requested date.
5. Project URL: https://panda-css.com/
6. Repository: https://github.com/chakra-ui/panda
7. Official docs describe Panda as a CSS-in-JS engine for the server-first era.
8. Panda's docs explicitly name runtime CSS-in-JS libraries such as Emotion and styled-components as challenged by Server Components/server-first frameworks.
9. Panda uses static analysis at build time and emits CSS files usable in any JavaScript framework.
10. Panda generates lightweight authoring/runtime helpers but does not generate or inject styles in the browser.
11. Panda provides type safety via `csstype` and generated typings.
12. Panda provides recipes, patterns, design tokens, JSX style props, and modern CSS output using cascade layers, CSS variables, `:where`, and `:is`.
13. Panda's own docs say it is a good choice for JavaScript applications with PostCSS support.
14. Panda's own docs say it is not the right fit for plain HTML/CSS, template-based PHP, or "absolute zero JS"; in those cases they recommend vanilla CSS or utility CSS.
15. In this research, Panda is the clearest successor to Park UI because Park was built on Panda CSS and Ark UI, and Park moved into the Chakra org.
16. vanilla-extract remains stable and credible.
17. Current version: `@vanilla-extract/css@1.20.1`, published 2026-03-28.
18. GitHub latest release from the monorepo is for `@vanilla-extract/webpack-plugin@2.3.27`, published 2026-04-12, showing ongoing maintenance.
19. Project URL: https://vanilla-extract.style/
20. Repository: https://github.com/vanilla-extract-css/vanilla-extract
21. Official docs describe vanilla-extract as zero-runtime stylesheets in TypeScript.
22. vanilla-extract generates static CSS at build time.
23. It supports type-safe scoped classes, variables, themes, selectors, pseudo-classes, media queries, feature queries, container queries, keyframes, font-face, and global styles.
24. It is framework-agnostic and has official integrations for webpack, esbuild, Vite, and Next.js.
25. In 2026, vanilla-extract is the conservative type-safe CSS-in-TS option.
26. It is less tightly connected to a current component/open-code ecosystem than Panda.
27. StyleX is active and credible, especially for Meta-style large React codebases.
28. Current version: `@stylexjs/stylex@0.18.3`, published 2026-04-20.
29. Latest GitHub release visible via `gh release view`: `0.17.5`, published 2026-01-21.
30. Project URL: https://stylexjs.com/
31. Repository: https://github.com/facebook/stylex
32. Official docs describe StyleX as a JavaScript syntax and compiler for styling web apps.
33. StyleX emits optimized collision-free atomic CSS.
34. StyleX has no runtime style injection and generates a static CSS file at compile time.
35. StyleX has a tiny runtime for merging class names.
36. StyleX is framework-agnostic across React-compatible `className`/`style` environments.
37. StyleX is a finalist when a team wants colocated typed styles and atomic CSS output without Tailwind syntax.
38. It is not evidenced as the common default for ordinary new SPAs.
39. Pigment CSS is not a canonical general SPA pick yet.
40. Current version: `@pigment-css/react@0.0.30`, published 2025-01-14.
41. GitHub release: `v0.0.30`, published 2025-01-14.
42. Maintenance status: low visible release activity since early 2025, but still documented by MUI.
43. Project URL: https://pigment-css.com/
44. Repository: https://github.com/mui/pigment-css
45. MUI's migration docs still describe Pigment CSS as early alpha.
46. MUI docs say Pigment CSS can be used with Next.js App Router with webpack v5 and Vite.
47. MUI docs say Turbopack is not supported yet.
48. MUI docs say Pigment is intended to solve Emotion's client-side recalculation and incomplete RSC support while keeping CSS-in-JS authoring.
49. Pigment CSS is best understood as a Material UI migration path, not a general canonical SPA styling choice.

## Component-tier styling (current state)

1. Ark UI is the canonical headless primitive layer in the Chakra/Park/Panda lineage.
2. Current version: `@ark-ui/react@5.36.2`, published 2026-04-22.
3. GitHub release family: latest `@ark-ui/svelte@5.21.2`, published 2026-04-22.
4. Project URL: https://ark-ui.com/
5. Repository: https://github.com/chakra-ui/ark
6. Maintenance status: active.
7. Official docs describe Ark UI as unstyled UI components for design systems.
8. Ark UI lists 45+ accessible components across React, Solid, Vue, and Svelte.
9. Ark UI docs explicitly say teams can bring Panda, Tailwind, CSS-in-JS, or plain stylesheets.
10. Ark UI is state-machine powered through the Chakra/Zag ecosystem.
11. Park UI uses Ark UI underneath.
12. Chakra UI is the full component-system option in the same ecosystem.
13. Current version: `@chakra-ui/react@3.35.0`, published 2026-04-22.
14. GitHub release family: `@chakra-ui/charts@3.35.0`, published 2026-04-22.
15. Project URL: https://www.chakra-ui.com/
16. Repository: https://github.com/chakra-ui/chakra-ui
17. Maintenance status: active.
18. Chakra docs show Vite, TanStack Router, Next App Router, Remix, and Storybook guides.
19. Chakra v3 docs also expose agent-facing docs, MCP server, LLM text, and AI rules.
20. Chakra v3 is a current full component library, not dated in version status.
21. Mantine is the strongest batteries-included React component-library finalist.
22. Current version: `@mantine/core@9.1.0`, published 2026-04-21.
23. GitHub release: `9.1.0`, published 2026-04-21.
24. Project URL: https://mantine.dev/
25. Repository: https://github.com/mantinedev/mantine
26. Maintenance status: active.
27. Mantine homepage now says v9.1.0.
28. Mantine docs describe 120+ customizable components and 70+ hooks.
29. Mantine explicitly presents itself as built for AI-assisted workflows with LLM docs, skills, and an MCP server regenerated every release.
30. The user named Mantine v8 as "newer"; primary sources show that by 2026 Q2 the current Mantine line is v9, not v8.
31. shadcn/ui remains current.
32. Current CLI/package: `shadcn@4.5.0`, published 2026-04-25.
33. GitHub release: `shadcn@4.5.0`, published 2026-04-25.
34. Project URL: https://ui.shadcn.com/
35. Repository: https://github.com/shadcn-ui/ui
36. Maintenance status: highly active.
37. shadcn/ui docs call it a set of accessible components and a code-distribution platform.
38. shadcn/ui docs explicitly say it is not a component library; it is how you build your component library.
39. shadcn/ui's 2026 documentation emphasizes open code, composition, distribution via schema/CLI, beautiful defaults, and AI-readiness.
40. shadcn/ui is the clearest mainstream "what displaced component libraries" answer.
41. Restyle is not a 2026 SPA finalist.
42. Current version: `@shopify/restyle@2.4.5`, published 2025-03-19.
43. Repository: https://github.com/Shopify/restyle
44. Maintenance status: not visibly current for web SPA needs.
45. Restyle targets React Native styling/design systems, not browser SPA styling.
46. Linaria remains active but not the default.
47. Current core package: `@linaria/core@7.0.0`, published 2026-01-26.
48. GitHub latest release: `linaria@7.0.1`, published 2026-01-26.
49. Repository: https://github.com/callstack/linaria
50. Maintenance status: active enough, but its main role is zero-runtime CSS-in-JS for teams already committed to that authoring model.

## Native CSS posture in 2026

1. Native CSS has reached a point where abstraction is optional for many SPAs.
2. This does not mean all teams should skip styling tools.
3. It means the default burden of proof has shifted: use a styling abstraction when it adds design-system governance, component distribution, type safety, or workflow speed.
4. W3C CSS Snapshot 2026 was published as a Group Note on 2026-03-26.
5. The snapshot says it collects the specs that form the current state of CSS as of 2026.
6. The snapshot includes CSS Cascading and Inheritance Level 5 as a reliable candidate recommendation and specifically identifies cascade layers.
7. The snapshot includes CSS Grid Level 2/subgrid as a reliable candidate recommendation.
8. The snapshot includes CSS Color Level 4 in the official definition, covering extended color spaces beyond sRGB.
9. Tailwind's own docs implicitly reinforce the native-CSS posture:
10. Tailwind says if you can use Tailwind v4, you can use native CSS variables.
11. Tailwind says native CSS nesting support is very good.
12. Tailwind says browsers support `min()`, `max()`, and `round()` natively.
13. Tailwind v4's own architecture is built on native cascade layers, custom properties, `@property`, `color-mix()`, logical properties, and container queries.
14. State of CSS 2025 shows "None" ranked third in CSS frameworks, with 1,061 responses.
15. State of CSS 2025 shows "Custom/in-house framework" ranked fourth, with 953 responses.
16. State of CSS 2025 shows "None" ranked first in CSS-in-JS with 2,110 responses.
17. State of CSS 2025 shows CSS Modules ranked second in CSS-in-JS with 1,037 responses.
18. This supports the claim that many teams are skipping runtime CSS-in-JS and/or CSS frameworks.
19. It does not prove that native CSS is the single canonical choice.
20. Practical 2026 native CSS posture:
21. Use native CSS + CSS Modules when the UI surface is small or design tokens are simple.
22. Use CSS Modules plus cascade layers, nesting, variables, container queries, and `:has()`/modern selectors when framework-neutral clarity matters more than utility speed.
23. Use vanilla-extract when native CSS is desired but token contracts and TypeScript-enforced theming matter.
24. Use Panda when native CSS output is desired but the authoring model should stay token/recipe/style-prop driven.

## Park UI — actual status + replacements

1. Park UI is not deprecated in primary sources.
2. Park UI joined the Chakra UI organization on 2025-11-27.
3. The announcement says "Nothing breaks" and imports keep working.
4. The announcement says docs remain at park-ui.com.
5. The announcement says Park UI benefits from Chakra resources and tighter integration.
6. Park UI's docs remain live in 2026.
7. Current package state: `@park-ui/panda-preset@0.43.1`, published 2024-11-22.
8. GitHub release: `@park-ui/panda-preset@0.43.1`, published 2024-11-22.
9. Project URL: https://park-ui.com/
10. Repository: https://github.com/chakra-ui/park-ui
11. Maintenance status: docs and ecosystem active, but package release activity is older than Ark/Panda/Chakra.
12. Park UI docs describe it as a component system and code-distribution platform.
13. Park UI is built with Panda CSS.
14. Park UI components are built on top of Ark UI.
15. Park UI distributes source code rather than shipping as a single npm component package.
16. Park UI's open-code model overlaps strongly with shadcn/ui.
17. The most likely reason a user calls Park UI "dated" is that Park was an earlier Ark+Panda open-code layer whose ecosystem now lives under Chakra.
18. Replacement path A: use Ark UI raw + Panda CSS for a custom design system.
19. Replacement path B: use Chakra UI v3 for a full batteries-included system from the same organization.
20. Replacement path C: use shadcn/ui if the desired model is open-code components and Tailwind is acceptable.
21. Replacement path D: use Mantine v9 if the desired model is a complete React component library with less styling architecture work.
22. Replacement path E: use Ark UI + Tailwind via projects like Tark UI/Shark UI if the team wants Ark primitives but Tailwind classes.

## Component-library + styling combinations actually shipping in 2026 Q2

1. Primary sources do not support a single universal "canonical" styling winner for 2026 Q2.
2. They do support a narrowed set of current, actively maintained combinations.
3. Most mainstream open-code SPA default:
4. `shadcn/ui + Tailwind CSS v4.2`
5. Evidence: shadcn CLI release 2026-04-25; Tailwind 4.2.4 release 2026-04-21; Tailwind Plus targets Tailwind v4.2; State of CSS 2025 ranks Tailwind #1 and shadcn/ui #5 among CSS frameworks.
6. Why teams pick it in 2026: fast component assembly, open code ownership, AI-readable component code, and the largest visible adoption footprint.
7. Best answer if the user rejects Tailwind and Park:
8. `Ark UI + Panda CSS`
9. Evidence: Ark release 2026-04-22; Panda release 2026-04-18; Park moved into Chakra and was built on Ark/Panda; Panda is explicitly server-first/build-time/type-safe.
10. Why teams pick it in 2026: accessible headless primitives plus type-safe token/recipe styling without runtime style injection.
11. Best full React component-library answer:
12. `Mantine v9`
13. Evidence: Mantine v9.1.0 release 2026-04-21 and homepage says v9.1.0; docs advertise 120+ components, 70+ hooks, AI docs, skills, and MCP.
14. Why teams pick it in 2026: complete React app surface with high coverage and low design-system assembly cost.
15. Best Chakra ecosystem answer:
16. `Chakra UI v3`
17. Evidence: Chakra v3.35.0 package/release 2026-04-22; docs show Vite/TanStack/Next/Remix support and AI/MCP docs.
18. Why teams pick it in 2026: integrated accessible React components, theming, snippets, and Chakra/Panda/Ark ecosystem alignment.
19. Best type-safe CSS-in-TS answer:
20. `vanilla-extract`
21. Evidence: current package 1.20.1 published 2026-03-28; official docs emphasize zero-runtime static CSS and type-safe themes.
22. Why teams pick it in 2026: CSS Modules-like output with TypeScript-enforced tokens and no runtime CSS engine.
23. Best large-codebase atomic CSS-in-JS answer:
24. `StyleX`
25. Evidence: current package 0.18.3 published 2026-04-20; official docs emphasize compile-time static CSS, atomic output, no runtime style injection, and type-safe APIs.
26. Why teams pick it in 2026: Meta-style scale, predictable override semantics, and small CSS growth as codebase grows.
27. MUI-specific migration answer:
28. `Material UI + Pigment CSS`
29. Evidence: MUI docs continue to document Pigment migration, but call it early alpha; latest Pigment package/release is 0.0.30 from 2025-01-14.
30. Why teams pick it in 2026: RSC-compatible, lower-runtime-cost styling for MUI migration, not a general default.
31. Utility-first alternative answer:
32. `UnoCSS`
33. Evidence: UnoCSS v66.6.8 release 2026-04-08; docs position it as flexible atomic engine and Windi successor.
34. Why teams pick it in 2026: custom atomic conventions, build-tool integrations, optional presets, and a Tailwind-compatible escape hatch.
35. Finalist table:
36. Tailwind CSS | https://tailwindcss.com/ | v4.2.4 | 2026-04-21 | active | picked for mainstream utility workflow, ecosystem, Tailwind Plus, shadcn compatibility.
37. shadcn/ui | https://ui.shadcn.com/ | `shadcn@4.5.0` | 2026-04-25 | active | picked for open-code components and AI-readable ownership.
38. Panda CSS | https://panda-css.com/ | `@pandacss/dev@1.10.0` | 2026-04-18 | active | picked for typed design-system styling, recipes, and build-time CSS.
39. Ark UI | https://ark-ui.com/ | `@ark-ui/react@5.36.2` | 2026-04-22 | active | picked for accessible headless primitives across frameworks.
40. Chakra UI | https://www.chakra-ui.com/ | `@chakra-ui/react@3.35.0` | 2026-04-22 | active | picked for a complete accessible React component system.
41. Mantine | https://mantine.dev/ | `@mantine/core@9.1.0` | 2026-04-21 | active | picked for broad component/hook coverage and fast SPA delivery.
42. vanilla-extract | https://vanilla-extract.style/ | `@vanilla-extract/css@1.20.1` | 2026-03-28 | active | picked for zero-runtime, type-safe CSS-in-TS.
43. StyleX | https://stylexjs.com/ | `@stylexjs/stylex@0.18.3` | 2026-04-20 | active | picked for compile-time atomic CSS with type safety and predictable composition.
44. UnoCSS | https://unocss.dev/ | `unocss@66.6.8` | 2026-04-08 | active | picked for atomic CSS engine flexibility.
45. Park UI | https://park-ui.com/ | `@park-ui/panda-preset@0.43.1` | 2024-11-22 | ecosystem active, package older | picked when adopting existing Ark/Panda open-code components.
46. Pigment CSS | https://pigment-css.com/ | `@pigment-css/react@0.0.30` | 2025-01-14 | alpha/low visible release cadence | picked for MUI migration experiments.
47. Linaria | https://linaria.dev/ | `@linaria/core@7.0.0` / `linaria@7.0.1` release | 2026-01-26 | active | picked for zero-runtime CSS-in-JS.
48. Master CSS | https://css.master.co/ | `@master/css@1.37.8` | 2025-06-26 npm package metadata | niche/less visibly current | picked for terse virtual-CSS syntax.
49. Restyle | https://github.com/Shopify/restyle | `@shopify/restyle@2.4.5` | 2025-03-19 | React Native-oriented | not a browser SPA finalist.
50. Actual current canonical choice under the user's constraints:
51. If Tailwind and Park are explicitly rejected, choose `Ark UI + Panda CSS` for a custom SPA design system.
52. If the project wants speed over bespoke design-system infrastructure, choose `Mantine v9`.
53. If Tailwind is not actually banned and "dated" only meant "v4.0 had rough edges," the strongest mainstream default remains `shadcn/ui + Tailwind CSS v4.2`.
54. Evidence does not support "Tailwind v4 was displaced by Tailwind v5."
55. Evidence does support "Park UI was absorbed into the Chakra/Ark/Panda ecosystem."

## Citations

1. Tailwind CSS v4.0 official blog, 2025-01-22: https://tailwindcss.com/blog/tailwindcss-v4
2. Tailwind CSS v4.1 official blog, 2025-04-03: https://tailwindcss.com/blog/tailwindcss-v4-1
3. Tailwind CSS compatibility docs, current docs banner v4.2, fetched 2026-04-26: https://tailwindcss.com/docs/compatibility
4. Tailwind CSS GitHub release `v4.2.4`, 2026-04-21: https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.2.4
5. Tailwind Plus setup docs, current Tailwind v4.2 requirement, fetched 2026-04-26: https://tailwindcss.com/plus/ui-blocks/documentation
6. Headless UI homepage, current v2.x docs, fetched 2026-04-26: https://headlessui.com/
7. Headless UI GitHub release `@headlessui/react@v2.2.10`, 2026-04-07: https://github.com/tailwindlabs/headlessui/releases/tag/%40headlessui/react%40v2.2.10
8. Catalyst introduction, 2023-12-20: https://tailwindcss.com/blog/introducing-catalyst
9. State of CSS 2025 Other Tools results, fetched 2026-04-26: https://2025.stateofcss.com/en-US/other-tools/
10. UnoCSS docs, current docs banner v66.6.8, fetched 2026-04-26: https://unocss.dev/guide/why
11. UnoCSS GitHub release `v66.6.8`, 2026-04-08: https://github.com/unocss/unocss/releases/tag/v66.6.8
12. Master CSS official site, fetched 2026-04-26: https://css.master.co/
13. Master CSS GitHub release `v1.37.7`, 2022-11-11: https://github.com/master-co/css/releases/tag/v1.37.7
14. Panda CSS docs, "Why Panda", fetched 2026-04-26: https://panda-css.com/docs/overview/why-panda
15. Panda CSS GitHub release family `@pandacss/core@1.10.0`, 2026-04-18: https://github.com/chakra-ui/panda/releases/tag/%40pandacss/core%401.10.0
16. vanilla-extract official docs, fetched 2026-04-26: https://vanilla-extract.style/
17. vanilla-extract GitHub latest monorepo release `@vanilla-extract/webpack-plugin@2.3.27`, 2026-04-12: https://github.com/vanilla-extract-css/vanilla-extract/releases/tag/%40vanilla-extract/webpack-plugin%402.3.27
18. StyleX docs, fetched 2026-04-26: https://stylexjs.com/docs/learn/
19. StyleX GitHub release `0.17.5`, 2026-01-21: https://github.com/facebook/stylex/releases/tag/0.17.5
20. Pigment CSS introduction, MUI blog, 2024-05-16: https://mui.com/blog/introducing-pigment-css/
21. MUI Pigment CSS migration docs, Material UI docs banner v9.0.0, fetched 2026-04-26: https://mui.com/material-ui/migration/migrating-to-pigment-css/
22. Pigment CSS GitHub release `v0.0.30`, 2025-01-14: https://github.com/mui/pigment-css/releases/tag/v0.0.30
23. Linaria GitHub release `linaria@7.0.1`, 2026-01-26: https://github.com/callstack/linaria/releases/tag/linaria%407.0.1
24. Restyle GitHub release `v2.4.5`, 2025-03-19: https://github.com/Shopify/restyle/releases/tag/v2.4.5
25. Ark UI homepage, fetched 2026-04-26: https://ark-ui.com/
26. Ark UI GitHub release family `@ark-ui/svelte@5.21.2`, 2026-04-22: https://github.com/chakra-ui/ark/releases/tag/%40ark-ui/svelte%405.21.2
27. Park UI joins Chakra UI organization, 2025-11-27: https://park-ui.com/blog/park-ui-joins-the-chakra-ui-organization
28. Park UI docs, fetched 2026-04-26: https://park-ui.com/docs/introduction
29. Park UI GitHub release `@park-ui/panda-preset@0.43.1`, 2024-11-22: https://github.com/chakra-ui/park-ui/releases/tag/%40park-ui/panda-preset%400.43.1
30. Chakra UI Vite docs, docs banner v3.35.0, fetched 2026-04-26: https://www.chakra-ui.com/docs/get-started/frameworks/vite
31. Chakra UI GitHub release family `@chakra-ui/charts@3.35.0`, 2026-04-22: https://github.com/chakra-ui/chakra-ui/releases/tag/%40chakra-ui/charts%403.35.0
32. Mantine homepage, docs banner v9.1.0, fetched 2026-04-26: https://mantine.dev/
33. Mantine GitHub release `9.1.0`, 2026-04-21: https://github.com/mantinedev/mantine/releases/tag/9.1.0
34. shadcn/ui docs, fetched 2026-04-26: https://ui.shadcn.com/docs
35. shadcn/ui GitHub release `shadcn@4.5.0`, 2026-04-25: https://github.com/shadcn-ui/ui/releases/tag/shadcn%404.5.0
36. W3C CSS Snapshot 2026, Group Note, 2026-03-26: https://www.w3.org/TR/css-2026/
37. npm registry package metadata fetched with `npm view` on 2026-04-26 for current package versions and publish times: `tailwindcss`, `unocss`, `@pandacss/dev`, `@stylexjs/stylex`, `@vanilla-extract/css`, `@pigment-css/react`, `@linaria/core`, `@shopify/restyle`, `@ark-ui/react`, `@park-ui/panda-preset`, `@chakra-ui/react`, `@mantine/core`, `shadcn`, `@headlessui/react`, `@master/css`.
