# Ark UI Solid coverage-gap findings

Date checked: 2026-04-27.

Scope: Solid 2 beta SPA, Ark UI Solid, vanilla CSS, no styled component
library, no Tailwind, no Panda CSS, no Park UI.

## Summary verdict

Meter: use path 3, hand-roll on top of native HTML. Prefer native `<meter>` for
the semantic object and accessible name/value exposure. Add a vanilla-CSS visual
layer only if the browser-native meter cannot be styled consistently enough.
Do not add Kobalte for Meter in this stack today: Kobalte has a good unstyled
Meter primitive, but its current npm peer range is `solid-js: ^1.8.15`, which
does not cover Solid 2 beta.

Toolbar: use path 3, hand-roll the APG toolbar pattern with native controls,
`role="toolbar"`, roving `tabindex`, orientation-aware arrow keys, `Home`, and
`End`. There is no current Solid-compatible headless Toolbar primitive that
passes the constraints. Kobalte has no Toolbar, Solid Aria has no Toolbar
package, React Aria Toolbar is React-only, and Zag does not publish a toolbar
machine.

Breadcrumbs: use path 3, hand-roll the canonical APG breadcrumb markup and feed
items from TanStack Router route matches/context. Breadcrumbs are simple enough
that a dependency is not justified, especially because Kobalte's Breadcrumbs
primitive fails the Solid 2 beta peer-range requirement. TanStack Router does
not auto-render breadcrumbs, but its route context docs explicitly support
building breadcrumb data from matches.

## Meter

- Native `<meter>` posture:
  - MDN marks `<meter>` as "Baseline Widely available"; it represents a scalar
    value within a known range or a fractional value.
  - Its implicit ARIA role is `meter`; MDN says no explicit ARIA role is
    permitted on `<meter>`.
  - MDN's ARIA `meter` role page recommends native `<meter>` where possible
    because native elements are more widely supported by browsers and assistive
    technology.
  - APG's Meter pattern is non-interactive: keyboard interaction is not
    applicable.
  - APG requires a value in a known range and a label via `aria-labelledby` or
    `aria-label` for custom `role="meter"` implementations.
  - APG explicitly says not to use meter for progress/loading; progress belongs
    to `progressbar` / `<progress>`.

- Native versus `role="meter"`:
  - Modern default should be native `<meter>`.
  - `role="meter"` on a `div` is appropriate only when native `<meter>` cannot
    satisfy the visual/DOM requirements.
  - A custom `role="meter"` must recreate the full accessible contract:
    accessible name, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, and
    `aria-valuetext` when percentage speech would be misleading.
  - Descendants of ARIA `meter` are treated as presentational in the accessibility
    tree, so do not put meaningful semantic content inside the custom meter
    element itself.

- Styling story:
  - `<meter>` is usable with vanilla CSS, but it is not a perfectly clean
    "unstyled primitive".
  - Browser-native meter internals are exposed through vendor-specific,
    non-standard pseudo-elements.
  - If the product only needs a simple horizontal gauge, style native `<meter>`
    with `appearance: none` plus browser-specific pseudo-elements.
  - If the product needs fully uniform design across browsers, keep native
    `<meter>` as the semantic element and render a separate `aria-hidden`
    visual bar controlled by the same value.
  - Avoid duplicate announcements: the decorative visual bar should be
    `aria-hidden="true"`.

- Library options + Solid 2 compat:
  - Kobalte has Meter.
  - Kobalte Meter imports selectively from `@kobalte/core/meter`.
  - `npm view @kobalte/core` on 2026-04-27 returned:
    - version `0.13.11`
    - peer dependency `solid-js: ^1.8.15`
    - export map with `"./*"` component subpath exports
  - `^1.8.15` does not include `solid-js@2.0.0-beta.8`.
  - Solid Aria has `@solid-aria/meter`, but it is version `0.0.2`, last
    modified in 2022, and peers on `solid-js: ^1.4.4`.
  - React Aria has `useMeter`, but it is React-only. `@react-aria/meter`
    currently peers on `react` and `react-dom`, not Solid.
  - React Aria's Meter docs are still useful evidence: Adobe notes that native
    `<meter>` exists but is difficult to style cross-browser, and their hook
    implements a stylable ARIA meter wrapper for React.
  - No credible newer Solid-compatible Meter library found in npm search that is
    both headless and Solid 2 beta peer-compatible.

- Recommended path:
  - Use native `<meter>` by default.
  - Wrap it in a project-owned `Meter` component so the app has one place for
    labeling, value clamping, value text, and styling conventions.
  - Do not use Zag `@zag-js/progress`; progress is not meter, and a progress
    machine would encode the wrong semantics.

- Code-shape sketch:

```tsx
type MeterProps = {
  id: string
  label: string
  value: number
  min?: number
  max?: number
  valueText?: string
}

export function Meter(props: MeterProps) {
  const min = () => props.min ?? 0
  const max = () => props.max ?? 100
  const clamped = () => Math.min(max(), Math.max(min(), props.value))
  const pct = () => ((clamped() - min()) / (max() - min())) * 100

  return (
    <div class="meter" style={{ "--meter-fill": `${pct()}%` }}>
      <label for={props.id} class="meter__label">{props.label}</label>
      <meter id={props.id} min={min()} max={max()} value={clamped()}>
        {props.valueText ?? `${Math.round(pct())}%`}
      </meter>
      <span class="meter__track" aria-hidden="true">
        <span class="meter__fill" />
      </span>
    </div>
  )
}
```

- Caveats:
  - Do not use this for task completion or loading; use `<progress>` or Ark's
    Progress if that component covers the case.
  - Test with browser/AT combinations if the meter conveys business-critical
    status, because APG warns that ARIA example support can vary.

## Toolbar

- WAI-ARIA pattern recap:
  - A toolbar groups related controls such as buttons, menu buttons, checkboxes,
    links, or other command controls.
  - APG says a toolbar can reduce tab stops by making the toolbar one tab stop
    and using arrow keys to move focus between controls.
  - Use `role="toolbar"` on the container and provide an accessible name with
    `aria-label` or `aria-labelledby`.
  - Horizontal is the implicit orientation.
  - For vertical toolbars, set `aria-orientation="vertical"`.
  - On first tab into the toolbar, focus should land on the first enabled
    control; later entries may restore the last focused control.
  - Horizontal toolbar: `Left Arrow` / `Right Arrow` move focus. Vertical
    toolbar: `Up Arrow` / `Down Arrow` move focus.
  - `Home` and `End` are optional but recommended in an app-style toolbar.
  - APG cautions against including controls whose own operation requires the
    same arrow keys used for toolbar navigation.
  - APG says use `toolbar` as a grouping element only when the group contains
    three or more controls.

- Library options + Solid 2 compat:
  - Kobalte does not list a Toolbar component.
  - Kobalte has Menubar, Navigation Menu, Toggle Group, etc., but none is a
    general APG toolbar primitive.
  - Solid Aria has no `@solid-aria/toolbar` package; npm returned 404.
  - Solid Aria packages are old and peer on Solid 1 ranges; they should not be
    adopted for a Solid 2 beta target.
  - React Aria has `@react-aria/toolbar` at `3.0.0-beta.25`, but its peer
    dependencies are React/React DOM ranges. It is not a Solid primitive.
  - Zag's public machine catalog/search shows many machines including progress,
    menu, combobox, switch, toggle, select, pagination, slider, and tooltip, but
    no `@zag-js/toolbar` package. `npm view @zag-js/toolbar` was not found.
  - `@zag-js/solid` exists, but its peer range is `solid-js: >=1.1.3`; strict
    semver does not satisfy `2.0.0-beta.8` for that range unless the installer
    is configured to allow prereleases/overrides.
  - `@solid-primitives/keyboard`, `event-listener`, and `refs` currently peer on
    `solid-js: ^1.6.12`, so avoid them under a strict Solid 2 beta peer gate.
  - Floating UI is not relevant to core Toolbar behavior. It helps position
    popovers/menus/tooltips, not manage toolbar roving focus.

- Native `<menu>` status:
  - MDN says browsers treat `<menu>` and expose it through the accessibility tree
    no differently than `<ul>`, while describing it as a semantic alternative for
    a list of interactive items/commands.
  - The old `type="toolbar"` / `type="context"` direction is obsolete.
  - For this project, a `<div role="toolbar">` containing native `<button>` and
    `<a>` controls is clearer than `<menu>` because APG directly specifies the
    `toolbar` role contract.

- Recommended path:
  - Create a small project-owned `Toolbar` and `ToolbarItem` abstraction.
  - Use native focusable controls as children.
  - Implement roving `tabindex` directly.
  - Do not adopt menu/menubar primitives as a toolbar substitute. Menubar and
    toolbar have different user expectations.

- Code-shape sketch:

```tsx
type ToolbarProps = {
  label: string
  orientation?: "horizontal" | "vertical"
  children: JSX.Element
}

export function Toolbar(props: ToolbarProps) {
  let items: HTMLElement[] = []
  const [active, setActive] = createSignal(0)
  const horizontal = () => props.orientation !== "vertical"
  const move = (delta: number) => {
    const next = (active() + delta + items.length) % items.length
    setActive(next)
    items[next]?.focus()
  }

  return (
    <div
      role="toolbar"
      aria-label={props.label}
      aria-orientation={props.orientation}
      onKeyDown={(event) => {
        const key = event.key
        if ((horizontal() && key === "ArrowRight") || (!horizontal() && key === "ArrowDown")) { event.preventDefault(); move(1) }
        if ((horizontal() && key === "ArrowLeft") || (!horizontal() && key === "ArrowUp")) { event.preventDefault(); move(-1) }
        if (key === "Home") { event.preventDefault(); setActive(0); items[0]?.focus() }
        if (key === "End") { event.preventDefault(); setActive(items.length - 1); items.at(-1)?.focus() }
      }}
    >
      {/* ToolbarButton registers its native button/link ref and sets tabindex */}
    </div>
  )
}
```

- Caveats:
  - The sketch omits disabled-item skipping, registration cleanup, and item
    context; implement those in production.
  - APG Toolbar does not define `Escape`; nested Ark popups should own their own
    escape/close/focus-return behavior.
  - A generic toolbar should not auto-focus on mount; if explicitly requested,
    focus the active toolbar item, not the toolbar container.
  - Do not put a text input or slider in the middle of a horizontal toolbar
    unless the arrow key conflict is intentionally designed and tested.
  - If an item wraps Ark Menu/Popover/Tooltip, keep toolbar roving focus at the
    trigger level and let Ark own popup focus management after activation.
  - Add Playwright keyboard tests for tab entry, arrow movement, wrap behavior,
    `Home`, `End`, disabled controls, and embedded Ark menu escape behavior.

## Breadcrumbs

- WAI-ARIA pattern recap:
  - APG defines breadcrumbs as links to parent pages of the current page in
    hierarchical order.
  - Keyboard interaction is not applicable beyond ordinary link behavior.
  - The trail should be inside a named navigation landmark.
  - If the current page is represented by a link, that link gets
    `aria-current="page"`.
  - If the current page is represented by plain text rather than a link,
    `aria-current` is optional.
  - MDN similarly says only one item in a set should be marked current.

- Library options + Solid 2 compat:
  - Kobalte has Breadcrumbs.
  - Kobalte Breadcrumbs imports selectively from `@kobalte/core/breadcrumbs`.
  - Kobalte is a reasonable Solid 1 option but is not selected here because
    `@kobalte/core@0.13.11` peers on `solid-js: ^1.8.15`.
  - Solid Aria has `@solid-aria/breadcrumbs`, but it is version `0.1.4`, last
    modified in 2022, and peers on `solid-js: ^1.4.4`.
  - Ark UI Solid does not list Breadcrumbs in the current Solid docs component
    navigation checked on 2026-04-27.

- TanStack Router auto-breadcrumb story:
  - TanStack Router is for React and Solid applications.
  - Its docs do not provide a prebuilt Breadcrumb component that auto-renders
    route labels.
  - Its Router Context guide explicitly lists breadcrumbs as a practical use of
    route context.
  - So the router story is "bring your own breadcrumb UI, derive data from route
    matches/context."
  - Separate npm check: `@tanstack/solid-router@1.168.25` currently peers on
    `solid-js: ^1.9.10`, which does not cover Solid 2 beta under strict semver.
    This is a stack-level compatibility item, not a reason to add a breadcrumb
    library.

- Recommended path:
  - Hand-roll a `Breadcrumbs` component in project code.
  - Keep the markup canonical: `<nav aria-label="Breadcrumb"><ol>...`.
  - Use normal router links for ancestors.
  - Render the final crumb as text, or as a link with `aria-current="page"` if
    the app requires the current item to be navigable.
  - Use CSS pseudo-elements or `aria-hidden` spans for separators.

- Code-shape sketch:

```tsx
type Crumb = { label: string; href?: string }

export function Breadcrumbs(props: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" class="breadcrumbs">
      <ol class="breadcrumbs__list">
        <For each={props.items}>
          {(item, index) => {
            const current = () => index() === props.items.length - 1
            return (
              <li class="breadcrumbs__item">
                <Show when={!current() && item.href} fallback={<span aria-current="page">{item.label}</span>}>
                  <A href={item.href!}>{item.label}</A>
                </Show>
              </li>
            )
          }}
        </For>
      </ol>
    </nav>
  )
}
```

- TanStack-derived data sketch:

```tsx
const matches = useRouterState({ select: (state) => state.matches })
const crumbs = createMemo(() =>
  matches()
    .filter((match) => match.context.getTitle)
    .map((match) => ({
      label: match.context.getTitle(),
      href: match.pathname,
    })),
)
```

- Caveats:
  - Breadcrumb labels should come from route metadata/context, not string-split
    URL segments.
  - Dynamic route labels should come from loader data or route context, e.g.
    server name rather than `$serverId`.
  - Avoid making visual separators part of the accessible name.

## Cross-cutting

- Mixing Ark + Kobalte:
  - In a Solid 1 app, using Kobalte for one missing component can be reasonable
    because it is headless and has component subpath imports.
  - In this Solid 2 beta app, Kobalte is not a clean dependency because its peer
    range is `solid-js: ^1.8.15`.
  - Installing it would require ignoring peer constraints, pinning Solid 1, or
    waiting for Kobalte to publish a Solid 2-compatible range.

- Focus-management collision check:
  - Meter and Breadcrumbs are not focus-management components, so Kobalte Meter
    or Breadcrumbs would not meaningfully collide with Ark focus traps or
    dismissable-layer stacks.
  - Toolbar itself should not create a focus trap or dismissable layer.
  - If a toolbar item opens Ark Menu/Popover/Dialog, Ark should own the popup's
    focus return and outside-interaction handling.

- Tree-shaking single Kobalte components:
  - Kobalte docs show component-level imports:
    - `@kobalte/core/meter`
    - `@kobalte/core/breadcrumbs`
  - `npm view @kobalte/core exports` shows a `"./*"` subpath export.
  - That supports selective imports at source level.
  - This is useful only if the peer range is acceptable; it is not acceptable
    for Solid 2 beta today.

- Adobe React Aria community ports:
  - React Aria itself has strong Meter and Toolbar accessibility work, but the
    packages peer on React/React DOM.
  - Solid Aria appears to be the relevant historical Solid port line, but its
    Meter and Breadcrumbs packages are from 2022 and peer on Solid 1.4.
  - No current 2025-2026 Solid port was found that covers Meter, Toolbar, and
    Breadcrumbs with Solid 2 beta peer support.

- Floating UI:
  - `@floating-ui/dom@1.7.6` is current and framework-agnostic positioning
    infrastructure.
  - There is no official `@floating-ui/solid` package in npm search.
  - Community packages found peer on Solid 1 ranges.
  - Floating UI is not directly relevant to Meter, Toolbar, or Breadcrumbs.

- Solid 2 beta peer-range note:
  - `solid-js` npm dist-tags checked on 2026-04-27:
    - `latest`: `1.9.12`
    - `next`: `2.0.0-beta.8`
  - Strict semver prerelease matching is conservative. Local `npx semver`
    checks returned non-zero for `2.0.0-beta.8` against `>=1.6.0`,
    `>=1.1.3`, and `^1.8.15`.
  - Dependencies with no Solid peer are therefore lower risk for a strict Solid
    2 beta install than Solid 1-only primitive packages.

## Citations

- WAI-ARIA APG: Meter pattern https://www.w3.org/WAI/ARIA/apg/patterns/meter/; Meter example https://www.w3.org/WAI/ARIA/apg/patterns/meter/examples/meter/; Toolbar pattern https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/; Toolbar example https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/examples/toolbar/; Breadcrumb pattern https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb/
- MDN: `<meter>` https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/meter; ARIA meter role https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/meter_role; ARIA toolbar role https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/toolbar_role; `<menu>` https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/menu; `aria-current` https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-current
- Kobalte: Meter https://kobalte.dev/docs/core/components/meter/; Breadcrumbs https://kobalte.dev/docs/core/components/breadcrumbs/; npm https://www.npmjs.com/package/@kobalte/core
- Ark UI: Solid Menu component navigation https://ark-ui.com/solid/docs/components/menu; changelog https://ark-ui.com/docs/overview/changelog; styling guide https://ark-ui.com/docs/guides/styling
- Zag: homepage/catalog https://zagjs.com/; Progress npm https://www.npmjs.com/package/@zag-js/progress
- React Aria: `useMeter` https://react-aria.adobe.com/Meter/useMeter; Meter https://react-spectrum.adobe.com/react-aria/Meter.html; Toolbar npm https://www.npmjs.com/package/@react-aria/toolbar
- TanStack Router: context https://tanstack.com/router/latest/docs/framework/react/guide/router-context; overview https://tanstack.com/router/router/docs
- Floating UI DOM npm package: https://www.npmjs.com/package/@floating-ui/dom

Npm registry checks run locally on 2026-04-27 with `npm view` for: `solid-js`, `@ark-ui/solid`, `@kobalte/core`, `@solid-aria/meter`, `@solid-aria/breadcrumbs`, `@solid-aria/toolbar`, `@zag-js/toolbar`, `@zag-js/progress`, `@react-aria/meter`, `@react-aria/toolbar`, `@tanstack/solid-router`, `@floating-ui/dom`, and `floating-ui-solid`.
Semver checks used `npx --yes semver -r <range> 2.0.0-beta.8`.
