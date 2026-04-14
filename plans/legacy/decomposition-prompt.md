# Document decomposition prompt (template)

## Hard rules

**YOU are the decomposition agent. YOU do the decomposition yourself.**
**Do not launch, spawn, dispatch, or report on any other agent.**

Write exactly one markdown file to `{{OUTPUT_PATH}}`.

Read `{{INPUT_PATH}}` directly and exhaustively.

Do not write code.
Do not propose implementation or sequencing beyond decomposition.
Do not merge this document with any other document.
Do not collapse distinct ideas just because they sound similar.
Separate explicit statements from your inferences.

## Goal

Decompose `{{DOC_LABEL}}` into a structured index that can later be
merged with indexes from other legacy platform documents.

The index must preserve:

- every named component / technology / subsystem
- every architectural decision and its rationale when stated
- every implementation unit or work package implied by the document
- every dependency on systems described elsewhere
- every outdated or questionable choice that may need modernization
- every missing or underspecified element the later merge must resolve

## User-overrides to preserve as conflict markers

These are not automatically resolved here; they are flags for the
later merge/conflict-resolution pass:

- `Buildkite` is the preferred modernization target over `Dagger`
- `Flux` is the preferred modernization target over `Argo`
- provider choice may move beyond the original Vultr framing
- the modernized platform will likely differ materially from these
  legacy specs

## Deliverable shape

Write `{{OUTPUT_PATH}}` with exactly these sections:

## 1. Scope and document intent

Briefly explain what this document is trying to define, what layer of
the platform it covers, and what kind of artifact it is
(vision/spec/proposal/implementation sketch/etc.).

## 2. Component inventory

Use a table with columns:
`Component | Kind | Role in document | Notes`

Include all named technologies, services, platforms, protocols, and
internal subsystems that matter to the design.

## 3. Architectural decisions

Use a table with columns:
`Decision | Evidence from document | Rationale in document | Confidence | Modernization risk`

Confidence should reflect how explicit the document is.
Modernization risk should be `low`, `medium`, or `high`.

## 4. Implementation units

Use a table with columns:
`Unit | What would need to be built/configured | Dependencies | Why it exists`

Break the document into individually discussable work units rather
than giant program phases whenever possible.

## 5. Cross-document dependencies

Use a table with columns:
`Dependency | Depends on what | Why it is cross-document | Confidence`

Include dependencies on other legacy specs, external control planes,
or platform layers not fully defined in this document.

## 6. Outdated or questionable items

Use a table with columns:
`Item | Why questionable | Likely modernization direction`

Include obsolete tools, superseded providers, hand-wavy assumptions,
and choices that conflict with the user's newer guidance.

## 7. Missing or underspecified elements

Use a table with columns:
`Gap | Why it matters | Confidence`

Capture important omissions, unresolved interfaces, and places where
later merge work must reconcile ambiguity.

## 8. Raw statistics

Provide exactly these bullets:

- Total components mentioned: <number>
- Total architectural decisions: <number>
- Total implementation units: <number>
- Total cross-document dependencies: <number>
- Total outdated/questionable flags: <number>

## Quality bar

Be exhaustive rather than elegant.
Preserve exact product and subsystem names.
Prefer dense technical indexing over prose.
If the document contains contradictions, record them rather than
resolving them.
