# INIT-101 Phase 1 Research: Self-Managed k3s Control Cluster

Scope: evidence-only research for replacing the archived INIT-008 VKE-shaped
control-cluster substrate with self-managed k3s everywhere: k3d for the local
channel and k3s on Vultr Cloud Compute VMs for remote channels.

Non-goal: this document does not choose the final implementation design. It
records constraints, existing repo facts, upstream interfaces, risks, and open
questions for the proposal phase.

## 0. Source Authority

- D8 is the controlling decision. It resets Phase 5 around local-as-first
  deployment, self-managed k3s everywhere, OpenTofu for Vultr primitives, and
  cloud-init for remote VM k3s bootstrap. Citation: `DECISIONS.md:175-203`.
- D8 supersedes VKE managed Kubernetes, kind as the local Kubernetes target,
  fixed dev/staging/production roots, VKE/provider-vultr Crossplane app-cluster
  compositions, and local-only/dry-run framing. Citation: `DECISIONS.md:207-249`.
- D8 consequence: no VKE module, no VKE channel schema, no kind-only harness,
  no SOPS-runtime framing, and no VKE Crossplane work should merge. Citation:
  `DECISIONS.md:251-259`.
- The environment-agnostic memory says local is a deployment target, not
  verification or simulation. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:7-10`.
- The local channel uses k3s in k3d, while remote channels use k3s on Vultr
  Cloud Compute VMs. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:15-18`.
- The memory explicitly forbids stubs, dry-run substitutes, kind-as-VKE
  simulation, local-only verification as the goal, and env-specific rules where
  channel parameterization can carry differences. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:29-37`.
- The memory identifies INIT-008's VKE choice as a wrong result of the old
  local-only framing and says to restore parity by switching to self-managed
  k3s and dropping kind-vs-VKE asymmetry. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:62-77`.
- The two-tier architecture memory preserves the control-cluster/app-cluster
  separation: control cluster hosts platform controllers, not app workloads.
  Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/two-tier-cluster-architecture.md:7-18`.
- The same memory says app workloads belong on app clusters and that INIT-017
  was the app-cluster provisioning owner in the old plan. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/two-tier-cluster-architecture.md:20-47`.
- The channel-template memory rejects hard-coded environment roots and starts
  from `infra/templates/platform-channel/`, `infra/channels/<id>/`, and
  `infra/schemas/channel.schema.json`. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:7-8` and
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:50-56`.
- The platform-stack memory locks Vultr, OpenTofu, Buildkite, Flux, Authentik,
  OPAL/Cedar, Pomerium, Vultr Object Storage, and Vultr Object Storage remote
  state, while its old VKE cluster row is superseded by D8. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/platform-stack.md:9-22`;
  supersession citation: `DECISIONS.md:211-213`.
- Phase 5 index names INIT-101 as the self-managed k3s control-cluster
  initiative: k3d locally and OpenTofu plus Vultr VMs plus cloud-init for the
  remote control-cluster contract. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:24-30`.
- Phase 5 operating rules repeat the local-first, no-local-special-exceptions,
  k3s-everywhere, wrong-shaped-work-deleted, and channel-template rules.
  Citation: `product-strategy/tickets/PHASE_5_INDEX.md:96-120`.
- Phase 5 index archives INIT-008 at commit `9f7090f` and says its VKE substrate
  is discarded. Citation: `product-strategy/tickets/PHASE_5_INDEX.md:150-156`.
- The phase-5 replan section for INIT-101 says the scope is self-managed k3s
  everywhere; local channel creates k3d; remote channels use OpenTofu to
  provision Vultr VMs and cloud-init to install k3s; VPC/firewall/object-state
  backend/channel-template ideas remain where applicable. Citation:
  `/home/nes/projects/server-manager/worktrees/phase-5-replan/.pipeline/replan.md:607-625`.
- The replan says the VKE module, VKE roots, VKE channel schema, and
  VKE-oriented docs are reference only and should not merge into the corrected
  main path. Citation:
  `/home/nes/projects/server-manager/worktrees/phase-5-replan/.pipeline/replan.md:202-211`.

## 1. Current Repo State for the Control Cluster

### 1.1 INIT-008 archive identity

- The archived INIT-008 worktree is
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap`.
  `git rev-parse --short HEAD` returns `9f7090f`. Command evidence: local
  command run on 2026-04-25 in this session.
- The archived commit subject is `fix: address INIT-008 CodeRabbit pass 5
  cross-file consistency findings`. Command evidence: `git -C
  /home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap log -1
  --oneline`, 2026-04-25.
- Phase 5 index matches this archive reference exactly. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:150-156`.

### 1.2 INIT-008 infra survey

- INIT-008 created `infra/bootstrap/state-backend/`, `infra/channels/`,
  `infra/modules/platform-cluster/`, `infra/modules/platform-network/`,
  `infra/roots/channels/dev/`, `infra/schemas/`, `infra/scripts/`,
  `infra/templates/platform-channel/`, and `infra/tests/`. Citation:
  local file listing from
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra`,
  2026-04-25.
- The archived `infra/channels/dev.yaml` has channel metadata:
  `schema_version`, `id`, `parent`, `exposure`, `tenant`,
  `allow_ephemeral_children`, and `enabled_platforms`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:1-7`.
- The same `dev.yaml` has a Vultr platform block with region `ewr` and VPC
  subnet `10.40.0.0/20`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:8-12`.
- The current `dev.yaml` cluster block is VKE-shaped: `label`,
  `kubernetes_version: v1.32.9+3`, a single `node_pools` array, managed
  `ha_controlplanes`, and `enable_firewall`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:13-21`.
- The `dev.yaml` state block points at Vultr Object Storage state:
  bucket `humility-tfstate`, key `channels/dev/terraform.tfstate`, region
  `ewr`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:22-25`.
- The source schema requires root channels to include `platform`, `cluster`,
  and `state`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:68-99`.
- The archived schema constrains `cluster.kubernetes_version` to a VKE-like
  `vX.Y.Z+N` pattern, not a k3s release tag like `vX.Y.Z+k3s1`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:145-148`.
- The archived schema constrains `cluster.node_pools` to exactly one item.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:149-157`.
- The archived platform template currently calls `modules/platform-network`
  and `modules/platform-cluster`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/templates/platform-channel/main.tf:1-20`.
- The template passes VKE-specific variables such as
  `cluster_kubernetes_version`, `node_plan`, `node_quantity`,
  `ha_controlplanes`, and `enable_firewall`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/templates/platform-channel/main.tf:9-20`.
- The archived `platform-cluster` module is explicitly documented as one VKE
  cluster per environment. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-cluster/main.tf:1-2`.
- The archived `platform-cluster` module provisions `vultr_kubernetes`, not
  `vultr_instance`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-cluster/main.tf:50-64`.
- The archived `platform-network` module provisions `vultr_vpc`, uses
  region/subnet/mask variables, and outputs the VPC id and subnet attributes.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-network/main.tf:8-50`.
- The archived state-backend bootstrap root provisions a
  `vultr_object_storage` subscription and outputs S3 hostname/access/secret
  values, with sensitive flags on keys. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/bootstrap/state-backend/main.tf:1-69`.
- The archived `resolve_platform_channel.py` has reusable structural behavior:
  source/resolved schema validation, YAML loading, parent lookup in active and
  fixture channels, deep merge, ephemeral key generation, circular-parent guard,
  and structured JSON errors. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/resolve_platform_channel.py:18-221`.
- The archived `generate_channel_backend.py` turns resolved state fields into a
  backend config with `bucket`, `key`, and `region`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/generate_channel_backend.py:14-37`.
- The archived `generate_channel_tfvars.py` is structurally reusable but its
  payload is VKE-shaped: it maps `cluster.kubernetes_version`,
  `node_pools[0].plan`, `node_pools[0].count`, `ha_controlplanes`, and
  `enable_firewall` to Terraform variables. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/generate_channel_tfvars.py:14-82`.
- The archived harness checks toolchain, file existence, Terraform formatting,
  Terraform validation, generated artifact drift, security assertions, and
  channel resolver behavior. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/tests/validate_platform_bootstrap.sh:496-837`.

### 1.3 Salvage/discard evidence from INIT-008

- Salvageable: channel-template directory layout, because D8 preserves channel
  templates and the channel-template memory names the same layout. Citations:
  `DECISIONS.md:197-200`;
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:50-56`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:72-118`.
- Salvageable: state-backend bootstrap concept, because D8 preserves Vultr
  Object Storage for remote state and the archived root already models the
  Object Storage subscription. Citations: `DECISIONS.md:191-192`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/bootstrap/state-backend/main.tf:1-69`;
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/platform-stack.md:15-16`.
- Salvageable: VPC/network module concept, because D8 keeps Vultr cloud
  primitives and remote VMs still need a Vultr network substrate. Citations:
  `DECISIONS.md:189-192`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-network/main.tf:29-50`.
- Salvageable with field changes: resolvers and generators, because their
  inheritance/generation structure is independent of VKE but their field set is
  not. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/resolve_platform_channel.py:143-189`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/generate_channel_tfvars.py:57-82`.
- Salvageable with assertions rewritten: harness shape, because it already
  covers toolchain, structure, generated drift, security, and channel-registry
  behavior. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/tests/validate_platform_bootstrap.sh:496-837`.
- Discard: `infra/modules/platform-cluster/`, because it is a
  `vultr_kubernetes` VKE module and D8 says VKE is no longer the runtime
  substrate. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-cluster/main.tf:50-64`;
  `DECISIONS.md:189-190`;
  `DECISIONS.md:211-213`.
- Rewrite: `infra/templates/platform-channel/main.tf`, because it calls the
  VKE module and passes VKE-shaped values. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/templates/platform-channel/main.tf:9-20`.
- Rewrite: channel schemas and dev channel YAML, because they encode VKE
  version and node-pool shape. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:137-164`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:13-21`.

## 2. Self-Managed k3s - Local Mode with k3d

### 2.1 What k3d is

- k3d is a wrapper that runs k3s in Docker. Citation:
  https://k3d.io/stable/
- k3d supports single-node and multi-node k3s clusters in Docker for local
  Kubernetes development. Citation: https://k3d.io/stable/
- k3d requires Docker; k3d v5 requires Docker v20.10.5 or newer, and kubectl is
  needed to interact with clusters. Citation: https://k3d.io/stable/
- This matches the governing requirement that local uses k3s distribution via
  k3d rather than kind. Citations:
  `DECISIONS.md:216-217`;
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:17`.

### 2.2 k3d installation evidence

- k3d official docs support installing the latest release with:
  `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`.
  Citation: https://k3d.io/stable/
- k3d official docs support pinning an install by setting `TAG`, for example:
  `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | TAG=v5.0.0 bash`.
  Citation: https://k3d.io/stable/
- GitHub API check on 2026-04-25 reports latest k3d release `v5.8.3`,
  published 2025-02-15. Citation:
  https://github.com/k3d-io/k3d/releases/tag/v5.8.3; command evidence:
  `curl -fsSL https://api.github.com/repos/k3d-io/k3d/releases/latest`.
- Research implication for the proposal phase: a pinned install should use a
  concrete k3d tag rather than floating `main`. Evidence: k3d docs support
  `TAG`; current latest is `v5.8.3`. Citations:
  https://k3d.io/stable/ and
  https://github.com/k3d-io/k3d/releases/tag/v5.8.3.

### 2.3 k3d cluster creation surface

- `k3d cluster create NAME` creates a new k3s cluster with containerized nodes.
  Citation: https://k3d.io/stable/usage/commands/k3d_cluster_create/
- A k3d cluster consists of one or more k3s server containers, optionally a
  load-balancer container, and optionally one or more k3s agent containers.
  Citation: https://k3d.io/stable/usage/commands/k3d_cluster_create/
- k3d supports `--servers` for the number of server nodes and `--agents` for
  the number of agent nodes. Citation:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/
- k3d supports `--api-port` to expose the Kubernetes API server through the
  k3d load balancer. Citation:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/
- k3d supports `--port` mappings from host to node containers through node
  filters such as `loadbalancer` or `agent:0`. Citations:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/ and
  https://k3d.io/stable/usage/exposing_services/
- k3d supports `--volume` mounts into node containers. Citation:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/
- k3d supports `--registry-create` to create and attach a k3d-managed registry,
  and `--registry-use` to attach existing k3d-managed registries. Citation:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/

### 2.4 Local topology evidence

- D8 requires the local channel to produce a real local deployment target, not a
  dry-run or render-only state. Citations: `DECISIONS.md:201-203`;
  `product-strategy/tickets/PHASE_5_INDEX.md:98-104`.
- The prompt allows local single-node to be fine while remote needs an HA
  story. This document records that local single-server k3d is supported by
  upstream; final local server/agent counts belong to proposal.
- Local cluster name convention evidence from channel-template memory: channel
  id is the environment identity and should replace hard-coded environment
  names. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:24-40`
  and
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:67-78`.

### 2.5 Local kubeconfig handling

- By default, k3d updates the default kubeconfig with new cluster details and
  sets the current context unless disabled. Citation:
  https://k3d.io/stable/usage/kubeconfig/
- k3d can emit kubeconfig with `k3d kubeconfig get mycluster > file`. Citation:
  https://k3d.io/stable/usage/kubeconfig/
- `k3d cluster delete mycluster` removes the cluster details from the default
  kubeconfig and deletes the matching `$HOME/.k3d/` kubeconfig if it exists.
  Citation: https://k3d.io/stable/usage/kubeconfig/
- Proposal-phase relevance: local kubeconfig handling needs a channel-scoped
  path or merge behavior because global current-context mutation is explicitly
  called out by k3d docs. Citation: https://k3d.io/stable/usage/kubeconfig/.

### 2.6 Local teardown/idempotency evidence

- k3d has a first-class `cluster delete` command and deletion removes
  kubeconfig entries. Citation: https://k3d.io/stable/usage/kubeconfig/.
- k3d `cluster create` supports `--no-rollback` and otherwise has rollback
  behavior on failure; `--wait` is enabled by default. Citation:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/.
- Research implication: a local bring-up harness can verify create/delete/list
  behavior through k3d commands, but the exact idempotent wrapper belongs in the
  proposal/implementation phases.

## 3. Self-Managed k3s - Remote Mode on Vultr VMs

### 3.1 k3s install method and versioning evidence

- K3s provides an install script at `https://get.k3s.io` for systemd/openrc
  systems. Citation: https://docs.k3s.io/quick-start.
- The standard single-node install command is
  `curl -sfL https://get.k3s.io | sh -`. Citation:
  https://docs.k3s.io/quick-start.
- K3s install creates a service that restarts after reboot/process failure,
  installs utilities including kubectl/crictl/ctr, and writes kubeconfig to
  `/etc/rancher/k3s/k3s.yaml`. Citation: https://docs.k3s.io/quick-start.
- A single-node K3s server is a fully functional Kubernetes cluster with
  datastore, control-plane, kubelet, and container runtime components. Citation:
  https://docs.k3s.io/quick-start.
- Agents join with `K3S_URL` and `K3S_TOKEN`; the token lives at
  `/var/lib/rancher/k3s/server/node-token` on the server. Citation:
  https://docs.k3s.io/quick-start.
- K3s install script supports `INSTALL_K3S_EXEC`, `K3S_` environment variables,
  and trailing flags, and persists these into service configuration. Citation:
  https://docs.k3s.io/installation/configuration.
- K3s supports configuration files at `/etc/rancher/k3s/config.yaml` and
  drop-ins under `/etc/rancher/k3s/config.yaml.d/*.yaml`. Citation:
  https://docs.k3s.io/installation/configuration.
- K3s manual upgrade docs support pinning to a specific version with
  `INSTALL_K3S_VERSION=vX.Y.Z+k3s1`. Citation:
  https://docs.k3s.io/upgrades/manual.
- GitHub API check on 2026-04-25 reports latest k3s release
  `v1.35.3+k3s1`, published 2026-03-28. Citation:
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1; command evidence:
  `curl -fsSL https://api.github.com/repos/k3s-io/k3s/releases/latest`.
- The prompt's example `v1.32.5+k3s1` matches the upstream k3s tag shape, but
  current latest observed in this session is `v1.35.3+k3s1`. Citation:
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1.

### 3.2 Remote HA and networking evidence

- K3s embedded-etcd HA requires an odd number of server nodes for quorum.
  Citation: https://docs.k3s.io/datastore/ha-embedded.
- K3s embedded-etcd HA is composed of three or more server nodes, optional
  agent nodes, and optionally a fixed registration address. Citation:
  https://docs.k3s.io/datastore/ha-embedded.
- The first HA server starts with `--cluster-init` and a shared token. Citation:
  https://docs.k3s.io/datastore/ha-embedded.
- K3s server nodes must match critical configuration flags, including network,
  component-disable, and feature flags. Citation:
  https://docs.k3s.io/datastore/ha-embedded.
- K3s requirements list inbound TCP 2379-2380 between servers for embedded
  etcd HA, TCP 6443 from agents to servers for supervisor/API, UDP 8472 for
  Flannel VXLAN, and TCP 10250 for kubelet metrics/API. Citation:
  https://docs.k3s.io/installation/requirements.
- K3s small HA-server sizing table lists up to 10 nodes as 2 vCPU and 4 GB RAM
  minimum for server nodes. Citation: https://docs.k3s.io/installation/requirements.
- D8 does not decide single server vs embedded-etcd HA vs external DB; it only
  decides self-managed k3s on Vultr VMs. Citation: `DECISIONS.md:186-194`.
- Proposal blocker: remote HA topology is not fully decided in current project
  sources; upstream supports both single-node and HA patterns, but D8 only
  fixes k3s-on-VM substrate.

### 3.3 Vultr VM provisioning surface

- Vultr Terraform provider has a `vultr_instance` resource for creating and
  managing virtual machine instances with configurable plans, regions, and
  operating systems. Citation:
  https://docs.vultr.com/reference/terraform/resources/instance.
- `vultr_instance` supports `firewall_group_id`, `vpc_ids`,
  `ssh_key_ids`, `user_data`, `hostname`, `tags`, and `label` attributes.
  Citation: https://docs.vultr.com/reference/terraform/resources/instance.
- Vultr docs say `user_data` is a generic store used by provisioning tools and
  cloud OSes as configuration and is generally consumed once at launch. Citation:
  https://docs.vultr.com/reference/terraform/resources/instance.
- Vultr cloud-init article says Terraform can provision Vultr Cloud Servers and
  initialize them with Cloud-Init. Citation:
  https://docs.vultr.com/provision-a-vultr-cloud-server-with-terraform-and-cloud-init.
- Vultr cloud-init article warns that applying the demo deploys actual cloud
  resources and unused services should be destroyed. Citation:
  https://docs.vultr.com/provision-a-vultr-cloud-server-with-terraform-and-cloud-init.
- Vultr `vultr_vpc` creates, manages, and deletes VPC networks with region,
  description, subnet, and mask. Citation:
  https://docs.vultr.com/reference/terraform/resources/vpc.
- Vultr `vultr_vpc2` is documented as deprecated and replaced by `vultr_vpc`.
  Citation: https://docs.vultr.com/reference/terraform/resources/vpc2.
- INIT-008's existing network module already uses `vultr_vpc`, not
  `vultr_vpc2`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-network/main.tf:29-34`.
- GitHub API check on 2026-04-25 reports latest Vultr Terraform provider
  release `v2.31.0`, published 2026-04-21. Citation:
  https://github.com/vultr/terraform-provider-vultr/releases/tag/v2.31.0.
- The locked memory says provider constraint `vultr/vultr ~> 2.30` and
  OpenTofu `>= 1.8.0`; current provider latest is `v2.31.0`, so proposal must
  either keep the existing constraint or update it explicitly. Citations:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/platform-stack.md:11`;
  https://github.com/vultr/terraform-provider-vultr/releases/tag/v2.31.0.

### 3.4 Vultr plans and minimum sizing evidence

- Vultr public plans API was reachable without auth on 2026-04-25 at
  `https://api.vultr.com/v2/plans?per_page=500`. Command evidence from this
  session.
- Observed EWR-capable candidate plans:
  `vc2-1c-2gb` = 1 vCPU, 2048 MB RAM, 55 GB SSD, $10/month;
  `vc2-2c-2gb` = 2 vCPU, 2048 MB RAM, 65 GB SSD, $15/month;
  `vc2-2c-4gb` = 2 vCPU, 4096 MB RAM, 80 GB SSD, $20/month;
  `vhf-2c-4gb` = 2 vCPU, 4096 MB RAM, 128 GB high-frequency disk, $24/month.
  Command evidence: Vultr plans API query run 2026-04-25.
- K3s small HA-server minimum is 2 vCPU and 4 GB RAM for up to 10 nodes.
  Citation: https://docs.k3s.io/installation/requirements.
- Evidence-based sizing implication: `vc2-2c-4gb` and `vhf-2c-4gb` meet the
  upstream small HA-server CPU/RAM minimum; `vc2-1c-2gb` and `vc2-2c-2gb` do
  not meet both CPU/RAM minimums for HA servers. Sources:
  K3s requirements URL above plus Vultr plans API command evidence.
- INIT-008 dev channel used `vc2-2c-4gb` for VKE node-pool nodes, which happens
  to match the K3s small HA-server CPU/RAM minimum. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:16-19`.
- This is sizing evidence, not a remote topology decision.

### 3.5 Remote kubeconfig retrieval evidence

- K3s writes kubeconfig at `/etc/rancher/k3s/k3s.yaml` after install. Citation:
  https://docs.k3s.io/quick-start.
- K3sup fetches kubeconfig from a remote VM and updates it for workstation
  kubectl access. Citation: https://github.com/alexellis/k3sup.
- K3sup runs over SSH, installs k3s, fetches kubeconfig, and can join agents.
  Citation: https://github.com/alexellis/k3sup.
- Vultr Marketplace's k3s app documentation says its preconfigured image
  exposes kubeconfig at `/root/k3s-public.yaml` after SSH login. Citation:
  https://www.vultr.com/marketplace/apps/k3s/.
- Research implication: remote kubeconfig retrieval has at least three evidence
  paths: direct SSH copy of `/etc/rancher/k3s/k3s.yaml`, k3sup, and Vultr
  Marketplace app behavior. The proposal must choose the project path.

### 3.6 Known Vultr+k3s references

- Official Vultr Marketplace has a k3s app that deploys a preconfigured k3s
  environment with kubectl and helm. Citation:
  https://www.vultr.com/marketplace/apps/k3s/.
- The Vultr Marketplace app is not the same as OpenTofu+cloud-init bootstrap,
  but it confirms Vultr-hosted VM k3s is an acknowledged Vultr path. Citation:
  https://www.vultr.com/marketplace/apps/k3s/.
- Greg Meszaros's 2020 article demonstrates k3sup installing a multi-node k3s
  cluster on separate Vultr VMs with SSH keys and master/worker nodes. Citation:
  https://gregmeszaros.medium.com/lightweight-kubernetes-cluster-on-vultr-com-7264e8fc03b1.
- k3sup upstream is provider-agnostic but explicitly supports bootstrapping k3s
  onto any VM, including through cloud-init, and supports HA/multi-master.
  Citation: https://github.com/alexellis/k3sup.
- Search found generic Terraform/k3s modules, for example
  `xunleii/k3s/module`, that manage k3s on given machines, but the first
  search pass did not confirm a current, official Vultr-specific Terraform k3s
  module suitable as a project dependency. Citation:
  https://registry.terraform.io/modules/xunleii/k3s/module/latest.
- Research classification: confirmed Vultr-VM-based k3s references exist
  (Vultr Marketplace, k3sup-on-Vultr article), but a maintained
  OpenTofu/Vultr/k3s/cloud-init reference architecture was not confirmed in the
  first-pass search.

## 4. Channel Schema - k3s-Shaped Fields

This section records evidence-backed schema pressure. Final schema is proposal
work.

- Current INIT-008 schema has `cluster.kubernetes_version` with VKE tag shape.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:145-148`.
- Current INIT-008 dev channel uses `v1.32.9+3`, a VKE-shaped version value.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:13-16`.
- Upstream k3s release tags use `vX.Y.Z+k3sN`; latest observed is
  `v1.35.3+k3s1`. Citation:
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1.
- D8 requires Kubernetes distribution to be self-managed k3s everywhere.
  Citation: `DECISIONS.md:186-194`.
- Environment-agnostic memory says local Kubernetes is k3s in k3d and remote
  Kubernetes is k3s on Vultr Cloud Compute VMs. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:15-18`.
- Research-backed top-level cluster fields required by D8:
  `cluster.distribution = k3s`, `cluster.target = k3d-local | vultr-vms`,
  and `cluster.k3s_version = vX.Y.Z+k3sN`. Citations:
  `DECISIONS.md:186-194`;
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1.
- For `vultr-vms`, field pressure comes from K3s topology and Vultr instance
  resource shape: server count, server plan, agent count, agent plan, region,
  VPC/firewall/SSH/user_data, and bootstrap token handling. Citations:
  https://docs.k3s.io/datastore/ha-embedded;
  https://docs.vultr.com/reference/terraform/resources/instance.
- For `k3d-local`, field pressure comes from k3d flags: server count, agent
  count, registry create/use/config, k3s image, kubeconfig behavior, port
  mappings, and volumes. Citations:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/;
  https://k3d.io/stable/usage/registries/;
  https://k3d.io/stable/usage/kubeconfig/.
- The prompt's proposed local fields
  `cluster.k3d_servers`, `cluster.k3d_agents`, and
  `cluster.k3d_registry_name` map directly to k3d `--servers`, `--agents`, and
  `--registry-create/--registry-use` capabilities. Citation:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/.
- The prompt's proposed remote fields `cluster.servers.count`,
  `cluster.servers.plan`, `cluster.agents.count`, `cluster.agents.plan`, and
  `cluster.region` map to K3s server/agent topology and Vultr `plan`/`region`.
  Citations: https://docs.k3s.io/datastore/ha-embedded and
  https://docs.vultr.com/reference/terraform/resources/instance.
- The existing channel resolver structurally supports parent inheritance and
  field overrides; the field names are what must change. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/resolve_platform_channel.py:143-189`.
- The existing tfvars generator does not support target-specific payloads; it
  assumes one VKE-shaped cluster payload. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/generate_channel_tfvars.py:14-82`.
- Open question: whether schema version remains `1` with a clean replacement
  before merge or bumps. No-backwards-compatibility rules forbid dual readers;
  D8 says wrong-shaped work is reference-only. Citations:
  `DECISIONS.md:204-205`;
  `product-strategy/tickets/PHASE_5_INDEX.md:108-115`.

## 5. Salvageable Structure from INIT-008

- Reuse: `infra/templates/platform-channel/` as the template directory shape.
  Evidence: channel-template memory names this shape, and INIT-008 implemented
  it. Citations:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:50-56`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/.pipeline/proposal.md:90-95`.
- Reuse: `infra/bootstrap/state-backend/`, because Object Storage remote state
  remains. Citations:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/platform-stack.md:15-16`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/bootstrap/state-backend/main.tf:47-69`.
- Reuse: `infra/modules/platform-network/`, because remote Vultr VM channels
  still need a VPC and the module already uses `vultr_vpc`. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-network/main.tf:29-50`;
  https://docs.vultr.com/reference/terraform/resources/vpc.
- Discard: `infra/modules/platform-cluster/`, because it is VKE-specific.
  Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-cluster/main.tf:1-2`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-cluster/main.tf:50-64`;
  `DECISIONS.md:211-213`.
- Rewrite: `infra/templates/platform-channel/main.tf`, because it calls the
  VKE module. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/templates/platform-channel/main.tf:9-20`.
- Rewrite: channel YAML schemas, because they encode VKE version and node-pool
  fields. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:137-164`.
- Reuse structurally: `resolve_platform_channel.py`, because parent lookup,
  inheritance, fixture handling, and structured errors are not VKE-specific.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/resolve_platform_channel.py:65-189`.
- Reuse structurally but rewrite payload: `generate_channel_tfvars.py`, because
  the current emitted keys are VKE-shaped. Citation:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/generate_channel_tfvars.py:14-82`.

## 6. Toolchain Check

- `tofu` is present at `/home/nes/.local/bin/tofu`. Command evidence:
  `command -v tofu`, 2026-04-25.
- `tofu version` reports `OpenTofu v1.11.5 on linux_amd64`. Command evidence:
  `tofu version`, 2026-04-25.
- `kubectl` is present at `/usr/local/bin/kubectl`. Command evidence:
  `command -v kubectl`, 2026-04-25.
- `kubectl version --client=true -o yaml` reports client `v1.34.1`,
  git commit `93248f9ae092f571eb870b7664c534bfc7d00f03`, build date
  `2025-09-09T19:44:50Z`, platform `linux/amd64`. Command evidence:
  `kubectl version --client=true -o yaml`, 2026-04-25.
- The same command reports embedded `kustomizeVersion: v5.7.1`. Command
  evidence: `kubectl version --client=true -o yaml`, 2026-04-25.
- `docker` is present at `/usr/bin/docker`. Command evidence:
  `command -v docker`, 2026-04-25.
- `docker --version` reports `Docker version 29.4.0, build 9d7ad9f`; `docker
  info --format '{{json .ServerVersion}}'` reports `29.4.0`. Command evidence,
  2026-04-25.
- `k3d` is not present in `PATH`; `k3d --version` exits 127 with `command not
  found`. Command evidence: `k3d --version`, 2026-04-25.
- `k3s` is not present in `PATH`; `k3s --version` exits 127 with `command not
  found`. Command evidence: `k3s --version`, 2026-04-25.

## 7. Known Risks and Open Questions

### BLOCKS_PROPOSAL

- Remote HA topology: D8 fixes k3s-on-Vultr-VMs but does not choose single
  server, embedded-etcd HA, or external database. Evidence: D8 scope at
  `DECISIONS.md:186-194`; K3s HA evidence at
  https://docs.k3s.io/datastore/ha-embedded.
- Fixed registration endpoint for remote HA: K3s HA docs allow an optional
  fixed registration address, but current INIT-101 sources do not decide
  whether that is a Vultr Load Balancer, reserved IP, one server address, or a
  later component. Evidence: https://docs.k3s.io/datastore/ha-embedded and
  Vultr resource list at https://docs.vultr.com/reference/terraform/resources.
- k3s version pinning strategy: upstream supports exact
  `INSTALL_K3S_VERSION`, channels, and current latest `v1.35.3+k3s1`, while
  prompt examples use `v1.32.5+k3s1`. Evidence:
  https://docs.k3s.io/upgrades/manual and
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1.
- k3d version pinning strategy: k3d supports `TAG`, current latest is
  `v5.8.3`, and k3d is absent locally. Evidence: https://k3d.io/stable/ and
  command evidence from the toolchain check.
- Provider version strategy: project memory says `vultr/vultr ~> 2.30`; latest
  provider observed is `v2.31.0`. Evidence:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/platform-stack.md:11`;
  https://github.com/vultr/terraform-provider-vultr/releases/tag/v2.31.0.
- Channel schema versioning: current schema is `schema_version: 1`; field shape
  replacement is breaking, and no backwards compatibility is allowed. Evidence:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:17-19`;
  `product-strategy/tickets/PHASE_5_INDEX.md:108-115`.
- Transition from archived INIT-008: D8 says wrong-shaped INIT-008 is reference
  only, but this current worktree already has a stale `.pipeline/research.md`
  from another slice before this research rewrite. Evidence:
  `.pipeline/research.md` pre-write command evidence, 2026-04-25; D8 citation:
  `DECISIONS.md:204-205`.

### BLOCKS_IMPLEMENTATION

- k3d install is required before a local k3d cluster can be created; toolchain
  check shows it absent. Command evidence: `k3d --version`, 2026-04-25.
- k3s cloud-init idempotency needs exact user_data behavior. Vultr docs say
  `user_data` is generally consumed once at launch; k3s docs say re-running the
  installer can alter service config and missing previous options can be lost.
  Citations:
  https://docs.vultr.com/reference/terraform/resources/instance and
  https://docs.k3s.io/installation/configuration.
- Remote token handling requires a secure source for `K3S_TOKEN` and a
  bootstrap/join sequence. Evidence: K3s docs require shared secret for HA and
  agent joins. Citations: https://docs.k3s.io/datastore/ha-embedded and
  https://docs.k3s.io/quick-start.
- Firewall rules must map K3s requirements: 6443, 2379-2380 for embedded etcd,
  8472/51820/51821 depending on flannel backend, 10250, and any operator SSH
  path. Evidence: https://docs.k3s.io/installation/requirements and
  https://docs.vultr.com/reference/terraform/resources/firewall_rule.
- Remote kubeconfig retrieval needs a secure artifact path and redaction rules.
  Evidence: K3s writes `/etc/rancher/k3s/k3s.yaml`; k3sup fetches kubeconfig;
  Vultr Marketplace k3s uses `/root/k3s-public.yaml`. Citations:
  https://docs.k3s.io/quick-start;
  https://github.com/alexellis/k3sup;
  https://www.vultr.com/marketplace/apps/k3s/.
- Harness must create a real local k3d cluster as done state, not only
  `tofu validate`; D8 and Phase 5 index require real local components. Citations:
  `DECISIONS.md:201-203`;
  `product-strategy/tickets/PHASE_5_INDEX.md:122-127`.

### INFORMATIONAL

- `vultr_vpc2` appears in Vultr resource docs but is deprecated in favor of
  `vultr_vpc`; INIT-008 already used `vultr_vpc`. Citations:
  https://docs.vultr.com/reference/terraform/resources/vpc2 and
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-network/main.tf:29-34`.
- K3s includes a default ingress controller unless disabled or changed; ingress
  choices are likely INIT-110/Kong territory, not INIT-101. Evidence:
  k3d exposing-services docs mention k3s deploys Traefik by default; Phase 5
  index assigns Kong ingress to INIT-110. Citations:
  https://k3d.io/stable/usage/exposing_services/ and
  `product-strategy/tickets/PHASE_5_INDEX.md:38`.
- INIT-101 does not install Flux; INIT-102 owns GitOps substrate after INIT-101.
  Citation: `product-strategy/tickets/PHASE_5_INDEX.md:29-30`.
- INIT-101 does not define Crossplane app-cluster claims; INIT-106 owns
  application cluster provisioning after INIT-101/102/103. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:34`.
- INIT-101 remote mode can stop at contract/plan evidence locally if proposal
  scopes remote apply out, but local mode cannot stop at dry-run because D8
  requires real local deployment target. Citations:
  `DECISIONS.md:201-203`;
  `/home/nes/projects/server-manager/worktrees/phase-5-replan/.pipeline/replan.md:607-625`.

## 8. Suggested Slice Decomposition Sketch

This is a handoff sketch for proposal refinement, not final design approval.

- SLICE-100: Replace INIT-008 substrate shape.
  Evidence basis: VKE-specific module/schema/template/dev YAML are present in
  INIT-008, and D8 says they must not merge. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/modules/platform-cluster/main.tf:50-64`;
  `DECISIONS.md:251-259`.
- SLICE-101: k3d local cluster bring-up surface.
  Evidence basis: k3d supports channel-relevant server/agent/registry/kubeconfig
  parameters, and the local channel must create a real cluster. Citations:
  https://k3d.io/stable/usage/commands/k3d_cluster_create/;
  `product-strategy/tickets/PHASE_5_INDEX.md:122-127`.
- SLICE-102: Vultr VM module plus cloud-init k3s bootstrap contract.
  Evidence basis: `vultr_instance` supports plan, region, SSH keys, VPC ids,
  firewall group, and `user_data`; K3s supports install script/config/env vars.
  Citations:
  https://docs.vultr.com/reference/terraform/resources/instance and
  https://docs.k3s.io/installation/configuration.
- SLICE-103: Channel template and channel root rewrite for k3s-shaped fields.
  Evidence basis: existing template/root/generator structure is reusable, but
  emitted fields are VKE-shaped. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/templates/platform-channel/main.tf:1-20`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/scripts/generate_channel_tfvars.py:14-82`.
- SLICE-104: Local k3d bootstrap end-to-end verification.
  Evidence basis: D8 requires real local components, k3d can create/delete
  clusters and manage kubeconfig, and current k3d is absent. Citations:
  `DECISIONS.md:201-203`;
  https://k3d.io/stable/usage/kubeconfig/;
  toolchain command evidence from 2026-04-25.
- SLICE-105: Documentation and handoff.
  Evidence basis: downstream INIT-102 and INIT-106 depend on INIT-101's control
  cluster contract. Citation: `product-strategy/tickets/PHASE_5_INDEX.md:29-34`.

## 9. Proposal-Phase Priority Items

- Priority 1: decide remote control-plane topology and registration endpoint:
  single server versus embedded-etcd HA versus external DB, plus how agents and
  operators reach the API. Evidence: K3s HA docs and D8 substrate decision.
  Citations: https://docs.k3s.io/datastore/ha-embedded and `DECISIONS.md:186-194`.
- Priority 2: decide exact k3s/k3d/provider pinning strategy. Evidence:
  k3s latest `v1.35.3+k3s1`, k3d latest `v5.8.3`, Vultr provider latest
  `v2.31.0`, project memory provider constraint `~> 2.30`, and k3d/k3s
  upstream support for exact pins. Citations:
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1;
  https://github.com/k3d-io/k3d/releases/tag/v5.8.3;
  https://github.com/vultr/terraform-provider-vultr/releases/tag/v2.31.0;
  https://k3d.io/stable/;
  https://docs.k3s.io/upgrades/manual.
- Priority 3: define the k3s-shaped channel schema and migration/deletion
  boundary for INIT-008 artifacts without compatibility shims. Evidence:
  current schema/dev YAML are VKE-shaped and Phase 5 forbids wrong-shaped
  work. Citations:
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/schemas/platform-channel.schema.json:137-164`;
  `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml:13-21`;
  `product-strategy/tickets/PHASE_5_INDEX.md:108-115`.

## 10. Confirmed Reference URLs

- k3d docs used: https://k3d.io/stable/,
  https://k3d.io/stable/usage/commands/k3d_cluster_create/,
  https://k3d.io/stable/usage/kubeconfig/,
  https://k3d.io/stable/usage/registries/,
  https://k3d.io/stable/usage/exposing_services/,
  https://github.com/k3d-io/k3d/releases/tag/v5.8.3.
- k3s docs used: https://docs.k3s.io/quick-start,
  https://docs.k3s.io/installation/configuration,
  https://docs.k3s.io/upgrades/manual,
  https://docs.k3s.io/datastore/ha-embedded,
  https://docs.k3s.io/installation/requirements,
  https://github.com/k3s-io/k3s/releases/tag/v1.35.3%2Bk3s1.
- Vultr docs used: https://docs.vultr.com/reference/terraform/resources,
  https://docs.vultr.com/reference/terraform/resources/instance,
  https://docs.vultr.com/reference/terraform/resources/vpc,
  https://docs.vultr.com/reference/terraform/resources/vpc2,
  https://docs.vultr.com/reference/terraform/resources/firewall_group,
  https://docs.vultr.com/reference/terraform/resources/firewall_rule,
  https://docs.vultr.com/reference/terraform/resources/object_storage,
  https://docs.vultr.com/reference/terraform/resources/ssh_key,
  https://docs.vultr.com/provision-a-vultr-cloud-server-with-terraform-and-cloud-init,
  https://github.com/vultr/terraform-provider-vultr/releases/tag/v2.31.0.
- Vultr+k3s references used: https://www.vultr.com/marketplace/apps/k3s/,
  https://github.com/alexellis/k3sup,
  https://gregmeszaros.medium.com/lightweight-kubernetes-cluster-on-vultr-com-7264e8fc03b1,
  https://registry.terraform.io/modules/xunleii/k3s/module/latest.
