# Sub-Question D — Modern vanilla CSS findings

Date basis: user requested 2026-04-26. Live web/npm sources were checked during
this run; caniuse pages used StatCounter March 2026 usage data where shown.

## Browser-native CSS feature matrix (2026 Q2)

Summary: "modern vanilla CSS" in 2026 means authored CSS using native cascade
control, native component responsiveness, native design tokens, and selective
build-tool help for hashing/types. It does not mean "no build step" for a SPA.

| Feature | 2026 browser support | Spec status | SPA styling implication |
|---|---:|---|---|
| Cascade layers (`@layer`) | caniuse global 95.29%; Chrome 99+, Safari 15.4+, Firefox 97+ | CSS Cascade 5; caniuse marks CR | Production-ready. Use for reset/base/tokens/components/utilities/overrides order. |
| CSS Nesting | caniuse global 91.83%; Chrome 120+, Safari 17.2+, Firefox 117+ | CSS Nesting Level 1; W3C WD 2026-01-22 | Production-ready for evergreen SPA targets. Keep nesting shallow to preserve readability. |
| `:has()` | caniuse global 94.31%; Chrome 105+, Safari 15.4+, Firefox 121+ | Selectors Level 4; W3C WD 2026-01-22 | Production-ready for state styling, parent styling, and form wrappers. Avoid treating it as a JS state replacement for complex behavior. |
| Container queries, size | caniuse global 94.05%; Chrome 106+, Safari 16.0+, Firefox 110+ | CSS Containment 3; caniuse marks WD | Production-ready. Use `container-type: inline-size` on component shells and `@container` for cards/tables/forms. |
| Container queries, style | caniuse shows 88.97% partial support; Firefox not supported | CSS Containment 3 WD | Do not make core behavior depend on style queries yet. Size queries are the stable part. |
| `@scope` | caniuse global 91.08%; Chrome 118+, Safari 17.4+, Firefox 146+ | CSS Cascade 6; W3C WD | Usable for progressive local scoping, but CSS Modules are still safer for component scoping in a TS SPA. |
| Custom properties | caniuse global 97.21%; Chrome 49+, Safari 10+, Firefox 31+ | CSS Custom Properties Level 1; caniuse marks CR | The default token substrate. Use for theme, density, spacing, typography, radii, shadows. |
| `color-mix()` | caniuse global 92.8%; Chrome 111+, Safari 16.2+, Firefox 113+ | CSS Color 5 WD | Production-ready for derived states if evergreen browsers are acceptable. Prefer precomputed critical contrast tokens. |
| `light-dark()` | caniuse global 90.02%; Chrome 123+, Safari 17.5+, Firefox 120+ | CSS Color 5 WD | Useful for native light/dark token pairs when paired with `color-scheme`; not enough alone for named app themes. |
| `@property` / registered custom properties | caniuse global 94.73%; Chrome 85+, Safari 16.4+, Firefox 128+ | CSS Properties and Values API Level 1 WD | Use selectively for animatable numeric/color tokens and guardrail typing, not for every token. |
| Anchor positioning | caniuse global 85.14%; Chrome 125+, Safari 26.0+, Firefox 147+ | CSS Anchor Positioning Level 1 WD | Emerging. Good for progressive menus/tooltips, but keep JS/Floating UI fallback if older Safari/Firefox matters. |
| View Transitions API, single document | caniuse global 90.94%; Chrome 111+, Safari 18.0+, Firefox 144+ | CSS View Transitions Level 1 WD | Good for SPA route/state transitions with `prefers-reduced-motion` guard. Cross-document support is separate and less relevant to a SPA. |
| `subgrid` | caniuse global 92.48%; Chrome 117+, Safari 16.0+, Firefox 71+ | CSS Grid Layout Level 2 CR | Production-ready. Good fit for admin forms, definition lists, and table-shaped card rows. |
| Modern color spaces: `oklch()`, `lch()`, `lab()`, `color(display-p3 ...)` | `oklch()` caniuse global 93.29%; `lch()/lab()` 93.32%; `color()` 93.27% | CSS Color 4 CR, CSS Color 5 WD for newer functions | Use OKLCH for authoring tokens; emit fallback sRGB for email/legacy/third-party surfaces if needed. |

Native CSS takeaways:

- The stable core for an evergreen SPA is now real: `@layer`, nesting, `:has()`,
  size container queries, custom properties, OKLCH, `color-mix()`, and subgrid.
- `@scope` is broadly available in the major evergreen line, but it is still a
  spec-level draft feature and does not give TypeScript import ergonomics.
- Anchor positioning and View Transitions are useful, but should be treated as
  progressive enhancement around component primitives, not as the foundation.
- "Runtime theme without runtime" means CSS custom properties plus selectors:
  `:root`, `[data-theme="dark"]`, `@media (prefers-color-scheme: dark)`, and
  `color-scheme: light dark`.
- "Utility-ish ergonomics" in vanilla CSS means tokenized classes and component
  helpers, not re-creating Tailwind's full atomic surface.

## CSS Modules in 2026

Build-tool support:

- Vite 8.0.10 docs: CSS imported from JS is injected with HMR; files ending in
  `.module.css` are CSS Modules; imports return a class mapping object; CSS
  Modules behavior is configurable through `css.modules`.
- Vite also supports named imports when `css.modules.localsConvention` enables
  camel-case locals. Vite's built-in client types cover generic CSS module
  imports, but not exact generated class-name unions.
- Rsbuild docs: CSS Modules are supported by default for `*.module.*`; docs
  explicitly show generated `.module.css.d.ts` declaration files after build.
- Rsbuild `output.cssModules` exposes `auto`, `exportLocalsConvention`, and
  `namedExport`, based on css-loader's module options.
- Bun docs: the bundler has built-in CSS support, CSS Modules, minification, and
  Lightning CSS-derived lowering/prefixing. It targets modern browsers by
  default and can lower nesting and modern color syntax.
- Bun's current package docs are useful for libraries/tools, but Vite remains
  the safer default for a Solid SPA because Solid's ecosystem and HMR path are
  Vite-centered.

TypeScript declaration posture:

- Vite's generic `vite/client` declaration makes `import styles from
  './x.module.css'` legal, but the default type is not a precise map of each
  class name.
- Exact class-name typing is a plugin/tooling choice in Vite: examples include
  `typed-css-modules`, `typescript-plugin-css-modules`, and Vite CSS module
  typing plugins.
- `typescript-plugin-css-modules` is IDE/language-service oriented; it does not
  by itself make `tsc` fail on missing CSS classes unless generated `.d.ts`
  files or a build-time checker are in place.
- Rsbuild is stronger out of the box if `.d.ts` generation for CSS Modules is a
  first-class requirement.

Composition (`composes:`) in 2026:

- CSS Modules still documents `composes:` for combining local classes.
- The CSS Modules docs warn that composing multiple classes from different files
  gives undefined order for conflicting properties and should stay hierarchical.
- In a 2026 app with cascade layers and tokens, `composes:` should be narrow:
  okay for same-file class reuse or primitive class composition; not good as the
  main design-system inheritance mechanism.
- Prefer `@layer` for global ordering, custom properties for variants, and
  explicit component classes for component behavior.

CSS Modules vs vanilla-extract for theme tokens:

- CSS Modules keep authoring in real `.css`, preserve readable output, and work
  well with native custom properties.
- vanilla-extract is zero-runtime "stylesheets in TypeScript"; it generates
  static CSS at build time, supports scoped classes, variables, selectors,
  media/feature/container queries, keyframes, and type-safe theme contracts.
- vanilla-extract is better when the team wants token contracts enforced by TS
  and theme objects authored in TS.
- CSS Modules are better when the project wants readable hand-authored CSS,
  easier browser-devtools mapping, less styling DSL, and fewer build concepts.
- For this project posture ("modern vanilla CSS"), CSS Modules plus native CSS
  variables fits better than vanilla-extract as the primary system. Use
  vanilla-extract only if typed token contracts become more valuable than plain
  CSS readability.

## Token systems (Open Props, Style Dictionary, etc.)

Style Dictionary:

- Current npm observed: `style-dictionary` 5.4.0, modified 2026-03-22.
- Official docs position Style Dictionary as a design-token build system that
  exports tokens to CSS, JS, HTML, native platforms, and docs.
- It is useful if Humility later needs cross-platform tokens or Figma/Tokens
  Studio ingestion.
- For a single web SPA, it may be more ceremony than needed at first. A native
  `tokens.css` file can graduate to Style Dictionary later.

Open Props:

- Current npm observed: `open-props` 1.7.23, modified 2026-01-31.
- Open Props is a library of "sub-atomic" CSS custom properties: sizes, fonts,
  shadows, gradients, easing, colors, etc.
- It is useful as a reference/token palette, but importing all of it can make
  the token surface too broad for an admin product.
- Good use: borrow naming/scale ideas or import a curated subset.
- Risk: adopting Open Props wholesale can become a second design system that
  competes with app-specific semantic tokens.

Open Props UI:

- No official `@open-props/ui` npm package was found. `npm search` found
  `opui-blocks` 0.2.0 and secondary listings.
- A current third-party listing describes Open Props UI v3.3.5, dated
  2026-02-19, as a copy-paste CSS component library using container queries,
  CSS layers, and OKLCH.
- Treat Open Props UI as inspiration/copy-paste reference, not a dependency to
  anchor production architecture.

Pico CSS / browser-default-leaning CSS:

- Current npm observed: `@picocss/pico` 2.1.1, modified 2025-03-15.
- Pico v2 is good for content-heavy docs and light forms because it leans on
  semantic HTML defaults.
- It is less suitable as the primary system for a dense admin SPA with custom
  dashboards, data tables, modals, and public/officer surfaces.

Sakura:

- Current npm observed: `sakura.css` 1.5.1, modified 2025-06-24.
- Sakura is a classless/minimal stylesheet for readable documents.
- Not a fit for a component-heavy SPA except as reference for baseline content
  typography.

Tachyons / modern atomic CSS:

- Current npm observed: `tachyons` 4.12.0, modified 2023-06-07.
- Tachyons is a historical atomic CSS system. It can supply utility-class ideas,
  but it does not represent the 2026 native-CSS direction better than local
  token utilities and layers.

Native custom-property token system:

- Best starting point for Humility:
  `src/styles/tokens.css`, `theme.css`, `reset.css`, `base.css`,
  `utilities.css`, and component `*.module.css`.
- Token layers:
  1. primitive tokens: raw OKLCH colors, spacing steps, font sizes, radii,
     shadows, z-index, motion.
  2. semantic tokens: `--color-bg`, `--color-surface`, `--color-border`,
     `--color-text`, `--color-accent`, `--color-danger`.
  3. component tokens: `--button-bg`, `--field-border`, `--table-row-hover`.
- Theme switching should override semantic tokens, not every component class.
- Use OKLCH for source tokens, but use semantic names in components.

## Real-world SPA examples that ship without Tailwind in 2026

Evidence found:

- Vercel has an official Geist Design System site with foundations and many
  product components: buttons, inputs, modals, tables, tooltips, drawers, tabs,
  theme switcher, etc.
- Vercel also has an official Tailwind template directory listing many Tailwind
  examples, including AI chatbot, SaaS starter, ecommerce, email client, and
  other Vercel templates.
- Therefore Vercel cannot be cited as a "no Tailwind" proof point. It is proof
  that serious teams maintain a design system and also tolerate Tailwind in
  examples/templates.
- Solid's own docs explicitly list CSS Modules, CSS preprocessors, CSS-in-JS,
  Tailwind, and UnoCSS as supported styling choices. Solid does not prescribe
  "vanilla CSS only."
- Solid site metadata from third-party crawls indicates Solid's own docs/site
  may use Tailwind; do not use Solid itself as evidence that "everyone moved to
  vanilla CSS."

Evidence not found in primary sources:

- No 2026 Q1/Q2 primary-source engineering post from Linear was found that says
  Linear chose "no Tailwind, native CSS" for its production app.
- No 2026 Q1/Q2 primary-source engineering post from Stripe was found that says
  Stripe's web property uses "no Tailwind, native CSS" as a named strategy.
- No broad 2026 primary-source corpus was found where large SPA teams publicly
  declare a mass migration from Tailwind to vanilla CSS.

Reasonable inference from available sources:

- The strongest current trend is not "everyone uses vanilla CSS instead of
  Tailwind."
- The stronger claim is: browser-native CSS is now capable enough that teams can
  build component systems with CSS Modules, layers, variables, container
  queries, `:has()`, OKLCH, and subgrid without Sass/Tailwind/Panda.
- Utility-first CSS remains common in templates and public examples.
- Design-system-heavy product teams often hide implementation details behind
  internal primitives, so public sentiment is a weak proxy for production use.

## Recommended pattern for a Solid 2 + Vite SPA

Version caveat:

- npm observed `solid-js` latest as 1.9.12; `next` was 2.0.0-beta.8.
- If the project says "Solid 2", treat that as beta/next unless the team has
  separately locked a stable Solid 2 release.
- The CSS strategy below works for Solid 1.x and Solid 2 because it relies on
  Vite CSS handling and standard JSX `class` bindings, not framework-specific
  runtime styling.

File layout:

- `apps/web/src/styles/layers.css`: declares `@layer reset, tokens, theme,
  base, components, utilities, overrides;`.
- `apps/web/src/styles/{reset,tokens,theme,base,utilities}.css`: global
  primitives and utilities.
- `apps/web/src/components/*/*.module.css`: component internals.
- `apps/web/src/components/*/*.tsx`: imports module maps and uses Solid's
  normal `class={styles.root}` binding.

Authoring shape:

- Put `color-scheme: light dark` and primitive spacing/radius/type/color tokens
  in `@layer tokens`.
- Put `[data-theme="light"]` and `[data-theme="dark"]` semantic token overrides
  in `@layer theme`.
- Put component classes in `@layer components`, with `container-type:
  inline-size` on shells that need local responsiveness.
- Use `:has(:focus-visible)` for local wrapper state, `@container` for
  component breakpoints, and `subgrid` for nested admin/form alignment.

Type safety:

- Keep `vite/client` types for generic CSS imports.
- Add generated `.module.css.d.ts` files or a Vite plugin if exact class-name
  typing is required.
- Enforce `localsConvention: "camelCaseOnly"` or a team rule that CSS class
  names are TS-friendly identifiers. Do not mix dash and camel access styles.

Theme switching:

- Store theme as `data-theme` on `<html>` or the app root.
- Set `color-scheme` in CSS so form controls, scrollbars, and built-in UI match.
- Use `@media (prefers-color-scheme: dark)` only for default selection when no
  explicit user preference exists.
- Do not generate theme classes at runtime. Theme is token overrides.

Scoping:

- Primary component scoping: CSS Modules.
- Local cascade control: `:where()` to keep selector specificity low.
- `@scope`: use sparingly for global page regions or docs/content islands, not
  as a replacement for CSS Modules yet.
- `:has()`: use for local state styling such as field wrapper focus/invalid,
  selected rows, cards with checked inputs, and disclosure state.

Utility-ish ergonomics:

- Provide a small, named utility layer:
  `.stack`, `.cluster`, `.grid`, `.visuallyHidden`, `.truncate`, `.bleed`,
  `.textSm`, `.textLg`, `.muted`, `.danger`.
- Use custom properties for spacing and type scale, not hundreds of atomic
  classes.
- If a utility appears in only one component, keep it in that component module.
- If a utility encodes product-wide rhythm or accessibility, promote it to the
  global utility layer.

Readable build output:

- Configure CSS Module names in dev as `[name]__[local]__[hash:base64:5]`.
- Production can use shorter hashes, but keep source maps.
- Avoid CSS-in-JS runtime libraries if readable final CSS and no runtime are
  goals.
- Avoid global class names for component internals; reserve globals for tokens,
  base elements, layout utilities, and explicit app shell regions.

## "Everyone is doing this" sanity check (is it really everyone, or is it a subset?)

The user's claim is overstated as a factual market statement.

What is true:

- Native CSS in 2026 is much stronger than the CSS environment that made
  Tailwind/Sass/styled-components feel necessary.
- An evergreen SPA can now use CSS Modules plus native CSS features for
  component-tier styling, themes, responsive components, and admin layouts.
- Modern CSS makes a "plain CSS first" strategy defensible for a serious app.
- AI-assisted coding reduces one Tailwind advantage: remembering utility names
  and composing long class strings manually.

What is not proven:

- "Everyone" is not supported by primary sources.
- Vercel has Geist, but also officially publishes Tailwind templates.
- Solid supports CSS Modules, but its docs also list Tailwind and UnoCSS.
- No primary-source 2026 Linear/Stripe post was found that validates a broad
  no-Tailwind production trend.

Recommended phrasing for strategy docs:

- Say: "We are choosing modern native CSS with CSS Modules, cascade layers, and
  custom-property tokens because the browser platform now covers our needs and
  keeps output readable."
- Do not say: "Tailwind is dead" or "everyone uses vanilla CSS now."
- The defensible posture is technical, not sentiment-driven.

## Citations

[C1] caniuse: CSS Cascade Layers, CR, global 95.29%, browser support. https://caniuse.com/css-cascade-layers
[C2] W3C: CSS Cascading and Inheritance Level 5. https://www.w3.org/TR/css-cascade-5/
[C3] caniuse: CSS Nesting, WD, global 91.83%, browser support. https://caniuse.com/css-nesting
[C4] W3C: CSS Nesting Module Level 1, Working Draft 2026-01-22. https://www.w3.org/TR/css-nesting-1/
[C5] caniuse: `:has()` CSS relational pseudo-class, WD, global 94.31%. https://caniuse.com/css-has
[C6] W3C: Selectors Level 4, Working Draft 2026-01-22. https://www.w3.org/TR/selectors-4/
[C7] caniuse: CSS Container Queries (Size), WD, global 94.05%. https://caniuse.com/css-container-queries
[C8] caniuse: CSS Container Style Queries, partial support. https://caniuse.com/css-container-queries-style
[C9] W3C: CSS Containment Module Level 3, container queries and units. https://www.w3.org/TR/css-contain-3/
[C10] caniuse: Scoped Styles `@scope`, WD, global 91.08%. https://caniuse.com/css-cascade-scope
[C11] W3C: CSS Cascading and Inheritance Level 6, `@scope`, Working Draft. https://www.w3.org/TR/css-cascade-6/
[C12] caniuse: CSS Variables / Custom Properties, CR, global 97.21%. https://caniuse.com/css-variables
[C13] W3C: CSS Custom Properties for Cascading Variables Level 1. https://www.w3.org/TR/css-variables-1/
[C14] caniuse: `color-mix()`, global 92.8%. https://caniuse.com/wf-color-mix
[C15] caniuse: `light-dark()`, global 90.02%. https://caniuse.com/wf-light-dark
[C16] W3C: CSS Color Module Level 5, `color-mix()` and `light-dark()`, WD. https://www.w3.org/TR/css-color-5/
[C17] caniuse: Registered custom properties / `@property`, global 94.73%. https://caniuse.com/wf-registered-custom-properties
[C18] W3C: CSS Properties and Values API Level 1. https://www.w3.org/TR/css-properties-values-api-1/
[C19] caniuse: CSS Anchor Positioning, WD, global 85.14%. https://caniuse.com/css-anchor-positioning
[C20] W3C: CSS Anchor Positioning Level 1. https://www.w3.org/TR/css-anchor-position-1/
[C21] caniuse: View Transitions API, single-document, WD, global 90.94%. https://caniuse.com/view-transitions
[C22] W3C: CSS View Transitions Module Level 1. https://www.w3.org/TR/css-view-transitions-1/
[C23] caniuse: CSS Subgrid, CR, global 92.48%. https://caniuse.com/css-subgrid
[C24] W3C: CSS Grid Layout Module Level 2. https://www.w3.org/TR/css-grid-2/
[C25] caniuse: OKLCH color model, global 93.29%. https://caniuse.com/mdn-css_types_color_oklch
[C26] caniuse: LCH/Lab color values, CR, global 93.32%. https://caniuse.com/css-lch-lab
[C27] caniuse: CSS `color()` function / Display P3, CR, global 93.27%. https://caniuse.com/css-color-function
[C28] W3C: CSS Color Module Level 4. https://www.w3.org/TR/css-color-4/
[C29] W3C: CSS Snapshot 2026, Group Note 2026-03-26. https://www.w3.org/TR/css-2026/
[C30] Vite docs: CSS, HMR, CSS Modules, named imports, `css.modules`. https://vite.dev/guide/features.html#css-modules
[C31] Rsbuild docs: CSS Modules support and generated declarations. https://rsbuild.dev/guide/styling/css-modules
[C32] Rsbuild config docs: `output.cssModules`. https://rsbuild.rs/config/output/css-modules
[C33] Bun docs: CSS bundler, CSS Modules, modern CSS lowering. https://bun.com/docs/bundler/css
[C34] CSS Modules docs: local scope and JS import mapping. https://github.com/css-modules/css-modules
[C35] CSS Modules docs: composition and undefined cross-file conflict order. https://github.com/css-modules/css-modules/blob/master/docs/composition.md
[C36] vanilla-extract docs: zero-runtime stylesheets in TypeScript and themes. https://vanilla-extract.style/
[C37] Style Dictionary docs: design tokens and transform system. https://styledictionary.com/info/tokens/
[C38] Style Dictionary docs: CSS variable output formats. https://styledictionary.com/reference/hooks/formats/
[C39] Open Props site. https://open-props.style/
[C40] Pico CSS site/docs. https://picocss.com/
[C41] Open Props UI third-party listing and changelog. https://www.cssscript.com/open-props-ui/
[C42] Vercel Geist Design System. https://vercel.com/geist/introduction
[C43] Vercel Tailwind templates directory. https://vercel.com/templates/tailwind
[C44] Solid docs: CSS Modules. https://docs.solidjs.com/guides/styling-components/css-modules
[C45] SolidStart docs: CSS and styling, Vite CSS Modules. https://docs.solidjs.com/solid-start/building-your-application/css-and-styling
[C46] Solid docs: styling options include CSS Modules, preprocessors, CSS-in-JS, Tailwind, and UnoCSS. https://docs.solidjs.com/guides/styling-your-components
[C47] npm registry observations from this run: `style-dictionary` 5.4.0; `open-props` 1.7.23; `@picocss/pico` 2.1.1; `sakura.css` 1.5.1; `tachyons` 4.12.0; `@vanilla-extract/css` 1.20.1; `vite` 8.0.10; `solid-js` latest 1.9.12 and `next` 2.0.0-beta.8.
