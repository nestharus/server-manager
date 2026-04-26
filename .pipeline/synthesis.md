# INIT-101 Phase 2 Synthesis: Self-Managed k3s Control Cluster

This synthesis bridges the INIT-101 research artifact into binding
initiative decisions. It does not design the final implementation. It fixes
the constraints the proposal must obey, identifies the stale material to
displace, and decomposes the corrected work into implementation-sized slices.

## 1. Initiative framing (INIT-101 ticket sketch)

### Strategic Context

**Subsystem:** Deployment substrate; control-cluster bootstrap.

**Phase:** Phase 5 reset successor; replacement for archived INIT-008.

**Executive priority:** Critical path for INIT-102 through INIT-117. No later
Phase 5 initiative can install Flux, Infisical, Crossplane, TLS/DNS,
workloads, or app-cluster provisioning until the control-cluster substrate is
real and environment-agnostic.

**Controlling reset:** DECISIONS.md D8 supersedes the VKE/local-verification
shape. Phase 5 is now local-as-first-deployment and self-managed k3s
everywhere. Local runs the same Kubernetes distribution through k3d; remote
channels run k3s on Vultr Cloud Compute VMs. OpenTofu provisions Vultr cloud
primitives and remote VMs; cloud-init bootstraps k3s. VKE, kind, fixed
environment roots, and render-only completion are no longer accepted.

Evidence:
- D8 resets Phase 5 around environment-agnostic local-as-first-deployment and
  self-managed k3s everywhere: `DECISIONS.md:175-203`; research
  `research.md:13-21`.
- D8 supersedes VKE, kind, hard dev/staging/production roots, and VKE
  Crossplane compositions: `DECISIONS.md:207-249`; research
  `research.md:16-21`.
- The environment-agnostic memory says local is a deployment target, not
  verification, and that local uses k3s in k3d while remote uses k3s on Vultr
  Cloud Compute VMs: `environment-agnostic-stack.md:7-18`; research
  `research.md:22-35`.
- INIT-101's replan scope is k3d locally, Vultr VMs plus cloud-init remotely,
  with a real local k3d control cluster as the done state:
  `phase-5-replan/.pipeline/replan.md:607-625`.

### Justification Chain

**Market signal:** Not a market-facing initiative. The value is preserving the
operator's ability to exercise the same control-plane contract locally before
remote channel onboarding.

**Problem axis:** Phase 5 deployment substrate parity. INIT-008 encoded a
VKE-shaped cluster contract, schema, template, and module:
`research.md:96-132`. That violates D8 because VKE has no same-distribution
local form, and D8 forbids VKE modules, VKE schemas, kind-only harnesses, and
dry-run-only completion: `DECISIONS.md:251-259`; research `research.md:19-21`.

**Proposal mechanism:** Replace the VKE substrate with a k3s-shaped channel
contract, local k3d bring-up, Vultr VM plus cloud-init remote contract, reused
state backend, reused channel-template shape, and an end-to-end local harness
that proves `kubectl get nodes` against a real local k3d control cluster.

**Executive priority:** High foundation risk. INIT-101 depends on INIT-100, and
INIT-102 GitOps plus every later Phase 5 runtime component depends on this
corrected control-cluster contract. Continuing from INIT-008's VKE artifacts
would propagate stale assumptions into Flux, Crossplane, app-cluster
provisioning, and documentation.

**Engineering assessment:** XL effort; no prototype. The governing substrate
choice is already made by D8. Risk is medium-high if the proposal blurs local
done state with remote plan-only scope. Risk factors are stale VKE artifacts,
version pin drift, kubeconfig handling, remote bootstrap token handling,
cloud-init idempotency, and false confidence from `tofu validate` without a
real local cluster.

### Scope

**Value slices:** SLICE-031 through SLICE-036.

**Dependencies:** INIT-100.

**Delivers:** Operators can create and verify a real local k3d control cluster
using the same k3s distribution family selected for remote channels; the repo
contains a k3s-shaped channel schema and channel template; remote Vultr
VM/cloud-init control-cluster resources are represented as an OpenTofu plan
surface without applying cloud changes; stale VKE artifacts are deleted from
this branch.

**In scope:**
- k3s/k3d version pinning for INIT-101.
- k3s-shaped channel schema fields and generated inputs.
- Local k3d module/script surface.
- Real local k3d cluster creation as the INIT-101 done state.
- Vultr VM module and cloud-init template sufficient for `tofu plan`.
- Reuse of Vultr Object Storage state-backend bootstrap from INIT-008.
- Deletion of VKE-shaped INIT-008 artifacts in this branch.
- Documentation and handoff to INIT-102.

**Out of scope:**
- VKE resources, VKE schemas, VKE roots, and VKE docs.
- Remote `tofu apply`.
- Remote HA implementation.
- Flux installation.
- Crossplane installation or app-cluster claims.
- Runtime secrets and Infisical.
- Public DNS, TLS, ingress, and workloads.
- Any compatibility shim for the archived INIT-008 shape.

### Acceptance Criteria

- [ ] The branch contains no active VKE module, VKE channel schema, VKE root, or
  VKE-oriented control-cluster documentation.
- [ ] Channel schema and generated tfvars are k3s-shaped and reject VKE-shaped
  fields rather than accepting them through aliases.
- [ ] The local channel creates a real k3d cluster using the pinned k3d release
  and pinned k3s release family.
- [ ] A channel-scoped kubeconfig is produced without relying on the global
  current kubectl context as the contract.
- [ ] The harness verifies a real `kubectl get nodes` against the local k3d
  cluster.
- [ ] Remote Vultr VM/cloud-init resources can pass local validation and, where
  credentials are present, `tofu plan`; no remote apply is executed by
  INIT-101.
- [ ] INIT-008's Object Storage state-backend bootstrap is reused unchanged or
  copied without semantic change.
- [ ] Documentation identifies INIT-102 as the next consumer of the local
  control-cluster kubeconfig and channel contract.

## 2. Binding decisions

These D1..D12 decisions are INIT-101-internal. They are not new project-level
entries in `DECISIONS.md`.

### D1 - Pin k3s to `v1.32.13+k3s1`

INIT-101 pins k3s to `v1.32.13+k3s1`.

Rationale:
- The research prompt asked for the latest 1.32.x k3s pin rather than a jump
  to the current latest minor.
- K3s supports exact install pins through `INSTALL_K3S_VERSION=vX.Y.Z+k3s1`:
  `research.md:318-320`.
- K3s release tags use the `vX.Y.Z+k3sN` shape:
  `research.md:460-472`.
- Upstream GitHub release metadata checked on 2026-04-26 reports
  `v1.32.13+k3s1` as the newest stable `v1.32.*` release:
  https://github.com/k3s-io/k3s/releases/tag/v1.32.13%2Bk3s1.

Consequence:
- Local k3d and remote cloud-init both use this k3s version.
- Moving to a later Kubernetes minor is a later initiative, not an INIT-101
  hidden upgrade.

### D2 - Pin k3d to `v5.8.3`

INIT-101 pins k3d to `v5.8.3`.

Rationale:
- k3d supports pinned install through `TAG`: `research.md:213-229`.
- GitHub release metadata observed by research reports `v5.8.3` as the latest
  k3d release: `research.md:221-229`.
- Local toolchain research shows k3d is not currently installed, so INIT-101
  must own a deterministic install/verification path: `research.md:559-560`.

Consequence:
- Scripts and documentation must not install floating k3d `main` or "latest".

### D3 - Use `humility-<channel_id>` for local k3d cluster names

Local k3d clusters use the convention `humility-<channel_id>`, for example
`humility-local`.

Rationale:
- The channel id is the environment identity and replaces hard-coded
  environment names: `channel-template-pattern.md:24-40`; research
  `research.md:262-267`.
- The name should be project-scoped so an operator can distinguish Humility
  clusters from unrelated local k3d clusters.

Consequence:
- Channel id remains the parameterization boundary.
- The k3d cluster name is derived, not separately invented per channel.

### D4 - Use one local k3d server and one local k3d agent

The local channel default topology is one k3d server and one k3d agent.

Rationale:
- k3d supports explicit `--servers` and `--agents` counts:
  `research.md:233-252`.
- D8 requires a real local deployment target, not render-only verification:
  `research.md:254-258`.
- A single server keeps local startup fast; one agent gives the harness an
  actual worker node without turning local into HA simulation.

Consequence:
- Local HA is not part of INIT-101.
- The local harness verifies a real two-node k3d cluster shape unless the
  implementation environment cannot support the agent, in which case the
  proposal must stop rather than silently downgrade.

### D5 - Use a single remote k3s server for INIT-101

Remote channels model a single k3s server initially. Embedded-etcd HA, fixed
registration endpoints, and multi-server operations are deferred to successor
INIT-118: Remote Control Cluster HA.

Rationale:
- The replan accepts INIT-101's remote contract as Vultr VMs plus cloud-init and
  does not require remote HA in this initiative:
  `phase-5-replan/.pipeline/replan.md:607-625`.
- K3s documents single-node servers as fully functional clusters:
  `research.md:298-308`.
- K3s embedded-etcd HA requires three or more server nodes and additional
  networking/registration decisions: `research.md:329-351`.
- The research explicitly flags HA topology and fixed registration endpoint as
  proposal blockers, not user-value questions: `research.md:568-576`.

Consequence:
- INIT-101 may define remote HA follow-up interfaces only enough to avoid
  blocking later work; it must not implement HA under INIT-101.
- Remote plan output represents the single-server default.

### D6 - Use `vc2-2c-4gb` as the remote server plan default

The remote control-plane server composition default is `vc2-2c-4gb`. Remote
agent defaults are `count: 0`; if agents are enabled later, their default plan
is `vc2-1c-2gb` unless the HA follow-up changes that.

Rationale:
- K3s small HA-server sizing lists 2 vCPU and 4 GB RAM as the small server
  minimum: `research.md:341-346`, `research.md:399-404`.
- Vultr EWR-capable plan research observed `vc2-2c-4gb` with 2 vCPU, 4096 MB
  RAM, and 80 GB disk: `research.md:390-398`.
- INIT-008 already used `vc2-2c-4gb` for its VKE node pool, so the cost/size
  baseline is familiar: `research.md:405-407`.

Consequence:
- This is a composition default only.
- INIT-101 must not apply remote resources, so no Vultr spend is created by
  this decision.

### D7 - Keep Vultr provider constraint `~> 2.30`

INIT-101 keeps the Vultr Terraform/OpenTofu provider constraint at `~> 2.30`.

Rationale:
- D8 says Vultr and OpenTofu survive while VKE does not:
  `DECISIONS.md:211-213`.
- The research records the existing project memory/provider constraint as
  `vultr/vultr ~> 2.30` with OpenTofu `>= 1.8.0`:
  `research.md:379-386`.
- Upstream latest provider `v2.31.0` is still compatible with `~> 2.30` under
  Terraform/OpenTofu pessimistic version semantics.

Consequence:
- INIT-101 does not create a provider-version churn slice.
- The proposal may refresh lock files if normal `tofu init` requires it, but
  the constraint remains `~> 2.30`.

### D8 - Replace the channel schema with k3s-shaped fields

The active channel schema remains `schema_version: 1`, but its contents become
k3s-shaped because the VKE schema is reference-only and must not be preserved
as a supported version.

Required schema additions/replacements:
- `cluster.distribution: k3s`
- `cluster.target: k3d-local | vultr-vms`
- `cluster.k3s_version: vX.Y.Z+k3sN`
- `cluster.kubeconfig_path`
- For `k3d-local`: `k3d.cluster_name`, `k3d.servers`, `k3d.agents`,
  `k3d.registry_name`, `k3d.api_port`, `k3d.port_mappings`, and `k3d.volumes`.
- For `vultr-vms`: `vultr.region`, `vultr.network`, `vultr.firewall`,
  `vultr.servers.count`, `vultr.servers.plan`, `vultr.agents.count`,
  `vultr.agents.plan`, `vultr.ssh_key_ids`, and `vultr.bootstrap`.

Rationale:
- Current INIT-008 schema and dev channel encode VKE version and node-pool
  shape: `research.md:454-459`.
- D8 requires k3s everywhere: `research.md:463-467`.
- Research identifies the minimum k3s-shaped top-level cluster fields:
  `research.md:468-472`.
- k3d and Vultr target-specific field pressure is documented in
  `research.md:473-493`.
- No-backwards-compatibility and D8 forbid dual readers for the stale VKE
  shape: `research.md:500-504`.

Consequence:
- The implementation deletes VKE field support instead of adding aliases.
- Fixture channels must prove inheritance against the new fields.

### D9 - Bootstrap remote k3s with cloud-init plus the official k3s installer

Remote bootstrap uses Vultr `user_data` cloud-init that writes k3s config and
runs the official installer with `INSTALL_K3S_VERSION=v1.32.13+k3s1`.

Rationale:
- D8 explicitly assigns remote VM k3s bootstrap to cloud-init:
  `DECISIONS.md:191-192`.
- Vultr `vultr_instance` supports `user_data`, VPCs, firewalls, SSH keys, tags,
  labels, plans, and regions: `research.md:353-364`.
- Vultr documents Terraform plus cloud-init for Cloud Compute initialization:
  `research.md:365-370`.
- K3s documents `curl -sfL https://get.k3s.io | sh -`, install config files,
  env vars, and exact version pinning: `research.md:298-320`.
- k3sup is useful but would add a second bootstrap tool when D8 already names
  cloud-init: `research.md:410-423`.

Consequence:
- k3sup is not part of the INIT-101 bootstrap path.
- The remote bootstrap contract is visible in OpenTofu/cloud-init artifacts and
  remains plan-only during INIT-101.

### D10 - Retrieve kubeconfig through channel-scoped files

Local kubeconfig retrieval uses `k3d kubeconfig get humility-<channel_id>` into
a channel-scoped generated path. Remote kubeconfig retrieval uses operator SSH
copy from a known root-only path written by cloud-init.

Binding paths:
- Local: `infra/channels/<id>/.generated/kubeconfig.yaml`.
- Remote: `/root/humility-k3s.yaml` on the server VM, copied by the operator
  when remote apply is introduced after INIT-101.

Rationale:
- k3d mutates default kubeconfig by default but can emit a kubeconfig with
  `k3d kubeconfig get`: `research.md:269-281`.
- K3s writes kubeconfig to `/etc/rancher/k3s/k3s.yaml`:
  `research.md:298-305`, `research.md:410-413`.
- Remote retrieval has multiple possible paths; this decision chooses direct
  SSH copy instead of adding k3sup or relying on Vultr Marketplace behavior:
  `research.md:414-423`.

Consequence:
- Generated kubeconfigs must be ignored by git.
- The harness uses the channel-scoped kubeconfig path, not the operator's
  current global kubectl context.

### D11 - Reuse the Vultr Object Storage state-backend module unchanged

INIT-101 reuses INIT-008's `infra/bootstrap/state-backend/` module unchanged
unless formatting-only drift is required by the current toolchain.

Rationale:
- D8 preserves Vultr Object Storage for remote state:
  `DECISIONS.md:191-192`.
- Research classifies the state-backend bootstrap concept as salvageable:
  `research.md:166-170`.
- The archived root provisions a `vultr_object_storage` subscription and marks
  access/secret outputs sensitive: `research.md:137-140`.
- Reuse is explicitly listed in the salvage section: `research.md:513-516`.

Consequence:
- INIT-101 does not redesign remote state.
- Any changes to this module must be justified as mechanical, not semantic.

### D12 - Delete VKE-shaped INIT-008 artifacts in this branch

The implementation slice deletes active VKE-shaped artifacts from this branch.
The archive remains the `feat/init-008-platform-bootstrap` branch and the
`../init-008-platform-bootstrap` worktree reference.

Artifacts to delete or rewrite:
- Delete `infra/modules/platform-cluster/` if it provisions `vultr_kubernetes`.
- Rewrite `infra/templates/platform-channel/`.
- Rewrite channel schemas and channel YAML.
- Rewrite tfvars generation payloads.
- Rewrite harness assertions that expected VKE or render-only completion.

Rationale:
- D8 preserves wrong-shaped INIT-008 work as reference branches only:
  `DECISIONS.md:204-205`, `DECISIONS.md:251-259`.
- Research classifies the VKE module as discard and the template/schema/dev
  YAML as rewrite: `research.md:184-196`, `research.md:521-538`.
- The replan says VKE module, VKE roots, VKE channel schema, and VKE docs should
  not merge into the corrected main path:
  `phase-5-replan/.pipeline/replan.md:186-211`.

Consequence:
- No compatibility shim, alias, forwarding module, or deprecated field survives
  for VKE.
- Reference copies remain available from the archived branch.

## 3. Slice decomposition

The archived INIT-008 proposal ended at SLICE-030. INIT-101 continues the
counter at SLICE-031.

### SLICE-031 - Discard VKE substrate and introduce k3s channel contract

Remove or rewrite the wrong-shaped INIT-008 substrate in this branch and
introduce the k3s-shaped channel schema plus local channel declaration.

Acceptance: no active schema accepts VKE `cluster.kubernetes_version`,
`node_pools`, `ha_controlplanes`, or VKE-only fields; the local channel
resolves to `distribution: k3s`, `target: k3d-local`, and
`k3s_version: v1.32.13+k3s1`; reference-only INIT-008 copies are not imported
as compatibility paths.

Dependencies: INIT-100.

### SLICE-032 - k3d local cluster module, bring-up script, and reachability harness

Add the local k3d creation surface using D1-D4 and D10: pinned k3d install
check, cluster create/delete/list wrapper, channel-scoped kubeconfig generation,
and initial API reachability harness.

Acceptance: k3d is `v5.8.3`; the local cluster name is `humility-local`; the
cluster uses one server and one agent; the harness does not depend on the
global current kubectl context.

Dependencies: SLICE-031.

### SLICE-033 - Vultr VM module and cloud-init k3s bootstrap plan surface

Replace the VKE module with a Vultr VM/cloud-init remote control-cluster plan
surface. Own the Vultr instance module, firewall/VPC inputs, cloud-init template
using `INSTALL_K3S_VERSION=v1.32.13+k3s1`, and remote kubeconfig known path.

Acceptance: `vultr_instance` replaces `vultr_kubernetes`; server default plan
is `vc2-2c-4gb`; remote server count default is one; `tofu validate` passes and
`tofu plan` is supported where credentials are present; no slice command
applies remote resources.

Dependencies: SLICE-031.

### SLICE-034 - Channel template and generated root rewrite

Rebuild `infra/templates/platform-channel/`, the generated local root, backend
generation, tfvars generation, and drift checks around the k3s-shaped schema.

Acceptance: generated tfvars contain only k3s/k3d or k3s/Vultr fields;
INIT-008 Object Storage state-backend remains unchanged; inheritance fixtures
exercise the new field shape; hard `infra/environments/{dev,staging,production}`
roots are not revived.

Dependencies: SLICE-031, SLICE-033.

### SLICE-035 - Local k3d bootstrap end-to-end verification

Turn the local bring-up surface into INIT-101's done-state proof: create a real
local k3d cluster, verify `kubectl get nodes` against the channel kubeconfig,
and make repeated runs explicit about teardown or stale generated state.

Acceptance: the cluster is real; `kubectl get nodes` succeeds against
`infra/channels/local/.generated/kubeconfig.yaml`; expected server/agent node
count is verified; stale generated state is not silently reused.

Dependencies: SLICE-032, SLICE-034.

### SLICE-036 - Documentation and INIT-102 handoff

Document the corrected substrate, operator local bring-up, remote plan-only
boundary, stale material displacement, and INIT-102 handoff.

Acceptance: docs name D8 as controlling authority, state that VKE artifacts are
retired and preserved only on the archived branch, identify the local kubeconfig
path consumed by INIT-102, and state that remote HA is deferred to INIT-118.

Dependencies: SLICE-035.

## 4. Open questions for user

No product-value questions surfaced. All technical and process decisions made
internally.

MUST_ANSWER: 0.

## 5. Stale material to displace

INIT-008's VKE-shaped artifacts are formally retired by D8. Slice 1 of
INIT-101 deletes or rewrites them in this branch. Reference copies remain on
the `feat/init-008-platform-bootstrap` branch and in the archived
`../init-008-platform-bootstrap` worktree.

Material displaced:
- VKE `platform-cluster` module based on `vultr_kubernetes`.
- VKE channel schema fields: `cluster.kubernetes_version`, `node_pools`,
  `ha_controlplanes`, and `enable_firewall` as managed-cluster fields.
- VKE-oriented platform-channel template inputs.
- VKE-shaped generated tfvars.
- Dev-channel framing as a remote VKE control cluster.
- Render-only or local-verification-only harness completion criteria.
- Documentation that names INIT-008 as the accepted control-cluster substrate.

Material salvaged:
- Channel-template directory idea.
- Channel inheritance/resolution concept.
- Generated backend/tfvars drift-check concept.
- Vultr Object Storage state-backend bootstrap module.
- Vultr VPC/network concept, rewritten only where needed for VM topology.
- Harness structure for toolchain checks, validation, generated-artifact drift,
  security assertions, and channel resolver behavior.

The displacement rule is strict: no backwards-compatible VKE reader, no VKE
field aliases, no forwarding module, and no note that old channels still work.
The corrected main path is k3s/k3d/Vultr-VM only.
