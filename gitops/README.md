# `gitops/`

This directory is the Flux CD source tree for the Humility control cluster.
Flux reconciles this tree from the `server-manager` repository after the
control cluster is bootstrapped.

The active Phase 5 channel is `dev`, matching `infra/channels/dev.yaml`.
In INIT-009, `dev` means the control-cluster channel. It is not an
application environment and it does not reconcile application workloads.

## Directory Layout

```text
gitops/
  bases/
    flux-system/
    crossplane/
    cert-manager/
    external-dns/
    cluster-security/
  channels/
    dev/
  secrets/
    dev/
  scripts/
  tests/
```

`bases/` contains shared Kustomize bases. `flux-system` is the active
INIT-009 base and is populated by later INIT-009 slices with the Flux
self-management manifests.

`channels/dev/` is the only active overlay in this slice. It composes every
base plus the per-channel secrets directory at `secrets/dev`.

`secrets/dev/` is the per-channel secret root. SLICE-034 adds the SOPS+age
custody workflow and encrypted fixtures.

## Secrets

Secrets use SOPS+age with per-channel recipients per the Q4 lock on
2026-04-25. Each channel under `gitops/secrets/<channel>/` owns its own
`.sops.yaml`, public age recipients, and custody runbook.

Private age keys stay operator-local. For the `dev` channel, the expected key
path is `~/.config/sops/age/dev.txt`, exposed to SOPS with
`SOPS_AGE_KEY_FILE=~/.config/sops/age/dev.txt`.

See `gitops/secrets/dev/README.md` for add, remove, rotate, and verification
commands.

## Placeholder Bases

The downstream control-cluster systems are scheduled in later initiatives:

- INIT-017 owns `bases/crossplane`
- INIT-018 owns `bases/cert-manager`
- INIT-018 owns `bases/external-dns`
- INIT-019 owns `bases/cluster-security`

Those bases are intentionally empty today. Each one has `resources: []` so
the channel composition contract exists now, while the validation harness can
detect drift if resources are added before the owning initiative ships.

## Validation

Run the layout-only harness when changing the Kustomize tree:

```bash
bash gitops/tests/validate_gitops.sh --layout-only
```

Run the SOPS workflow harness when changing per-channel secrets:

```bash
bash gitops/tests/validate_gitops.sh --sops-only
```

Default validation also runs toolchain checks:

```bash
bash gitops/tests/validate_gitops.sh
```

Prerequisite tool installation and version checks live in
`gitops/scripts/install-tools.sh`.

The underlying control-cluster substrate is documented in `infra/README.md`.
