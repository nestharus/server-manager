# Infrastructure

Authoritative operator documentation for the Humility deployment substrate.

## Overview

`infra/` contains the INIT-101 control-cluster substrate: Vultr-locked
OpenTofu, self-managed k3s, channel templates, and local-first deployment
scripts. The local channel runs k3s through k3d. Remote channels describe k3s
on Vultr Cloud Compute VMs bootstrapped by cloud-init.

Local is a real deployment target, not a dry run. The completion proof creates
`humility-local` and reaches it with `kubectl` through
`~/.kube/humility-local.yaml`. Remote Vultr work is plan-only in INIT-101.

## Local Prerequisites

Required tools: OpenTofu `1.11.5`, kubectl `>= 1.31`, Docker `>= 24`,
Python `>= 3.10` with `jsonschema` and `PyYAML`, and k3d `v5.8.3`.

Verify or install the pinned k3d binary:

```bash
bash infra/scripts/install-cluster-tools.sh --check
bash infra/scripts/install-cluster-tools.sh --install
```

`--install` writes k3d to `~/.local/bin`. It does not install OpenTofu,
kubectl, Docker, Python, `jsonschema`, or `PyYAML`.

## Layout

```text
infra/
  bootstrap/state-backend/          # Vultr Object Storage tfstate root
  channels/
    local.yaml                      # Local k3d channel
    dev.yaml                        # Remote Vultr VM plan channel
    fixtures/                       # Resolver and spawn fixtures
  schemas/                          # Source and resolved channel schemas
  scripts/                          # Tool install, channel, spawn, k3d ops
  modules/
    platform-cluster-k3d/           # Local k3d target
    platform-cluster-vms/           # Vultr VM plus cloud-init k3s target
    platform-network/               # Vultr VPC module
  templates/platform-channel/       # Shared root template and dispatch
  roots/channels/local/             # Committed local OpenTofu root
  roots/channels/dev/               # Committed remote plan OpenTofu root
  tests/validate_platform_bootstrap.sh
```

Retired INIT-008 artifacts are intentionally absent: no
`infra/modules/platform-cluster/`, no `infra/environments/`, and no active
VKE-shaped channel fields.

## Channel Pattern

Channels are the environment model. A channel YAML declares provider, k3s
target, state backend, exposure class, inheritance parent, and whether
ephemeral children are allowed. Active declarations are
`infra/channels/local.yaml` and `infra/channels/dev.yaml`.

Resolve and validate channels:

```bash
python infra/scripts/resolve_platform_channel.py --channel local
python infra/scripts/resolve_platform_channel.py --channel dev
python infra/scripts/validate_platform_channels.py
```

Committed generated roots under `infra/roots/channels/{local,dev}/` are
drift-checked by the harness. `cluster.target` dispatches through
`infra/templates/platform-channel`: `k3d-local` calls
`infra/modules/platform-cluster-k3d`, and `vultr-vms` calls
`infra/modules/platform-cluster-vms`.

`local` resolves to `k3d-local`, k3s `v1.32.13+k3s1`, one server, one agent,
registry `humility-local`, and kubeconfig `~/.kube/humility-local.yaml`.

`dev` resolves to `vultr-vms`, k3s `v1.32.13+k3s1`, region `ewr`, one
`vc2-2c-4gb` server, zero agents, empty `vultr_ssh_key_ids`, and empty
`vultr_allowed_ssh_cidrs`.

## Local Channel Bring-Up

Verify local tooling:

```bash
bash infra/scripts/install-cluster-tools.sh --check
docker info
kubectl version --client
tofu version
```

Create, verify, repair, recreate, and tear down the local channel:

```bash
bash infra/scripts/bring-up-local-channel.sh --channel local
KUBECONFIG=~/.kube/humility-local.yaml kubectl get nodes
KUBECONFIG=~/.kube/humility-local.yaml kubectl get pods -A
bash infra/scripts/bring-up-local-channel.sh --channel local --repair
bash infra/scripts/bring-up-local-channel.sh --channel local --force
bash infra/scripts/delete-local-channel.sh --channel local
```

The script resolves `local.yaml`, creates `humility-local` if needed, writes
`~/.kube/humility-local.yaml`, and verifies one server plus one agent. A second
run is a no-op when the live cluster matches the channel contract. The delete
script is idempotent when the cluster and kubeconfig are absent.

## Remote Channel Plan-Only

The `dev` channel is a Vultr VM k3s plan surface. INIT-101 validates the shape
without spending Vultr resources:

```bash
cd infra/roots/channels/dev
tofu init -backend=false
tofu validate
```

Remote apply is post-INIT-117 deployment work. That work must define Vultr
credentials, SSH key IDs, backend initialization, bootstrap token handling,
kubeconfig retrieval, rollback, and `tofu apply` procedure. Do not run
`tofu apply` against `infra/roots/channels/dev` as part of INIT-101.

## Channel Registry And Spawn

To add a durable channel: add `infra/channels/<id>.yaml`, run
`validate_platform_channels.py`, resolve the channel, generate
`backend.tfbackend` and `channel.auto.tfvars.json`, then commit the source and
generated root artifacts together.

Spawn ephemeral children under `.tmp/` only:

```bash
python infra/scripts/spawn_platform_channel.py \
  --parent dev \
  --suffix pr-123 \
  --out .tmp/dev-pr-123
```

The spawn script refuses outputs outside `.tmp/` and parents with
`allow_ephemeral_children: false`. It does not create active files under
`infra/`.

## Local Verification

Canonical INIT-101 verification:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Default mode validates files, schemas, resolver behavior, generator drift,
OpenTofu validation, cloud-init strictness, VKE retirement, and no-cluster
script idempotency.

Real local cluster proof:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

Cluster mode requires Docker, k3d, and kubectl. It verifies
`kubectl get nodes` against `~/.kube/humility-local.yaml`, confirms all nodes
are `Ready`, checks bring-up idempotency, deletes the cluster, and checks
delete idempotency.

## Anti-Scope

This directory does not install or operate:

- GitOps reconciliation or Flux installation: INIT-102.
- Runtime secret management or Infisical installation: INIT-103.
- Crossplane app-cluster provisioning: INIT-106.
- DNS automation, TLS, cert-manager, ingress, and edge policy: later INITs.
- Application workloads, API service deployment, Discord daemon deployment,
  databases, queues, or observability workloads: INIT-113 and later.
- Remote k3s apply, remote HA, remote kubeconfig retrieval, or Vultr load
  balancer registration.

Remote HA is scheduled for INIT-118. Remote apply is post-INIT-117 deployment
work.

## Cross-References

Controlling decision: `DECISIONS.md` D8, "Environment-agnostic Phase 5 reset:
local-as-first-deployment and self-managed k3s everywhere."

Workflow library references under `~/ai/` apply here, especially the
no-backwards-compatibility and unfinished-work conventions. D8 also points
future INIT proposals at the environment-agnostic stack reference: local is a
deployment target, channels carry provider configuration, and k3s is used
locally and remotely.

For contributors starting in `docs/`, see `docs/deployment-substrate.md` for
the short context handoff back to this README.
