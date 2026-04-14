# Risk assessment prompt — SHORTCUT risk for proposals/31-phase1-terraform.md

## Hard rules (read these first)

**YOU are the shortcut-risk assessor. YOU do the assessment yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is a single markdown file: `risk/31-shortcut.md`.

- **DO** read `proposals/31-phase1-terraform.md` in full. It is your
  primary input.
- **DO** read `plans/proposals/phase1-foundation.md` for the overarching
  Phase 1 context.
- **DO** read `AGENTS.md` for the project's operational rules.
- **DO** read `research/31-phase1-terraform.md` and
  `research/31-phase1-terraform-needs.md` for research context.
- **DO** write the assessment to `risk/31-shortcut.md` using your Write
  tool.
- **DO NOT** modify any file other than `risk/31-shortcut.md`
- **DO NOT** write the proposal itself — you're evaluating it
- **DO NOT** launch subprocesses

## What you're assessing

Your job is to identify **shortcut risk** — whether the proposal
introduces hacks, hardcoded values, duplicated logic, or workarounds
that will create technical debt.

Ask yourself:

1. **Hardcoded values**: are there values in the Terraform files that
   should be variables? Are there magic numbers or strings?
2. **Module abstraction**: does the kube-hetzner module instantiation
   use proper variable references, or does it hardcode configuration?
3. **DRY violations**: is there duplicated configuration between
   staging and production tfvars that should be in defaults?
4. **State backend**: is the remote state configuration clean, or does
   it use workarounds for Hetzner Object Storage compatibility?
5. **Provider configuration**: are provider configurations clean and
   idiomatic, or do they use workarounds?
6. **Future-proofing shortcuts**: does the proposal take shortcuts
   that will need to be undone in later phases? Are there "TODO"
   or "for now" patterns?
7. **Any other shortcut concern** — this list is not exhaustive.

## Output format

Write `risk/31-shortcut.md` with this structure:

```markdown
# Shortcut risk assessment — proposals/31-phase1-terraform.md

Date: 2026-04-14
Assessor: claude-opus (shortcut)

## Verdict

**LOW** | **MEDIUM** | **HIGH**

[One-sentence headline justification. Then ≤ 200 words of summary.]

## Findings

### Finding N — <short title>

- **Severity**: LOW | MEDIUM | HIGH
- **Section of proposal**: which subsection this applies to
- **Description**: what the concern is
- **Why it matters**: technical debt or maintenance burden
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
