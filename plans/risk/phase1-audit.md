# Phase 1 Foundation — Audit Risk Assessment

**Proposal**: `plans/proposals/phase1-foundation.md`
**Assessor**: claude-opus (audit risk)
**Date**: 2026-04-11

---

## Verdict: LOW

---

## Findings

### 1. OpenTofu remote state contains sensitive infrastructure state — Severity: MEDIUM-LOW

**Issue**: OpenTofu state files stored in Hetzner Object Storage will contain resource attributes including internal IPs, resource IDs, and potentially sensitive outputs. The proposal specifies S3-compatible bucket storage but does not address state-file encryption at rest or access controls on the state bucket.

**Mitigants already in proposal**: State is separated per environment (production/staging keys), manual edits are prohibited, and the bucket is external to the cluster.

**Recommendation**: Enable server-side encryption on the state bucket if Hetzner Object Storage supports it. Restrict bucket credentials to CI runners and named operators only. Document who has state-bucket access. This is a configuration detail, not a design flaw.

### 2. Bootstrap secrets enter via CI/operator shell environment — Severity: LOW

**Issue**: The Hetzner API token, Flux Git credential, and object-storage access keys are injected through environment variables before sealed-secrets exists. This is the correct bootstrap pattern — you cannot encrypt secrets into a cluster that doesn't exist yet.

**Mitigants already in proposal**: The proposal explicitly acknowledges this caveat (Section 6, "Bootstrap caveat") and scopes it to the minimum set. Secrets are not committed to the repo.

**Recommendation**: No change needed. Ensure CI runner environment variables are masked in logs and that shell history on operator workstations is not persisted or is excluded from backups.

### 3. sealed-secrets controller key is a single point of compromise — Severity: LOW

**Issue**: The sealed-secrets controller generates a key pair on first install. If this private key leaks, all SealedSecret manifests in the Git repo become decryptable. If the key is lost, all sealed secrets must be re-encrypted.

**Mitigants already in proposal**: sealed-secrets is scoped to Phase 1 only, with an explicit note that migration to Infisical may follow. The secret count is small during bootstrap.

**Recommendation**: Back up the sealed-secrets key pair to a secure offline location immediately after bootstrap. Document key rotation procedure. This is operational hygiene, not a proposal defect.

### 4. Kubernetes API exposed on public IP (6443/tcp) — Severity: LOW

**Issue**: The proposal allows 6443/tcp from "operator/admin CIDRs." This is standard for self-managed clusters without a VPN overlay, but misconfigured CIDR allowlists (e.g., 0.0.0.0/0) would expose the API server publicly.

**Mitigants already in proposal**: Section 3 ("Network") explicitly restricts 6443 and 22 to operator/admin CIDRs, specifies default-deny on unsolicited public inbound, and prohibits NodePort exposure.

**Recommendation**: Enforce CIDR allowlists via OpenTofu variables with validation (no /0 masks). Consider a VPN or Pomerium tunnel for API access in Phase 2+, but the CIDR approach is acceptable for bootstrap.

### 5. SSH access open during bootstrap — Severity: LOW

**Issue**: Port 22 is allowed from operator CIDRs during bootstrap. The proposal notes this should be reduced in later phases.

**Mitigants already in proposal**: Explicitly scoped to bootstrap and break-glass. The proposal says "later phases can reduce this further."

**Recommendation**: Acceptable for Phase 1. Document the expected Phase 2 reduction (Pomerium-tunneled SSH or disabling direct SSH). No action needed now.

### 6. No public HTTP surface before ingress/auth stack — Severity: LOW (positive finding)

**Issue**: None. The proposal correctly defers ports 80/443, Kong, and public load balancers until a real service needs them. Grafana is accessed via `kubectl port-forward` or internal-only exposure, not public endpoints.

**Recommendation**: This is the right call. No change needed.

### 7. Buildkite agent token as sealed secret — Severity: LOW

**Issue**: The Buildkite agent token will be stored as a sealed secret. Buildkite agents connect outbound over HTTPS. This is a standard pattern.

**Mitigants already in proposal**: Agents are deferred to Phase 2, so this secret doesn't even exist in Phase 1. When it does, the sealed-secrets path is already proven.

**Recommendation**: No change needed. When activated in Phase 2, ensure the agent token has minimal scope (queue-specific, not org-admin).

### 8. Hetzner Cloud Controller and CSI require API credentials in-cluster — Severity: LOW

**Issue**: The Hetzner Cloud Controller Manager and CSI driver need a Hetzner API token to provision load balancers and volumes. This token lives as a Kubernetes secret inside the cluster.

**Mitigants already in proposal**: The token is delivered through the sealed-secrets path once it exists, or through bootstrap injection before that. The cluster runs on a private network with restricted public access.

**Recommendation**: Use a Hetzner API token scoped to the specific project (not account-wide). Hetzner supports project-scoped tokens. This is a deployment detail.

### 9. No credential rotation mechanism in Phase 1 — Severity: LOW

**Issue**: sealed-secrets does not provide automated rotation. The Hetzner API token, object-storage credentials, and Git deploy keys will be static until manually rotated.

**Mitigants already in proposal**: The proposal acknowledges sealed-secrets is "not a full secret-management platform" and explicitly flags rotation as a reason to migrate to Infisical later. Phase 1 has a small secret set with low rotation pressure.

**Recommendation**: Acceptable for bootstrap. Document the rotation procedure even if it's manual. Ensure Phase 2 planning includes a rotation story.

### 10. Object-storage test workload writes in production — Severity: LOW

**Issue**: Definition-of-done item 9 requires a test pod to write/read objects in Hetzner Object Storage. This is a production bucket.

**Mitigants**: The test writes a "small object" and is a one-time validation, not a persistent workload. The bucket is for platform use (state, artifacts), not user data.

**Recommendation**: Use a dedicated test prefix or test bucket for validation. Clean up test objects after validation passes.

---

## Overall Assessment

The Phase 1 proposal demonstrates strong security awareness throughout. The proposal:

- **Correctly defers public exposure** until services justify it (no premature load balancers, no public Grafana, no NodePorts).
- **Restricts management access** to operator CIDRs with default-deny firewall posture.
- **Separates bootstrap secrets** from in-cluster secret delivery and acknowledges the bootstrapping chicken-and-egg explicitly.
- **Avoids Docker-in-Docker** and privileged containers for CI execution.
- **Pins versions** for k3s and kube-hetzner to prevent drift.
- **Isolates environments** in state, Git structure, and cluster topology from day one.

No finding reaches true MEDIUM severity. The findings are operational hygiene items (key backup, CIDR validation, state encryption) that belong in implementation checklists, not proposal revisions.

---

## What LOW Requires

For this assessment to remain LOW, the implementation must:

1. Store the sealed-secrets key pair in a secure backup location outside the cluster.
2. Enforce CIDR allowlists for 6443/tcp and 22/tcp through OpenTofu with input validation — no wildcard masks.
3. Use project-scoped Hetzner API tokens, not account-level tokens.
4. Mask sensitive environment variables in CI runner output.
5. Not expose Grafana, Prometheus, or Alertmanager on public endpoints during Phase 1.
6. Clean up test objects written during definition-of-done validation.
