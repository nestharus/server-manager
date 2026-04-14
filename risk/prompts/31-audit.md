# Risk assessment prompt — AUDIT risk for proposals/31-phase1-terraform.md

## Hard rules (read these first)

**YOU are the audit-risk assessor. YOU do the assessment yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is a single markdown file: `risk/31-audit.md`.

- **DO** read `proposals/31-phase1-terraform.md` in full. It is your
  primary input.
- **DO** read `plans/proposals/phase1-foundation.md` for the overarching
  Phase 1 context.
- **DO** read `AGENTS.md` for the project's operational rules.
- **DO** read `research/31-phase1-terraform.md` and
  `research/31-phase1-terraform-needs.md` for research context.
- **DO** write the assessment to `risk/31-audit.md` using your Write
  tool.
- **DO NOT** modify any file other than `risk/31-audit.md`
- **DO NOT** write the proposal itself — you're evaluating it
- **DO NOT** launch subprocesses

## What you're assessing

Your job is to identify **audit risk** — safety, security, and
data-integrity risks introduced by `proposals/31-phase1-terraform.md`.

Ask yourself these specific questions:

1. **Credential management**: does the proposal properly handle the
   Hetzner API token? Is it marked sensitive in Terraform? Is there any
   path where it could be committed to the repo, logged in plan output,
   or exposed in state files?
2. **Remote state security**: is the S3-compatible backend for Hetzner
   Object Storage configured securely? Are access keys and secret keys
   handled properly? Is state encryption considered?
3. **SSH key management**: are SSH key IDs handled securely? Is there
   any risk of key material being exposed?
4. **Network security**: does the private networking configuration
   properly isolate cluster traffic? Are there any public-facing
   attack surfaces beyond what's intended?
5. **Cluster access**: after bootstrap, who can access the cluster?
   Is kubeconfig distribution secure?
6. **Module supply chain**: is the `kube-hetzner` module source pinned
   to a specific version? Could a module supply-chain attack occur?
7. **Any other audit-risk concern you find** — this list is not
   exhaustive.

## Output format

Write `risk/31-audit.md` with this structure:

```markdown
# Audit risk assessment — proposals/31-phase1-terraform.md

Date: 2026-04-14
Assessor: claude-opus (audit)

## Verdict

**LOW** | **MEDIUM** | **HIGH**

[One-sentence headline justification. Then ≤ 200 words of summary.]

## Findings

### Finding N — <short title>

- **Severity**: LOW | MEDIUM | HIGH
- **Section of proposal**: which subsection this applies to
- **Description**: what the concern is
- **Why it matters**: concrete blast radius or exploit path
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
