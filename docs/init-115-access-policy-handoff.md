# INIT-115 Handoff: Access Policy, Break-Glass, and Service Identity

INIT-115 promotes the INIT-114 sample Cedar rule into a structured local
access-policy bundle and adds operator recovery contracts.

## Delivered

- Cedar policy repo:
  - `policy/cedar/channels/local/services/server-manager-api/manifest.yaml`
  - `policy/cedar/channels/local/services/server-manager-api/policies.json`
  - `policy/cedar/channels/local/services/server-manager-api/service-identities.json`
- GitOps reconciliation for `ConfigMap/cedar-access-policy-bundle` and
  `Job/cedar-access-policy-bootstrap`.
- Service identity issuer contract in `ConfigMap/service-identity-issuer`.
- Buildkite and Crossplane machine identities mapped to Cedar `Service`
  principals.
- Dry-run-first operator scripts:
  - `infra/scripts/verify-service-identity-claim.sh`
  - `infra/scripts/rotate-platform-credentials.sh`
  - `infra/scripts/break-glass-sops-recovery.sh`
  - `infra/scripts/apply-object-storage-policies.sh`
- Operator RBAC narrowing removes the rendered `crossplane-admin`
  `ClusterRoleBinding` from the local root and grants platform operators only
  namespaced `AppCluster` claim access.
- Bucket policy cadence is encoded in the channel contract and script:
  versioning enabled, SSE-S3, 30-day lifecycle.

## Validation

Static:

```bash
pytest infra/tests/test_access_policy_contract.py
infra/tests/validate_access_policy_local.sh --static-only
```

Runtime:

```bash
infra/tests/validate_access_policy_local.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

Runtime proof checks:

- OPAL/Cedar client is available.
- `Job/cedar-access-policy-bootstrap` is complete.
- Cedar allows `sample@local.humility.local` for `api:read`.
- Cedar denies `other@local.humility.local` for `api:read`.
- Cedar allows `Service::"buildkite-agent.local"` for `api:ci:deploy`.

## Break-Glass

Dry-run:

```bash
infra/scripts/break-glass-sops-recovery.sh --channel local
```

Execute only when Infisical is down and Flux decryption must be recovered:

```bash
infra/scripts/break-glass-sops-recovery.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml \
  --execute
```

The script re-encrypts `gitops/bootstrap/sops-sentinel.enc.yaml` with the
operator-local age key, reapplies `Secret/sops-age`, and reconciles
`Kustomization/humility-local`.

## Credential Rotation

Cadence:

- Infisical Universal Auth tokens: 30 days.
- SOPS age key: 180 days.
- SOPS recipients: 180 days.

Dry-run:

```bash
infra/scripts/rotate-platform-credentials.sh --channel local
```

Execute with an explicit guard:

```bash
ROTATION_CONFIRM=local/infisical-ua \
INFISICAL_UA_CLIENT_ID=... \
INFISICAL_UA_CLIENT_SECRET=... \
INFISICAL_ORGANIZATION_ID=... \
infra/scripts/rotate-platform-credentials.sh \
  --channel local \
  --mode infisical-ua \
  --kubeconfig ~/.kube/humility-local.yaml \
  --execute
```

## INIT-116 Handoff

INIT-116 should add tenant-aware policy boundaries. It should not change the
INIT-115 service identity issuer shape unless tenant isolation needs a new
claim namespace or a tenant-scoped Cedar principal convention.
