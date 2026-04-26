# Audit Risk - INIT-104

## Verdict
LOW

## Summary
Audit risk is LOW. The proposal is PRESENT for every required checklist item:
schema shape, module surface, local-as-first-deployment proof, Infisical
credential flow, raw MinIO install, bucket creation, Vultr Object Storage
contract, same-S3-SDK contract, slice coverage, provider/version pins, and
successor INIT anti-scope.

No PARTIAL or MISSING load-bearing artifacts were found in the current proposal.

## Findings Table
| ID | Category | Severity | Finding | Proposal cite | Required convergence |
|---|---|---:|---|---|---|
| None | Audit checklist | LOW | No checklist gaps found. | `.pipeline/proposal.md:24-29`, `.pipeline/proposal.md:977-1006` | None. |

## Coverage Matrix
| Checklist item | Status | Proposal cite | Notes |
|---|---|---|---|
| `object_storage` block defined exactly | PRESENT | `.pipeline/proposal.md:127-167`, `.pipeline/proposal.md:169-237` | Concrete local/dev YAML and exact JSON Schema addition are included. |
| `additionalProperties: false` enforced | PRESENT | `.pipeline/proposal.md:221-235` | `$defs.objectStorage` sets `additionalProperties: false`. |
| Per-target conditional: `k3d-local` uses MinIO | PRESENT | `.pipeline/proposal.md:132-137`, `.pipeline/proposal.md:172-197`, `.pipeline/proposal.md:240-262` | Local requires `object_storage` and constrains it to the MinIO Service URL, local bucket, and local Infisical path. |
| Per-target conditional: `vultr-vms` uses Vultr OS | PRESENT | `.pipeline/proposal.md:132-137`, `.pipeline/proposal.md:198-218`, `.pipeline/proposal.md:247-260` | Vultr is optional for INIT-104, but if present must be `vultr-object-storage` with validated endpoint/path shape. |
| Schema versioning posture | PRESENT | `.pipeline/proposal.md:127-130` | `schema_version` remains `1` because the schema change is additive. |
| `gitops/channels/local/object-storage/` directory layout enumerated | PRESENT | `.pipeline/proposal.md:59-78`, `.pipeline/proposal.md:99-125` | Full file surface and directory tree are listed with dependency ordering. |
| MinIO Deployment, Service, PVC, ServiceAccount | PRESENT | `.pipeline/proposal.md:69-74`, `.pipeline/proposal.md:284-402` | Raw workload resources are specified. |
| Bucket-creation Job spec | PRESENT | `.pipeline/proposal.md:75-78`, `.pipeline/proposal.md:430-488` | Job resource and command are specified. |
| `InfisicalSecret` CR | PRESENT | `.pipeline/proposal.md:66-68`, `.pipeline/proposal.md:548-577` | Concrete `InfisicalSecret/minio-root` CR is specified. |
| Toolchain installer extension for `mc` | PRESENT | `.pipeline/proposal.md:87-91`, `.pipeline/proposal.md:269-282`, `.pipeline/proposal.md:742-750` | Host `mc` version and checksum are pinned and covered by slice ACs. |
| Storage bootstrap script | PRESENT | `.pipeline/proposal.md:88-89`, `.pipeline/proposal.md:579-601` | `bootstrap-infisical-storage.sh` behavior is specified. |
| Local proof: MinIO Pod Ready | PRESENT | `.pipeline/proposal.md:831-837` | Harness requires Deployment Available and Pod Ready. |
| Local proof: PVC Bound | PRESENT | `.pipeline/proposal.md:831-835`, `.pipeline/proposal.md:850-855` | Harness checks initial and post-restart PVC Bound state. |
| Local proof: `InfisicalSecret` CR reconciled | PRESENT | `.pipeline/proposal.md:831-837` | Harness requires `secrets.infisical.com/ReadyToSyncSecrets=True`. |
| Local proof: target Secret synced with expected keys | PRESENT | `.pipeline/proposal.md:838-844` | Harness checks non-empty target keys and byte equality with Infisical values. |
| Local proof: bucket exists | PRESENT | `.pipeline/proposal.md:845-847` | Harness checks `mc ls local/humility-local-sample`. |
| Local proof: PUT object via S3 SDK, GET, content matches | PRESENT | `.pipeline/proposal.md:638-649`, `.pipeline/proposal.md:848-849` | Round-trip script reads `S3_*`, PUTs, GETs, compares bytes, and deletes. |
| Local proof: idempotent across re-bring-up | PRESENT | `.pipeline/proposal.md:856-858` | Second bring-up, Flux reconcile, Job state, bucket existence, and round trip are required. |
| Infisical flow: `platform-storage` project and path explicit per channel | PRESENT | `.pipeline/proposal.md:519-529`, `.pipeline/proposal.md:579-597`, `.pipeline/proposal.md:695-711` | Local path and Vultr path convention are both specified. |
| Infisical flow: bootstrap script idempotent | PRESENT | `.pipeline/proposal.md:579-593`, `.pipeline/proposal.md:761-766` | Creates or finds resources and leaves existing MinIO root credentials unchanged. |
| Infisical flow: Operator UA credential reuse from INIT-103 | PRESENT | `.pipeline/proposal.md:531-546`, `.pipeline/proposal.md:594-600`, `.pipeline/proposal.md:872-887`, `.pipeline/proposal.md:985-987` | Proposal explicitly reuses `Secret/infisical-operator-auth` and does not create a storage-specific UA Secret. |
| Infisical flow: storage credentials are not in SOPS | PRESENT | `.pipeline/proposal.md:514-517`, `.pipeline/proposal.md:421-428`, `.pipeline/proposal.md:768-770` | SOPS remains bootstrap-only; storage credential files are anti-scope. |
| MinIO install: raw manifests, not Operator or Helm | PRESENT | `.pipeline/proposal.md:264-267`, `.pipeline/proposal.md:779-784`, `.pipeline/proposal.md:936-943` | Helm, HelmRelease, Operator, Tenant, AdminJob, and helm-controller are excluded. |
| MinIO install: image tag pinned | PRESENT | `.pipeline/proposal.md:269-282`, `.pipeline/proposal.md:333-335` | Server image uses a fixed `RELEASE.2025-09-07T16-13-09Z` tag and digest. |
| MinIO install: PVC size and storageClass | PRESENT | `.pipeline/proposal.md:299-310`, `.pipeline/proposal.md:779-784` | PVC is `10Gi` with `local-path`. |
| MinIO install: resources and probes specified | PRESENT | `.pipeline/proposal.md:357-379`, `.pipeline/proposal.md:779-784` | Readiness, liveness, requests, and limits are specified. |
| MinIO install: ServiceAccount and minimum RBAC | PRESENT | `.pipeline/proposal.md:292-297`, `.pipeline/proposal.md:404-411`, `.pipeline/proposal.md:779-784` | ServiceAccounts disable token automount and no Role/RoleBinding is created. |
| Bucket creation: `mc mb --ignore-existing` Job spec explicit | PRESENT | `.pipeline/proposal.md:435-488`, `.pipeline/proposal.md:793-797` | Job command includes `mc alias set`, `mc ready`, and `mc mb --ignore-existing`. |
| Bucket creation: idempotency under Flux re-apply | PRESENT | `.pipeline/proposal.md:490-499`, `.pipeline/proposal.md:856-858` | Completed Job remains stable under re-apply; rerun against an existing bucket succeeds. |
| Bucket creation: Job lifecycle bound | PRESENT | `.pipeline/proposal.md:490-503`, `.pipeline/proposal.md:793-797` | One-shot stable Job, no TTL, not CronJob, not init container, not Operator AdminJob. |
| Vultr OS contract: endpoint pattern specified | PRESENT | `.pipeline/proposal.md:153-165`, `.pipeline/proposal.md:668-684`, `.pipeline/proposal.md:958-964` | Pattern and current `dev` endpoint are specified. |
| Vultr OS contract: credentials at same Infisical path | PRESENT | `.pipeline/proposal.md:153-165`, `.pipeline/proposal.md:695-711` | Uses `platform-storage`, `/object-storage/<channel>/`, and `VULTR_OS_*` keys. |
| Vultr OS contract: per-target endpoint resolution | PRESENT | `.pipeline/proposal.md:253-262`, `.pipeline/proposal.md:713-721` | MinIO uses explicit Service URL; Vultr endpoint is explicit or computed from region. |
| Same-S3-SDK contract: env var contract specified | PRESENT | `.pipeline/proposal.md:610-620`, `.pipeline/proposal.md:638-649` | The five application-facing `S3_*` names are listed and consumed by the proof script. |
| Same-S3-SDK contract: synced K8s Secret structure documented | PRESENT | `.pipeline/proposal.md:622-636`, `.pipeline/proposal.md:702-711` | Local MinIO and future Vultr provider-native keys are mapped to generic `S3_*` names. |
| Slice-level coverage: each of 7 slices has explicit ACs | PRESENT | `.pipeline/proposal.md:723-825` | All seven slices include ACs. |
| Slice-level coverage: each AC locally executable | PRESENT | `.pipeline/proposal.md:733-737`, `.pipeline/proposal.md:746-750`, `.pipeline/proposal.md:761-766`, `.pipeline/proposal.md:779-784`, `.pipeline/proposal.md:793-797`, `.pipeline/proposal.md:807-809`, `.pipeline/proposal.md:819-822` | ACs are schema tests, installer checks, scripts, render/static checks, or local cluster harness checks. |
| Slice-level coverage: dependency DAG acyclic | PRESENT | `.pipeline/proposal.md:739-740`, `.pipeline/proposal.md:752-753`, `.pipeline/proposal.md:768-770`, `.pipeline/proposal.md:786-787`, `.pipeline/proposal.md:799-800`, `.pipeline/proposal.md:811-812`, `.pipeline/proposal.md:824-825` | Dependencies progress from INIT-102/103 through slices 104.01-104.07 without cycles. |
| Slice-level coverage: anti-scope per slice | PRESENT | `.pipeline/proposal.md:739-740`, `.pipeline/proposal.md:752-753`, `.pipeline/proposal.md:768-770`, `.pipeline/proposal.md:786-787`, `.pipeline/proposal.md:799-800`, `.pipeline/proposal.md:811-812`, `.pipeline/proposal.md:824-825` | Every slice has anti-scope. |
| Provider/version reproducibility: MinIO image tag pinned | PRESENT | `.pipeline/proposal.md:269-282`, `.pipeline/proposal.md:977-980`, `.pipeline/proposal.md:1003-1006` | Server image tag and digest are pinned. |
| Provider/version reproducibility: `mc` CLI version pinned | PRESENT | `.pipeline/proposal.md:269-282`, `.pipeline/proposal.md:742-750`, `.pipeline/proposal.md:1003-1006` | Host `mc` release and checksum are pinned. |
| Provider/version reproducibility: init Job image pinned | PRESENT | `.pipeline/proposal.md:269-282`, `.pipeline/proposal.md:461-463`, `.pipeline/proposal.md:793-797`, `.pipeline/proposal.md:1003-1006` | Bucket Job image uses a pinned `quay.io/minio/mc` tag and digest. |
| Anti-scope: all successor INITs 105-117 named | PRESENT | `.pipeline/proposal.md:907-934` | INIT-105 through INIT-117 are all listed. |

## Convergence Statement
INIT-104 audit coverage converges at LOW. All checklist artifacts are PRESENT in
the current proposal, and no load-bearing PARTIAL or MISSING item remains. The
proposal satisfies the local-as-first-deployment bar with a live MinIO,
InfisicalSecret, synced Secret, bucket, SDK PUT/GET/content-match proof, and
idempotent re-bring-up requirement.
