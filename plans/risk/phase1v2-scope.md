# Scope Risk Assessment — Phase 1 Foundation v2

**Proposal**: `plans/proposals/phase1-foundation-v2.md`
**Research**: `plans/research/phase1-environments-and-benchmarks.md`
**Date**: 2026-04-11

---

## Verdict: LOW

---

## Findings

### 1. Environment model is correctly asymmetric — no scope excess

**Severity**: None (positive finding)

The 3-environment model is correctly scoped. Dev is persistent and cheap ($13/mo). Production is persistent. Staging is explicitly on-demand and ephemeral. The proposal does not fall into the common trap of building three identical always-on clusters. The promotion policy (default `dev -> production`, elevated `dev -> staging -> production`) is proportionate for a one-person-plus-agents team and avoids mandatory staging ceremony for routine changes.

**No action required.**

### 2. Benchmarking scope is definition-only — correctly deferred

**Severity**: None (positive finding)

The proposal defines benchmark families, selects k6, specifies artifact storage paths, and establishes a regression-vs-baseline gate policy — but explicitly defers building a benchmark suite or enforcing gates until real application workloads exist. This is the right call. Building benchmark infrastructure against imaginary endpoints would be fake certainty.

**No action required.**

### 3. Video QA is proof-of-concept only — correctly deferred

**Severity**: None (positive finding)

The proposal limits LLM video QA to a single advisory Playwright-to-Gemini run in dev. It explicitly excludes CI-blocking enforcement, broad prompt libraries, and production gating. This is proportionate. The UI does not exist yet; a single PoC run validates the pipeline shape without over-investing.

**No action required.**

### 4. Draft code has structural misalignment with proposal — must be corrected

**Severity**: MEDIUM (implementation risk, not scope risk)

The proposal identifies these correctly, but they remain unfixed in the current codebase:

- **Hetzner storage classes**: `k8s/base/monitoring/helmrelease.yaml` references `hcloud-volumes` three times (Grafana, Prometheus, Alertmanager). These will fail on Vultr. The proposal calls for `vultr-block-storage`.
- **Single-cluster Flux root**: `k8s/base/flux-system/` is a single bootstrap path. The proposal requires per-cluster roots under `k8s/clusters/{dev,staging,production}/`. The current overlay structure (`k8s/overlays/*`) references `../../base/` but is not wired as a Flux reconciliation target per cluster.
- **Mechanical autoscaling**: `cluster.tf` uses `min_nodes = var.worker_count` and `max_nodes = var.worker_count * 2` for all environments. The proposal specifies explicit per-environment bounds (dev: 1/2, staging: 3/6, production: 3/5). These are not yet parameterized in `variables.tf`.
- **Stale Kubernetes version**: `variables.tf` defaults to `v1.31.0+1`. Vultr's supported lines are 1.33.x–1.35.x as of March 2026.

**Recommendation**: These are implementation tasks, not scope problems. They are already identified in the proposal's definition of done. The risk is that they get deprioritized during implementation — they should be first, not last.

### 5. No module extraction yet in OpenTofu

**Severity**: LOW

The proposal recommends `infra/modules/vke-cluster/` and `infra/modules/object-storage/`, but the current code is a flat single root (`infra/main.tf`, `infra/cluster.tf`, `infra/variables.tf`) with per-environment `.tfvars` and `.tfbackend` files. The flat structure technically works for Phase 1 because the environments share the same resource shape. Module extraction is a code-quality improvement, not a Phase 1 blocker.

**Recommendation**: Accept the flat structure for Phase 1 if implementation time is tight. Extract modules before Phase 2 adds divergent resource types per environment.

### 6. Dev storage sizing may hit Vultr minimums

**Severity**: LOW

The dev overlay patches Prometheus storage to 2Gi and Grafana to 1Gi. Vultr NVMe block storage has a 10GB minimum volume size. Requesting less than 10Gi in a PVC on `vultr-block-storage` will either round up to 10GB (billed at $1/mo) or fail provisioning. The cost impact is small (~$3/mo for three 10GB volumes instead of the requested sizes), but the manifests should request what will actually be provisioned.

**Recommendation**: Set dev PVC requests to 10Gi to match the Vultr minimum. The cost difference is negligible and avoids provisioning surprises.

### 7. Cost model is realistic and conservative

**Severity**: None (positive finding)

The $108/mo baseline uses verified April 2026 Vultr pricing. The model correctly accounts for Vultr's 10GB NVMe minimum, free VKE control plane, and $10/mo per load balancer. The amortized staging cost of ~$13/mo is honest — it depends on discipline, and the proposal explicitly flags the risk of staging becoming permanent (~$159/mo worst case). Buildkite at $0/mo on Personal plan is accurate for Phase 1 scope.

**No action required.**

### 8. Missing: explicit dev Discord guild decision

**Severity**: LOW

The proposal requires per-environment Discord bot tokens and guild IDs. Staging has a known guild (`1492663622458151003` from `.tmp/beta-guild.txt`). Production uses the Humility guild. But the dev guild target is unresolved — the proposal says "if a separate dev guild does not exist yet, dev must not silently target production." This is a configuration gap, not a scope gap. It does not block cluster provisioning, but it blocks the definition-of-done item "distinct Discord configuration per environment."

**Recommendation**: Create or designate a dev guild before calling Phase 1 complete. This is a 5-minute Discord action, not an engineering task.

### 9. No Phase 2 blockers introduced

**Severity**: None (positive finding)

The proposal explicitly lists what Phase 2 needs from Phase 1 (section 12) and the definition of done covers each dependency. Sealed-secrets is positioned as bootstrap-only with a clear Infisical migration path. The API-first principle is stated as a cross-cutting rule without premature implementation. No architectural decisions in this proposal would need to be unwound for Phase 2.

**No action required.**

### 10. Scope boundary is well-defined — nothing critical is missing, nothing included should be deferred

**Severity**: None (positive finding)

The proposal explicitly excludes: full benchmark suite, CI-blocking video QA, Infisical, broad public ingress, custom CNI work. These are all correctly deferred. The included items (VKE provisioning, Flux restructuring, sealed-secrets, monitoring, benchmark definition, one PoC video QA run) are all necessary for the foundation substrate and none are premature.

**No action required.**

---

## Overall Assessment

The proposal is well-scoped for Phase 1. The 3-environment model is the right shape — asymmetric by design, with staging as an on-demand lane rather than a permanent clone. Benchmarking and video QA are included at the right level of commitment: definitions and proof-of-concept, not premature suites. The cost model is grounded in verified pricing and honestly flags the main budget risk (staging permanence).

The primary risk is not scope — it is implementation fidelity. The draft code has four known misalignments with the proposal (Hetzner storage classes, single-cluster Flux root, mechanical autoscaling, stale K8s version). The proposal identifies all four, but the gap between "identified in the proposal" and "fixed in the code" is where Phase 1 could stall. These should be the first implementation tasks, not cleanup items.

No items need to be added to Phase 1 scope. No items need to be removed. The scope is correctly sized.

---

## What LOW Requires

LOW holds if all of the following remain true during implementation:

1. Staging is treated as on-demand — not left running by default
2. The four code-vs-proposal misalignments (storage classes, Flux roots, autoscaling bounds, K8s version) are fixed early in implementation, not deferred
3. Dev PVC requests are adjusted to respect Vultr's 10GB NVMe minimum
4. A dev Discord guild is designated before Phase 1 is declared complete
5. The benchmark deliverable remains definition + runner + storage path — no premature suite construction
6. Video QA remains a single advisory PoC run — no CI enforcement creep
7. Module extraction is accepted as a Phase 2 prerequisite if skipped in Phase 1
