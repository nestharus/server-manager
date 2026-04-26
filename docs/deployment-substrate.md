# Deployment Substrate

This repository uses a two-tier Kubernetes architecture. The control cluster
hosts platform controllers and reconciliation systems; application workloads
belong on application clusters introduced by later initiatives. INIT-101
establishes only the control-cluster substrate: k3s in k3d locally and
self-managed k3s on Vultr Cloud Compute VMs for remote channels.

The source of truth for operators is `infra/README.md`. This document is only
a `docs/` landing reference for contributors who need platform context before
following the infra runbook.

Controlling architecture decision: `DECISIONS.md` D8. D8 resets Phase 5 around
local-as-first-deployment, self-managed k3s everywhere, and channel templates
as the environment model. It supersedes VKE, the prior local-verification
target, and fixed `infra/environments/{dev,staging,production}` roots.

The environment-agnostic stack reference in the workflow library is the topic
source behind D8: local is a deployment target, not a simulation; the same
components run locally and remotely; per-channel config carries provider and
endpoint details.

Active channel declarations:

```text
infra/channels/local.yaml
infra/channels/dev.yaml
```

Committed channel roots:

```text
infra/roots/channels/local/
infra/roots/channels/dev/
```

The local channel targets k3d:

```text
cluster.target = k3d-local
kubeconfig     = ~/.kube/humility-local.yaml
cluster name   = humility-local
```

The remote `dev` channel targets Vultr VMs:

```text
cluster.target = vultr-vms
region         = ewr
server plan    = vc2-2c-4gb
```

INIT-101 proves the local channel by creating a real k3d cluster and reaching
it with `kubectl`. INIT-101 validates the remote channel root and plan surface,
but does not run a real Vultr apply.

Downstream ownership:

- INIT-102 owns GitOps reconciliation and Flux installation.
- INIT-103 owns runtime secret management.
- INIT-106 owns Crossplane app-cluster provisioning.
- INIT-113 and later own application workloads.
- INIT-118 owns remote control-cluster HA.

Do not add GitOps manifests, secret-store runtime wiring, application
workloads, or remote apply runbooks to INIT-101 docs. Add those details to the
owning downstream INIT when that work is implemented.
