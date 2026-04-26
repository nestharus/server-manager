# INIT-101 Phase 3 Proposal: Self-Managed k3s Control Cluster
## Binding sources
- `.pipeline/research.md` - Phase 1 evidence for replacing the archived
  VKE-shaped INIT-008 substrate with k3s/k3d/Vultr-VMs.
- `.pipeline/synthesis.md` - Phase 2 synthesis, D1-D12, stale-material
  disposition, and six implementation slices.
- `worktrees/phase-5-replan/.pipeline/replan.md` - Section 5, INIT-101
  corrected Phase 5 scope.
- `DECISIONS.md` D8 - environment-agnostic Phase 5 reset:
  local-as-first-deployment and self-managed k3s everywhere.
- `memory/environment-agnostic-stack.md` - local is a deployment target, not a
  dry-run or simulation.
- `memory/two-tier-cluster-architecture.md` - control cluster hosts platform
  controllers; application workloads wait for app clusters.
- `memory/channel-template-pattern.md` - channels replace hard
  `dev/staging/production` roots and carry provider/endpoint config.
- `memory/platform-stack.md` - Vultr, OpenTofu, Vultr Object Storage remote
  state, Buildkite, and Flux remain locked; VKE is superseded by D8.
- `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md` - closest
  proposal shape precedent and source for salvage/discard boundaries.
- `worktrees/init-008-platform-bootstrap/infra/` - reference copy of the
  VKE-shaped substrate to salvage structurally or discard.
- `product-strategy/tickets/INIT-001.md` - ticket-ready initiative framing
  shape.
- `~/ai/conventions/no-backwards-compatibility.md` - old VKE field/module/root
  shape is deleted, not adapted.
- `~/ai/conventions/no-deferred-stubs.md` - postponed work must be explicit
  anti-scope with a named successor, not a placeholder.
This proposal is bound to synthesis decisions D1-D12:
- D1: k3s is pinned to `v1.32.13+k3s1`.
- D2: k3d is pinned to `v5.8.3`.
- D3: local k3d cluster names are `humility-<channel_id>`.
- D4: local topology is one k3d server and one k3d agent.
- D5: remote INIT-101 topology is a single k3s server.
- D6: remote server plan default is `vc2-2c-4gb`.
- D7: Vultr provider constraint remains `~> 2.30`.
- D8: channel schema is replaced with k3s-shaped fields.
- D9: remote bootstrap is cloud-init plus the official k3s installer.
- D10: kubeconfig retrieval is channel-scoped.
- D11: Vultr Object Storage state-backend bootstrap is reused unchanged.
- D12: active VKE-shaped INIT-008 artifacts are deleted in this branch.
No proposal section may preserve VKE compatibility, substitute dry-runs for
the real local cluster, or turn future remote work into checked-in stubs.
---
## 1. Executive summary
INIT-101 establishes the self-managed k3s control-cluster substrate for Phase
5. The local channel runs k3d, which is k3s in Docker, and remote channels are
represented as OpenTofu-managed Vultr Cloud Compute VMs bootstrapped by
cloud-init using the standard `curl -sfL https://get.k3s.io | sh -` install
path. This is the replacement for INIT-008's VKE-shaped substrate. The done
state is concrete: a real local k3d cluster is up, a channel-scoped kubeconfig
is retrieved, and the harness proves `kubectl get nodes` succeeds against that
kubeconfig.
The proposal keeps the pieces of INIT-008 that matched the corrected
architecture and discards the pieces that encoded VKE. Salvageable structure
includes the channel-template directory layout, the channel resolver/generator
script shape, the Vultr Object Storage state-backend bootstrap module, the
Vultr VPC/network module concept, and the validation harness pattern. VKE
cluster code, VKE-shaped channel fields, VKE-shaped generated tfvars, hard
environment roots, and render-only completion criteria are deleted rather than
wrapped.
Ticket-ready framing mirrors INIT-001. **Subsystem:** Deployment substrate;
control-cluster bootstrap. **Phase:** Phase 5 reset successor, replacing
archived INIT-008. **Executive priority:** critical path for INIT-102 through
INIT-117. Flux, Infisical, Crossplane, DNS/TLS, app workloads, and later
control-plane operations all depend on an environment-agnostic control-cluster
contract that works locally first and can be parameterized for remote channels
later. **Proposal mechanism:** use the same k3s distribution family locally
and remotely, express the target through channel config, and verify the local
deployment with a real cluster before any remote apply exists.
This initiative intentionally stops short of remote deployment. The remote
Vultr VM/cloud-init path must validate and plan, but INIT-101 does not spend
Vultr resources or fetch a remote kubeconfig. That boundary is not a dry-run
substitute for local work: local k3d is the first deployment target and must
come up as the completion proof. Remote apply, remote HA, Flux, Crossplane,
Infisical, DNS, TLS, and application workloads are named successor work.
---
## 2. Architecture
### 2.1 Control-cluster boundary
INIT-101 owns the control-cluster substrate only.
The control cluster is the platform cluster that later hosts:
- Flux, installed by INIT-102.
- Infisical runtime secret store, installed by INIT-103.
- Crossplane, installed by INIT-106.
- Control-plane DNS/TLS/security/observability components from later INITs.
It does not host application workloads in INIT-101. The API service, Discord
daemon, data plane, app ingress, app auth, and workload observability wait for
application clusters and later Phase 5 initiatives. This preserves the
two-tier architecture while updating the old memory's VKE references to D8's
k3s-on-k3d/Vultr-VM substrate.
### 2.2 Repo layout after INIT-101
The implementation leaves `infra/` in this shape:
```text
infra/
  README.md
  schemas/
    platform-channel.schema.json
    platform-channel-resolved.schema.json
  channels/
    local.yaml
    dev.yaml
    fixtures/
      local-child.yaml
      dev-child.yaml
      ephemeral-disabled.yaml
      missing-parent.yaml
      circular-a.yaml
      circular-b.yaml
  templates/
    platform-channel/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
  roots/
    channels/
      local/
        main.tf
        backend.tfbackend
        channel.auto.tfvars.json
      dev/
        main.tf
        backend.tfbackend
        channel.auto.tfvars.json
  bootstrap/
    state-backend/
      main.tf
      versions.tf
  modules/
    platform-network/
      main.tf
      versions.tf
    platform-cluster-k3d/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    platform-cluster-vms/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
      cloud-init/
        k3s-server.yaml.tftpl
  scripts/
    resolve_platform_channel.py
    spawn_platform_channel.py
    generate_channel_backend.py
    generate_channel_tfvars.py
    validate_platform_channels.py
    bring-up-local-channel.sh
    delete-local-channel.sh
  tests/
    validate_platform_bootstrap.sh
```
The old roots and module are removed:
```text
infra/environments/dev/
infra/environments/staging/
infra/environments/production/
infra/modules/platform-cluster/
```
No `legacy/`, `archived/`, symlink, forwarding module, deprecated alias, or
dual schema reader remains. The reference copy is the
`feat/init-008-platform-bootstrap` branch and its worktree, not an active
directory in this branch.
### 2.3 Channel schema
The source schema remains:
```text
infra/schemas/platform-channel.schema.json
```
The resolved schema remains:
```text
infra/schemas/platform-channel-resolved.schema.json
```
The schema version remains `1`, but the field shape is a clean replacement.
This follows D8 and the no-backwards-compatibility rule: there is no old VKE
reader for `schema_version: 1`, because the wrong-shaped work never becomes
the accepted main-path contract.
Top-level source fields stay channel-shaped: `schema_version`, `id`, `parent`,
`exposure`, `tenant`, `allow_ephemeral_children`, `enabled_platforms`,
`platform`, `cluster`, and `state`. `schema_version` accepts only `1`;
channel ids use `^[a-z0-9][a-z0-9-]*$`; `exposure` is `prod`, `stage`, or
`dev`; `enabled_platforms` accepts `kubernetes` for INIT-101.
The required k3s replacement fields are:
- `platform.provider: local | vultr`, plus provider-specific region, network,
  and object-storage endpoint fields.
- `cluster.distribution: k3s`.
- `cluster.target: k3d-local | vultr-vms`.
- `cluster.k3s_version`, matching `vX.Y.Z+k3sN`.
- `cluster.kubeconfig_path`, always channel-scoped.
- For `k3d-local`: `k3d.cluster_name`, `servers`, `agents`,
  `registry_name`, `api_port`, `port_mappings`, and `volumes`.
- For `vultr-vms`: `vultr.region`, network, firewall, `servers.count`,
  `servers.plan`, `agents.count`, `agents.plan`, `ssh_key_ids`, and
  `bootstrap` with install version, remote kubeconfig path, and token input.
- `state.backend: local | s3-compatible`, with bucket/key/region/endpoint
  fields appropriate to that backend.
Resolved channels must contain concrete inherited values, no unresolved parent
links for OpenTofu consumption, and `additionalProperties: false` everywhere
unless a field is explicitly documented open. Generated tfvars consume the
resolved schema only.
### 2.4 Initial channels
INIT-101 ships two active channel declarations:
```text
infra/channels/local.yaml
infra/channels/dev.yaml
```
`local.yaml` is the done-state channel: `provider: local`,
`cluster.target: k3d-local`, `cluster.k3s_version: v1.32.13+k3s1`,
`cluster.kubeconfig_path: infra/channels/local/.generated/kubeconfig.yaml`,
`k3d.cluster_name: humility-local`, `k3d.servers: 1`, `k3d.agents: 1`, local
state, and optional local registry/API-port/port/volume fields.
`dev.yaml` is the remote Vultr VM plan channel: `provider: vultr`,
`region: ewr`, `network: 10.40.0.0/20`, `cluster.target: vultr-vms`,
`cluster.k3s_version: v1.32.13+k3s1`, single server plan `vc2-2c-4gb`, zero
agents by default, cloud-init bootstrap with remote kubeconfig path
`/root/humility-k3s.yaml`, and Vultr Object Storage state key
`channels/dev/terraform.tfstate`.
Remote values that would cause real mutation, such as SSH key IDs and allowed
SSH CIDRs, are accepted only as plan inputs where OpenTofu can validate the
root. They are not runtime stubs; remote apply is explicitly anti-scope.
### 2.5 `platform-cluster-k3d` module
New module:
```text
infra/modules/platform-cluster-k3d/
```
This module is the local target surface. It does not call the Vultr provider.
It may use the `null` provider and `local-exec` only if the implementation
keeps the command path deterministic and validates inputs before execution.
The preferred local bring-up path is the script in Section 2.10, with the
module exposing generated outputs consumed by the channel root. The module
owns:
- k3d cluster name.
- k3s image/version value derived from D1.
- server count `1`.
- agent count `1`.
- optional local registry name.
- optional API port.
- optional port and volume mappings.
- channel-scoped kubeconfig path.
- outputs for cluster name, kubeconfig path, server count, and agent count.
The module must not fall back to kind, Docker Compose Kubernetes, minikube, or
the operator's global kubeconfig. It must not silently reduce the topology to a
single node if the agent cannot start. A failed two-node local topology is a
failure to fix, not a downgrade.

Variable contract for `infra/modules/platform-cluster-k3d/variables.tf`:

| Variable | Type | Default | Description |
|---|---:|---|---|
| `channel_id` | `string` | no default; required | Channel identifier used for labels and generated paths. No default; required. |
| `cluster_name` | `string` | no default; required | k3d cluster name resolved from `k3d.cluster_name`. No default; required. |
| `k3s_version` | `string` | no default; required | Pinned k3s version used for the local k3d node image. No default; required. |
| `server_count` | `number` | `1` | Number of k3d server nodes; INIT-101 expects one. Default: `1`. |
| `agent_count` | `number` | `1` | Number of k3d agent nodes; INIT-101 expects one. Default: `1`. |
| `kubeconfig_path` | `string` | no default; required | Channel-scoped generated kubeconfig path. No default; required. |
| `registry_name` | `string` | `null` | Optional local k3d registry name. Default: `null`. |
| `api_port` | `string` | `null` | Optional host API-port binding passed to k3d. Default: `null`. |
| `port_mappings` | `list(string)` | `[]` | Optional k3d port mappings. Default: `[]`. |
| `volume_mappings` | `list(string)` | `[]` | Optional k3d volume mappings. Default: `[]`. |
### 2.6 `platform-cluster-vms` module
New module:
```text
infra/modules/platform-cluster-vms/
```
This replaces the VKE module:
```text
infra/modules/platform-cluster/
```
The new module provisions remote plan-surface resources only:
- One `vultr_instance` server by default.
- Optional future agent instances from `agents.count`, default `0`.
- VPC attachment through the existing `platform-network` output.
- Firewall group/rules sufficient for the single-server plan surface.
- SSH key IDs as required inputs for apply-capable remote channels.
- `user_data` rendered from cloud-init.
- Outputs for server label, server IP, remote kubeconfig path, and cluster
  version.
The module must not use `vultr_kubernetes`. It must not preserve VKE variables
such as `cluster_kubernetes_version`, `node_plan`, `node_quantity`,
`ha_controlplanes`, or `enable_firewall` as compatibility aliases.

Variable contract for `infra/modules/platform-cluster-vms/variables.tf`:

| Variable | Type | Default | Description |
|---|---:|---|---|
| `channel_id` | `string` | no default; required | Channel identifier used for names, tags, and labels. No default; required. |
| `region` | `string` | no default; required | Vultr region resolved from the channel. No default; required. |
| `vpc_id` | `string` | no default; required | Existing Vultr VPC identifier from `platform-network`. No default; required. |
| `k3s_version` | `string` | no default; required | Pinned k3s version exported to the installer. No default; required. |
| `server_count` | `number` | `1` | Number of remote server VMs for INIT-101. Default: `1`. |
| `server_plan` | `string` | `"vc2-2c-4gb"` | Vultr plan for server VMs. Default: `"vc2-2c-4gb"`. |
| `agent_count` | `number` | `0` | Number of remote agent VMs for INIT-101. Default: `0`. |
| `agent_plan` | `string` | `"vc2-2c-4gb"` | Vultr plan for future agent VMs. Default: `"vc2-2c-4gb"`. |
| `ssh_key_ids` | `list(string)` | no default; required | Vultr SSH key IDs for apply-capable remote channels. No default; required. |
| `allowed_ssh_cidrs` | `list(string)` | no default; required | CIDRs allowed to reach SSH on remote VMs. No default; required. |
| `remote_kubeconfig_path` | `string` | `"/root/humility-k3s.yaml"` | Path where cloud-init copies the server kubeconfig. Default: `"/root/humility-k3s.yaml"`. |
| `firewall_name` | `string` | `null` | Optional explicit firewall group name. Default: `null`. |
### 2.7 Cloud-init template
Cloud-init lives at:
```text
infra/modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl
```
The template writes a k3s config and installs the pinned version:
```yaml
#cloud-config
write_files:
  - path: /etc/rancher/k3s/config.yaml
    owner: root:root
    permissions: "0600"
    content: |
      write-kubeconfig-mode: "0600"
      node-name: ${node_name}
runcmd:
  - export INSTALL_K3S_VERSION="${k3s_version}"
  - curl -sfL https://get.k3s.io | sh -
  - cp /etc/rancher/k3s/k3s.yaml ${remote_kubeconfig_path}
  - chmod 0600 ${remote_kubeconfig_path}
```
The actual implementation may add strict shell flags, file existence checks,
and token handling. It may not switch to k3sup, the Vultr Marketplace k3s app,
or an unpinned installer.

Cloud-init idempotency is part of the plan contract even though remote apply is
anti-scope in INIT-101:
- k3s installation runs at most once per VM, guarded by
  `/var/lib/k3s-installed` or by checking for an existing k3s systemd unit.
- Config and kubeconfig writes are in `runcmd` steps with prerequisite checks;
  they do not overwrite an existing valid config or valid kubeconfig copy.
- Given the same resolved channel inputs, the rendered `user_data` payload is
  byte-identical between harness runs.
### 2.8 Channel template
The template remains:
```text
infra/templates/platform-channel/
```
`main.tf` is rewritten to dispatch by `cluster.target`:
- `k3d-local` calls `infra/modules/platform-cluster-k3d`.
- `vultr-vms` calls `infra/modules/platform-network` and
  `infra/modules/platform-cluster-vms`.
Because OpenTofu module counts/for_each have static-shape implications, the
implementation can use explicit conditional module `count` blocks or split
target-specific locals, but it must keep one channel template directory and one
generated root shape. It must not revive hard environment roots or create a
parallel "local-only" template that bypasses the channel contract.
Generated tfvars must contain only the k3s-shaped payload:
- `channel_id`
- `exposure`
- `cluster_distribution`
- `cluster_target`
- `cluster_k3s_version`
- `cluster_kubeconfig_path`
- `k3d_*` fields for local targets
- `vultr_*` fields for remote targets
- `state_*` fields
No generated tfvars may contain `kubernetes_version`, `node_pools`,
`ha_controlplanes`, `enable_firewall` as VKE managed-cluster fields, or
`vultr_kubernetes`-oriented names.
### 2.9 Kubeconfig retrieval
Local kubeconfig:
```text
infra/channels/local/.generated/kubeconfig.yaml
```
Local retrieval command:
```bash
k3d kubeconfig get humility-local > infra/channels/local/.generated/kubeconfig.yaml
```
The harness uses:
```bash
KUBECONFIG=infra/channels/local/.generated/kubeconfig.yaml kubectl get nodes
```
Remote kubeconfig, for post-INIT-101 remote deployment:
```text
/root/humility-k3s.yaml
```
Remote retrieval is an operator SSH copy after remote apply exists. INIT-101
does not implement or exercise that copy path because no remote cluster is
created.
Generated kubeconfigs and any generated local channel artifacts are ignored by
git:
```text
infra/channels/*/.generated/
```
### 2.10 Provider and version pins
OpenTofu:
- Required version: `>= 1.8.0`.
- Verified INIT-101 CLI version: `1.11.5`.
The `terraform { required_version = ">= 1.8.0" }` floor may remain in module
and root blocks for runtime compatibility, but the proposal, harness, and
operator docs verify OpenTofu `1.11.5` for INIT-101.
Providers:
- `vultr/vultr` or the project-standard Vultr provider source already used by
  the repo, constrained to `~> 2.30` per D7 and platform-stack memory.
- `hashicorp/local`, `hashicorp/null`, and `hashicorp/random` only if needed
  for generated local artifacts or remote token plan inputs.
Runtime tools:
- k3s: `v1.32.13+k3s1`.
- k3d: `v5.8.3`.
- kubectl: existing local tool is acceptable if it can talk to the created
  cluster.
- Docker: required by k3d.
Tool installer:
```text
infra/scripts/install-cluster-tools.sh
```
The installer pins k3d to `v5.8.3`, the current stable GitHub release at this
revision, and owns any future cluster-tier tool pins. It is idempotent and
supports `--check`, which exits nonzero if any required tool is missing or at
the wrong version. It may install k3d through the documented `TAG=v5.8.3`
installer path, but it must not install floating `latest`.
### 2.11 Local bring-up scripts
Primary script:
```text
infra/scripts/bring-up-local-channel.sh
```
Responsibilities:
- Resolve `infra/channels/local.yaml`.
- Generate backend and tfvars for `infra/roots/channels/local/`.
- Check Docker, kubectl, OpenTofu, and k3d.
- Ensure k3d is `v5.8.3` or install/check that exact tag.
- Create `humility-local` with one server and one agent.
- Use the pinned k3s image/version corresponding to `v1.32.13+k3s1`.
- Write `infra/channels/local/.generated/kubeconfig.yaml`.
- Run `kubectl get nodes` through that kubeconfig.
- Print the kubeconfig path and cluster name.
Idempotency contract:
- If `humility-local` already exists and matches the channel contract, succeed
  without re-creating it.
- If `humility-local` already exists and does not match the channel contract,
  fail with a clear message unless an explicit `--recreate` flag is supplied.
- A no-op second bring-up must leave generated backend, tfvars, and kubeconfig
  material byte-identical.
Companion script:
```text
infra/scripts/delete-local-channel.sh
```
Responsibilities:
- Delete `humility-local`.
- Remove the channel `.generated/` kubeconfig.
- Leave checked-in channel declarations and roots intact.
Idempotency contract:
- If `humility-local` does not exist, succeed without error.
- If generated local channel material is already absent, succeed without error.
- A no-op second tear-down must not modify checked-in files.
### 2.12 Harness extensions
Existing harness shape is preserved:
```text
infra/tests/validate_platform_bootstrap.sh
```
INIT-101 extends it to check:
- No active VKE artifacts remain.
- Channel schemas reject VKE-shaped fields.
- Channel resolver/generator output is drift-free.
- `tofu fmt -check` passes for `infra/`.
- `tofu init -backend=false` and `tofu validate` pass for
  `infra/bootstrap/state-backend`.
- `tofu init -backend=false` and `tofu validate` pass for
  `infra/roots/channels/local`.
- `tofu init -backend=false` and `tofu validate` pass for
  `infra/roots/channels/dev`.
- Provider lockfiles are drift-free: `.terraform.lock.hcl` is committed for
  every root that runs `tofu init`, regenerated with `tofu init -backend=false`,
  and byte-identical to the committed file.
- Modules do not carry `.terraform.lock.hcl` files because they are not
  independently initialized.
- `tofu plan` for the dev channel root is supported when required Vultr
  environment variables are present; otherwise the harness records a skipped
  remote plan with an explicit credential-missing message.
- Real local k3d cluster creation succeeds.
- Double bring-up succeeds as an idempotent no-op when the cluster already
  matches the channel contract.
- `KUBECONFIG=infra/channels/local/.generated/kubeconfig.yaml kubectl get nodes`
  returns at least one node and, under the default topology, one server and one
  agent node.
- Double tear-down succeeds when the cluster and generated kubeconfig are
  already absent.
- Cloud-init `user_data` render is byte-identical between runs with the same
  resolved channel inputs.
Skipping remote plan for missing credentials is allowed because remote apply is
anti-scope. Skipping local cluster creation is not allowed because local is the
INIT-101 done state.
---
## 3. Slice decomposition
INIT-101 uses INIT-specific slice numbering: `SLICE-101.01` through
`SLICE-101.06`. This keeps the corrected Phase 5 work visibly separate from
the archived INIT-008 `SLICE-030` series and the Phase 5 reset's INIT-100
work.
### SLICE-101.01 - Discard VKE substrate and introduce k3s channel contract
**Scope:** Remove or rewrite the wrong-shaped INIT-008 substrate in this
branch and introduce the k3s-shaped channel schema plus `local` and `dev`
channel declarations. This slice implements D8 and D12 first so later slices
cannot accidentally build on VKE names or VKE-generated payloads.
**Files touched:**
- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/channels/local.yaml`
- `infra/channels/dev.yaml`
- `infra/channels/fixtures/*.yaml`
- `infra/scripts/resolve_platform_channel.py`
- `infra/scripts/validate_platform_channels.py`
- `infra/modules/platform-cluster/` deleted
- `infra/environments/` deleted
- `infra/README.md`
- `.gitignore`
**Local-verification acceptance commands:**
```bash
python infra/scripts/validate_platform_channels.py
python infra/scripts/resolve_platform_channel.py infra/channels/local.yaml > /tmp/local-channel.json
python infra/scripts/resolve_platform_channel.py infra/channels/dev.yaml > /tmp/dev-channel.json
rg -n "vultr_kubernetes|kubernetes_version|node_pools|ha_controlplanes|enable_firewall" infra && exit 1 || true
```
**Acceptance criteria:** no active schema accepts VKE
`cluster.kubernetes_version`, `node_pools`, `ha_controlplanes`, or VKE-only
fields; `local` resolves to `distribution: k3s`, `target: k3d-local`, and
`k3s_version: v1.32.13+k3s1`; `dev` resolves to `distribution: k3s`,
`target: vultr-vms`, and the single-server remote defaults.
**Dependencies:** INIT-100.
**Magnitude:** M.
**Anti-scope:** no OpenTofu module implementation, no k3d cluster creation, no
remote VM resources, no VKE compatibility adapter, no archived copy of
INIT-008 inside this branch.
### SLICE-101.02 - k3d local cluster module, scripts, and reachability harness
**Scope:** Add the local k3d creation surface using D1-D4 and D10. This slice
owns pinned k3d version checking, local cluster create/delete wrappers,
channel-scoped kubeconfig generation, and the first reachability check against
the local API server.
**Files touched:**
- `infra/modules/platform-cluster-k3d/main.tf`
- `infra/modules/platform-cluster-k3d/variables.tf`
- `infra/modules/platform-cluster-k3d/outputs.tf`
- `infra/modules/platform-cluster-k3d/versions.tf`
- `infra/scripts/install-cluster-tools.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `infra/scripts/delete-local-channel.sh`
- `infra/tests/validate_platform_bootstrap.sh`
- `infra/README.md`
- `.gitignore`
**Local-verification acceptance commands:**
```bash
bash infra/scripts/install-cluster-tools.sh --check
bash infra/scripts/bring-up-local-channel.sh
bash infra/scripts/bring-up-local-channel.sh
k3d version
k3d cluster list humility-local
test -f infra/channels/local/.generated/kubeconfig.yaml
KUBECONFIG=infra/channels/local/.generated/kubeconfig.yaml kubectl get nodes
bash infra/scripts/delete-local-channel.sh
bash infra/scripts/delete-local-channel.sh
```
**Acceptance criteria:** k3d is exactly `v5.8.3`; cluster name is
`humility-local`; the cluster uses one server and one agent; kubeconfig is
written under `infra/channels/local/.generated/`; double bring-up and double
tear-down are idempotent; no command relies on the operator's global current
kubectl context.
**Dependencies:** SLICE-101.01.
**Magnitude:** L.
**Anti-scope:** no Flux bootstrap, no app workloads, no hidden single-node
downgrade, no kind/minikube fallback, no remote apply.
### SLICE-101.03 - Vultr VM module and cloud-init k3s bootstrap plan surface
**Scope:** Replace the VKE module with a Vultr VM/cloud-init remote
control-cluster plan surface. This slice owns the `vultr_instance` resources,
single-server defaults, VPC/firewall inputs, cloud-init template, pinned k3s
installer environment, and known remote kubeconfig path.
**Files touched:**
- `infra/modules/platform-cluster-vms/main.tf`
- `infra/modules/platform-cluster-vms/variables.tf`
- `infra/modules/platform-cluster-vms/outputs.tf`
- `infra/modules/platform-cluster-vms/versions.tf`
- `infra/modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl`
- `infra/modules/platform-network/main.tf`
- `infra/modules/platform-network/versions.tf`
- `infra/templates/platform-channel/*.tf`
- `infra/roots/channels/dev/*`
- `infra/tests/validate_platform_bootstrap.sh`
**Local-verification acceptance commands:**
```bash
tofu -chdir=infra/modules/platform-cluster-vms fmt -check
tofu -chdir=infra/roots/channels/dev init -backend=false
git diff --exit-code -- infra/roots/channels/dev/.terraform.lock.hcl
tofu -chdir=infra/roots/channels/dev validate
rg -n "vultr_kubernetes" infra && exit 1 || true
```
When credentials and required variables are present:
```bash
tofu -chdir=infra/roots/channels/dev plan -out=/tmp/init-101-dev.tfplan
rm -f /tmp/init-101-dev.tfplan
```
**Acceptance criteria:** `vultr_instance` replaces `vultr_kubernetes`; server
default plan is `vc2-2c-4gb`; remote server count default is one; cloud-init
sets `INSTALL_K3S_VERSION=v1.32.13+k3s1`; `tofu validate` passes; `tofu plan`
is possible with credentials; no slice command applies remote resources.
**Dependencies:** SLICE-101.01.
**Magnitude:** L.
**Anti-scope:** no remote `tofu apply`, no embedded-etcd HA, no Vultr load
balancer, no k3sup, no Vultr Marketplace k3s image, no DNS or TLS resources.
### SLICE-101.04 - Channel template and generated root rewrite
**Scope:** Rebuild the platform-channel template, generated roots, backend
generation, tfvars generation, and drift checks around the k3s-shaped channel
schema. This is where the salvaged INIT-008 resolver/generator structure is
adapted to the new target-specific payload.
**Files touched:**
- `infra/templates/platform-channel/main.tf`
- `infra/templates/platform-channel/variables.tf`
- `infra/templates/platform-channel/outputs.tf`
- `infra/templates/platform-channel/versions.tf`
- `infra/roots/channels/local/main.tf`
- `infra/roots/channels/local/backend.tfbackend`
- `infra/roots/channels/local/channel.auto.tfvars.json`
- `infra/roots/channels/local/.terraform.lock.hcl`
- `infra/roots/channels/dev/main.tf`
- `infra/roots/channels/dev/backend.tfbackend`
- `infra/roots/channels/dev/channel.auto.tfvars.json`
- `infra/roots/channels/dev/.terraform.lock.hcl`
- `infra/scripts/generate_channel_backend.py`
- `infra/scripts/generate_channel_tfvars.py`
- `infra/scripts/spawn_platform_channel.py`
- `infra/tests/validate_platform_bootstrap.sh`
**Local-verification acceptance commands:**
```bash
python infra/scripts/generate_channel_backend.py infra/channels/local.yaml --out infra/roots/channels/local/backend.tfbackend
python infra/scripts/generate_channel_tfvars.py infra/channels/local.yaml --out infra/roots/channels/local/channel.auto.tfvars.json
python infra/scripts/generate_channel_backend.py infra/channels/dev.yaml --out infra/roots/channels/dev/backend.tfbackend
python infra/scripts/generate_channel_tfvars.py infra/channels/dev.yaml --out infra/roots/channels/dev/channel.auto.tfvars.json
git diff --exit-code -- infra/roots/channels/local infra/roots/channels/dev
tofu -chdir=infra/roots/channels/local init -backend=false
git diff --exit-code -- infra/roots/channels/local/.terraform.lock.hcl
tofu -chdir=infra/roots/channels/local validate
tofu -chdir=infra/roots/channels/dev init -backend=false
git diff --exit-code -- infra/roots/channels/dev/.terraform.lock.hcl
tofu -chdir=infra/roots/channels/dev validate
```
**Acceptance criteria:** generated tfvars contain only k3s/k3d or k3s/Vultr
fields; the INIT-008 Object Storage state-backend root remains unchanged
except for formatting if required; root provider lockfiles are committed and
drift-free after `tofu init -backend=false`; inheritance fixtures exercise the
new field shape; hard `infra/environments/{dev,staging,production}` roots are
not revived.
**Dependencies:** SLICE-101.01, SLICE-101.03.
**Magnitude:** L.
**Anti-scope:** no new channel onboarding beyond `local` and `dev`, no
multi-channel root, no compatibility generation for old tfvars, no semantic
state-backend redesign.
### SLICE-101.05 - Local k3d bootstrap end-to-end verification
**Scope:** Turn the local bring-up surface into the INIT-101 done-state proof.
This slice creates a real local k3d cluster, verifies `kubectl get nodes`
against the channel kubeconfig, checks the expected node shape, and makes stale
generated state handling explicit.
**Files touched:**
- `infra/scripts/bring-up-local-channel.sh`
- `infra/scripts/delete-local-channel.sh`
- `infra/tests/validate_platform_bootstrap.sh`
- `infra/tests/README.md` if added
- `infra/README.md`
- `.gitignore`
**Local-verification acceptance commands:**
```bash
bash infra/scripts/delete-local-channel.sh || true
bash infra/scripts/bring-up-local-channel.sh
bash infra/scripts/bring-up-local-channel.sh
KUBECONFIG=infra/channels/local/.generated/kubeconfig.yaml kubectl get nodes -o wide
KUBECONFIG=infra/channels/local/.generated/kubeconfig.yaml kubectl get nodes --no-headers | wc -l
bash infra/tests/validate_platform_bootstrap.sh
```
Cleanup after verification:
```bash
bash infra/scripts/delete-local-channel.sh
bash infra/scripts/delete-local-channel.sh
```
**Acceptance criteria:** the cluster is real; `kubectl get nodes` succeeds
against `infra/channels/local/.generated/kubeconfig.yaml`; at least one node
exists and the default two-node server/agent shape is verified where k3d
reports roles; stale generated state is not silently reused; double bring-up
and double tear-down prove no-op idempotency; harness failure messages
distinguish missing credentials for remote plan from forbidden local cluster
failures.
**Dependencies:** SLICE-101.02, SLICE-101.04.
**Magnitude:** M.
**Anti-scope:** no remote VM creation, no Flux install, no workload smoke test,
no skipping cluster creation because Docker/k3d is unavailable.
### SLICE-101.06 - Documentation and INIT-102 handoff
**Scope:** Document the corrected substrate, operator local bring-up, remote
plan-only boundary, stale material displacement, and INIT-102 handoff. This
slice makes the decisions visible to future proposal, hookpoint, and
implementation agents.
**Files touched:**
- `infra/README.md`
- `docs/` deployment substrate document if the repo already has the right
  location
- `.pipeline/implementation.md` if the implementation stage records slice
  status there
- `DECISIONS.md` only if a mechanical cross-reference to D8 is required; no
  new decision is expected
**Local-verification acceptance commands:**
```bash
rg -n "D8|k3d|k3s|humility-local|INIT-102|INIT-118|VKE" infra README.md docs .pipeline 2>/dev/null || true
rg -n "vultr_kubernetes|kind|local-only verification|kubernetes_version|node_pools" infra docs .pipeline && exit 1 || true
bash infra/tests/validate_platform_bootstrap.sh
```
**Acceptance criteria:** docs name D8 as controlling authority; docs state VKE
artifacts are retired and preserved only on reference branches; docs identify
the local kubeconfig path consumed by INIT-102; docs state remote HA is
deferred to INIT-118; docs do not imply remote apply, Flux, Crossplane,
Infisical, DNS, TLS, or workloads are part of INIT-101.
**Dependencies:** SLICE-101.05.
**Magnitude:** S.
**Anti-scope:** no tutorial-only substitute for executable scripts, no remote
operations runbook that claims INIT-101 has deployed remote k3s, no new
architecture decision beyond documenting D8 and D1-D12.
---
## 4. Tradeoffs accepted
1. **Single remote server for INIT-101.** D5 accepts a single remote k3s server
   plan surface instead of embedded-etcd HA. This keeps INIT-101 focused on the
   substrate contract and local done state. HA is explicitly deferred to
   INIT-118: Remote Control Cluster HA.
2. **Local must be real, remote stays plan-ready.** D8 requires every Phase 5
   initiative to deploy a real local component. INIT-101 therefore creates
   k3d locally, but does not run a real Vultr apply. The proposal accepts the
   asymmetry because local is the first deployment target and remote channel
   onboarding is post-INIT-117 work.
3. **Schema version remains `1` while the field shape is replaced.** The VKE
   shape never becomes the accepted main-path contract after D8, so preserving
   `schema_version: 1` with a clean k3s replacement is less misleading than
   supporting v1 and v2 side by side. No old reader remains.
4. **Keep Vultr provider constraint `~> 2.30`.** D7 avoids provider churn even
   though newer releases exist. INIT-101 changes substrate shape, not provider
   version policy.
5. **Use cloud-init plus the official k3s installer, not k3sup.** D9 chooses
   the bootstrap path already named by D8. k3sup remains out of scope even
   though it can fetch kubeconfig and join nodes.
6. **Generated kubeconfigs are files, not global context mutation.** D10
   accepts channel-scoped kubeconfig files because k3d can mutate global
   kubeconfig by default. This makes the harness deterministic and keeps later
   INITs from depending on the operator's current context.
7. **Delete instead of archive in-tree.** D12 and the no-backwards-compatibility
   convention reject an `archived/` directory. The old artifacts remain
   inspectable on the reference branch.
8. **One channel template dispatches targets.** Keeping
   `infra/templates/platform-channel/` means local and remote use the same
   channel-generation contract. The target-specific modules differ, but the
   environment model does not fork.
9. **No remote bootstrap token finalization.** INIT-101 exposes the remote
   token as a plan input/reference shape but does not create a runtime secret
   flow. Infisical and remote apply are not in this initiative.
10. **No local exception components.** k3d is accepted because it runs k3s in
    Docker. kind and VKE simulation are rejected because they violate the
    same-distribution requirement.
---
## 5. Hookpoints preview
Full hookpoint research happens after the risk gate. The expected blast radius
is visible enough for risk assessment:
### Delete
- `infra/modules/platform-cluster/` - VKE module based on
  `vultr_kubernetes`.
- `infra/environments/dev/` - hard environment root.
- `infra/environments/staging/` - hard environment root.
- `infra/environments/production/` - hard environment root.
- VKE-shaped generated tfvars in any active root.
- Any docs describing INIT-008's VKE substrate as the accepted Phase 5 path.
### Rewrite
- `infra/schemas/platform-channel.schema.json` - replace VKE cluster fields
  with k3s/k3d/Vultr-VM fields.
- `infra/schemas/platform-channel-resolved.schema.json` - resolved shape for
  generated roots.
- `infra/channels/dev.yaml` - remote VKE dev channel becomes remote Vultr VM
  k3s plan channel.
- `infra/templates/platform-channel/main.tf` - replace VKE module call with
  target-specific k3d or Vultr-VM module calls.
- `infra/templates/platform-channel/variables.tf` - replace VKE variables.
- `infra/templates/platform-channel/outputs.tf` - output channel-scoped
  cluster/kubeconfig facts.
- `infra/scripts/generate_channel_tfvars.py` - emit k3s-shaped variables.
- `infra/tests/validate_platform_bootstrap.sh` - add real local cluster proof
  and VKE grep invariants.
- `infra/README.md` - document D8-substrate contract and handoff.
### Salvage with narrow changes
- `infra/bootstrap/state-backend/` - reuse unchanged per D11 except formatting
  or lock-file refresh required by toolchain.
- `infra/modules/platform-network/` - keep Vultr VPC concept; adjust variables
  only if the VM module requires stricter inputs.
- `infra/scripts/resolve_platform_channel.py` - keep inheritance, fixture
  lookup, deep merge, circular-parent guard, and structured errors.
- `infra/scripts/spawn_platform_channel.py` - keep ephemeral child concept;
  update field names.
- `infra/scripts/generate_channel_backend.py` - keep state backend generation;
  update local-vs-S3 backend handling if needed.
- Harness structure for toolchain, formatting, validation, drift, security,
  and resolver checks.
### New files
- `infra/channels/local.yaml`
- `infra/roots/channels/local/*`
- `infra/modules/platform-cluster-k3d/*`
- `infra/modules/platform-cluster-vms/*`
- `infra/modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl`
- `infra/scripts/install-cluster-tools.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `infra/scripts/delete-local-channel.sh`
---
## 6. Acceptance criteria for INIT-101
- [ ] A real local k3d cluster named `humility-local` is created.
- [ ] The local cluster uses pinned k3d `v5.8.3`.
- [ ] The local cluster uses pinned k3s `v1.32.13+k3s1`.
- [ ] `infra/scripts/install-cluster-tools.sh --check` verifies pinned cluster
  tools, including k3d `v5.8.3`.
- [ ] OpenTofu CLI verification uses version `1.11.5` while root/module
  `required_version` floors may remain `>= 1.8.0`.
- [ ] The local default topology is one k3d server and one k3d agent.
- [ ] Local bring-up is idempotent when an existing cluster matches the channel
  contract, and local tear-down is idempotent when the cluster is absent.
- [ ] A channel-scoped kubeconfig is written at
  `infra/channels/local/.generated/kubeconfig.yaml`.
- [ ] `KUBECONFIG=infra/channels/local/.generated/kubeconfig.yaml kubectl get nodes`
  returns at least one node.
- [ ] The harness verifies the local `kubectl get nodes` command.
- [ ] `tofu validate` is clean for `infra/bootstrap/state-backend`.
- [ ] `tofu validate` is clean for `infra/roots/channels/local`.
- [ ] `tofu validate` is clean for `infra/roots/channels/dev`.
- [ ] `tofu plan` against `infra/roots/channels/dev` produces a clean plan
  when Vultr credentials and required remote inputs are present.
- [ ] Missing Vultr credentials skip only the remote plan assertion, never the
  local k3d proof.
- [ ] Old VKE-shaped artifacts are deleted: no active
  `infra/modules/platform-cluster/` VKE module remains.
- [ ] No active channel file contains VKE-shaped fields such as
  `cluster.kubernetes_version`, `node_pools`, `ha_controlplanes`, or VKE
  managed-cluster `enable_firewall`.
- [ ] `infra/templates/platform-channel/main.tf` calls the k3d module for
  `k3d-local` and the VM module for `vultr-vms`.
- [ ] Cloud-init uses `INSTALL_K3S_VERSION=v1.32.13+k3s1`.
- [ ] Cloud-init renders byte-identical `user_data` for byte-identical channel
  inputs and guards k3s installation to at most once per VM.
- [ ] The remote module uses `vultr_instance`, not `vultr_kubernetes`.
- [ ] Generated tfvars are drift-free and k3s-shaped.
- [ ] `.terraform.lock.hcl` is committed and drift-free for every root, and no
  module carries a provider lockfile.
- [ ] Generated kubeconfigs and `.generated/` artifacts are ignored by git.
- [ ] Documentation identifies INIT-102 as the next consumer of the local
  control-cluster kubeconfig and channel contract.
Canonical validation command:
```bash
bash infra/tests/validate_platform_bootstrap.sh
```
The harness is allowed to call narrower commands internally, but this command
is the single operator-facing verification entry point for INIT-101.
---
## 7. Anti-scope
INIT-101 explicitly does not do the following:
- No Flux install. INIT-102 owns GitOps and Flux reconciliation.
- No Crossplane install. INIT-106 owns application-cluster provisioning.
- No app workloads. INIT-113 owns workload deployment.
- No HA topology beyond a single remote server in this initiative.
- No remote embedded-etcd cluster.
- No Vultr load balancer or fixed remote registration endpoint.
- No real Vultr `tofu apply`.
- No remote k3s actually deployed.
- No remote kubeconfig fetched.
- No DNS automation.
- No cert-manager.
- No Infisical.
- No public ingress.
- No SOPS runtime secret expansion.
- No Buildkite worker.
- No app-cluster claim or composition.
- No VKE module.
- No VKE root.
- No VKE channel schema.
- No kind-only harness.
- No dry-run-only completion.
- No archived copy of INIT-008 inside this branch.
Named successors:
- INIT-102: Flux/GitOps substrate on the local k3d control cluster.
- INIT-103: Infisical runtime secret store.
- INIT-106: Crossplane app-cluster provisioning.
- INIT-113: application workloads.
- INIT-118: Remote Control Cluster HA, including multi-server topology and any
  fixed registration endpoint.
- Post-INIT-117 remote deployment work: first real remote k3s apply and remote
  kubeconfig retrieval.
These are not deferred stubs. They are explicit scope boundaries for scheduled
successor initiatives.
---
## 8. Stale material disposal
INIT-008's VKE-shaped artifacts are deleted from this branch. The reference
copy lives on `feat/init-008-platform-bootstrap` and in the
`worktrees/init-008-platform-bootstrap/` checkout. No in-tree archive is
created.
Disposed material:
- `infra/modules/platform-cluster/` if it provisions `vultr_kubernetes`.
- VKE channel schema fields:
  `cluster.kubernetes_version`, `node_pools`, `ha_controlplanes`, and
  `enable_firewall` as managed-cluster fields.
- VKE-oriented platform-channel template inputs.
- VKE-shaped generated tfvars.
- Hard `infra/environments/{dev,staging,production}` roots.
- Dev-channel framing as a remote VKE control cluster.
- Render-only or local-verification-only harness completion criteria.
- Documentation that names INIT-008 as the accepted control-cluster substrate.
Salvaged material:
- Channel-template directory idea.
- Channel inheritance/resolution concept.
- Generated backend/tfvars drift-check concept.
- Vultr Object Storage state-backend bootstrap module.
- Vultr VPC/network concept.
- Resolver structured errors and fixture testing pattern.
- Harness structure for toolchain checks, validation, generated-artifact drift,
  security assertions, and channel resolver behavior.
The disposal rule is strict: no backwards-compatible VKE reader, no VKE field
aliases, no forwarding module, no "legacy channel" examples, and no note that
old channels still work. The corrected main path is k3s/k3d/Vultr-VM only.
---
## 9. Revision history
- Round 1 A-1 closed by the `platform-cluster-k3d` variable contract in
  Section 2.5, lines 248-261.
- Round 1 A-2 closed by the `platform-cluster-vms` variable contract in
  Section 2.6, lines 284-299.
- Round 1 A-3 closed by cloud-init idempotency invariants and harness proof in
  Sections 2.7 and 2.12, lines 325-332 and 478-479.
- Round 1 A-4 closed by bring-up/tear-down idempotency contracts and double-run
  harness assertions in Sections 2.11, 2.12, and 3, lines 427-445, 470-477,
  and 657-675.
- Round 1 A-5 closed by the OpenTofu `1.11.5` verified CLI pin in Section 2.10,
  lines 385-391.
- Round 1 A-6 closed by provider lockfile policy and root drift checks in
  Sections 2.12, 3, and 6, lines 462-466, 610-636, and 834-835.
- Round 1 A-7 closed by the named `install-cluster-tools.sh` installer
  commitment in Sections 2.10, 3, 5, and 6, lines 403-411, 531-554, 795-796,
  and 803-804.
