# Sub-Question D - Form library findings

Date basis: researched on 2026-04-26. Scope: "Cloudflare React fork" is treated
as React-compatible, not a new form-state ecosystem.
Existing Humility form shape: `forms/dark-nemesis.yaml` is a project-owned DSL
with `short`, `long`, `select`, `multi_select`, `number`, `required`,
`max_length`, ordered `questions`, and expected email/pages/conditions.

## React-fork stack: candidate form libs

### TanStack Form

- Project URL: https://tanstack.com/form and https://github.com/TanStack/form
- Current package: `@tanstack/react-form` 1.29.1.
- Release date: 2026-04-21 UTC from npm registry `time["1.29.1"]`.
- Maintenance status: active; current release was 5 days before this research
  date, docs are current under Form v1, and the same repo ships React and Solid
  packages.
- Why people pick it in 2026: type-heavy, headless, framework-agnostic form
  state with granular subscriptions and native Standard Schema validation.
- Field-state posture: first-class field and form validators, sync/async
  validators, configurable validation events, field-level and form-level error
  maps. [C1]
- Schema posture: natively accepts Standard Schema validators including Zod,
  Valibot, ArkType, and Effect/Schema. [C1]
- Type posture: strong TypeScript surface for field names and values, but
  validation does not return transformed schema values. [C1]
- Conditional UI posture: `form.Subscribe` is documented for showing/hiding UI
  based on field values without root component rerenders. [C2]
- Conditional validation posture: `onDynamic` plus `revalidateLogic()` is the
  documented dynamic validation mechanism. [C3]
- Side-effect posture: field and form listeners support onChange/onBlur effects,
  debouncing, and dependent-field resets. [C4]
- Wizard posture: no canonical built-in wizard component found in primary docs;
  pattern is to compose local step state/router state plus `form.Field`,
  `form.Subscribe`, `form.validateField`, and per-step schemas.
- YAML renderer fit: good low-level engine for a project-owned YAML renderer;
  not a schema renderer by itself.

### React Hook Form

- Project URL: https://react-hook-form.com and
  https://github.com/react-hook-form/react-hook-form
- Current package: `react-hook-form` 7.74.0.
- Release date: 2026-04-25 UTC from npm registry `time["7.74.0"]`.
- Version posture: npm `latest` is v7; npm `beta` is 8.0.0-beta.1, published
  2026-01-11 UTC. v8 exists but is not the default release line.
- Maintenance status: very active; package released the day before this research
  date and GitHub repo remains heavily used.
- Why people pick it in 2026: mature React default for uncontrolled inputs,
  small dependency footprint, broad ecosystem support, and a large resolver/UI
  integration surface.
- Field-state posture: hook-based API around `register`, `Controller`,
  `useWatch`, `useFieldArray`, `unregister`, and form state.
- Conditional UI posture: official `watch` docs say watch is useful for
  determining what to render conditionally; the docs include a checkbox that
  conditionally renders an age input. [C5]
- Large-form posture: official `useWatch` docs isolate rerendering at hook level
  and now include a `compute` selector for selective/computed subscriptions.
  [C6]
- Conditional removal posture: official `unregister` removes field ref and
  value, but does not remove schema validation; schemas must be adjusted when
  fields disappear. [C7]
- Wizard posture: official advanced docs recommend a state-management library to
  store input across pages/sections for wizard/funnel forms. [C8]
- Schema posture: use `@hookform/resolvers`; current package is 5.2.2, released
  2025-09-14 UTC. The resolver repo documents Valibot and Standard Schema
  support in addition to Zod and many older validators. [C9]
- YAML renderer fit: good if Humility wants conventional React field components
  and project-owned schema interpretation; RHF is not a schema renderer.
- Risk: conditional fields require policy decisions around `shouldUnregister`,
  explicit `unregister`, and schema pruning. That is manageable but not
  first-class declarative branching.

## Solid stack: candidate form libs

### TanStack Form for Solid

- Project URL: https://tanstack.com/form and https://github.com/TanStack/form
- Current package: `@tanstack/solid-form` 1.29.1.
- Release date: 2026-04-21 UTC from npm registry `time["1.29.1"]`.
- Maintenance status: active; same release train as `@tanstack/react-form`.
- Why people pick it in 2026: it brings the TanStack Form model to Solid with
  the same Standard Schema and cross-framework design.
- Field-state posture: Solid docs mirror the React validation guide, including
  form/field validation and Standard Schema examples. [C10]
- Schema posture: same Standard Schema model as React TanStack Form.
- Wizard posture: no built-in wizard; compose step state, route params, and
  per-step field subsets.
- Conditional posture: use Solid reactivity plus form subscription/store
  primitives; no YAML-style declarative condition interpreter exists in core.
- YAML renderer fit: good if the project wants one schema-to-renderer adapter
  with parallel React/Solid targets, but Solid-specific examples are less common
  than React examples.

### Modular Forms

- Project URL: https://modularforms.dev and
  https://github.com/fabian-hiller/modular-forms
- Current package: `@modular-forms/solid` 0.25.1.
- Release date: 2025-03-01 UTC from npm registry `time["0.25.1"]`.
- Maintenance status: slower release cadence; docs are live and the site is
  current, but the npm latest is more than a year old as of 2026-04-26.
- Why people pick it in 2026: Solid-native, signal-friendly, tiny, headless,
  and built by the Valibot author.
- Field-state posture: docs describe Modular Forms as state management and
  input validation; API is type-safe, headless, and signal-based. [C11]
- Schema posture: official Solid validation guide supports internal validators,
  Valibot, and Zod; it explicitly calls Valibot a good fit because both are
  modular. [C12]
- Type posture: docs use `v.InferInput<typeof LoginSchema>` for Valibot-driven
  form types. [C12]
- Dynamic fields posture: homepage calls out dynamic field arrays and deeply
  nested values. [C11]
- Wizard posture: no canonical built-in wizard found in primary docs; compose
  signals/router state and validate step-specific field groups.
- Conditional posture: hand-coded with Solid control flow and form state; no
  first-class declarative show-if DSL found in docs.
- YAML renderer fit: likely the most idiomatic Solid foundation for a
  Humility-owned YAML renderer.

### Felte

- Project URL: https://felte.dev and https://github.com/pablo-abc/felte
- Current packages: `felte` 1.3.0 and `@felte/solid` 1.2.14.
- Release dates: 2024-10-29 UTC for both current packages from npm registry.
- Maintenance status: usable and documented, but slower-moving than TanStack
  Form; current Solid adapter is about 18 months old as of 2026-04-26.
- Why people pick it in 2026: framework-neutral forms with plain HTML ergonomics
  and extensible validation/reporting.
- Field-state posture: Felte describes itself as an extensible form library for
  Svelte, Solid, and React. [C13]
- Schema posture: official site says it supports Yup, Zod, and Superstruct; no
  first-party Valibot or Standard Schema support found in primary docs. [C13]
- File value posture: API types include `File` and `File[]`, so native file
  fields are representable, but that is not a resumable upload system. [C14]
- Wizard posture: no canonical built-in wizard found in primary docs.
- Conditional posture: hand-coded via framework reactivity and stores.
- YAML renderer fit: acceptable for simple Solid forms, but weaker for 2026
  schema convergence than TanStack Form or Modular Forms.

## Schema validation (Zod / Valibot / Standard Schema)

- Standard Schema is now the convergence layer. Its repo defines a common
  interface for TypeScript validation libraries so ecosystem tools can accept
  validators without custom adapters. [C15]
- The Standard Schema implementer list includes Zod 3.24.0+, Valibot v1.0+,
  ArkType v2.0+, Effect Schema v3.13.0+, yup v1.7.0+, joi v18.0.0+, and more.
  [C15]
- `@standard-schema/spec` current package: 1.1.0, released 2025-12-15 UTC.
- Zod current package: 4.3.6, released 2026-01-22 UTC.
- Zod 4 docs position Zod 4 as the current major and document Zod Mini and Zod 4
  performance/type-system changes. [C16]
- Valibot current package: 1.3.1, released 2026-03-18 UTC.
- Valibot docs recommend accepting `StandardSchemaV1` when building libraries
  that accept user-defined schemas, unless Valibot-specific APIs are needed.
  [C17]
- TanStack Form has the cleanest direct Standard Schema integration among the
  field-state engines: pass the schema directly to validator slots. [C1]
- React Hook Form uses adapters/resolvers; `@hookform/resolvers` includes
  `standardSchemaResolver`, `zodResolver`, and `valibotResolver`. [C9]
- Modular Forms auto-derives form types only through the chosen schema library
  type helpers, for example Valibot `InferInput`; it is not a generic Standard
  Schema type-derivation layer in the current docs. [C12]
- For Humility YAML, recommended validation shape is:
  1. YAML parser normalizes fields/pages/conditions.
  2. Project code generates a Zod or Valibot schema for client and API use.
  3. Form engine consumes the schema via Standard Schema or resolver adapter.
  4. Conditional visibility prunes or marks inactive values before validation.

## Multi-step pattern

- React Hook Form official pattern: split pages/sections and persist values in
  a state store; final page submits accumulated data. [C8]
- TanStack Form canonical pattern: not a built-in wizard; use route/local step
  state, `form.Subscribe`, and step-specific validation/schema slices.
- Modular Forms canonical pattern: not a built-in wizard; use Solid route/signal
  state and validate each step's active field subset.
- Schema renderers:
  - RJSF supports object/array schemas and custom UI schema, but wizard UX is
    not the core abstraction. [C18]
  - JSON Forms has a UI schema layout model and rule-based visibility; it is
    closer to a full schema-renderer workflow. [C19]
- For Humility, multi-page YAML should stay in the project DSL. The form engine
  should be asked to manage fields, errors, dirty state, and submission, not to
  own the wizard model.

## Conditional fields

- React Hook Form: first-class primitives exist (`watch`, `useWatch`,
  `unregister`), but declarative show-if logic is hand-coded. [C5] [C6] [C7]
- TanStack Form: `form.Subscribe` directly supports showing/hiding UI based on
  field values, and `onDynamic` covers dynamic validation, but conditions are
  still implemented in app code. [C2] [C3]
- Modular Forms: no primary-doc first-class conditional DSL found; use Solid
  control flow with form values and validation rules.
- Felte: no primary-doc first-class conditional DSL found; use Solid stores and
  conditional rendering.
- RJSF: supports JSON Schema conditionals and dynamic `uiSchema` functions; docs
  show UI changing based on item data, including hidden widgets. [C20]
- JSON Forms: rule-based visibility/enablement is a first-class UI schema
  concept; the homepage demo shows a rule enabling an address group when
  `committer` is true. [C19]
- Humility YAML conditional logic should be represented explicitly, for example:
  `visible_if: { field: daily_events, includes: "PvP Events" }`.
- The renderer should define inactive-field semantics: either unregister/remove
  inactive values before validation, or preserve them as draft-only values and
  omit them from submit payloads.

## YAML / JSON-schema-driven renderers

### react-jsonschema-form (RJSF)

- Project URL: https://github.com/rjsf-team/react-jsonschema-form
- Current package: `@rjsf/core` 6.5.1.
- Release date: 2026-04-18 UTC from npm registry and GitHub latest release.
- Maintenance status: active; latest release 8 days before research date.
- Why people pick it in 2026: mature React JSON Schema renderer with many theme
  packages and AJV validation.
- Docs describe it as a React component that uses JSON Schema to declaratively
  build and customize web forms. [C18]
- Supported themes include Ant Design v5, Chakra UI v3, Daisy UI v5, Fluent UI
  v9, Mantine, Material UI v7, React-Bootstrap, Semantic UI, and Shad CN. [C18]
- UI polish layer: `uiSchema` exists because JSON Schema cannot describe enough
  rendering details; it controls widgets, descriptions, order, templates, and
  options. [C21]
- Conditional/dynamic UI: current docs include dynamic `uiSchema` functions.
  [C20]
- Fit for Humility YAML: strong if YAML is converted to JSON Schema plus
  uiSchema; weak if the project wants Solid.

### Formily

- Project URL: https://github.com/alibaba/formily
- Current package: `@formily/react` 2.3.7.
- Release date: 2025-05-15 UTC from npm registry; GitHub page shows v2.3.6 as
  latest release on the same date.
- Maintenance status: slower; still large and maintained, but current release is
  nearly a year old as of 2026-04-26.
- Why people pick it in 2026: enterprise-grade dynamic JSON Schema/form-builder
  system with data-linkage and low-code/no-code orientation.
- Repo describes dynamic JSON Schema forms, form builder, React/React Native/Vue
  support, independent field state, and side-effect/data-linkage support. [C22]
- Fit for Humility YAML: probably too heavy unless the product direction is a
  full internal form-builder/admin-builder.

### uniforms

- Project URL: https://uniforms.tools and https://github.com/vazco/uniforms
- Current package: `uniforms` 4.0.0.
- Release date: 2025-02-28 UTC from npm registry.
- Maintenance status: slower release cadence, but docs are current to 2026 and
  project is established.
- Why people pick it in 2026: React forms generated from schema bridges with
  strong customization and theme support.
- Docs state it is a React library for building forms from any schema and lists
  JSON Schema, GraphQL, SimpleSchema, SimpleSchema2, Zod, and custom schema
  support. [C23]
- Fit for Humility YAML: viable React renderer if the team wants schema bridges
  rather than direct field-engine control.

### JSON Forms

- Project URL: https://jsonforms.io and https://github.com/eclipsesource/jsonforms
- Current package: `@jsonforms/react` 3.7.0.
- Release date: 2025-11-27 UTC from npm registry `time["3.7.0"]`; npm package
  metadata was modified 2026-03-05 UTC, and the site says v3.7.0 is current.
- Maintenance status: active.
- Why people pick it in 2026: full JSON Schema plus UI schema renderer with
  data binding, validation, and rule-based visibility.
- Docs say JSON Forms declares forms as JSON based on JSON Schema and includes
  data-binding, validation, and rule-based visibility out of the box. [C19]
- Fit for Humility YAML: strongest off-the-shelf renderer model if staying in
  React and accepting JSON Schema/UI schema conversion.

## Accessibility primitives

### React

- Radix Form package: `@radix-ui/react-form` 0.1.8, released 2025-08-13 UTC.
- Radix Form docs: built on native constraint validation API, supports built-in
  and custom validation, accessible validation messages, client/server-side
  scenarios, and managed focus. [C24]
- Radix Form caveat: docs state it cannot currently compose Form with Radix's
  other form primitives such as Checkbox and Select. [C24]
- Ark UI React package: `@ark-ui/react` 5.36.2, released 2026-04-22 UTC.
- Ark UI Forms guide: Field and Fieldset integrate with native forms and popular
  form libraries including React Hook Form and TanStack Form. [C25]
- Ark UI docs: labels/helper text are automatically linked through ARIA
  description wiring. [C25]
- React choice: Ark UI Field/Fieldset is the more complete 2026 accessibility
  primitive for mixed controls; Radix Form is useful for native text/select
  flows but narrower.

### Solid

- Kobalte package: `@kobalte/core` 0.13.11, released 2025-07-26 UTC.
- Kobalte TextField docs: has label, input, description, error message, HTML
  form integration through `name`, and `validationState` for assistive
  technologies. [C27]
- Ark UI Solid package: `@ark-ui/solid` 5.36.2, released 2026-04-22 UTC.
- Ark UI forms guide is cross-framework and includes Solid examples in the same
  component system. [C25]
- Solid choice: Kobalte remains the established Solid ARIA primitive library;
  Ark UI is more active in 2026 and aligns with React/Solid parity.

## File upload

### Uppy

- Project URL: https://uppy.io and https://github.com/transloadit/uppy
- Current packages: `@uppy/core` 5.2.0, `@uppy/react` 5.2.0, `@uppy/tus` 5.1.1.
- Release dates: `@uppy/core` 5.2.0 published 2025-12-02 UTC;
  `@uppy/react` 5.2.0 and `@uppy/tus` 5.1.1 published 2026-02-03 UTC.
- Maintenance status: active; npm package metadata modified 2026-04-02 UTC and
  Uppy 5 docs are current.
- Why people pick it in 2026: battle-tested upload workflow with Dashboard,
  React components, headless hooks, drag/drop, remote sources, progress, retries,
  pause/resume, and tus resumable uploads.
- React docs: Uppy 5 React exposes Dashboard, DashboardModal, StatusBar,
  FilesList, FilesGrid, Dropzone, `useDropzone`, `useFileInput`, and reactive
  `useUppyState`. [C28]
- Dashboard docs: pause/resume controls are tied to resumable uploads such as
  tus and per-file status bar controls. [C29]
- Tus docs: supports chunk size, retry delays, endpoint/headers, concurrency
  limit, and resumable chunk recovery via tus-js-client. [C30]
- Solid fit: no first-party Solid adapter found; use vanilla Uppy Dashboard or
  headless Uppy core in a Solid wrapper.

### FilePond

- Project URL: https://pqina.nl/filepond and https://github.com/pqina/filepond
- Current package: `filepond` 4.32.12.
- Release date: 2026-03-02 UTC from npm registry.
- Maintenance status: active, with FilePond 5 beta also advertised on product
  page.
- Why people pick it in 2026: polished upload widget with multi-file UX,
  accessible keyboard support, previews, validation, image plugins, and chunked
  upload support.
- Product page: supports multiple file upload, drag/drop, reorder, previews,
  plugins, keyboard navigation, and AT testing with VoiceOver/JAWS. [C31]
- Server docs: chunk uploads use POST/PATCH/HEAD, resume by checking
  `Upload-Offset`, and allow user retry after chunk retry failure. [C32]
- React adapter: `react-filepond` 7.1.3 was last published 2024-12-16 UTC, so
  the core is more current than the React adapter.
- Solid fit: no official Solid adapter found; use vanilla FilePond or choose
  Uppy for cross-framework control.

### UploadThing

- Project URL: https://docs.uploadthing.com and
  https://github.com/pingdotgg/uploadthing
- Current package: `uploadthing` 7.7.4.
- Release date: 2025-08-17 UTC from npm registry.
- Maintenance status: active docs, but less directly aligned with arbitrary
  resumable, self-owned upload UX than Uppy/FilePond.
- Why people pick it in 2026: fastest path for type-safe uploads in full-stack
  TypeScript/React apps when using UploadThing infrastructure.
- Docs: React API strongly recommends generated type-safe components; upload
  docs describe resumable flows with `Range` header and v7 `createUpload`.
  [C33]
- Fit for Humility: good if adopting UploadThing service; less neutral if the
  project wants storage-provider independence.

## Citations

- [C1] TanStack Form React validation docs, accessed 2026-04-26: https://tanstack.com/form/v1/docs/framework/react/guides/validation
- [C2] TanStack Form React reactivity docs, accessed 2026-04-26: https://tanstack.com/form/v1/docs/framework/react/guides/reactivity
- [C3] TanStack Form React dynamic validation docs, accessed 2026-04-26: https://tanstack.com/form/v1/docs/framework/react/guides/dynamic-validation
- [C4] TanStack Form React listeners docs, accessed 2026-04-26: https://tanstack.com/form/v1/docs/framework/react/guides/listeners
- [C5] React Hook Form `watch` docs source, accessed 2026-04-26: https://github.com/react-hook-form/documentation/blob/master/src/content/docs/useform/watch.mdx
- [C6] React Hook Form `useWatch` docs source, accessed 2026-04-26: https://github.com/react-hook-form/documentation/blob/master/src/content/docs/usewatch.mdx
- [C7] React Hook Form `unregister` docs source, accessed 2026-04-26: https://github.com/react-hook-form/documentation/blob/master/src/content/docs/useform/unregister.mdx
- [C8] React Hook Form advanced usage docs source, accessed 2026-04-26: https://github.com/react-hook-form/documentation/blob/master/src/content/advanced-usage.mdx
- [C9] React Hook Form resolvers repo, accessed 2026-04-26: https://github.com/react-hook-form/resolvers
- [C10] TanStack Form Solid validation docs, accessed 2026-04-26:
  https://tanstack.com/form/v1/docs/framework/solid/guides/validation
- [C11] Modular Forms homepage, accessed 2026-04-26: https://modularforms.dev/
- [C12] Modular Forms Solid validation guide, accessed 2026-04-26: https://modularforms.dev/solid/guides/validate-your-fields
- [C13] Felte homepage, accessed 2026-04-26: https://felte.dev/
- [C14] Felte API TypeDoc, accessed 2026-04-26: https://api.felte.dev/modules.html
- [C15] Standard Schema repo, accessed 2026-04-26: https://github.com/standard-schema/standard-schema
- [C16] Zod 4 release notes, accessed 2026-04-26: https://zod.dev/v4
- [C17] Valibot integration guide, accessed 2026-04-26: https://valibot.dev/guides/integrate-valibot/
- [C18] RJSF repo README, accessed 2026-04-26: https://github.com/rjsf-team/react-jsonschema-form
- [C19] JSON Forms homepage, accessed 2026-04-26: https://jsonforms.io/
- [C20] RJSF dynamic uiSchema docs, accessed 2026-04-26: https://rjsf-team.github.io/react-jsonschema-form/docs/api-reference/dynamic-ui-schema-examples/
- [C21] RJSF uiSchema docs, accessed 2026-04-26: https://rjsf-team.github.io/react-jsonschema-form/docs/api-reference/uiSchema/
- [C22] Formily repo README, accessed 2026-04-26: https://github.com/alibaba/formily
- [C23] uniforms homepage, accessed 2026-04-26: https://uniforms.tools/
- [C24] Radix Form docs, accessed 2026-04-26: https://www.radix-ui.com/primitives/docs/components/form
- [C25] Ark UI Forms guide, accessed 2026-04-26: https://ark-ui.com/docs/guides/forms
- [C27] Kobalte TextField docs, accessed 2026-04-26: https://kobalte.dev/docs/core/components/text-field/
- [C28] Uppy React docs, accessed 2026-04-26: https://uppy.io/docs/react/
- [C29] Uppy Dashboard docs, accessed 2026-04-26: https://uppy.io/docs/dashboard/
- [C30] Uppy Tus docs, accessed 2026-04-26: https://uppy.io/docs/tus/
- [C31] FilePond product page, accessed 2026-04-26: https://pqina.nl/filepond/
- [C32] FilePond server docs, accessed 2026-04-26: https://pqina.nl/filepond/docs/api/server/
- [C33] UploadThing docs, accessed 2026-04-26: https://docs.uploadthing.com/api-reference/react and https://docs.uploadthing.com/uploading-files
- [C34] npm registry package metadata queried 2026-04-26 for current versions and publish dates: https://registry.npmjs.org/
