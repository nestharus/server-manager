# Phase 1 Shortcut Risk Assessment

**Proposal**: `plans/proposals/phase1-foundation.md`
**Assessed**: 2026-04-11
**Verdict**: **LOW**

---

## Findings

### 1. sealed-secrets as a temporary secret-management solution — Severity: LOW

The proposal explicitly selects `sealed-secrets` over Infisical for Phase 1, calling it "the simplest thing that satisfies the actual bootstrap requirement." This is a deliberate "for now" choice that will require migration when Phase 2+ services need rotation workflows, non-Kubernetes secret consumers, or multi-service credential management.

**Why this is not MEDIUM**: The proposal is transparent about the tradeoff (§6), gives a clear rationale for why Infisical is premature at bootstrap time, and does not pretend sealed-secrets is the long-term answer. The unified platform index lists `infisical-secrets` as a Phase 1 anchor, but the proposal is a refinement of that index — it narrows Phase 1 to what is actually needed for bootstrap, not for the full platform. The migration surface is small: Phase 1 creates only a handful of secrets (Hetzner API token, Flux Git credential, object-storage keys, monitoring credentials). Migrating these to Infisical later is a bounded, low-risk operation.

**Recommendation**: Accept. Ensure the Phase 2 proposal includes an explicit sealed-secrets → Infisical migration step with a defined cutover point rather than letting both coexist indefinitely.

### 2. No sealed-secrets controller key backup procedure — Severity: LOW

The proposal describes the secret flow (§6) but does not mention backing up the sealed-secrets controller's private key. If the controller is destroyed without a key backup, all existing SealedSecret manifests become undecryptable. Re-sealing is straightforward (re-encrypt with the new key), but the gap between "controller dies" and "operator realizes the key wasn't backed up" is where incidents happen.

**Recommendation**: Add a definition-of-done item or an operational note: back up the sealed-secrets controller key to Hetzner Object Storage (encrypted) or to operator-controlled secure storage immediately after bootstrap. This is a one-line addition, not a scope change.

### 3. State locking mechanism unspecified — Severity: LOW

The proposal states "serialize applies per environment" for OpenTofu remote state (§4) but does not specify the locking mechanism. Hetzner Object Storage is S3-compatible but may not support DynamoDB-style state locking. For a one-person operation this is unlikely to cause issues, but concurrent CI runs or operator-plus-CI contention could corrupt state.

**Recommendation**: Clarify whether Hetzner Object Storage supports S3 conditional writes or object locking for state serialization. If not, document the operational constraint (single-writer discipline) or add a lightweight locking mechanism. This is a documentation gap, not a design flaw.

### 4. kubectl port-forward as the initial Grafana access method — Severity: NEGLIGIBLE

The proposal recommends `kubectl port-forward` or internal-only exposure for Grafana until Kong lands in Phase 2+ (§3). This is explicitly temporary and avoids creating public attack surface before the auth stack exists.

**Recommendation**: None. This is the correct bootstrap approach, not a shortcut.

### 5. Staging directory structure without provisioning — Severity: NEGLIGIBLE

The proposal creates `live/staging/` and `clusters/staging/` directory structures without provisioning staging infrastructure (§4, §5). This is forward-compatible scaffolding, not a deferred stub.

**Recommendation**: None. Correct approach.

### 6. Buildkite agent contract designed but not deployed — Severity: NEGLIGIBLE

The proposal describes the Buildkite agent execution model, queue sizing, and secret requirements (§8) but defers actual deployment to Phase 2. The contract is specified; the workload is deferred.

**Recommendation**: None. Clean scope boundary.

---

## Items checked and found clean

- **No hardcoded values**: The bucket name `humility-platform-tfstate` is a convention, not a hardcoded shortcut. Node sizes, firewall rules, and cost figures are specification, not magic constants.
- **No duplicated logic**: The proposal cleanly separates OpenTofu (infra provisioning) from Flux (cluster reconciliation) from sealed-secrets (secret delivery). No overlapping ownership surfaces.
- **No "fix one shortcut by adding another" patterns**: The sealed-secrets choice replaces nothing — it fills an empty slot with the simplest working answer.
- **No source-vs-artifact confusion**: Flux watches Git (source); Helm charts are consumed through HelmRepository/HelmRelease objects (artifacts). The proposal explicitly forbids ad-hoc `helm install` (§5).
- **No symptom-masking workarounds**: Deferred items (Kong, Loki, Buildkite) are deferred with rationale, not stubbed with dummy implementations.
- **No compatibility shims**: Nothing in the proposal maintains backward compatibility with a prior system. The foundation is greenfield.

---

## Overall assessment

The proposal is disciplined about scope control and transparent about its temporary choices. The only genuine "for now" decision is sealed-secrets, and it is well-justified, small in blast radius, and comes with an explicit migration path. The remaining findings are minor documentation gaps (key backup, state locking), not architectural shortcuts.

The proposal does not introduce hacks, duplicated logic, hardcoded values, or workarounds that will silently compound. Deferred items are deferred with clear boundaries, not stubbed with placeholder implementations.

## What LOW requires

1. **Finding 2**: Document the sealed-secrets key backup procedure (one-line operational note or DoD item).
2. **Finding 3**: Clarify the state locking strategy for Hetzner Object Storage (documentation, not code).
3. **Finding 1**: Phase 2 proposal must include an explicit sealed-secrets → Infisical migration plan with a defined cutover point.

These are minor additions that do not change the proposal's architecture or scope.
