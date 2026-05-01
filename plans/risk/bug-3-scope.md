# BUG-3 — Scope risk gate

**Verdict:** LOW

BUG-3 stops CodeRabbit from re-emitting Solid 1 / stable false positives
against this repo's pinned Solid 2 beta install
(`solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`,
`@solidjs/signals@2.0.0-beta.8` per
`services/web/package.json:23, 33`). The RCA's evidence (eight beta-i/ii
review rounds repeating the same `For` accessor claim, plus parallel
`@solidjs/web`, `createContext.Provider`, and `Show` accessor patterns —
`research/32-bug-3-coderabbit-foraccessor-rca.md` §"Symptom Catalog"
Patterns 1-8) shows the recurrence is a missing-context problem, not a
source-code defect. The proposal locks one mechanism (a repository-root
`.coderabbit.yaml` with one `reviews.path_instructions` entry scoped to
`services/web/**`) and limits substrate to two new files with no
modified files (`proposals/19-bug-3-coderabbit-solid2-context.md` §2
Q1-Q6, §3, §5). Diff budget about 95-165 added lines, no runtime code,
no test code, no lockfile churn (§6).

## Gate checks

### 1. Only adds `.coderabbit.yaml` (and possibly a baseline file)

**PASS.** §3 "New files" enumerates exactly two paths:

- `.coderabbit.yaml` — repository-root CodeRabbit config with the
  Q4-locked Solid 2 beta instruction bullets under one
  `reviews.path_instructions` entry for `services/web/**`.
- `docs/coderabbit-solid2-false-positive-baseline.md` — tracked
  baseline of the five canonical false-positive families
  (For accessors, Show accessors, `@solidjs/web`, `createContext`
  shape, legacy effect arity), used by future review runs to detect
  regressions.

§3 "Modified files: None." The optional second file is the
"baseline file" the gate criteria explicitly sanctions
("possibly a baseline file"); it is documentation only and does
not alter reviewer behavior on its own. §3 also forecloses a
hookpoint surprise: "The eventual implementation should only add
the two files above unless hookpoint research finds an
already-existing repository-level CodeRabbit config in another
branch that must be merged" — a merge-aware caveat, not a scope
expansion. ✅

### 2. No source code changes

**PASS.** §3 "Modified files: None." §5 anti-scope is explicit:

- "Do not change Solid package versions."
- "Do not change `services/web/src/solid-compat/solid.ts`."
- "Do not change web route code to satisfy Solid 1/stable assumptions."

The four affected surfaces named in the RCA
(`ApplicationQueueRoute.tsx`, `ApplicationDetailRoute.tsx`,
`ApplicationTransitionActions.tsx`, `solid-compat/solid.ts`,
`tests/solid-compat.spec.ts`, `tsconfig.json`, `vite.config.ts` —
RCA §"Affected Surfaces") are all left untouched. The fix shifts
context into CodeRabbit's own config file rather than reshaping the
code being reviewed. The substrate is YAML configuration plus a
markdown baseline document; no `.ts`, `.tsx`, or `.spec.*` files
are added or modified.

§5 also explicitly bans `@coderabbitai ignore` source-comment
patterns and `@coderabbitai ignore` PR-description controls, which
are the only alternatives that would have required editing source
files or changing review-loop semantics. ✅

### 3. No version bumps to Solid, CodeRabbit, or any tool

**PASS.** §5 anti-scope: "Do not bump CodeRabbit CLI or service
configuration versions" and "Do not change Solid package versions."

The fix sits in CodeRabbit's repository-config substrate, not in
package versioning. `services/web/package.json` versions of
`solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`, and
`@solidjs/signals@2.0.0-beta.8` are unchanged (they are the
intentional install — the whole point is to make CodeRabbit
review against them rather than against stable docs). No
`package-lock.json` or other lockfile churn from this fix.

CodeRabbit's CLI is invoked with the same command shape today
(`coderabbit review --plain --base main --cwd <project-dir>` per
`AGENTS.md:155-171` and TG-1 acceptance), and the proposal does not
upgrade it. The `# yaml-language-server: $schema=...schema.v2.json`
header in §3's skeleton pins the existing CodeRabbit YAML schema
version that is already in use in the documented examples; it is
not a bump. ✅

### 4. No CI/CD pipeline changes beyond what CodeRabbit reads

**PASS.** §3 "Modified files: None." The only file added at the
repository root is `.coderabbit.yaml` itself, which is exactly
"what CodeRabbit reads" — the documented configuration substrate
(<https://docs.coderabbit.ai/reference/configuration>, also
recorded in the RCA's "Repository YAML surface" audit).

The proposal does not touch:

- GitHub Actions workflows or any other CI YAML.
- `AGENTS.md` (the documented review-loop spec) — §5 anti-scope:
  "Do not edit `AGENTS.md` for Solid 2 beta context in this
  proposal."
- The CodeRabbit review-loop invocation. §5 anti-scope: "Do not …
  custom pre-merge checks." TG-1 reuses the existing review
  command; no new flag or `--config <file>` is added to the loop.
- PR templates, branch protection, required-status-check
  configuration, or auto-review labels.
- The CLI installation path or version pin.

§5 also rules out two reviewer-context mechanisms that would have
expanded CI surface: AST-grep instructions
("Do not add lint rules, AST-grep instructions, or custom
pre-merge checks") and `@coderabbitai ignore` PR-description
controls ("Do not add `@coderabbitai ignore` to PR descriptions
as the BUG-3 fix"). The proposal locks `reviews.path_instructions`
exclusively, the documented in-config knob — no out-of-config CI
plumbing. ✅

### 5. No new abstraction or framework choice

**PASS.** The fix is configuration text, not code. There is no
new module, no new helper, no new framework, and no API surface
introduced. The Q4-locked instruction body is a markdown bullet
list inside a YAML `|` block scalar — the documented
`reviews.path_instructions[].instructions` substrate per
CodeRabbit's configuration reference (RCA "Repository YAML
surface").

§2 Q3 explicitly chooses markdown bullets inside a YAML block
scalar over alternative formats so the project does not
introduce a new escaped-string convention. §2 Q1 chooses
`.coderabbit.yaml` over an `AGENTS.md` section so the project
does not entangle review-runtime config with human/agent
workflow policy.

§5 anti-scope rules out the abstraction/framework alternatives
that were on the table:

- "Do not add lint rules, AST-grep instructions, or custom
  pre-merge checks." — rules out a structural review framework.
- "Do not add `@coderabbitai ignore` scattered through source
  code." — rules out a per-call-site suppression abstraction.
- "Do not add `@coderabbitai ignore` to PR descriptions as the
  BUG-3 fix." — rules out a PR-level toggle abstraction.

§2 Q5 ("rely solely on `reviews.path_instructions`; do not add
`@coderabbitai ignore` to source call sites") and §2 Q6
(CodeRabbit Knowledge Base learnings deferred — "not part of the
locked implementation scope for BUG-3") narrow the proposal to
exactly one mechanism: documented YAML path instructions. No
parallel mechanism, no fallback branch, no feature flag, no
"abstraction layer" over CodeRabbit. ✅

## In scope (justified)

- **Single `reviews.path_instructions` entry scoped to
  `services/web/**`** — the documented mechanism for path-scoped
  review guidance per CodeRabbit's configuration reference (RCA
  "Repository YAML surface"). §2 Q2 locks the scope so API,
  Discord daemon, migration, infra, and product-strategy
  documents do not inherit Solid-specific review assumptions.
- **Q4-locked instruction bullets covering the five canonical
  false-positive families** — `For` accessors, `Show` accessors,
  `@solidjs/web` SSR import, `createContext` callable provider
  shape, legacy effect handler arity. The bullet body names the
  exact installed beta versions
  (`solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`,
  `@solidjs/signals@2.0.0-beta.8`) so the reviewer prefers
  installed package types over stable public Solid docs.
- **`docs/coderabbit-solid2-false-positive-baseline.md` baseline
  file** — explicitly sanctioned by the gate criteria. §4 TG-2
  acceptance compares TG-1 review output against this baseline
  so future regressions are visible without rereading every
  historical `.tmp/**/coderabbit*.log` from
  `init-133B-i`, `init-133B-ii`, `init-133B-iii`, and
  `bug-1-admin-timeout`.
- **TG-1 representative CodeRabbit rerun** using the same
  `coderabbit review --plain --base main --cwd <project-dir>`
  invocation already documented in `AGENTS.md`. No new CLI flag,
  no new `--config <file>`, no new harness.

## Out of scope (deferred / explicit anti-scope §5)

- **`@coderabbitai ignore` scattered through source code** —
  explicitly banned. Source comments already failed to stop the
  recurrence (`tests/solid-compat.spec.ts:1-4` warning still
  triggered BUG-1 r6 at
  `.tmp/bug-1-admin-timeout/phase7/coderabbit-r6.log:19-26`).
- **`@coderabbitai ignore` in PR descriptions as the BUG-3 fix**
  — explicitly banned. That command disables review entirely,
  which would hide real findings in the same files.
- **CodeRabbit CLI / service configuration version bumps** —
  explicitly banned. The fix runs against the existing CLI.
- **Lint rules, AST-grep instructions, custom pre-merge checks**
  — explicitly banned. Path instructions are the locked
  mechanism.
- **Solid package version changes** — explicitly banned. The
  pinned beta versions are intentional; the bug is review
  context, not framework choice.
- **`services/web/src/solid-compat/solid.ts` changes** —
  explicitly banned. The compat shim is intentionally Solid 1-
  shape on the outside; the false positive about `.Provider`
  being incorrect was the reviewer misreading the shim, not the
  shim being wrong.
- **Web route code changes to satisfy Solid 1/stable assumptions**
  — explicitly banned. The accessors in `ApplicationQueueRoute`,
  `ApplicationDetailRoute`, and `ApplicationTransitionActions`
  match the installed Solid 2 beta `For`/`Show` types in
  `services/web/node_modules/solid-js/types/client/flow.d.ts`.
- **`AGENTS.md` Solid 2 beta context section** — explicitly
  out of scope for this proposal. The locked surface is
  `.coderabbit.yaml`, not the agent-workflow document.
- **Knowledge-base learnings via CodeRabbit chat / UI** — §2 Q6
  defers these to a possible operational follow-up only if TG-1
  still shows the canonical patterns after this config lands.
  Not part of the BUG-3 implementation diff.

## Risk surface

| Area | Pre | Post (BUG-3) | Justification |
|---|---|---|---|
| Modified source files | — | None | §3 "Modified files: None" |
| New source files | — | None | The fix is config + docs only |
| New repo-root files | None CodeRabbit-related | `.coderabbit.yaml` (about 25-45 lines) | §3 New files |
| New docs files | — | `docs/coderabbit-solid2-false-positive-baseline.md` (about 70-120 lines) | §3 New files |
| Modified test files | — | None | §3 "Modified files: None"; TG-1 reuses existing review loop |
| Package versions | `solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`, `@solidjs/signals@2.0.0-beta.8` | Identical | §5 explicitly bans Solid version changes |
| `node_modules` content | upstream releases | Identical | No package or lockfile change |
| CodeRabbit CLI version | Currently installed | Identical | §5 explicitly bans bumps |
| CodeRabbit invocation | `coderabbit review --plain --base main --cwd <project-dir>` per `AGENTS.md:155-171` | Identical | TG-1 reuses the same command; no `--config <file>` added |
| AGENTS.md | Review-loop instructions only, no Solid 2 beta context | Identical | §5 "Do not edit `AGENTS.md` for Solid 2 beta context in this proposal" |
| `services/web/src/solid-compat/solid.ts` | Solid 1-style `.Provider` wrapper around Solid 2 beta callable provider (lines 16-20) | Identical | §5 explicitly bans changes to this file |
| `services/web/src/features/officer/ApplicationQueueRoute.tsx` | `For` accessors `state()` and `application()` (lines 154-165, 185-221) | Identical | §5 explicitly bans web route code changes |
| `services/web/src/features/officer/ApplicationDetailRoute.tsx` | `For` over metadata rows, response tuples, transcript entries (`row()[0]`, `entry()[0]`) | Identical | §5 explicitly bans web route code changes |
| `services/web/src/features/officer/ApplicationTransitionActions.tsx` | `For` over transition actions using `action()` (lines 103-119) | Identical | §5 explicitly bans web route code changes |
| `services/web/tests/solid-compat.spec.ts` | `@solidjs/web` `renderToString` import + warning comment (lines 1-4) | Identical | §3 "Modified files: None" |
| `services/web/tsconfig.json`, `services/web/vite.config.ts` | Compat aliases | Identical | Not in §3 modified files |
| GitHub Actions / CI workflows | Existing | Identical | No CI YAML change |
| PR templates / branch protection / required checks | Existing | Identical | No CI surface change |
| Auto-review labels, `@coderabbitai pause`, `@coderabbitai resume`, `@coderabbitai review` flow | Existing | Identical | §5 anti-scope on `@coderabbitai ignore` and CLI bumps; auto-review eligibility unchanged |
| CodeRabbit Knowledge Base learnings | None seeded by repo | Identical (deferred per §2 Q6) | Not part of BUG-3 implementation scope |
| API service, Discord daemon, Alembic migrations, GitOps templates, Pomerium, Authentik | Existing | Identical | §2 Q2 path scope `services/web/**`; §3 "Modified files: None" |
| Diff budget | — | About 95-165 added lines, 2 new files, 0 modified files | §6 self-policed |

## Splittable concerns

- **`.coderabbit.yaml` and the baseline document are not splittable.**
  §4 TG-2 acceptance depends on the baseline existing before
  TG-1 reruns CodeRabbit, so the baseline cannot be deferred
  without breaking the regression-detection contract. They are
  also tiny enough that splitting would not materially shrink
  diff size — the larger of the two files
  (`docs/coderabbit-solid2-false-positive-baseline.md`,
  about 70-120 lines) is still well under any single-PR threshold.
- **Knowledge-base learnings are correctly deferred.** §2 Q6
  identifies CodeRabbit Knowledge Base learnings as a separate
  follow-up that lives outside the source-controlled diff. If
  TG-1 still shows canonical false positives after this config
  lands, that would be a new operational task (PR comment or
  CodeRabbit UI), not a re-run of BUG-3. Bundling that into
  BUG-3 would cross the proposal's "auditable repository config"
  boundary.
- **Knowledge-base `code_guidelines` toggling
  (`AGENTS.md`/`CLAUDE.md`/`copilot-instructions.md`)** is
  correctly out of scope. The RCA's audit confirms CodeRabbit
  already scans `**/AGENTS.md` by default, but the file does
  not currently contain Solid 2 beta semantics. §5 forbids
  editing `AGENTS.md` for Solid 2 beta context here, which
  keeps the locked mechanism singular (`reviews.path_instructions`).
- **Future widening of the path scope** (for example to
  `services/api/**` if a TypeScript false-positive pattern
  appears there) is correctly deferred. The BUG-3 evidence is
  Solid-specific, and §2 Q2 explicitly justifies the
  `services/web/**` scope. Expanding the glob pre-emptively
  would be unsupported by current evidence.

## Verdict reasoning

LOW. Every gate check passes:

1. **Only adds `.coderabbit.yaml` (and possibly a baseline file).**
   §3 enumerates exactly two new files: `.coderabbit.yaml` and
   `docs/coderabbit-solid2-false-positive-baseline.md`. The second
   file is the gate-sanctioned baseline. §3 "Modified files: None."
   ✅ check 1.
2. **No source code changes.** No `.ts`, `.tsx`, or `.spec.*`
   files are added or modified. The four canonical false-positive
   surfaces (`ApplicationQueueRoute.tsx`,
   `ApplicationDetailRoute.tsx`,
   `ApplicationTransitionActions.tsx`, `solid-compat/solid.ts`)
   are all left untouched, deliberately — the fix moves context
   into CodeRabbit's config rather than reshaping correct code.
   §5 explicitly bans changes to Solid source, web routes, the
   compat shim, and tests. ✅ check 2.
3. **No version bumps to Solid, CodeRabbit, or any tool.**
   §5 anti-scope explicitly bans Solid package version changes
   and CodeRabbit CLI/service version bumps. The fix sits in
   CodeRabbit's repo-config substrate; no `package.json`,
   lockfile, or CLI version change is touched. The
   `$schema=...schema.v2.json` header pins an existing schema,
   it is not a bump. ✅ check 3.
4. **No CI/CD pipeline changes beyond what CodeRabbit reads.**
   The only repo-root file added is `.coderabbit.yaml` itself —
   exactly the substrate CodeRabbit reads. GitHub Actions, PR
   templates, branch protection, auto-review labels, and the
   CodeRabbit invocation in `AGENTS.md:155-171` are all unchanged.
   §5 explicitly bans AGENTS.md edits, AST-grep instructions, and
   custom pre-merge checks — the alternative mechanisms that
   would have widened CI surface. ✅ check 4.
5. **No new abstraction or framework choice.** The fix is YAML
   configuration text plus a markdown baseline. No module, no
   helper, no framework, no API surface. §2 Q1-Q5 lock one
   mechanism (`reviews.path_instructions` with markdown bullets
   in a YAML block scalar), and §5 explicitly bans the alternative
   abstractions (lint rules, AST-grep, custom pre-merge checks,
   per-call-site `@coderabbitai ignore`, PR-description ignore
   commands, parallel knowledge-base learnings). ✅ check 5.

Three judgment calls worth naming explicitly — all LOW-risk:

- **Including the baseline document
  (`docs/coderabbit-solid2-false-positive-baseline.md`) in the
  initial diff** is sanctioned by the gate criteria
  ("possibly a baseline file") and is required by §4 TG-2 for
  regression detection against future CodeRabbit runs. It is
  documentation only — no reviewer behavior changes from this
  file alone — so it does not expand the runtime surface or
  introduce a new framework.
- **Scoping `reviews.path_instructions` to `services/web/**`
  rather than the whole repository** keeps the Solid-specific
  context off the API service, Discord daemon, Alembic
  migrations, Pomerium templates, Authentik blueprints, and
  product-strategy docs. The RCA's evidence is uniformly
  Solid-frontend-specific (RCA §"Affected Surfaces"), so a
  narrower glob is the correct mechanism choice. Widening to
  the whole repo would import Solid framework assumptions into
  reviews of unrelated services.
- **Deferring CodeRabbit Knowledge Base learnings to a possible
  operational follow-up rather than seeding them in this PR**
  keeps the BUG-3 fix entirely in source-controlled,
  diff-auditable form. §2 Q6 records the deferral explicitly,
  and TG-1 will reveal whether that follow-up is needed at all.
  Bundling learnings into BUG-3 would cross the proposal's
  "auditable repository config" boundary because learnings
  live outside the diff.

No "while we're at it" cleanups, no upstream tool upgrades, no
source-code edits, no consumer refactors, no AGENTS.md
re-write, no lint or AST-grep framework, no CI workflow
changes, no Pomerium / Authentik / API / Discord / migration
scope leakage, no test framework changes.

SCOPE_DONE: plans/risk/bug-3-scope.md
