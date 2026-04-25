# `gitops/`

## Overview

`gitops/` is the Flux CD source tree for the Humility control cluster. After
the control cluster exists, Flux reconciles this directory from the
`server-manager` repository and keeps the control-cluster GitOps substrate in
sync with Git.

The active Phase 5 channel is `dev`, matching `infra/channels/dev.yaml`.
Within INIT-009, `dev` means the control-cluster channel. It is not an
application environment, and it does not reconcile application workloads.

The underlying cluster, OpenTofu channel registry, state backend posture, and
provider-backed runbooks are documented in `infra/README.md`. This document is
the authority for the Flux, SOPS+age, and channel-overlay layout inside
`gitops/`.

## Layout

```text
gitops/
  bases/
    flux-system/              # Active INIT-009 Flux self-management base.
      kustomization.yaml
      gotk-components.yaml    # Flux controller install payload.
      source-gitrepository.yaml
      root-kustomization.yaml
    crossplane/               # Empty INIT-017 handoff base.
      kustomization.yaml
    cert-manager/             # Empty INIT-018 handoff base.
      kustomization.yaml
    external-dns/             # Empty INIT-018 handoff base.
      kustomization.yaml
    cluster-security/         # Empty INIT-019 handoff base.
      kustomization.yaml
  channels/
    dev/
      kustomization.yaml      # Active control-cluster channel overlay.
      patches/
        flux-source-local.yaml
  secrets/
    dev/
      .sops.yaml              # Per-channel public age recipient rules.
      bootstrap-creds.enc.yaml
      kustomization.yaml
  scripts/
    install-tools.sh          # Tool check/install helper.
    bootstrap-flux.sh         # Local kind + Flux bootstrap harness.
  tests/
    validate_gitops.sh        # Local acceptance harness.
  README.md
```

`bases/` holds reusable Kustomize bases. `flux-system` is the only populated
base in INIT-009. The other bases are intentionally empty handoff points for
downstream control-cluster initiatives.

`channels/` holds channel overlays. `channels/dev` is the only active overlay
in INIT-009.

`secrets/` holds per-channel encrypted material and per-channel SOPS rules.
Each channel owns its own recipient list and custody notes.

## Channel overlays

Channels are overlays over shared bases. A channel does not copy a base; it
selects the shared base directories it needs, applies channel-specific patches,
and composes the channel's encrypted secret root.

`gitops/channels/dev/kustomization.yaml` composes:

- `../../bases/flux-system`
- `../../bases/crossplane`
- `../../bases/cert-manager`
- `../../bases/external-dns`
- `../../bases/cluster-security`
- `../../secrets/dev`

This follows the channel/template inheritance pattern used elsewhere in the
project: shared intent lives once in a base, while each channel expresses only
the differences needed for that channel. For INIT-009, the only active
channel-specific difference is the local Flux source patch used by the kind
verification path.

## Self-managing Flux

Flux self-management is anchored in `gitops/bases/flux-system`.

The base contains:

- `gotk-components.yaml` with the Flux controller install manifest.
- `source-gitrepository.yaml` with the `server-manager` `GitRepository`.
- `root-kustomization.yaml` with the root Flux `Kustomization` for
  `./gitops/channels/dev`.
- `kustomization.yaml`, which renders those resources as a single Flux base.

The `GitRepository` is named `server-manager` in the `flux-system` namespace.
It polls at `1m` and tracks the configured branch. The root `Kustomization` is
named `server-manager-dev`, points at `./gitops/channels/dev`, prunes drift,
waits for reconciliation, and reconciles at `5m`.

Local verification uses `gitops/channels/dev/patches/flux-source-local.yaml`
to replace the repository URL with:

```text
git://git-local.git-system.svc.cluster.local/server-manager.git
```

`bootstrap-flux.sh` seeds that in-cluster Git source from the current worktree.
The patch still points Flux at this repository's content; it only changes the
transport so local verification does not require GitHub, Vultr, public DNS, or
any hosted Git service.

## SOPS+age secrets

Secrets use SOPS+age with per-channel recipients. A channel's public age
recipient is committed in `gitops/secrets/<channel>/.sops.yaml`. The matching
private age key is operator-local and is not committed.

For `dev`, the default operator-local private key path is:

```text
~/.config/sops/age/dev.txt
```

The validation and bootstrap scripts honor `SOPS_AGE_KEY_FILE` when an
operator wants to use a different local path.

Custody is per channel. Adding, removing, or rotating a channel recipient is a
change to that channel's secret root and must be verified with the SOPS mode in
the GitOps harness. See `gitops/secrets/dev/README.md` for the `dev` channel's
custody and verification runbook.

## Local verification

Check the local toolchain without installing anything:

```bash
bash gitops/scripts/install-tools.sh --check
```

Run the GitOps harness modes directly:

```bash
bash gitops/tests/validate_gitops.sh --layout-only
bash gitops/tests/validate_gitops.sh --flux-render-only
bash gitops/tests/validate_gitops.sh --sops-only
bash gitops/tests/validate_gitops.sh --cluster
bash gitops/tests/validate_gitops.sh --docs-only
bash gitops/tests/validate_gitops.sh
```

`--layout-only` checks structure, empty handoff bases, and `channels/dev`
composition. `--flux-render-only` checks Flux manifests, renderability,
cadence, and the local-source patch. `--sops-only` checks per-channel SOPS
rules, encrypted fixture shape, age-key support, and decrypts when keys exist.
`--cluster` runs the kind + Flux proof when required tools are installed, or
returns a skipped marker. `--docs-only` checks this handoff, the
`infra/README.md` cross-link, stale plan disposal, and active `k8s/` references.
The default mode runs layout, Flux render, SOPS, toolchain, legacy-layout, and
documentation checks.

`bootstrap-flux.sh` owns the local control-cluster proof. Its subcommands are
`help`, `age-key`, `cluster-up`, `bootstrap`, and `teardown`.

The local proof is intentionally bounded. It proves that the control-cluster
GitOps substrate renders and reconciles locally from this repository. It does
not prove Vultr provisioning, public DNS, GitHub access, application-cluster
reconciliation, or externally hosted Git workflows.

## Placeholder bases

The downstream bases are intentionally empty today:

- INIT-017 owns `gitops/bases/crossplane`.
- INIT-018 owns `gitops/bases/cert-manager`.
- INIT-018 owns `gitops/bases/external-dns`.
- INIT-019 owns `gitops/bases/cluster-security`.

Each placeholder base has `resources: []` and a README naming the owning
initiative. That empty-base discipline is part of the contract: the channel
composition exists now, but resources must not appear in those bases before
their owning initiatives populate them.

## Anti-scope

`gitops/` does not contain application workloads in INIT-009.

It also does not install Crossplane, cert-manager, ExternalDNS, or cluster
security policy resources. Those directories exist only as empty downstream
handoff bases until INIT-017, INIT-018, and INIT-019 populate them.

`gitops/` does not replace `infra/`. OpenTofu channel definitions, state
backend posture, and provider-backed infrastructure runbooks remain under
`infra/`.

`gitops/` does not keep a compatibility path for the retired `k8s/` tree. The
old base, overlays, cluster roots, and tests under that tree were deleted in
INIT-009 and are not aliases, inputs, or live authority.
