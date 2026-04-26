# GitOps

Reader's guide for the local GitOps substrate.

## Layout

- `gitops/flux/` - pinned Flux `v2.8.6` component manifests. INIT-102 installs
  source-controller and kustomize-controller only.
- `gitops/sources/local/` - local Git source support, including the
  git-daemon Deployment. Rendered `GitRepository` and source-side
  `Kustomization` manifests are generated from the channel contract.
- `gitops/channels/local/` - the local channel overlay, namespace, bootstrap
  sentinel reference, generated snapshot marker, runtime Infisical subtree, and
  local object-storage subtree.
- `gitops/channels/local/infisical/` - INIT-103 runtime-secret management for
  the local channel. `server/` and `operator/` contain committed raw YAML
  rendered from pinned Helm charts. `sample/` contains the authored
  `InfisicalSecret/infisical-local-sample` proof that syncs
  `Secret/infisical-local-sample` into `infisical-sample`.
- `gitops/bootstrap/` - SOPS+age bootstrap-only encrypted secrets. Runtime
  application secrets do not live here; they move through Infisical in
  INIT-103.
- `gitops/channels/local/object-storage/` - INIT-104 local S3-compatible
  storage. It contains raw Kustomize resources for `minio-system`,
  `InfisicalSecret/minio-root`, single-node MinIO, and
  `Job/create-sample-bucket`.
- `gitops/channels/local/tls/` - INIT-105 local certificate automation. It
  contains raw chart-rendered cert-manager, step-ca, step-issuer, a generated
  `StepClusterIssuer/humility-local-step-ca`, and the
  `Certificate/humility-local-sample` proof.
- `gitops/channels/local/dns/` - INIT-105 local DNS automation. It owns the
  local CoreDNS ConfigMap rewrite for `*.humility.local` to
  `*.svc.cluster.local`.
- `gitops/channels/local/app-clusters/` - INIT-106 Crossplane application
  cluster provisioning. It contains raw chart-rendered Crossplane v1.20.7,
  provider-kubernetes, provider-vultr, ProviderConfigs, the AppCluster XRD and
  Compositions, and the local `AppCluster/local-sample` proof.
- `gitops/contracts/remote/tls-dns/` - INIT-105 remote contract-only manifests
  for Cloudflare ExternalDNS credentials, ExternalDNS configuration, and a
  Let's Encrypt staging ACME `ClusterIssuer`. The local channel does not
  reference this subtree.
- `gitops/contracts/remote/app-clusters/` - INIT-106 remote contract-only
  AppCluster manifests for Vultr credential flow and the Vultr VM plus k3s
  Composition.

`gitops/channels/local/infisical/` is part of the Flux-reconciled local
channel. It does not introduce Helm controller, `HelmRelease`, `OCIRepository`,
or runtime chart fetching. Helm is used only by
`infra/scripts/render-infisical-manifests.sh` to refresh committed raw
manifests.

SOPS+age remains bootstrap-only. The Infisical server bootstrap Secret is
allowed under `gitops/bootstrap/`; Operator Universal Auth credentials and all
downstream runtime secrets are created outside Git and consumed through
Infisical plus `InfisicalSecret` resources.

Object storage credentials remain outside Git. `InfisicalSecret/minio-root`
syncs `Secret/minio-root` from Infisical project `platform-storage`, path
`/object-storage/local/`, using the existing
`Secret/infisical-operator-auth` in `infisical-system`. MinIO and Vultr Object
Storage credentials must not be placed in `gitops/bootstrap/` or any
SOPS-encrypted file.

DNS credentials remain outside Git. The remote Cloudflare API token contract
uses Infisical project `platform-dns`, environment `dev`, path `/dns/dev/`,
secret key `CLOUDFLARE_API_TOKEN`, and target
`Secret/cloudflare-api-token` in `external-dns-system`. INIT-105 does not apply
remote DNS records or contact Cloudflare.

TLS manifests are raw Kubernetes YAML. cert-manager, step-ca, step-issuer, and
ExternalDNS are rendered from pinned charts outside the cluster; Flux applies
the committed manifests directly. There is still no Helm controller,
`HelmRelease`, or runtime chart fetch in the local channel.

Crossplane follows the same render-only rule. `crossplane-1.20.7.yaml` is
rendered with local Helm and committed as raw YAML; provider installation uses
Crossplane `Provider` packages, not Helm resources. The local AppCluster proof
creates a nested k3d cluster named `humility-local-app` from
`AppCluster/local-sample`. Vultr API credentials are synced from Infisical
project `platform-vultr`, environment `dev`, path `/api`, into
`Secret/vultr-creds` in `crossplane-system`.

## Generated Artifacts

- `.tmp/gitops-source/local/` - rendered local GitOps snapshot used to seed the
  in-cluster Git daemon during local bring-up and harness runs.
- `gitops/channels/local/generated/` - committed channel overlay artifacts that
  are generated from the local source snapshot contract.

The canonical acceptance harness is:

```bash
bash infra/tests/validate_platform_bootstrap.sh
bash infra/tests/validate_platform_bootstrap.sh --cluster
```
