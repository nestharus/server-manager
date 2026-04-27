# Sub-Question C — Toolchain findings

Date basis: 2026-04-26. Scope: verify the named JS/TS frontend stack, what
each tool replaces, production status, caveats, and Solid/React wiring.

## Oxlint

- Real: yes. Oxlint is the Oxc project's JS/TS linter.
- Replaces: ESLint for JavaScript/TypeScript linting.
- Current npm latest observed: `oxlint@1.61.0`.
- Latest npm publish timestamp observed: 2026-04-20T20:01:24.976Z.
- Package description: "Linter for the JavaScript Oxidation Compiler."
- Status: 1.x, actively maintained, production-used.
- Production-grade: yes for normal JS/TS linting, CI, and large repos.
- Caveat: not every ESLint rule/plugin/custom parser is at parity.
- Oxc docs say Oxlint is built for large repositories and CI.
- Oxc docs claim 50-100x ESLint benchmark speed.
- Rule coverage: Oxc docs say more than 720 built-in rules.
- Coverage includes ESLint core, TypeScript, React, Jest, Vitest, Import,
  Unicorn, jsx-a11y, and Oxc-specific rules.
- Migration docs say most ESLint core and popular plugin rules are supported.
- Migration docs also warn some rules may not yet be available.
- Supported files: `.js`, `.mjs`, `.cjs`, `.ts`, `.mts`, `.cts`, `.jsx`,
  `.tsx`.
- Framework files: `.vue`, `.svelte`, `.astro` are linted for script blocks.
- Monorepo support: explicit large-repo design plus multi-file analysis.
- Multi-file analysis builds a project-wide module graph in the core engine.
- `import/*` rules can discover `tsconfig.json` path aliases.
- Type-aware linting is integrated through `tsgolint`.
- `oxlint-tsgolint@0.22.0` latest observed; published 2026-04-25T09:41:04Z.
- Type-aware coverage: docs say 59 of 61 type-aware `typescript-eslint` rules.
- Type-aware command: `oxlint --type-aware`.
- Type-check command: `oxlint --type-aware --type-check`.
- Docs say `--type-check` can replace a separate `tsc --noEmit` step.
- Type-aware caveat: build monorepo dependencies first so `.d.ts` files exist.
- Config caveat: `options.typeAware` and `options.typeCheck` are root-only.
- JS plugins: real, ESLint v9-compatible, but alpha.
- JS plugin docs say almost the whole ESLint plugin API is implemented.
- JS plugin docs list supported traversal, fixes, options, selectors,
  `SourceCode`, scope, control flow, disable comments, LSP diagnostics/fixes.
- JS plugin gaps: custom parsers/file formats and type-aware JS plugin rules.
- Built-in plugin list includes `eslint`, `typescript`, `unicorn`, `react`,
  `react-perf`, `nextjs`, `oxc`, `import`, `jsdoc`, `jsx-a11y`, `node`,
  `promise`, `jest`, `vitest`, `vue`.
- Editor support: official Oxc extension supports VS Code/Cursor, Zed,
  JetBrains, Neovim, and generic LSP editors.
- Editor implementation uses local `oxlint --lsp`.

Basic wiring:

```json
{
  "scripts": {
    "lint": "oxlint",
    "lint:fix": "oxlint --fix",
    "lint:type": "oxlint --type-aware --type-check"
  },
  "devDependencies": {
    "oxlint": "1.61.0",
    "oxlint-tsgolint": "0.22.0"
  }
}
```

VS Code wiring:

```json
{
  "recommendations": ["oxc.oxc-vscode"],
  "editor.codeActionsOnSave": {
    "source.fixAll.oxc": "always"
  }
}
```

## Oxfmt

- Real: yes. Oxfmt is the Oxc formatter.
- Replaces: Prettier.
- Current npm latest observed: `oxfmt@0.46.0`.
- Latest npm publish timestamp observed: 2026-04-20T19:47:21.818Z.
- Package description: "Formatter for the JavaScript Oxidation Compiler."
- Status: beta, not GA/1.0.
- Production-grade: production-adopted beta; not GA in strict version terms.
- Oxc announced Oxfmt beta on 2026-02-24.
- Beta post lists adoption by Vue core, Turborepo, Sentry JavaScript,
  Hugging Face JS, and others.
- Supported languages: JS, JSX, TS, TSX, JSON, JSONC, JSON5, YAML, TOML, HTML,
  Angular, Vue, CSS, SCSS, Less, Markdown, MDX, GraphQL, Ember, Handlebars.
- Docs say Oxfmt passes 100% of Prettier's JS/TS conformance tests.
- Docs say formatting differences from recent Prettier should be bugs.
- Caveat: Prettier plugins are not supported directly.
- Built-in replacements for common plugins: import sorting, Tailwind class
  sorting, package.json sorting, embedded formatting.
- Config files: `.oxfmtrc.json`, `.oxfmtrc.jsonc`, `oxfmt.config.ts`.
- Nested configs are supported; nearest config wins.
- Common options include `printWidth`, `tabWidth`, `useTabs`, `semi`,
  `singleQuote`, `trailingComma`, `ignorePatterns`, `sortImports`,
  `sortTailwindcss`, `sortPackageJson`.
- Default difference: Oxfmt `printWidth` is 100; Prettier default is 80.
- Editor support follows Oxc editor integrations.

Basic wiring:

```json
{
  "scripts": {
    "fmt": "oxfmt --write .",
    "fmt:check": "oxfmt --check ."
  },
  "devDependencies": {
    "oxfmt": "0.46.0"
  }
}
```

Prettier migration:

```bash
pnpm add -D oxfmt@latest
pnpm oxfmt --migrate prettier
pnpm oxfmt
```

Prettier-like width:

```jsonc
{
  "$schema": "./node_modules/oxfmt/configuration_schema.json",
  "printWidth": 80
}
```

## tsgo

- Real: yes.
- Repository: `microsoft/typescript-go`.
- npm preview package: `@typescript/native-preview`.
- CLI binary: `tsgo`.
- Current npm latest observed: `@typescript/native-preview@7.0.0-dev.20260426.1`.
- npm `beta` tag observed: `7.0.0-dev.20260421.2`.
- Observed CLI versions match those package versions.
- Replaces: eventually `tsc`/TypeScript language service; today selected
  `tsc` workflows.
- Status: TypeScript 7.0 Beta, not GA.
- Microsoft says TypeScript 7.0 ports the TypeScript codebase to Go.
- Microsoft says it is often about 10x faster than TypeScript 6.0.
- Microsoft says type-checking logic is structurally identical to TS 6.0.
- Microsoft says the beta is ready for daily workflows and CI pipelines.
- Production-grade: production-suitable beta for type checking/build validation;
  not final GA.
- Programmatic API caveat: stable API expected no earlier than TS 7.1.
- Future plan: package becomes `typescript`; binary becomes `tsc`.
- README status: program creation, parsing/scanning, command line/tsconfig,
  type resolution, type checking, JSX, JS emit, build mode/project references,
  and incremental build are marked done.
- README caveats: JSDoc/JS inference in progress; declaration emit incomplete
  for JavaScript files; watch mode prototype with no incremental rechecking;
  language service in progress; API not ready.
- CLI parity conclusion: much stronger than 2025 previews, but not universal
  for tools importing TypeScript's JS API.
- IDE integration: VS Code Native Preview extension.
- Microsoft 2026 beta post says editor support is stable and LSP-based.

Install/use:

```bash
pnpm add -D @typescript/native-preview@latest
pnpm tsgo --noEmit
pnpm tsgo --build
```

VS Code:

```json
{
  "js/ts.experimental.useTsgo": true
}
```

Adoption recommendation: keep TS 6 available for tools that import
`typescript`; add pinned `tsgo` as a fast CI/type-check lane before making it
the only checker.

## @nkzw/oxlint-config

- Real: yes.
- Current npm latest observed: `@nkzw/oxlint-config@1.1.1`.
- Latest npm publish timestamp observed: 2026-04-20T00:03:46.799Z.
- Package description: "Oxlint config with sensible defaults."
- Author in package metadata: Christoph Nakazawa.
- Repository: `github.com/nkzw-tech/oxlint-config`.
- Replaces: local Oxlint rule setup, not Oxlint itself.
- Peer dependency: `oxlint >=1.46.0`.
- README says direct JS plugin installs are required due to an Oxlint resolver
  limitation.
- README philosophy: errors instead of warnings, strict consistency, bug
  prevention, avoid slow rules, avoid subjective rules, prefer autofix.
- README says use with TypeScript `noUnusedLocals` and Oxfmt.
- Dependencies: `@nkzw/eslint-plugin`, `eslint-plugin-no-only-tests`,
  `eslint-plugin-perfectionist`, `eslint-plugin-react-hooks`,
  `eslint-plugin-unused-imports`.
- Actual config enables JS plugins for NKZW, no-only-tests, Perfectionist,
  unused-imports, and aliased React Hooks as `react-hooks-js`.
- Actual config enables built-in Oxlint plugins: `typescript`, `import`,
  `react`, `unicorn`.
- Actual config disables category defaults and enumerates explicit errors.
- Rule families: ESLint correctness, TypeScript, import, React, React Hooks,
  React Compiler-oriented hooks rules, Unicorn, Perfectionist, unused imports,
  no-only-tests, and NKZW custom rules.
- NKZW custom rules include `@nkzw/no-instanceof`,
  `@nkzw/ensure-relay-types`, `@nkzw/require-use-effect-arguments`.
- React Compiler lint coverage appears through `react-hooks-js/config`,
  `gating`, `immutability`, `incompatible-library`, `purity`, `refs`,
  `set-state-in-effect`, `set-state-in-render`, `unsupported-syntax`,
  `use-memo`, and related rules.

Wiring:

```bash
pnpm add -D oxlint @nkzw/oxlint-config @nkzw/eslint-plugin \
  eslint-plugin-no-only-tests eslint-plugin-perfectionist \
  eslint-plugin-react-hooks eslint-plugin-unused-imports
```

```ts
import nkzw from "@nkzw/oxlint-config";
import { defineConfig } from "oxlint";

export default defineConfig({
  extends: [nkzw],
});
```

## React Compiler (current GA state)

- Real: yes.
- Current npm latest observed: `babel-plugin-react-compiler@1.0.0`.
- npm metadata modified timestamp observed: 2026-04-24T16:31:48.761Z.
- Replaces: most manual memoization with `useMemo`, `useCallback`,
  `React.memo`.
- Does not replace React, a bundler, or all performance work.
- GA status: stable since React Compiler v1.0 on 2025-10-07.
- React blog says Compiler 1.0 is fully production-ready.
- React blog says it works on React and React Native.
- Mechanism: build-time automatic memoization for components/hooks.
- Implementation: currently a Babel plugin.
- Architecture: compiler lowers Babel AST to its own HIR and performs
  data-flow/mutability analysis.
- Docs say optimized components show a "Memo" badge in React DevTools.
- Best with React 19; supports React 17/18 with `target` plus
  `react-compiler-runtime`.
- Current `react-compiler-runtime` latest observed: `1.0.0`.
- Required lint companion: `eslint-plugin-react-hooks`, not the old
  `eslint-plugin-react-compiler`.
- Current `eslint-plugin-react-hooks` latest observed: `7.1.1`.
- React blog says compiler lint rules ship in `eslint-plugin-react-hooks`
  recommended presets.
- Lint behavior: compiler skips violating components/hooks and keeps optimizing
  the rest.
- Escape hatch: `"use no memo"` at function or file top.
- Opt-in annotation path: `"use memo"` plus `compilationMode: "annotation"`.
- Config controls include `compilationMode`, `target`, `panicThreshold`,
  `logger`, `gating`.
- Docs recommend `panicThreshold: "none"` for production skipping instead of
  build failure.
- Upgrade caveat: exact-pin if test coverage is weak because memoization
  changes can expose latent Rules of React violations.
- Vite docs still show `@vitejs/plugin-react` Babel config.
- Vite 8 / `@vitejs/plugin-react@6` changed this: official release notes say
  Babel-related features were removed because React Refresh is handled by Oxc.
- For Vite 8/plugin-react 6, release notes recommend
  `@rolldown/plugin-babel` plus `reactCompilerPreset()`.
- Current observed versions: `vite@8.0.10`, `@vitejs/plugin-react@6.0.1`,
  `@vitejs/plugin-react-swc@4.3.0`.
- SWC support: React blog calls it experimental.
- Oxc/native support: React blog says React is working with Oxc; docs will be
  updated when supported.

Vite 8 wiring:

```bash
pnpm add -D @vitejs/plugin-react @rolldown/plugin-babel \
  babel-plugin-react-compiler eslint-plugin-react-hooks
```

```ts
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
});
```

## Async React (what it actually means in 2026)

- "Async React" is real conference vocabulary, not a single package.
- React Conf 2025 recap lists "Async React Part I" and "Part II".
- Practical 2026 cluster: Suspense, `use()`, async Actions/transitions,
  `cache()`, `cacheSignal()`, `<Activity>`, and `<ViewTransition>`.
- `use()` is stable; it reads a Promise or context and integrates with
  Suspense/Error Boundaries for Promises.
- `use()` can be called in loops/conditionals unlike normal Hooks.
- Server Component caveat: docs prefer `async`/`await` over `use` for fetching.
- Suspense is stable; it shows fallback until child code/data is ready.
- Suspense-enabled data sources include frameworks like Relay/Next.js, `lazy`,
  and reading a cached Promise with `use`.
- Suspense caveat: building a Suspense data source without a framework remains
  unstable/undocumented.
- React 19 added async functions in transitions for pending states, errors,
  forms, and optimistic updates.
- `cache()` is official for React Server Components.
- `cacheSignal()` is official for React Server Components and returns an
  AbortSignal for cache-lifetime cancellation.
- `<Activity>` shipped in React 19.2.
- Current observed React latest: `react@19.2.5`, `react-dom@19.2.5`.
- Activity use cases: hide/show/prioritize UI, preserve hidden state,
  pre-render likely next UI, background-load data/CSS/images.
- `<ViewTransition>` is not stable as of 2026-04-26.
- React Labs says `<ViewTransition>` and `addTransitionType` are canary-only.
- Current observed React canary: `19.3.0-canary-561ed529-20260423`.
- ViewTransition integrates React updates with browser View Transitions.
- ViewTransition triggers include transitions, deferred values, and Suspense.
- Async React production conclusion: Suspense/use/Actions/cache/Activity are
  production APIs where applicable; ViewTransition remains canary.

## How they wire together for a Solid SPA project (note: Oxc/Oxlint are
   framework-agnostic; React Compiler obviously not — but the user mentioned
   both Solid and React-fork interest, so cover both wiring stories)

- Solid SPA baseline: Oxfmt for formatting, Oxlint for linting, tsgo for fast
  TS checking after parity verification.
- Solid build remains Vite + Solid plugin; React Compiler does not apply.
- Oxc/Oxlint are framework-agnostic for JS/TS and work with TSX.
- NKZW preset caveat: it includes React/React Hooks rules, so it is not a clean
  Solid-only preset without overrides.
- Better Solid choice: raw Oxlint config or a Solid-specific preset, plus Oxfmt.

Solid package skeleton:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "fmt": "oxfmt --write .",
    "fmt:check": "oxfmt --check .",
    "lint": "oxlint",
    "typecheck": "tsgo --noEmit"
  },
  "devDependencies": {
    "@typescript/native-preview": "7.0.0-dev.20260426.1",
    "oxfmt": "0.46.0",
    "oxlint": "1.61.0",
    "typescript": "npm:@typescript/typescript6@^6.0.0"
  }
}
```

Solid-oriented Oxlint config:

```ts
import { defineConfig } from "oxlint";

export default defineConfig({
  plugins: ["typescript", "import", "unicorn", "oxc"],
  options: { typeAware: true },
  rules: {
    "no-console": "error",
    "import/no-cycle": ["error", { maxDepth: 3 }],
  },
});
```

React fork/story:

- Add React Compiler only to React packages.
- Use `@vitejs/plugin-react` + `@rolldown/plugin-babel` +
  `reactCompilerPreset()` for Vite 8/plugin-react 6.
- Use `eslint-plugin-react-hooks@7.1.1` directly or via Oxlint JS plugins/NKZW.
- React 19 can use default compiler config.
- React 17/18 need `react-compiler-runtime` and `target: "17"` or `"18"`.
- React Async APIs belong only in React code; Solid has separate async/data
  primitives.
- CI order: `pnpm fmt:check`, `pnpm lint`, `pnpm typecheck`, `pnpm build`.
- Adoption path: Oxfmt after one formatting commit; Oxlint after rule/plugin
  parity check; tsgo as pinned fast lane before sole checker; React Compiler
  only after compiler lint is clean enough in React packages.
## Citations

- Oxlint: https://oxc.rs/docs/guide/usage/linter.html; https://oxc.rs/docs/guide/usage/linter/migrate-from-eslint; https://oxc.rs/docs/guide/usage/linter/plugins.html; https://oxc.rs/docs/guide/usage/linter/js-plugins; https://oxc.rs/docs/guide/usage/linter/type-aware; https://oxc.rs/docs/guide/usage/linter/multi-file-analysis; https://oxc.rs/docs/guide/usage/linter/editors
- Oxfmt: https://oxc.rs/docs/guide/usage/formatter.html; https://oxc.rs/docs/guide/usage/formatter/config.html; https://oxc.rs/docs/guide/usage/formatter/migrate-from-prettier; https://oxc.rs/blog/2026-02-24-oxfmt-beta
- Oxc parser/transformer/resolver: https://oxc.rs/; https://oxc.rs/docs/guide/usage/transformer.html; https://github.com/oxc-project/oxc-resolver
- tsgo: https://devblogs.microsoft.com/typescript/announcing-typescript-7-0-beta/; https://devblogs.microsoft.com/typescript/announcing-typescript-native-previews/; https://github.com/microsoft/typescript-go
- React Compiler: https://react.dev/blog/2025/10/07/react-compiler-1; https://react.dev/learn/react-compiler; https://react.dev/learn/react-compiler/installation; https://react.dev/reference/react-compiler/configuration; https://react.dev/reference/react-compiler/directives/use-no-memo; https://react.dev/reference/react-compiler/compiling-libraries
- Vite React plugin: https://github.com/vitejs/vite-plugin-react/releases
- Async React/API docs: https://react.dev/blog/2024/12/05/react-19; https://react.dev/blog/2025/10/01/react-19-2; https://react.dev/blog/2025/04/23/react-labs-view-transitions-activity-and-more; https://react.dev/blog/2025/10/16/react-conf-2025-recap; https://react.dev/reference/react/use; https://react.dev/reference/react/cache; https://react.dev/reference/react/cacheSignal; https://react.dev/reference/react/Suspense; https://react.dev/reference/react/Activity; https://react.dev/reference/react/ViewTransition
- npm registry packages: https://registry.npmjs.org/oxlint; https://registry.npmjs.org/oxfmt; https://registry.npmjs.org/oxlint-tsgolint; https://registry.npmjs.org/@typescript/native-preview; https://registry.npmjs.org/@nkzw/oxlint-config; https://registry.npmjs.org/babel-plugin-react-compiler; https://registry.npmjs.org/react-compiler-runtime; https://registry.npmjs.org/eslint-plugin-react-hooks; https://registry.npmjs.org/vite; https://registry.npmjs.org/@vitejs/plugin-react; https://registry.npmjs.org/react
