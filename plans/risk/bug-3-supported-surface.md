# BUG-3 — Supported-surface risk gate

**Verdict:** LOW

BUG-3 (CodeRabbit Solid 2 beta review-context drift) is a review-tooling
configuration change that adds two new files at the repository root and
under `docs/`:

- `.coderabbit.yaml` containing one `reviews.path_instructions[]` entry
  scoped to `services/web/**` (proposal §3, skeleton at proposal §3 lines
  138-147).
- `docs/coderabbit-solid2-false-positive-baseline.md` containing the
  RCA's symptom catalog as a regression checklist (proposal §3 lines
  148-173).

No application source, no test source, no package version, no Solid
compat shim, no AGENTS.md text, and no CodeRabbit invocation is touched
(proposal §3 modified-files list and proposal §5 anti-scope). The change
exclusively alters the *review tool's* behavior on `services/web/**`
diffs by feeding it Solid 2 beta semantics; runtime, build, deploy,
auth, and storage paths see no byte change.

## Surfaces touched

### 1. Public API surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Web SPA exported modules (`services/web/src/**`) | as checked in | unchanged — proposal §3 modified-files list states "None"; anti-scope §5 forbids changing Solid source, tests, package versions, or `services/web/src/solid-compat/solid.ts` (proposal §5 lines 222-230) | none |
| API service routes (`services/api/**`) | as checked in | unchanged — `services/web/**` scoping in the path instruction (Q2 lock, proposal §2 lines 50-56) does not reach the API; the change is review tooling, not code | none |
| Discord daemon (`services/discord/**`) | as checked in | unchanged | none |
| Compatibility shim `services/web/src/solid-compat/solid.ts` | exports `batch`, `equalFn`, `Suspense`, `ErrorBoundary`, `startTransition`, `useTransition`, `mergeProps`, `splitProps`, `Index`, `onMount`, `createEffect`, `createComputed`, `createRenderEffect`, `on`, `createResource` plus `export *` re-exports (already locked by `plans/risk/bug-1-supported-surface.md:22-36`) | unchanged — anti-scope §5 line 228 forbids changing this file | none |
| `services/web/tests/solid-compat.spec.ts` and other test files | as checked in (e.g. `@solidjs/web` import already comment-warned at lines 1-4 per RCA §6) | unchanged — anti-scope §5 forbids editing tests for BUG-3; the RCA-documented in-source comment that previously failed to suppress false positives stays as-is and is now backstopped by the path instruction (RCA §6 line 292-295, proposal §2 Q5 lock) | none |

Risk on §1: **none** — gate criterion 1 (no public API change) holds.
The proposal's diff budget of "2 new files, no modified code files"
(proposal §6 lines 233-241) means there is no exported name added,
removed, renamed, or re-typed anywhere in the repository.

### 2. Environment variables — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Web build/runtime env (`VITE_*`) | as defined in `services/web/vite.config.ts` | unchanged — proposal touches no Vite config or web env | none |
| API service env (`API_*`, DB URLs, storage creds) | as defined | unchanged — proposal does not modify `services/api/**` | none |
| Discord daemon env | as defined | unchanged | none |
| CI / CodeRabbit invocation env | `coderabbit review --plain --base main --cwd <project-dir>` (RCA §"CLI surface" lines 240-251) | unchanged — proposal §2 Q5 and §5 anti-scope keep the CLI invocation identical; the new YAML is auto-discovered at the repo root, requiring no `--config` flag and no env-var injection | none |

Risk on §2: **none** — gate criterion 2 (no env vars) holds. The
`.coderabbit.yaml` is read directly by the CodeRabbit service/CLI at
the repository root; it does not introduce or consume any process env
var.

### 3. Database migrations — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Alembic head (`services/api/migrations/versions/...`) | current head | unchanged — proposal §3 modified-files: "None"; anti-scope §5 enumerates packages, source, AGENTS.md, review loop — schema is implicitly out of scope and explicitly absent from the diff budget (proposal §6) | none |
| Database schema, indexes, constraints | as deployed | unchanged | none |
| Web service ↔ DB | web is a static SPA with no direct DB connection (already noted in `plans/risk/bug-1-supported-surface.md:79-82`) | unchanged | none |

Risk on §3: **none** — gate criterion 3 (no DB migrations) holds.

### 4. GitOps surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/**` | as checked in (Crossplane, Flux, CNPG, Atlas, Authentik, Pomerium, Infisical, etc.) | unchanged — `.coderabbit.yaml` lives at the repository root, not under `gitops/`; proposal §3 lines 135-147 and the diff budget §6 lines 233-241 confirm only repo-root and `docs/` paths receive new files | none |
| `gitops/bootstrap/**` | as checked in | unchanged | none |
| Web container image / build pipeline | Vite production build via existing pipeline | unchanged — `.coderabbit.yaml` is consumed by CodeRabbit, not by the build, and is not packaged into the container image | none |
| CI manifests under `gitops/channels/local/cicd/**` | as checked in (Buildkite agent) | unchanged — proposal does not touch CI deployment manifests | none |

Risk on §4: **none** — gate criterion 4 (no GitOps changes) holds.
CodeRabbit's repository configuration is documented to live at the
repository root (`.coderabbit.yaml`) per `https://docs.coderabbit.ai/reference/configuration`
(RCA §"Repository YAML surface" lines 254-284); the gate's intent is
that delivery-pipeline manifests under `gitops/` remain frozen, and
they do.

### 5. Pomerium / Authentik surface — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Pomerium routes (`gitops/channels/local/auth/pomerium/**`) | as checked in (and live drift documented as separate follow-up Bug #5 per `plans/risk/bug-1-supported-surface.md:90`) | unchanged — proposal does not touch `gitops/**` | none |
| Authentik blueprint (`gitops/channels/local/auth/authentik/**`) | as checked in | unchanged | none |
| OAuth round-trip behavior, claim headers, identity flows | as deployed | unchanged — review-tooling configuration cannot affect runtime auth | none |

Risk on §5: **none** — gate criterion 5 (no Pomerium/Authentik
changes) holds.

### 6. CodeRabbit configuration — supported surface

This is the only surface the proposal does change, and it is the
explicit subject of the gate's sixth criterion ("`.coderabbit.yaml`
file is a supported CodeRabbit surface per their docs").

| Surface | Pre | Post | Supported-surface evidence |
|---|---|---|---|
| Repository-root CodeRabbit config | none — RCA §"Current repository state" lines 228-238 confirms no `.coderabbit.yaml`, `.coderabbit.yml`, `coderabbit.yaml`, `coderabbit.yml`, `services/web/.coderabbit.yaml`, or `.github` CodeRabbit/Copilot file exists | new `.coderabbit.yaml` at repo root with one `reviews.path_instructions[]` entry scoped to `services/web/**` (proposal §3 lines 135-147) | CodeRabbit's configuration reference at `https://docs.coderabbit.ai/reference/configuration` documents `.coderabbit.yaml` as the repository-root substrate (RCA "Repository YAML surface" lines 254-258); the path-instructions sub-doc at `https://docs.coderabbit.ai/configuration/path-instructions` documents `reviews.path_instructions` as the mechanism for path-scoped review guidance (RCA lines 263-265 and proposal Q1 / Q2 / Q3 locks at proposal §2 lines 34-72); the `# yaml-language-server: $schema=https://coderabbit.ai/integrations/schema.v2.json` header in proposal §3 line 140 references CodeRabbit's published schema |
| `reviews.path_instructions[].path` glob | n/a | `services/web/**` (proposal Q2 lock at lines 50-56) | path glob form is documented as the standard CodeRabbit globbing syntax (RCA lines 263-265) |
| `reviews.path_instructions[].instructions` body | n/a | YAML `\|` block scalar containing markdown bullet list of Solid 2 beta facts (proposal Q3 lock at lines 65-72; bullet content frozen at proposal Q4 lines 76-99) | CodeRabbit docs define `instructions` as a free-form string with additional review guidance, and example multi-line free-form text under that field (proposal Q3 lines 67-71); each bullet's *factual claim* is grounded in installed `services/web/node_modules/**` evidence cited in the RCA Summary lines 13-30 and Symptom Catalog lines 51-218 |
| `reviews.path_filters` | n/a | not used (proposal Q2 lock at lines 60-62 explicitly rejects path_filters because the goal is "to keep CodeRabbit reviewing the affected web files with correct framework context, not to exclude them from review") | no risk — exclusion path explicitly avoided |
| `@coderabbitai ignore` PR-description suppression | not used in repo | not added (proposal Q5 lock at lines 102-111) | no risk — the proposal explicitly avoids the only documented PR-level ignore command, which would have hidden real bugs |
| `@coderabbitai ignore` inline source comments | not present (no documented inline directive exists per RCA lines 287-295) | not added (proposal Q5 lock and anti-scope §5 line 222) | no risk — proposal correctly does not invent unsupported source-code directives |
| Knowledge Base learnings | not seeded | not seeded as part of this change (proposal Q6 lock at lines 114-129 defers learnings to a possible operational follow-up after TG-1 evidence) | the gate is "no learnings created in the CodeRabbit service as part of this PR" — proposal honors that and keeps the change auditable in the source-controlled diff |
| AGENTS.md | unchanged (RCA "Current repository state" line 235 confirms AGENTS.md does not mention Solid 2 beta accessors, `@solidjs/web`, or `createContext` semantics) | unchanged — anti-scope §5 line 230 forbids editing AGENTS.md for Solid 2 beta context in this proposal | none |
| `docs/coderabbit-solid2-false-positive-baseline.md` | n/a | new RCA-derived regression checklist (proposal §3 lines 148-173 and §4 TG-2 lines 208-219) | this is a documentation file under `docs/`, not a CodeRabbit-consumed surface; CodeRabbit's `knowledge_base.code_guidelines` defaults include `**/AGENTS.md` only (RCA lines 268-270), so the new docs file is not auto-ingested as review context — it is a *human-/agent-readable* regression baseline. That is intentional: the path instruction carries the review-time authority, and the docs file carries the human-auditable history |

Risk on §6: **none** — gate criterion 6 (`.coderabbit.yaml` is a
supported CodeRabbit surface per their docs) holds. The proposal uses
only documented YAML keys (`reviews.path_instructions[].path` and
`reviews.path_instructions[].instructions`) sourced from
`https://docs.coderabbit.ai/reference/configuration` and
`https://docs.coderabbit.ai/configuration/path-instructions`. It
deliberately *avoids* unsupported or risky CodeRabbit surfaces:
`@coderabbitai ignore` PR commands (would hide real bugs), undocumented
inline source directives (do not exist), Knowledge Base learnings
(not source-controlled), AST-grep instructions (out of scope), pre-merge
checks (docs say these cannot modify review comments), and CLI
`--config` injection (would couple Solid 2 beta facts to invocation
rather than to the repo).

### 7. Review-loop process — unchanged

| Surface | Pre | Post | Risk |
|---|---|---|---|
| AGENTS.md CodeRabbit review-loop policy ("rerun until clean", `AGENTS.md:155-171` per RCA lines 38-40) | as documented | unchanged — anti-scope §5 line 230 forbids AGENTS.md edits | none |
| `coderabbit review --plain --base main --cwd <project-dir>` invocation | as used in existing review loops | unchanged — `.coderabbit.yaml` is auto-discovered at the repo root by the CodeRabbit CLI/service; no flag changes are needed (proposal §4 TG-1 lines 188-205) | none |
| Per-PR commands and labels (`@coderabbitai pause`, `@coderabbitai resume`, `@coderabbitai review`, etc., RCA lines 297-309) | as documented | unchanged — proposal does not introduce or rely on per-PR commands or labels | none |

Risk on §7: **none** — review-loop semantics are preserved; the only
delta is that subsequent reviews of `services/web/**` diffs will
receive Solid 2 beta context inline.

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS — diff is 2 new files, 0 modified code files (proposal §6) |
| 2. No env vars | PASS — `.coderabbit.yaml` is auto-discovered at repo root; no env vars added or consumed |
| 3. No DB migrations | PASS — proposal §3 modified-files: "None" |
| 4. No GitOps changes | PASS — `.coderabbit.yaml` lives at repo root, not under `gitops/`; proposal does not touch `gitops/**` |
| 5. No Pomerium / Authentik changes | PASS — proposal does not touch `gitops/channels/local/auth/**` |
| 6. `.coderabbit.yaml` is a supported CodeRabbit surface per their docs | PASS — documented at `https://docs.coderabbit.ai/reference/configuration`; `reviews.path_instructions` documented at `https://docs.coderabbit.ai/configuration/path-instructions`; only documented YAML keys are used; unsupported or risky surfaces (`@coderabbitai ignore`, inline directives, KB learnings, AST-grep, pre-merge checks, CLI `--config`) are explicitly avoided per proposal Q5/Q6 locks |

## Out-of-scope items intentionally not addressed

- CodeRabbit Knowledge Base learnings as a persistent fact source
  (proposal Q6 lines 114-129). Deferred to a possible operational
  follow-up *after* TG-1 demonstrates whether the path instruction
  alone resolves the canonical Solid 2 beta false positives.
- AGENTS.md edits for Solid 2 beta semantics (proposal anti-scope §5
  line 230). Adding tool-specific framework context to a process
  guidance document would mix concerns; the path instruction is the
  durable mechanism.
- Solid package version changes (proposal anti-scope §5 line 226).
  The repo intentionally pins `solid-js@2.0.0-beta.8`,
  `@solidjs/web@2.0.0-beta.8`, and `@solidjs/signals@2.0.0-beta.8`
  (proposal §1 / RCA §Summary).
- `services/web/src/solid-compat/solid.ts` edits (proposal anti-scope
  §5 line 228). The shim is the subject of BUG-1's fix and is locked
  by `plans/risk/bug-1-supported-surface.md`.
- AST-grep, custom pre-merge checks, lint rules, or new test
  frameworks (proposal anti-scope §5 lines 225-227). The proposal
  uses only `reviews.path_instructions`.
- Live-cluster Pomerium drift (Bug #5 follow-up; same carve-out as in
  `plans/risk/bug-1-supported-surface.md:90, 100`). Not a BUG-3
  concern.

## Verdict

**LOW** — the change adds review-tool context as two new files at
documented CodeRabbit and `docs/` paths, modifies zero code files,
preserves every runtime, build, deploy, and auth surface, and uses
only documented `.coderabbit.yaml` keys. The only behavioral delta is
that future CodeRabbit reviews of `services/web/**` receive Solid 2
beta semantics, replacing Solid 1/stable-doc assumptions that produced
recurring false positives across at least eight catalogued review
rounds (RCA §"Symptom Catalog" lines 51-218).

SUPPORTED_SURFACE_DONE: plans/risk/bug-3-supported-surface.md
