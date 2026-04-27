# INIT-118 Phase 1 Research: Web UI Substrate

INIT-118 consumes the existing frontend research rather than reopening stack
selection. The locked stack is Solid 2 beta plus Vite, TanStack Router/Query/
Form/Store/Table/Virtual, Ark UI Solid, vanilla CSS Modules and cascade layers,
FontAwesome SVG Core, Oxlint/Oxfmt, and TypeScript native preview. Binding
inputs are `.pipeline/08-frontend-stack.md` ("Corrected stack synthesis"),
`.pipeline/09-solid-component-primitives-findings.md` ("Recommendation"),
`.pipeline/10-ark-gap-components-findings.md` ("Gap components"),
`.pipeline/11-webawesome-fontawesome-findings.md` ("Path C"), and
`.pipeline/12-fa-wa-agent-integration-findings.md` ("Operational handoff").

The implementation pins the observed beta set: `solid-js@2.0.0-beta.8`,
`@solidjs/web@2.0.0-beta.8`, `vite-plugin-solid@3.0.0-next.5`, `vite@8.0.10`,
Ark UI `5.36.2`, Oxlint `1.62.0`, Oxfmt `0.47.0`, Playwright `1.59.1`, and
`@typescript/native-preview@7.0.0-dev.20260427.1` for `tsgo`. Solid 2 beta has
split web rendering into `@solidjs/web`; the release gate therefore treats the
Solid 2 renderer and current Solid 1-oriented adapters as a compatibility risk.

## Toolchain Availability

- Node `v22.15.0`, npm `11.6.2`, Bun `1.3.4`, and Playwright `1.59.1` are present.
- `solid-js@next` resolves to `2.0.0-beta.8`; `@solidjs/web@next` resolves to
  the same beta.
- Vite `8.0.10`, `vite-plugin-solid@3.0.0-next.5`, Oxlint `1.62.0`, Oxfmt
  `0.47.0`, and `@typescript/native-preview@7.0.0-dev.20260427.1` install.
- There is no npm package named `tsgo`; the `tsgo` binary is provided by
  `@typescript/native-preview`.
- Ark UI installs because its peer range allows Solid `>=1.6.0`, but its
  explicit Solid 2 support remains a release-gated compatibility item.

## Proposal Priorities

- Keep Pomerium as the auth boundary; the SPA reads `/api/v1/me` only.
- Ship one local k3d proof: Pod Ready, public route reachable, admin route gated.
- Keep CSS vanilla through layers, tokens, and modules; do not add Tailwind,
  Panda, WebAwesome, or a styling DSL.
- Put FontAwesome token handling in scripts and templates, never committed
  `.npmrc` token material.
- Make the Solid 2 beta adapter risk visible through compatibility tests and
  the INIT-119+ handoff.
