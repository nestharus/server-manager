# INIT-101 Implementation

## Status

INIT-101 is complete across all six implementation slices:

- `SLICE-101.01`: discarded VKE-shaped substrate and introduced the k3s channel
  contract.
- `SLICE-101.02`: added the k3d local cluster module, scripts, and local
  reachability harness.
- `SLICE-101.03`: added the Vultr VM module and cloud-init k3s plan surface.
- `SLICE-101.04`: rewrote the channel template, generated roots, and spawn
  workflow.
- `SLICE-101.05`: verified the local k3d bootstrap end to end.
- `SLICE-101.06`: consolidated `infra/README.md`, added the
  `docs/deployment-substrate.md` handoff, and recorded INIT-102 takeover
  context.

## Verification Entry Point

Canonical INIT-101 verification:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Real local cluster proof, when Docker, k3d, and kubectl are available:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

## Handoff

INIT-102 should consume the channel contract, the local kubeconfig path
`~/.kube/humility-local.yaml`, and the `local`/`dev` channel roots. INIT-102
owns GitOps reconciliation and Flux installation; INIT-101 does not install
Flux or apply remote Vultr resources.

## INIT-102 Done State

INIT-102 is complete when the canonical harness passes in both default and
cluster modes:

```bash
bash infra/tests/validate_platform_bootstrap.sh
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

The done state is a local k3d control cluster named `humility-local` with Flux
source-controller and kustomize-controller installed from the pinned
`gitops/flux/gotk-components.yaml` manifest, an in-cluster Git daemon serving
the rendered local GitOps snapshot, and `GitRepository/humility-local` plus
`Kustomization/humility-local` reconciling successfully in `flux-system`.

The local proof also covers the bootstrap-only SOPS+age channel: the operator
age key is delivered to Flux as `Secret/sops-age`, and the encrypted sentinel
in `gitops/bootstrap/sops-sentinel.enc.yaml` reconciles through the local
channel overlay.

## INIT-103 Handoff

INIT-103 can build on:

- The local channel contract and kubeconfig at `~/.kube/humility-local.yaml`.
- The Flux installation path in `infra/scripts/install-flux-for-channel.sh`.
- The rendered GitOps source pipeline under `.tmp/gitops-source/local/`.
- The local channel overlay under `gitops/channels/local/`.
- The bootstrap-only age key channel used by Flux decryption.

Boundary handoff:

- INIT-102 owns Flux, the GitOps overlay pipeline, and bootstrap-only SOPS+age.
- INIT-103 owns Infisical runtime secret management, including Infisical
  Operator installation details, `InfisicalSecret` CRDs, RBAC, and the runtime
  secret contract.
- The Infisical Operator should be installed by Flux as part of the local
  channel. INIT-103 manifests should land under `gitops/channels/local/`, for
  example as an Infisical-specific subdirectory referenced by
  `gitops/channels/local/kustomization.yaml`.
- Runtime `InfisicalSecret` resources are INIT-103's contract. Do not encode
  runtime application secrets in SOPS files.

Open questions for INIT-103:

- How is the Infisical server URL represented per channel?
- Is the Infisical project ID one-per-channel, inherited from parent channels,
  or split by tenant/application surface?
- Where does the Infisical service token enter bootstrap, and how is that
  boundary kept separate from the age key used only for bootstrap decryption?
- Which namespace owns the Infisical Operator, and which namespaces may receive
  synced runtime Kubernetes Secrets?
- What readiness assertions should extend the INIT-102 harness once
  `InfisicalSecret` reconciliation exists?
