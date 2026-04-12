# Phase 1 Scope Risk Assessment

**Proposal**: `plans/proposals/phase1-foundation.md`
**Assessed by**: claude-opus (scope risk)
**Date**: 2026-04-11

---

## Verdict: LOW

---

## Findings

### 1. Hosting decision assumed but not locked (Severity: MEDIUM)

The proposal assumes Hetzner throughout — cluster topology, object storage, CSI, cloud controller, cost model. However, `platform-decisions-overlay.md` marks hosting as **OPEN** with "user decision needed." If the user later picks Vultr, every provider-specific section (§3, §4 remote state, §9 cost model) must be rewritten.

**Recommendation**: This is not a proposal defect — the proposal explicitly designs for Hetzner, and the user should lock the hosting decision before implementation begins. Flag as a pre-implementation gate, not a proposal revision.

### 2. Sealed-secrets diverges from unified index's Infisical expectation (Severity: LOW)

The unified index Phase 1 lists `infisical-secrets` as a primary unit anchor. The proposal replaces it with `sealed-secrets` and defers Infisical. This is a deliberate, well-justified simplification: Infisical adds stateful complexity before the cluster is proven healthy.

**Recommendation**: Accept. The proposal's §6 evaluation is thorough. The sealed-secrets-to-Infisical migration path is a Phase 2/3 concern and the proposal correctly identifies this tradeoff. The unified index should be updated to reflect this change once the proposal is approved.

### 3. Cluster sizing targets future phases, not just Phase 1 (Severity: LOW)

The proposed 3×CPX21 + 3×CPX31 topology (~EUR 84/mo compute) is sized for "the expected non-optional platform" including future Harbor, PostgreSQL, Buildkite, etc. For Phase 1 alone (Flux, sealed-secrets, kube-prometheus-stack), this is over-provisioned.

**Recommendation**: Accept. Over-provisioning at this scale (tens of EUR/mo, not hundreds) avoids a disruptive resize when Phase 2 lands. The proposal is transparent about the reasoning (§3). This is good forward planning, not scope creep.

### 4. Staging structure without staging provisioning (Severity: LOW)

The proposal creates directory structure for both `production/` and `staging/` in OpenTofu and Flux layouts but explicitly does not provision staging. This is the right call — structure is cheap, infrastructure is not.

**Recommendation**: Accept as-is. No action needed.

### 5. Kong and Buildkite correctly deferred (Severity: LOW — positive finding)

The proposal explicitly defers Kong to Phase 2 and treats Buildkite agents as a Phase 2 consumer. This is correct scope control. The unified index's Phase 1 does not require either, and the proposal resists the temptation to "prepare" them beyond repo structure.

**Recommendation**: Accept. This is the proposal's strongest scope decision.

### 6. Definition of done is concrete and testable (Severity: LOW — positive finding)

The 10-point definition of done (§10) is specific, falsifiable, and covers all Phase 1 deliverables: cluster access, OpenTofu reproducibility, Flux reconciliation (both modes), secrets path, observability health, object storage connectivity, and persistent volume path. No ambiguous "basically working" criteria.

**Recommendation**: Accept. This is a strength.

### 7. Observability scope is appropriately minimal (Severity: LOW)

The proposal installs kube-prometheus-stack and defers Loki. For a phase with no application workloads, centralized logging adds cost without value. The alert baseline (§7) covers the right failure modes for an empty cluster.

**Recommendation**: Accept. Loki deferral is well-justified.

### 8. No CI/CD pipeline for the Phase 1 infrastructure itself (Severity: LOW)

The proposal mentions "CI and operator workstations" for running OpenTofu but does not specify how Phase 1 infrastructure changes are applied after bootstrap. Since Buildkite agents are deferred, the initial OpenTofu workflow is operator-driven.

**Recommendation**: Accept for Phase 1. An operator running `tofu plan` and `tofu apply` from a workstation is appropriate for bootstrap. The proposal correctly notes that Buildkite agents are a Phase 2 addition, and Phase 2 should include a CI-driven OpenTofu workflow.

### 9. No explicit rollback or disaster recovery for the cluster itself (Severity: LOW)

The proposal does not cover what happens if the cluster bootstrap fails partway or if a control-plane node is lost during initial setup. Velero is explicitly out of scope.

**Recommendation**: Accept. At Phase 1, the cluster is empty — the recovery path is "re-run OpenTofu." The proposal's version-pinning discipline (§3) and HA control plane reduce the likelihood of partial failure. DR becomes meaningful in Phase 2 when stateful workloads exist.

---

## Overall Assessment

This is a well-disciplined Phase 1 proposal. Its primary strength is knowing what to exclude: Kong, Buildkite agents, Loki, Infisical, public endpoints, and the entire auth/data/security stack are all correctly deferred. The scope matches what "foundation bootstrap" actually means — cluster, GitOps, secrets, storage, observability — without pulling in Phase 2 consumers.

The one material pre-implementation dependency is the hosting decision (Finding 1). The proposal is written for Hetzner; if the user picks Vultr, the provider-specific sections need revision but the architectural shape survives.

The sealed-secrets divergence from the unified index (Finding 2) is a strength, not a risk. The proposal correctly identifies that bootstrapping a stateful secret manager before the cluster is stable is backwards.

The proposal does not create downstream problems. Phase 2's dependency list (§12) is explicit and achievable given Phase 1's deliverables. No Phase 1 decision forecloses a later phase or creates technical debt that compounds.

The phasing is correct. Nothing in Phase 1 belongs in Phase 2, and nothing critical for Phase 1 has been pushed to Phase 2.

---

## What LOW Requires

- **Hosting decision locked before implementation.** The user must confirm Hetzner (or Vultr, triggering a proposal revision) before any OpenTofu code is written.
- **Unified index updated.** Once approved, `unified-platform-index.md` Phase 1 should reflect sealed-secrets replacing Infisical and the Hetzner-specific topology.
- **No scope additions during implementation.** The proposal's strength is its restraint. Adding "just one more thing" (Loki, Kong prep, Buildkite agent namespace) during implementation would undermine the scope discipline that makes this LOW risk.
