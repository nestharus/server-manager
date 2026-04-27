# Frontend Stack — Research Synthesis

## Question

Which frontend stack should `server-manager` use for the Phase 6 web UI?

The user context is:

- A single SPA should cover both public-applicant and admin/operator surfaces.
- Forms already exist as YAML schemas; "forms will likely need work to look nice" means a generic schema renderer plus per-form polish layer is acceptable.
- The web UI talks to a Python API in `services/api/`.
- Auth is handled by Pomerium at the edge with Authentik OIDC.
- Candidate repo location is `services/web/`.
- Tailwind v4, Park UI, Next.js, Remix, and the `ui-designer` reference are rejected as dated.
- The user mentioned a "new React fork from Cloudflare" as likely the best option.

The synthesis is constrained to the four finding reports:

- `.tmp/07-frontend-stack-A-findings.md` — Cloudflare React fork investigation
- `.tmp/07-frontend-stack-B-findings.md` — Solid ecosystem state
- `.tmp/07-frontend-stack-C-findings.md` — styling story
- `.tmp/07-frontend-stack-D-findings.md` — form library landscape

## Evidence-vs-premise gaps

- Cloudflare React fork: the user described a "new React fork from Cloudflare." Researcher A found `vinext`, not a React fork. Cloudflare describes `vinext` as "the Next.js API surface, reimplemented on Vite"; the README says it is not a fork of Next.js, and the findings say no evidence was found that it changes React semantics. It depends on React, React DOM, React Server Components infrastructure, Vite, `@vitejs/plugin-react`, and `@vitejs/plugin-rsc`. Citation: `.tmp/07-frontend-stack-A-findings.md` sections "Primary identification", "Project name + official URL", "Why it exists vs upstream React", and "Limitations vs upstream React".
- Tailwind v4 "dated": Researcher C found the current official Tailwind line is v4.2, latest release `v4.2.4` on 2026-04-21. Tailwind v4 is not deprecated or superseded. The strongest evidence behind skepticism is that v4.0 made a modern-browser bet that v4.1 later softened with older-browser fallbacks. Citation: `.tmp/07-frontend-stack-C-findings.md` section "Tailwind v4 actual status (and what came after)".
- Park UI "dated": Researcher C found Park UI is not deprecated in primary sources. It joined the Chakra UI organization on 2025-11-27, docs remain live, and imports keep working. The weaker point is package release activity: `@park-ui/panda-preset@0.43.1` was published 2024-11-22, older than Ark/Panda/Chakra. Citation: `.tmp/07-frontend-stack-C-findings.md` section "Park UI — actual status + replacements".
- Mantine version premise: Researcher C notes the user mentioned Mantine v8 as newer, but primary sources show Mantine v9.1.0 current as of 2026-04-21. Citation: `.tmp/07-frontend-stack-C-findings.md` section "Component-tier styling (current state)".
- Solid production line: Solid 2.0 is active beta, not the production default. The safer production posture is Solid 1.9.x plus Vite. Citation: `.tmp/07-frontend-stack-B-findings.md` sections "Solid core (version, release date, posture)" and "Momentum signals (last 90 days)".

## Stack candidates (with current-state evidence)

### Candidate 1: Solid SPA + Vite + TanStack + Ark UI/Panda CSS

- Components: router `@tanstack/solid-router`; data `@tanstack/solid-query`; forms `@tanstack/solid-form`; components `@ark-ui/solid`; styling Panda CSS; build Vite + `vite-plugin-solid`.
- Versions + release dates:
  - `solid-js@1.9.12`, published 2026-03-24; Solid 2.0 beta exists but is not production default.
  - `@tanstack/solid-router@1.168.24`, released 2026-04-26.
  - `@tanstack/solid-query@5.100.5`, released 2026-04-25.
  - `@tanstack/solid-form@1.29.1`, released 2026-04-21.
  - Ark UI docs version `v5.36.2`, changelog date 2026-04-22, with Solid as a first-class framework.
  - Panda CSS `@pandacss/dev@1.10.0`, published 2026-04-18.
  - `vite-plugin-solid@2.11.12`; `3.0.0-next.5` is for Solid 2 work.
- Pros for this project's constraints:
  - Fits an API-backed SPA without requiring a full-stack meta-framework.
  - Vite is the canonical Solid build setup for a plain SPA.
  - TanStack Query is specifically recommended by researcher B for Humility's FastAPI-backed dashboard.
  - TanStack Form has active Solid support and Standard Schema validation, which fits a project-owned YAML-to-schema renderer.
  - Ark UI gives accessible primitives across Solid and React; Panda gives type-safe design-system styling without Tailwind or Park.
  - Solid + TanStack adapters have current April 2026 releases, so the stack is current rather than stale.
- Cons / risks:
  - Solid ecosystem breadth is smaller and less uniformly active than React's.
  - Solid 2.0 transition churn is the main 12-month risk; production should stay on Solid 1.9.x until the ecosystem catches up.
  - There is no single Solid-wide form canonical equivalent to React Hook Form.
  - Off-the-shelf YAML/JSON-schema renderers are stronger in React than Solid, so Humility would own more of the renderer layer.
- Citations:
  - `.tmp/07-frontend-stack-B-findings.md` sections "Solid core (version, release date, posture)", "Router (canonical + runners-up)", "Data / cache", "Forms", "Component primitives", "Build tooling", and "Momentum signals (last 90 days)".
  - `.tmp/07-frontend-stack-C-findings.md` sections "Compile-time CSS solutions (current state)", "Component-tier styling (current state)", and "Component-library + styling combinations actually shipping in 2026 Q2".
  - `.tmp/07-frontend-stack-D-findings.md` sections "Solid stack: candidate form libs", "Schema validation (Zod / Valibot / Standard Schema)", "Conditional fields", and "Accessibility primitives".

### Candidate 2: vinext Next-compatible app on Vite/Cloudflare

- Components: router Next-compatible App Router or Pages Router; data Next-compatible server APIs and cache APIs; forms `next/form` plus Server Actions; components not prescribed by vinext; styling likely Ark UI/Panda, Mantine, Chakra, or another React-compatible layer; build `vinext` on Vite with `@vitejs/plugin-rsc` and `@cloudflare/vite-plugin`.
- Versions + release dates:
  - `vinext@0.0.44`, npm publish timestamp 2026-04-24.
  - GitHub repository created 2026-02-24.
  - Launch post dated 2026-02-24.
  - Launch status and README status: experimental, active, not GA.
  - Public npm versioning remains `0.0.x`; no explicit stable SemVer or breaking-change policy found.
- Pros for this project's constraints:
  - Strongest Cloudflare integration in the findings: Workers native target, `cloudflare:workers` bindings, workerd dev/runtime alignment, KV cache handler, and `vinext deploy`.
  - Familiar Next-compatible route and form model if the project wants App Router conventions without Vercel lock-in.
  - Official docs state non-Cloudflare targets exist through Nitro and static export, although Cloudflare Workers is the first native path.
  - If the app later needs server components, server actions, or edge-adjacent Cloudflare bindings, vinext is directly aimed at that shape.
- Cons / risks:
  - It is not a React fork and does not solve a React-framework choice by changing React itself.
  - It is experimental, under heavy development, and most code/tests/docs were written by AI per the README warning captured by researcher A.
  - It targets Next.js compatibility, not the user's stated single-SPA API-backed shape.
  - The documented form path is `next/form` plus Server Actions, while Humility's stated backend is Python API. That may create a second mutation surface instead of keeping the API first-class.
  - No vinext-native component primitive stack or TanStack Router/Form path was found in primary sources.
- Citations:
  - `.tmp/07-frontend-stack-A-findings.md` sections "Project name + official URL", "Status (version, release stage, date)", "Why it exists vs upstream React", "SPA stack ecosystem", "Cloudflare integration", and "Limitations vs upstream React".
  - `.tmp/07-frontend-stack-D-findings.md` sections "React-fork stack: candidate form libs", "YAML / JSON-schema-driven renderers", and "Accessibility primitives".

### Candidate 3: React SPA + Vite + TanStack/JSON Forms + Mantine v9

- Components: router TanStack Router for React; data TanStack Query for React; forms either TanStack React Form for project-owned form rendering or JSON Forms/RJSF for a heavier JSON-schema renderer; components/styling Mantine v9; build Vite.
- Versions + release dates:
  - React-specific router/query versions were not covered by the four reports, so this is a gap.
  - `@tanstack/react-form@1.29.1`, released 2026-04-21.
  - `react-hook-form@7.74.0`, released 2026-04-25; v8 beta exists but is not the default line.
  - `@jsonforms/react@3.7.0`, released 2025-11-27, package metadata modified 2026-03-05.
  - `@rjsf/core@6.5.1`, released 2026-04-18.
  - `@mantine/core@9.1.0`, released 2026-04-21.
- Pros for this project's constraints:
  - React has the strongest off-the-shelf schema-renderer evidence in the findings.
  - JSON Forms has JSON Schema plus UI schema, validation, data binding, and rule-based visibility out of the box.
  - RJSF is active and supports custom UI schema, dynamic UI schema, and themes including Mantine and Shad CN.
  - Mantine v9 is current, active, broad, and batteries-included, reducing design-system assembly cost.
  - A plain React SPA behind Pomerium is straightforward in principle, though the findings did not specifically research Pomerium integration.
- Cons / risks:
  - This candidate is assembled from strong React ecosystem pieces, but router/data current-state evidence for React was not directly researched in the four reports.
  - JSON Forms/RJSF require converting Humility YAML into JSON Schema plus UI schema, which may be heavier than a project-owned renderer.
  - Mantine is React-only, so choosing it closes the Solid path.
  - If Tailwind rejection is firm, this avoids Tailwind; if the real goal was open-code components, Mantine is a different model.
- Citations:
  - `.tmp/07-frontend-stack-C-findings.md` sections "Component-tier styling (current state)" and "Component-library + styling combinations actually shipping in 2026 Q2".
  - `.tmp/07-frontend-stack-D-findings.md` sections "React-fork stack: candidate form libs", "YAML / JSON-schema-driven renderers", "Conditional fields", "Schema validation (Zod / Valibot / Standard Schema)", and "Accessibility primitives".

## Tradeoff matrix

| Axis | Solid SPA + Vite + TanStack + Ark/Panda | vinext Next-compatible app | React SPA + Vite + TanStack/JSON Forms + Mantine |
| --- | --- | --- | --- |
| Production-readiness today | Strong if pinned to Solid 1.9.x; Solid 2.0 should be avoided for production. | Weak-to-mixed: active but experimental, `0.0.x`, no stable SemVer policy found. | Strongest mainstream readiness among the three, but React router/data specifics were not directly researched. |
| Form-renderer fitness for YAML schemas | Good if Humility owns the renderer; weaker off-the-shelf renderer ecosystem than React. | Mixed: Next forms/server actions exist, but they pull toward vinext server mutations rather than Python API-first YAML rendering. | Strong: JSON Forms/RJSF are the best off-the-shelf renderer evidence; TanStack/RHF are strong lower-level engines. |
| Maintenance momentum (last 90 days) | Strong: Solid core, TanStack Solid adapters, Ark, and Panda all have recent releases. | Strong activity but young and experimental; latest release 2026-04-24. | Strong for Mantine, TanStack Form, RHF, RJSF; JSON Forms current but latest release is 2025-11-27. |
| Auth-via-Pomerium fit | No stack-specific blocker found; SPA behind edge auth should fit. Evidence gap: Pomerium was not directly researched. | No stack-specific blocker found, but server actions/RSC may complicate the clean edge-auth plus Python API boundary. Evidence gap: Pomerium was not directly researched. | No stack-specific blocker found; conventional SPA behind edge auth should fit. Evidence gap: Pomerium was not directly researched. |
| Risk if the project peaks in 12 months | Medium: Solid 2 migration churn and smaller ecosystem breadth. | High: experimental API-compat layer may churn or fail to match long-tail Next behavior. | Low-to-medium: broad ecosystem, but schema-renderer conversion and React-only component choice can add complexity. |

## Recommendation

Choose **Solid 1.9.x + Vite + TanStack Router/Query/Form + Ark UI + Panda CSS** for Phase 6, unless the user wants the frontend decision to optimize specifically for an off-the-shelf schema renderer.

Rationale:

- It best matches the stated architecture: a single API-backed SPA in `services/web/`, not a full-stack React/Next-compatible server framework.
- It respects the rejected stack constraints without relying on the false premise that Tailwind/Park are actually deprecated.
- It gives a coherent current stack: Vite is the Solid default, TanStack Solid packages have April 2026 releases, Ark UI has active Solid support, and Panda is the strongest current replacement path for Park-style typed design-system styling.
- It keeps the Python API first-class. vinext's strongest value is Cloudflare/Next compatibility, but Humility's current need is a Pomerium-protected SPA that talks to `services/api/`.
- The main cost is owned form rendering. Given the user's context explicitly allows "generic schema renderer + per-form polish layer," that cost is acceptable.

Do **not** choose vinext as the default on current evidence. It is real and active, but it is experimental, not a React fork, and is optimized around Next.js API compatibility rather than this project's API-first SPA boundary.

If the user-mentioned Cloudflare React fork is real and is **not** `vinext`, researcher A missed it. That would require a follow-up identification pass before changing the recommendation.

## Open questions for the user (Phase 4 decision)

1. Is the Tailwind/Park rejection a hard ban, or just a rejection of the old `ui-designer` reference stack?
2. Is owning a Solid YAML form renderer acceptable for Phase 6, or must the first version use an off-the-shelf schema renderer such as JSON Forms/RJSF?
3. Is Cloudflare Workers deployment a near-term requirement, or is the web UI simply a static/API-backed SPA behind Pomerium for now?

## Draft current problem map

- Build a single `services/web/` SPA that can serve public applicant flows and authenticated admin/operator workflows.
- Keep the Python API as the mutation/query boundary.
- Treat Pomerium/Authentik as edge auth; frontend should consume authenticated API responses rather than own OIDC flows unless later research says otherwise.
- Render existing YAML forms with a generic renderer, plus per-form polish for high-value application flows.
- Provide enough component and styling structure for dense admin/operator screens, not a marketing surface.
- Avoid dated or rejected project references, but distinguish factual deprecation from user taste/architecture choices.

## Draft assumption register

- The first production target is a browser SPA, not SSR/RSC/server actions.
- Solid 1.9.x remains the production baseline through the proposal; Solid 2.0 beta is out of scope.
- TanStack Query will own API server-state caching and mutations.
- TanStack Form will own field state; Humility code will own YAML normalization, conditional visibility, inactive-field semantics, and submit payload shaping.
- Ark UI supplies accessible primitives; Panda CSS supplies typed tokens/recipes/styling.
- Pomerium integration does not require frontend framework-specific code beyond normal authenticated API requests. This remains an evidence gap because Pomerium was not researched in these four findings.

## Citations

- https://github.com/cloudflare/vinext
- https://vinext.io/
- https://blog.cloudflare.com/vinext/
- https://tailwindcss.com/blog/tailwindcss-v4
- https://tailwindcss.com/blog/tailwindcss-v4-1
- https://tailwindcss.com/docs/compatibility
- https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.2.4
- https://tailwindcss.com/plus/ui-blocks/documentation
- https://headlessui.com/
- https://github.com/tailwindlabs/headlessui/releases/tag/%40headlessui/react%40v2.2.10
- https://tailwindcss.com/blog/introducing-catalyst
- https://2025.stateofcss.com/en-US/other-tools/
- https://unocss.dev/guide/why
- https://github.com/unocss/unocss/releases/tag/v66.6.8
- https://css.master.co/
- https://github.com/master-co/css/releases/tag/v1.37.7
- https://panda-css.com/docs/overview/why-panda
- https://github.com/chakra-ui/panda/releases/tag/%40pandacss/core%401.10.0
- https://vanilla-extract.style/
- https://github.com/vanilla-extract-css/vanilla-extract/releases/tag/%40vanilla-extract/webpack-plugin%402.3.27
- https://stylexjs.com/docs/learn/
- https://github.com/facebook/stylex/releases/tag/0.17.5
- https://mui.com/blog/introducing-pigment-css/
- https://mui.com/material-ui/migration/migrating-to-pigment-css/
- https://github.com/mui/pigment-css/releases/tag/v0.0.30
- https://github.com/callstack/linaria/releases/tag/linaria%407.0.1
- https://github.com/Shopify/restyle/releases/tag/v2.4.5
- https://ark-ui.com/
- https://github.com/chakra-ui/ark/releases/tag/%40ark-ui/svelte%405.21.2
- https://park-ui.com/blog/park-ui-joins-the-chakra-ui-organization
- https://park-ui.com/docs/introduction
- https://github.com/chakra-ui/park-ui/releases/tag/%40park-ui/panda-preset%400.43.1
- https://www.chakra-ui.com/docs/get-started/frameworks/vite
- https://github.com/chakra-ui/chakra-ui/releases/tag/%40chakra-ui/charts%403.35.0
- https://mantine.dev/
- https://github.com/mantinedev/mantine/releases/tag/9.1.0
- https://ui.shadcn.com/docs
- https://github.com/shadcn-ui/ui/releases/tag/shadcn%404.5.0
- https://www.w3.org/TR/css-2026/
- https://registry.npmjs.org/
- https://tanstack.com/form
- https://github.com/TanStack/form
- https://tanstack.com/form/v1/docs/framework/react/guides/validation
- https://tanstack.com/form/v1/docs/framework/react/guides/reactivity
- https://tanstack.com/form/v1/docs/framework/react/guides/dynamic-validation
- https://tanstack.com/form/v1/docs/framework/react/guides/listeners
- https://react-hook-form.com
- https://github.com/react-hook-form/react-hook-form
- https://github.com/react-hook-form/documentation/blob/master/src/content/docs/useform/watch.mdx
- https://github.com/react-hook-form/documentation/blob/master/src/content/docs/usewatch.mdx
- https://github.com/react-hook-form/documentation/blob/master/src/content/docs/useform/unregister.mdx
- https://github.com/react-hook-form/documentation/blob/master/src/content/advanced-usage.mdx
- https://github.com/react-hook-form/resolvers
- https://tanstack.com/form/v1/docs/framework/solid/guides/validation
- https://modularforms.dev/
- https://github.com/fabian-hiller/modular-forms
- https://modularforms.dev/solid/guides/validate-your-fields
- https://felte.dev/
- https://github.com/pablo-abc/felte
- https://api.felte.dev/modules.html
- https://github.com/standard-schema/standard-schema
- https://zod.dev/v4
- https://valibot.dev/guides/integrate-valibot/
- https://github.com/rjsf-team/react-jsonschema-form
- https://jsonforms.io/
- https://rjsf-team.github.io/react-jsonschema-form/docs/api-reference/dynamic-ui-schema-examples/
- https://rjsf-team.github.io/react-jsonschema-form/docs/api-reference/uiSchema/
- https://github.com/alibaba/formily
- https://uniforms.tools/
- https://www.radix-ui.com/primitives/docs/components/form
- https://ark-ui.com/docs/guides/forms
- https://kobalte.dev/docs/core/components/text-field/
- https://uppy.io/
- https://github.com/transloadit/uppy
- https://uppy.io/docs/react/
- https://uppy.io/docs/dashboard/
- https://uppy.io/docs/tus/
- https://pqina.nl/filepond
- https://github.com/pqina/filepond
- https://pqina.nl/filepond/
- https://pqina.nl/filepond/docs/api/server/
- https://docs.uploadthing.com
- https://github.com/pingdotgg/uploadthing
- https://docs.uploadthing.com/api-reference/react
- https://docs.uploadthing.com/uploading-files
