# BUG-3 — Shortcut risk gate (CodeRabbit Solid 2 beta context)

**Verdict:** LOW

Source: `proposals/19-bug-3-coderabbit-solid2-context.md`,
`research/32-bug-3-coderabbit-foraccessor-rca.md`.

## C1 — Instructions describe Solid 2 beta semantics, not "skip these patterns"

**Pass.**

Q4 (proposal lines 76-99) locks an instruction body whose six bullets are
positive semantic descriptions of the installed beta contract, not blanket
suppressions:

| Bullet | What it teaches CodeRabbit |
|---|---|
| 1 | The project intentionally pins `solid-js@2.0.0-beta.8`, `@solidjs/web@2.0.0-beta.8`, `@solidjs/signals@2.0.0-beta.8`; prefer installed beta types/runtime over stable docs. |
| 2 | `<For>` callbacks receive accessors with the explicit signature `(item: Accessor<T>, index: Accessor<number>) => U`. Calling `item()` and `index()` is correct. |
| 3 | `<Show>` callback children receive an accessor for the narrowed `when` value; calling `value()` is correct. |
| 4 | SSR/web helpers come from `@solidjs/web` in this beta; `solid-js/web` is not exported from `solid-js@2.0.0-beta.8`. |
| 5 | `createContext` returns a callable provider with `id` and `defaultValue`, not an object with native `.Provider`; the local compat shim intentionally attaches a Solid 1-style wrapper. |
| 6 | Native `createEffect` / `createRenderEffect` require an effect handler argument; the compat shim deliberately routes one-arg call sites through handler-supplying paths. |

These bullets are anchored to evidence the RCA already established in
`services/web/node_modules/solid-js/types/client/flow.d.ts:19-23`,
`flow.d.ts:4-6`/`:47-52`, `solid-js/dist/solid.js:6-17`, and the
`@solidjs/web` package metadata at
`services/web/node_modules/@solidjs/web/package.json:31-116`. The instructions
re-state the actual contract; they don't say "ignore these warnings" or
"these patterns are intentional, move on."

The framing also pairs each callable parameter with what's correct
(`item()`, `value()`) and what would be wrong (`item.id` raw access, switching
the import to `solid-js/web`), so the reviewer has a positive model rather
than a denylist.

## C2 — No `@coderabbitai ignore` stuffed into source files

**Pass.**

Q5 (lines 101-111) is explicit:

> Lock: rely solely on `reviews.path_instructions`; do not add
> `@coderabbitai ignore` to source call sites.

The proposal also notes that `@coderabbitai ignore` is documented as a
PR-description control, not an inline source suppression, so scattering it
through code wouldn't even do what the check is guarding against.

Anti-scope (lines 223-224) reinforces this with two separate prohibitions:

- "Do not add `@coderabbitai ignore` scattered through source code."
- "Do not add `@coderabbitai ignore` to PR descriptions as the BUG-3 fix."

Substrate (section 3) lists no source-file edits at all — only
`.coderabbit.yaml` and `docs/coderabbit-solid2-false-positive-baseline.md` are
added; line 178 reads "Modified files: None." That structurally rules out
sprinkling ignore comments into source as part of this fix.

## C3 — Fix is auditable in source control, not CodeRabbit cloud-only

**Pass.**

The two delivered artifacts are both repository files committed under the
project root:

- `.coderabbit.yaml` (substrate, lines 134-146) — the actual review-context
  config that ships in the repo.
- `docs/coderabbit-solid2-false-positive-baseline.md` (lines 148-174) — the
  baseline used by TG-2 for regression detection.

Q6 (lines 113-129) explicitly considered the cloud-only path (CodeRabbit
"learnings") and rejected it as the primary mechanism precisely because it
would not be auditable in source control:

> learnings live outside the source-controlled diff and can be edited or
> scoped through the CodeRabbit service. For this bug, the primary fix
> should be auditable repository config: `.coderabbit.yaml` with
> `reviews.path_instructions`.

A future operational follow-up to seed CodeRabbit learnings is left as a
contingent option ("If TG-1 still shows canonical Solid 2 beta false
positives after the config lands…"), not as the locked deliverable. The
shipped fix is entirely diff-visible, reviewable, and revertible through
ordinary git history.

## C4 — TG-1 actually re-runs CodeRabbit, not "trust me it works"

**Pass.**

TG-1 (lines 186-205) names the executable command and the surfaces to
exercise:

```bash
coderabbit review --plain --base main --cwd <project-dir>
```

against "a representative BUG-1-ish PR or local branch that touches the
Solid compat shim and web route surfaces." That's the same command the
existing AGENTS review loop already uses
(`research/32-bug-3-coderabbit-foraccessor-rca.md:249-251`), so the test is
running the real reviewer rather than a synthetic stand-in.

Acceptance criteria are concrete and falsifiable, mapped to the RCA's
canonical false-positive families:

- CodeRabbit still reviews `services/web/**` (guards against the
  path_filters mistake the proposal explicitly avoids).
- It does **not** re-emit any of the five canonical Solid 2 beta false
  positives:
  - `<For>` callback parameters treated as raw values (RCA Patterns 1-4).
  - `<Show>` callback parameters treated as raw values (RCA Pattern 8).
  - `renderToString` import flagged for change to `solid-js/web`
    (RCA Pattern 6).
  - `createContext` assumed to have native `.Provider` (RCA Pattern 7).
  - Legacy compat effect arity treated as a mistake (RCA contributing
    factor; BUG-1 r1-r6 logs).
- Any remaining findings are reviewed on their own merits (no whitelist
  laundering of unrelated CodeRabbit comments under the BUG-3 banner).

TG-2 (lines 208-219) adds a baseline document the test compares against, so
"clean" is defined relative to the recorded historical false positives in
the RCA symptom catalog rather than an unwritten standard. The baseline
makes regressions visible without rereading every `.tmp/**/coderabbit` log.

This is a real rerun against named patterns, not an assertion that the
config "should work."

## Findings worth carrying into implementation

Not blockers — the shortcut review is LOW — but the implementation phase
should preserve them:

1. **Path scope is `services/web/**`, not the whole repo.** Q2 (lines 50-60)
   intentionally avoids `path_filters` and intentionally avoids broadening
   the instruction to API/Discord/migrations/infra-plan paths. Don't widen
   the glob during implementation; the false-positive family is
   web-package-specific, and broader scope risks confusing reviewers on
   non-Solid surfaces.

2. **YAML block scalar, not escaped strings.** Q3 (lines 64-72) commits to
   markdown bullets inside a `|` block scalar. Implementation should not
   collapse the bullets into a single-line escaped YAML string — that
   defeats the readability/diffability rationale and risks losing newlines
   the reviewer keys off of.

3. **Don't change source as part of this fix.** Anti-scope (lines 222-230)
   is explicit: no edits to Solid source, tests, package versions,
   `services/web/src/solid-compat/solid.ts`, web route code, or
   `AGENTS.md`. The fix is review-context only; mixing in code edits would
   muddy TG-1 (a clean rerun would no longer attribute results to the
   config alone).

4. **TG-1 must run after the config commits.** The acceptance signal is
   "config lands → rerun → canonical patterns absent." If the rerun is
   done against an uncommitted local config or a stashed file,
   `.coderabbit.yaml` is what the service reads from the repo, so testing
   against committed state is the meaningful check.

5. **Q6's deferred learnings remain deferred.** If TG-1 still shows the
   canonical false positives, the Q6 escape hatch is to add CodeRabbit
   learnings via PR comment / CodeRabbit UI as an operational follow-up.
   That should not become a quiet shortcut substituted for a fully-working
   `.coderabbit.yaml`.

## Verdict

LOW. No shortcuts. The proposal:

- Writes an instruction body that teaches Solid 2 beta semantics, with type
  signatures and the precise package/import truth, rather than telling
  CodeRabbit to suppress patterns.
- Forbids `@coderabbitai ignore` in both source files and PR descriptions,
  in two separate anti-scope items, and structurally adds zero source-file
  edits.
- Delivers the fix as two committed repository files (`.coderabbit.yaml`
  and the baseline doc), explicitly choosing source-controlled config over
  cloud-only learnings, with the cloud path retained only as a
  contingent operational follow-up.
- Defines TG-1 as a real `coderabbit review` rerun against the same command
  the AGENTS loop already uses, with falsifiable acceptance criteria mapped
  one-to-one to the RCA's five canonical false-positive families and a
  TG-2 baseline to detect regressions.

The diff budget (~95-165 added lines, two new files, no runtime/test/code
changes) matches the locked scope and avoids blurring into the Solid compat
shim or AGENTS.md.

SHORTCUT_DONE: plans/risk/bug-3-shortcut.md
