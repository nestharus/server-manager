# Solid 2 component primitives findings

## Summary verdict

Ark UI Solid is the modern best-practice direction for a headless Solid component-primitives stack in 2026 Q2: it has the broadest coverage, the most active release cadence, visible production/showcase users, current Solid ecosystem listing, and explicit maintainer intent to support Solid 2. The important caveat is timing: as of 2026-04-27, Ark UI has not yet published explicit Solid 2 support; its maintainer says Solid 2 support is intended for the next major release. Kobalte remains the established Solid-native library with much higher npm downloads, but it is currently less active and has a Solid 1-only peer range. Corvu is Solid-native and cleanly headless, but its component surface and maintenance signal are too small for the requested component matrix. Solid Aria is explicitly not production-ready.

## Candidates

### Kobalte

- URL: https://kobalte.dev/
- GitHub repo: https://github.com/kobaltedev/kobalte
- npm package: `@kobalte/core`
- Current latest version: `0.13.11`
- Release date: 2025-07-26
- Repo status: 1,771 GitHub stars, 105 forks, pushed 2026-03-19, 1 commit observed since 2026-01-27 via GitHub commits API.
- npm downloads: 710,146 downloads in the last month ending 2026-04-26; 4,195,954 downloads from 2025-04-27 through 2026-04-27.
- Solid 2 compat: not declared. `@kobalte/core@0.13.11` publishes `peerDependencies: { "solid-js": "^1.8.15" }`, which excludes `solid-js@2.0.0-beta.8` under normal npm peer resolution.
- Solid 2 migration path: no explicit Solid 2 migration path or support timeline found in repo/docs during this pass.
- Headless / unstyled: yes. Docs state Kobalte ships zero styles and lets vanilla CSS, Tailwind, CSS-in-JS, etc. own appearance.

| Component | Present |
|---|---:|
| Dialog / Modal | ✓ |
| Popover | ✓ |
| Tooltip | ✓ |
| Menu (context, dropdown) | ✓ |
| Select (single + multi) | ✓ |
| Combobox / Autocomplete | ✓ |
| Listbox | ✓ |
| Tabs | ✓ |
| Accordion | ✓ |
| Disclosure | ✓ |
| Toggle / Switch | ✓ |
| Checkbox + Radio | ✓ |
| Slider | ✓ |
| Progress + Meter | ✓ |
| Toast / Notification | ✓ |
| Toolbar | ✗ |
| Breadcrumbs | ✓ |
| Pagination | ✓ |
| Form field (label, hint, error region, ARIA wiring) | ✓ |
| Date picker | ✗ |
| Number field | ✓ |
| Color picker | ✓ |

- Coverage evidence: npm package contents include `accordion`, `breadcrumbs`, `checkbox`, `collapsible`, `combobox`, `context-menu`, `dialog`, `dropdown-menu`, `listbox`, `meter`, `number-field`, `pagination`, `popover`, `progress`, `radio-group`, `select`, `slider`, `switch`, `tabs`, `text-field`, `toast`, `toggle-button`, `tooltip`, and color primitives.
- Color-picker note: Kobalte exposes color primitives (`color-area`, `color-channel-field`, `color-field`, `color-slider`, `color-swatch`, `color-wheel`) rather than a single `color-picker` package name.
- Form-field note: Kobalte has `text-field` and per-control `Label`, `Description`, and `ErrorMessage` APIs; the docs show ARIA wiring on controls such as Select.
- Select note: Select docs explicitly state support for single and multiple selection.
- Accessibility posture: docs say components follow WAI-ARIA Authoring Practices whenever possible and handle ARIA attributes, focus management, and keyboard navigation. Component docs include keyboard-interaction tables; Select docs document listbox pattern behavior, typeahead, focus management, hidden native select form integration, and modal focus/scroll behavior.
- Focus trap quality: package contents include internal focus-scope, hide-outside, interact-outside, and modal/select/dialog primitives; tests are present in the package tarball for many components. This is evidence of intentional focus management, not independent screen-reader certification.
- Screen-reader testing posture: docs discuss assistive-technology exposure and ARIA relationships, but no current public screen-reader test matrix was found.
- Maintenance signal in last 90 days: weak. One GitHub commit observed since 2026-01-27; latest npm release is 2025-07-26; no release in last 90 days.
- Sponsor count: no reliable repo-specific sponsor count found from primary sources. GitHub sponsor information is organization/person-level, not package-level.
- Production users cited by project docs: none found in Kobalte docs during this pass.
- Verdict for this project: strong established Solid-native option for Solid 1.x and broad coverage, but not the modern Solid 2 beta choice without a peer-range/support update.

### Ark UI Solid

- URL: https://ark-ui.com/
- GitHub repo: https://github.com/chakra-ui/ark
- npm package: `@ark-ui/solid`
- Current latest version: `5.36.2`
- Release date: 2026-04-22
- Repo status: 5,140 GitHub stars, 192 forks, pushed 2026-04-24, at least 100 commits observed since 2026-01-27 via the GitHub commits API page limit.
- npm downloads: 100,083 downloads in the last month ending 2026-04-26; 1,147,318 downloads from 2025-04-27 through 2026-04-27.
- Solid 2 compat: planned, not yet explicit. `@ark-ui/solid@5.36.2` publishes `peerDependencies: { "solid-js": ">=1.6.0" }`, which does not upper-bound Solid 2. However, in GitHub Discussion #3852 on 2026-04-10, Ark maintainer Segun Adebayo wrote that Solid 2 is still beta and Ark intends to batch 2.0 support with the next major release.
- Solid 2 migration path: explicit maintainer statement exists; no released migration guide or Solid 2-specific package was found as of 2026-04-27.
- Headless / unstyled: yes. Ark homepage says it is an unstyled/headless component library, has no default styles, supports plain stylesheets, and works across React, Solid, Vue, and Svelte.

| Component | Present |
|---|---:|
| Dialog / Modal | ✓ |
| Popover | ✓ |
| Tooltip | ✓ |
| Menu (context, dropdown) | ✓ |
| Select (single + multi) | ✓ |
| Combobox / Autocomplete | ✓ |
| Listbox | ✓ |
| Tabs | ✓ |
| Accordion | ✓ |
| Disclosure | ✓ |
| Toggle / Switch | ✓ |
| Checkbox + Radio | ✓ |
| Slider | ✓ |
| Progress + Meter | ✗ |
| Toast / Notification | ✓ |
| Toolbar | ✗ |
| Breadcrumbs | ✗ |
| Pagination | ✓ |
| Form field (label, hint, error region, ARIA wiring) | ✓ |
| Date picker | ✓ |
| Number field | ✓ |
| Color picker | ✓ |

- Coverage evidence: npm package contents include `accordion`, `checkbox`, `collapsible`, `color-picker`, `combobox`, `date-picker`, `dialog`, `field`, `fieldset`, `listbox`, `menu`, `number-input`, `pagination`, `popover`, `progress`, `radio-group`, `select`, `slider`, `switch`, `tabs`, `toast`, `toggle`, `tooltip`, and many additional components.
- Progress + Meter note: Ark has `progress`; no `meter` component was present in the package contents.
- Menu note: Ark Menu docs include dropdown menu behavior, checkbox/radio menu items, nested menus, and `Menu.ContextTrigger` for context menus.
- Select note: Ark Select/Combobox APIs support multi-selection via a `multiple` prop.
- Accessibility posture: homepage says WAI-ARIA patterns, keyboard navigation, and screen-reader support are built in. Component docs include explicit accessibility sections and keyboard-support tables; Combobox docs state compliance with the WAI-ARIA Combobox pattern.
- Focus trap quality: Ark is built on Zag state machines; the Solid package depends on `@zag-js/focus-trap`, `@zag-js/dialog`, `@zag-js/popover`, and related dismissable-layer/floating machinery. Ark also exposes a `focus-trap` component.
- Screen-reader testing posture: docs claim screen-reader support, but no public per-screen-reader/browser matrix was found.
- Maintenance signal in last 90 days: strong. Latest release is 2026-04-22; recent releases include 2026-04-10, 2026-04-16, and 2026-04-22; at least 100 commits since 2026-01-27.
- Sponsor count: no reliable Ark-package-specific sponsor count found from primary sources. Chakra organization sponsor data is not package-specific.
- Production users cited by project docs: Ark homepage/showcase cites Chakra UI, Park UI, Tark UI, Pluralsight Pando Design System, OVHCloud Design System, Typebot, RELAND, Gumbo, Promptmetheus, NDLA, Cerberus Design System, and Shark UI.
- Verdict for this project: best ecosystem/trending choice if accepting a short Solid 2 support risk. It is the only candidate with broad matrix coverage, active releases, production-user evidence, and an explicit Solid 2 support plan.

### Corvu

- URL: https://corvu.dev/
- GitHub repo: https://github.com/corvudev/corvu
- npm packages: `corvu`, `@corvu/*`
- Current latest meta-package version: `corvu@0.7.2`
- Meta-package release date: 2025-01-24
- Current latest checked primitive version: `@corvu/dialog@0.2.4`, released 2025-01-29; later package releases include `@corvu/disclosure@0.2.2` on 2025-03-24 and `@corvu/resizable@0.2.5` on 2025-05-04.
- Repo status: 698 GitHub stars, 15 forks, pushed 2025-08-07, 0 commits observed since 2026-01-27.
- npm downloads: `corvu` had 2,141 downloads in the last month ending 2026-04-26; `@corvu/dialog` had 19,460 downloads in the same period.
- Solid 2 compat: not declared. `corvu@0.7.2` and `@corvu/dialog@0.2.4` publish `peerDependencies: { "solid-js": "^1.8" }`, which excludes Solid 2 under normal peer resolution.
- Solid 2 migration path: no explicit Solid 2 migration path or support timeline found in repo/docs during this pass.
- Headless / unstyled: yes. Docs state primitives provide no styling and can be styled with plain CSS, Tailwind, UnoCSS, or CSS-in-JS.

| Component | Present |
|---|---:|
| Dialog / Modal | ✓ |
| Popover | ✓ |
| Tooltip | ✓ |
| Menu (context, dropdown) | ✗ |
| Select (single + multi) | ✗ |
| Combobox / Autocomplete | ✗ |
| Listbox | ✗ |
| Tabs | ✗ |
| Accordion | ✓ |
| Disclosure | ✓ |
| Toggle / Switch | ✗ |
| Checkbox + Radio | ✗ |
| Slider | ✗ |
| Progress + Meter | ✗ |
| Toast / Notification | ✗ |
| Toolbar | ✗ |
| Breadcrumbs | ✗ |
| Pagination | ✗ |
| Form field (label, hint, error region, ARIA wiring) | ✗ |
| Date picker | ✗ |
| Number field | ✗ |
| Color picker | ✗ |

- Coverage evidence: `corvu@0.7.2` package contents expose `accordion`, `calendar`, `dialog`, `disclosure`, `drawer`, `otp-field`, `popover`, `resizable`, and `tooltip`. Utility packages include focus trap, prevent scroll, dismissible, list, and presence.
- Date-picker note: Corvu has `calendar`, not a full date picker/field component matching the requested matrix.
- Accessibility posture: docs state primitives adhere to WAI-ARIA guidelines and handle ARIA attributes, focus management, and keyboard interactions. Docs also expose utility primitives such as `createFocusTrap`, `createPreventScroll`, and `createPresence`.
- Focus trap quality: solid-focus-trap and related Corvu utilities are first-class packages and dependencies of overlays; this is a positive architecture signal.
- Screen-reader testing posture: no public screen-reader matrix found.
- Maintenance signal in last 90 days: weak. No commits observed since 2026-01-27; latest repository push was 2025-08-07; last meta-package release was 2025-01-24.
- Sponsor count: no reliable repo-specific sponsor count found from primary sources.
- Production users cited by project docs: none found in Corvu docs during this pass.
- Verdict for this project: good Solid-native overlay/disclosure utility library, not enough coverage or current Solid 2 support to be the main primitives library.

### Solid Aria

- URL / GitHub repo: https://github.com/solidjs-community/solid-aria
- npm packages: `@solid-aria/primitives`, `@solid-aria/*`
- Current latest aggregate version: `@solid-aria/primitives@0.4.0`
- Release date: 2022-07-15
- Repo status: 291 GitHub stars, 18 forks, latest visible repo activity in 2022, 0 commits observed since 2026-01-27.
- npm downloads: `@solid-aria/primitives` had 65 downloads in the last month ending 2026-04-26; `@solid-aria/dialog` had 103.
- Solid 2 compat: no. Example packages publish Solid 1-only peer ranges such as `@solid-aria/button@0.1.3` with `solid-js: ^1.4.4`.
- Solid 2 migration path: none found.
- Headless / unstyled: yes at the primitive behavior layer, but the project is incomplete and explicitly not production-ready.

| Component | Present |
|---|---:|
| Dialog / Modal | ✓ |
| Popover | ✓ |
| Tooltip | ✗ |
| Menu (context, dropdown) | ✓ |
| Select (single + multi) | ✓ |
| Combobox / Autocomplete | ✗ |
| Listbox | ✓ |
| Tabs | ✗ |
| Accordion | ✓ |
| Disclosure | ✗ |
| Toggle / Switch | ✓ |
| Checkbox + Radio | ✓ |
| Slider | ✗ |
| Progress + Meter | ✓ |
| Toast / Notification | ✗ |
| Toolbar | ✗ |
| Breadcrumbs | ✓ |
| Pagination | ✗ |
| Form field (label, hint, error region, ARIA wiring) | ✓ |
| Date picker | ✗ |
| Number field | ✗ |
| Color picker | ✗ |

- Coverage evidence: README lists packages for button, checkbox, label, radio, select, switch, textfield, toggle, accordion, listbox, breadcrumbs, meter, progress, dialog, menu, overlays, collection, list, selection, tree, focus, interactions, i18n, and visually-hidden.
- Caveat: README also labels many future items as roadmap, including AutoComplete, Calendar, Combobox, DatePicker, NumberField, Pagination, Slider, Tabs, Toast, Tooltip, and Virtualizer.
- Accessibility posture: strong aspiration because it ports Adobe React Aria concepts, but the repo README explicitly says Solid Aria is early-stage and not ready for production.
- Focus trap quality: overlay/focus primitives exist, but current abandoned status makes quality hard to rely on.
- Screen-reader testing posture: README says more than half of features and tests had been ported toward React Aria parity, but collection packages needed testing and validation. No current public screen-reader matrix found.
- Maintenance signal in last 90 days: none.
- Sponsor count: no reliable repo-specific sponsor count found from primary sources.
- Production users cited by project docs: none.
- Verdict for this project: ruled out.

### Park UI primitives

- URL: https://park-ui.com/
- GitHub repo: https://github.com/chakra-ui/park-ui
- npm package checked: `@park-ui/cli`
- Current role: styled component generator/library built with Ark UI and Panda CSS, not a distinct headless primitive runtime.
- Solid 2 compat: inherits Ark UI dependency risk and adds Panda/CSS-system assumptions.
- Headless / unstyled: out of scope for the locked vanilla CSS stack. Installation docs require Panda project setup and state Park UI is built on Ark UI as its headless foundation.
- Coverage: not separately evaluated as primitives because the headless primitives are Ark UI.
- Maintenance signal: `@park-ui/cli` had 7,406 npm downloads in the last month ending 2026-04-26.
- Production users cited: Park UI itself is cited by Ark UI as an app/library built with Ark UI.
- Verdict for this project: ruled out as a styled/Panda layer, not the primitives choice.

### Other candidates surfaced

- Solid UI / solid-ui: listed in ecosystem/blog references as a Solid UI component layer, but current docs describe it as reusable components built with Kobalte and Corvu and styled with Tailwind CSS. That makes it out of scope for vanilla CSS headless primitives.
- Solid Primitives: active and official/community-important reactive primitives, but not a component primitives library covering the requested ARIA widgets.
- Formisch: surfaced on the Solid ecosystem page as a 2025 headless Solid form library. It is relevant for form state/validation, not dialog/select/menu/date-picker primitives.
- `@geenius/ui`: surfaced in npm search as a 2026 React/Solid shared component library, but its package description says "including HeroUI-backed React variants" and it did not surface as a headless Solid primitives library with the requested coverage. Ruled out for this question unless separately investigated.
- Headless UI Solid / Adobe React Aria Solid / Spectrum-Solid / Wedges / Magnet / OpenUI: no current primary-source Solid component-primitives library matching these names and the requested coverage surfaced in this pass.

### Pure HTML5 + ARIA + handwritten

- URL / repo: none; this is an in-house implementation path.
- Solid 2 compat: yes, because it avoids third-party Solid component peer ranges.
- Headless / unstyled: yes by definition.

| Component | Present |
|---|---:|
| Dialog / Modal | ✓ |
| Popover | ✓ |
| Tooltip | ✗ |
| Menu (context, dropdown) | ✗ |
| Select (single + multi) | ✓ |
| Combobox / Autocomplete | ✗ |
| Listbox | ✗ |
| Tabs | ✗ |
| Accordion | ✓ |
| Disclosure | ✓ |
| Toggle / Switch | ✓ |
| Checkbox + Radio | ✓ |
| Slider | ✓ |
| Progress + Meter | ✓ |
| Toast / Notification | ✗ |
| Toolbar | ✗ |
| Breadcrumbs | ✓ |
| Pagination | ✓ |
| Form field (label, hint, error region, ARIA wiring) | ✓ |
| Date picker | ✓ |
| Number field | ✓ |
| Color picker | ✓ |

- Coverage note: the checkmarks here mean browser-native elements or straightforward semantic HTML exist, not that a full accessible app widget exists. Native dialog/popover support is browser-dependent and still needs focus, escape-key, inertness, and screen-reader verification for production-grade composites.
- Accessibility posture: highest control, highest implementation burden. Complex widgets such as menu, combobox, listbox, tabs, and toast require handwritten ARIA, roving focus or active-descendant logic, keyboard behavior, focus restoration, dismissal, and testing.
- Maintenance signal: internal maintenance only.
- Verdict for this project: viable fallback if Solid 2 beta is non-negotiable before Ark publishes explicit support, but it gives up the main value of a primitives library.

## Trending signals

- Solid official ecosystem page: Ark UI and Corvu are listed in the Solid ecosystem UI/primitives areas; Formisch appears as a recent headless Solid form library. The page is a directory, not a recommendation or endorsement.
- Brenelz article: the April 27, 2024 "Solid Myths Debunked" article names Solid UI, Kobalte, and Corvu as evidence that Solid's UI library ecosystem exists. It predates current Ark momentum and Solid 2 beta.
- Ark UI momentum: latest release 2026-04-22, at least 100 commits since 2026-01-27, 5,140 stars, multi-framework docs, and visible production/showcase users.
- Kobalte momentum: still the npm install incumbent by downloads, with 710,146 last-month downloads vs Ark Solid's 100,083, but release cadence is stale relative to Ark and peer range excludes Solid 2.
- Corvu momentum: Solid-native and mentioned by Solid ecosystem/docs, but the 2026 maintenance signal is weak and coverage is intentionally smaller.
- Solid maintainer / Ryan Carniato comments: no primary-source Ryan Carniato or Solid core-maintainer statement from the last 90 days explicitly recommending Kobalte, Ark, Corvu, or Solid Aria was found in this pass.
- Ark maintainer statement: Segun Adebayo explicitly addressed Solid 2 on 2026-04-10 and said Ark is following Solid 2 and intends to batch support with the next major release.
- GitHub stars current snapshot: Ark 5,140; Kobalte 1,771; Corvu 698; Solid Aria 291. Historical 12-month star deltas were not reliably observable from primary repo APIs within rate limits in this pass.

## Recommendation

Choose Ark UI Solid as the target primitives library, with a release gate: require an Ark major release or documented build proving Solid 2 support before committing the production frontend to it. If the frontend must ship on Solid 2 beta before that Ark release exists, use native HTML plus tiny in-house wrappers for the immediate surface and keep the wrapper API close to Ark's component boundaries so migration is localized.

The evidence for Ark is stronger than the alternatives: it has current release velocity, current docs, wide component coverage, production-user examples, state-machine-backed behavior, a Solid package, and a maintainer-stated Solid 2 plan. The evidence against immediate blind adoption is also primary: explicit Solid 2 support is planned for the next major, not already shipped.

## Risks

- Ark UI Solid: the current package may work in simple cases with Solid 2 beta because the peer range has no upper bound, but maintainers have not called support done. Risk is beta churn or a major Ark API adjustment when official support lands. Migration cost if wrong in 12 months: moderate; component names/parts are explicit and wrappers can isolate imports.
- Kobalte: mature and heavily downloaded, but Solid 2 peer range excludes the target and release cadence is stale. Risk is being pinned to Solid 1-era assumptions or waiting on an unclear migration path. Migration cost if wrong in 12 months: moderate to high because Kobalte APIs differ from Ark/Zag state-machine APIs.
- Corvu: clean Solid-native overlays and utilities, but insufficient coverage for the requested matrix and no current Solid 2 support signal. Risk is needing to combine it with custom implementations for most complex controls. Migration cost if wrong in 12 months: low to moderate if used only for overlays; high if treated as the primary primitives layer.
- Solid Aria: explicitly not production-ready and inactive. Risk is adopting abandoned/incomplete primitives. Migration cost if wrong in 12 months: high relative to value because many missing widgets would be custom anyway.
- Park UI: strong ecosystem signal for Ark, but not compatible with the vanilla CSS lock because it assumes Panda CSS and styled generated components. Migration cost if wrong in 12 months: high if Panda recipes leak into app styling.
- Pure HTML + ARIA: avoids dependency/Solid 2 risk but transfers accessibility and keyboard behavior risk in-house. Migration cost if wrong in 12 months: low if wrappers are intentionally thin; high if every feature hand-rolls a different pattern.

## Citations

- Ark UI homepage and showcase: https://ark-ui.com/
- Ark UI GitHub repo API: https://api.github.com/repos/chakra-ui/ark
- Ark UI npm metadata: `npm view @ark-ui/solid version time repository homepage description peerDependencies dependencies --json`
- Ark UI package contents: `npm pack @ark-ui/solid --dry-run --json`
- Ark UI Combobox docs: https://ark-ui.com/docs/components/combobox
- Ark UI Menu docs: https://ark-ui.com/docs/components/menu
- Ark UI Solid 2 discussion: https://github.com/chakra-ui/ark/discussions/3852
- Kobalte docs: https://kobalte.dev/docs/core/overview/introduction
- Kobalte Select docs: https://kobalte.dev/docs/core/components/select
- Kobalte GitHub repo API: https://api.github.com/repos/kobaltedev/kobalte
- Kobalte npm metadata: `npm view @kobalte/core version time peerDependencies dependencies --json`
- Kobalte package contents: `npm pack @kobalte/core --dry-run --json`
- Corvu docs: https://corvu.dev/docs/
- Corvu GitHub repo API: https://api.github.com/repos/corvudev/corvu
- Corvu npm metadata: `npm view corvu version time peerDependencies dependencies --json` and `npm view @corvu/dialog version time peerDependencies dependencies --json`
- Corvu package contents: `npm pack corvu --dry-run --json`
- Solid Aria repo and README: https://github.com/solidjs-community/solid-aria
- Solid Aria npm metadata: `npm search --json "@solid-aria"` and `npm view @solid-aria/button peerDependencies --json`
- Park UI installation docs: https://park-ui.com/docs/installation
- Solid ecosystem page: https://www.solidjs.com/ecosystem
- Brenelz Solid ecosystem article: https://brenelz.com/posts/solid-myths-debunked/
- npm download API examples: https://api.npmjs.org/downloads/point/last-month/@ark-ui/solid and https://api.npmjs.org/downloads/point/last-month/@kobalte/core
