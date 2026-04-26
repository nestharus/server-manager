# Scope Risk — INIT-104

## Verdict
LOW

## Summary

INIT-104's proposal is convergent against its synthesis-bound scope on every
non-negotiable axis. The five hard bounds (S3-storage-layer-only, real-local
S3 round-trip, storage-creds-in-Infisical-not-SOPS, Vultr-OS-config-only,
no-Crossplane / no-Ingress / no-TLS) are each held by named proposal sections,
each with an explicit anti-scope mirror in §12, and each owned by a slice in
§9. All 13 successor Phase 5 INITs (INIT-105 through INIT-117 inclusive) are
named in §12 with bound scope.

Concrete evidence: the local install ships exactly `Namespace/minio-system`,
one `ServiceAccount/minio` (no token automount, no RBAC), one
`PersistentVolumeClaim/minio-data` (10Gi `local-path`), one single-replica
`Recreate` MinIO `Deployment` on `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`,
one `ClusterIP` `Service/minio` exposing port `9000` only, one
`InfisicalSecret/minio-root` materializing `Secret/minio-root`, one Operator
UA Secret `infisical-storage-operator-auth`, one
`ServiceAccount/minio-bucket-bootstrap`, and one one-shot `Job` running
`mc mb --ignore-existing` for the single bucket `humility-local-sample` —
and nothing else (§2, §4, §5, §10, §11). `MINIO_BROWSER=off`, no port 9001,
no Console Service, no Ingress, no TLS asset (§4 lines 414-420). MinIO root
credentials live exclusively in Infisical project `platform-storage`, env
`local`, path `/object-storage/local/`; the proposal explicitly states "INIT-104
does not use SOPS, hardcoded literals, or Kubernetes Secrets committed to Git
for MinIO root credentials" (§6 lines 515-517) and "SOPS remains
bootstrap-only; no storage credential is added to `gitops/bootstrap/`"
(§4 lines 427-428). Vultr Object Storage is contract-only: "INIT-104 does
not provision the subscription, bucket, remote Flux, or remote
`InfisicalSecret`; it defines the contract that later remote INITs must
honor" (§8 lines 661-664), "INIT-104 does not add `vultr_object_storage`
resources under `infra/`" (§8 lines 683-684), and the resolved `vultr-vms`
schema branch contains no `required: ["object_storage"]` (§3 lines 198-218,
optional for remote). The local proof harness in §10 binds nine concrete
assertions including PVC `Bound`, Pod Ready, `InfisicalSecret`
ReadyToSyncSecrets, target Secret keys non-empty, bucket Job Complete, real
PUT/GET byte-compare/DELETE via the five `S3_*` env vars, and re-bring-up
idempotency. §12 names INIT-105 (cert-manager/DNS/TLS), INIT-106 (Crossplane),
INIT-107 (security baseline), INIT-108 (container delivery), INIT-109 (CI/CD),
INIT-110 (Ingress / Console exposure), INIT-111 (data plane / app S3
wrapper), INIT-112 (backup), INIT-113 (app workloads), INIT-114 (Authentik),
INIT-115 (rotation, fine-grained bucket policy, app-scoped credentials),
INIT-116 (tenant isolation), INIT-117 (observability) — all 13 successors,
each with bound scope.

One conscious deferral worth flagging: §6 line 597-600 explicitly defers
credential rotation to INIT-115 ("INIT-104 does not rotate `MINIO_ROOT_USER`,
`MINIO_ROOT_PASSWORD`, Vultr OS access keys, or app scoped credentials.
INIT-104 only provides an idempotent initial seed for local proof"). The
`bootstrap-infisical-storage.sh` script supports `--rotate-ua-secret` for
the Operator UA Secret only; this is operator-credential rotation for the
sync path itself, not workload credential rotation, and is the same shape
INIT-103 used for its UA Secret. Not scope drift.

## Boundary findings

| ID | Risk | Severity | Cite | Recommendation |
|---|---|---|---|---|
| S1 | Initiative-boundary drift to other Phase 5 INITs (cert-manager, Crossplane, Ingress, app workloads, Authentik, observability, backup) | LOW | §1 lines 46-52 explicit non-scope list; §12 lines 887-913 enumerates INIT-105 through INIT-117 each with specific bound scope; §4 lines 414-420 Service ClusterIP only; §11 line 869-873 metrics/dashboards/alerts deferred to INIT-117 | None — every successor INIT named with bound scope; only the sample S3 round-trip script crosses workload boundary, and it is the contract proof, not an app workload (§7 lines 656-658 "the wrapper lands only when INIT-111, INIT-112, or INIT-113 first needs it"). |
| S2 | Real local S3 round-trip drifts toward Ingress-shaped, TLS-shaped, or app-workload-shaped manifests | LOW | §10 lines 819-846 nine assertions: NS exists, PVC Bound, Pod Ready, `InfisicalSecret` ReadyToSyncSecrets, target Secret keys, bucket Job Complete, in-cluster `mc ls`, real S3 SDK PUT/GET byte-compare/DELETE, two-pass idempotency; §10 line 845-846 "No harness step exposes MinIO outside the cluster"; §4 line 396 Service `type: ClusterIP` only | None — assertions are workload + PVC + InfisicalSecret + target Secret + bucket Job + real PUT/GET/DELETE round-trip with byte-fidelity check. No TLS issuance, no Ingress reconciliation, no DNS, no consumer Deployment beyond the bucket Job and harness round-trip Job/`kubectl run`. The host-side `kubectl port-forward` mention (§10 line 845-846) is explicitly *not* the canonical path. |
| S3 | Storage-creds-in-SOPS regression (the INIT-009 / runtime-secret-shape mistake) | LOW | §6 lines 515-517 "INIT-104 does not use SOPS, hardcoded literals, or Kubernetes Secrets committed to Git for MinIO root credentials"; §4 lines 425-428 "The committed GitOps manifests never contain `MINIO_ROOT_USER` or `MINIO_ROOT_PASSWORD` literal values. SOPS remains bootstrap-only; no storage credential is added to `gitops/bootstrap/`"; §6 lines 588-591 "Applies `Secret/infisical-storage-operator-auth` ... never writing those values to Git"; §12 line 925 "No remote Flux, remote Infisical, or remote storage reconciliation" | None — SOPS named-file invariant from INIT-103 is preserved; no SOPS allowlist extension is requested for INIT-104; both MinIO root credentials and the storage-Operator UA credential land via Infisical/`bootstrap-infisical-storage.sh` `kubectl apply`, never Git. The dedicated UA Secret name `infisical-storage-operator-auth` (§6 line 533-538) is intentionally distinct from INIT-103's `infisical-operator-auth` to enforce least-privilege scoping to project `platform-storage`. |
| S4 | Vultr Object Storage scope creep (subscription provisioning, bucket creation, remote Flux/InfisicalSecret install, Terraform module) | LOW | §1 lines 47-49 "It also does not provision Vultr Object Storage subscriptions or buckets, install remote Flux or remote Infisical, create app-scoped S3 credentials"; §8 lines 661-664 "INIT-104 does not provision the subscription, bucket, remote Flux, or remote `InfisicalSecret`"; §8 lines 678-684 "Operator supplied. Created through Vultr dashboard, `vultr-cli`, Vultr API, or a future Terraform/OpenTofu resource outside INIT-104. INIT-104 does not add `vultr_object_storage` resources under `infra/`"; §8 line 685-686 "INIT-104 does not auto-create remote buckets through the S3 SDK on first PUT"; §12 lines 891-893 INIT-106 owns Vultr OS subscription provisioning via Crossplane | None — Vultr surface is exactly schema (optional `object_storage` block on `vultr-vms`), endpoint pattern (`https://<region>1.vultrobjects.com`), Infisical key convention (`VULTR_OS_ACCESS_KEY` / `VULTR_OS_SECRET_KEY`), future Secret name (`vultr-object-storage`), and consumer SDK aliasing — all documentation/contract, no Flux manifests, no Terraform, no API calls. |
| S5 | MinIO HA / multi-tenancy drift (StatefulSet replicas, distributed mode, Tenant CRD, per-tenant buckets) | LOW | §4 line 73, line 318 `replicas: 1`; §4 lines 274-276 single-node `Deployment`; §11 lines 884-885 "single-node MinIO on one `local-path` PVC is real storage for local proof, not HA object storage or backup"; SLICE-104.04 anti-scope line 778 "HA/distributed MinIO"; §12 lines 916-918 "No MinIO Operator. No MinIO Tenant CRD. No Operator AdminJob"; §12 line 911-913 INIT-116 owns tenant isolation (namespace delegation, per-tenant buckets, per-tenant secret paths, scoped Operator RBAC) | None — single-node binding is enforced at three layers: prose (§4, §11), slice acceptance (SLICE-104.04 line 776 "Deployment is one replica"), and static manifest test `test_object_storage_manifests.py` (§2 line 95 "no HelmRelease, no MinIO Operator"). HA upgrade is explicitly an out-of-tree re-author per §11 line 858-860, not an INIT-104 path. |
| S6 | Bucket-creation scope creep (lifecycle policies, encryption, versioning, app buckets, backup buckets, remote buckets) | LOW | §5 lines 433-434 "creates exactly one sample bucket in INIT-104: `humility-local-sample`"; §5 lines 511-513 "INIT-104 creates only the local sample bucket. App buckets and backup buckets are successor work"; §5 lines 481-488 Job command is exactly `mc alias set` + `mc ready` + `mc mb --ignore-existing` (no lifecycle, no encryption, no versioning, no policy); SLICE-104.05 anti-scope line 791 "remote, app, and backup buckets"; §12 line 911 INIT-115 owns "fine-grained bucket policies"; §12 line 906 INIT-112 owns backup buckets | None — bucket Job is a single `mc mb` call against one named bucket. No `mc ilm`, no `mc encrypt`, no `mc version`, no `mc admin policy` in scope. Future bucket creation (per-channel `humility-<channel>-sample` per §5 lines 506-508) follows the same shape; lifecycle/encryption/versioning/policy land with INIT-115/INIT-116 as named in §12. |
| S7 | Channel template extension creep (schema bloat, post-Flux script reshape, alias acceptance, schema_version bump) | LOW | §3 lines 219-237 `object_storage` block is `additionalProperties: false`, 8 fields, all storage/Infisical-binding metadata; §3 line 130 "`schema_version` remains `1` because this is additive"; §3 lines 248-251 "No aliases such as `s3`, `storage`, `endpoint_url`, `secret_namespace`, or provider-specific app fields are accepted"; SLICE-104.01 acceptance line 729 "aliases like `s3`, `endpoint_url`, and `secret_namespace` fail"; §6 lines 571-574 `bootstrap-infisical-storage.sh` is a sibling of INIT-103's `bootstrap-infisical-identity.sh` (matches INIT-102 D8 post-install bash pattern); §2 line 89 `bring-up-local-channel.sh` modification is an ordering insert, not a reshape | None — `object_storage` block follows INIT-103's `infisical` block shape (strict additive, required when `cluster.target == "k3d-local"`, optional for `vultr-vms`); no nested objects beyond the single `objectStorage` def; no compatibility aliases. The bootstrap script is a sibling, not an extension of the INIT-103 identity script — the same single-responsibility shape that earned the INIT-103 LOW. |
| S8 | Anti-scope completeness — every Phase 5 successor INIT named | LOW | §12 lines 887-913 enumerates INIT-105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117 — all 13 successors with bound scope; §12 lines 916-930 plus non-INIT items (no MinIO Operator, no Tenant CRD, no AdminJob, no community chart, no HelmRelease, no helm-controller, no OCIRepository, no Console Service or Ingress, no public exposure, no remote Flux/Infisical/storage reconciliation, no Vultr OS Terraform, no provider-native-only abstraction, no app credentials, no backwards-compatibility aliases) | None — full coverage; INIT-105 also has positive interface contract in §13 (lines 932-952) to prevent ambiguous handoff (local plain HTTP ClusterIP, no Console exposure, Vultr endpoint pattern, provider-side TLS for Vultr). |
| S9 | Slice-boundary clarity — overlap or unowned files | LOW | §9 lines 716-817 slices 104.01–07; each has Files / ACs / Anti-scope / Dependencies; clean dependency chain (01 schema → 02 toolchain → 03 Infisical bootstrap + InfisicalSecret manifest → 04 MinIO manifests → 05 bucket Job → 06 round-trip script → 07 harness + docs) | None — minor co-ownership exists where SLICE-104.03 / 04 / 05 each touch `test_object_storage_manifests.py` (single static-check entrypoint covering all rendered manifests, defensible) and SLICE-104.06 / 07 both list `validate_object_storage_local.sh` (06 introduces the script, 07 wires it into `validate_platform_bootstrap.sh --cluster`). Co-ownership is intentional and dependency order resolves it. |
| S10 | Application-scope leak — INIT-104 sneaks an app S3 wrapper, app-namespace Secrets, or workload manifests | LOW | §1 line 49 explicit "create app-scoped S3 credentials" in non-scope; §7 lines 656-658 "The script is a contract proof, not the future app storage wrapper. The wrapper lands only when INIT-111, INIT-112, or INIT-113 first needs it"; §6 line 599-600 "INIT-104 does not rotate ... app scoped credentials"; §8 line 691-704 future Vultr `Secret/vultr-object-storage` namespace "proposed as `app-runtime`" is *proposed*, not created in INIT-104; §12 lines 901-906 INIT-111 owns "app databases, upload models, S3 wrapper, and application write paths" | None — the round-trip script reads only the five canonical `S3_*` env vars and is explicitly a contract proof; no app-namespace Secret is materialized; the Vultr consumer-namespace and `s3-credentials` Secret name (synthesis D6 line 274-276) are documented as INIT-111/112/113 ownership, not INIT-104 surface. |

## Convergence statement

INIT-104's proposal is convergent against its synthesis-bound scope. The
five non-negotiables (S3-storage-layer-only, real-local S3 round-trip with
PUT+GET+DELETE byte-fidelity, storage-credentials-in-Infisical-not-SOPS,
Vultr-OS-config-only with no Flux/Terraform/API surface, single-node MinIO
with no Operator/Tenant/HA/multi-tenancy) are each held by named proposal
sections, each with explicit anti-scope mirrors in §12, and each enforced at
runtime by either harness assertions in §10, static-manifest tests
referenced in §2 (`test_object_storage_manifests.py`), or schema validation
in §3 (`additionalProperties: false`, conditional `required` for `k3d-local`,
optional for `vultr-vms`, no aliases). All 13 successor Phase 5 INITs are
named in §12 (INIT-105 through INIT-117), and the INIT-105 handoff has a
positive interface contract in §13 that explicitly leaves the local MinIO
endpoint as plain `http://` ClusterIP with no Console exposure, no DNS, and
no certificate placeholders — preventing TLS/Ingress drift. Storage
credentials never enter Git: MinIO root keys live in Infisical project
`platform-storage` env `local` path `/object-storage/local/`, the storage
Operator UA Secret (`infisical-storage-operator-auth`, distinct from
INIT-103's `infisical-operator-auth` for least-privilege scoping) is
generated and `kubectl apply`'d by `bootstrap-infisical-storage.sh`, and
SOPS remains bootstrap-only with no allowlist extension requested. Vultr
Object Storage surface is exactly schema + endpoint pattern + Infisical key
convention + consumer-side `S3_*` aliasing — no provisioning, no remote Flux,
no `vultr_object_storage` Terraform, no auto-create-on-PUT. Bucket creation
is exactly one `mc mb --ignore-existing` Job for one named bucket
(`humility-local-sample`); lifecycle policies, encryption, versioning,
fine-grained policy, and rotation are explicitly deferred to INIT-115 in
§6 and §12. The MinIO install is single-replica `Recreate`, ClusterIP API
port `9000` only, `MINIO_BROWSER=off`, dedicated `ServiceAccount/minio` with
`automountServiceAccountToken: false` and no Role/RoleBinding — no Operator,
no Tenant CRD, no Console, no Ingress, no TLS, no HA. The local proof
harness in §10 asserts real cluster reconciliation including PVC Bound, Pod
Ready, `InfisicalSecret` ReadyToSyncSecrets, target Secret keys non-empty,
bucket Job Complete, real S3 SDK PUT/GET byte-compare/DELETE, and two-pass
idempotency; the harness canonical path is in-cluster (no host network
exposure). Credential rotation is the only conscious deferral (S10's
sibling concern), explicitly pinned to INIT-115; the `--rotate-ua-secret`
flag covers the Operator UA Secret only and matches INIT-103's pattern. No
HIGH or MEDIUM findings were raised; all ten boundary axes are LOW.
Recommend proceeding to the next risk gate.
