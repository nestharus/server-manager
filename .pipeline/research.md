# INIT-008 Phase 1 Research — Platform Bootstrap State

Scope: characterize the current repo state for Vultr/OpenTofu platform bootstrap, prior decisions, prior material, and gaps. This is evidence only. No solution design is proposed here.

Primary source set read in the requested order:

1. `infra/README.md`
2. `plans/platform-decisions-overlay.md`
3. `plans/research/hetzner-vs-vultr.md`
4. `plans/research/vultr-fix-hookpoints.md`
5. `plans/research/vultr-object-storage-fix.md`
6. `plans/research/opentofu-providers.md`
7. `plans/research/platform-bootstrap-hookpoints.md`
8. `plans/proposals/platform-bootstrap.md`
9. `plans/proposals/vultr-object-storage-fix.md`
10. `plans/proposals/phase1-foundation.md`
11. `plans/proposals/app-cluster-provisioning.md`
12. `product-strategy/engineering roadmap.md`
13. `infra/bootstrap/state-backend/main.tf`
14. `infra/modules/platform-network/main.tf`
15. `infra/modules/platform-cluster/main.tf`
16. `infra/environments/dev/`
17. `infra/environments/staging/`
18. `infra/environments/production/`

Local verification note:

- On 2026-04-23 in this worktree, `tofu init -backend=false && tofu validate` succeeded in `infra/bootstrap/state-backend`, `infra/environments/dev`, `infra/environments/staging`, and `infra/environments/production`. This is an observed local command result, not a checked-in repo artifact.

## 1. Current repo state

### 1.1 `infra/` tree as checked in

| Path | Exists | Current role | Evidence |
| --- | --- | --- | --- |
| `infra/bootstrap/state-backend/` | Yes | One-time bootstrap root for remote-state backing; README describes it as creating Object Storage for tfstate and applying before environment roots. | `infra/README.md:7-31` |
| `infra/modules/platform-network/` | Yes | Shared VPC module. | `infra/README.md:10-16`, `infra/modules/platform-network/main.tf:1-50` |
| `infra/modules/platform-cluster/` | Yes | Shared VKE module. | `infra/README.md:10-16`, `infra/modules/platform-cluster/main.tf:1-81` |
| `infra/environments/dev/` | Yes | Persistent dev root. | `infra/README.md:13-16`, `infra/environments/dev/main.tf:1-50` |
| `infra/environments/staging/` | Yes | On-demand staging/validation root. | `infra/README.md:13-16`, `infra/environments/staging/main.tf:1-51` |
| `infra/environments/production/` | Yes | Persistent production root. | `infra/README.md:13-16`, `infra/environments/production/main.tf:1-50` |

### 1.2 Bootstrap state-backend: what it actually creates now

Current checked-in bootstrap root does less than some prior docs assume.

| Item | Current state in code | Notes | Evidence |
| --- | --- | --- | --- |
| Terraform/OpenTofu block | Present | Requires OpenTofu `>= 1.8.0`; pins provider constraint `~> 2.30`. | `infra/bootstrap/state-backend/main.tf:11-20` |
| Required inputs | `object_storage_cluster_id`, `object_storage_tier_id` | Both are required variables; no defaults. | `infra/bootstrap/state-backend/main.tf:22-30` |
| Optional label input | `object_storage_label` default `humility-tfstate` | Labels the subscription. | `infra/bootstrap/state-backend/main.tf:32-36` |
| Optional bucket-name input | `bucket_name` default `humility-tfstate` | Output-only in current code; not attached to a resource. | `infra/bootstrap/state-backend/main.tf:38-42`, `52-54` |
| Vultr provider block | Present | No inline credentials. | `infra/bootstrap/state-backend/main.tf:44` |
| Resource created | `vultr_object_storage.state` only | Creates the object-storage subscription. | `infra/bootstrap/state-backend/main.tf:46-50` |
| Bucket resource | Not present | Current code does **not** declare `vultr_object_storage_bucket`. | `infra/bootstrap/state-backend/main.tf:46-67`; corroborated by `infra/tests/validate_platform_bootstrap.sh:193-205` |
| Outputs | `bucket_name`, `s3_hostname`, `s3_access_key`, `s3_secret_key` | `bucket_name` is just the variable value; `s3_*` come from `vultr_object_storage.state`. | `infra/bootstrap/state-backend/main.tf:52-67` |
| State backend for bootstrap root | Local state only | README calls this out explicitly. | `infra/README.md:18-31`, `plans/research/platform-bootstrap-hookpoints.md:61-78` |

Current-state implication:

- The checked-in bootstrap root provisions a Vultr object-storage subscription and exposes operator-consumable S3 connection outputs, but it does **not** provision a bucket resource in the current repo state. [`infra/bootstrap/state-backend/main.tf:46-67`]

### 1.3 Shared modules: what exists and what they provision

#### `infra/modules/platform-network/main.tf`

| Concern | Current state | Evidence |
| --- | --- | --- |
| Inputs | `environment`, `region`, `v4_subnet`, `v4_subnet_mask` | `infra/modules/platform-network/main.tf:8-27` |
| Resource | One `vultr_vpc.platform` | `infra/modules/platform-network/main.tf:29-34` |
| Naming | `description = "humility-${var.environment}-platform"` | `infra/modules/platform-network/main.tf:29-34` |
| Outputs | `vpc_id`, `description`, `v4_subnet`, `v4_subnet_mask` | `infra/modules/platform-network/main.tf:36-50` |
| Hardcoded environment names inside module logic | None beyond comments | Module takes environment as input; no `dev`/`staging`/`production` literals in resource logic. | `infra/modules/platform-network/main.tf:8-50`, `infra/tests/validate_platform_bootstrap.sh:263-285` |

#### `infra/modules/platform-cluster/main.tf`

| Concern | Current state | Evidence |
| --- | --- | --- |
| Inputs | `environment`, `region`, `cluster_label`, `kubernetes_version`, `vpc_id`, `node_plan`, `node_quantity`, `ha_controlplanes`, `enable_firewall` | `infra/modules/platform-cluster/main.tf:3-48` |
| Resource | One `vultr_kubernetes.platform` | `infra/modules/platform-cluster/main.tf:50-64` |
| Node pool shape | Embedded default node pool inside `vultr_kubernetes` resource | `infra/modules/platform-cluster/main.tf:58-63` |
| Firewall flag | Managed Vultr firewall toggle exists and defaults `true` | `infra/modules/platform-cluster/main.tf:44-48`, `50-56` |
| Outputs | `cluster_id`, `endpoint`, `kube_config`, `firewall_group_id` | `infra/modules/platform-cluster/main.tf:66-81` |
| Sensitive output handling | `kube_config` marked sensitive | `infra/modules/platform-cluster/main.tf:74-77`, `infra/tests/validate_platform_bootstrap.sh:217-230` |

### 1.4 Environment roots: include/exclude surface

#### Common shape across `dev`, `staging`, `production`

| Concern | Current state | Evidence |
| --- | --- | --- |
| Terraform/OpenTofu block | Present in all three roots | `infra/environments/dev/main.tf:4-15`, `infra/environments/staging/main.tf:5-16`, `infra/environments/production/main.tf:4-15` |
| Required version | `>= 1.8.0` in all three roots | `infra/environments/dev/main.tf:4-15`, `infra/environments/staging/main.tf:5-16`, `infra/environments/production/main.tf:4-15` |
| Vultr provider constraint | `~> 2.30` in all three roots | `infra/environments/dev/main.tf:7-12`, `infra/environments/staging/main.tf:8-13`, `infra/environments/production/main.tf:7-12` |
| Backend type | `backend "s3" {}` in all three roots | `infra/environments/dev/main.tf:14-15`, `infra/environments/staging/main.tf:15-16`, `infra/environments/production/main.tf:14-15` |
| Provider block | `provider "vultr" {}` in all three roots | `infra/environments/dev/main.tf:17`, `infra/environments/staging/main.tf:18`, `infra/environments/production/main.tf:17` |
| Network module included | Yes | `infra/environments/dev/main.tf:19-25`, `infra/environments/staging/main.tf:20-26`, `infra/environments/production/main.tf:19-25` |
| Cluster module included | Yes | `infra/environments/dev/main.tf:27-38`, `infra/environments/staging/main.tf:28-39`, `infra/environments/production/main.tf:27-38` |
| Outputs exposed | `vpc_id`, `cluster_id`, `endpoint` | `infra/environments/dev/main.tf:40-50`, `infra/environments/staging/main.tf:41-51`, `infra/environments/production/main.tf:40-50` |

#### Environment-specific parameterization

| Root | Declared purpose | Region | VPC subnet | Cluster label | Kubernetes version | Node plan | Node qty | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dev` | Persistent, always-on; application dev, E2E tests, LLM video QA, fast iteration | `ewr` | `10.40.0.0/20` | `humility-dev-platform` | `v1.32.3+1` | `vc2-2c-4gb` | `2` | `infra/environments/dev/main.tf:1-38` |
| `staging` | On-demand; benchmarks, load tests, release-candidate validation | `ewr` | `10.40.16.0/20` | `humility-staging-platform` | `v1.32.3+1` | `vc2-2c-4gb` | `3` | `infra/environments/staging/main.tf:1-39` |
| `production` | Persistent; real workloads, user-facing services | `ewr` | `10.40.32.0/20` | `humility-production-platform` | `v1.32.3+1` | `vc2-2c-4gb` | `3` | `infra/environments/production/main.tf:1-38` |

#### What environment roots currently exclude

| Excluded concern | Evidence |
| --- | --- |
| No DNS resources in roots | Each root contains only `network` and `cluster` module blocks plus outputs. `infra/environments/dev/main.tf:19-50`, `infra/environments/staging/main.tf:20-51`, `infra/environments/production/main.tf:19-50` |
| No object-storage resources in roots | Same evidence as above; roots do not declare `vultr_object_storage` or bucket resources. |
| No load balancer resources in roots | Same evidence as above. |
| No firewall-rule resources beyond cluster `enable_firewall` flag | `infra/modules/platform-cluster/main.tf:44-56` |
| No GitOps/Flux resources | Root code is infra-only. `infra/environments/dev/main.tf:19-50`, `infra/environments/staging/main.tf:20-51`, `infra/environments/production/main.tf:19-50` |
| No Crossplane resources | Root code is infra-only. `infra/environments/dev/main.tf:19-50`, `infra/environments/staging/main.tf:20-51`, `infra/environments/production/main.tf:19-50`; boundary also stated in `plans/proposals/platform-bootstrap.md:191-196` and `plans/proposals/app-cluster-provisioning.md:105-121` |

### 1.5 Backend config files and placeholders

| File | Bucket | Key | Region | Placeholder state | Credentials in file | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `infra/environments/dev/backend.tfbackend` | `humility-tfstate` | `infra/dev/terraform.tfstate` | `ewr` | `endpoints = { s3 = "REPLACE_AFTER_BOOTSTRAP" }` | No access/secret key values committed | `infra/environments/dev/backend.tfbackend:1-13` |
| `infra/environments/staging/backend.tfbackend` | `humility-tfstate` | `infra/staging/terraform.tfstate` | `ewr` | `endpoints = { s3 = "REPLACE_AFTER_BOOTSTRAP" }` | No access/secret key values committed | `infra/environments/staging/backend.tfbackend:1-13` |
| `infra/environments/production/backend.tfbackend` | `humility-tfstate` | `infra/production/terraform.tfstate` | `ewr` | `endpoints = { s3 = "REPLACE_AFTER_BOOTSTRAP" }` | No access/secret key values committed | `infra/environments/production/backend.tfbackend:1-13` |

Current-state implication:

- All three environment roots are structurally present, but none can initialize the real S3 backend until `REPLACE_AFTER_BOOTSTRAP` is replaced with the bootstrap-provided endpoint. [`infra/README.md:20-31`, `infra/environments/dev/backend.tfbackend:1-13`, `infra/environments/staging/backend.tfbackend:1-13`, `infra/environments/production/backend.tfbackend:1-13`, `plans/research/platform-bootstrap-hookpoints.md:64-78`]
- The repo does not commit backend credentials into `backend.tfbackend`; bootstrap exposes `s3_access_key` and `s3_secret_key` as sensitive outputs instead. [`infra/bootstrap/state-backend/main.tf:56-67`, `infra/tests/validate_platform_bootstrap.sh:307-325`]

### 1.6 Pinned versions and current pin behavior

| Surface | Pinned in repo | Where pinned | Notes |
| --- | --- | --- | --- |
| OpenTofu / Terraform CLI compatibility | `required_version = ">= 1.8.0"` | Bootstrap root and all environment roots | `infra/bootstrap/state-backend/main.tf:11-20`, `infra/environments/dev/main.tf:4-15`, `infra/environments/staging/main.tf:5-16`, `infra/environments/production/main.tf:4-15`, `infra/README.md:39` |
| Vultr provider constraint | `version = "~> 2.30"` | Bootstrap root and all environment roots | `infra/bootstrap/state-backend/main.tf:14-19`, `infra/environments/dev/main.tf:7-12`, `infra/environments/staging/main.tf:8-13`, `infra/environments/production/main.tf:7-12`, `infra/README.md:39` |
| Checked-in lock file | None present under `infra/` | No `.terraform.lock.hcl` is committed in the current tree | Local file-tree observation from `rg --files infra` on 2026-04-23 |

Local observation:

- On 2026-04-23, `tofu init` resolved the `~> 2.30` constraint to provider `v2.31.0` in local validation runs. That behavior matters because some older docs were written when the bucket resource had not yet shipped.

### 1.7 Direct repo/doc mismatches visible now

| Topic | Live repo state | Older material | Status |
| --- | --- | --- | --- |
| Hosting record | `infra/README.md` already describes Vultr-managed infra | `plans/platform-decisions-overlay.md` still lists `Hetzner` vs `Vultr` as open | Documentation conflict |
| Bootstrap bucket creation | Bootstrap root creates only `vultr_object_storage` | Older hookpoint/research/proposal docs discuss `vultr_object_storage_bucket` in bootstrap | Stale material |
| Test script expectation | `infra/tests/validate_platform_bootstrap.sh` asserts there is **no** `vultr_object_storage_bucket` resource | Older Vultr object-storage fix docs assume test needed updating the other direction | Stale material |
| Formal decision log | Engineering roadmap still requires hosting formalization in `DECISIONS.md` | Live infra and platform-bootstrap proposal already assume Vultr | Formalization gap |

Evidence:

- `infra/README.md:1-39`
- `plans/platform-decisions-overlay.md:15-29`
- `infra/bootstrap/state-backend/main.tf:46-67`
- `infra/tests/validate_platform_bootstrap.sh:193-205`
- `plans/research/vultr-fix-hookpoints.md:31-67`
- `plans/research/vultr-object-storage-fix.md:5-33`
- `plans/proposals/vultr-object-storage-fix.md:6-30`
- `product-strategy/engineering roadmap.md:5-10`, `102-117`

## 2. Prior decisions and where they live

Table legend:

- `LOCKED` = recorded as settled in current checked-in material.
- `ASSUMED IN REPO` = implemented/assumed by repo artifacts but not yet fully ratified in the stated authoritative log.
- `NOT YET FORMALIZED` = current repo/proposals depend on it, but the repo still says formalization is pending.

| Decision | Status | Authoritative source(s) in repo | Notes |
| --- | --- | --- | --- |
| Infrastructure substrate in the live `infra/` tree is Vultr | `ASSUMED IN REPO` | `infra/README.md:1-3` | This is the clearest checked-in statement of current infra reality. |
| OpenTofu is the canonical operator/IaC entrypoint for bootstrap | `ASSUMED IN REPO` | `infra/README.md:3`, `plans/proposals/platform-bootstrap.md:31-37`, `147-170` | Repo structure and proposal agree. |
| GitOps reconciler direction is Flux | `LOCKED` | `plans/platform-decisions-overlay.md:17-23` | Overlay says Flux replaces Argo CD and is the reconciler direction. |
| CI/CD direction is Buildkite | `LOCKED` | `plans/platform-decisions-overlay.md:17-23` | Overlay says Buildkite is canonical CI/CD direction. |
| Provider-native object storage is preferred before self-hosted S3 | `LOCKED` | `plans/platform-decisions-overlay.md:17-23` | Overlay says provider-native object storage first; SeaweedFS is fallback only. |
| Bootstrap must avoid self-hosted S3 layers | `ASSUMED IN REPO` | `plans/research/platform-bootstrap-hookpoints.md:10-25`, `plans/proposals/platform-bootstrap.md:128-145`, `221-238` | Hookpoints/proposal both treat this as a constraint. |
| Two-tier model: platform cluster first, application clusters later | `ASSUMED IN REPO` | `plans/proposals/platform-bootstrap.md:22-29`, `72-78`; `plans/proposals/app-cluster-provisioning.md:96-103`, `107-121` | Boundary is proposal-level and consistent across both initiatives. |
| Crossplane belongs to Application Cluster Provisioning, not Platform Bootstrap | `ASSUMED IN REPO` | `plans/proposals/platform-bootstrap.md:191-196`, `227-228`; `plans/proposals/app-cluster-provisioning.md:96-121`, `316-323` | This boundary is consistent but not yet recorded in the overlay. |
| Hosting decision still needs explicit formalization in `DECISIONS.md` before Phase 0 completion | `NOT YET FORMALIZED` | `product-strategy/engineering roadmap.md:5-10`, `97-110` | Roadmap explicitly says hosting is framed as whatever `infra/` currently configures, but formalization in `DECISIONS.md` is still required. |
| `plans/platform-decisions-overlay.md` still records hosting as open | `STALE/CONFLICTED` | `plans/platform-decisions-overlay.md:25-29` | This conflicts with the live Vultr-specific `infra/` tree and the later platform-bootstrap proposal. |

Decision-log state:

- `DECISIONS.md` exists, but the engineering roadmap still treats hosting formalization as incomplete. [`product-strategy/engineering roadmap.md:5-10`, `102-117`]
- For INIT-008, the practical authoritative sources are split:
  - live infra state: `infra/README.md` and `infra/` code
  - locked platform-adjacent directions: `plans/platform-decisions-overlay.md`
  - unresolved formal ratification: engineering roadmap Phase 0 acceptance criteria

## 3. Prior material — current vs. stale

### 3.1 `plans/platform-decisions-overlay.md`

- Maps cleanly onto current state:
  - Buildkite as canonical CI/CD direction. [`plans/platform-decisions-overlay.md:17-23`]
  - Flux as reconciler direction. [`plans/platform-decisions-overlay.md:17-23`]
  - Provider-native object storage preferred before self-hosted S3. [`plans/platform-decisions-overlay.md:17-23`]
- Stale/displaced:
  - The overlay still lists hosting as `Hetzner` vs `Vultr` open. [`plans/platform-decisions-overlay.md:25-29`]
  - That is stale relative to the current `infra/` tree already being Vultr-specific. [`infra/README.md:1-3`]
- Open questions it still leaves:
  - Hosting formalization is still unresolved at the overlay level. [`plans/platform-decisions-overlay.md:25-29`]
  - OpenTofu provider research is still listed as running, even though `infra/` already exists. [`plans/platform-decisions-overlay.md:25-29`]

### 3.2 `plans/research/hetzner-vs-vultr.md`

- Maps cleanly onto current state:
  - Recommends Vultr as the stronger managed-Kubernetes host. [`plans/research/hetzner-vs-vultr.md:5-14`, `72-80`]
  - Highlights VKE as the first-party managed Kubernetes path and better fit for this platform. [`plans/research/hetzner-vs-vultr.md:17-30`, `53-61`]
- Stale/displaced:
  - It is comparison research, so the only stale part is that the decision it informed is no longer supposed to be open for proposal work. [`plans/research/hetzner-vs-vultr.md:72-80`; compare `infra/README.md:1-3`]
- Open questions that survive:
  - VKE/VPC attachment ambiguity remains a live diligence item. [`plans/research/hetzner-vs-vultr.md:13-14`, `plans/research/hetzner-vs-vultr.md:39-41`, `plans/research/hetzner-vs-vultr.md:63-70`, `plans/research/hetzner-vs-vultr.md:80`]
  - Stateful-service backup/restore design remains outside the provider choice itself. [`plans/research/hetzner-vs-vultr.md:49-51`, `63-70`]

### 3.3 `plans/research/vultr-fix-hookpoints.md`

- Maps cleanly onto current state:
  - The backend files still hardcode `bucket = "humility-tfstate"` and use manual endpoint replacement. [`plans/research/vultr-fix-hookpoints.md:82-95`; confirmed by `infra/environments/dev/backend.tfbackend:1-13`, `infra/environments/staging/backend.tfbackend:1-13`, `infra/environments/production/backend.tfbackend:1-13`]
  - Bootstrap outputs are operator-facing and not consumed via `terraform_remote_state`. [`plans/research/vultr-fix-hookpoints.md:69-80`; confirmed by `infra/bootstrap/state-backend/main.tf:52-67`]
- Stale/displaced:
  - It assumes `infra/bootstrap/state-backend/main.tf` still declares `vultr_object_storage_bucket`. [`plans/research/vultr-fix-hookpoints.md:31-67`]
  - It frames the fix as a provider bump from `~> 2.30` to `~> 2.31`. [`plans/research/vultr-fix-hookpoints.md:13-29`, `96-124`]
  - The live repo no longer has that bucket resource at all. [`infra/bootstrap/state-backend/main.tf:46-67`, `infra/tests/validate_platform_bootstrap.sh:193-205`]
- Open questions that survive:
  - Manual bootstrap ordering still exists. [`plans/research/vultr-fix-hookpoints.md:82-95`]
  - Backend endpoint replacement remains a manual seam. [`plans/research/vultr-fix-hookpoints.md:82-95`; `infra/environments/dev/backend.tfbackend:5-6`, `infra/environments/staging/backend.tfbackend:5-6`, `infra/environments/production/backend.tfbackend:5-6`]

### 3.4 `plans/research/vultr-object-storage-fix.md`

- Maps cleanly onto current state:
  - Correctly identifies that backend files are literal strings and not dynamically wired to Terraform outputs. [`plans/research/vultr-object-storage-fix.md:197-206`]
  - Correctly identifies bootstrap required inputs and operator outputs as the seam. [`plans/research/vultr-object-storage-fix.md:5-33`, `197-206`]
- Stale/displaced:
  - It says current code declares a `vultr_object_storage_bucket` resource and fails because provider `v2.30.x` lacks it. [`plans/research/vultr-object-storage-fix.md:5-33`]
  - It says the resource was only on provider `master` and unreleased. [`plans/research/vultr-object-storage-fix.md:34-73`]
  - The live bootstrap root no longer declares the bucket resource. [`infra/bootstrap/state-backend/main.tf:46-67`]
- Open questions that survive:
  - None as a direct repo bug description; its main problem statement has been bypassed by changing the checked-in code rather than landing the proposed provider-bump fix.

### 3.5 `plans/research/opentofu-providers.md`

- Maps cleanly onto current state:
  - OpenTofu as canonical IaC remains consistent with the repo. [`plans/research/opentofu-providers.md:5-12`, `88-100`; `infra/README.md:1-39`]
  - Vultr remains the cleaner first-party managed-Kubernetes path for the current initiative boundary. [`plans/research/opentofu-providers.md:56-76`, `88-100`]
- Stale/displaced:
  - The document says Vultr’s current resource set includes `vultr_object_storage_bucket`. [`plans/research/opentofu-providers.md:56-65`]
  - That may now be true provider-side, but the repo no longer consumes that resource in bootstrap. [`infra/bootstrap/state-backend/main.tf:46-67`]
  - The Hetzner path discussion is now mainly superseded for INIT-008. [`plans/research/opentofu-providers.md:25-55`; compare `infra/README.md:1-3`]
- Open questions that survive:
  - VKE networking caveat around legacy VPC vs newer networking remains live. [`plans/research/opentofu-providers.md:78-87`, `123-124`]
  - Extra node-pool / managed-service scope choices remain implementation-time questions. [`plans/research/opentofu-providers.md:62-76`, `84-86`]

### 3.6 `plans/research/platform-bootstrap-hookpoints.md`

- Maps cleanly onto current state:
  - Shared-module + per-environment-root composition matches the current `infra/` layout. [`plans/research/platform-bootstrap-hookpoints.md:26-41`; `infra/modules/platform-network/main.tf:1-50`, `infra/modules/platform-cluster/main.tf:1-81`, `infra/environments/dev/main.tf:1-50`, `infra/environments/staging/main.tf:1-51`, `infra/environments/production/main.tf:1-50`]
  - Bootstrap-before-environment ordering remains real because of backend endpoint replacement. [`plans/research/platform-bootstrap-hookpoints.md:59-78`; `infra/environments/dev/backend.tfbackend:5-6`, `infra/environments/staging/backend.tfbackend:5-6`, `infra/environments/production/backend.tfbackend:5-6`]
  - Cluster outputs `endpoint` and `kube_config` still exist as handoff seams. [`plans/research/platform-bootstrap-hookpoints.md:43-57`; `infra/modules/platform-cluster/main.tf:70-77`]
  - Provider pins and OpenTofu version constraints match the current code. [`plans/research/platform-bootstrap-hookpoints.md:94-102`; `infra/bootstrap/state-backend/main.tf:11-20`; `infra/environments/dev/main.tf:4-15`]
- Stale/displaced:
  - Hookpoint 1 says bootstrap implements both `vultr_object_storage` and `vultr_object_storage_bucket` with versioning enabled. [`plans/research/platform-bootstrap-hookpoints.md:10-25`]
  - Live code no longer does that. [`infra/bootstrap/state-backend/main.tf:46-67`]
- Open questions that survive:
  - Bootstrap ordering and output-contract stability are still live constraints. [`plans/research/platform-bootstrap-hookpoints.md:43-78`]

### 3.7 `plans/proposals/platform-bootstrap.md`

- Maps cleanly onto current state:
  - Targets Vultr VKE, Vultr VPC, Vultr Object Storage, and per-environment OpenTofu roots. [`plans/proposals/platform-bootstrap.md:5-37`, `45-62`, `87-100`, `128-170`, `198-215`]
  - Preserves the two-tier model and explicitly defers Flux install and Crossplane. [`plans/proposals/platform-bootstrap.md:22-29`, `72-78`, `173-196`, `221-238`]
  - Exit criteria identify the exact unresolved bootstrap seams: state locking, restore procedure, credential custody, VKE/VPC verification, handoff contract. [`plans/proposals/platform-bootstrap.md:240-317`]
- Stale/displaced:
  - The proposal expects `platform-decisions-overlay.md` to be updated to lock Vultr; that has not happened yet. [`plans/proposals/platform-bootstrap.md:13-20`, `283-317`; `plans/platform-decisions-overlay.md:25-29`]
  - It describes remote-state backing in broader terms than the currently checked-in bootstrap code, which at present only creates the object-storage subscription and outputs. [`plans/proposals/platform-bootstrap.md:128-170`, `202-215`; compare `infra/bootstrap/state-backend/main.tf:46-67`]
- Open questions that survive:
  - First environment choice. [`plans/proposals/platform-bootstrap.md:268-281`]
  - Exact region and node-pool baseline. [`plans/proposals/platform-bootstrap.md:268-281`]
  - State isolation model. [`plans/proposals/platform-bootstrap.md:274-276`]
  - DNS ownership. [`plans/proposals/platform-bootstrap.md:277-278`]
  - Minimal reserved public endpoint vs pure reachability. [`plans/proposals/platform-bootstrap.md:279-281`]

### 3.8 `plans/proposals/vultr-object-storage-fix.md`

- Maps cleanly onto current state:
  - Backend files still use literal `bucket = "humility-tfstate"` and are not dynamically connected to outputs. [`plans/proposals/vultr-object-storage-fix.md:60-66`; `infra/environments/dev/backend.tfbackend:1-13`, `infra/environments/staging/backend.tfbackend:1-13`, `infra/environments/production/backend.tfbackend:1-13`]
  - Bootstrap still uses provider constraint `~> 2.30`. [`plans/proposals/vultr-object-storage-fix.md:22-30`; `infra/bootstrap/state-backend/main.tf:14-19`]
- Stale/displaced:
  - The proposal assumes bootstrap still contains the invalid `vultr_object_storage_bucket` resource. [`plans/proposals/vultr-object-storage-fix.md:6-30`]
  - The live repo has already removed that resource rather than applying the proposal’s provider-bump fix. [`infra/bootstrap/state-backend/main.tf:46-67`, `infra/tests/validate_platform_bootstrap.sh:193-205`]
- Open questions that survive:
  - None for current bootstrap state; this proposal is mostly superseded by the checked-in code path.

### 3.9 `plans/proposals/phase1-foundation.md` — explicitly stale

- Maps cleanly onto current state:
  - Buildkite/Flux separation remains conceptually aligned with later overlay decisions. [`plans/proposals/phase1-foundation.md:107-121`, `191-205`; `plans/platform-decisions-overlay.md:17-23`]
  - Provider-native object storage before self-hosted S3 remains directionally aligned, but provider and implementation details are displaced. [`plans/proposals/phase1-foundation.md:158-173`; compare `plans/platform-decisions-overlay.md:17-23`]
- Stale/displaced:
  - Hetzner hosting, self-managed `k3s`, and `kube-hetzner` substrate are displaced by the Vultr-managed path. [`plans/proposals/phase1-foundation.md:5-18`, `61-67`, `92-105`, `276-296`]
  - Installs Flux, SOPS, and Kong as part of the same bootstrap phase; current three-initiative split explicitly keeps Platform Bootstrap narrower. [`plans/proposals/phase1-foundation.md:31-53`, `107-156`, `191-207`; compare `plans/proposals/platform-bootstrap.md:221-238`]
  - Assumes Hetzner Object Storage. [`plans/proposals/phase1-foundation.md:158-173`, `289-291`]
- Open questions that survive:
  - None that should control INIT-008 proposal work directly; this doc is substrate-stale and should be treated as superseded input, not active design authority.

### 3.10 `plans/proposals/app-cluster-provisioning.md`

- Maps cleanly onto current state:
  - Preserves the same two-tier boundary as Platform Bootstrap. [`plans/proposals/app-cluster-provisioning.md:5-23`, `96-121`]
  - Explicitly says OpenTofu owns platform-tier VPC/network/object storage/VKE creation and state isolation. [`plans/proposals/app-cluster-provisioning.md:105-121`]
  - Confirms Crossplane installation belongs to the later initiative, not bootstrap. [`plans/proposals/app-cluster-provisioning.md:47-53`, `96-121`, `316-323`]
- Stale/displaced:
  - It still treats hosting as not yet formally locked in `platform-decisions-overlay.md`. [`plans/proposals/app-cluster-provisioning.md:299-304`, `319-321`]
- Open questions that survive:
  - First provider-specific composition target is gated on hosting formalization. [`plans/proposals/app-cluster-provisioning.md:299-304`]
  - Supported cluster classes and node-pool override surface remain open. [`plans/proposals/app-cluster-provisioning.md:305-310`]

## 4. Phase 0 acceptance criteria gap analysis

Only the Phase 0 acceptance criteria that materially touch INIT-008 / platform bootstrap are included below.

### 4.1 Criteria selected from the engineering roadmap

Relevant acceptance-criteria source:

- `product-strategy/engineering roadmap.md:102-117`

### 4.2 Gap table

| Phase 0 acceptance criterion | Status | Current repo evidence | What is still missing |
| --- | --- | --- | --- |
| Hosting decision is formalized in `DECISIONS.md` | `PARTIAL` | Live infra tree is already Vultr-specific. [`infra/README.md:1-3`] Engineering roadmap explicitly says formalization in `DECISIONS.md` remains required. [`product-strategy/engineering roadmap.md:5-10`, `product-strategy/engineering roadmap.md:104`] | A formal ratification entry still needs to exist in the decision log or overlay. Current repo evidence still shows split authority. [`plans/platform-decisions-overlay.md:25-29`] |
| Shared test harness is functional, including monorepo install and fixture support | `PARTIAL` | There is at least an infra-specific shell validation surface for platform bootstrap. [`infra/tests/validate_platform_bootstrap.sh:56-341`] | This is not the shared monorepo test harness the roadmap describes; it is a narrow infra acceptance script plus local `tofu validate` surface. [`product-strategy/engineering roadmap.md:109`] |
| Deployable service substrate is operational against the `infra/` baseline | `PARTIAL` | `infra/` now contains bootstrap, shared modules, and three environment roots. [`infra/README.md:7-39`, `infra/modules/platform-network/main.tf:1-50`, `infra/modules/platform-cluster/main.tf:1-81`, `infra/environments/dev/main.tf:1-50`, `infra/environments/staging/main.tf:1-51`, `infra/environments/production/main.tf:1-50`] | Engineering roadmap still says there are no workload manifests, no image/build pipeline, and no completed workload substrate. [`product-strategy/engineering roadmap.md:5-10`, `97-110`] Current INIT-008 surface stops at infra substrate, not deployable services. [`plans/proposals/platform-bootstrap.md:198-215`, `221-238`] |
| Secret management is operational | `MISSING` | Bootstrap marks S3 credentials as sensitive outputs and avoids committing backend creds. [`infra/bootstrap/state-backend/main.tf:60-67`, `infra/tests/validate_platform_bootstrap.sh:307-325`] | No operational secret-management/custody procedure is present in the checked-in INIT-008 surface; platform-bootstrap proposal still treats credential custody as unresolved exit criteria. [`plans/proposals/platform-bootstrap.md:257-260`, `302-304`] |

### 4.3 Criteria intentionally excluded from this table

These Phase 0 criteria were not classified here because they are not direct platform-bootstrap concerns in the current source set:

- Scheduler technology selection. [`product-strategy/engineering roadmap.md:105`]
- Single write-path mutation primitive. [`product-strategy/engineering roadmap.md:106`]
- Audit action/target registry. [`product-strategy/engineering roadmap.md:107`]
- Correlation/causation propagation. [`product-strategy/engineering roadmap.md:108`]
- Authority grant / permission intent / policy version / chapter role / roster foundations. [`product-strategy/engineering roadmap.md:112`]
- Discord interaction framework. [`product-strategy/engineering roadmap.md:113`]
- Graceful degradation mechanics. [`product-strategy/engineering roadmap.md:114`]
- Data portability property. [`product-strategy/engineering roadmap.md:115`]

## 5. Local-verification surface

### 5.1 What can be verified locally without a Vultr deployment

| Target | Command class | What it verifies | Constraints / prerequisites |
| --- | --- | --- | --- |
| `infra/bootstrap/state-backend` | `tofu fmt -check`, `tofu init -backend=false`, `tofu validate` | Syntax, provider resolution, and structural validity of the bootstrap root | Does not prove provider credentials or actual plan/apply behavior. Repo test script also expects this surface. [`infra/tests/validate_platform_bootstrap.sh:83-205`] |
| `infra/environments/dev` | `tofu fmt -check`, `tofu init -backend=false`, `tofu validate` | Syntax, module wiring, provider resolution, and structural validity with backend disabled | Real S3 backend init still needs endpoint replacement. [`infra/environments/dev/backend.tfbackend:1-13`] |
| `infra/environments/staging` | `tofu fmt -check`, `tofu init -backend=false`, `tofu validate` | Same as dev, but staging root | Same backend constraint. [`infra/environments/staging/backend.tfbackend:1-13`] |
| `infra/environments/production` | `tofu fmt -check`, `tofu init -backend=false`, `tofu validate` | Same as dev, but production root | Same backend constraint. [`infra/environments/production/backend.tfbackend:1-13`] |
| `infra/tests/validate_platform_bootstrap.sh` | Shell acceptance script | File presence, fmt, root validation for bootstrap + dev, content assertions, module isolation, and no hardcoded secrets in `.tf` / backend file | Script currently covers bootstrap + `dev`; it does not validate `staging` or `production`. [`infra/tests/validate_platform_bootstrap.sh:56-341`] |

Local observation:

- `tofu validate` succeeded in bootstrap + all three environment roots on 2026-04-23 when run with `-backend=false` and cleaned-up local artifacts afterward.

### 5.2 What a clean `tofu plan` would target

#### Bootstrap root: `infra/bootstrap/state-backend`

Expected clean-plan surface from the checked-in code:

- One `vultr_object_storage.state` creation. [`infra/bootstrap/state-backend/main.tf:46-50`]
- No bucket resource creation from Terraform in current repo state. [`infra/bootstrap/state-backend/main.tf:46-67`]
- Output surface:
  - `bucket_name` = variable/default value. [`infra/bootstrap/state-backend/main.tf:52-54`]
  - `s3_hostname`, `s3_access_key`, `s3_secret_key` from the object-storage subscription. [`infra/bootstrap/state-backend/main.tf:56-67`]

Prerequisites for a real bootstrap `tofu plan`:

- Vultr provider credentials available at runtime. The repo does not commit them. [`infra/bootstrap/state-backend/main.tf:44`, `infra/tests/validate_platform_bootstrap.sh:292-305`]
- Required variables supplied:
  - `object_storage_cluster_id`
  - `object_storage_tier_id`
  [`infra/bootstrap/state-backend/main.tf:22-30`]

#### Environment roots: `infra/environments/{dev,staging,production}`

Expected clean-plan surface from the checked-in code:

- One VPC via `module.network` -> `vultr_vpc.platform`. [`infra/modules/platform-network/main.tf:29-34`]
- One VKE cluster via `module.cluster` -> `vultr_kubernetes.platform`, including embedded default node pool. [`infra/modules/platform-cluster/main.tf:50-64`]
- Root outputs `vpc_id`, `cluster_id`, `endpoint`. [`infra/environments/dev/main.tf:40-50`, `infra/environments/staging/main.tf:41-51`, `infra/environments/production/main.tf:40-50`]

Prerequisites for a real environment `tofu init`/`plan` against the intended backend:

- Bootstrap must have already run so `s3_hostname` exists. [`infra/README.md:20-31`, `plans/research/platform-bootstrap-hookpoints.md:64-78`]
- `REPLACE_AFTER_BOOTSTRAP` must be replaced in the relevant `backend.tfbackend`. [`infra/environments/dev/backend.tfbackend:5-6`, `infra/environments/staging/backend.tfbackend:5-6`, `infra/environments/production/backend.tfbackend:5-6`]
- Backend credentials must be available to the S3 backend at runtime; they are not committed in the file. [`infra/tests/validate_platform_bootstrap.sh:320-325`, `infra/bootstrap/state-backend/main.tf:60-67`]
- Vultr provider credentials must be available for cluster/VPC planning. [`infra/environments/dev/main.tf:17`, `infra/environments/staging/main.tf:18`, `infra/environments/production/main.tf:17`, `infra/modules/platform-network/main.tf:29-34`, `infra/modules/platform-cluster/main.tf:50-64`]

### 5.3 What the state-backend bootstrap needs before environment roots can `init`

| Needed before `tofu init -backend-config=backend.tfbackend` | Why | Evidence |
| --- | --- | --- |
| Successful bootstrap apply of `infra/bootstrap/state-backend` | README and hookpoints require bootstrap first. | `infra/README.md:20-31`, `plans/research/platform-bootstrap-hookpoints.md:64-78` |
| Real S3 endpoint value | Backend file contains `REPLACE_AFTER_BOOTSTRAP`. | `infra/environments/dev/backend.tfbackend:5-6`, `infra/environments/staging/backend.tfbackend:5-6`, `infra/environments/production/backend.tfbackend:5-6` |
| S3 backend credentials available at runtime | Backend files do not commit them. Bootstrap outputs produce them. | `infra/bootstrap/state-backend/main.tf:60-67`, `infra/tests/validate_platform_bootstrap.sh:320-325` |
| Decision on actual bucket existence/creation path | Backend files assume `bucket = "humility-tfstate"`, but current bootstrap root does not create a bucket resource in Terraform. | `infra/environments/dev/backend.tfbackend:2`, `infra/environments/staging/backend.tfbackend:2`, `infra/environments/production/backend.tfbackend:2`, `infra/bootstrap/state-backend/main.tf:46-67` |

### 5.4 Existing local testing approach for module correctness

Checked-in repo surface:

- `infra/tests/validate_platform_bootstrap.sh` is the explicit Terraform/infra acceptance script. [`infra/tests/validate_platform_bootstrap.sh:56-341`]
- The script verifies:
  - file existence. [`infra/tests/validate_platform_bootstrap.sh:56-81`]
  - formatting. [`infra/tests/validate_platform_bootstrap.sh:83-127`]
  - `tofu init -backend=false` + `tofu validate` for bootstrap and dev. [`infra/tests/validate_platform_bootstrap.sh:129-187`]
  - content assertions on bootstrap/module/dev files. [`infra/tests/validate_platform_bootstrap.sh:189-260`]
  - module isolation expectations. [`infra/tests/validate_platform_bootstrap.sh:262-286`]
  - no hardcoded credentials plus sensitive-output checks. [`infra/tests/validate_platform_bootstrap.sh:288-341`]

No checked-in evidence found in the requested source set for:

- `tofu test`
- Terratest / Go-based Terraform tests
- a separate local cluster simulator such as `kind`/`k3d` tied to the current `infra/` code

That means the current verification surface is repo-structure + validation heavy, not provider-emulation or end-to-end bootstrap heavy.

## 6. Known risks and open questions

Tag meanings:

- `BLOCKS_PROPOSAL` = proposal phase cannot credibly close scope without addressing it.
- `BLOCKS_IMPLEMENTATION` = proposal can proceed, but implementation cannot complete without resolving it.
- `INFORMATIONAL` = should be tracked but is not a gate for proposal quality by itself.

### 6.1 Known risks already named in prior material

| Risk | Source | Urgency | Why it matters to INIT-008 |
| --- | --- | --- | --- |
| VKE/VPC attachment ambiguity | `plans/research/hetzner-vs-vultr.md:13-14`, `plans/research/hetzner-vs-vultr.md:39-41`, `plans/research/hetzner-vs-vultr.md:63-70`, `plans/research/hetzner-vs-vultr.md:80`; `plans/proposals/platform-bootstrap.md:247-250`, `307-308` | `BLOCKS_IMPLEMENTATION` | Network topology and environment isolation depend on supported VKE/VPC behavior. |
| State locking on S3-compatible backend is unresolved | `plans/proposals/platform-bootstrap.md:252-256`, `297-300` | `BLOCKS_PROPOSAL` | Exit criteria explicitly gate on working lock acquisition and restore procedure. |
| Credential custody for bootstrap token / kubeconfig handoff | `plans/proposals/platform-bootstrap.md:257-260`, `302-315` | `BLOCKS_PROPOSAL` | Bootstrap has no secrets platform yet; proposal needs a bounded deliverable for custody. |
| Scope creep into Flux / identity / CI / platform services | `plans/proposals/platform-bootstrap.md:244-246`, `221-238` | `INFORMATIONAL` | Important boundary discipline, but already well stated. |
| Per-environment isolation could collapse into shared-state infra | `plans/proposals/platform-bootstrap.md:261-263`, `149-171`, `295-296` | `BLOCKS_PROPOSAL` | State boundary and environment ownership are core bootstrap requirements. |
| Hidden manual console steps break reproducibility | `plans/proposals/platform-bootstrap.md:264-266`, `309-311` | `BLOCKS_IMPLEMENTATION` | This initiative’s value is reproducible bootstrap, not one-off setup. |
| Bucket/resource semantics changed under the repo | `plans/research/vultr-object-storage-fix.md:5-33`; current repo `infra/bootstrap/state-backend/main.tf:46-67` | `INFORMATIONAL` | Prior material about bucket handling is stale; proposal work must not inherit it blindly. |
| Object-storage bucket updates can be destructive if bucket is later Terraform-managed | `plans/research/opentofu-providers.md:84-86` | `INFORMATIONAL` | Relevant if bucket management returns to Terraform later. |

### 6.2 Open questions still waiting for a decision

| Open question | Source | Urgency | Current repo state |
| --- | --- | --- | --- |
| Which environment is the first validated bootstrap target? | `plans/proposals/platform-bootstrap.md:270-271` | `BLOCKS_PROPOSAL` | Repo already defines `dev`, `staging`, `production`, but no document here names the first validation target. |
| Exact region and node-pool baseline for the first platform environment | `plans/proposals/platform-bootstrap.md:272-273` | `BLOCKS_PROPOSAL` | Repo defaults all roots to region `ewr` and fixed node counts, but proposal still treats exact baseline as open. [`infra/environments/dev/main.tf:20-38`, `infra/environments/staging/main.tf:20-39`, `infra/environments/production/main.tf:19-38`] |
| State isolation model: separate instances, separate buckets, or prefix-plus-policy | `plans/proposals/platform-bootstrap.md:274-276` | `BLOCKS_PROPOSAL` | Repo currently uses one bucket name string across all backend files with different keys only. [`infra/environments/dev/backend.tfbackend:2-3`, `infra/environments/staging/backend.tfbackend:2-3`, `infra/environments/production/backend.tfbackend:2-3`] |
| Which DNS records, if any, belong to bootstrap | `plans/proposals/platform-bootstrap.md:277-278` | `BLOCKS_PROPOSAL` | Current repo contains no DNS resources in the INIT-008 surface. [`infra/environments/dev/main.tf:19-50`, `infra/environments/staging/main.tf:20-51`, `infra/environments/production/main.tf:19-50`, `infra/modules/platform-network/main.tf:1-50`, `infra/modules/platform-cluster/main.tf:1-81`] |
| Does bootstrap need a reserved public endpoint or only reachability + network attachment | `plans/proposals/platform-bootstrap.md:279-281` | `BLOCKS_PROPOSAL` | Current repo has no dedicated public-endpoint resource in bootstrap. |
| How backend bucket existence is guaranteed in the current repo path | Inferred from repo mismatch: backend assumes a bucket name; bootstrap root does not create one | `BLOCKS_PROPOSAL` | Current code outputs `bucket_name` but has no bucket resource. [`infra/bootstrap/state-backend/main.tf:52-67`, `infra/environments/dev/backend.tfbackend:2`, `infra/environments/staging/backend.tfbackend:2`, `infra/environments/production/backend.tfbackend:2`] |
| Hosting formalization source of truth: overlay vs README vs decision log | `plans/platform-decisions-overlay.md:25-29`; `infra/README.md:1-3`; `product-strategy/engineering roadmap.md:5-10`, `product-strategy/engineering roadmap.md:104` | `BLOCKS_PROPOSAL` | Proposal phase needs a single authoritative statement so later docs stop contradicting each other. |
| App-cluster proposal’s provider-gated composition target | `plans/proposals/app-cluster-provisioning.md:299-304` | `INFORMATIONAL` for INIT-008, `BLOCKS_IMPLEMENTATION` for downstream work | Boundary is clear, but downstream proposal work still depends on hosting formalization. |

### 6.3 Repo contradictions that should be treated as open questions, not silently papered over

| Contradiction | Why it matters | Evidence | Urgency |
| --- | --- | --- | --- |
| Overlay says hosting open; infra tree is already Vultr | Proposal work needs one authoritative source of truth. | `plans/platform-decisions-overlay.md:25-29`, `infra/README.md:1-3` | `BLOCKS_PROPOSAL` |
| Older Vultr fix docs assume bootstrap bucket resource exists; current code/test assert it does not | Proposal phase must characterize current reality, not stale bug history. | `plans/research/vultr-fix-hookpoints.md:31-67`, `plans/research/vultr-object-storage-fix.md:5-33`, `plans/proposals/vultr-object-storage-fix.md:6-30`, `infra/bootstrap/state-backend/main.tf:46-67`, `infra/tests/validate_platform_bootstrap.sh:193-205` | `BLOCKS_PROPOSAL` |
| Environment backends point at `humility-tfstate`; bootstrap root does not currently create a bucket resource | Remote-state bootstrap completeness is ambiguous in live code. | `infra/environments/dev/backend.tfbackend:2-3`, `infra/environments/staging/backend.tfbackend:2-3`, `infra/environments/production/backend.tfbackend:2-3`, `infra/bootstrap/state-backend/main.tf:46-67` | `BLOCKS_PROPOSAL` |

## 7. Suggested slice decomposition (sketch only)

This is a sketch for proposal-phase refinement, not a commitment.

| Tentative slice | Why it appears separable from the current source set | Evidence anchor |
| --- | --- | --- |
| State-backend bootstrap | Distinct bootstrap root, distinct manual ordering, distinct outputs. | `infra/bootstrap/state-backend/main.tf:1-67`, `infra/README.md:18-31` |
| Remote-state backend handoff into environment roots | All three `backend.tfbackend` files share the same placeholder and bucket pattern. | `infra/environments/dev/backend.tfbackend:1-13`, `infra/environments/staging/backend.tfbackend:1-13`, `infra/environments/production/backend.tfbackend:1-13` |
| Platform VPC module | Isolated shared module with its own inputs/outputs. | `infra/modules/platform-network/main.tf:1-50` |
| Platform VKE module | Isolated shared module with its own inputs/outputs. | `infra/modules/platform-cluster/main.tf:1-81` |
| Environment-root normalization | `dev`, `staging`, `production` roots exist already and are parameterized but not formally justified against proposal open questions. | `infra/environments/dev/main.tf:1-50`, `infra/environments/staging/main.tf:1-51`, `infra/environments/production/main.tf:1-50` |
| Provider/version pin review | Pins are shared across bootstrap + roots and older docs discuss provider-version drift. | `infra/bootstrap/state-backend/main.tf:11-20`, `infra/environments/dev/main.tf:4-15`, `infra/environments/staging/main.tf:5-16`, `infra/environments/production/main.tf:4-15`, `plans/research/platform-bootstrap-hookpoints.md:94-102` |
| Object-storage-fix material reconciliation | Prior research/proposals about bucket handling no longer match live code and should not be silently carried forward. | `plans/research/vultr-fix-hookpoints.md:31-67`, `plans/research/vultr-object-storage-fix.md:5-33`, `plans/proposals/vultr-object-storage-fix.md:6-30`, `infra/bootstrap/state-backend/main.tf:46-67` |
| Hosting-ratification/documentation cleanup | Multiple docs still disagree about whether Vultr is formally locked. | `infra/README.md:1-3`, `plans/platform-decisions-overlay.md:25-29`, `product-strategy/engineering roadmap.md:5-10`, `product-strategy/engineering roadmap.md:104` |

## Proposal-phase priority readout

Highest-priority items for the proposal phase to address, based on current repo evidence:

1. Resolve the source-of-truth conflict on hosting and formalize Vultr in the authoritative decision surface. Evidence: `infra/README.md:1-3`, `plans/platform-decisions-overlay.md:25-29`, `product-strategy/engineering roadmap.md:104`.
2. Resolve the remote-state completeness question created by the current mismatch between backend files assuming `humility-tfstate` and the checked-in bootstrap root creating only the object-storage subscription, not a bucket resource. Evidence: `infra/bootstrap/state-backend/main.tf:46-67`, `infra/environments/dev/backend.tfbackend:2-6`, `infra/environments/staging/backend.tfbackend:2-6`, `infra/environments/production/backend.tfbackend:2-6`.
3. Resolve the state-boundary / locking / credential-custody exit criteria before treating bootstrap as proposal-ready. Evidence: `plans/proposals/platform-bootstrap.md:252-260`, `295-315`.
