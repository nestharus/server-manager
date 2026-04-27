# WebAwesome + FontAwesome findings

## Headline verdict

Path C is the default recommendation: reject WebAwesome as the primary component layer for this locked stack, keep Ark UI Solid/headless primitives as primary, hand-roll the small gaps with vanilla CSS, and use FontAwesome through SVG Core or a Kit package. WebAwesome is active, well-funded by the Font Awesome team, and technically compatible with Solid/Vite, but it is a styled Lit/Web Components design system, not a headless Solid layer; it does not provide the requested Meter or Toolbar components; and its strongest Pro-only value, Combobox/autocomplete plus premium themes/assets, would make the app accept WebAwesome's styling and account/license surface. A narrow conditional exception is reasonable for `<wa-icon>` and possibly breadcrumbs if a wrapper isolates Web Component binding and CSS token bridging.

## WebAwesome — current state

- Name: WebAwesome.
- Official site: https://webawesome.com/.
- Docs URL: https://webawesome.com/docs/.
- Component docs: https://webawesome.com/docs/components/.
- GitHub repo: https://github.com/shoelace-style/webawesome.
- npm package: `@awesome.me/webawesome`, version `3.5.0`, modified 2026-04-03, MIT license.
- Official install path supports CDN and npm.
- CDN example uses `ka-f.webawesome.com/webawesome@3.5.0`.
- npm install for free package is `npm install @awesome.me/webawesome`.
- Pro install path is `npm install @awesome.me/webawesome-pro`.
- WebAwesome calls itself a framework-agnostic web component library.
- WebAwesome docs position it as a large open-source component library plus themes, utilities, patterns, and Pro assets.

### Relationship to Shoelace

- Shoelace and WebAwesome are not two equally active sibling projects in 2026 Q2.
- Shoelace is the predecessor project.
- The Shoelace GitHub repository is archived and read-only as of 2026-03-24.
- Shoelace's README says active development stopped on Shoelace and directs issues, PRs, and features to WebAwesome.
- The Shoelace README describes WebAwesome as the successor project.
- Shoelace remains MIT-licensed and available as `@shoelace-style/shoelace`.
- `@shoelace-style/shoelace` latest observed npm version: `2.20.1`, published 2025-03-11.
- WebAwesome continues under the `shoelace-style` GitHub organization.
- The migration implication is clear: new work should evaluate WebAwesome, not start new design-system work on Shoelace.

### Architecture and Web Components shape

- WebAwesome components are Custom Elements / Web Components built with Lit and Shadow DOM.
- Components expose attributes, properties, custom events, methods, slots, CSS custom properties, CSS parts, and custom states.
- WebAwesome custom events are prefixed with `wa-`.
- Lit batches updates; docs tell callers to await `updateComplete` when code needs the rendered/reflected result.
- Docs warn that custom elements should not be written as self-closing tags.
- Docs warn WebAwesome elements are not always one-to-one replacements for native controls.
- Example: `wa-button` defaults to `type="button"` rather than native submit behavior.
- Readiness can be awaited with `customElements.whenDefined(...)`.
- WebAwesome also exports `allDefined()` for waiting until registered components are upgraded.
- The package includes editor metadata: `vscode.html-custom-data.json` and `web-types.json`.
- The docs do not present a Solid-specific wrapper package as the primary integration path.
- The expected integration is direct custom-element use from the framework.

### Licensing and account model

- WebAwesome Free is open source under MIT as `@awesome.me/webawesome`.
- WebAwesome Pro is distributed separately as `@awesome.me/webawesome-pro`.
- The Pro license covers Pro Asset Packs and Online Services.
- Pro Asset Packs include Pro-only patterns, themes, materials, and premium component variants.
- The Pro license is seat based.
- Customers appoint Creators up to the purchased seat count.
- Creators may integrate Pro assets into permitted end-user projects, but Pro assets cannot be redistributed as standalone assets to non-Creators.
- Pro credentials and license keys must remain confidential.
- Some plans may limit downloads, perpetual rights, or use after subscription expiration.
- Font Awesome Pro / Pro+ account value is also surfaced inside WebAwesome through icon kits.
- WebAwesome `<wa-icon>` ships with free Font Awesome icons by default.
- A Font Awesome Pro kit code unlocks premium families and Pro+ packs for `<wa-icon>`.
- Pro gates found in component docs include `wa-combobox`, which is labeled Experimental and Pro.

### Themability and vanilla-CSS lock compatibility

- WebAwesome is not headless.
- WebAwesome ships a styled component system.
- It can be heavily customized with CSS.
- It uses CSS custom properties as design tokens.
- WebAwesome tokens are prefixed with `--wa-`.
- Theme token source of truth is `src/styles/themes/default.css`.
- Prebuilt themes are available through WebAwesome account/project settings.
- Docs say any theme can be overridden with plain CSS.
- No preprocessor is required for theme overrides.
- Shadow DOM means ordinary CSS Modules selectors will not reach internal component markup.
- Internal customization uses CSS custom properties, CSS parts, and custom states.
- CSS parts are documented as a stable styling API until a major version.
- Component-level custom properties may not use the `--wa-` prefix.
- Examples include component-scoped values such as `--size`, `--background-color`, and `--border-style`.
- WebAwesome also ships optional native element styles.
- `webawesome.css` loads all styles.
- `default.css` is the required default theme.
- `native.css` is optional.
- `utilities.css` is optional.
- Native styles can style ordinary HTML elements to match the WebAwesome theme.
- Native styles include form controls, native buttons, tables, native `<dialog>`, and native `<progress>`.
- Native styles can be omitted if the app wants its own vanilla CSS.
- Native styles can also be opted out locally with CSS reset/revert rules.
- The practical fit is conditional: custom-property tokens align with the locked stack, but Shadow DOM/parts and WebAwesome's default visual grammar create a separate styling layer.

### Component coverage matrix

| Need | WebAwesome coverage | Evidence / notes |
|---|---:|---|
| Dialog / Modal | Yes | `Dialog` component is listed under Organization. Native `<dialog>` is also covered by optional native styles. |
| Popover | Yes | `Popover` appears under Utilities; `Popup` is also listed. |
| Tooltip | Yes | `Tooltip` appears under Feedback & Status. |
| Menu, context, dropdown | Partial | `Dropdown` and `Dropdown Item` exist. A named `Menu` or `Context Menu` component is not listed. |
| Select, single | Yes | `Select` exists and supports standard form participation. |
| Select, multi | Yes | `wa-select` supports `multiple`; docs say framework users can bind directly to the `value` property for array values. |
| Combobox / Autocomplete | Conditional | `Combobox` exists, but it is marked Experimental and Pro, introduced since 3.1. |
| Tabs | Yes | `Tab`, `Tab Group`, and `Tab Panel` are listed. |
| Accordion / Disclosure | Partial | `Details` exists and covers disclosure behavior. A named Accordion component is not listed. |
| Toggle / Switch | Yes | `Switch` exists. |
| Checkbox | Yes | `Checkbox` exists. |
| Radio | Yes | `Radio` and `Radio Group` exist. |
| Slider | Yes | `Slider` exists. |
| Progress | Yes | `Progress Bar` and `Progress Ring` exist. Native `<progress>` styling also exists. |
| Meter | No | No `Meter` component is listed. Native styles mention `<progress>`, not `<meter>`. |
| Toast / Notification | Yes | `Toast` and `Toast Item` exist. |
| Toolbar | No | No `Toolbar` component is listed. |
| Breadcrumbs | Yes | `Breadcrumb` and `Breadcrumb Item` are listed. |
| Pagination | No | No `Pagination` component is listed. |
| Form field | Partial | Form controls include built-in `label` and `hint` APIs. A separate generic Field component is not listed. |
| Date picker | Partial | `wa-input` supports `type="date"`. A dedicated date-picker/calendar component is not listed. |
| Number field | Yes | `Number Input` is listed, and `wa-input` supports number-related APIs. |
| Color picker | Yes | `Color Picker` is listed. |
| Tree | Yes | `Tree` and `Tree Item` are listed. |
| TreeGrid | No | No `TreeGrid` component is listed. |
| Data table | No | No data table component is listed. Native table styling exists only as CSS. |
| Drawer | Yes | `Drawer` is listed. |
| Split panel | Yes | `Split Panel` is listed. |

### Solid 2 binding details

- Solid can render custom elements directly.
- Custom element attributes can be passed in JSX as attributes.
- Solid provides `prop:*` to force property assignment instead of attribute assignment.
- `prop:*` is needed when the target property must receive non-string values.
- Solid docs specifically call out custom elements for `prop:*`.
- Solid provides `on:*` for custom events.
- Solid TypeScript support allows augmentation for custom events, explicit properties, explicit attributes, and boolean attributes.
- WebAwesome `wa-select multiple` uses an array value; Solid should bind that with `prop:value`.
- WebAwesome function-valued APIs such as `getTag`, `filter`, or validators also require property assignment, not string attributes.
- WebAwesome custom events such as `wa-clear`, `wa-invalid`, and `wa-create` should be handled with Solid custom event syntax.
- Standard DOM events such as `input`, `change`, `focus`, and `blur` can be handled normally.
- Solid event handlers receive DOM event objects; value extraction should read from the custom element instance.
- WebAwesome has editor metadata, but there is no evidence from official docs of Solid-specific generated JSX intrinsic typings.
- A practical Solid integration should create local wrapper components for nontrivial WebAwesome controls.
- Wrappers should own `prop:*`, `on:*`, value typing, and CSS part/custom-property usage.
- Without wrappers, call sites will repeat Web Component binding details and tsgo type augmentations.

### Form integration

- WebAwesome form controls document standard HTML form participation.
- `wa-input` works with standard `<form>` elements.
- `wa-select` works with standard `<form>` elements.
- `wa-combobox` works with standard `<form>` elements.
- `wa-input` exposes `name`, `form`, `required`, `disabled`, `readonly`, `value`, `defaultValue`, and validation APIs.
- `wa-input` supports standard events including `input`, `change`, `focus`, and `blur`.
- `wa-input` also emits `wa-clear` and `wa-invalid`.
- `wa-input` exposes `setCustomValidity`, `resetValidity`, `checkValidity`, and related methods.
- `wa-select` supports single and multiple values; the multiple value is a string array.
- `wa-select` supports lazy-loaded options.
- `wa-select` emits standard `input` and `change` events plus WebAwesome-specific events.
- TanStack Form Solid's documented pattern is field state plus handlers.
- TanStack Form Solid examples bind `value={field().state.value}`, call `field().handleBlur`, and call `field().handleChange(...)`.
- TanStack Form docs state that `onInput` must be implemented so TanStack Form receives changes.
- For `wa-input`, a wrapper can map `value` to `field().state.value` and `input` to `field().handleChange(el.value)`.
- For `wa-select multiple`, a wrapper should map `prop:value` to an array and `input/change` to `field().handleChange(el.value)`.
- For `wa-combobox`, a wrapper must decide whether TanStack Form owns `value`, `inputValue`, or both.
- Native form participation does not remove the need to wire TanStack Form field state.
- WebAwesome validation APIs and TanStack Form validators can overlap.
- The clean integration pattern is to make TanStack Form the source of truth and use WebAwesome validity only for presentation or native form compatibility.

### Accessibility

- WebAwesome's GitHub README says the library is built with accessibility in mind.
- Component docs expose `label` and `hint` APIs for form controls.
- `<wa-icon>` treats icons without `label` as presentational and uses `label` for non-decorative icons.
- `<wa-icon>` animations respect `prefers-reduced-motion`.
- `wa-combobox` documentation says it follows the ARIA Authoring Practices Guide combobox pattern.
- `wa-combobox` uses live region announcements for filtering changes.
- Color token docs include WCAG 2.1 contrast guidance for selecting token tint deltas.
- The docs inspected do not provide a single global WAI-ARIA conformance matrix.
- The docs inspected do not provide a VPAT.
- The docs inspected do not provide a public screen-reader/browser test matrix.
- Accessibility posture is stronger than hand-rolled controls by default, but not enough evidence was found to treat WebAwesome as a formal compliance artifact.

### Maintenance and production users

- WebAwesome GitHub and npm latest observed release: `v3.5.0` on 2026-04-03.
- GitHub latest visible commit observed during research: 2026-04-23.
- WebAwesome had releases within the last 90 days: 2026-02-04, 2026-03-04, 2026-03-25, and 2026-04-03.
- GitHub repo stats observed: about 1k stars, 139 forks, 49 contributors, and 5,174 commits.
- The project is stewarded by the Font Awesome team.
- Shoelace is archived, which concentrates future maintenance on WebAwesome.
- The WebAwesome docs inspected do not cite named production users.
- The strongest maintenance signal is active releases/commits plus Font Awesome stewardship, not a published customer list.

### TypeScript / build / bundle

- WebAwesome supports CDN loading through a loader and npm bundler loading.
- Docs recommend per-component imports for bundlers.
- Example import path: `@awesome.me/webawesome/dist/components/button/button.js`.
- Docs say cherry-picking components keeps bundles smaller.
- `dist-cdn` bundles everything together for CDN use.
- `dist` keeps dependencies separate so bundlers such as Vite can optimize and share dependencies.
- For the locked stack, Vite should use `dist`, not `dist-cdn`.
- CSS can be loaded globally from `dist/styles/webawesome.css` or split into theme, native, and utility imports.
- WebAwesome assets may need a base path.
- Base path can be provided with `data-webawesome` on the loader script or `setBasePath(...)`.
- WebAwesome provides metadata useful for editor completion.
- The docs do not establish generated Solid JSX typings as a first-class integration.
- TypeScript in a Solid project will likely need local intrinsic-element and custom-event declarations for strict typing.
- tsgo should be compatible as long as the project uses modern module resolution and Vite-style ESM.
- The project should avoid importing all components from a root loader if bundle size matters.

### Pro gates

- Pro package: `@awesome.me/webawesome-pro`; Pro license covers Pro Asset Packs and Online Services.
- Pro Asset Packs include premium themes, premium component variants, and patterns.
- `wa-combobox` is Pro and Experimental.
- Pro users can set a Font Awesome kit code for `<wa-icon>`.
- Pro icon families include premium Font Awesome families.
- Pro+ packs require an eligible Pro+ plan.
- Account/project settings appear in docs as the place to manage themes and kit-related settings.
- Credential and license-key handling must be treated as secret build configuration.

## FontAwesome — current state

### Pro vs free

- Current FontAwesome SVG core npm version observed on 2026-04-27: `7.2.0`.
- `@fortawesome/fontawesome-svg-core` latest observed publish time: 2026-02-10.
- Free SVG packages include free solid, regular, and brands packages.
- Free package examples include `@fortawesome/free-solid-svg-icons`.
- Pro SVG packages include Pro Classic, Sharp, Duotone, and Sharp Duotone variants.
- Pro+ icons are available through Kit Packages, not ordinary SVG icon packages.
- Font Awesome docs recommend Kit Packages for new projects.
- Kit Packages can include Pro+ icons when the account plan allows them.
- Kit Packages can include uploaded custom icons.
- Kit Packages can be subset by icon for smaller output.
- All-inclusive packages exist but include much more than most apps need.
- SVG icon packages can still be used style-by-style.
- Pro npm package access requires an active Pro plan and a package token.

### Solid integration patterns

- FontAwesome has official React package docs, but no official `@fortawesome/solid-*` package was found in the official docs inspected.
- Solid integration therefore has three realistic patterns.
- Pattern 1: use `@fortawesome/fontawesome-svg-core` directly and render SVG in a local Solid component.
- Pattern 2: use a Font Awesome Kit package and import only individual icons from the generated package exports.
- Pattern 3: use WebAwesome `<wa-icon>` as the icon rendering component.
- Third-party Solid wrappers exist, but they are not the official Font Awesome integration path.
- SVG Core direct integration best matches the locked stack because it avoids Web Components for icons and keeps icon styling inside the app's CSS Modules/token layer.
- Kit Package individual-icon imports preserve tree-shaking.
- Importing whole styles or `all` arrays makes tree-shaking harder.
- Font Awesome docs say individual icon imports are tree-shakable.
- Font Awesome docs say Kit Package icon subsetting can replace some need for bundler tree-shaking.
- For Pro+ or custom icons, Kit Packages are the cleanest official path.

### WebAwesome icon component integration

- WebAwesome `<wa-icon>` is stable since 2.0.
- `<wa-icon>` is bundled with over 2,000 free Font Awesome icons.
- The default WebAwesome icon library includes free Classic and Brands icons.
- `<wa-icon>` supports `family`, `variant`, `library`, `name`, `src`, `label`, animation, rotation, flip, and duotone options.
- `<wa-icon>` inherits text color through `currentColor`.
- Duotone icons can be customized with CSS custom properties for primary and secondary color/opacity.
- Pro and Pro+ icons can be unlocked by passing a Font Awesome kit code to WebAwesome.
- Kit code can be set with `data-fa-kit-code` or `setKitCode(...)` from `webawesome.loader.js`.
- Custom icon libraries can be registered with WebAwesome's `registerIconLibrary(...)`.
- Using `<wa-icon>` creates a Web Component dependency even if the rest of the app stays headless.
- If `<wa-icon>` is used, a local Solid wrapper should own kit code policy and a typed icon-name surface.

### Custom kit tokens

- Font Awesome npm registry for Pro packages is `https://npm.fontawesome.com/`, using `@fortawesome` and, for Kit Packages, `@awesome.me` scopes.
- Font Awesome docs recommend a `FONTAWESOME_PACKAGE_TOKEN` environment variable in `.npmrc`.
- Pro Package Tokens come from the Font Awesome account.
- Kit Packages install as `@awesome.me/kit-KIT_CODE`.
- Kit Packages require enabling package download in Kit settings.
- Hosted Kits can be domain-limited and can count pageviews.
- Public Font Awesome CDN is only documented for older v5-and-below packages; current v7 use is through Kits/packages.
- Uploaded custom icons require a Pro Plan with perpetual license.
- Uploaded custom icons are tied to a specific Kit.
- Uploaded custom icons use kit prefixes such as `fak`; custom duotone kit icons use `fakd`.
- Downloaded Kit packages include uploaded custom icons when included in that Kit.
- TypeScript module resolution for Kit Packages should be `nodenext` or `bundler`; older `node` and `classic` module resolution are not supported by the Kit Package API docs.

## Stack-fit decision drivers

### Vanilla-CSS compatibility analysis

- WebAwesome is compatible with vanilla CSS technically.
- It uses CSS custom properties, CSS parts, and native CSS selectors without Tailwind, CSS-in-JS, or runtime styling.
- It aligns with custom-property tokens in the locked stack.
- It conflicts with the headless preference because it ships styled components.
- CSS Modules cannot style Shadow DOM internals except through documented styling hooks.
- Cascade layers can order WebAwesome CSS relative to app CSS, but they do not dissolve Shadow DOM boundaries.
- The app can bridge token systems by assigning `--wa-*` tokens from the app's own design tokens.
- This creates a second token namespace to maintain.
- The optional `native.css` can make native controls visually match WebAwesome.
- Loading `native.css` would make WebAwesome styling bleed into native elements.
- Not loading `native.css` avoids global bleed but leaves WebAwesome components visually distinct unless tokens and parts are tuned.
- WebAwesome's customization story buys a styled accessible component set, not a headless primitive layer.
- For a product UI that wants dense, custom, operational surfaces, the default WebAwesome look is likely an island until deliberately rethemed.
- Retheming is possible, but then the team carries a Web Component theming surface plus the app's own CSS Modules surface.

### Headless lock relaxation

- Relaxing headless for WebAwesome could be justified if component coverage removed major implementation risk.
- The coverage does not remove the known gaps.
- WebAwesome lacks Meter, Toolbar, Data Table, and Pagination.
- WebAwesome Combobox is Pro and Experimental.
- TanStack Table remains needed for data grids/tables.
- Ark UI or equivalent primitives remain useful for headless behavior and app-owned styling.
- Therefore the FontAwesome/WebAwesome account value does not outweigh the headless preference as a primary-layer decision.

### Mixing with Ark UI Solid

- Mixing WebAwesome and Ark is technically feasible because WebAwesome is framework-agnostic custom elements.
- The main risk is owning overlapping behavior systems, not rendering compatibility.
- Both ecosystems can provide dialogs, popovers, select-like controls, tabs, tooltips, and focusable overlays.
- Mixing modal/dialog systems can create focus-management, inert, scroll-lock, and escape-key ownership ambiguity.
- Mixing tooltip/popover systems can create z-index and portal/layering inconsistencies.
- If WebAwesome is used with Ark, it should be limited to non-overlapping components or wrapped behind one overlay policy.
- Safe narrow candidates: icons, breadcrumbs, maybe passive display components.
- Riskier candidates: dialog, drawer, popover, dropdown, select, combobox, tooltip.
- The app should not mount Ark and WebAwesome modals as peer systems without a single overlay/layering policy.

### Mixing with TanStack Form on Solid

- TanStack Form is framework state and validation; WebAwesome controls are form-associated custom elements with their own validity APIs.
- Integration is straightforward for scalar inputs when wrapped.
- `wa-input` can map field state to `value`, `input` to `field().handleChange(...)`, and blur to `field().handleBlur`.
- Multi-select requires property binding because the value is an array.
- `wa-select multiple` should use `prop:value`, not an HTML string attribute.
- Combobox requires extra decisions because it separates typed input and selected value.
- Wrapper components should normalize event detail/value reads.
- Wrapper components should display TanStack field errors through `hint`, custom parts, or adjacent app-owned error text.
- TanStack Form should remain the source of truth to avoid duplicate validation states.

### Long-term Web Components posture

- Web Components are a viable long-term distribution format and WebAwesome can outlive Solid-specific component APIs.
- The tradeoff is that Web Components are less idiomatic inside Solid than Solid primitives and property/event typing requires extra local work.
- SSR and hydration constraints can be sharper because custom elements upgrade after definition.
- `prop:*` has no SSR output in Solid, so property-only state may need careful client initialization.
- Shadow DOM limits direct styling and test selectors.
- Framework-agnostic longevity is valuable for a design system shared across multiple frontend stacks.
- In this project, the stack is already locked to Solid 2 and TanStack.
- That reduces the value of framework-agnostic distribution.
- The architectural complication is justified only if WebAwesome becomes the accepted visual design system.

## Recommendation

### Path A: Replace Ark UI Solid with WebAwesome as primary component layer

- Decision: No.
- Conditions for reconsideration: the project abandons the headless requirement and explicitly adopts WebAwesome as the app design system.
- Conditions for reconsideration: the team accepts Shadow DOM styling hooks as the main component customization surface.
- Conditions for reconsideration: the team accepts Pro licensing for Combobox/autocomplete if that component is needed.
- Conditions for reconsideration: the team accepts hand-rolled Meter, Toolbar, Pagination, and Data Table gaps anyway.
- Evidence against: WebAwesome is styled, not headless.
- Evidence against: WebAwesome lacks Meter.
- Evidence against: WebAwesome lacks Toolbar.
- Evidence against: WebAwesome lacks Data Table.
- Evidence against: WebAwesome lacks Pagination.
- Evidence against: primary use would require wrapper/typing policy for Solid.

### Path B: Keep Ark UI Solid primary; use WebAwesome only for Meter, Toolbar, Breadcrumbs, plus FA icons

- Decision: Conditional, but not as stated.
- WebAwesome can provide Breadcrumbs and Font Awesome icons through `<wa-icon>`.
- WebAwesome cannot provide Meter or Toolbar.
- Therefore it cannot fill the three stated gap components.
- Conditional acceptable form: use WebAwesome only for `<wa-icon>` and `wa-breadcrumb`, with local Solid wrappers and token bridging.
- Condition: no WebAwesome overlays, selects, comboboxes, dialogs, drawers, or tooltips unless the overlay policy is redesigned.
- Condition: no global `native.css` unless the team explicitly wants WebAwesome styling on native elements.
- Condition: all WebAwesome usage is isolated under an adapter directory.

### Path C: Reject WebAwesome on stack-fit grounds; use Ark plus hand-rolled gaps, use FontAwesome SVG Core

- Decision: Yes.
- This best preserves Solid-native composition.
- This best preserves vanilla CSS Modules and cascade-layer ownership.
- This avoids Shadow DOM styling boundaries for primary UI.
- This avoids duplicate overlay/focus systems.
- This avoids WebAwesome Pro gates for core form primitives.
- This still uses the user's FontAwesome account value.
- For Free/Pro non-Pro+ icons, use `@fortawesome/fontawesome-svg-core` plus individual icon packages.
- For Pro+ or custom icons, use a Kit Package and individual icon imports.
- Build a small local Solid `<Icon>` wrapper.
- Build Meter with native `<meter>` or a div/ARIA meter pattern and app tokens.
- Build Toolbar as semantic app markup using buttons, roving focus if needed, and Ark primitives where appropriate.
- Build Breadcrumbs either by hand or with Ark/app markup; WebAwesome breadcrumb is optional but not necessary.

### Path D: Replace everything with WebAwesome + FA, accepting WebAwesome styling as the design system

- Decision: No for the locked stack.
- This is coherent only if the product wants WebAwesome's visual system.
- This is coherent only if the team is comfortable with Pro licensing and WebAwesome account workflows.
- This is coherent only if missing components are accepted as custom app work.
- This path undercuts the locked headless/Solid-first component strategy.
- It may be viable for a separate quick admin console or prototype, not the primary app stack.

### Side-by-side: WA-as-primary vs Ark-as-primary in this stack

| Driver | WebAwesome as primary | Ark as primary |
|---|---|---|
| Rendering model | Lit custom elements with Shadow DOM | Solid-native primitives |
| Styling model | Built-in styled components, `--wa-*`, parts, states | App-owned CSS Modules, cascade layers, app tokens |
| Headless fit | Weak | Strong |
| Vite fit | Good | Good |
| Solid 2 typing | Requires custom-element/event augmentation | Native Solid typing |
| TanStack Form fit | Requires wrappers for custom element values/events | Direct Solid control binding |
| Overlay policy | WebAwesome overlay components unless avoided | One Solid overlay/focus system |
| Component gaps | Missing Meter, Toolbar, Data Table, Pagination | Gaps are expected and app-owned |
| Icons | Excellent through `<wa-icon>` and kit code | Excellent through SVG Core/Kit wrapper |
| Pro dependency | Combobox and premium assets can be Pro-gated | Only FontAwesome icons need Pro token if used |
| Long-term portability | Strong across frameworks | Strong inside Solid stack, less portable |
| Visual consistency risk | Medium unless fully adopted/rethemed | Low because app owns styles |

## Risks

### Path A risks

- High risk of styled-component drift from the app's vanilla CSS design language.
- Medium risk of Solid typing friction around custom elements and custom events.
- Medium risk of duplicate state/validity handling with TanStack Form.
- Medium risk from Pro-gated Combobox if autocomplete becomes core.
- Medium risk from missing components forcing custom work despite replacement.
- Medium risk from Shadow DOM limiting fine-grained CSS Modules control.

### Path B risks

- Medium risk if the scope expands from icons/breadcrumbs into overlays or form controls.
- Medium risk of visual inconsistency if WebAwesome components are not rethemed.
- Low risk for `<wa-icon>` if wrapped and treated as an implementation detail.
- Low-to-medium risk for Breadcrumbs if the app accepts Web Component styling hooks.
- High risk if the team believes WebAwesome covers Meter and Toolbar; the docs do not support that.

### Path C risks

- Low risk of losing WebAwesome prebuilt component speed.
- Low-to-medium risk of more app-owned accessibility work for Meter/Toolbar/Breadcrumbs.
- Low risk around FontAwesome Pro token handling; it is a standard npm registry or Kit workflow.
- Low risk of bundle bloat if the implementation uses individual icon imports.
- Medium risk if custom icon uploads or Pro+ icons are needed and Kit Package setup is delayed.

### Path D risks

- High risk of violating the locked headless/component strategy.
- High risk of visual system lock-in to WebAwesome.
- Medium risk from account/license gates.
- Medium risk from missing enterprise app primitives such as Data Table and Pagination.
- Medium risk from having to teach the codebase Web Component wrappers, Shadow DOM parts, and WebAwesome token conventions everywhere.

## Citations

- WebAwesome official site: https://webawesome.com/
- WebAwesome docs and installation: https://webawesome.com/docs/
- WebAwesome usage and custom element model: https://webawesome.com/docs/usage
- WebAwesome component index: https://webawesome.com/docs/components/
- WebAwesome customization docs: https://webawesome.com/docs/customizing
- WebAwesome color tokens: https://webawesome.com/docs/tokens/color/
- WebAwesome native styles: https://webawesome.com/docs/utilities/native
- WebAwesome icon component: https://webawesome.com/docs/components/icon/
- WebAwesome input component: https://webawesome.com/docs/components/input/
- WebAwesome select component: https://webawesome.com/docs/components/select/
- WebAwesome combobox component: https://webawesome.com/docs/components/combobox/
- WebAwesome Pro license: https://webawesome.com/license/pro
- WebAwesome GitHub repo: https://github.com/shoelace-style/webawesome
- WebAwesome npm package: https://www.npmjs.com/package/@awesome.me/webawesome
- Shoelace GitHub repo and sunset notice: https://github.com/shoelace-style/shoelace
- Shoelace npm package: https://www.npmjs.com/package/@shoelace-style/shoelace
- Solid `prop:*` docs: https://docs.solidjs.com/reference/jsx-attributes/prop
- Solid TypeScript custom attributes/events docs: https://docs.solidjs.com/configuration/typescript#forcing-properties-and-custom-attributes
- TanStack Form Solid basic concepts: https://raw.githubusercontent.com/TanStack/form/main/docs/framework/solid/guides/basic-concepts.md
- TanStack Form Solid validation guide: https://raw.githubusercontent.com/TanStack/form/main/docs/framework/solid/guides/validation.md
- TanStack Form Solid simple example: https://raw.githubusercontent.com/TanStack/form/main/examples/solid/simple/src/index.tsx
- TanStack Solid Form npm package: https://www.npmjs.com/package/@tanstack/solid-form
- FontAwesome package setup docs: https://docs.fontawesome.com/web/setup/packages
- FontAwesome Kit Package API: https://docs.fontawesome.com/web/dig-deeper/kit-package-api
- FontAwesome Kit setup docs: https://docs.fontawesome.com/web/setup/use-kit
- FontAwesome custom icon upload docs: https://docs.fontawesome.com/web/add-icons/upload-icons
- FontAwesome React integration docs, used only to verify official component patterns and tree-shaking guidance: https://docs.fontawesome.com/web/use-with/react/add-icons
- FontAwesome SVG Core npm package: https://www.npmjs.com/package/@fortawesome/fontawesome-svg-core
- FontAwesome free solid icons npm package: https://www.npmjs.com/package/@fortawesome/free-solid-svg-icons
