# INIT-106 Implementation

## Status

INIT-106 is implemented across five code slices after the pipeline commit:

- `SLICE-106.01`: strict `app_cluster` channel schema, local/dev channel
  values, fixture inheritance, and alias rejection.
- `SLICE-106.02`: Crossplane v1.20.7 raw manifests rendered from the upstream
  chart, plus provider-kubernetes and provider-vultr package resources.
- `SLICE-106.03`: AppCluster XRD, local sample claim, provider configs, local
  nested-k3d Composition, and Vultr VM Composition.
- `SLICE-106.04`: remote contract-only Vultr AppCluster manifests.
- `SLICE-106.05`: local harness support, Docker socket mount for local proof,
  nested cluster cleanup, and focused AppCluster validation.

## Pins

- Crossplane chart/app: `1.20.7`
- provider-kubernetes: `xpkg.upbound.io/crossplane-contrib/provider-kubernetes:v0.18.0`
- provider-vultr: `xpkg.upbound.io/crossplane-contrib/provider-vultr:v0.2.0`
- local provisioner image: `docker:29.0.4-cli`
- local provisioner k3d binary: `v5.8.3`
- app-cluster k3s: `v1.32.13+k3s1`

## Local Contract

Local claim:

```text
namespace: platform-app-clusters
kind: AppCluster
name: local-sample
target: k3d-local
nested cluster: humility-local-app
```

The local Composition creates a Kubernetes Job through provider-kubernetes.
The Job reaches the host Docker daemon through the local-only Docker socket
mount and creates the nested k3d cluster. The cluster harness then verifies the
claim Ready condition and independently checks the nested cluster nodes.

## Remote Contract

Remote Vultr credential flow:

```text
Infisical project: platform-vultr
environment: dev
path: /api
target Secret: crossplane-system/vultr-creds
target key: credentials
ProviderConfig: vultr.upbound.io/v1beta1/default
```

The remote Composition creates a Vultr `Instance` and reuses INIT-101's
cloud-init install shape: `/etc/k3s-install-marker`, pinned
`INSTALL_K3S_VERSION`, and `/root/humility-k3s.yaml`.

## Verification

Static harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Cluster harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

Focused local proof:

```bash
bash infra/tests/validate_app_clusters_local.sh \
  --kubeconfig ~/.kube/humility-local.yaml
```

## Handoff To INIT-107

- Replace or harden local Docker socket access.
- Narrow provider-kubernetes RBAC.
- Define PodSecurity, NetworkPolicy, resource limits, and namespace boundaries
  for Crossplane and provisioner Jobs.
- Decide how app-cluster kubeconfigs are stored, rotated, and accessed.

## Handoff To INIT-113

- Install actual workloads onto app clusters.
- Define app-cluster namespace and certificate strategy.
- Consume app-cluster kubeconfig or API access through a documented runtime
  contract.
