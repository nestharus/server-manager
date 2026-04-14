# Risk assessment prompt — SCOPE risk for proposals/31-phase1-terraform.md

## Hard rules (read these first)

**YOU are the scope-risk assessor. YOU do the assessment yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is a single markdown file: `risk/31-scope.md`.

- **DO** read `proposals/31-phase1-terraform.md` in full. It is your
  primary input.
- **DO** read `plans/proposals/phase1-foundation.md` for the overarching
  Phase 1 context.
- **DO** read `AGENTS.md` for the project's operational rules.
- **DO** read `research/31-phase1-terraform.md` and
  `research/31-phase1-terraform-needs.md` for research context.
- **DO** write the assessment to `risk/31-scope.md` using your Write
  tool.
- **DO NOT** modify any file other than `risk/31-scope.md`
- **DO NOT** write the proposal itself — you're evaluating it
- **DO NOT** launch subprocesses

## What you're assessing

Your job is to identify **scope risk** — whether the proposal is
appropriately sized for the problem.

Ask yourself:

1. **Too ambitious?** Does the proposal try to solve problems beyond
   the Terraform bootstrap layer? Does it include concerns that belong
   in later phases (Flux CD, Kong, secrets, Buildkite)?
2. **Too narrow?** Does the proposal omit any Terraform files or
   configurations that are necessary for a working kube-hetzner
   bootstrap?
3. **Environment parity**: are the staging and production tfvars
   appropriately differentiated? Is staging too small to be useful,
   or is production oversized for the current needs?
4. **Downstream impact**: does the proposed variable surface create
   downstream work that's hard to change later? Are there hardcoded
   values that should be variables, or vice versa?
5. **Module version risk**: is the kube-hetzner version constraint
   appropriate? Too loose? Too tight?
6. **Any other scope concern** — this list is not exhaustive.

## Output format

Write `risk/31-scope.md` with this structure:

```markdown
# Scope risk assessment — proposals/31-phase1-terraform.md

Date: 2026-04-14
Assessor: claude-opus (scope)

## Verdict

**LOW** | **MEDIUM** | **HIGH**

[One-sentence headline justification. Then ≤ 200 words of summary.]

## Findings

### Finding N — <short title>

- **Severity**: LOW | MEDIUM | HIGH
- **Section of proposal**: which subsection this applies to
- **Description**: what the concern is
- **Why it matters**: downstream impact
- **Recommendation**: what change would fix it

[Repeat for each finding.]

## Overall assessment

[Summary of how the findings combine into the verdict.]
```

## Anti-goals

- Do not rewrite the proposal
- Do not return MEDIUM or HIGH without a concrete finding
- Do not hedge — pick a verdict and justify it
- Do not write more than 2500 words
