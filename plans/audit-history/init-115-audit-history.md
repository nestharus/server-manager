# Audit history — INIT-115 process recovery

## Purpose
Track blocking Phase 6 firstness and Phase 4 supported-surface violations for INIT-115 recovery.

## Artifact lineage
- Main audit: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
- Prompt/log evidence: `/home/nes/projects/server-manager/.tmp/init-115-pipeline.md`, `/home/nes/projects/server-manager/.tmp/init-115-pipeline.log`.
- Git evidence: `feat/init-115-access-policy`, implementation commit `9b292ac`.

## Round summaries
### Round 1 — process audit
- Artifact under review: INIT-115 pipeline history.
- Round artifacts: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
- Report artifacts: none.
- Prior finding counters: closed 0; intact 0; weakened 0; regressed 0; not closed 0.
- New findings: `R1-F01` blocking same invocation for full pipeline; `R1-F02` blocking missing Step 6b output index; `R1-F03` blocking missing red/green/process-tree gates; `R1-F04` blocking 3-way Phase 4 risk only.
- Oscillation: none.
- Decompose trigger: fired; reason: access policy and break-glass behavior must be independently specified and tested.
- Watch signals for next round: policy tests mirror implementation instead of contract.
- Verdict or determination: decompose.
- Role outputs: process-tree-auditor determination DECOMPOSE.
- Next handoff: rebuild policy contract and independent tests first.

## Decision register
- Round 1: decompose; deciding input: main audit; reason: policy surface is too sensitive for same-agent validation provenance.

## Watch signals
- Break-glass exceptions not fixed by proposal.
- Cedar allow/deny tests depend on implementation internals.

## Final state
Open.
