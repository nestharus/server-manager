# Risk audit — BUG-3 CodeRabbit Solid 2 beta review context

Inputs:
- Proposal: `proposals/19-bug-3-coderabbit-solid2-context.md`
- RCA: `research/32-bug-3-coderabbit-foraccessor-rca.md`
- Substrate: new file `.coderabbit.yaml`, new file
  `docs/coderabbit-solid2-false-positive-baseline.md`

## Verdict

APPROVED — proceed to implementation.

The proposed `.coderabbit.yaml` with a `services/web/**`-scoped
`reviews.path_instructions` block addresses the RCA's named root cause
(framework-version context mismatch in CodeRabbit reviews), covers all six
canonical false-positive families called out by the audit prompt, scopes
correctly, introduces no security regression, and has a testable TG-1 plan.
Three non-blocking observations are recorded below.

## Findings

### F-1 Root-cause coverage — PASS

The RCA names the root cause as a framework-version context mismatch:
CodeRabbit applies Solid 1 / stable-doc assumptions while the repo intentionally
runs Solid 2 beta packages
(`research/32-bug-3-coderabbit-foraccessor-rca.md:316-345`). Contributing
factors enumerated in §"Root Cause" include the absence of a
`.coderabbit.yaml`, default web-search reinforcing stable Solid 1 docs, and
`AGENTS.md` containing process guidance only.

The proposal directly counters those contributing factors via CodeRabbit's
documented mechanism: a repository-root `.coderabbit.yaml` with
`reviews.path_instructions` (proposal Q1, §3 substrate). This is exactly the
documented knob CodeRabbit positions for "recurring path-specific review gaps"
(RCA §"CodeRabbit Config Audit"). The fix attacks the context-injection
deficit, not just the symptom files.

### F-2 Six canonical false-positive coverage — PASS

The audit prompt lists six canonical false positives. All six are addressed by
the locked Q4 instruction bullets:

| Canonical pattern | Q4 bullet | RCA evidence |
|---|---|---|
| Version pin (umbrella) | bullet 1 (`solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`, `@solidjs/signals@2.0.0-beta.8`) | RCA §Summary, §"Pattern 6" |
| `For` accessor children | bullet 2 (`(item: Accessor<T>, index: Accessor<number>) => U`; `item()` correct; do not suggest `item.id`) | RCA Patterns 1-4 (8+ recurrences across init-133B-i/ii/iii rounds) |
| `Show` accessor children | bullet 3 (callback children receive an accessor for the narrowed `when` value) | RCA Pattern 8 (typed in `flow.d.ts:4-6, :47-52`) |
| `@solidjs/web` import | bullet 4 (do not suggest `solid-js/web`; not exported by `solid-js@2.0.0-beta.8`) | RCA Pattern 6 (BUG-1 r2/r4/r6 recurrences) |
| `createContext` callable provider shape | bullet 5 (callable function with `id`/`defaultValue`; no native `.Provider`; local compat shim wraps) | RCA Pattern 7 (BUG-1 r2/r3) |
| Legacy effect handler arity | bullet 6 (Solid 2 native requires handler argument; compat shim preserves legacy single-arg call sites) | RCA §"Affected Surfaces" + cross-link to BUG-1 |

Each bullet calls out both the correct semantic AND the wrong CodeRabbit
suggestion, which is the right shape for path_instructions text — the model
has both the rule and the anti-rule to compare against generic Solid 1
training data.

### F-3 Path scope — PASS

Proposal Q2 locks scope to `services/web/**` and §3 substrate confirms the
single `path: "services/web/**"` entry. This is correct:

- The RCA §"Affected Surfaces" enumerates only files under
  `services/web/src/**`, `services/web/tests/**`, `services/web/tsconfig.json`,
  and `services/web/vite.config.ts`. All fall under `services/web/**`.
- Other services (`services/api`, Discord daemon, `infra/**`, `migrations/**`,
  product-strategy docs) have no Solid 2 beta surface and must not inherit
  framework-specific review assumptions. The scoped glob preserves that
  isolation.
- The proposal explicitly rejects `reviews.path_filters` (Q2), which is the
  right choice — the goal is to add context, not to exclude files from review.

The chosen `services/web/**` glob is slightly wider than the RCA's intervention
list (which split `services/web/src/**` and `services/web/tests/**`). The
wider glob is acceptable: it captures `services/web/tsconfig.json` and
`services/web/vite.config.ts` (which contain the compat aliases per RCA
§"Affected Surfaces"), and there is no co-located non-Solid code under
`services/web/**` that would be miscued by Solid 2 beta context.

### F-4 Security — PASS

The instruction text does not:

- Expose secrets, tokens, or environment variables.
- Disable any CodeRabbit security category (no `reviews.tools.*`,
  `reviews.pre_merge_checks.*`, `chat.*`, or auto-review opt-out is touched).
- Alter what CodeRabbit treats as a vulnerability — every bullet is
  framework-semantic disambiguation, not a class of finding to suppress.
- Use the `@coderabbitai ignore` PR-description switch, which would have
  silenced all review on a PR. Q5 explicitly rejects that mechanism.
- Add per-file source comment suppressions, which RCA §"Per-file directives"
  notes are not officially supported and have already failed once for the
  `@solidjs/web` case.

The diff budget (95-165 added lines) covers two non-runtime files only. No
package versions, lockfiles, source code, or CI configuration change. The
attack surface is limited to whether CodeRabbit reads attacker-controlled YAML
from a forked PR — but `.coderabbit.yaml` lives at repo root and is governed
by ordinary PR review, so a malicious change would be visible in the diff.

### F-5 TG-1 verification plan — PASS, with clarification

TG-1 specifies the verification command exactly:

```bash
coderabbit review --plain --base main --cwd <project-dir>
```

This matches the AGENTS.md review loop (`AGENTS.md:155-171` per RCA
§"Required Reading Completed"), so reviewer behavior under TG-1 mirrors normal
operation.

Acceptance criteria are observable and machine-checkable against captured logs:

- "still reviews `services/web/**` files" — verifiable by grepping log for any
  finding under that path.
- "does not re-emit the canonical Solid 2 beta false positives" — each of the
  five enumerated patterns (`<For>` callback raw, `<Show>` callback raw,
  `renderToString → solid-js/web`, `createContext.Provider`, legacy compat
  effect arity) has a representative log signature documented in the RCA
  symptom catalog. Future runs can be diffed against those signatures.

Clarification: TG-1 calls for re-running on "a representative BUG-1-ish PR or
local branch that touches the Solid compat shim and web route surfaces." This
is loose. The implementation should pin verification to a branch that touches
the specific RCA-enumerated files (`ApplicationQueueRoute.tsx`,
`ApplicationDetailRoute.tsx`, `ApplicationTransitionActions.tsx`,
`services/web/src/solid-compat/solid.ts`, `services/web/tests/solid-compat.spec.ts`)
to ensure each canonical pattern is actually exercised. Otherwise a clean run
may reflect an empty diff rather than working path_instructions.

TG-2's baseline document is non-blocking and serves regression detection. The
locked five-pattern list in `docs/coderabbit-solid2-false-positive-baseline.md`
matches the canonical patterns covered in F-2.

## Observations (non-blocking)

1. **Fact slip on `@solidjs/signals` pin location.** Proposal §1 and RCA §Summary
   both cite `services/web/package.json:33` as the pin source for
   `@solidjs/signals@2.0.0-beta.8`. Verified: line 33 is `solid-js`, and
   `@solidjs/signals` is not in the direct dependency list at all — it is a
   transitive dependency only (confirmed installed at
   `services/web/node_modules/@solidjs/signals/package.json` as version
   `2.0.0-beta.8`). The version assertion in Q4 bullet 1 is still factually
   correct (the package is present at that version), but the cited pin source
   is wrong. Implementation should not propagate the bad cite into commit
   messages or the baseline doc; just say "installed as a transitive at
   2.0.0-beta.8" or omit the package.json line reference.

2. **Web search reinforcement.** RCA §"Contributing factors" notes CodeRabbit's
   `knowledge_base.web_search.enabled` defaults to enabled and likely
   reinforces public Solid 1 docs over the beta-local semantics. The proposal
   does not disable web search. This is the correct staging — disabling web
   search would have wider review consequences. If TG-1 still emits canonical
   false positives despite the path_instructions, the operational follow-up
   noted in Q6 (CodeRabbit learnings via PR comment / UI) should be the next
   lever, not a global web-search opt-out.

3. **Diff budget.** Proposal estimates 95-165 added lines across two new files
   (`.coderabbit.yaml` ~25-45 lines; baseline doc ~70-120 lines). No source,
   test, lockfile, or CI changes. Implementation materially larger should
   re-check anti-scope, particularly the prohibitions on editing
   `services/web/src/solid-compat/solid.ts`, modifying `AGENTS.md` for Solid 2
   context, or adding ast-grep / pre-merge custom checks.

## Acceptance check (proposed)

When implementation lands, the following must all hold:

- A new file `.coderabbit.yaml` exists at repository root with a single
  `reviews.path_instructions` entry whose `path` is `"services/web/**"` and
  whose `instructions` block scalar contains all six bullets from proposal Q4
  verbatim or with editorial-only changes.
- A new file `docs/coderabbit-solid2-false-positive-baseline.md` exists,
  enumerating the five canonical pattern families and citing the RCA as the
  source.
- No source file under `services/web/src/**` is modified.
- No `@coderabbitai ignore` token is added to any PR description, source
  comment, or commit message as part of this change.
- TG-1: a CodeRabbit rerun on a branch that touches at least one of the
  RCA-enumerated affected files produces a log free of the five canonical
  false-positive signatures.
- TG-2: the baseline document is created before TG-1 is run, and the TG-1 log
  is diffed against the baseline patterns.

AUDIT_DONE: plans/risk/bug-3-audit.md
