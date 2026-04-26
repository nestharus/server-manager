# Infrastructure

OpenTofu-managed infrastructure for the Humility platform.

## Structure

    infra/
    ├── bootstrap/
    │   └── state-backend/    # One-time: create Object Storage for tfstate
    ├── channels/
    │   ├── local.yaml        # Local k3d channel declaration
    │   └── dev.yaml          # Vultr VM k3s channel declaration
    ├── schemas/              # Platform channel JSON schemas
    ├── scripts/              # Channel resolution and validation tools
    ├── modules/
    │   ├── platform-cluster-k3d/
    │   ├── platform-cluster-vms/
    │   └── platform-network/ # Shared VPC module
    ├── templates/
    │   └── platform-channel/
    ├── roots/
    │   └── channels/
    │       ├── local/        # Local k3d first-deployment root
    │       └── dev/          # Remote Vultr VM plan surface
    └── tests/

## Bootstrap

1. Create the remote-state bucket:
   `cd infra/bootstrap/state-backend`
   `tofu init`
   `tofu apply -var="object_storage_cluster_id=<cluster-id>" -var="object_storage_tier_id=<tier-id>"`

2. Capture the `s3_hostname` output for later channel-root backend
   generation.

3. Validate channel definitions:
   `python infra/scripts/validate_platform_channels.py`

## Local Channel Bring-Up

Install the pinned local cluster toolchain once:

```bash
bash infra/scripts/install-cluster-tools.sh --install
```

Create the local k3d channel cluster. Re-running this command is idempotent
and does not mutate the global kubectl context.

```bash
bash infra/scripts/bring-up-local-channel.sh
```

Use the channel-scoped kubeconfig explicitly:

```bash
KUBECONFIG=~/.kube/humility-local.yaml kubectl get nodes
```

If the script reports stale local state, choose the repair path explicitly:

```bash
bash infra/scripts/bring-up-local-channel.sh --repair
```

Use `--force` only when the local k3d cluster itself should be deleted and
recreated:

```bash
bash infra/scripts/bring-up-local-channel.sh --force
```

Delete the local channel cluster when finished:

```bash
bash infra/scripts/delete-local-channel.sh
```

The delete script is safe to run again after the cluster and kubeconfig are
already gone.

## Done-State Proof

Run the full local proof when Docker, k3d, and kubectl are available:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

The harness performs this sequence:

```bash
bash infra/scripts/bring-up-local-channel.sh
KUBECONFIG=~/.kube/humility-local.yaml kubectl get nodes
bash infra/scripts/bring-up-local-channel.sh
bash infra/scripts/delete-local-channel.sh
bash infra/scripts/delete-local-channel.sh
```

The expected proof is:

- `kubectl get nodes` returns at least one node through
  `~/.kube/humility-local.yaml`.
- All reported nodes are `Ready`.
- The second bring-up exits 0 with an `already up` no-op message.
- Both delete runs exit 0, and the second reports the cluster is already gone.

## Notes

- `local` is the local k3d target for first deployment work.
- `infra/roots/channels/local/` uses an operator-local OpenTofu backend for
  first deployment. Remote channels use generated S3-compatible backend config.
- `dev` is the remote Vultr VM k3s channel declaration.
- `infra/roots/channels/dev/channel.auto.tfvars.json` intentionally commits
  `vultr_ssh_key_ids` as an empty list. Operators populate Vultr SSH key IDs at
  apply time; no SSH key IDs or private keys are committed.
- INIT-101 validates the remote Vultr VM plan surface but does not run
  `tofu apply` against Vultr.
