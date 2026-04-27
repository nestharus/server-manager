# Audit history — INIT-114 process recovery

## Purpose
Track blocking Phase 6 firstness, missing supported-surface risk, and skipped RCA for INIT-114 recovery.

## Artifact lineage
- Main audit: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
- Prompt/log evidence: `/home/nes/projects/server-manager/.tmp/init-114-pipeline.md`, `/home/nes/projects/server-manager/.tmp/init-114-pipeline.log`.
- Git evidence: `feat/init-114-auth-stack`, runtime fix commits `a53f14b` through `806f60f`.

## Round summaries
### Round 1 — process audit
- Artifact under review: INIT-114 pipeline history.
- Round artifacts: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
- Report artifacts: none.
- Prior finding counters: closed 0; intact 0; weakened 0; regressed 0; not closed 0.
- New findings: `R1-F01` blocking same invocation for full pipeline; `R1-F02` blocking missing Step 6b output index; `R1-F03` blocking missing red/green/process-tree gates; `R1-F04` blocking 3-way Phase 4 risk only; `R1-F05` skipped RCA for repeated runtime fixes.
- Oscillation: none.
- Decompose trigger: fired; reason: auth stack is security-sensitive and had many fix commits after tests.
- Watch signals for next round: any access/auth behavior inferred from implementation rather than contract.
- Verdict or determination: decompose.
- Role outputs: process-tree-auditor determination DECOMPOSE.
- Next handoff: rebuild from auth contract; Step 6b test writer must not read implementation.

## Decision register
- Round 1: decompose; deciding input: main audit; reason: same-agent validators plus runtime fixes make current state unsuitable as trusted baseline.

## Watch signals
- Pomerium/Auth/Cedar behavior not pinned by contract.
- Tests require existing manifests to define expected behavior.

## Final state
Open.
