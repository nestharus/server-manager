# Audit Risk Assessment — Phase 1 Foundation v2

**Proposal:** `plans/proposals/phase1-foundation-v2.md`
**Research:** `plans/research/phase1-environments-and-benchmarks.md`
**Assessed by:** claude-opus (audit risk)
**Date:** 2026-04-11

---

## Verdict: MEDIUM

---

## Findings

### 1. Terraform state credentials lack gitignore protection — MEDIUM

**Issue:** `.tfvars` files containing environment configuration are committed to Git. While the current `.tfvars` files do not contain secrets (the Vultr API key is passed via `var.vultr_api_key` at runtime), there is no `.gitignore` rule for `*.tfstate`, `*.tfstate.backup`, `*.tfvars` (for override files), or `terraform.tfstate.d/`. If a developer runs `tofu apply` locally and a `.tfstate` file is generated (even as a cache), it could be committed. State files contain sensitive outputs including the base64-encoded kubeconfig (`output "kubeconfig"` in `cluster.tf`), which grants full cluster access.

**Severity:** MEDIUM

**Recommendation:** Add `*.tfstate`, `*.tfstate.backup`, `*.tfstate.d/`, `.terraform/`, and `crash.log` to `.gitignore`. The remote S3 backend means local state files should not normally exist, but defense-in-depth requires the exclusion.

### 2. Kubeconfig output is sensitive but lacks access boundary documentation — LOW

**Issue:** `infra/cluster.tf` outputs `kubeconfig` marked `sensitive = true`, which is correct. However, the proposal does not specify how kubeconfig material is distributed, stored, or rotated per environment. Anyone with the kubeconfig has full cluster-admin access. The proposal mentions "credentials restricted to named operators and CI" for state bucket access but does not extend this discipline to kubeconfig handling.

**Severity:** LOW

**Recommendation:** Document kubeconfig distribution and storage policy as part of the bootstrap runbook. Kubeconfigs should not be stored in shared locations, CI artifact caches, or shell history.

### 3. Vultr API key injection path is underspecified — LOW

**Issue:** `infra/variables.tf` declares `vultr_api_key` as sensitive. `infra/main.tf` passes it directly to the provider. The proposal says sensitive values are "injected at runtime via environment variables or secret files outside Git" but does not specify whether this is `TF_VAR_vultr_api_key`, a `.tfvars` override, or a CI secret. If operators default to passing it as a CLI flag, it appears in shell history.

**Severity:** LOW

**Recommendation:** Standardize on `TF_VAR_vultr_api_key` environment variable injection. Document that CLI `-var` flags must not be used for secrets due to shell history exposure.

### 4. Hetzner storage class residue — provider misconfiguration bug — MEDIUM

**Issue:** The proposal correctly identifies this, but the code is still broken. `k8s/base/monitoring/helmrelease.yaml` references `hcloud-volumes` on lines 35, 44, and 58. This storage class does not exist on Vultr. If manifests are applied to a VKE cluster as-is, all monitoring PVCs will fail with `storageclass "hcloud-volumes" not found`, leaving Prometheus, Grafana, and Alertmanager unable to start. This is not a security vulnerability per se, but a misconfiguration that could lead operators to bypass GitOps and manually create resources, creating configuration drift and potential secret exposure.

**Severity:** MEDIUM (operational integrity, not direct credential risk)

**Recommendation:** Replace all three `hcloud-volumes` references with `vultr-block-storage` before any cluster provisioning. This is a blocking prerequisite.

### 5. Grafana admin secret bootstrap has a plaintext window — LOW

**Issue:** The `grafana-admin-secret.yaml` file is a placeholder with instructions for creating a SealedSecret. The workflow requires: (1) create a plaintext secret via `kubectl create secret generic`, (2) pipe it to `kubeseal`, (3) commit the sealed output. Step 1 creates a plaintext secret in the cluster temporarily. This is standard sealed-secrets workflow and the plaintext Kubernetes Secret exists only transiently. The instructions correctly say "DO NOT commit plaintext credentials to this file."

**Severity:** LOW

**Recommendation:** The bootstrap instructions are sound. Add a note to delete the local YAML intermediate if the operator saves it to disk during the sealing process. Consider adding the sealed-secrets public cert to the repo (it is not sensitive) so operators don't need cluster access to seal secrets for future rotations.

### 6. Sealed-secrets controller key backup is identified but not enforced — MEDIUM

**Issue:** The proposal correctly identifies sealed-secrets key backup as a mandatory bootstrap operation (Section 6, last paragraph). However, there is no runbook, script, or checklist artifact in the code that enforces this. The sealed-secrets controller generates an encryption key at first startup. If the controller pod is deleted or the cluster is recreated without backing up this key, all existing SealedSecrets become undecryptable. This is a data-integrity risk for all secrets in the cluster.

**Severity:** MEDIUM

**Recommendation:** Create a documented bootstrap runbook that includes `kubectl get secret -n sealed-secrets -l sealing-key -o yaml > sealed-secrets-key-backup.yaml` immediately after controller startup, with explicit instructions for secure offline storage. This should be a hard gate in the definition of done, not just a prose mention.

### 7. Flux bootstrap path is single-cluster — structural security concern — LOW

**Issue:** The current Flux bootstrap README (`k8s/base/flux-system/README.md`) shows `--path=k8s/base/flux-system`, a single shared root. The proposal mandates per-cluster roots (`k8s/clusters/<env>/flux-system`). If the current single-root pattern is accidentally used for multiple clusters, all clusters reconcile the same path, meaning a dev change immediately affects production. This is a blast-radius concern rather than a credential exposure, but it could cause production outages from dev experimentation.

**Severity:** LOW (proposal correctly identifies and mandates the fix)

**Recommendation:** The proposal's per-cluster root structure is the correct fix. Ensure the old `k8s/base/flux-system/README.md` is updated or removed during implementation to prevent operators from following stale bootstrap instructions.

### 8. No network policy for sealed-secrets or monitoring namespaces — LOW

**Issue:** The proposal notes that VKE ships with Calico and that Phase 1 will not add custom CNI work. However, no `NetworkPolicy` resources are defined for the `sealed-secrets` or `monitoring` namespaces. In the default Kubernetes model, all pods can communicate with all other pods. The sealed-secrets controller processes decryption requests from any namespace. While this is standard for a bootstrap phase, it means any compromised workload in the cluster could query the sealed-secrets controller or scrape Prometheus data.

**Severity:** LOW (acceptable for Phase 1 bootstrap scope; Calico is available for later hardening)

**Recommendation:** Note as a Phase 2 hardening item. Add `NetworkPolicy` resources to restrict ingress to sealed-secrets and monitoring namespaces once application workloads exist.

### 9. Benchmark and LLM video QA data handling — object storage security — LOW

**Issue:** The proposal specifies benchmark artifacts and video QA recordings stored at `s3://server-manager-artifacts/benchmarks/<environment>/<date>/<git-sha>/`. Video QA clips may contain UI state including form data visible in the recording. The proposal correctly separates artifact storage from Terraform state storage by prefix. However, Vultr Object Storage buckets are private by default only if no public ACL is set. The proposal does not specify bucket ACL policy or whether video artifacts should have retention/expiry rules.

**Severity:** LOW

**Recommendation:** Ensure artifact buckets are created with private ACL and no public access. Add lifecycle rules to expire benchmark and video QA artifacts after a defined retention period (e.g., 90 days) to limit exposure window for any sensitive UI state captured in recordings.

### 10. Discord bot token isolation per environment — LOW

**Issue:** The proposal correctly mandates separate `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` per environment (Section 2, "Discord bot integration per environment"). The code does not yet implement this — no environment-specific Discord configuration exists in the k8s manifests. The risk is that during implementation, a single token could be reused across environments, meaning dev mistakes could affect the production guild.

**Severity:** LOW (proposal addresses this; code does not yet exist)

**Recommendation:** When Discord daemon manifests are created, enforce per-environment SealedSecrets for bot tokens. Add a CI or reconciliation check that dev and production never reference the same `DISCORD_GUILD_ID` value.

---

## Overall Assessment

The proposal is security-aware and explicitly addresses most credential and isolation concerns. The research backing it is thorough and grounded in verified provider documentation. The major structural decisions (sealed-secrets for bootstrap, per-environment state isolation, per-cluster Flux roots, environment-specific secrets) are all correct from a security perspective.

The MEDIUM verdict is driven by three findings that represent real gaps between the proposal's intent and the current code state:

1. **Missing `.gitignore` rules for Terraform state files** — a single accidental local apply could commit kubeconfig material to Git
2. **Hetzner storage class residue** — not a direct security issue, but a blocking misconfiguration that could push operators toward manual workarounds
3. **Sealed-secrets key backup is described but not enforced** — the most consequential operational security gap, since key loss means total secret recovery failure

None of these are architectural problems with the proposal itself. They are implementation gaps that are straightforward to close.

---

## What LOW Requires

To reduce this assessment from MEDIUM to LOW:

1. **Add Terraform-related entries to `.gitignore`**: `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `crash.log`, `override.tf`, `override.tf.json`, `*_override.tf`, `*_override.tf.json`
2. **Replace `hcloud-volumes` with `vultr-block-storage`** in `k8s/base/monitoring/helmrelease.yaml` (lines 35, 44, 58) before any cluster provisioning
3. **Create a sealed-secrets key backup step** as a documented, enforceable part of the bootstrap runbook — not just a prose mention in the proposal
4. **Standardize Vultr API key injection** as `TF_VAR_vultr_api_key` and document that CLI `-var` flags must not be used for secrets
