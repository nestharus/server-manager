# Platform Bootstrap — Code Agent Retrospective Review

**Files reviewed:**
- `infra/bootstrap/state-backend/main.tf`
- `infra/modules/platform-network/main.tf`
- `infra/modules/platform-cluster/main.tf`
- `infra/environments/dev/main.tf`
- `infra/environments/dev/backend.tfbackend`

**Reference documents:**
- `plans/proposals/platform-bootstrap.md`
- `plans/research/platform-bootstrap-hookpoints.md`
- `plans/risk/platform-bootstrap-audit.md`
- `plans/risk/platform-bootstrap-scope.md`
- `plans/risk/platform-bootstrap-shortcut.md`

**Date:** 2026-04-14

---

## 1. Proposal alignment

Each requirement from the proposal's section 2 (Scope) and section 4
(Deliverables) is checked against the implementation.

### Vultr VKE as platform-cluster substrate

**ALIGNED.** `infra/modules/platform-cluster/main.tf` provisions a
`vultr_kubernetes` resource. The dev environment root at
`infra/environments/dev/main.tf` consumes it with VKE-specific
parameters (`kubernetes_version = "v1.32.3+1"`). No other cluster
substrate appears.

### Two-tier model preserved (platform cluster only, no app clusters)

**ALIGNED.** The module is named `platform-cluster` and provisions
exactly one VKE cluster per environment. No application cluster
resources, no Crossplane definitions, no fleet-management primitives
exist in any of the five files. The dev root creates one network and
one cluster.

### Base network layout with Vultr VPC

**ALIGNED.** `infra/modules/platform-network/main.tf` provisions a
`vultr_vpc` resource with parameterized subnet, mask, region, and
environment name. The dev root passes `v4_subnet = "10.40.0.0"` with
mask `/20`. The module header documents the per-environment allocation
plan (dev: `10.40.0.0/20`, staging: `10.40.16.0/20`, production:
`10.40.32.0/20`). The cluster module accepts `vpc_id` as input and
attaches the VKE cluster to the VPC.

### Provider-native object-storage state backing

**ALIGNED.** `infra/bootstrap/state-backend/main.tf` provisions a
`vultr_object_storage` subscription and a `vultr_object_storage_bucket`
with `enable_versioning = true`. No self-hosted S3 layer (SeaweedFS,
MinIO, Ceph) appears anywhere in the implementation. State is external
to the cluster being created.

### Per-environment OpenTofu roots

**ALIGNED.** `infra/environments/dev/main.tf` is a self-contained root
with its own `terraform` block, provider declaration, and `backend "s3" {}`
configuration. It composes shared modules via relative source paths. The
companion `backend.tfbackend` provides environment-specific state
parameters (`key = "infra/dev/terraform.tfstate"`). The pattern is
designed for repetition: a new environment root with different variables
would create an isolated environment.

### Reproducible bootstrap path

**PARTIALLY ALIGNED.** The two-stage bootstrap path is structurally
sound:

1. `infra/bootstrap/state-backend/` creates the object storage and
   bucket using local state.
2. `infra/environments/dev/` consumes the bucket via S3 backend.

The bootstrap root's header documents the usage pattern (`tofu init`,
`tofu apply` with `-var` flags). The `REPLACE_AFTER_BOOTSTRAP`
placeholder in `backend.tfbackend` makes the ordering dependency
explicit.

However, the propagation from bootstrap outputs to `backend.tfbackend`
is manual — the operator must capture `s3_hostname` from the bootstrap
apply and hand-edit the placeholder. No automation script or documented
step-by-step procedure bridges the two stages. See finding W-1.

### Handoff seam to GitOps

**PARTIALLY ALIGNED.** The cluster module exposes four outputs:
`cluster_id`, `endpoint`, `kube_config` (sensitive), and
`firewall_group_id`. These provide the technical connection point for a
later Flux bootstrap.

The dev root re-exports `vpc_id`, `cluster_id`, and `endpoint` but
does not re-export `kube_config`. Since the kubeconfig is the primary
artifact that the GitOps Foundation initiative needs to bootstrap Flux
against the cluster, its absence from the environment root's output
interface is a gap. See finding W-2.

The proposal also specifies the handoff contract should define
"kubeconfig or connection-secret storage path, who may retrieve it,
whether the credential is encrypted at rest, and whether a short-lived
or long-lived credential model is used." These are documentation
deliverables rather than code artifacts, so their absence from the
`.tf` files is expected at this stage.

---

## 2. Hookpoint compliance

### Hookpoint 1 — State backend locked to Vultr Object Storage

**COMPLIANT.** Bootstrap uses only `vultr_object_storage` and
`vultr_object_storage_bucket`. Object versioning is enabled. No
self-hosted S3 dependency exists in the bootstrap path.

### Hookpoint 2 — Module composition pattern for environment roots

**COMPLIANT.** Both modules (`platform-network`, `platform-cluster`)
are environment-agnostic — all environment-specific values are passed
as variables. No hardcoded environment names, regions, or subnets
appear in the modules. The dev root composes both modules with
environment-specific parameters. Future environments can follow the
same pattern by creating a new root with different variable values.

### Hookpoint 3 — Flux CD GitOps layer (future consumer)

**COMPLIANT.** The cluster module exposes `endpoint` and `kube_config`
(sensitive) as specified. The output interface matches the forward
contract described in the hookpoint research. Renaming or removing
these outputs would break the GitOps handoff seam.

### Hookpoint 4 — State bootstrapping ordering

**COMPLIANT.** The bootstrap root uses local state only (no `backend`
block). The dev environment root uses `backend "s3" {}` with an
external config file. The `REPLACE_AFTER_BOOTSTRAP` placeholder in
`backend.tfbackend` makes the ordering explicit — running the
environment root before bootstrap will fail on backend initialization.
The documented sequence (bootstrap first, capture `s3_hostname`,
populate `backend.tfbackend`, then init the environment root) is
enforced by construction.

### Hookpoint 5 — Two-tier cluster model preserved

**COMPLIANT.** The `platform-cluster` module provisions only the
platform/control cluster via `vultr_kubernetes`. No application cluster
resources exist. The module naming (`platform-cluster`, not `cluster`)
reinforces the boundary. The dev root labels the cluster
`humility-dev-platform`, making the control-plane purpose explicit.

### Hookpoint 6 — Provider version pinning

**COMPLIANT.** Both roots that declare providers pin consistently:

- `infra/bootstrap/state-backend/main.tf`: `vultr ~> 2.30`,
  `required_version >= 1.8.0`
- `infra/environments/dev/main.tf`: `vultr ~> 2.30`,
  `required_version >= 1.8.0`

The modules do not declare their own `required_providers` blocks. This
is acceptable — modules inherit provider configuration from the calling
root. However, see finding N-1 regarding best practice for reusable
modules.

---

## 3. Findings

### W-1. No automated or documented bootstrap-to-environment bridge — WARNING

**Location:** `infra/bootstrap/state-backend/main.tf` (outputs),
`infra/environments/dev/backend.tfbackend` (placeholder).

The bootstrap root outputs `s3_hostname`, `s3_access_key`, and
`s3_secret_key`. The dev environment's `backend.tfbackend` contains
`REPLACE_AFTER_BOOTSTRAP` as the S3 endpoint placeholder. The operator
must manually capture the bootstrap outputs and edit the backend config
file before initializing the environment root.

The proposal's exit criteria require "a first reproducible bootstrap
path that can create a fresh platform environment from a clean starting
point without hidden manual infrastructure steps." A manual copy-paste
between stages is not hidden, but it is undocumented in the
implementation and error-prone. An operator who misses this step or
pastes the wrong value will get an opaque backend initialization
failure.

**Recommendation:** Add a documented step-by-step bootstrap runbook or
a minimal shell script that captures bootstrap outputs and populates
`backend.tfbackend`. This does not need to be sophisticated — even a
`sed` one-liner in a comment or a `Makefile` target would close the
gap.

### W-2. Dev root does not re-export `kube_config` — WARNING

**Location:** `infra/environments/dev/main.tf` lines 40-50.

The dev root exports `vpc_id`, `cluster_id`, and `endpoint` from the
composed modules. It does not export `kube_config` from the cluster
module. The hookpoint research (Hookpoint 3) identifies `endpoint` and
`kube_config` as the forward contract for GitOps Foundation.

A downstream consumer (e.g., the GitOps Foundation initiative running
`tofu output` against the dev root) cannot retrieve the kubeconfig
without modifying this root to add the output. Since each environment
root is the external interface for its environment, the kubeconfig
should be part of that interface.

**Recommendation:** Add a `kube_config` output (marked `sensitive =
true`) to the dev environment root that passes through
`module.cluster.kube_config`.

### W-3. `ha_controlplanes = true` for dev environment — WARNING

**Location:** `infra/environments/dev/main.tf` line 36.

The dev root enables HA control planes. The proposal describes the
cluster shape as "minimal and control-oriented" with "worker pools
sized for platform services rather than application workloads." HA
control planes add provider cost in a non-production environment whose
stated purpose is "application dev, E2E tests, LLM video QA, fast
iteration."

This is a deliberate sizing choice and may be intentional for
reliability during development. However, it is worth confirming that
the cost is justified for dev, given the proposal's emphasis on minimal
bootstrap.

**Recommendation:** Confirm this is intentional. If dev does not need
HA control planes, set `ha_controlplanes = false` to reduce cost. The
variable defaults to `true` in the module, so production environments
would still get HA by default.

### N-1. Modules do not declare `required_providers` — NOTE

**Location:** `infra/modules/platform-network/main.tf`,
`infra/modules/platform-cluster/main.tf`.

Neither module declares a `required_providers` block. They inherit
provider configuration from the calling root, which works correctly.
However, HashiCorp/OpenTofu best practice for reusable modules is to
declare provider requirements so that consumers see explicit
dependency information and version constraints without inspecting the
module internals.

This does not cause any functional issue. The provider version is
pinned consistently across both roots (Hookpoint 6 compliance). This
is a code-quality observation only.

### N-2. Bootstrap root local state has no documented backup path — NOTE

**Location:** `infra/bootstrap/state-backend/main.tf` lines 1-2.

The bootstrap root uses local state only and its header says "Run once,
then never touch again." If the local `.tfstate` file is lost, the
Vultr Object Storage subscription and bucket become unmanaged
resources. The file cannot be trivially regenerated — `tofu import`
would be required to re-associate the existing resources.

The risk audit (F-3) notes that bucket destroy/recreate on update is
a concern, and the exit criteria require an exercised state-restore
procedure — but that criterion applies to the environment-level state,
not the bootstrap state.

This is a low-probability concern because the bootstrap root should
rarely, if ever, be re-applied. The local state file should be checked
into the repository or stored in a known location.

### N-3. `backend.tfbackend` includes access_key/secret_key by omission — NOTE

**Location:** `infra/environments/dev/backend.tfbackend`.

The backend config does not include `access_key` or `secret_key`
fields. OpenTofu's S3 backend will look for these in environment
variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or shared
credentials files. This is the correct approach — credentials should
not be in files committed to git.

The bootstrap root outputs `s3_access_key` and `s3_secret_key` (both
sensitive). The operator must know to export these as environment
variables before running `tofu init` on the environment root. This is
standard practice but part of the undocumented bridge noted in W-1.

### N-4. No state-locking configuration — NOTE

**Location:** `infra/environments/dev/backend.tfbackend`.

The backend config does not include any locking configuration
(`dynamodb_table` or equivalent). The risk audit (F-1) already
identifies this as an implementation-time design decision: Vultr does
not offer a DynamoDB-equivalent service, so the standard S3 backend
locking mechanism is unavailable.

The proposal's exit criteria require "working lock acquisition
demonstrated by an intentional concurrent-plan test." This is an
unresolved implementation item, not a code defect — the current files
correctly omit what does not yet exist. The locking mechanism must be
resolved before the initiative can close.

---

## 4. Verdict

**APPROVED WITH CONDITIONS**

The implementation is structurally sound. All five files align with the
proposal's architectural direction and comply with all six hookpoints.
The module composition pattern is clean, the provider versions are
consistent, the two-tier model is preserved, and the bootstrap ordering
is enforced by construction.

Two conditions should be addressed before merge:

1. **W-1 (bootstrap bridge):** Document or automate the step that
   propagates bootstrap outputs into `backend.tfbackend`. The
   reproducibility exit criterion requires this.

2. **W-2 (`kube_config` output):** Add the `kube_config` sensitive
   output to the dev environment root to complete the GitOps handoff
   contract.

W-3 (HA control planes for dev) should be confirmed as intentional but
is not blocking.

The four NOTE findings are observations that do not affect correctness
or proposal compliance. N-4 (state locking) is an acknowledged open
item from the risk audit that must be resolved during the initiative
but is not a code defect in the current implementation.
