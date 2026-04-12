# Phase 1 Foundation v2 — Shortcut Risk Assessment

Date: 2026-04-11
Assessed by: claude-opus (shortcut risk agent)
Input: `plans/proposals/phase1-foundation-v2.md`, `plans/research/phase1-environments-and-benchmarks.md`, `AGENTS.md`, current `infra/` and `k8s/` draft code

## Verdict: LOW

The proposal does not take shortcuts. It is unusually explicit about identifying existing shortcuts in the codebase and requiring their removal as part of the definition of done. The few areas that could drift toward shortcut territory are flagged below with mitigations.

---

## Findings

### 1. Hetzner storage class leftovers — identified but not yet fixed (Severity: LOW)

**What**: `k8s/base/monitoring/helmrelease.yaml` contains `storageClassName: hcloud-volumes` on three PVCs (Grafana, Prometheus, Alertmanager). This is a Hetzner storage class that will not work on Vultr.

**Why this is LOW, not MEDIUM**: The proposal explicitly identifies this as a "direct provider migration bug" (§3, §7) and lists its replacement with `vultr-block-storage` as a hard requirement in the definition of done (§11). The overlays patch retention and sizes but do not patch the storage class, so the fix must happen in base or overlays — but the proposal knows this.

**Risk**: Implementation treats the proposal as a wish list and ships without actually replacing the storage class references.

**Recommendation**: Implementation must grep all `k8s/` manifests for `hcloud` before declaring Phase 1 complete. A checklist item, not a structural change.

---

### 2. Mechanical autoscaling placeholder still in code (Severity: LOW)

**What**: `infra/cluster.tf` computes `min_nodes = var.worker_count` and `max_nodes = var.worker_count * 2`. This is a formula, not a policy. The proposal (§3) correctly calls this out and specifies explicit per-environment bounds: dev 1/2, staging 3/6, production 3/5.

**Why this is LOW**: The proposal replaces the formula with concrete numbers. The code hasn't been updated yet, but that is implementation sequencing, not a proposal shortcut.

**Risk**: Implementation keeps the formula because it "works" and the explicit bounds from the proposal are never encoded. Production ends up with max=6 instead of the proposed max=5.

**Recommendation**: Implementation must move `min_nodes` and `max_nodes` into per-environment tfvars rather than computing them from `worker_count`. The proposal already specifies the values.

---

### 3. Stale Kubernetes version default (Severity: LOW)

**What**: `infra/variables.tf` defaults to `v1.31.0+1`. The proposal (§3) identifies this as stale — Vultr supports 1.33.x through 1.35.x as of March 2026 — and requires pinning to a current line at implementation start.

**Why this is LOW**: The proposal is explicit about the correction. This is not a hidden assumption.

**Risk**: None beyond normal implementation discipline.

**Recommendation**: Pin the version in the first implementation commit. Do not leave the stale default in place with a comment saying "update later."

---

### 4. Single-cluster Flux root not yet restructured (Severity: LOW)

**What**: Flux bootstrap currently lives at `k8s/base/flux-system/` — a single root that cannot cleanly serve three independent clusters. The proposal (§5) requires moving to `k8s/clusters/{dev,staging,production}/flux-system/` with per-cluster root Kustomizations.

**Why this is LOW**: The proposal calls this "the biggest structural correction in v2" and provides a complete target layout. The current code is a draft, and the proposal does not pretend the draft is correct.

**Risk**: This is the restructuring most likely to be deferred during implementation because it touches the most files and requires re-bootstrapping Flux. If deferred, the multi-environment story becomes cosmetic — overlays exist, but Flux reconciles from one root.

**Recommendation**: This restructuring should be the first implementation task, not the last. If it is deferred, the environment model is an illusion. The proposal already says this (§13, risk 5), but it bears repeating.

---

### 5. sealed-secrets: bootstrap vs. permanent (Severity: LOW)

**What**: The proposal uses sealed-secrets for Phase 1 secret management. This could become a permanent solution by inertia.

**Why this is LOW**: The proposal (§6) explicitly treats sealed-secrets as bootstrap-only and defines a five-step migration path to Infisical. It also requires backing up the controller key immediately after bootstrap — a sign the authors understand the operational cost of sealed-secrets. The proposal does not confuse "good enough for now" with "permanent."

**Risk**: Infisical migration never happens, and sealed-secrets becomes the permanent secret manager without anyone deciding that.

**Recommendation**: No change to the proposal. The migration is correctly scoped to Phase 2+. The key backup requirement is the right operational hygiene for a bootstrap tool.

---

### 6. Benchmarking definition vs. enforcement (Severity: LOW)

**What**: The proposal (§8) defines benchmark metrics, tooling (k6), storage paths, and pass/fail gates but explicitly does not enforce benchmarking as a release blocker in Phase 1.

**Why this is LOW**: This is not "we'll figure it out later." The proposal defines what to measure, where to store results, what constitutes a regression, and when benchmarks are required (staging promotion path). It defers enforcement because there are no real application workloads to benchmark yet. That is honest scoping, not a shortcut.

**Risk**: The definition exists on paper but k6 is never actually set up, and Phase 2 inherits no working benchmark infrastructure.

**Recommendation**: The definition of done (§11) already requires "the benchmark definition exists, k6 is chosen, and an artifact storage path is defined." To avoid paper-only benchmarking, implementation should include at least one trivial k6 script that runs against the dev cluster health endpoint and stores output in the defined artifact path. This proves the pipeline works without requiring real workloads.

---

### 7. No module structure in OpenTofu code yet (Severity: LOW)

**What**: The proposal (§4) specifies a `modules/vke-cluster/` reusable module, but the current code has a flat `infra/` directory with `cluster.tf`, `main.tf`, and `variables.tf` at the root. Each environment directory contains only tfvars and backend config, not its own `main.tf` root module.

**Why this is LOW**: The proposal specifies the target layout clearly. The current code is a draft that predates the proposal. The gap is implementation work, not a design shortcut.

**Risk**: Implementation keeps the flat structure and uses the same root module with different tfvars, which technically works but makes state isolation less explicit and module reuse harder.

**Recommendation**: Follow the proposal layout. Each environment should be its own root module calling a shared `modules/vke-cluster/` module. This is not over-engineering — it is the standard pattern for multi-environment OpenTofu.

---

### 8. Dev overlay does not patch storage class (Severity: LOW)

**What**: The dev overlay (`k8s/overlays/dev/kustomization.yaml`) patches Prometheus retention and storage sizes but does not patch the `hcloud-volumes` storage class. If the storage class fix happens only in base, this is fine. If it requires per-environment patching (e.g., different storage classes per environment), the overlays need updating too.

**Why this is LOW**: The proposal specifies `vultr-block-storage` for all environments in Phase 1 (§3). The fix belongs in base, making overlay patches unnecessary for storage class.

**Risk**: None, as long as the base fix happens.

**Recommendation**: Fix `hcloud-volumes` → `vultr-block-storage` in `k8s/base/monitoring/helmrelease.yaml`. No overlay patches needed for storage class.

---

## Overall Assessment

The proposal is thorough, self-aware, and does not introduce shortcuts. Its defining characteristic is that it *identifies existing shortcuts in the code and requires their removal*. The Hetzner storage class bug, the mechanical autoscaling formula, the stale Kubernetes version, and the single-cluster Flux root are all called out explicitly with specific corrections.

The deferred items (benchmark enforcement, Infisical migration, CI-blocking video QA) are deferred with clear reasoning and concrete Phase 2 handoff requirements, not vague promises. The proposal distinguishes between "not yet needed" and "not yet thought through."

The risk is not in the proposal itself but in implementation discipline: will the corrections the proposal requires actually be made, or will the draft code ship with comments saying "TODO: fix storage class"?

## What LOW Requires

For this assessment to remain LOW through implementation:

1. All `hcloud-volumes` references in `k8s/` must be replaced with `vultr-block-storage` before Phase 1 is declared complete
2. Autoscaler bounds must be explicit per-environment values in tfvars, not computed from `worker_count`
3. The Kubernetes version must be pinned to a currently supported VKE line at implementation start
4. Flux must be restructured to per-cluster roots — this is non-negotiable for the environment model to be real
5. The sealed-secrets controller key must be backed up as part of bootstrap, not deferred
6. At least one trivial k6 run must execute against dev and store output in the defined artifact path, proving the benchmark pipeline works
7. The OpenTofu layout must use per-environment root modules, not a shared root with different tfvars
8. A grep for `hcloud`, `hetzner`, and other provider-specific terms must pass clean across all cluster-facing manifests and documentation before Phase 1 closes
