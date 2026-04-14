# Hookpoint Research: K8s GitOps Manifests

Date: 2026-04-14

## Scope

This note maps
[proposals/32-k8s-manifests.md](/home/nes/projects/server-manager/proposals/32-k8s-manifests.md:1)
onto the current manifest tree under
[k8s/](/home/nes/projects/server-manager/k8s).

It answers:

1. what already exists in the target manifest paths
2. what files are still missing and must be created
3. what existing files can be reused as-is
4. whether anything pre-existing conflicts strongly enough to delete

It does not include implementation code.

## Primary Sources

- Proposal:
  [proposals/32-k8s-manifests.md](/home/nes/projects/server-manager/proposals/32-k8s-manifests.md:1)
- Monitoring base:
  [k8s/base/monitoring/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/kustomization.yaml:1),
  [k8s/base/monitoring/namespace.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/namespace.yaml:1),
  [k8s/base/monitoring/helmrepository.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/helmrepository.yaml:1)
- Secrets base:
  [k8s/base/secrets/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/secrets/kustomization.yaml:1),
  [k8s/base/secrets/namespace.yaml](/home/nes/projects/server-manager/k8s/base/secrets/namespace.yaml:1),
  [k8s/base/secrets/helmrepository.yaml](/home/nes/projects/server-manager/k8s/base/secrets/helmrepository.yaml:1)
- Existing phase artifacts:
  [research/32-k8s-manifests-needs.md](/home/nes/projects/server-manager/research/32-k8s-manifests-needs.md:1),
  [risk/32-scope.md](/home/nes/projects/server-manager/risk/32-scope.md:1),
  [risk/32-shortcut.md](/home/nes/projects/server-manager/risk/32-shortcut.md:1)

## 1. What exists already

### Monitoring base already has the non-HelmRelease scaffolding

The monitoring base already contains the three supporting files the
proposal expects to build on:

- [k8s/base/monitoring/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/kustomization.yaml:1)
- [k8s/base/monitoring/namespace.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/namespace.yaml:1)
- [k8s/base/monitoring/helmrepository.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/helmrepository.yaml:1)

Those files already align with the proposal's intended object split:

- the file-level Kustomize root is already
  `kustomize.config.k8s.io/v1beta1`
- the namespace is already `monitoring`
- the Helm repository is already `prometheus-community` in namespace
  `monitoring`
- the Helm repository already uses
  `source.toolkit.fluxcd.io/v1`, which matches the proposal

Important existing condition:
[k8s/base/monitoring/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/kustomization.yaml:1)
already lists `helmrelease.yaml` in `resources`, but that file does not
exist yet. So the base shape is present, but the directory is currently
incomplete.

### Secrets base already has the non-HelmRelease scaffolding

The secrets base also already contains the three supporting files the
proposal expects to reuse:

- [k8s/base/secrets/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/secrets/kustomization.yaml:1)
- [k8s/base/secrets/namespace.yaml](/home/nes/projects/server-manager/k8s/base/secrets/namespace.yaml:1)
- [k8s/base/secrets/helmrepository.yaml](/home/nes/projects/server-manager/k8s/base/secrets/helmrepository.yaml:1)

These also align with the proposal:

- the file-level Kustomize root is already
  `kustomize.config.k8s.io/v1beta1`
- the namespace is already `sealed-secrets`
- the Helm repository is already named `sealed-secrets` in namespace
  `sealed-secrets`
- the Helm repository already uses
  `source.toolkit.fluxcd.io/v1`, which matches the proposal

Important existing condition:
[k8s/base/secrets/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/secrets/kustomization.yaml:1)
already lists `helmrelease.yaml` in `resources`, but that file does not
exist yet. This base is also structurally ready but currently
incomplete.

### `k8s/base/flux-system/` exists only as an empty directory

The proposal's target directory already exists:
[k8s/base/flux-system/](/home/nes/projects/server-manager/k8s/base/flux-system).

There are no files in that directory today. In particular, there is no
existing:

- `kustomization.yaml`
- `gotk-components.yaml`
- `gotk-sync.yaml`
- Flux `Kustomization` CRD manifest

That means proposal 32 is not replacing any pre-existing
`flux-system` file root in-repo; it is filling an empty hookpoint.

### `k8s/overlays/staging/` exists only as an empty directory

The staging overlay directory already exists:
[k8s/overlays/staging/](/home/nes/projects/server-manager/k8s/overlays/staging).

There are no files in it today. There is no existing
`kustomization.yaml`, no patch files, and no other overlay manifests.

This matches the scope note in
[risk/32-scope.md](/home/nes/projects/server-manager/risk/32-scope.md:1):
the overlay path exists on disk but is not yet reconcilable.

## 2. What needs to be created

The proposal's four target files are all currently absent and still
need to be created:

1. [k8s/base/flux-system/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/flux-system)
   does not exist and must be added as the file-level bootstrap root.
2. [k8s/base/monitoring/helmrelease.yaml](/home/nes/projects/server-manager/k8s/base/monitoring)
   does not exist and must be added to complete the existing monitoring
   base.
3. [k8s/base/secrets/helmrelease.yaml](/home/nes/projects/server-manager/k8s/base/secrets)
   does not exist and must be added to complete the existing secrets
   base.
4. [k8s/overlays/staging/kustomization.yaml](/home/nes/projects/server-manager/k8s/overlays/staging)
   does not exist and must be added as the first staging overlay
   manifest.

The two base `kustomization.yaml` files already point at the missing
`helmrelease.yaml` paths, so the monitoring and secrets `HelmRelease`
files are not new structural concepts. They are the missing manifests
that the current base directories already expect.

## 3. What is reusable

### Reuse the monitoring base support files as-is

The following monitoring files are directly reusable:

- [k8s/base/monitoring/namespace.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/namespace.yaml:1)
- [k8s/base/monitoring/helmrepository.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/helmrepository.yaml:1)
- [k8s/base/monitoring/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/monitoring/kustomization.yaml:1)

Why they align:

- namespace identity already matches the proposal's
  `metadata.namespace: monitoring`
- Helm repository identity already matches the proposal's
  `sourceRef.name: prometheus-community`
- API versions already match the intended split: Kustomize manifest on
  `kustomize.config.k8s.io/v1beta1`, source object on
  `source.toolkit.fluxcd.io/v1`
- the base resource ordering already places `namespace.yaml` before the
  missing `helmrelease.yaml`, which is the right shape for
  `install.createNamespace: false`

### Reuse the secrets base support files as-is

The following secrets files are also directly reusable:

- [k8s/base/secrets/namespace.yaml](/home/nes/projects/server-manager/k8s/base/secrets/namespace.yaml:1)
- [k8s/base/secrets/helmrepository.yaml](/home/nes/projects/server-manager/k8s/base/secrets/helmrepository.yaml:1)
- [k8s/base/secrets/kustomization.yaml](/home/nes/projects/server-manager/k8s/base/secrets/kustomization.yaml:1)

Why they align:

- namespace identity already matches the proposal's
  `metadata.namespace: sealed-secrets`
- Helm repository identity already matches the proposal's
  `sourceRef.name: sealed-secrets`
- API versions already match the proposal's source/object split
- the base resource ordering already assumes namespace-first, then
  repository, then release

### Reuse the existing directory layout

The proposal fits the existing repo-local Kustomize layout cleanly:

- `k8s/base/<component>/` for reusable base manifests
- `k8s/overlays/<environment>/` for environment-specific composition
- `k8s/base/flux-system/` as the bootstrap-local manifest root

Nothing in the current tree suggests a competing structure. Proposal 32
extends the existing layout rather than introducing a new one.

### Repo-local infra/Terraform patterns do not currently inform this batch

I did not find an `infra/` directory or any checked-in `.tf`, `.tfvars`,
or `.hcl` files in this repository snapshot.

That means there is no repo-local Terraform or OpenTofu manifest
structure to reuse for naming, path layout, or environment wiring in
this batch. The useful hookpoints are therefore the existing
`k8s/base/...` directories and the already-written phase artifacts, not
Terraform code.

The Hetzner and staging sizing assumptions referenced in
[research/32-k8s-manifests-needs.md](/home/nes/projects/server-manager/research/32-k8s-manifests-needs.md:1)
remain proposal inputs, not code-derived hookpoints from this repo.

## 4. What conflicts or needs deletion

I did not find any pre-existing files that conflict with the proposal
strongly enough to delete.

Specifically:

- there is no existing `k8s/base/flux-system/kustomization.yaml` to
  replace
- there is no existing `k8s/base/monitoring/helmrelease.yaml` to
  replace
- there is no existing `k8s/base/secrets/helmrelease.yaml` to replace
- there is no existing `k8s/overlays/staging/kustomization.yaml` or
  staging patch file to replace

The only notable mismatch is that both existing base
`kustomization.yaml` files already reference `helmrelease.yaml` files
that are not yet present. That is not a deletion target. It is the
precise hookpoint the proposal is meant to complete.

Because the target directories are either already aligned or empty,
proposal 32 is additive. No cleanup step is indicated by the current
tree.

## Conclusion

Proposal 32 maps cleanly onto the current `k8s/` tree.

The monitoring and secrets bases already provide reusable
`namespace.yaml`, `helmrepository.yaml`, and `kustomization.yaml`
support files, and both already expect a `helmrelease.yaml` that does
not yet exist. The `flux-system` base and staging overlay directories
already exist but are empty, so they are ready hookpoints for the new
file-level `kustomization.yaml` manifests. I found no repo-local
Terraform/OpenTofu files to constrain this work and no pre-existing
files that need deletion.
