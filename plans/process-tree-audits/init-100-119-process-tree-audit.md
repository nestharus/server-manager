# Process-tree audit — INIT-100..119

## Scope note

- This audit classifies INIT-101 through INIT-119, as requested in the per-INIT scope.
- INIT-100 is the reset baseline commit (`eb2e434 INIT-100: Phase 5 reset — environment-agnostic re-plan`), not a Phase 6 implementation pipeline. It is not counted in the per-INIT totals.
- This is a process audit only. It does not assert that the shipped code is wrong; it asserts that the required process evidence for trusting the code/test relationship is absent or contradicted.

## Headline

- Total INITs audited: 19
- Phase 6 separation rule violations: 19
- Phase 4 missing-supported-surface-risk: 19
- Phase 0 RCA skipped on bug-shaped slices: 6 hard-evidence slices, plus 8 CodeRabbit/review-fix-only slices tracked as advisory bug-shaped evidence
- Step 6b output index missing: 19/19
- red-phase-gate skipped: 19/19
- green-phase-gate skipped: 19/19
- process-tree-auditor skipped before CodeRabbit: 19/19
- Overall verdict: FAIL, blocking process violations.

## Binding workflow rules checked

- Phase 4 requires four risk reports: audit, scope, shortcut, and supported-surface.
- Phase 4 requires process-tree-auditor on the risk-gate subtree before Phase 5 consumes reports.
- Phase 6 requires Step 6a contract definition, Step 6b test writer, and Step 6c code writer.
- Step 6b and Step 6c must be separate agent invocations.
- Step 6b must emit `${scratch_dir}/phase6/step6b-output-index.md`.
- Step 6c must read the Step 6b output index and Step 6b test paths before product-code changes, and the log must echo those paths.
- red-phase-gate must run after Step 6b.
- green-phase-gate must run after Step 6c.
- process-tree-auditor must run on the Phase 6 subtree before CodeRabbit.

## Evidence model

- Prompt/log evidence for INIT-105..119 lives outside this worktree at `/home/nes/projects/server-manager/.tmp/init-NNN-pipeline.{md,log}`.
- Prompt/log evidence for INIT-101..104 is missing at `/home/nes/projects/server-manager/.tmp/init-NNN-pipeline.{md,log}`.
- Git evidence comes from the branch history for `feat/init-NNN-*`.
- Risk evidence comes from `plans/risk/init-NNN-{audit,scope,shortcut}.md` where present, or branch-local `.pipeline/risk-{audit,scope,shortcut}.md` for INIT-107, INIT-108, and INIT-117.
- No `step6b-output-index.md`, red-phase gate, green-phase gate, or Phase 6 process-tree audit artifact was found under `/home/nes/projects/server-manager` or this worktree.

## Per-INIT findings table

| INIT | Phase 6 separation | 6b index present | red-phase | green-phase | process-tree | Phase 4 surface-risk | Verdict |
|---|---|---|---|---|---|---|---|
| 101 | VIOLATED — implementation commits exist, but Step 6b/6c prompt-log evidence missing; no separate test/code invocation evidence | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 102 | VIOLATED — implementation commits exist, but Step 6b/6c prompt-log evidence missing; no separate test/code invocation evidence | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 103 | VIOLATED — implementation commits exist, but Step 6b/6c prompt-log evidence missing; no separate test/code invocation evidence | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 104 | VIOLATED — implementation commits exist, but Step 6b/6c prompt-log evidence missing; no separate test/code invocation evidence | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 105 | VIOLATED — prompt explicitly requested one agent run for the full pipeline and Phase 6 implementation | absent | not run | not run | not run | not run; prompt required 3 risk gates | blocking |
| 106 | VIOLATED — prompt explicitly requested one agent run for the full pipeline and Phase 6 implementation | absent | not run | not run | not run | not run; prompt required audit/scope/shortcut only | blocking |
| 107 | VIOLATED — prompt explicitly requested one agent run for the full pipeline and Phase 6 implementation | absent | not run | not run | not run | not run; branch has audit/scope/shortcut only | blocking |
| 108 | VIOLATED — prompt explicitly requested one agent run for the full pipeline and Phase 6 implementation | absent | not run | not run | not run | not run; branch has audit/scope/shortcut only | blocking |
| 109 | VIOLATED — prompt explicitly requested one agent run for the full pipeline and Phase 6 implementation | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 110 | VIOLATED — prompt explicitly requested one agent run for the full pipeline; log reports same invocation implemented and ran CodeRabbit | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 111 | VIOLATED — prompt explicitly requested one agent run for the full pipeline; log reports same invocation implemented, fixed, and reviewed | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 112 | VIOLATED — prompt required full pipeline in one run; log reports one invocation implemented and committed | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 113 | VIOLATED — prompt required full pipeline in one run; log reports one invocation implemented in 6 commits, including test commit | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 114 | VIOLATED — prompt required full pipeline in one run; log reports one invocation implemented 13 commits, including tests and runtime fixes | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 115 | VIOLATED — prompt required full pipeline; log reports one invocation implemented, verified, and fixed CodeRabbit findings | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 116 | VIOLATED — prompt required full pipeline; log reports one invocation implemented, verified, and fixed CodeRabbit findings | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 117 | VIOLATED — prompt required full pipeline; log reports one invocation implemented, verified, and ran CodeRabbit cleanup passes | absent | not run | not run | not run | not run; branch has audit/scope/shortcut only | blocking |
| 118 | VIOLATED — prompt explicitly says one agent run and Phase 6 one commit per slice; log reports one invocation committed 10 slices | absent | not run | not run | not run | not run; only 3 risk files | blocking |
| 119 | VIOLATED/PARTIAL — WIP one-invocation bring-up/test-suite prompt; no formal Phase 4 or Phase 6 substep evidence | absent | not run | not run | not run | not run; stale `.pipeline/risk-*` is INIT-117, not INIT-119 | blocking |

## Per-INIT evidence details

### INIT-101

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-101-pipeline.md` and `.log` are absent.
- Git evidence: `feat/init-101-k3s-control-cluster` contains pipeline commit `7ce20ae`, implementation commits `639dd90` through `d4529d6`, and fix commits `3df0b34`, `aa1cbd9`, `dffa301`, `d9e4a9d`.
- Phase 6 status: partial/nonconforming. Implementation exists, but required Step 6a/6b/6c invocation split is not evidenced.
- Phase 4 status: `plans/risk/init-101-{audit,scope,shortcut}.md` exist and return LOW; `plans/risk/init-101-supported-surface.md` is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent recovery tests unless later watch signals show behavioral mismatch.

### INIT-102

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-102-pipeline.md` and `.log` are absent.
- Git evidence: `feat/init-102-gitops-substrate` contains pipeline commit `07e3afb`, implementation commits `1dc5d4d` through `91fe501`, and CodeRabbit fix commits.
- Phase 6 status: partial/nonconforming. No separate Step 6b/6c evidence.
- Phase 4 status: `plans/risk/init-102-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent Flux/SOPS reconciliation validators.

### INIT-103

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-103-pipeline.md` and `.log` are absent.
- Git evidence: `feat/init-103-infisical-runtime-secrets` contains pipeline commit `08eb7e7`, implementation commits `98b049e` through `691ed69`, and CodeRabbit fix commits.
- Phase 6 status: partial/nonconforming.
- Phase 4 status: `plans/risk/init-103-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent secret-boundary validators.

### INIT-104

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-104-pipeline.md` and `.log` are absent.
- Git evidence: `feat/init-104-object-storage` contains pipeline commit `471a219`, implementation commits `5b812be` through `dd4d5c4`, and CodeRabbit fix commits.
- Phase 6 status: partial/nonconforming.
- Phase 4 status: `plans/risk/init-104-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent object-storage contract and cluster proof validators.

### INIT-105

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-105-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests executing the full implementation pipeline in one agent run; lines 60-68 define 3 risk gates and Phase 6 implementation, not Step 6a/6b/6c separation.
- Log evidence: lines 1-2 show one invocation/session; line 3 reports completion; lines 7-16 list one pipeline commit plus seven implementation slice commits.
- Phase 6 status: partial/nonconforming. One invocation performed implementation and reported harness proof.
- Phase 4 status: prompt line 61 requires only audit, scope, and shortcut; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent TLS/DNS validators and supported-surface review.

### INIT-106

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-106-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests the full implementation pipeline in one agent run; line 54 requires audit/scope/shortcut only; line 59 starts Phase 6 implementation without Step 6a/6b/6c.
- Log evidence: lines 1-3 show one invocation/session and "Implemented INIT-106 end to end"; line 15 records `db745d9 fix: sequence Crossplane app-cluster reconciliation`.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: skipped despite bug-shaped sequencing fix evidence.
- Phase 4 status: `plans/risk/init-106-{audit,scope,shortcut}.md` exist; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; procedure-step violation; silent-success violation.
- Recovery determination: CONTINUE, but write RCA for the sequencing fix if recovery depends on that behavior.

### INIT-107

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-107-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests full pipeline in one agent run; line 45 lists only audit/scope/shortcut risk; line 49 starts Phase 6 implementation without substep split.
- Log evidence: lines 1-3 show one invocation/session and "Implemented and committed"; line 22 says cluster-mode surfaced/fixed two real ordering bugs.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: skipped despite explicit real ordering bugs.
- Phase 4 status: branch-local `.pipeline/risk-audit.md`, `.pipeline/risk-scope.md`, and `.pipeline/risk-shortcut.md` return LOW; no supported-surface artifact.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; procedure-step violation; silent-success violation.
- Recovery determination: CONTINUE with independent cluster-security validators; RCA the ordering bugs before relying on their fixes.

### INIT-108

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-108-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests full pipeline in one agent run; line 47 lists audit/scope/shortcut risk; line 51 starts Phase 6 implementation without substep split.
- Log evidence: lines 1-3 show one invocation/session and "Implemented INIT-108 end to end".
- Phase 6 status: partial/nonconforming.
- Phase 4 status: branch-local `.pipeline/risk-audit.md`, `.pipeline/risk-scope.md`, and `.pipeline/risk-shortcut.md` return LOW; no supported-surface artifact.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent image-registry and delivery validators.

### INIT-109

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-109-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests one full-pipeline run; lines 44-48 define all-LOW risk gates and Phase 6 implementation without supported-surface or Step 6 split.
- Log evidence: lines 1-2 show one invocation/session; line 5 reports total commits; lines 8-13 include docs, feature, and test commits.
- Phase 6 status: partial/nonconforming.
- Phase 4 status: `plans/risk/init-109-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent Buildkite/local-runner validators.

### INIT-110

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-110-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests full pipeline in one agent run; line 22 compresses research through implementation into one deliverable.
- Log evidence: lines 1-3 show one invocation/session and implementation; lines 8-13 include docs, feature, test, and fix commits; line 34 reports CodeRabbit fixes.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: skipped despite bug-shaped ingress issuer/class and private-key-removal evidence.
- Phase 4 status: `plans/risk/init-110-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; procedure-step violation; silent-success violation.
- Recovery determination: CONTINUE only after independent ingress/TLS validators cover the fixed behavior.

### INIT-111

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-111-pipeline.md` and `.log`.
- Prompt evidence: line 3 requests one full-pipeline run; line 22 compresses risk and implementation into one deliverable.
- Log evidence: lines 1-3 show one invocation/session and implementation; lines 11-14 include test plus runtime-policy and storage-project fix commits; line 40 reports CodeRabbit fixes.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: skipped despite runtime-policy and storage-project fix evidence.
- Phase 4 status: `plans/risk/init-111-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; procedure-step violation; silent-success violation.
- Recovery determination: CONTINUE with independent data-plane and backup-precondition validators.

### INIT-112

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-112-pipeline.md` and `.log`.
- Prompt evidence: line 21 requires full pipeline through implementation slices; no supported-surface or Step 6 split is present.
- Log evidence: lines 1-3 show one invocation/session and implementation; line 14 reports contract tests passed.
- Phase 6 status: partial/nonconforming.
- Phase 4 status: `plans/risk/init-112-{audit,scope,shortcut}.md` exist; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent backup/restore validators.

### INIT-113

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-113-pipeline.md` and `.log`.
- Prompt evidence: line 30 requires full pipeline through implementation slices; no supported-surface or Step 6 split is present.
- Log evidence: lines 1-3 show one invocation/session; lines 5-10 include docs, feature, test, and CI commits; lines 21-24 report tests passed.
- Phase 6 status: partial/nonconforming.
- Phase 4 status: `plans/risk/init-113-{audit,scope,shortcut}.md` exist; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent workload deployment validators.

### INIT-114

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-114-pipeline.md` and `.log`.
- Prompt evidence: line 21 requires full pipeline through implementation slices; no supported-surface or Step 6 split is present.
- Log evidence: lines 1-3 show one invocation/session; lines 8-18 include feature, test, and seven runtime-fix commits.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: skipped despite repeated runtime-fix evidence.
- Phase 4 status: `plans/risk/init-114-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; procedure-step violation; silent-success violation.
- Recovery determination: DECOMPOSE for auth-stack recovery because security-sensitive behavior, many runtime fixes, and self-authored validators combine into high provenance risk.

### INIT-115

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-115-pipeline.md` and `.log`.
- Prompt evidence: line 22 says full pipeline; no supported-surface or Step 6 split is present.
- Log evidence: lines 1-3 show one invocation/session; lines 19-21 report focused tests and static harnesses; lines 28-30 report CodeRabbit findings fixed.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: CodeRabbit-fix-only bug-shaped evidence tracked as advisory, not counted in hard RCA total.
- Phase 4 status: `plans/risk/init-115-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: DECOMPOSE for policy/break-glass recovery because policy behavior must be test-first from an independent contract.

### INIT-116

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-116-pipeline.md` and `.log`.
- Prompt evidence: line 22 says full pipeline; no supported-surface or Step 6 split is present.
- Log evidence: lines 1-3 show one invocation/session; lines 12-16 report contract and validation passes; lines 27-30 report CodeRabbit findings fixed.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: CodeRabbit-fix-only bug-shaped evidence tracked as advisory.
- Phase 4 status: `plans/risk/init-116-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: DECOMPOSE for tenant isolation recovery because isolation policy must be independently specified and tested.

### INIT-117

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-117-pipeline.md` and `.log`.
- Prompt evidence: line 27 requires standard full pipeline; no supported-surface or Step 6 split is present.
- Log evidence: lines 1-2 show one invocation/session; lines 10-11 include implementation commits; line 20 reports tests; line 54 reports CodeRabbit cleanup passes and account cap.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: review-finding fixes are tracked as advisory bug-shaped evidence, not counted in the hard RCA total.
- Phase 4 status: branch-local `.pipeline/risk-{audit,scope,shortcut}.md` return LOW; no supported-surface artifact.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: CONTINUE with independent scrape/log/alert validators.

### INIT-118

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-118-pipeline.md` and `.log`.
- Prompt evidence: lines 3-4 request one agent run; lines 159-160 require only three risk files; line 168 says Phase 6 one commit per slice.
- Log evidence: lines 1-3 show one invocation/session and 10 committed slices; lines 21-23 report tests; cluster proof reports no web pods and DNS returning `000`.
- Phase 6 status: partial/nonconforming.
- Phase 0 status: skipped despite failed cluster proof after claimed implementation completion.
- Phase 4 status: `plans/risk/init-118-{audit,scope,shortcut}.md` exist and return LOW; supported-surface risk is absent.
- Classification: role/independence violation; output/artifact violation; gate/termination violation; procedure-step violation; silent-success violation.
- Recovery determination: DECOMPOSE for web UI substrate because this is the first product-surface initiative and cluster proof contradicted done-state.

### INIT-119

- Prompt/log: `/home/nes/projects/server-manager/.tmp/init-119-pipeline.md` and `.log`.
- Prompt evidence: lines 73-100 instruct the same run to diagnose/fix gaps; lines 102-169 instruct the same run to author the permanent E2E suite and CI wiring; line 190 requires one commit per stage/fix/test group.
- Log evidence: lines 1-2 show one invocation/session only. No completion report exists.
- Git evidence: `feat/init-119-fullstack-e2e` has `9b8f0b0 WIP: INIT-119 partial — full-stack bring-up scaffolding + 19 cross-cutting test files`.
- Phase 6 status: partial/skipped in formal terms. Work happened, but no Phase 4, Step 6a/6b/6c, red/green gates, or process-tree audit evidence exists.
- Phase 4 status: no INIT-119 risk artifacts. Current `.pipeline/risk-*` files are stale INIT-117 artifacts.
- Classification: procedure-step violation; role/independence violation; output/artifact violation; gate/termination violation; silent-success violation.
- Recovery determination: DECOMPOSE/restart from contract because the E2E suite is itself the validator layer and was authored in the same fix-oriented run.

## Violation taxonomy (per workflow-execution-violations.md)

### V1 — Phase 6 same-invocation test/code execution

- Formal class: Role/independence violation.
- Severity: blocking.
- Evidence source: companion and inferred.
- Observed in: INIT-101..119.
- Evidence: prompts for INIT-105..119 request one full-pipeline run; logs show one invocation/session completing implementation and validation. INIT-101..104 lack companion prompt/log evidence and therefore fail closed.
- Why load-bearing: Phase 6 says the test writer and code writer must be different agent invocations because same-agent tests mirror implementation.
- Required next action: recovery must use separate Step 6b and Step 6c invocations where the test writer sees only contract/test-intent inputs.

### V2 — Missing Step 6b output index

- Formal class: Output/artifact violation and silent-success / false-completion violation.
- Severity: blocking.
- Evidence source: missing.
- Observed in: INIT-101..119.
- Evidence: no `${scratch_dir}/phase6/step6b-output-index.md` or equivalent found; no prompt/log mentions Step 6b output index.
- Why load-bearing: the output index is the canonical map from proposal risks to emitted tests and residuals.
- Required next action: regenerate test-first output indexes during recovery.

### V3 — Missing Step 6c consumption evidence

- Formal class: Output/artifact violation and silent-success / false-completion violation.
- Severity: blocking.
- Evidence source: missing.
- Observed in: INIT-101..119.
- Evidence: no Step 6c logs echo which Step 6b output index and test paths were read before product-code changes.
- Why load-bearing: without consumption evidence, tests may have been written after or alongside implementation.
- Required next action: Step 6c logs in recovery must list the exact Step 6b index and test paths read before product-code edits.

### V4 — red-phase-gate skipped

- Formal class: Gate/termination violation.
- Severity: blocking.
- Evidence source: missing.
- Observed in: INIT-101..119.
- Evidence: no red-phase-gate reports or log mentions found.
- Why load-bearing: red phase proves the independent tests fail for the intended reason before implementation.
- Required next action: run red-phase-gate after Step 6b in recovery.

### V5 — green-phase-gate skipped

- Formal class: Gate/termination violation.
- Severity: blocking.
- Evidence source: missing.
- Observed in: INIT-101..119.
- Evidence: no green-phase-gate reports or log mentions found.
- Why load-bearing: green phase proves Step 6c made independent tests pass without mutating test intent.
- Required next action: run green-phase-gate after Step 6c in recovery.

### V6 — Phase 6 process-tree-auditor skipped before CodeRabbit

- Formal class: Gate/termination violation and silent-success / false-completion violation.
- Severity: blocking.
- Evidence source: missing.
- Observed in: INIT-101..119.
- Evidence: no Phase 6 process-tree audit artifact exists before CodeRabbit; logs for INIT-110, INIT-111, INIT-115, INIT-116, INIT-117 show CodeRabbit activity without Phase 6 process-tree evidence.
- Why load-bearing: CodeRabbit review is not a substitute for firstness or invocation separation.
- Required next action: run process-tree-auditor on the Phase 6 subtree before CodeRabbit in recovery.

### V7 — Phase 4 supported-surface risk missing

- Formal class: Procedure-step violation and output/artifact violation.
- Severity: blocking.
- Evidence source: companion and missing.
- Observed in: INIT-101..119.
- Evidence: every available Phase 4 prompt/artifact uses audit/scope/shortcut only; no `init-NNN-supported-surface.md` exists. INIT-119 has no valid INIT-119 risk artifacts.
- Why load-bearing: the current workflow requires supported-surface risk to evaluate value, migration, rollback, observability, and adjacent user-reachable paths.
- Required next action: run supported-surface risk for any recovered proposal before implementation.

### V8 — Phase 4 process-tree-auditor skipped

- Formal class: Gate/termination violation.
- Severity: blocking for new downstream consumption; historical advisory for already-landed lower-risk substrate if recovery chooses CONTINUE.
- Evidence source: missing.
- Observed in: INIT-101..119.
- Evidence: no risk-gate process-tree audit artifacts found.
- Why load-bearing: Phase 5 consumed risk outputs without proof that the required fanout ran as required.
- Required next action: include Phase 4 process-tree audit in recovered slices.

### V9 — Phase 0 RCA skipped on bug-shaped work

- Formal class: Procedure-step violation and evidence/grounding violation.
- Severity: blocking where the bug fix is part of the recovery target; advisory where the evidence is CodeRabbit-only and not part of the next recovery decision.
- Evidence source: companion and git history.
- Hard-evidence slices: INIT-106, INIT-107, INIT-110, INIT-111, INIT-114, INIT-118.
- Advisory CodeRabbit/review-fix-only slices: INIT-101, INIT-102, INIT-103, INIT-104, INIT-105, INIT-115, INIT-116, INIT-117.
- Why load-bearing: bug-shaped fixes were applied without a separate RCA artifact that explains root cause before repair.
- Required next action: if recovery depends on a prior bug fix, write a narrow RCA artifact before reimplementation.

## Decompose-trigger status (per audit-history.md)

### Layer A — Environment and control-cluster substrate, INIT-101..106

- Determination: CONTINUE.
- Reason: Process firstness is broken, but the surfaces are mostly declarative infrastructure and harnessable runtime behavior. The existing state can be kept as an implementation candidate if independent recovery tests are written from the contract and run against it.
- Required recovery: supported-surface risk, Step 6b output index, red/green gates, and Phase 6 process-tree audit for any touched recovery slice.
- Decompose trigger: fires if independent tests reveal hidden assumptions in channel schema, k3d/k3s behavior, secret boundaries, object-storage behavior, TLS/DNS issuance, or Crossplane reconciliation.

### Layer B — Security baseline and delivery substrate, INIT-107..113

- Determination: CONTINUE with named watch signals.
- Reason: The implementation-choice surface is broader, but much of the behavior can be validated by black-box cluster/harness evidence. INIT-107, INIT-110, and INIT-111 require RCA notes for the known ordering/runtime fixes before those fixes are relied on.
- Required recovery: independent cluster-security, registry, CI, ingress, data-plane, backup, and app-workload validators.
- Decompose trigger: fires if independent tests cannot be written without consulting implementation internals, or if supported-surface review finds non-positive value or invalidated assumptions.

### Layer C — Auth, policy, and tenant isolation, INIT-114..116

- Determination: DECOMPOSE.
- Reason: These are security-sensitive and policy-sensitive surfaces, with multiple runtime-fix commits and self-authored validators. The risk of tests encoding the implementation rather than the intended access contract is high enough to rebuild the recovery slice from contract.
- Required recovery: write a new contract, run independent Step 6b for access/auth/tenant tests, prove red, then separate Step 6c implementation.
- Continue condition: only possible if an external authoritative policy spec already fixes the behavior and independent tests pass without implementation-derived assumptions.

### Layer D — Observability, INIT-117

- Determination: CONTINUE.
- Reason: Observability can be externally validated by scrape targets, metrics text, logs, dashboards, and alert rules. Process firstness remains broken, but black-box validators are likely enough unless the recovery work changes alert semantics.
- Required recovery: independent scrape/log/alert tests plus supported-surface risk.
- Decompose trigger: fires if dashboard/alert semantics depend on implementation-only assumptions.

### Layer E — Product web surface, INIT-118

- Determination: DECOMPOSE.
- Reason: This is the first product-surface initiative, has high implementation-choice latitude, and the logged cluster proof contradicted done-state (`No resources found` and curl `000`).
- Required recovery: restart Phase 6 from contract, with independent tests for API identity, auth-gated route behavior, build/toolchain, and cluster web route proof.
- Continue condition: only if a fresh independent test-first run passes against the existing code without changes and supported-surface risk returns LOW with positive value.

### Layer F — Full-stack E2E validator suite, INIT-119

- Determination: DECOMPOSE.
- Reason: INIT-119 is itself the validator layer. A same-run diagnose/fix/test-suite authoring process cannot be treated as independent validation of the stack.
- Required recovery: freeze the intended E2E contract first, have a separate Step 6b test agent author the suite and output index, prove red or documented environment skips, then have a separate Step 6c fix/code agent repair implementation.
- Continue condition: none for the current WIP commit as canonical validator source.

## Watch signals

- A previously violated Phase 6 may be acceptable to CONTINUE when an independent Step 6b test suite can be written from proposal/contract text alone and passes the current implementation without product-code edits.
- A layer is likely wrong-shaped when independent tests require implementation archaeology to know what behavior to assert.
- A layer is likely wrong-shaped when the prior proposal leaves multiple valid behaviors open and the existing tests choose the behavior the implementation happened to take.
- A layer is likely wrong-shaped when prior logs mention "fixed" runtime behavior but no RCA explains the original failure path.
- A layer is likely wrong-shaped when supported-surface risk finds non-positive value, missing rollback, missing observability, or invalidated assumptions.
- A layer is likely acceptable to CONTINUE when black-box cluster proof validates the exact user/supported path and no implementation-only test details are needed.
- A layer is likely acceptable to CONTINUE when all validators are externally observable: Kubernetes resources, HTTP status, metrics scrape, object round trip, DNS resolution, or backup restore.
- A layer requires DECOMPOSE when the validator itself was produced by the same fix-oriented run, as in INIT-119.
- A layer requires DECOMPOSE when the surface is access-control, tenant isolation, or user-facing product behavior and the intended behavior is not fully pinned by a separate contract.

## Recommendation summary

- CONTINUE with recovery tests: INIT-101, INIT-102, INIT-103, INIT-104, INIT-105, INIT-106, INIT-107, INIT-108, INIT-109, INIT-110, INIT-111, INIT-112, INIT-113, INIT-117.
- DECOMPOSE before relying on current state: INIT-114, INIT-115, INIT-116, INIT-118, INIT-119.
- For every CONTINUE layer, do not treat existing tests as Phase 6 firstness evidence. Treat them as regression candidates only after a new independent Step 6b output index maps proposal risks to validators.
- For every DECOMPOSE layer, preserve the current implementation as research input only; do not let the Step 6b test writer see it.
- Before any recovered slice reaches CodeRabbit, run red-phase-gate, green-phase-gate, and process-tree-auditor on the Phase 6 subtree.
