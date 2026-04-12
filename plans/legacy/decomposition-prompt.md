# Document decomposition prompt (template)

## Hard rules

**YOU are the decomposition agent. YOU do the decomposition yourself.
Do not launch, spawn, dispatch, or report on any other agent.**

Your deliverable is a structured index file. Write it using the
Write tool. Do not print progress commentary.

## Task

Read the document at `{DOC_PATH}` in full. Produce a structured
decomposition at `{OUTPUT_PATH}`. This document is one of four
legacy enterprise platform specifications that need to be
modernized and broken into individually-implementable units.

The decomposition must capture ALL detail without losing information.
The original document will still exist, but the index is what
downstream agents will use to plan work. If a detail is in the
document but not in the index, it will be lost.

## Required sections in the output

### 1. Executive summary (≤200 words)

What this document specifies, at what scope, and what it assumes
exists underneath it.

### 2. Component inventory

For EVERY named technology, service, or tool mentioned:

| Component | Role in this spec | Category | External dependency? | Notes |
|---|---|---|---|---|

Categories: compute, networking, security, auth, observability,
storage, CI/CD, messaging, API, other.

### 3. Architectural decisions

Every explicit or implied design decision. For each:

- **Decision**: what was decided
- **Rationale**: why (quote the document if possible)
- **Scope**: which components it affects
- **Confidence**: HIGH (explicitly stated with rationale) / MEDIUM
  (stated without full rationale) / LOW (implied or assumed)
- **Modernization risk**: does this decision reference a specific
  tool version, a now-deprecated approach, or a vendor that may
  have changed? Flag it.

### 4. Cross-document dependencies

What does this document assume already exists? What does it provide
that other documents likely depend on? Be specific — name the
components, not vague categories.

### 5. Implementation units

Break the document into the smallest self-contained implementation
units that could each become a separate task or PR. For each:

- **Unit ID**: short slug (e.g., `auth-authentik-setup`,
  `gitops-kafka-cdc-pipeline`)
- **Title**: one line
- **Description**: 2-3 sentences
- **Dependencies**: which other units (from this or other documents)
  must exist first
- **Components involved**: from the inventory
- **Estimated complexity**: S / M / L / XL
- **Can be parallelized with**: other unit IDs that have no
  dependency relationship

### 6. Outdated or questionable elements

Flag anything that:
- References a specific tool version that is likely outdated by
  April 2026
- Uses a technology that has been superseded (e.g., the user has
  told us Dagger → Buildkite, Argo → Flux)
- Makes assumptions about a vendor (Vultr) that may change
- Contains vague "future work" placeholders without concrete specs
- Duplicates functionality that another document also specifies

### 7. Missing elements

What does this document NOT specify that it should? Gaps in:
- Error handling / failure modes
- Scaling limits
- Cost modeling
- Security hardening
- Operational runbooks
- Monitoring/alerting
- Backup/recovery for specific components

### 8. Raw statistics

- Total components mentioned: N
- Total architectural decisions: N
- Total implementation units: N
- Total cross-document dependencies: N
- Total outdated/questionable flags: N

## Output quality bar

- Every component in the document must appear in section 2
- Every decision must appear in section 3
- No implementation unit should be larger than "a team could
  implement and validate this in 1-2 weeks"
- Dependencies must be specific enough that a scheduler could
  build a dependency graph
- Do NOT summarize — decompose. The goal is structured access to
  ALL the information, not a shorter version of the document.
