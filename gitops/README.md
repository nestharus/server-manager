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

## Local Verification

The full local proof runs Flux against a kind cluster and a local Git source:

```bash
bash gitops/scripts/bootstrap-flux.sh bootstrap
```

Clean up the kind cluster when finished:

```bash
bash gitops/scripts/bootstrap-flux.sh teardown
```

Prerequisites:

- `bash gitops/scripts/install-tools.sh --check` passes, including `kind`,
  `flux`, `kubectl`, `age-keygen`, `git`, and `tar`.
- Docker can start a kind cluster cleanly.
- The current Git commit contains the GitOps state to verify.

The bootstrap creates or reuses the `server-manager-dev` kind cluster, creates
the local dev age key if needed, installs Flux from
`bases/flux-system/gotk-components.yaml`, seeds a bare copy of this repository
into an in-cluster `git daemon`, and reconciles `gitops/channels/dev` from:

```text
git://git-local.git-system.svc.cluster.local/server-manager.git
```

This proves the control-cluster GitOps substrate can reconcile locally from the
repository layout in this tree. It does not prove Vultr provisioning, public
DNS, GitHub access, application-cluster reconciliation, or any externally
hosted Git workflow.

The opt-in cluster harness runs the same bootstrap when all required tools are
present. If they are missing, it exits successfully with a SKIPPED marker:

```bash
bash gitops/tests/validate_gitops.sh --cluster
```

Default validation also runs toolchain checks:

```bash
bash gitops/tests/validate_gitops.sh
```

Prerequisite tool installation and version checks live in
`gitops/scripts/install-tools.sh`.

The underlying control-cluster substrate is documented in `infra/README.md`.
