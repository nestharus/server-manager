# INIT-008 Phase 5 Hookpoint Research

Date: 2026-04-25.

Branch/worktree: `feat/init-008-platform-bootstrap` at `/home/nes/projects/server-manager/worktrees/init-008-platform-bootstrap`.

Purpose: map the cleared INIT-008 proposal onto the actual repo state before implementation. This is research only. No infra implementation, no cloud calls, and no Discord-visible actions were performed.

Inputs read:
- `.pipeline/proposal.md`
- `.pipeline/synthesis.md`
- `.pipeline/research.md`
- current `infra/`
- prior proposals and prior hookpoint research under `plans/`
- `infra/tests/validate_platform_bootstrap.sh`
- `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md`
- `plans/risk/init-008-{audit,scope,shortcut}.md`

Verification commands run:
- `find infra -maxdepth 4 -type f | sort`
- `rg -n "infra/environments" . --glob '!.git/**'`
- `rg -n "retired-provider|legacy-self-managed" . --glob '!.git/**'`
- `rg -n "humility-tfstate|dev\.yaml|customer\.yaml|internal\.yaml|e2e\.yaml" . --glob '!.git/**'`
- `bash infra/tests/validate_platform_bootstrap.sh`
- local prerequisite checks for `python3`, Python packages, `tofu`, `jq`, `yq`, `uv`, and `pip`

Current repo summary:
- `infra/bootstrap/state-backend/main.tf` exists and validates locally.
- `infra/modules/platform-network/main.tf` exists and is reusable.
- `infra/modules/platform-cluster/main.tf` exists and is reusable.
- `infra/environments/{dev,staging,production}/` still exists.
- `infra/schemas/`, `infra/channels/`, `infra/scripts/`, `infra/templates/`, and `infra/roots/` do not exist yet.
- The current harness passed: 31/31 checks, 0 failed.

BLOCKS_IMPLEMENTATION flags:
- `BLOCKS_IMPLEMENTATION-DOC-DISPOSAL`: this prompt says stale docs should be deleted, not parked. The proposal Section 8 still uses `supersede` and `leave-as-historical` semantics for several stale planning files. Implementation can proceed only if SLICE-025 interprets `supersede` as `DELETE`, keeps only explicitly still-authoritative docs as `MODIFY`, and does not move stale files into an archive directory. If that interpretation is rejected, the proposal needs revision.

Pass-1 closure note: SLICE-025 used DELETE semantics, not archival semantics.
The stale `phase1-foundation*`, `vultr-fix-hookpoints*`,
`vultr-object-storage-fix*`, `platform-bootstrap-hookpoints*`, and
`hetzner-vs-vultr*` plan artifacts are absent from `plans/`; no `archived/`
parking path was introduced for those files.

## 1. Per-Slice File Map

### SLICE-025 - Authority Alignment and Stale Input Disposal

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `DECISIONS.md` | MODIFY | Add ratified Vultr/OpenTofu/channel-pivot decision. | Exists. Current D1-D6 stop at app architecture/OCR; no Phase 5 hosting/channel decision. |
| `infra/README.md` | MODIFY | Replace old environment-triad bootstrap instructions with channel-root/runbook prerequisites. | Exists. Still documents `infra/environments/{dev,staging,production}` and `tofu apply`. |
| `.pipeline/proposal.md` | MODIFY | Keep final proposal as active authority; reconcile stale-doc disposal wording if needed. | Exists. Already updated to channel pivot; Section 8 disposal wording conflicts with delete-not-park rule. |
| `plans/platform-decisions-overlay.md` | MODIFY | Close hosting as Vultr and OpenTofu; remove open hosting entry. | Exists. Still says hosting decision is open and providers research is open. |
| `plans/proposals/platform-bootstrap.md` | MODIFY | Revise as active ancestor or delete if treated as stale replacement by `.pipeline/proposal.md`. | Exists. Contains older Phase 5 framing and provider comparison context. |
| `plans/proposals/vultr-object-storage-fix.md` | DELETE | Superseded provider-bump/bucket-resource fix path. | Exists. Assumes `vultr_object_storage_bucket` bug and provider release path. |
| `plans/proposals/phase1-foundation.md` | DELETE | Retired provider/self-managed proposal conflicts with Vultr/VKE direction. | Exists. Many active-sounding retired-provider foundation claims. |
| `plans/proposals/app-cluster-provisioning.md` | MODIFY | Preserve two-tier boundary but align hosting/channel language. | Exists. Still mentions provider branch ambiguity and app-cluster boundary. |
| deleted provider-comparison research file | MODIFY_OR_DELETE | Proposal says leave historical; prompt says stale docs delete. If kept, must be clearly non-authority evidence. | Exists. Provider comparison; not an active INIT-008 design if Vultr is ratified. |
| `plans/research/vultr-fix-hookpoints.md` | DELETE | Superseded by no-bucket-resource, operator bucket verification decision. | Exists. Describes stale `vultr_object_storage_bucket` hookpoint. |
| `plans/research/vultr-object-storage-fix.md` | DELETE | Superseded research for stale bucket-resource bug state. | Exists. No longer matches live bootstrap root or D3. |
| `plans/research/opentofu-providers.md` | MODIFY | Keep OpenTofu/Vultr provider research while removing stale bucket-resource/host-comparison authority. | Exists. Useful Vultr/OpenTofu evidence plus stale provider comparison sections. |
| `plans/research/platform-bootstrap-hookpoints.md` | DELETE_OR_REPLACE | Old hookpoint research assumes hard environment triad. This file replaces it for INIT-008. | Exists. References `infra/environments/dev` and old backend placeholder flow. |
| `plans/proposals/phase1-foundation-prompt.md` | DELETE | Not in proposal file list, but grep surfaced active retired-provider prompt material. | Exists. Prompt-only artifact with old provider/self-managed premise. |

SLICE-025 notes:
- The proposal file list did not mention `plans/proposals/phase1-foundation-prompt.md`; grep found it.
- No cloud state is touched.
- No old docs should be moved to `archived/`; delete or revise in place.
- `DECISIONS.md` is the durable authority hookpoint for D7+ channel pivot closure.

### SLICE-026 - Channel Contract and Registry Skeleton

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/schemas/platform-channel.schema.json` | CREATE | Source channel YAML contract. | Missing. New `infra/schemas/` directory required. |
| `infra/schemas/platform-channel-resolved.schema.json` | CREATE | Resolved JSON contract consumed by generators/template inputs. | Missing. Must reject unknown schema versions and disallow extra fields. |
| `infra/channels/dev.yaml` | CREATE | Only active INIT-008 channel; carries old dev baseline. | Missing. Values come from old `infra/environments/dev/main.tf` and backend. |
| `infra/channels/fixtures/e2e-from-dev.yaml` | CREATE | Inheritance fixture proving child override plus inherited region. | Missing. Fixture only, not active root. |
| `infra/channels/fixtures/e2e-pr-1234.yaml` | CREATE | Depth-2 inheritance fixture. | Missing. Must inherit from `e2e-from-dev`, then `dev`. |
| `infra/channels/fixtures/dev-pr-123.yaml` | CREATE | Generated/example ephemeral child fixture. | Missing. Must not become an active channel. |
| `infra/channels/fixtures/ephemeral-disabled.yaml` | CREATE | Negative spawn fixture. | Missing. `spawn_platform_channel.py` should fail with `ephemeral_children_disabled`. |
| `infra/channels/fixtures/missing-parent.yaml` | CREATE | Negative resolver fixture. | Missing. Must fail with `missing_parent`. |
| `infra/channels/fixtures/circular-a.yaml` | CREATE | Negative cycle fixture. | Missing. Paired with circular-b. |
| `infra/channels/fixtures/circular-b.yaml` | CREATE | Negative cycle fixture. | Missing. Paired with circular-a. |
| `infra/scripts/resolve_platform_channel.py` | CREATE | Resolve inheritance and emit resolved JSON. | Missing. New `infra/scripts/` directory required. |
| `infra/scripts/spawn_platform_channel.py` | CREATE | Local-only ephemeral materialization proof. | Missing. Must write under `.tmp/`, not `infra/channels/` or `infra/roots/`. |
| `infra/scripts/validate_platform_channels.py` | CREATE | Schema/resolution/cross-field validation. | Missing. Must include id-to-state-key assertion from H1. |
| `infra/README.md` | MODIFY | Document channel registry and schema/spawn boundaries. | Exists. Currently environment-root documentation only. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Add channel validation checks while allowing named temporary failures only where proposal permits. | Exists. Current harness only checks bootstrap, modules, and `environments/dev`. |

SLICE-026 notes:
- The channel pattern reference fits: `id`, `parent`, `exposure`, `tenant`, `allow_ephemeral_children`, and per-platform config map cleanly to proposal fields.
- `customer.yaml`, `internal.yaml`, and active `e2e.yaml` must not be created.
- Python validator must enforce schema plus semantic checks that JSON Schema cannot express.
- Required semantic check from shortcut H1: non-ephemeral resolved `state.key` must equal `channels/{id}/terraform.tfstate`.

### SLICE-027 - Platform Template and Dev Channel Root

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/templates/platform-channel/main.tf` | CREATE | Parameterized template calling existing network and cluster modules. | Missing. Must call `../../modules` relative to template path if used as module source. |
| `infra/templates/platform-channel/variables.tf` | CREATE | Formal variable contract for resolved channel values. | Missing. Must type every variable and mark default/no-default in description. |
| `infra/templates/platform-channel/outputs.tf` | CREATE | Expose channel and module outputs. | Missing. Output set extends old root outputs with channel metadata and sensitive kubeconfig. |
| `infra/templates/platform-channel/versions.tf` | CREATE | Template-level version/provider requirements if needed; no provider/backend blocks. | Missing. Proposal says no provider/backend in template. |
| `infra/roots/channels/dev/main.tf` | CREATE | Active per-channel OpenTofu root with backend/provider/module call. | Missing. Replaces old `infra/environments/dev/main.tf`. |
| `infra/roots/channels/dev/backend.tfbackend` | CREATE | Generated backend config for `channels/dev/terraform.tfstate`. | Missing. Old dev backend uses `infra/dev/terraform.tfstate` and endpoint placeholder. |
| `infra/roots/channels/dev/channel.auto.tfvars.json` | CREATE | Generated resolved channel values for template. | Missing. Must be regen-drift checked. |
| `infra/roots/channels/dev/.terraform.lock.hcl` | CREATE | Provider reproducibility record for active dev root. | Missing. Generated by `tofu init -backend=false`; commit after implementation. |
| `infra/scripts/generate_channel_backend.py` | CREATE | Deterministically produce backend config from resolved JSON. | Missing. Must byte-match committed backend output. |
| `infra/scripts/generate_channel_tfvars.py` | CREATE | Deterministically produce generated tfvars JSON from resolved JSON. | Missing. Must byte-match or canonical-JSON match committed output. |
| `infra/environments/dev/main.tf` | DELETE | Old hard root replaced by channel template + root. | Exists. Source for dev baseline values: `ewr`, `10.40.0.0/20`, 2 nodes. |
| `infra/environments/dev/backend.tfbackend` | DELETE | Old backend key and placeholder replaced by generated dev backend. | Exists. Uses bucket `humility-tfstate`, key `infra/dev/terraform.tfstate`, placeholder endpoint. |
| `infra/environments/staging/main.tf` | DELETE | Non-active hard environment root removed. | Exists. Staging baseline not preserved in INIT-008 active channels. |
| `infra/environments/staging/backend.tfbackend` | DELETE | Non-active hard environment backend removed. | Exists. Key `infra/staging/terraform.tfstate`, placeholder endpoint. |
| `infra/environments/production/main.tf` | DELETE | Non-active hard environment root removed. | Exists. Production baseline deferred to future channel onboarding. |
| `infra/environments/production/backend.tfbackend` | DELETE | Non-active hard environment backend removed. | Exists. Key `infra/production/terraform.tfstate`, placeholder endpoint. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Switch root checks from `environments/dev` to `roots/channels/dev`; assert no `infra/environments`. | Exists. Currently requires old dev files. |

SLICE-027 notes:
- Delete-after-replace is mandatory: create channel schema/dev channel/template/root first, then remove old roots.
- The old dev root contains all active baseline values needed by `dev.yaml` and generated tfvars.
- Staging/production values are not lost as active behavior because proposal defers those channels; if historical values are needed, they are in git history after deletion.
- No compatibility wrappers, symlinks, or forwarding roots.

### SLICE-028 - State-Backend and Remote-State Handoff Contract

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/bootstrap/state-backend/main.tf` | MODIFY | Clarify local-state bootstrap contract and sensitive outputs; avoid bucket-resource implication. | Exists. Creates `vultr_object_storage`, has `bucket_name` variable/output, no bucket resource. |
| `infra/bootstrap/state-backend/.terraform.lock.hcl` | CREATE | Provider reproducibility record for bootstrap root. | Missing. Generated by `tofu init -backend=false`. |
| `infra/roots/channels/dev/backend.tfbackend` | MODIFY | Ensure generated backend uses bucket/key contract and no credentials. | Missing until SLICE-027. Must use `channels/dev/terraform.tfstate`. |
| `infra/README.md` | MODIFY | Document bucket verification, endpoint injection, retirement, restore/locking bounds. | Exists. Currently instructs replacement of `REPLACE_AFTER_BOOTSTRAP` and `tofu apply`. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Assert no bucket-resource expectation, no endpoint placeholder, no credentials. | Exists. Already asserts no `vultr_object_storage_bucket` in bootstrap. |
| `plans/proposals/platform-bootstrap.md` | MODIFY | Align prior active ancestor with explicit handoff/restore posture. | Exists. Older exit criteria include restore procedure exercised. |

SLICE-028 notes:
- Existing bootstrap logic translates cleanly if docs stop saying it creates the bucket.
- Current root already does not declare `vultr_object_storage_bucket`.
- Current comments say "create Object Storage bucket"; revise to subscription/backend handoff language.
- Handoff remains local-only; do not run provider-backed apply.

### SLICE-029 - Provider Locking and Local Verification Harness

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Make final no-credentials validation surface authoritative. | Exists. Passed 31/31 today against old layout. |
| `infra/scripts/validate_platform_channels.py` | MODIFY | Add/confirm validation checks used by harness. | Missing until SLICE-026. Must include schema, resolver fixtures, and H1 cross-field key check. |
| `infra/bootstrap/state-backend/.terraform.lock.hcl` | MODIFY | Ensure lockfile exists and is checked. | Missing until SLICE-028. |
| `infra/roots/channels/dev/.terraform.lock.hcl` | MODIFY | Ensure lockfile exists and is checked. | Missing until SLICE-027. |
| `infra/README.md` | MODIFY | Document prerequisites and final no-credential harness expectations. | Exists. Prerequisites absent. |

SLICE-029 notes:
- This slice is harness consolidation, not new infra semantics.
- It depends on 026/027/028 because the harness references all new artifacts.
- It should remove old harness fallbacks once the new layout exists.

### SLICE-030 - Optional Provider-Backed Plan Runbook and Dev Plan Surface

| Path | Action | Rationale | Existing content notes |
|---|---|---|---|
| `infra/README.md` | MODIFY | Add optional credentialed `tofu plan` runbook and `tofu apply` prohibition. | Exists. Currently instructs `tofu apply` as normal flow. |
| `infra/roots/channels/dev/backend.tfbackend` | MODIFY | Document/use as backend init input for optional plan. | Missing until SLICE-027. Must contain no credentials. |
| `infra/roots/channels/dev/channel.auto.tfvars.json` | MODIFY | Document/use as generated plan input. | Missing until SLICE-027. Must not contain secrets. |
| `infra/tests/validate_platform_bootstrap.sh` | MODIFY | Ensure no allowed failure exceptions remain after final slice. | Exists. Must print and assert `tofu` 1.11 major/minor. |
| `.pipeline/implementation.md` | MODIFY | Later phase notes only if implementation workflow uses it. | Exists. Current notes are older; optional touch only. |

SLICE-030 notes:
- Optional provider-backed plan is not CI and not required without credentials.
- Shortcut H5 should be honored by wording plan as "exits 0 with expected creation plan" rather than implying empty plan.
- No `tofu apply` acceptance path.

## 2. Deletion Plan for `infra/environments/{dev,staging,production}/`

Deletion owner:
- SLICE-027 owns deletion of all six files under `infra/environments/`.
- SLICE-027 also owns removal of the now-empty `infra/environments/` directory.
- SLICE-029 owns validating the absence with `test ! -d infra/environments`.

Delete-after-replace sequence:
1. SLICE-026 creates channel schemas, `infra/channels/dev.yaml`, fixtures, and resolver/validator scripts.
2. SLICE-027 creates `infra/templates/platform-channel/`.
3. SLICE-027 creates `infra/roots/channels/dev/main.tf`.
4. SLICE-027 generates `infra/roots/channels/dev/backend.tfbackend`.
5. SLICE-027 generates `infra/roots/channels/dev/channel.auto.tfvars.json`.
6. SLICE-027 validates dev root with backend disabled.
7. SLICE-027 deletes `infra/environments/dev/main.tf`.
8. SLICE-027 deletes `infra/environments/dev/backend.tfbackend`.
9. SLICE-027 deletes `infra/environments/staging/main.tf`.
10. SLICE-027 deletes `infra/environments/staging/backend.tfbackend`.
11. SLICE-027 deletes `infra/environments/production/main.tf`.
12. SLICE-027 deletes `infra/environments/production/backend.tfbackend`.
13. SLICE-027 removes empty directories.
14. SLICE-029 hardens the harness so the old directory cannot return.

Existing environment files:
- `infra/environments/dev/main.tf`: 50 lines.
- `infra/environments/dev/backend.tfbackend`: 13 lines.
- `infra/environments/staging/main.tf`: 51 lines.
- `infra/environments/staging/backend.tfbackend`: 13 lines.
- `infra/environments/production/main.tf`: 50 lines.
- `infra/environments/production/backend.tfbackend`: 13 lines.
- Total old-environment files to delete: 6.
- Total old-environment file lines removed: 190.

Logic translation check:
- `dev/main.tf` translates cleanly to `dev.yaml` plus template variables.
- `staging/main.tf` does not translate to an active channel because staging is out of INIT-008 scope.
- `production/main.tf` does not translate to an active channel because production/customer is out of INIT-008 scope.
- All three roots share provider/backend/module/output structure; no unique root logic blocks deletion.
- Old backend files contain only bucket/key/region/endpoint flags; dev backend translates to generated channel backend.
- Old `REPLACE_AFTER_BOOTSTRAP` placeholder should not survive.

Cross-references that must be updated or deleted:
- `infra/README.md:29` instructs `cd infra/environments/dev`.
- `plans/proposals/vultr-object-storage-fix.md:62` references environment backend files.
- `product-strategy/engineering research.md:91-94` characterizes old environment roots.
- `plans/research/platform-bootstrap-hookpoints.md:34,41,62,74,97` references old dev root.
- `plans/research/gitops-foundation-hookpoints.md:14,24` references old dev root.
- `plans/research/vultr-fix-hookpoints.md:88-90,130-132` references old roots/backends.

Deletion blockers:
- No OpenTofu logic blocks deletion after `dev` channel root exists.
- `BLOCKS_IMPLEMENTATION-DOC-DISPOSAL` is doc-disposal policy, not infra logic.

## 3. Cross-Reference Grep Results

### `infra/environments`

Active/current references:
- `infra/README.md:29` is active docs; SLICE-025/030 update.
- `product-strategy/engineering research.md:91-94` is research characterization; SLICE-025 should update or mark historical.

Stale proposal/research references:
- `plans/proposals/vultr-object-storage-fix.md:62`.
- `plans/research/platform-bootstrap-hookpoints.md`.
- `plans/research/gitops-foundation-hookpoints.md`.
- `plans/research/vultr-fix-hookpoints.md`.

Risk docs:
- `plans/risk/init-008-audit.md`, `scope.md`, `shortcut.md` mention deletion as risk evidence; keep as phase artifacts.

Pipeline docs:
- `.pipeline/research.md` and `.pipeline/proposal.md` mention old roots as inputs/history and planned deletion; keep as current pipeline evidence.

### Retired provider and self-managed cluster terms

Active authority concern:
- `plans/platform-decisions-overlay.md:27` still says hosting is open.
- `product-strategy/engineering research.md:108,327` still says hosting is not settled.
- `plans/proposals/phase1-foundation.md` remains a full old provider proposal.
- `plans/proposals/phase1-foundation-prompt.md` remains a full old provider prompt.

Historical/provider research:
- The deleted provider-comparison research is useful evidence if clearly non-authoritative.
- `plans/research/opentofu-providers.md` contains useful OpenTofu/Vultr evidence plus stale provider comparison.
- `plans/research/self-hosted-s3.md` includes old provider object-storage comparison.

Non-infra docs:
- `docs/DAEMON_DESIGN.md:178` mentions an old VPS cost note. Not an infra bootstrap authority, but should be removed or marked historical if SLICE-025 sweeps all hosting ambiguity.

Risk docs:
- Many `plans/risk/phase1-*`, `platform-bootstrap-*`, and app-cluster risk files mention old provider history as risk evidence. Do not edit unless SLICE-025 chooses a broader stale-doc deletion.

### `humility-tfstate`

Current live code:
- `infra/bootstrap/state-backend/main.tf:35` default `object_storage_label`.
- `infra/bootstrap/state-backend/main.tf:41` default `bucket_name`.
- `infra/environments/*/backend.tfbackend:2` old backend bucket.
- `infra/tests/validate_platform_bootstrap.sh:259-260` old harness assertion.

Expected after INIT-008:
- Keep `humility-tfstate` in `infra/channels/dev.yaml` as `platform.state.bucket`.
- Keep `humility-tfstate` in generated `infra/roots/channels/dev/backend.tfbackend`.
- Keep bootstrap `bucket_name` default if the README explains operator bucket verification.
- Change key from `infra/dev/terraform.tfstate` to `channels/dev/terraform.tfstate`.
- Harness should assert bucket/key through channel/backend generation, not old environment path.

### `dev.yaml`, `customer.yaml`, `internal.yaml`, `e2e.yaml`

Findings:
- No live channel YAML files exist yet.
- Mentions are in proposal/risk docs as rfqautomation reference and anti-scope assertions.
- `customer.yaml`, `internal.yaml`, and active `e2e.yaml` must remain absent in INIT-008.
- Fixture `e2e-from-dev.yaml` and `e2e-pr-1234.yaml` are allowed under `infra/channels/fixtures/`.

RFQ leakage status:
- No checked-in `customer.yaml`, `internal.yaml`, or active `e2e.yaml` leaked into this repo.
- Existing `k8s/` still uses `dev/staging/production` overlays; that is outside INIT-008 but important for INIT-009 channel alignment.

## 4. Test Harness Changes

Current harness file:
- `infra/tests/validate_platform_bootstrap.sh`
- Current result: 31/31 passed, 0 failed.

Current checks:
1. `bootstrap/state-backend/main.tf` exists.
2. `modules/platform-network/main.tf` exists.
3. `modules/platform-cluster/main.tf` exists.
4. `environments/dev/main.tf` exists.
5. `environments/dev/backend.tfbackend` exists.
6. `tofu fmt -check -recursive infra/` or heuristic indentation fallback.
7. `tofu init -backend=false` for bootstrap.
8. `tofu validate` for bootstrap.
9. `tofu init -backend=false` for `environments/dev`.
10. `tofu validate` for `environments/dev`.
11. Bootstrap declares `vultr_object_storage`.
12. Bootstrap does not declare `vultr_object_storage_bucket`.
13. Bootstrap provider version constraint is `~> 2.30`.
14. Bootstrap required OpenTofu version is `>= 1.8.0`.
15. Network module declares `vultr_vpc`.
16. Cluster module declares `vultr_kubernetes`.
17. Cluster `kube_config` output is sensitive.
18. Dev root uses `backend "s3" {}`.
19. Dev root references `../../modules/platform-network`.
20. Dev root references `../../modules/platform-cluster`.
21. Dev root provider version constraint is `~> 2.30`.
22. Dev root required OpenTofu version is `>= 1.8.0`.
23. Dev backend bucket is `humility-tfstate`.
24. Network module has no `terraform {}` block.
25. Network module has no provider block.
26. Network module has no non-comment hardcoded `dev/staging/production`.
27. Cluster module has no `terraform {}` block.
28. Cluster module has no provider block.
29. Cluster module has no non-comment hardcoded `dev/staging/production`.
30. No hardcoded credentials in any `.tf` file.
31. Bootstrap S3 access/secret outputs are sensitive.
32. Old dev backend contains no actual access/secret credential values.

SLICE-025 harness changes:
- Keep current old-layout checks green or allow only named temporary failures.
- Add/report missing channel schemas, `dev.yaml`, active root lockfile, generated root artifacts as allowed only until later slices.
- Add OpenTofu CLI prerequisite reporting if README mentions it.
- Do not add new OpenTofu roots yet.

SLICE-026 harness changes:
- Run `python infra/scripts/validate_platform_channels.py`.
- Validate both schemas exist.
- Resolve `dev` to `.tmp/dev.resolved.json`.
- Resolve `e2e-from-dev` and assert inherited `platform.region == "ewr"`.
- Assert `e2e-from-dev` child override `cluster.label == "humility-e2e-from-dev-platform"`.
- Resolve `e2e-pr-1234` and assert depth-2 inheritance/override.
- Assert `missing-parent` fails with `missing_parent`.
- Assert `circular-a` fails with `circular_parent`.
- Assert disabled ephemeral spawn fails with `ephemeral_children_disabled`.
- Assert active `customer.yaml`, `internal.yaml`, and `e2e.yaml` are absent.

SLICE-027 harness changes:
- Replace `VALIDATE_ROOTS=(environments/dev)` with `roots/channels/dev`.
- Assert `test ! -d infra/environments`.
- Run `tofu fmt -check` for `infra/roots/channels/dev`.
- Run `tofu init -backend=false` and `tofu validate` for dev channel root.
- Assert template calls existing modules.
- Assert template has no `backend "s3"`.
- Assert root has `backend "s3"`.
- Assert variable contracts in template.
- Regenerate `backend.tfbackend` and compare byte-for-byte.
- Regenerate `channel.auto.tfvars.json` and compare byte-for-byte or canonical JSON.

SLICE-028 harness changes:
- Validate bootstrap root after edits.
- Assert no `vultr_object_storage_bucket` expectation in bootstrap/tests.
- Assert generated dev backend key is `channels/dev/terraform.tfstate`.
- Assert no committed `access_key` or `secret_key` values in generated backend.
- Assert no `endpoint_placeholder` or `REPLACE_AFTER_BOOTSTRAP` under channels/schemas/roots.
- Assert README/runbook documents locking, restore, single-operator posture, object-storage versioning, and post-Phase-5 restore/cleanup.

SLICE-029 harness changes:
- Exit 0 with no credentials.
- Print `tofu version`.
- Assert OpenTofu major/minor `1.11`.
- Validate bootstrap root.
- Validate active dev channel root.
- Validate channel schemas and fixtures.
- Assert no `infra/environments`.
- Assert no committed credentials in `.tf`, `.tfbackend`, `.yaml`, or active generated tfvars.
- Assert active root lockfiles exist.
- Assert generated artifact drift checks.
- Run recursive formatting over active infra roots, template modules, and shared modules.

SLICE-030 harness changes:
- Ensure no allowed failure exceptions remain.
- Keep no-credential baseline green.
- Do not run provider-backed plan unless explicit local credentials/endpoint are present.
- README owns optional credentialed commands.

Obsolete checks to delete:
- File-existence checks for `environments/dev/main.tf`.
- File-existence checks for `environments/dev/backend.tfbackend`.
- Validate-root entry `environments/dev`.
- Assertions using `../../modules/...` from old dev root.
- Old backend bucket assertion scoped to `environments/dev/backend.tfbackend`.
- Old backend credential assertion scoped to `environments/dev/backend.tfbackend`.
- Terraform fallback support is not required by proposal; prefer hard `tofu` prerequisite.

Final harness state after SLICE-030:
- Checks OpenTofu CLI version `1.11.x`.
- Checks Python 3.12.
- Runs channel validator.
- Resolves inheritance fixtures.
- Runs negative fixture checks.
- Generates and compares backend/tfvars artifacts.
- Validates bootstrap root with backend disabled.
- Validates dev channel root with backend disabled.
- Checks formatting across active infra.
- Checks both active lockfiles.
- Checks absence of old environment roots.
- Checks absence of committed secrets.
- Checks no active placeholder endpoint fields.
- Exits 0 without Vultr credentials.

## 5. Duplications and Overlap With Prior Proposals

Disposition principle:
- The prompt overrides archival parking: stale docs are deleted, not moved.
- Revised docs remain only if they continue to be authoritative after edit.
- Historical evidence can remain only if explicitly framed as non-authority; otherwise delete.

Prior proposals:
- `plans/proposals/platform-bootstrap.md`: MODIFY if kept as ancestor; otherwise DELETE if `.pipeline/proposal.md` is the only INIT-008 authority. Current proposal says revise.
- `plans/proposals/vultr-object-storage-fix.md`: DELETE. It is stale and no longer matches D3/no bucket-resource path.
- `plans/proposals/app-cluster-provisioning.md`: MODIFY. Boundary remains useful; hosting/channel assumptions need alignment.
- `plans/proposals/phase1-foundation.md`: DELETE. Conflicts directly with Vultr/VKE channel substrate.
- `plans/proposals/phase1-foundation-prompt.md`: DELETE. Grep surfaced old provider prompt not listed by proposal.

Prior hookpoint/research docs:
- `plans/research/platform-bootstrap-hookpoints.md`: DELETE_OR_REPLACE. This artifact replaces it for INIT-008.
- `plans/research/vultr-fix-hookpoints.md`: DELETE.
- `plans/research/vultr-object-storage-fix.md`: DELETE.
- `plans/research/opentofu-providers.md`: MODIFY if retained as current provider research; strip stale bucket-resource claims and hosting-open framing.
- `plans/research/database-stack.md`: no direct INIT-008 hookpoint. It does not need INIT-008 deletion unless grep later finds infra authority drift.
- Deleted provider-comparison research file: MODIFY_OR_DELETE per doc-disposal blocker; if kept, mark as historical evidence only.

Dangling stale-doc risk:
- If SLICE-025 only adds "superseded" banners, stale assumptions remain grep-visible as quasi-authority.
- That conflicts with the prompt's no-backwards-compat doc rule.
- The implementation prompt should explicitly say "delete stale docs; do not archive."

## 6. Documentation That Needs Updating

| Path | Exists | Slice | Required action |
|---|---:|---|---|
| `AGENTS.md` | yes | none | No infra layout reference found beyond generic architecture. No update required. |
| `DECISIONS.md` | yes | 025 | Add Vultr/OpenTofu/channel pivot decision, likely D7. |
| `infra/README.md` | yes | 025,026,028,029,030 | Major rewrite from environments/apply to channels/local validation/optional plan. |
| `docs/ARCHITECTURE_NOTES.md` | no | none | Missing. Do not create unless user wants a new docs surface. |
| `docs/PATTERNS_FROM_SLICES.md` | no | none | Missing. Channel pattern can live in `DECISIONS.md` and `infra/README.md`. |
| `plans/platform-decisions-overlay.md` | yes | 025 | Close hosting/OpenTofu open items. |
| `product-strategy/engineering research.md` | yes | 025 | Update or mark stale old infra characterization. |
| `docs/DAEMON_DESIGN.md` | yes | 025 optional | Contains old VPS cost note; remove if sweeping hosting ambiguity. |
| `k8s/overlays/{dev,staging,production}` | yes | defer | Not INIT-008. INIT-009 must align Kustomize with channels. |
| `k8s/clusters/{dev,staging,production}` | yes | defer | Not INIT-008. Mention as future GitOps/channel alignment. |

Docs not found:
- `docs/ARCHITECTURE_NOTES.md`
- `docs/PATTERNS_FROM_SLICES.md`
- `product-strategy/tickets/INIT-008.md`
- `product-strategy/tickets/PHASE_5_INDEX.md`

Documentation ownership:
- SLICE-025: decision authority, stale docs, README high-level layout.
- SLICE-026: README channel schema/resolver/spawn fixture boundaries.
- SLICE-028: README backend handoff, locking/restore/retirement.
- SLICE-029: README prerequisites and no-credential harness.
- SLICE-030: README optional credentialed plan path.

## 7. Implementation Prerequisites

Installed locally:
- `python3`: `/usr/bin/python3`, version `3.12.3`.
- `jsonschema`: installed, version `4.10.3`.
- `PyYAML`: installed as import `yaml`, version `6.0.1`.
- `tofu`: `/home/nes/.local/bin/tofu`, version `1.11.5`.
- `jq`: `/home/nes/.local/bin/jq`, version `1.7.1`.
- `uv`: `/home/nes/.local/bin/uv`, version `0.9.9`.
- `pip`: available for Python 3.12.

Not installed:
- `terraform`: not installed; proposal should rely on `tofu`, not fallback.
- `yq`: not installed; avoid adding a `yq` dependency.

Required package implications:
- `PyYAML` is already in root `pyproject.toml`.
- `jsonschema` is installed locally but not declared in root `pyproject.toml`.
- SLICE-026 should add `jsonschema` to project dependencies if scripts import it.
- Standard library `json`, `argparse`, `pathlib`, `subprocess`, and `tempfile` are sufficient for the rest.

Install guidance if missing:
- Python packages: `uv add PyYAML jsonschema` or edit `pyproject.toml` and run `uv sync`.
- OpenTofu: install `tofu` `1.11.5`; harness should assert major/minor `1.11`.
- `jq`: only required if harness uses it; Python can replace most JSON assertions to avoid the dependency.
- `yq`: do not require; use Python/YAML.

Local-only constraint:
- Do not run `tofu apply`.
- Do not require Vultr credentials for baseline harness.
- Do not require S3 endpoint material for baseline harness.
- Optional SLICE-030 plan path may be documented but should not execute by default.

## 8. Risk-Deferred Items to Honor

Audit LOWs:
- A1: SLICE-027 owns explicit variable type/default/no-default contracts.
- A2: SLICE-025 documents `tofu` 1.11.5; SLICE-029 asserts `tofu` 1.11 major/minor.
- A3: SLICE-028 documents restore/cleanup bounds; do not add placeholder `cleanup-state`.
- A4: SLICE-030 documents optional plan; harness remains no-credential green.

Scope LOWs:
- S1: All INIT-009..016 and app-cluster exclusions remain anti-scope; all slices should avoid sister-initiative artifacts.
- S2: SLICE-030 provider-backed plan is optional and never followed by apply.
- S3: SLICE-026 schema stays platform-substrate only; no image tags, routes, TLS, secrets, Buildkite, Flux fields.
- S4: SLICE-026 spawn script is a schema-prover only; README must say it is not PR-preview infrastructure.
- S5: SLICE-026 must assert no active `customer.yaml`, `internal.yaml`, or `e2e.yaml`.
- S6: All slices touch harness; sequence them, do not merge harness edits out of order.
- S7: SLICE-027 produces backend; SLICE-028 documents handoff and validates credentials absence.
- S8: SLICE-030 may be small; acceptable to merge with 029 only if implementation discovers it is trivial and user/proposal workflow permits.
- S9: Acceptance stays local-executable; no hidden deployed-state requirement.
- S10: Bootstrap outputs credentials only after out-of-acceptance apply; INIT-008 produces no real credentials.
- S11: SLICE-025 stale-material disposal must cover all listed docs plus `phase1-foundation-prompt.md`.
- S12: Six-slice decomposition remains right-sized.

Shortcut LOWs:
- H1: SLICE-026 `validate_platform_channels.py` must assert non-ephemeral `state.key == channels/{id}/terraform.tfstate`.
- H2: Defer. Successor initiative lacks INIT id; not in INIT-008 scope. Keep neutral phrasing.
- H3: Defer to INIT-009. Manual S3 endpoint handoff must be replaced, not kept alongside, when SOPS/age lands.
- H4: Defer to post-Phase-5 deployment. Per-channel `main.tf` generation is not INIT-008.
- H5: SLICE-030 README should say `tofu plan` exits 0 with expected creation plan, not an empty clean plan.
- H6 from proposal closure: Defer. Bucket existence remains operator verification, not local automated validation.
- H7 from proposal closure: SLICE-025/029 README prerequisites must name OpenTofu 1.11.5, Python 3.12, and `jq` only if used.
- H8 from proposal closure: SLICE-025 may enumerate temporary harness failures; SLICE-030 removes all exceptions.

## 9. Implementation Order and Conflict DAG

Proposal dependencies:
- SLICE-025: no dependencies.
- SLICE-026: depends on SLICE-025.
- SLICE-027: depends on SLICE-026.
- SLICE-028: depends on SLICE-025 and SLICE-027.
- SLICE-029: depends on SLICE-026, SLICE-027, and SLICE-028.
- SLICE-030: depends on SLICE-028 and SLICE-029.

Recomputed DAG:
- 025 -> 026 -> 027 -> 028 -> 029 -> 030 is the safe linear order.
- 028 cannot run before 027 because it touches `infra/roots/channels/dev/backend.tfbackend`.
- 029 cannot run before 026/027/028 because it references schemas, scripts, roots, and lockfiles.
- 030 cannot run before 029 because it requires final harness state.

Parallelism conflict check:
- 025 and 026 both touch `infra/README.md` and harness if run in parallel; avoid parallel merge.
- 026 and 027 both touch scripts/harness; 027 consumes resolver output; avoid parallel merge.
- 027 and 028 both touch `infra/roots/channels/dev/backend.tfbackend`; avoid parallel merge.
- 028 and 029 both touch bootstrap lockfile, README, and harness; avoid parallel merge.
- 029 and 030 both touch README and harness; avoid parallel merge.

Independent-looking but not safe:
- SLICE-025 stale docs and SLICE-026 schema creation could be coded in separate worktrees only if merged in dependency order and conflicts in `infra/README.md`/harness are resolved deliberately.
- The current proposal's S6 observation is accurate: the harness is touched by every slice and should be treated as a serialized integration file.

Recommended implementation sequence:
1. SLICE-025: authority/doc cleanup and stale deletion policy reconciliation.
2. SLICE-026: schemas, channel files, resolver/spawn/validator, early harness additions.
3. SLICE-027: template/root/generators and delete old environment triad.
4. SLICE-028: state backend handoff docs, lockfile, backend contract assertions.
5. SLICE-029: full no-credential harness hardening and lockfile checks.
6. SLICE-030: optional provider-backed plan runbook and final no-exception harness state.

## 10. Module Fit Verification

Existing module inputs:
- `platform-network`: `environment`, `region`, `v4_subnet`, `v4_subnet_mask`.
- `platform-cluster`: `environment`, `region`, `cluster_label`, `kubernetes_version`, `vpc_id`, `node_plan`, `node_quantity`, `ha_controlplanes`, `enable_firewall`.

Proposal channel fields:
- `channel_id` maps to existing module `environment`.
- `platform.region` maps to both modules `region`.
- `platform.network.v4_subnet` maps to network `v4_subnet`.
- `platform.network.v4_subnet_mask` maps to network `v4_subnet_mask`.
- `platform.cluster.label` maps to cluster `cluster_label`.
- `platform.cluster.kubernetes_version` maps to cluster `kubernetes_version`.
- `platform.cluster.node_plan` maps to cluster `node_plan`.
- `platform.cluster.node_quantity` maps to cluster `node_quantity`.
- `platform.cluster.ha_controlplanes` maps to cluster `ha_controlplanes`.
- `platform.cluster.enable_firewall` maps to cluster `enable_firewall`.

Existing module outputs:
- Network: `vpc_id`, `description`, `v4_subnet`, `v4_subnet_mask`.
- Cluster: `cluster_id`, `endpoint`, `kube_config` sensitive, `firewall_group_id`.

Proposal template outputs:
- `channel_id`: new template output.
- `channel_exposure`: new template output.
- `vpc_id`: available from network module.
- `cluster_id`: available from cluster module.
- `endpoint`: available from cluster module.
- `kube_config`: available and already sensitive in cluster module.
- `firewall_group_id`: available from cluster module.

Fit conclusion:
- No missing module parameter blocks implementation.
- Template can adapt `channel_id` to existing `environment` inputs.
- Template can output `channel_exposure` directly from variable.
- `tenant` is not consumed by current modules; safe to pass as template variable and leave unused only if OpenTofu permits unused variables. Prefer output or local metadata if needed to avoid dead input confusion.
- Existing module comments still say "environment"; optional wording cleanup may be included in SLICE-027, but not required for function.

## 11. Final Hookpoint Summary

Reusable:
- `infra/bootstrap/state-backend/main.tf`
- `infra/modules/platform-network/main.tf`
- `infra/modules/platform-cluster/main.tf`
- current `infra/tests/validate_platform_bootstrap.sh` structure and assertion helpers
- old `infra/environments/dev/main.tf` values as source baseline for `dev.yaml`
- `DECISIONS.md` as authority log

Parallel/stale:
- `infra/environments/{dev,staging,production}/` is a parallel system after the channel root exists; delete in SLICE-027.
- `plans/proposals/vultr-object-storage-fix.md` and matching research/hookpoints are stale.
- Retired provider/self-managed cluster docs are stale as active authority after D7+ decision.

Create-heavy areas:
- Channel schemas.
- Channel YAML + fixtures.
- Channel scripts.
- Platform template.
- Dev channel root.
- Lockfiles.

Main implementation caution:
- The harness is a shared integration file across all slices. Keep slice order linear and make each intermediate allowed-failure state explicit.
