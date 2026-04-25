# INIT-008 Phase 3 Proposal: Platform Bootstrap - OpenTofu/Vultr Substrate
## Binding sources
- `.pipeline/research.md` - Phase 1 evidence over current `infra/` state.
- `.pipeline/synthesis.md` - D1-D12, stale-material disposition, and six candidate slices.
- Phase 5 local-only deployment-substrate framing, quoted inline in Sections 2.1 and 7.
- `product-strategy/tickets/INIT-001.md` - initiative/ticket shape.
- Channel-template memory reference `channel-template-pattern.md` - schema shape,
  root development channel, production-class channel, operator/stage channel,
  and child-channel inheritance patterns.
This proposal is bound to synthesis decisions D1-D12. The user decisions
from 2026-04-25 replace the old hard environment triad with a channel
registry plus parameterized platform template. The old
`infra/environments/{dev,staging,production}/` shape is not preserved as a
compatibility surface.
---
## 1. Executive summary
INIT-008 turns the existing OpenTofu/Vultr bootstrap footprint into a
proposal-grade platform substrate contract. The goal is not deployment. The
goal is a locally verified, Vultr-locked infrastructure baseline whose
bootstrap root, channel root, modules, remote-state handoff, documentation,
and validation harness agree about what they create and how later Phase 5
initiatives consume them. This closes D1, D2, D11, and D12 by making
`DECISIONS.md`, the `infra/` layout, and the verification surface point at a
single Vultr/OpenTofu substrate.
The central architecture shift is from hard-coded environments to platform
channels. A channel is not an environment name. A channel is a declared
platform release target with an `id`, optional `parent`, exposure class,
optional tenant, optional ephemeral-child permission, and platform-specific
OpenTofu settings. This mirrors the rfqautomation reference: the schema file
defines `id`, `parent`, `exposure`, `tenant`, `allow_ephemeral_children`, and
per-platform objects; `dev.yaml` and `customer.yaml` show root channels;
`internal.yaml` shows an operator/stage class; `e2e.yaml` shows a child that
inherits from `dev` and overrides only what differs. INIT-008 adopts that
pattern for infrastructure channels instead of keeping `dev`, `staging`, and
`production` as separate handwritten roots. This closes D4, D5, D6, and the
user's state-isolation answer.
The first validated channel is `dev`. INIT-008 ships only the `dev` channel
definition and root. Production-class `customer`, operator-class `internal`,
and named e2e channels are anti-scope for INIT-008 and for the entire Phase 5
deployment-substrate effort because Phase 5 is local-only, the user selected
minimal isolation cost, and there is no near-term Vultr apply. They are owned
by a separate initiative opened after Phase 5 converges, where real Vultr
deployment and real channel onboarding happen. The schema reserves
the same fields needed for those future channels, and the implementation must
prove inheritance and ephemeral materialization against fixtures without
adding active non-dev channels. This closes D5 and D6 while keeping D2 narrow.
Local verification is the binding completion surface. Every slice must support
`tofu init -backend=false && tofu validate`; provider-backed `tofu plan` is
allowed only where credentials are locally available and still never followed
by `tofu apply`. No DNS, public ingress, Flux, Buildkite, SOPS, workloads,
Crossplane, or real cluster bootstrap occurs in INIT-008. This closes D7,
D8, D9, D10, and D11 by making the initiative honest about its local-only
state and by documenting which operational guarantees are intentionally not
claimed yet.
---
## 2. Architecture
### 2.1 Ticket-ready framing
**Subsystem:** Deployment Substrate; Platform Bootstrap.
**Phase:** Phase 5 entry initiative; execution of the unticketed Phase 0
platform foundation.
**Executive priority:** Dependency head for INIT-009 through INIT-016.
Nothing downstream should need to guess how platform channels, OpenTofu state,
or the Vultr substrate are named, validated, or handed off.
**Justification chain:** The Phase 5 index says INIT-008 authors the
OpenTofu/Vultr VPC, VKE, Object Storage, and state-backend substrate and
ends at local authoring plus `tofu plan`, with no apply. Phase 1 research
found the repo already contains a partial substrate, but it also found split
authority, stale provider-fix material, an implicit shared-bucket
state model, missing bucket-existence contract, and inconsistent local
verification. This proposal binds those open seams without widening the
initiative.
### 2.2 Repo layout after INIT-008
The implementation should leave `infra/` in this shape:
```text
infra/
  README.md
  schemas/
    platform-channel.schema.json
    platform-channel-resolved.schema.json
  channels/
    dev.yaml
    fixtures/
      e2e-from-dev.yaml
      e2e-pr-1234.yaml
      dev-pr-123.yaml
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
      dev/
        main.tf
        backend.tfbackend
        channel.auto.tfvars.json
  bootstrap/
    state-backend/
      main.tf
  modules/
    platform-network/
      main.tf
    platform-cluster/
      main.tf
  scripts/
    resolve_platform_channel.py
    spawn_platform_channel.py
    generate_channel_backend.py
    generate_channel_tfvars.py
    validate_platform_channels.py
  tests/
    validate_platform_bootstrap.sh
```
The old environment roots are removed:
```text
infra/environments/dev/
infra/environments/staging/
infra/environments/production/
```
No compatibility aliases, symlinks, forwarding roots, duplicated backend files,
or "legacy environment" wrappers remain. This is required by the no
backwards-compatibility rule and by the channel-pivot instruction.
### 2.3 Channel schema
The schema lives at:
```text
infra/schemas/platform-channel.schema.json
```
It is modeled on the rfqautomation schema at:
```text
channel-template-pattern.md memory reference, schema section
```
Both channel schemas are executable contracts, not presence markers. Every object in both schemas uses `additionalProperties: false` unless explicitly documented open; INIT-008 has no deliberately open objects. Every field defines required-vs-optional status, type, enum values where applicable, regex patterns where applicable, numeric min/max where applicable, and nullable handling through explicit `["string", "null"]` or equivalent JSON Schema syntax.

Top-level source fields:
- `schema_version`: required integer; accepted value exactly `1`.
- `id`: required string; `^[a-z0-9][a-z0-9-]*$`.
- `parent`: required string-or-null; non-null value uses the channel id regex.
- `exposure`: required enum string; `prod`, `stage`, or `dev`.
- `tenant`: required string-or-null; non-null value uses `^[a-z0-9][a-z0-9-]*$`.
- `allow_ephemeral_children`: required boolean.
- `enabled_platforms`: required array; items are enum strings `docker` or
  `kubernetes`; `uniqueItems: true`. INIT-008 only uses `kubernetes`.
- `platform`: optional object on child fixtures and required on root active channels.

`platform` fields:
- `region`: required string, `^[a-z]{3}$`.
- `network.v4_subnet`: required string with IPv4 CIDR base-address pattern.
- `network.v4_subnet_mask`: required integer, min `16`, max `28`.
- `cluster.label`: required string, `^[a-z0-9][a-z0-9-]*$`.
- `cluster.kubernetes_version`: required string, `^v[0-9]+\\.[0-9]+\\.[0-9]+\\+[0-9]+$`.
- `cluster.node_pools`: required array of node-pool objects, exactly one item
  for INIT-008 (`minItems: 1`, `maxItems: 1`). Multi-pool channel support is
  deferred to a future channel template.
- `cluster.node_pools[].name`: required string.
- `cluster.node_pools[].plan`: required string.
- `cluster.node_pools[].count`: required integer, min `1`.
- `cluster.ha_controlplanes`: required boolean.
- `cluster.enable_firewall`: required boolean.
- `state.bucket`: required string, `^[a-z0-9][a-z0-9.-]*$`.
- `state.key`: required string matching active keys
  `channels/<id>/terraform.tfstate` or ephemeral keys
  `channels/<parent>/ephemeral/<suffix>/terraform.tfstate`.
- `state.region`: required string matching the same region pattern.

Schema versioning contract:
- `schema_version: 1` is the only accepted value today.
- `resolve_platform_channel.py`, `spawn_platform_channel.py`, and
  `validate_platform_channels.py` must reject unknown schema versions with an
  explicit structured error; unknown versions are never silently ignored.
- When a future schema bump happens, it follows
  `~/ai/conventions/no-backwards-compatibility.md`: bump the version, update
  all channel files in the same change, delete v1 support, and do not add
  transitional aliases or dual readers.
The resolved schema lives at:
```text
infra/schemas/platform-channel-resolved.schema.json
```
That schema is stricter than the source schema: after inheritance resolution, all required platform fields must be concrete and `parent` must be `null` or preserved only as metadata. It uses the same type, enum, pattern, numeric-bound, nullable, and `additionalProperties: false` contract as the source schema, but does not require a concrete S3 endpoint at resolve time. OpenTofu consumes the resolved contract, not raw inherited YAML.
### 2.4 Initial channel definition
INIT-008 ships one active channel:
```text
infra/channels/dev.yaml
```
Representative shape:
```yaml
schema_version: 1
id: dev
parent: null
exposure: dev
tenant: null
allow_ephemeral_children: true
enabled_platforms: [kubernetes]
platform:
  region: ewr
  network:
    v4_subnet: 10.40.0.0
    v4_subnet_mask: 20
cluster:
  label: humility-dev-platform
  kubernetes_version: v1.32.9+3
  node_pools:
    - name: default
      count: 2
      plan: vc2-2c-4gb
  ha_controlplanes: true
  enable_firewall: true
state:
  bucket: humility-tfstate
  key: channels/dev/terraform.tfstate
  region: ewr
```
This preserves the checked-in `dev` baseline from the old environment root:
region `ewr`, subnet `10.40.0.0/20`, Kubernetes version `v1.32.9+3`, node plan
`vc2-2c-4gb`, node quantity `2` through the single node-pool entry, HA control planes enabled, and managed
firewall enabled. That closes D5 and D6.
Production-class `customer`, operator-class `internal`, and named e2e channels
are not active INIT-008 channels and are not Phase 5 deliverables. They are
cited as references because the rfqautomation `customer.yaml`,
`internal.yaml`, and `e2e.yaml` demonstrate the future classes this repo will
need, but checked-in active non-dev channels would imply validation, remote
state ownership, and live channel onboarding that Phase 5 has not commissioned
yet. The post-Phase-5 deployment initiative owns those real channels.
### 2.5 Fixture channel definitions
The implementation may include fixtures under:
```text
infra/channels/fixtures/
```
These are validation fixtures only. They are not OpenTofu roots and do not
receive backend keys that operators use.
Expected fixtures:
- `e2e-from-dev.yaml`: parent `dev`, narrow override such as `cluster.label: humility-e2e-from-dev-platform`; proves inherited `platform.region: ewr` plus child override.
- `e2e-pr-1234.yaml`: parent `e2e-from-dev`, narrow override such as
  `tenant: pr-1234`; proves depth-2 parent-chain resolution through both
  `e2e-from-dev` and `dev`.
- `dev-pr-123.yaml`: generated example of an ephemeral child id, used to test spawn and key generation.
- `ephemeral-disabled.yaml`: root-like fixture with `allow_ephemeral_children: false`; proves spawn permission rejection.
- `missing-parent.yaml`: child fixture whose parent id does not exist; proves non-zero missing-parent resolver exit.
- `circular-a.yaml` and `circular-b.yaml`: paired fixtures that point at each other; prove non-zero circular-parent resolver exit.
Fixtures must be named and documented as test material so they cannot be
mistaken for live channels.
### 2.6 Template module surface
The parameterized OpenTofu template lives at:
```text
infra/templates/platform-channel/
```
It calls existing shared modules:
```text
infra/modules/platform-network/
infra/modules/platform-cluster/
```
Variables exposed by the template:
- `channel_id`: string.
- `channel_exposure`: string.
- `tenant`: nullable string.
- `region`: string.
- `network`: object with `v4_subnet` and `v4_subnet_mask`.
- `cluster`: object with `label`, `kubernetes_version`, `node_plan`,
  `node_quantity`, `ha_controlplanes`, and `enable_firewall`.
Outputs exposed by the template:
- `channel_id`.
- `channel_exposure`.
- `vpc_id`.
- `cluster_id`.
- `endpoint`.
- `kube_config` as sensitive.
- `firewall_group_id`.
The template does not declare a provider block or backend block. Provider and
backend belong to per-channel roots. This keeps the template reusable and
keeps local validation predictable.
### 2.7 Per-channel TF root versus unified registry
Chosen direction: per-channel OpenTofu roots.
The active root is:
```text
infra/roots/channels/dev/
```
The root contains:
- `main.tf`: required version/provider constraints, `backend "s3" {}`,
  `provider "vultr" {}`, and a module call to
  `../../../templates/platform-channel`.
- `backend.tfbackend`: generated S3 backend settings for the resolved channel
  state key.
- `channel.auto.tfvars.json`: generated resolved channel values
  for the module.
`backend.tfbackend` is generated from resolved channel JSON by:
```text
infra/scripts/generate_channel_backend.py
```
`channel.auto.tfvars.json` is generated from resolved channel JSON by:
```text
infra/scripts/generate_channel_tfvars.py
```
For INIT-008, that generator flattens the single resolved
`cluster.node_pools[0]` entry into the template's `node_plan` and
`node_quantity` variables. The source schema keeps the array-shaped channel
contract, but the schema caps it at one pool until a future channel template
supports multiple pools.
Generated root artifacts are not hand-edited. Every generated artifact in
`infra/roots/channels/<id>/` must have regeneration drift-detection
acceptance. For INIT-008 that list is:
- `backend.tfbackend`.
- `channel.auto.tfvars.json`.

Acceptance regenerates each artifact from the committed channel through the
resolved JSON, writes the result to a temp file, and compares it against the
committed root artifact. Non-JSON artifacts compare byte-for-byte. JSON
artifacts may compare byte-for-byte or by canonical-JSON-ordered structural
equivalence. Drift means the source channel and active OpenTofu input
disagree.
Rationale:
- Local operation stays simple: one root, one `tofu init`, one `tofu validate`,
  and one optional `tofu plan` for `dev`.
- Risk review can reason about the blast radius of the only active channel.
- The local-only Phase 5 contract does not need a multi-channel graph plan.
- Adding `customer` or `internal` later is a channel-onboarding change, not a
  hidden expansion of INIT-008.
Rejected direction: unified registry root that iterates every channel.
That pattern is flexible, but it makes a single `tofu plan` span all channels
and makes future production-class channel definitions active by default. That
is the wrong operational shape for local-only bootstrap verification.
### 2.8 Inheritance resolution mechanism
Chosen direction: pre-process time resolution.
The script:
```text
infra/scripts/resolve_platform_channel.py
```
loads a channel YAML file, follows `parent` references within
`infra/channels/`, performs deterministic deep-merge override semantics, and
emits a resolved JSON document that matches:
```text
infra/schemas/platform-channel-resolved.schema.json
```
Override rules:
- Scalars replace parent values.
- Objects merge recursively.
- Arrays replace parent arrays in full.
- `id`, `parent`, `tenant`, `exposure`, and `allow_ephemeral_children` follow
  explicit child values if present.
- A child may not change its effective state bucket unless the schema allows
  that class in a later initiative.
- Circular parent references fail validation.
- Missing parent references fail validation.
- Unsupported `schema_version` values fail validation.
Errors from channel scripts are structured, machine-readable messages with at
least `code`, `channel`, and `message` fields, written before non-zero exit.
Rationale:
- OpenTofu sees concrete values and does not need to implement YAML merge
  semantics in HCL.
- Validation errors happen before provider initialization.
- The pattern stays close to the rfqautomation channel files, where `e2e.yaml`
  is a compact child of `dev.yaml`.
### 2.9 Ephemeral-children spawn mechanism
Ephemeral children are reserved by schema and tested locally, but no live
ephemeral channel is applied in INIT-008.
The script:
```text
infra/scripts/spawn_platform_channel.py
```
accepts:
```bash
python infra/scripts/spawn_platform_channel.py \
  --parent dev \
  --suffix pr-123 \
  --out .tmp/platform-channels/dev-pr-123
```
Expected behavior:
- Loads `infra/channels/dev.yaml`.
- Requires `allow_ephemeral_children: true` on the parent.
- Emits a transient child YAML with id `dev-pr-123`.
- Emits resolved tfvars for that child.
- Emits a transient backend config using key
  `channels/dev/ephemeral/pr-123/terraform.tfstate`.
- Does not write into `infra/channels/` or `infra/roots/`.
- Does not run `tofu apply`.
The script exists to prove the schema's `allow_ephemeral_children` field is
materializable in local fixtures. It is not a usable PR-preview surface: it has
no Buildkite integration, no apply path, no automatic cleanup, and no live
channel registration.
This closes the channel-pattern requirement without turning INIT-008 into PR
preview infrastructure. Buildkite and PR-preview execution remain outside
INIT-008.
### 2.10 Remote-state contract
Chosen state model: one object-storage bucket with per-channel keys.
Bucket:
```text
humility-tfstate
```
Active channel key:
```text
channels/dev/terraform.tfstate
```
Ephemeral key pattern:
```text
channels/<parent>/ephemeral/<suffix>/terraform.tfstate
```
Bootstrap root:
```text
infra/bootstrap/state-backend/
```
The bootstrap root remains local-state only. It owns the Vultr Object Storage
subscription contract and emits operator handoff outputs:
- `bucket_name`.
- `s3_hostname`.
- `s3_access_key`.
- `s3_secret_key`.
Bucket existence is guaranteed by an explicit operator handoff, not by an
implicit assumption. INIT-008 documents the handoff this way:
1. Bootstrap plans the Object Storage subscription and may create it only if
   an operator explicitly runs an apply outside INIT-008 acceptance.
2. Operator creates or verifies bucket `humility-tfstate` in that subscription
   before backend initialization, with provider-side object-storage versioning
   enabled at bucket creation time.
3. Operator injects endpoint and credentials locally when running backend
   init or provider-backed plan.
4. No backend credentials are committed.
The S3 endpoint is an operator handoff value documented in `infra/README.md`
and passed through backend init flags or the operator's local environment. It
is not a channel schema field because the channel contract should carry only
values with resolver or OpenTofu-input semantics.
This is an accepted tradeoff. It closes D3 by making bucket existence an
explicit operator custody step rather than an accidental backend assumption.
The proposal does not add `vultr_object_storage_bucket` because live repo state
and research displaced the older provider-fix path, and because INIT-008 is
local-only.
### 2.11 Channel retirement and state cleanup lifecycle
Removing `infra/channels/<id>.yaml` retires a channel id. A retired id is no longer resolvable by `resolve_platform_channel.py`, spawn parents cannot refer to it, and validation treats any active root that still depends on a retired id as an error. State files are not auto-deleted when a channel is retired; remote state lifecycle is operator-explicit:
- The channel's state object remains in Object Storage until an operator runs
  an explicit `cleanup-state` command or manual equivalent.
- INIT-008 does not implement `cleanup-state`; the command shape is reserved
  for the post-Phase-5 deployment initiative.
- The corresponding `infra/roots/channels/<id>/` directory may remain or be
  removed. The harness handles both states by validating roots only for active
  channels and by rejecting a root that points at a missing non-retired channel.
- `infra/README.md` documents retirement, retained state, and the
  post-Phase-5 cleanup handoff in SLICE-025 or SLICE-029.

This keeps deletion irreversible only when an operator explicitly chooses it. There is no hidden garbage collection or automatic state destruction in INIT-008.
### 2.12 Locking and restore posture
Chosen posture: INIT-008 does not claim multi-operator remote-state locking.
INIT-008 claims:
- Per-channel state key separation.
- No committed backend credentials.
- Local validation with backend disabled.
- Optional provider-backed plan with operator-supplied backend material.
- A documented single-operator rule for any manual backend experiment.
- Provider-side object-storage versioning is enabled at bucket creation time,
  and operators can manually pull a prior state object version if needed.
INIT-008 does not claim:
- Lock acquisition correctness.
- Multi-operator concurrent plan/apply safety.
- A tested restore drill against live Vultr Object Storage.
- SOPS/age custody of backend credentials.
- Automated restore tooling.
INIT-008 does not include a restore drill. A runbook-level state-restore procedure is the responsibility of the post-Phase-5 deployment initiative. The only restore claim INIT-008 makes is that provider-side object-storage versioning is part of the bucket-creation handoff and that operators can pull a prior state version manually if needed.
This closes D8 by choosing a bounded non-locking posture that matches
local-only Phase 5. The risk gate should validate that this is acceptable
given no `tofu apply` occurs in INIT-008.
### 2.13 Provider/version posture
Provider constraints remain:
- OpenTofu required version: `>= 1.8.0`.
- Vultr provider constraint: `~> 2.30`.
INIT-008 acceptance verifies with OpenTofu CLI `1.11.5`, the version installed
in the dev environment on 2026-04-25. The
`required_version = ">= 1.8.0"` floor remains in active roots because it
captures the OpenTofu feature baseline, not the exact verifier. Newer OpenTofu
1.x patch releases should also work; drift against the `1.11` verification
line is reportable.
Reproducibility posture changes:
- Each root that runs `tofu init` commits its `.terraform.lock.hcl` if the
  root is active.
- The active `dev` root lockfile is expected to exist after implementation.
- Bootstrap lockfile is expected to exist after implementation.
- Generated or transient ephemeral roots do not commit lockfiles.
- The validation harness checks that active roots do not silently drift.
This closes D12. The exact resolved provider version is not chosen in the
proposal; the lockfile generated during implementation is the reproducibility
record.
### 2.14 Credential custody contract
INIT-008 uses operator manual custody.
Allowed:
- Operator supplies `VULTR_API_KEY` locally.
- Operator supplies S3 backend credentials locally through backend init
  configuration or environment variables.
- Bootstrap outputs are marked sensitive where OpenTofu supports it.
- README/runbook states how to pass credentials without committing them.
Forbidden:
- Committed Vultr API tokens.
- Committed S3 access keys or secret keys.
- `.tfvars` files containing credentials.
- SOPS/age implementation inside INIT-008.
- Discord-visible or cloud-visible mutation during verification.
This closes D7. SOPS/age belongs to INIT-009; Auth stack custody belongs to
INIT-015; deployment execution belongs to the post-Phase-5 deployment
initiative.
### 2.15 DNS and public endpoint posture
INIT-008 owns no DNS.
INIT-008 owns no reserved public endpoint.
The channel template may output the VKE endpoint returned by Vultr because the
current cluster module already exposes it, but that is not an ingress,
hostname, TLS, or public-audience contract. This closes D9 and D10.
---
## 3. Slice decomposition
### SLICE-025 - Authority Alignment and Stale Input Disposal
**Scope:** Formalize the Vultr/OpenTofu authority record for INIT-008, align
active docs to the channel-pivot architecture, and mark stale planning
material as revised, superseded, or historical. This slice closes D1, D2, D9,
D10, and G1/G10 from synthesis. It is documentation and authority cleanup,
not infrastructure implementation.
**Files this slice touches:**
- `DECISIONS.md`
- `infra/README.md`
- `.pipeline/proposal.md`
- `plans/platform-decisions-overlay.md`
- `plans/proposals/platform-bootstrap.md`
- `plans/proposals/vultr-object-storage-fix.md`
- `plans/proposals/phase1-foundation.md`
- `plans/proposals/app-cluster-provisioning.md`
- deleted provider-comparison research file
- `plans/research/vultr-fix-hookpoints.md`
- `plans/research/vultr-object-storage-fix.md`
- `plans/research/opentofu-providers.md`
- `plans/research/platform-bootstrap-hookpoints.md`
**Local-verification acceptance criteria:**
- `rg -n "retired-provider|legacy-self-managed" infra plans/platform-decisions-overlay.md`
  returns no active INIT-008 authority claim.
- `rg -n "INIT-008|Vultr|OpenTofu" DECISIONS.md infra/README.md` shows Vultr
  and OpenTofu as ratified for platform bootstrap.
- `rg -n "infra/environments" infra/README.md plans/proposals/platform-bootstrap.md`
  returns no active instruction to operate the old triad.
- `infra/README.md` declares local prerequisites: OpenTofu CLI `1.11.5` (the
  version INIT-008 acceptance was verified against; newer 1.x patch releases
  should also work, report drift if they do not), Python major version `3.12`
  for channel scripts, and `jq` only if any acceptance command or harness
  assertion uses it.
- `bash infra/tests/validate_platform_bootstrap.sh` still runs; failures are
  allowed only for these named checks until later slices install their
  artifacts: missing channel schemas, missing `infra/channels/dev.yaml`,
  missing `infra/roots/channels/dev`, missing active-root lockfile, and missing
  generated channel-root artifacts. No other failure may be waived.
- OpenTofu validation target: not applicable; this slice changes authority and
  documentation only, not OpenTofu roots.
**Dependencies:** none.
**Magnitude estimate:** S.
**Anti-scope:**
- Does not change OpenTofu resources.
- Does not add channel schema or roots.
- Does not run Vultr provider-backed plans.
- Does not revise INIT-009 through INIT-016 designs beyond boundary references.
### SLICE-026 - Channel Contract and Registry Skeleton
**Scope:** Add the platform-channel schema, the active `dev` channel
definition, validation fixtures, and the channel-validation script. This slice
implements the rfqautomation-style channel registry in repo form while keeping
only `dev` active. It closes D4, D5, D6, and the non-negotiable channel-pivot
instruction.
**Files this slice touches:**
- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/channels/dev.yaml`
- `infra/channels/fixtures/e2e-from-dev.yaml`
- `infra/channels/fixtures/e2e-pr-1234.yaml`
- `infra/channels/fixtures/dev-pr-123.yaml`
- `infra/channels/fixtures/ephemeral-disabled.yaml`
- `infra/channels/fixtures/missing-parent.yaml`
- `infra/channels/fixtures/circular-a.yaml`
- `infra/channels/fixtures/circular-b.yaml`
- `infra/scripts/resolve_platform_channel.py`
- `infra/scripts/spawn_platform_channel.py`
- `infra/scripts/validate_platform_channels.py`
- `infra/README.md`
- `infra/tests/validate_platform_bootstrap.sh`
**Local-verification acceptance criteria:**
- `python infra/scripts/validate_platform_channels.py` exits 0.
- `infra/schemas/platform-channel.schema.json` and
  `infra/schemas/platform-channel-resolved.schema.json` define, for every
  field, required-vs-optional status, type, enum values where applicable,
  regex patterns where applicable, numeric min/max where applicable, and
  `additionalProperties: false` for every object.
- The schema and scripts accept only `schema_version: 1`; an unknown version
  exits non-zero with a structured error containing `code`, `channel`, and
  `message`.
- `python infra/scripts/resolve_platform_channel.py --channel dev --out .tmp/dev.resolved.json`
  emits resolved JSON with no missing platform fields.
- `python infra/scripts/resolve_platform_channel.py --channel e2e-from-dev --out .tmp/e2e-from-dev.resolved.json`
  emits resolved JSON whose inherited values include
  `platform.region == "ewr"` and whose child override includes
  `cluster.label == "humility-e2e-from-dev-platform"`.
- A Python assertion over `.tmp/e2e-from-dev.resolved.json` checks the specific
  merged field equality values above; the acceptance path does not rely on
  manual inspection.
- `python infra/scripts/resolve_platform_channel.py --channel e2e-pr-1234 --out .tmp/e2e-pr-1234.resolved.json`
  emits resolved JSON through a depth-2 parent chain. Assertions check that
  `platform.region == "ewr"` is inherited from `dev`,
  `cluster.label == "humility-e2e-from-dev-platform"` is inherited from
  `e2e-from-dev`, and the child override such as `tenant == "pr-1234"`
  remains effective.
- Resolving `missing-parent.yaml` exits non-zero with a structured
  `missing_parent` error.
- Resolving `circular-a.yaml` exits non-zero with a structured
  `circular_parent` error.
- `python infra/scripts/spawn_platform_channel.py --parent dev --suffix pr-123 --out .tmp/platform-channels/dev-pr-123`
  emits transient files only under `.tmp/platform-channels/dev-pr-123`.
- `python infra/scripts/spawn_platform_channel.py --parent ephemeral-disabled --suffix pr-123 --out .tmp/platform-channels/blocked`
  exits non-zero with a structured `ephemeral_children_disabled` error.
- `test ! -e infra/channels/customer.yaml`.
- `test ! -e infra/channels/internal.yaml`.
- `test ! -e infra/channels/e2e.yaml`.
- OpenTofu validation target: not applicable; this slice adds channel
  contracts and Python validation only, not OpenTofu roots.
**Dependencies:** SLICE-025.
**Magnitude estimate:** M.
**Anti-scope:**
- Does not create production-class or operator-class active channels.
- Does not create PR preview automation.
- Does not implement Buildkite.
- Does not write credentials.
- Does not run OpenTofu apply.
### SLICE-027 - Platform Template and Dev Channel Root
**Scope:** Replace hard-coded environment roots with the parameterized
platform-channel template and a single per-channel `dev` root. The old
`infra/environments/{dev,staging,production}` roots are deleted. This slice
maps the resolved `dev` channel to OpenTofu execution and preserves the
current VPC/VKE baseline through the template. It closes D5, D6, D11, and
D12 for the active channel root.
**Files this slice touches:**
- `infra/templates/platform-channel/main.tf`
- `infra/templates/platform-channel/variables.tf`
- `infra/templates/platform-channel/outputs.tf`
- `infra/templates/platform-channel/versions.tf`
- `infra/roots/channels/dev/main.tf`
- `infra/roots/channels/dev/backend.tfbackend`
- `infra/roots/channels/dev/channel.auto.tfvars.json`
- `infra/roots/channels/dev/.terraform.lock.hcl`
- `infra/scripts/generate_channel_backend.py`
- `infra/scripts/generate_channel_tfvars.py`
- `infra/environments/dev/main.tf` (delete)
- `infra/environments/dev/backend.tfbackend` (delete)
- `infra/environments/staging/main.tf` (delete)
- `infra/environments/staging/backend.tfbackend` (delete)
- `infra/environments/production/main.tf` (delete)
- `infra/environments/production/backend.tfbackend` (delete)
- `infra/tests/validate_platform_bootstrap.sh`
**Local-verification acceptance criteria:**
- `test ! -d infra/environments`.
- `cd infra/roots/channels/dev && tofu fmt -check`.
- `cd infra/roots/channels/dev && tofu init -backend=false`.
- `cd infra/roots/channels/dev && tofu validate`.
- `rg -n "module \"network\"|module \"cluster\"" infra/templates/platform-channel`
  shows the template calls the existing modules.
- `rg -n "backend \"s3\"" infra/templates/platform-channel` returns no match.
- `rg -n "backend \"s3\"" infra/roots/channels/dev/main.tf` returns a match.
- `infra/templates/platform-channel/variables.tf` specifies each variable's
  type and either an explicit default or an explicit "no default; required"
  contract in the variable description.
- `python infra/scripts/resolve_platform_channel.py --channel dev --out .tmp/dev.resolved.json`
  followed by
  `python infra/scripts/generate_channel_backend.py --resolved .tmp/dev.resolved.json --out .tmp/dev.backend.tfbackend`
  produces a file byte-identical to
  `infra/roots/channels/dev/backend.tfbackend`.
- The same resolved `.tmp/dev.resolved.json` followed by
  `python infra/scripts/generate_channel_tfvars.py --resolved .tmp/dev.resolved.json --out .tmp/dev.channel.auto.tfvars.json`
  produces JSON that is byte-identical to, or canonical-JSON structurally
  identical with, `infra/roots/channels/dev/channel.auto.tfvars.json`.
- Every generated artifact committed under `infra/roots/channels/dev/` is
  named in Section 2.7 and covered by a regeneration drift-detection check.
**Dependencies:** SLICE-026.
**Magnitude estimate:** M.
**Anti-scope:**
- Does not add `customer`, `internal`, `staging`, or `production` roots.
- Does not keep compatibility wrappers for old environment paths.
- Does not change VPC/VKE resource semantics beyond channel parameterization.
- Does not claim provider-backed plan success unless credentials are present.
### SLICE-028 - State-Backend and Remote-State Handoff Contract
**Scope:** Make the state backend and channel backend handoff explicit:
single bucket, per-channel keys, local-state bootstrap, sensitive outputs, and
operator-owned bucket verification. This slice revises docs and validation so
the repo no longer implies the bootstrap root creates a bucket resource it
does not declare. It closes D3, D4, D7, and D8.
**Files this slice touches:**
- `infra/bootstrap/state-backend/main.tf`
- `infra/bootstrap/state-backend/.terraform.lock.hcl`
- `infra/roots/channels/dev/backend.tfbackend`
- `infra/README.md`
- `infra/tests/validate_platform_bootstrap.sh`
- `plans/proposals/platform-bootstrap.md`
**Local-verification acceptance criteria:**
- `cd infra/bootstrap/state-backend && tofu fmt -check`.
- `cd infra/bootstrap/state-backend && tofu init -backend=false`.
- `cd infra/bootstrap/state-backend && tofu validate`.
- `rg -n "vultr_object_storage_bucket" infra/bootstrap/state-backend infra/tests`
  shows no active expectation that INIT-008 manages bucket lifecycle in
  OpenTofu.
- `rg -n "channels/dev/terraform.tfstate" infra/roots/channels/dev/backend.tfbackend`
  returns a match.
- `rg -n "access_key|secret_key" infra/roots/channels/dev/backend.tfbackend`
  returns no committed credential values.
- `rg -n "locking|restore|single-operator|object-storage versioning|post-Phase-5 deployment initiative" infra/README.md plans/proposals/platform-bootstrap.md`
  shows the bounded locking and restore posture is documented, including that
  INIT-008 has no restore drill and that the post-Phase-5 deployment initiative
  owns the runbook-level restore procedure.
- `rg -n "endpoint placeholder|REPLACE_AFTER_BOOTSTRAP" infra/channels infra/schemas infra/roots`
  returns no match.
- `infra/README.md` documents that the S3 endpoint is supplied through
  backend init flags or the operator's local environment after bootstrap.
- The channel schema has no field whose only purpose is to carry endpoint
  prose; endpoint handling is documentation-only and the resolved schema does
  not require a concrete endpoint at resolve time.
- `infra/README.md` documents channel retirement: removing
  `infra/channels/<id>.yaml` retires the channel, state files are retained
  until an explicit operator cleanup, and cleanup-state tooling is post-Phase-5
  deployment scope.
**Dependencies:** SLICE-025, SLICE-027.
**Magnitude estimate:** M.
**Anti-scope:**
- Does not implement remote-state locking.
- Does not test live restore from Vultr Object Storage.
- Does not implement automated restore tooling.
- Does not implement `cleanup-state` state-deletion tooling.
- Does not commit backend credentials.
- Does not introduce SOPS/age.
- Does not add a Terraform bucket resource as a compatibility fix.
### SLICE-029 - Provider Locking and Local Verification Harness
**Scope:** Update the validation harness so it checks the new channel layout,
all active OpenTofu roots, channel schema validation, lockfile posture, and
the absence of committed secrets. This slice makes local verification the
observable done surface for INIT-008. It closes D11 and D12.
**Files this slice touches:**
- `infra/tests/validate_platform_bootstrap.sh`
- `infra/scripts/validate_platform_channels.py`
- `infra/bootstrap/state-backend/.terraform.lock.hcl`
- `infra/roots/channels/dev/.terraform.lock.hcl`
- `infra/README.md`
**Local-verification acceptance criteria:**
- `bash infra/tests/validate_platform_bootstrap.sh` exits 0.
- The harness validates:
  - `infra/bootstrap/state-backend`.
  - `infra/roots/channels/dev`.
  - channel schema files.
  - `infra/channels/dev.yaml`.
  - fixture resolution for inheritance, missing parent, circular parent, and
    disabled ephemeral children.
  - no `infra/environments` directory.
  - no committed credentials in `.tf`, `.tfbackend`, `.yaml`, or generated
    active tfvars files.
  - active root lockfiles exist.
  - every generated artifact in the active per-channel root regenerates from
    resolved channel JSON without drift: `backend.tfbackend` byte-identical,
    and `channel.auto.tfvars.json` byte-identical or canonical-JSON
    structurally identical.
  - recursive OpenTofu formatting for active infra roots, template modules, and
    shared modules.
  - YAML/schema validation through the channel schemas and Python validator;
    no separate YAML linter is required unless the implementation adds one.
- `infra/README.md` lists local prerequisites: OpenTofu CLI `1.11.5` (the
  version INIT-008 acceptance was verified against; newer 1.x patch releases
  should also work, report drift if they do not), Python major version `3.12`,
  and `jq` only if the harness uses it.
- The harness prints `tofu version` and asserts the major/minor version is
  `1.11`.
- `cd infra/bootstrap/state-backend && tofu init -backend=false && tofu validate`
  exits 0.
- `cd infra/roots/channels/dev && tofu init -backend=false && tofu validate`
  exits 0.
**Dependencies:** SLICE-026, SLICE-027, SLICE-028.
**Magnitude estimate:** M.
**Anti-scope:**
- Does not add CI or Buildkite.
- Does not require a local Kubernetes cluster.
- Does not require Vultr credentials for baseline validation.
- Does not run `tofu apply`.
### SLICE-030 - Optional Provider-Backed Plan Runbook and Dev Plan Surface
**Scope:** Define and verify the optional provider-backed plan path for the
`dev` channel when an operator has local Vultr and S3 backend credentials.
This is a runbook and command-surface slice: it proves INIT-008 can produce a
clean plan target without turning plan into mandatory CI or applying changes.
It closes the Phase 5 "author + `tofu plan`; no apply" expectation and maps
the handoff into concrete commands.
**Files this slice touches:**
- `infra/README.md`
- `infra/roots/channels/dev/backend.tfbackend`
- `infra/roots/channels/dev/channel.auto.tfvars.json`
- `infra/tests/validate_platform_bootstrap.sh`
- `.pipeline/implementation.md` (later phase notes only, if present)
**Local-verification acceptance criteria:**
- Without credentials:
  - The harness output includes `tofu version` and asserts the major/minor
    version is `1.11`.
  - `bash infra/tests/validate_platform_bootstrap.sh` exits 0.
  - The harness has no allowed failure exceptions after SLICE-030 lands.
  - `cd infra/roots/channels/dev && tofu init -backend=false && tofu validate`
    exits 0.
- With operator-supplied credentials and endpoint:
  - `cd infra/roots/channels/dev && tofu init -backend-config=backend.tfbackend`
    succeeds.
  - `cd infra/roots/channels/dev && tofu plan` produces a plan without
    applying.
  - The runbook states that a provider-backed plan may read Vultr API state
    but must not be followed by `tofu apply` in INIT-008.
- `rg -n "tofu apply" infra/README.md` shows apply is described only as
  out-of-scope or future deployment work, not an INIT-008 verification step.
**Dependencies:** SLICE-028, SLICE-029.
**Magnitude estimate:** S-M.
**Anti-scope:**
- Does not require credentials in CI.
- Does not make provider-backed plan mandatory for all contributors.
- Does not apply the plan.
- Does not bootstrap a real VKE cluster.
- Does not create DNS records or ingress.
---
## 4. Tradeoffs accepted
- **One active channel only:** INIT-008 ships `dev` and defers `customer`,
  `internal`, and named e2e channels to a separate initiative opened after
  Phase 5 converges. This reduces local blast radius and keeps Phase 5
  aligned with D2 and D5.
- **Per-channel roots over unified registry root:** INIT-008 optimizes for
  local operator clarity. A unified root can be introduced later if the repo
  needs fleet-level planning, but it is not the right first substrate.
- **Pre-process inheritance over HCL merge logic:** Python resolves YAML
  inheritance before OpenTofu sees inputs. This adds a small script surface but
  keeps HCL simple and validation failures earlier.
- **Ephemeral children reserved, not operationalized:** The schema and spawn
  script prove materialization and permission checks against fixtures;
  Buildkite/PR preview execution is deferred to INIT-011 or to the
  post-Phase-5 deployment initiative only if a future runbook needs live
  channel onboarding.
- **Single bucket with per-channel keys:** This accepts lower isolation cost
  for local-only Phase 5. Stronger per-channel buckets or subscriptions are
  deferred until there is real deployment pressure.
- **Manual bucket verification:** INIT-008 makes bucket existence an explicit
  operator handoff rather than adding a bucket resource that stale docs already
  proved can drift against provider behavior.
- **No remote-state locking claim:** INIT-008 documents single-operator use
  and does not pretend to solve concurrent backend safety before deployment.
- **No automated restore or cleanup tooling:** INIT-008 enables
  provider-side object-storage versioning at bucket creation time and documents
  manual prior-version retrieval. The post-Phase-5 deployment initiative owns
  runbook-level restore and explicit state cleanup tooling.
- **Lockfiles for active roots only:** Active roots commit provider locks.
  Transient ephemeral material does not.
- **No DNS and no public endpoint:** INIT-012 owns ingress and north-south
  routing. INIT-008 outputs only the VKE endpoint already exposed by the
  cluster module.
- **No SOPS/age:** Credential custody is manual operator handoff in INIT-008.
  INIT-009 owns SOPS/age.
- **No compatibility shims:** Old environment paths are deleted instead of
  forwarded.
- **Plan is optional without credentials:** Baseline acceptance is validation.
  Provider-backed `tofu plan` is documented and run only when local credentials
  exist.
---
## 5. Hookpoints (preview)
Full hookpoint research happens after risk. This preview identifies the
expected blast radius for risk assessment.
### SLICE-025 hookpoints
- `DECISIONS.md`: add Vultr/OpenTofu ratification entry.
- `infra/README.md`: replace environment-triad instructions with channel
  instructions.
- `plans/platform-decisions-overlay.md`: close hosting as open.
- `plans/proposals/platform-bootstrap.md`: revise as the active INIT-008
  ancestor.
- `plans/proposals/vultr-object-storage-fix.md`: supersede.
- `plans/proposals/phase1-foundation.md`: supersede.
- `plans/proposals/app-cluster-provisioning.md`: revise only as a boundary
  input.
- `plans/research/*`: mark stale research according to Section 8.
### SLICE-026 hookpoints
- New `infra/schemas/` directory.
- New `infra/channels/` directory.
- New `infra/scripts/` channel utilities.
- Existing `infra/tests/validate_platform_bootstrap.sh` gains channel
  validation checks.
- External reference shape comes from rfqautomation `channel.schema.json`,
  `dev.yaml`, `customer.yaml`, `internal.yaml`, and `e2e.yaml`.
- Fixture hookpoints include `e2e-from-dev.yaml`, `e2e-pr-1234.yaml`,
  `ephemeral-disabled.yaml`, `missing-parent.yaml`, `circular-a.yaml`, and
  `circular-b.yaml`.
### SLICE-027 hookpoints
- Existing `infra/modules/platform-network/main.tf` remains the network
  resource hookpoint.
- Existing `infra/modules/platform-cluster/main.tf` remains the VKE resource
  hookpoint.
- Existing `infra/environments/dev/main.tf` is replaced by the resolved
  `dev` channel plus `infra/roots/channels/dev/main.tf`.
- Existing `infra/environments/staging/*` and `infra/environments/production/*`
  are deleted.
- Existing backend config shape is moved to `infra/roots/channels/dev`.
- New `infra/scripts/generate_channel_backend.py` and
  `infra/scripts/generate_channel_tfvars.py` become the only way to produce
  committed generated artifacts under active per-channel roots from resolved
  channel JSON.
### SLICE-028 hookpoints
- Existing `infra/bootstrap/state-backend/main.tf` remains the Object Storage
  subscription and output hookpoint.
- Existing `bucket_name`, `s3_hostname`, `s3_access_key`, and `s3_secret_key`
  outputs remain the handoff seam.
- Existing `backend.tfbackend` placeholder convention becomes channel-root
  backend config.
- Existing tests that assert no `vultr_object_storage_bucket` remain aligned
  with the no-bucket-resource decision.
- `infra/README.md` records bucket versioning, manual restore, and channel
  retirement state-retention rules.
### SLICE-029 hookpoints
- Existing `infra/tests/validate_platform_bootstrap.sh` is the main harness.
- New channel scripts are invoked by the harness.
- Active root `.terraform.lock.hcl` files become test inputs.
- Security assertions expand from `.tf` and dev backend only to all active
  channel files.
### SLICE-030 hookpoints
- `infra/README.md` becomes the operator runbook.
- `infra/roots/channels/dev/backend.tfbackend` is the backend init input.
- `infra/roots/channels/dev/channel.auto.tfvars.json` is the plan input.
- No hookpoint exists in CI yet; Buildkite belongs to INIT-011.
---
## 6. Acceptance criteria for INIT-008 as a whole
- [ ] **Phase 0 hosting formalization:** `DECISIONS.md` ratifies Vultr and
      OpenTofu as the INIT-008 substrate, and active Phase 5 docs no longer
      treat hosting as open. Satisfies the Phase 0 criterion "hosting decision
      is formalized."
- [ ] **Phase 0 deployable substrate alignment:** `infra/` has a channel
      registry, platform-channel template, active `dev` root, state-backend
      bootstrap root, and existing VPC/VKE modules wired through the channel
      template. Satisfies "deployable service substrate aligned to `infra/`"
      for bootstrap authoring, not workload deployment.
- [ ] **Phase 0 test harness:** `bash infra/tests/validate_platform_bootstrap.sh`
      validates the bootstrap root, active channel root, channel schemas,
      absence of old environment roots, no committed credentials, and provider
      lockfile posture. Satisfies the infra-specific part of "shared test
      harness is functional."
- [ ] **Phase 0 secret-management boundary:** INIT-008 documents manual
      operator custody for Vultr and backend credentials and commits no
      secrets. This partially satisfies the Phase 0 secret-management criterion
      by defining custody until INIT-009 implements SOPS/age.
- [ ] **Channel pivot complete:** `infra/environments/{dev,staging,production}`
      no longer exists, and `infra/channels/dev.yaml` plus
      `infra/roots/channels/dev` are the only active platform-channel target.
      Satisfies the user's non-negotiable channel-pattern decision.
- [ ] **Remote-state contract explicit:** The active backend uses bucket
      `humility-tfstate` and key `channels/dev/terraform.tfstate`; bootstrap
      outputs the endpoint and credentials; bucket existence is an explicit
      operator handoff with provider-side object-storage versioning enabled at
      bucket creation, not an implicit assumption. Satisfies D3 and D4.
- [ ] **Schema contract complete:** Source and resolved channel schemas define
      required fields, types, enums, patterns, numeric bounds, nullable
      handling, and `additionalProperties: false`; only `schema_version: 1` is
      accepted, and unknown versions fail explicitly.
- [ ] **Inheritance and spawn gates tested:** Resolver fixtures prove inherited
      `dev` values, child overrides, missing-parent failure, circular-parent
      failure, and disabled-ephemeral spawn failure.
- [ ] **Generated root artifacts deterministic:** The committed generated
      artifacts in `infra/roots/channels/dev/` are generated from resolved
      channel JSON and regenerate without drift: `backend.tfbackend`
      byte-identically and `channel.auto.tfvars.json` byte-identically or by
      canonical-JSON structural equivalence.
- [ ] **Retirement lifecycle documented:** Removing a channel YAML retires the
      id, does not auto-delete state, and hands explicit cleanup tooling to
      the post-Phase-5 deployment initiative.
- [ ] **Local validation clean:** These commands succeed without Vultr
      credentials:
      `cd infra/bootstrap/state-backend && tofu init -backend=false && tofu validate`;
      `cd infra/roots/channels/dev && tofu init -backend=false && tofu validate`;
      `python infra/scripts/validate_platform_channels.py`;
      `bash infra/tests/validate_platform_bootstrap.sh`.
      Satisfies D11.
- [ ] **Optional plan path documented:** With operator-supplied credentials,
      `infra/roots/channels/dev` has a documented `tofu plan` path. The
      documentation says no `tofu apply` occurs in INIT-008. Satisfies the
      Phase 5 INIT-008 "author + plan; no apply" framing.
- [ ] **Provider reproducibility:** Active roots have committed lockfiles or a
      documented implementation reason if OpenTofu cannot generate one in the
      local environment. Satisfies D12.
- [ ] **Boundary preserved:** No Flux, Buildkite, ingress, DNS, SOPS/age,
      application workload, data-plane, auth, observability, or Crossplane
      resources are added. Satisfies D2, D7, D9, and D10.
---
## 7. Anti-scope
INIT-008 explicitly does not do the following:
- **INIT-009 GitOps Substrate:** no Flux install, no Kustomize environment
  layout, no SOPS/age secret encryption, no GitOps reconciliation.
- **INIT-010 Container Delivery:** no Dockerfiles, no image build pipeline, no
  service smoke-run packaging.
- **INIT-011 CI/CD:** no Buildkite pipeline, no local Buildkite agent
  validation, no PR-preview execution.
- **INIT-012 Ingress and North-South:** no Kong or equivalent ingress, no TLS,
  no DNS records, no hostnames, no public routing contract.
- **INIT-013 Data Plane:** no CloudNativePG, no database bootstrap, no Atlas
  migrations on deploy, no persistent workload data plane.
- **INIT-014 Application Workloads:** no API deployment, no Discord daemon
  deployment, no Kubernetes workload manifests, no ConfigMaps or runtime
  service secrets.
- **INIT-015 Auth Stack:** no Authentik, OPAL/Cedar, Pomerium, policy agent,
  identity plumbing, or auth deployment.
- **INIT-016 Observability:** no logs, metrics, tracing, dashboards, agents, or
  observability stack selection.
- **Application-cluster provisioning:** no Crossplane installation, no
  application-cluster compositions, no managed app-cluster lifecycle.
- **Live infrastructure mutation:** no `tofu apply`, no real VKE cluster
  creation, no real DNS mutation, no visible Discord action.
- **Backward compatibility:** no old `infra/environments/*` compatibility
  wrappers, no deprecated aliases, no duplicate roots.
- **Multi-channel onboarding:** no active `customer`, `internal`, `staging`,
  `production`, or named e2e channel root.
- **Remote-state concurrency guarantee:** no multi-operator locking or tested
  restore drill.
- **Automated state restore:** no restore command, no restore drill, no
  provider-side version selection workflow beyond documenting manual operator
  retrieval.
- **State cleanup tooling:** no `cleanup-state` implementation and no automatic
  state deletion when a channel retires; the post-Phase-5 deployment initiative
  owns this runbook and tooling.
- **Post-Phase-5 channel onboarding:** no real `customer`, `internal`, named
  e2e, or production-class channel onboarding in Phase 5.
---
## 8. Stale material disposal
| Path | Action | Reason |
| --- | --- | --- |
| deleted provider-comparison research file | delete | Historical provider comparison only; INIT-008 is Vultr-locked by D1 and the user decision, so this file is removed rather than parked. |
| `plans/research/vultr-fix-hookpoints.md` | delete | Assumes `vultr_object_storage_bucket` exists in bootstrap and frames the fix as a provider bump. Live repo and D3 choose explicit operator bucket verification instead. |
| `plans/research/vultr-object-storage-fix.md` | delete | Describes a stale bucket-resource bug state. The file is removed rather than retained as historical context. |
| `plans/research/opentofu-providers.md` | revise | OpenTofu/Vultr direction remains useful, but bucket-resource and host-comparison framing must be updated to the channel-root proposal and D12 lockfile posture. |
| `plans/research/platform-bootstrap-hookpoints.md` | delete | Old hookpoint research is replaced by `.pipeline/hookpoints.md` and still assumes the pre-channel root shape. |
| `plans/proposals/platform-bootstrap.md` | revise | Closest ancestor proposal, but it predates the channel pivot and keeps unresolved state/custody questions that this proposal closes. |
| `plans/proposals/vultr-object-storage-fix.md` | delete | The live repo already moved away from that provider-bump/resource path; INIT-008 must not carry it forward. |
| `plans/proposals/phase1-foundation.md` | delete | Retired self-managed provider substrate, bundled Flux/Kong/secrets scope, and older substrate assumptions conflict with Phase 5. |
| `plans/proposals/app-cluster-provisioning.md` | revise | Its two-tier boundary remains relevant, but hosting ambiguity and platform/application split need alignment with the Vultr/channel substrate. |

Disposal semantics:
- `revise`: update the file so active claims match this proposal.
- `delete`: remove stale files from the repo rather than parking them.
---
## Risk-gate focus
The three biggest tradeoffs the risk gate should validate are:
1. One active `dev` channel plus deferred `customer`/`internal` onboarding is
   enough for INIT-008 and all of Phase 5, even though the schema reserves
   production-class and operator-class fields for a separate initiative opened
   after Phase 5 converges.
2. One bucket with per-channel keys and explicit operator bucket verification
   is acceptable for local-only Phase 5, despite not implementing Terraform
   bucket lifecycle, automated restore, cleanup-state tooling, or remote-state
   locking.
3. Pre-processing channel inheritance into resolved tfvars is the right
   complexity tradeoff versus implementing channel merge semantics directly in
   OpenTofu.
---
## 9. Revision history
### Round 1 risk closure map
- **A1 - Schema field constraints incomplete:** Closed by Section 2.3 and SLICE-026 acceptance: both schemas must define required/optional status, types, enums, regexes, numeric bounds, nullable handling, and `additionalProperties: false`.
- **A2 - Schema versioning strategy missing:** Closed by Section 2.3 and SLICE-026 acceptance: only `schema_version: 1` is accepted, unknown versions fail structurally, and future bumps follow no-backwards-compatibility.
- **A4 - Restore posture not concrete:** Closed by Sections 2.10, 2.12, SLICE-028 acceptance, and Section 7 anti-scope: no INIT-008 restore drill; bucket versioning plus manual prior-version retrieval only; the post-Phase-5 deployment initiative owns runbook restore and tooling.
- **A5 - Channel removal lifecycle missing:** Closed by Section 2.11, SLICE-028 acceptance, and Section 7 anti-scope: removing YAML retires the id, resolver refuses retired ids, state is retained until explicit cleanup, and cleanup-state belongs to the post-Phase-5 deployment initiative.
- **H1 - Inheritance not exercised:** Closed by Sections 2.5, 2.8, and SLICE-026 acceptance: `e2e-from-dev.yaml`, `missing-parent.yaml`, `circular-a.yaml`, and `circular-b.yaml` drive positive merged-field assertions and negative resolver failures.
- **H2 - Ephemeral spawn permission not negative-tested:** Closed by Sections 2.5, 2.9, and SLICE-026 acceptance: `ephemeral-disabled.yaml` must make spawn exit non-zero with `ephemeral_children_disabled`.
- **H3 - Channel-onboarding successor initiative unnamed:** Closed by Section 1, Section 2.4, Section 4, Section 7, and risk-gate focus: real `customer`, `internal`, and named e2e onboarding is anti-scope for INIT-008 and Phase 5, and belongs to a separate initiative opened after Phase 5 converges.

### Round 2 risk closure map
- **A1 - OpenTofu CLI verification version unpinned:** Closed by Section 2.13, SLICE-025 acceptance, and SLICE-029/SLICE-030 acceptance: INIT-008 verifies with OpenTofu CLI `1.11.5`, roots keep the `>= 1.8.0` feature floor, README prerequisites name `1.11.5`, and the harness prints `tofu version` while asserting major/minor `1.11`.
- **H1 - Fictional successor initiative label:** Closed throughout the proposal by replacing the invented deployment-successor label with neutral post-Phase-5 language: a separate initiative opened after Phase 5 converges, the post-Phase-5 deployment initiative, or anti-scope until a deployment initiative is opened.

### Round 3 risk closure map
- **A1 - Generated tfvars drift contract missing:** Closed by Section 2.7, SLICE-027 acceptance, SLICE-029 harness acceptance, and Section 6 acceptance: every generated artifact in `infra/roots/channels/<id>/` has regeneration drift detection. INIT-008 names `backend.tfbackend` and `channel.auto.tfvars.json`; backend output must compare byte-identically, and generated tfvars must compare byte-identically or by canonical-JSON structural equivalence.
- **H2 - Inheritance fixtures only depth-1:** Closed by Section 2.5, SLICE-026 files, SLICE-026 acceptance, and SLICE-026 hookpoints: `e2e-pr-1234.yaml` is a depth-2 fixture with parent `e2e-from-dev`, and acceptance asserts values inherited from both `dev` and `e2e-from-dev`.
- **H3 - Prose-only state endpoint field:** Closed by Section 2.3, Section 2.4, Section 2.10, and SLICE-028 acceptance: the state schema carries no prose-only endpoint field; the S3 endpoint explanation lives in the operator handoff documentation and `infra/README.md`.

LOW findings folded in:
- **A3:** SLICE-027 requires each `variables.tf` variable to specify a type and either a default or explicit "no default; required" contract.
- **H4:** Section 2.7 and SLICE-027 require `backend.tfbackend` to be generated from resolved channel JSON and byte-identical when regenerated.
- **H5:** Sections 2.3, 2.4, and SLICE-028 remove the endpoint placeholder field; endpoint handling is documentation-only through backend init flags.
- **H7:** SLICE-025 and SLICE-029 require `infra/README.md` prerequisites: OpenTofu CLI `1.11.5`, Python major `3.12`, and `jq` only if used.
- **H8:** SLICE-025 enumerates temporary harness failures; SLICE-030 requires no allowed exceptions after the final slice lands.

LOW findings intentionally left as-is:
- **H6:** Left as-is because D3 chose operator bucket verification over Terraform-managed bucket lifecycle; live bucket existence validation remains outside local-only scope.
