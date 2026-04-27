# Audit history — INIT-105 process recovery

## Purpose
Track blocking Phase 6 firstness and Phase 4 supported-surface violations for INIT-105 recovery.

## Artifact lineage
- Main audit: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
- Prompt/log evidence: `/home/nes/projects/server-manager/.tmp/init-105-pipeline.md`, `/home/nes/projects/server-manager/.tmp/init-105-pipeline.log`.
- Git evidence: `feat/init-105-tls-dns`, pipeline commit `20198f0`, implementation commits through `1f7291f`.

## Round summaries
### Round 1 — process audit
- Artifact under review: INIT-105 pipeline history.
- Round artifacts: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
- Report artifacts: none.
- Prior finding counters: closed 0; intact 0; weakened 0; regressed 0; not closed 0.
- New findings: `R1-F01` blocking same invocation for full pipeline; `R1-F02` blocking missing Step 6b output index; `R1-F03` blocking missing red/green/process-tree gates; `R1-F04` blocking 3-way Phase 4 risk only.
- Oscillation: none.
- Decompose trigger: not fired; reason: TLS/DNS behavior has externally observable cluster proofs.
- Watch signals for next round: certificate/DNS tests require implementation-derived names not fixed by contract.
- Verdict or determination: continue.
- Role outputs: process-tree-auditor determination CONTINUE.
- Next handoff: independent Step 6b creates TLS/DNS risk-indexed tests.

## Decision register
- Round 1: continue; deciding input: main audit; reason: external validation can recover confidence.

## Watch signals
- Cluster proof differs from proposal.
- Remote DNS/ACME assumptions not covered by supported-surface risk.

## Final state
Open.
